"""WP-119 phase 5 «Le feuilleton»: the serial reads an editorial dossier through the bridge."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from loguru import logger
from sqlalchemy import inspect

from app.db.models.revue_session import RevueSession
from app.db.models.user import User
from app.services.graphic_novel import GraphicNovelScheduler, learner_facing_source
from app.services.revue import feuilleton_bridge
from app.services.revue.evergreen import evergreens_for_week, load_evergreens

# The old ``feuilleton_daily_seed`` keys the graphic-novel seam reads, plus the card tag
# and the dossier's identity. Pinned: a change here is a change to the prompt contract.
PINNED_SNAPSHOT_KEYS = {
    "mode",
    "date",
    "seed_version",
    "title",
    "title_fr",
    "summary",
    "summary_fr",
    "source",
    "url",
    "items",
    "named_people",
    "digest",
    "source_policy",
    "learner_visible",
    "dossier_id",
    "week",
    "topic",
    "evergreen",
}


class _Stop(Exception):
    pass


@pytest.fixture()
def revue_db(db_session, db_engine):
    """``revue_sessions`` is not in the shared test schema; create it for the recency test."""

    created = not inspect(db_engine).has_table(RevueSession.__tablename__)
    if created:
        RevueSession.__table__.create(bind=db_engine, checkfirst=True)
    try:
        yield db_session
    finally:
        if created:
            db_session.rollback()
            RevueSession.__table__.drop(bind=db_engine, checkfirst=True)


def _user(db_session, *, interests: str | None = None) -> User:
    user = User(
        id=uuid4(),
        email=f"bridge-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        interests=interests,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _evergreen():
    return load_evergreens()[0]


def test_prompt_snapshot_keeps_the_old_seed_keys():
    dossier = _evergreen()
    snapshot = feuilleton_bridge.snapshot_for_prompt(dossier)

    assert set(snapshot) == PINNED_SNAPSHOT_KEYS == set(feuilleton_bridge.PROMPT_SNAPSHOT_KEYS)
    assert feuilleton_bridge.LEGACY_SEED_KEYS <= set(snapshot)
    assert snapshot["learner_visible"] is True
    assert snapshot["mode"] == "revue_dossier"
    assert snapshot["title"] == dossier.title_fr
    assert snapshot["summary"] == dossier.summary_fr
    assert snapshot["dossier_id"] == dossier.id
    assert snapshot["evergreen"] is True
    assert snapshot["source"] in {source.name for source in dossier.sources}
    assert snapshot["url"] in {source.url for source in dossier.sources}
    assert snapshot["items"] and all(set(item) == feuilleton_bridge.ITEM_KEYS for item in snapshot["items"])
    assert snapshot["items"][0]["title"] == dossier.title_fr
    # The digest separates facts from attributed readings.
    assert dossier.title_fr in snapshot["digest"]
    assert "Faits" in snapshot["digest"]


def test_source_card_shows_the_same_fields_as_the_snapshot_card():
    dossier = _evergreen()
    card = feuilleton_bridge.source_card(dossier)

    assert set(card) <= feuilleton_bridge.SOURCE_CARD_KEYS
    assert {"title", "source", "url"} <= set(card)
    assert card == learner_facing_source(feuilleton_bridge.snapshot_for_prompt(dossier))
    assert card["title"] == dossier.title_fr
    assert len(card.get("summary", "")) <= 221


def test_thread_seed_is_a_json_snapshot_of_the_dossier():
    dossier = _evergreen()
    seed = feuilleton_bridge.thread_seed(dossier)

    assert seed["title"] == dossier.title_fr
    assert "learner_visible" not in seed
    assert seed["dossier"]["id"] == dossier.id
    assert type(dossier).model_validate(seed["dossier"]) == dossier


def test_dossier_for_feuilleton_prefers_the_least_recent_topic(revue_db):
    db_session = revue_db
    week = "2026-W40"
    offered = feuilleton_bridge.available_dossiers(week)
    assert offered, "the week must have at least the evergreens"
    user = _user(db_session)

    first = feuilleton_bridge.dossier_for_feuilleton(user, week, db=db_session)
    assert first is not None and first.id == offered[0].id

    topics = {dossier.topic for dossier in offered}
    if len(topics) < 2:
        pytest.skip("the week offers a single topic")
    # The learner just discussed the first topic in La Revue: the feuilleton moves on.
    db_session.add(
        RevueSession(
            user_id=user.id,
            week=week,
            dossier_id=first.id,
            status="closed",
            started_at=datetime(2026, 9, 29, 9, tzinfo=UTC),
            closed_at=datetime(2026, 9, 29, 10, tzinfo=UTC),
            state={"events": [{"kind": "choice", "payload": {"kind": "dossier", "snapshot": {"topic": first.topic}}}]},
            plan={},
        )
    )
    db_session.commit()
    second = feuilleton_bridge.dossier_for_feuilleton(user, week, db=db_session)
    assert second is not None and second.topic != first.topic


def test_dossier_for_feuilleton_falls_back_to_evergreens(monkeypatch):
    def _broken(week):  # noqa: ANN001, ANN202
        raise ValueError("bad weekly file")

    monkeypatch.setattr("app.services.revue.weekly.available_for_week", _broken)
    dossier = feuilleton_bridge.dossier_for_feuilleton(object(), "2026-W40")
    assert dossier is not None
    assert dossier.id in {d.id for d in evergreens_for_week("2026-W40")}


def _spy_source_snapshot(monkeypatch, seen: dict):
    original = GraphicNovelScheduler._source_snapshot

    async def _spy(self, **kwargs):  # noqa: ANN001, ANN003, ANN202
        seen.update(kwargs)
        seen["snapshot"] = await original(self, **kwargs)
        raise _Stop

    monkeypatch.setattr(GraphicNovelScheduler, "_source_snapshot", _spy)


def test_create_threads_the_dossier_into_the_source_snapshot(db_session, monkeypatch):
    user = _user(db_session)
    dossier = _evergreen()
    seen: dict = {}
    _spy_source_snapshot(monkeypatch, seen)

    with pytest.raises(_Stop):
        asyncio.run(GraphicNovelScheduler(db_session).create(user=user, dossier=dossier))

    assert seen["dossier"] is dossier
    assert seen["snapshot"] == feuilleton_bridge.snapshot_for_prompt(dossier)
    assert learner_facing_source(seen["snapshot"]) == feuilleton_bridge.source_card(dossier)


def test_create_without_dossier_stays_curated(db_session, monkeypatch):
    user = _user(db_session)
    seen: dict = {}
    _spy_source_snapshot(monkeypatch, seen)

    with pytest.raises(_Stop):
        asyncio.run(GraphicNovelScheduler(db_session).create(user=user))

    assert seen["dossier"] is None
    assert seen["snapshot"]["mode"] == "atelier_curated"
    assert learner_facing_source(seen["snapshot"]) == {}


def test_deprecated_use_news_picks_the_recommended_dossier_and_logs(db_session, monkeypatch):
    user = _user(db_session)
    seen: dict = {}
    _spy_source_snapshot(monkeypatch, seen)
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="WARNING")
    try:
        with pytest.raises(_Stop):
            asyncio.run(GraphicNovelScheduler(db_session).create(user=user, use_news=True))
    finally:
        logger.remove(sink)

    expected = feuilleton_bridge.dossier_for_feuilleton(user, db=db_session)
    assert seen["dossier"] is not None and seen["dossier"].id == expected.id
    assert seen["snapshot"]["learner_visible"] is True
    assert any("use_news=True) is deprecated" in message for message in messages)
