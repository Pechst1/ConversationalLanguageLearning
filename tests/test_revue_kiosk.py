"""WP-119 phase 3 «Le kiosque»: the Papier day, the period, the second Papier, the Relevé
and the operator's refresh.

- the planner deals one ``DayShape.REVUE`` day a week, on or after the learner's seeded
  weekday, never on a tentpole, never drawn by the dice, and plans it as a short classic
  story day inside the budget (the player mounts Le Papier after the ending);
- under ``REVUE_CADENCE=daily`` the period is the ISO date and the kiosk shows the last
  seven days (§12.2);
- a second Papier in the same period is allowed for another story and never moves "filed";
- ``GET /revue/releve`` gives the filed Papiers with their claims, words and source lines;
- ``POST /revue/admin/refresh`` is admin-only and runs the intake with ``refresh=True``.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.revue import get_revue_provider
from app.config import settings
from app.db.models.npc import NPC, NPCMemory
from app.db.models.revue_session import RevueDossier, RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.story import Story
from app.db.models.user import User
from app.main import create_app
from app.services.journey_contracts import DAY_SHAPE_RULES, DayShape, StepKind
from app.services.journey_day_shapes import (
    DayShapeInputs,
    choose_day_shape,
    is_revue_day,
    revue_weekday,
)
from app.services.journey_planner import plan_journey
from app.services.revue import encounter as enc
from app.services.revue import weekly
from app.services.revue.encounter import FakeRevueProvider, RevueEncounter, RevueError
from app.services.revue.evergreen import evergreens_for_week, load_evergreens
from app.services.revue.releve import releve_for
from tests.test_journey_planner import POLITE, SCENE_FITTING, _brief

WEEK = "2026-W40"
MONDAY = date(2026, 9, 28)
PASSWORD = "securepass123"
TABLES = (
    Story.__table__,
    NPC.__table__,
    NPCMemory.__table__,
    RevueSession.__table__,
    RevuePictogram.__table__,
    RevueVignette.__table__,
    RevueDossier.__table__,
)


# ---------------------------------------------------------------------------
# The Papier day (planner)
# ---------------------------------------------------------------------------


def inputs(day: date, **extra) -> DayShapeInputs:
    return DayShapeInputs(user_id=extra.pop("user_id", "learner-1"), local_date=day, revue_available=True, **extra)


def play_week(user_id: str, *, tentpoles: set[date] = frozenset(), missed: set[date] = frozenset()) -> dict[date, DayShape]:
    dealt = False
    previous: DayShape | None = None
    shapes: dict[date, DayShape] = {}
    for offset in range(7):
        day = MONDAY + timedelta(days=offset)
        decision = choose_day_shape(
            inputs(day, user_id=user_id, revue_dealt_this_week=dealt, tentpole=day in tentpoles,
                   previous_shape=previous, missed_previous_day=day in missed)
        )
        shape = decision.shape
        if day in tentpoles:
            # daily_journey serves a tentpole as written, whatever was dealt (WP-111).
            assert shape is not DayShape.REVUE
            shape = DayShape.STANDARD
        shapes[day] = shape
        dealt = dealt or shape is DayShape.REVUE
        previous = shape
    return shapes


@pytest.mark.parametrize("user_id", [f"learner-{n}" for n in range(12)])
def test_one_papier_day_a_week_on_or_after_the_seeded_weekday(user_id: str) -> None:
    shapes = play_week(user_id)
    revue_days = [day for day, shape in shapes.items() if shape is DayShape.REVUE]
    assert len(revue_days) == 1, shapes
    assert revue_days[0].weekday() == revue_weekday(inputs(MONDAY, user_id=user_id))


@pytest.mark.parametrize("user_id", [f"learner-{n}" for n in range(12)])
def test_a_tentpole_on_the_papier_day_moves_it_to_the_next_gap_day(user_id: str) -> None:
    preferred = MONDAY + timedelta(days=revue_weekday(inputs(MONDAY, user_id=user_id)))
    tentpoles = {preferred, preferred + timedelta(days=1)}
    shapes = play_week(user_id, tentpoles=tentpoles)
    revue_days = [day for day, shape in shapes.items() if shape is DayShape.REVUE]
    assert len(revue_days) == 1
    assert revue_days[0] not in tentpoles
    assert revue_days[0] == preferred + timedelta(days=2)


def test_never_on_a_tentpole_never_twice_never_when_off() -> None:
    day = MONDAY + timedelta(days=6)  # Sunday: past every seeded weekday
    assert choose_day_shape(inputs(day)).shape is DayShape.REVUE
    assert choose_day_shape(inputs(day, tentpole=True)).shape is not DayShape.REVUE
    assert choose_day_shape(inputs(day, revue_dealt_this_week=True)).shape is not DayShape.REVUE
    off = DayShapeInputs(user_id="learner-1", local_date=day, revue_available=False)
    assert not is_revue_day(off) and choose_day_shape(off).shape is not DayShape.REVUE
    # A missed day comes back short first; the Papier waits for the next day.
    assert choose_day_shape(inputs(day, missed_previous_day=True, previous_shape=DayShape.STANDARD)).shape is DayShape.SHORT


def test_the_dice_never_draw_a_papier_day() -> None:
    for offset in range(60):
        day = MONDAY + timedelta(days=offset)
        decision = choose_day_shape(inputs(day, revue_dealt_this_week=True, audio_available=True, errata_count=3))
        assert decision.shape is not DayShape.REVUE
        assert DayShape.REVUE not in decision.eligible


def test_the_papier_day_is_a_short_classic_story_day_inside_the_budget() -> None:
    assert DAY_SHAPE_RULES[DayShape.REVUE].max_steps == 5
    for budget in (300, 600, 1200):
        plan = plan_journey(
            scenario=_brief(),
            candidates=[SCENE_FITTING, POLITE],
            budget_seconds=budget,
            day_shape=DayShape.REVUE,
            shape_reason="revue_weekly",
            practice=True,
        )
        plan.validate()
        kinds = [step.kind for step in plan.steps]
        assert plan.day_shape is DayShape.REVUE and plan.practice is False
        assert len(plan.steps) <= 5
        assert kinds[0] is StepKind.SCENE and kinds[-1] is StepKind.RESOLUTION
        assert set(kinds) <= {StepKind.SCENE, StepKind.RECALL, StepKind.RESPOND, StepKind.RESOLUTION}
        assert sum(step.estimated_seconds for step in plan.steps if not step.optional) <= budget


# ---------------------------------------------------------------------------
# Sessions: period, second Papier
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def revue_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, revue_tables) -> Generator[Session, None, None]:
    db_session.execute(delete(RevueDossier))
    db_session.commit()
    yield db_session
    db_session.rollback()
    db_session.execute(delete(RevueDossier))
    db_session.commit()


@pytest.fixture()
def evergreens(monkeypatch) -> None:
    monkeypatch.setattr(enc, "available_dossiers", evergreens_for_week)


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"kiosk-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x",
                cefr_estimate="A2.1", native_language="de", interests="")
    db.add(user)
    db.commit()
    return user


def file_papier(revue: RevueEncounter, user: User, dossier_id: str | None, week: str = WEEK) -> RevueSession:
    row = revue.start(user, week, dossier_id=dossier_id)
    revue.turn(row, "D'accord, je t'aide.")
    revue.close(row)
    return row


def test_a_second_papier_is_another_story_and_never_moves_filed(db: Session, evergreens) -> None:
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    first_id, second_id = (d.id for d in evergreens_for_week(WEEK)[:2])
    first = file_papier(revue, user, first_id)

    with pytest.raises(RevueError) as raised:
        revue.start(user, WEEK)  # the hero / the recommendation: the week is filed
    assert (raised.value.code, raised.value.extra["session_id"]) == ("revue_week_filed", str(first.id))
    with pytest.raises(RevueError) as raised:
        revue.start(user, WEEK, dossier_id=first_id)  # the same story again
    assert raised.value.code == "revue_week_filed"

    second = file_papier(revue, user, second_id)  # another story, from the chip
    assert second.status == "closed" and second.dossier_id == second_id
    offer = revue.week_offer(user, WEEK)
    assert offer.filed is not None and offer.filed.session_id == str(first.id)
    # It counts like any Papier: its close wrote Romy's memory and the cost row.
    assert db.scalar(select(NPCMemory).where(NPCMemory.scene_id == str(second.id))) is not None


def stock(db: Session, period: str, dossiers) -> None:  # noqa: ANN001
    for dossier in dossiers:
        db.add(RevueDossier(id=f"{period}:{dossier.id}", week=weekly.week_of_period(period), period=period,
                            topic=dossier.topic, payload=dossier.model_dump(mode="json"), source_hashes={},
                            checks={}, builder_version="test"))
    db.commit()


def test_daily_cadence_uses_the_date_as_the_period(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_CADENCE", "daily")
    today = weekly.period_for(datetime.now(UTC))
    assert weekly.is_daily_period(today)
    stock(db, today, load_evergreens()[:3])
    user = make_user(db)
    revue = RevueEncounter(db, FakeRevueProvider())
    row = revue.start(user)
    assert row.week == today
    offer = revue.week_offer(user)
    assert offer.week.iso == today and offer.week.label.startswith("Semaine ")
    assert offer.resume is not None and offer.resume.session_id == str(row.id)
    # One active Papier per *day*: another day is free while this one is open.
    tomorrow = (date.fromisoformat(today) + timedelta(days=1)).isoformat()
    assert revue.start(user, tomorrow).week == tomorrow
    revue.close(row)
    assert releve_for(db, user).entries[0].period_label.startswith("Semaine ")


def test_the_daily_kiosk_shows_the_last_seven_days(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_CADENCE", "daily")
    day = date(2026, 10, 3)
    pool = load_evergreens()[:3]
    for offset, dossier in zip((0, 3, 8), pool, strict=True):
        stock(db, (day - timedelta(days=offset)).isoformat(), [dossier])
    kiosk = enc.available_dossiers(day.isoformat(), db)
    assert [d.id for d in kiosk] == [pool[0].id, pool[1].id], "newest first, nothing older than seven days"
    assert weekly.period_for(day) == "2026-10-03"
    assert weekly.period_for(day, cadence_name="weekly") == WEEK
    assert weekly.week_of_period("2026-10-03") == WEEK


def test_the_weekly_kiosk_reads_the_intakes_rows(db: Session) -> None:
    dossier = evergreens_for_week(WEEK)[0]
    db.add(RevueDossier(id=f"2026-w40:{dossier.id}", week=WEEK, period=WEEK, topic=dossier.topic,
                        payload=dossier.model_dump(mode="json"), source_hashes={}, checks={"evergreen_top_up": True},
                        builder_version="test"))
    db.commit()
    kiosk = enc.available_dossiers(WEEK, db)
    assert kiosk[0].id == dossier.id
    assert [d.id for d in enc.available_dossiers(WEEK)] != [d.id for d in kiosk] or len(kiosk) >= 3


# ---------------------------------------------------------------------------
# The Relevé and the refresh, over HTTP
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db: Session, evergreens) -> Iterator[TestClient]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_revue_provider] = lambda: FakeRevueProvider()
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"kiosk-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "target_language": "fr",
                                               "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


@pytest.mark.parametrize(("method", "path"), [("get", "/api/v1/revue/releve"), ("post", "/api/v1/revue/admin/refresh")])
def test_the_new_routes_are_404_while_the_revue_is_off(api: TestClient, monkeypatch, method: str, path: str) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert getattr(api, method)(path).status_code == 404


def test_the_releve_lists_filed_papiers_with_claims_words_and_sources(api: TestClient, db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    headers, _ = login(api)
    assert api.get("/api/v1/revue/releve", headers=headers).json() == {"entries": []}
    dossier = evergreens_for_week(WEEK)[0]
    started = api.post("/api/v1/revue/sessions", headers=headers, json={"week": WEEK, "dossier_id": dossier.id})
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    closed = api.post(f"/api/v1/revue/sessions/{session_id}/close", headers=headers)
    assert closed.status_code == 200, closed.text
    kept = closed.json()["closing"]["kept"]

    body = api.get("/api/v1/revue/releve", headers=headers).json()
    (entry,) = body["entries"]
    assert entry["session_id"] == session_id and entry["period"] == WEEK and entry["period_label"] == "Semaine 40"
    assert entry["title_fr"] == dossier.title_fr and entry["second"] is False
    assert [c["id"] for c in entry["claims"]] == [c["id"] for c in kept["claims"]]
    for claim in entry["claims"]:
        assert claim["source"]["name"] and claim["source"]["url"].startswith("http")
        assert len(claim["source"]["published_at"]) == 10
        if claim["kind"] != "fact":
            assert claim["attributed_to"]
    assert [w["fr"] for w in entry["words"]] == [w["fr"] for w in kept["words"]]
    assert entry["sources"], "the dispatch's source line"


def test_refresh_is_admin_only_and_runs_the_intake_with_refresh(api: TestClient, db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    seen: dict = {}

    def fake_intake(*, refresh: bool = False, period: str | None = None, now=None) -> dict:  # noqa: ANN001
        seen.update(refresh=refresh, period=period)
        return {"status": "built", "period": period or WEEK, "built": ["x"]}

    monkeypatch.setattr("app.tasks.revue.intake_now", fake_intake)
    headers, email = login(api)
    assert api.post("/api/v1/revue/admin/refresh", headers=headers).status_code == 403
    user = db.scalar(select(User).where(User.email == email))
    user.role = "admin"
    db.commit()
    response = api.post("/api/v1/revue/admin/refresh?period=2026-W40", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "built"
    assert seen == {"refresh": True, "period": "2026-W40"}
    assert api.post("/api/v1/revue/admin/refresh?period=last-week", headers=headers).status_code == 422


def test_the_beat_runs_every_morning_and_the_task_is_off_with_the_flag(monkeypatch) -> None:
    from app.celery_app import celery_app
    from app.tasks import revue as task

    entry = celery_app.conf.beat_schedule["revue-weekly-intake"]
    assert entry["task"] == "app.tasks.revue.weekly_intake"
    assert entry["schedule"].hour == {5} and entry["schedule"].minute == {0}
    assert celery_app.conf.timezone in {"Europe/Paris", "Europe/Berlin"}
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert task.weekly_intake() == {"status": "disabled"}
