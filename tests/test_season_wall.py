"""Le mur du Mistral: the season's objects come from the pages the learner read,
and an object shows a choice only once the learner has made it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.living_story import ENGINE_VERSION_PREFIX
from app.services.season.wall import marks_of, season_wall


@pytest.fixture()
def active_user(db_session):
    user = User(email=f"wall-{uuid4().hex[:8]}@example.com", hashed_password="test", native_language="en", target_language="fr", is_active=True)
    db_session.add(user)
    db_session.flush()
    return user


def _thread(db, user, flags=None):
    thread = SerialThread(
        user_id=user.id,
        status="active",
        world_bible={},
        state={"living_story": {"season_script": {"flags": flags or {}}}},
        news_seed={},
        current_episode_index=1,
    )
    db.add(thread)
    db.flush()
    return thread


def _page(db, user, thread, segment, *, status="completed", season="s1"):
    # pages in one transaction share now(): give each its own time, in the order written
    _page.count = getattr(_page, "count", 0) + 1
    scene = GraphicNovelScene(
        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=_page.count),
        user_id=user.id,
        serial_thread_id=thread.id,
        episode_index=1,
        status=status,
        cadence="daily",
        title=segment,
        brief="",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        script_payload={"season": {"id": season, "segment": segment, "kind": "tentpole"}},
        recap_payload={},
        cache_key=f"wall-{uuid4().hex}",
        prompt_version=f"{ENGINE_VERSION_PREFIX}test",
        image_model="test",
        image_quality="medium",
    )
    db.add(scene)
    db.flush()
    return scene


def test_no_story_yet_is_an_empty_wall(db_session, active_user):
    assert season_wall(db_session, active_user) == {"season_id": None, "through": 0, "pages": {}, "marks": {}}


def test_the_wall_reaches_as_far_as_the_pages_read(db_session, active_user):
    thread = _thread(db_session, active_user, {"s1.fire_photo": "margaux", "s1.promise_gus": "half", "s1.lila_has_key": True})
    t1 = _page(db_session, active_user, thread, "t1")
    _page(db_session, active_user, thread, "t1")
    _page(db_session, active_user, thread, "g2")
    _page(db_session, active_user, thread, "t3", status="ready")

    wall = season_wall(db_session, active_user)
    assert wall["season_id"] == "s1"
    # a gap of part 2 means part 2's page was read; the unread t3 counts for nothing
    assert wall["through"] == 2
    assert wall["pages"] == {"t1": str(t1.id)}
    # only the choices an object shows, never any other flag
    assert wall["marks"] == {"s1.fire_photo": "margaux", "s1.promise_gus": "half"}


def test_an_epilogue_page_means_the_whole_season(db_session, active_user):
    thread = _thread(db_session, active_user)
    _page(db_session, active_user, thread, "t8")
    _page(db_session, active_user, thread, "e1")
    assert season_wall(db_session, active_user)["through"] is None


def test_a_mark_is_only_a_choice_the_learner_made():
    assert marks_of(None) == {}
    assert marks_of({"flags": {"s1.fire_photo": "wall"}}) == {"s1.fire_photo": "wall"}
    assert marks_of({"flags": {"s1.fire_photo": "elsewhere", "s1.promise_gus": ""}}) == {}
