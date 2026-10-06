"""WP-119 phase 3 «Le kiosque»: the weekly intake, end to end on the fixture corpus.

``tests/fixtures/revue_rss/``: five French feeds of a fictitious outlet group on
``https://kiosque.test`` (served by ``httpx.MockTransport``), their article pages and a
``robots.txt``. The fake dossier provider builds from the article sentences, so the run is
deterministic and offline.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.db.models.revue_session import RevueDossier
from app.services.revue import checks, intake, weekly
from app.services.revue.builder import FakeDossierProvider
from app.services.revue.evergreen import evergreens_for_week
from app.services.revue.sources import extract_text

FIXTURES = Path(__file__).parent / "fixtures" / "revue_rss"
WEEK = "2026-W40"
TODAY = date(2026, 10, 2)
REGISTRY = json.loads((FIXTURES / "registry.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dossier_table(db_engine) -> Generator[None, None, None]:
    created = not inspect(db_engine).has_table(RevueDossier.__table__.name)
    if created:
        RevueDossier.__table__.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        if created:
            RevueDossier.__table__.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, dossier_table) -> Generator[Session, None, None]:
    # The intake commits; every test starts and ends on an empty kiosk.
    db_session.execute(delete(RevueDossier))
    db_session.commit()
    yield db_session
    db_session.rollback()
    db_session.execute(delete(RevueDossier))
    db_session.commit()


class Web:
    """The fixture host: feeds, articles, robots.txt; every request is recorded."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=(FIXTURES / "robots.txt").read_text(encoding="utf-8"))
        if path.startswith("/feeds/"):
            feed = FIXTURES / path.rsplit("/", 1)[-1]
            return httpx.Response(200, text=feed.read_text(encoding="utf-8")) if feed.exists() else httpx.Response(404)
        page = FIXTURES / "articles" / path.rsplit("/", 1)[-1]
        if page.exists():
            return httpx.Response(200, text=page.read_text(encoding="utf-8"))
        return httpx.Response(404)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def article_texts() -> dict[str, str]:
    """URL → extracted text, as the builder saw it (the test re-runs the checks with it)."""

    texts: dict[str, str] = {}
    host = "https://kiosque.test"
    for feed in FIXTURES.glob("*.xml"):
        for link in __import__("re").findall(r"<link>(.*?)</link>", feed.read_text(encoding="utf-8")):
            page = FIXTURES / "articles" / link.rsplit("/", 1)[-1]
            if link.startswith(host) and page.exists():
                texts[link] = extract_text(page.read_text(encoding="utf-8"))
    return texts


def run(db: Session, web: Web, *, sources=None, refresh: bool = False, target: int = 6, provider=None):
    return intake.run_intake(
        db,
        WEEK,
        refresh=refresh,
        provider=provider or FakeDossierProvider(),
        client=web.client(),
        sources=REGISTRY if sources is None else sources,
        target=target,
        today=TODAY,
        fetch_enabled=True,
    )


def stored(db: Session, period: str = WEEK) -> list[RevueDossier]:
    return list(db.scalars(select(RevueDossier).where(RevueDossier.period == period).order_by(RevueDossier.built_at)))


# ---------------------------------------------------------------------------


def test_fixture_rss_gives_six_dossiers_that_pass_every_check(db: Session) -> None:
    web = Web()
    report = run(db, web)
    assert report.status == "built"
    assert len(report.built) == 6, report.as_dict()
    assert report.evergreen_top_up == []
    rows = stored(db)
    assert len(rows) == 6
    texts = article_texts()
    for row in rows:
        dossier = weekly.EditorialDossier.model_validate(row.payload)
        assert dossier.week == WEEK and not dossier.evergreen
        assert len(dossier.claims) >= checks.MIN_ANCHORED_CLAIMS
        source_texts = {source.id: texts[source.url] for source in dossier.sources}
        results = checks.run_dossier_checks(dossier, source_texts=source_texts, week=WEEK)
        assert checks.passed(results), checks.failures(results)
        assert row.checks["passed"] is True
        assert row.checks["fetch"], "the fetch status per source is kept"
        # §12.3: quotes and a hash only — never the article text.
        assert set(row.source_hashes) == {source.id for source in dossier.sources}
        assert all(len(value) == 64 for value in row.source_hashes.values())
        raw = json.dumps(row.payload, ensure_ascii=False)
        assert "Abonnez-vous" not in raw and "mentions légales" not in raw
        assert len(dossier.angles) == 2 and dossier.places and dossier.vignette_object_fr


def test_the_week_spreads_two_two_one_one(db: Session) -> None:
    report = run(db, Web())
    groups = {topics: 0 for topics, _ in intake.TOPIC_SPREAD}
    for row in stored(db):
        for topics, _ in intake.TOPIC_SPREAD:
            if row.topic in topics:
                groups[topics] += 1
    assert list(groups.values()) == [2, 2, 1, 1], report.topics
    assert intake.slots_for(6) == [2, 2, 1, 1]
    assert sum(intake.slots_for(4)) == 4 and sum(intake.slots_for(9)) == 9


def test_sensitive_and_foreign_items_never_become_candidates() -> None:
    web = Web()
    candidates, statuses = intake.fetch_candidates(today=TODAY, client=web.client(), sources=REGISTRY)
    titles = " ".join(c.title for c in candidates)
    assert "fusillade" not in titles.lower()
    assert "City council" not in titles
    assert all(status.startswith("ok:") for status in statuses.values())
    assert {c.published_at for c in candidates} <= {date(2026, 9, d) for d in (29, 30)} | {date(2026, 10, d) for d in (1, 2)}


def test_a_thin_feed_is_topped_up_with_the_weeks_evergreens(db: Session) -> None:
    politics_only = [row for row in REGISTRY if row["id"] == "kiosque_politique"]
    report = run(db, Web(), sources=politics_only)
    assert len(report.built) == 1
    expected = min(6, 1 + len(evergreens_for_week(WEEK)))
    assert len(report.built) + len(report.evergreen_top_up) == expected
    assert set(report.evergreen_top_up) <= {d.id for d in evergreens_for_week(WEEK)}
    rows = stored(db)
    assert sum(1 for row in rows if row.checks.get("evergreen_top_up")) == len(report.evergreen_top_up)
    # The kiosk the chooser reads is the intake's, top-up included.
    kiosk = weekly.load_week(WEEK, db)
    assert len(kiosk) == expected
    assert kiosk[0].id == report.built[0]


def test_a_built_week_is_kept_unless_refreshed(db: Session) -> None:
    first = run(db, Web())
    again = run(db, Web())
    assert again.status == "kept" and again.built == []
    refreshed = run(db, Web(), refresh=True, target=4)
    assert refreshed.status == "built"
    assert len(stored(db)) == 4
    assert set(refreshed.built) <= set(first.built)


def test_load_week_reads_the_table_first_and_the_files_second(db: Session) -> None:
    files = weekly.load_week(WEEK)
    assert files and all(d.id.startswith("2026-w40-") for d in files)
    assert [d.id for d in weekly.load_week(WEEK, db)] == [d.id for d in files], "no rows: the files"
    report = run(db, Web())
    from_table = weekly.load_week(WEEK, db)
    assert [d.id for d in from_table] == report.built
    assert weekly.load_week(WEEK) == files, "without a session nothing changes"
    assert intake.dossiers_for(WEEK, "politics", db=db)[0].topic == "politics"


def test_a_story_whose_build_fails_gives_its_place_to_the_next_one(db: Session) -> None:
    class FailsOnMetro(FakeDossierProvider):
        def build_dossier(self, context):  # noqa: ANN001, ANN201
            if any("ligne 14" in item["title"] for item in context["items"]):
                raise RuntimeError("model down")
            return super().build_dossier(context)

    report = run(db, Web(), provider=FailsOnMetro())
    assert len(report.built) == 6
    assert any("provider_failed" in reasons for reasons in report.rejected.values())
    assert any("pistes" in dossier_id for dossier_id in report.built), "the next city story took the slot"


def test_registry_carries_a_fetch_policy_and_the_new_feeds() -> None:
    rows = intake.registry()
    assert all(row.get("fetch_policy") in {"allows", "refuses"} for row in rows)
    topics = {intake.topic_for("", row.get("topic_tags") or ()) for row in rows}
    assert {"culture", "food", "sport", "city"} <= topics
    refusing = {row["id"] for row in rows if row["fetch_policy"] == "refuses"}
    assert "france24_france" in refusing
