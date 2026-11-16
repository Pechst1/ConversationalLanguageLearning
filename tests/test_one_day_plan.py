"""S2.1 · one stored day plan: made with the day, written by events, compared in the shadow.

The plan lives on the journey row (``plan_selection["day_plan"]``). Its step status is
written by the transitions that already happen (the journey planned, paused, resumed,
finished or ended early; a Forge séance opened or finished; the words marked done),
never recomputed on read. ``DAY_PLAN_STORED`` off: nothing is stored or compared.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.daily_journey import DailyJourney
from app.services import day_plan
from app.services.daily_session import SessionInputs, session_view
from tests import test_journey_end_to_end as support
from tests.test_journey_end_to_end import (
    CAFE_WORDS,
    Clock,
    Driver,
    key,
    learner_id,
    register,
    seed_due_vocabulary,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

CAFE_ANSWER = "Bonjour, je voudrais un café en terrasse, s'il vous plaît."


@pytest.fixture()
def plan_stored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", True)


def _plan_of(db: Session, journey_id: str) -> day_plan.DayPlan | None:
    row = db.get(DailyJourney, uuid.UUID(journey_id))
    db.refresh(row)
    return day_plan.read_plan(row)


def _statuses(plan: day_plan.DayPlan) -> dict[str, str]:
    return {step.kind: step.status for step in plan.steps}


def _learner(client: TestClient, db: Session) -> tuple[dict[str, str], uuid.UUID]:
    email = f"s21-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(client, email)
    user_id = learner_id(db, email)
    seed_due_vocabulary(db, user_id, CAFE_WORDS)
    return headers, user_id


def _revision_call(client: TestClient, driver: Driver, action: str) -> None:
    response = client.post(
        f"/api/v1/daily-journeys/{driver.id}/{action}",
        headers=driver.headers,
        json={"mutation_id": key(), "expected_revision": driver.revision},
    )
    assert response.status_code == 200, response.text
    driver.journey = response.json()


def _forge_session(db: Session, user_id: uuid.UUID, *, status: str = "in_progress") -> Any:
    from app.db.models.atelier import AtelierSession
    from app.services import daily_journey as service

    row = AtelierSession(
        user_id=user_id,
        selected_concept_ids=[],
        quote_payload={"forge": {"concept_id": 1}},
        status=status,
        recap_payload={},
        completed_at=service._utcnow() if status != "in_progress" else None,
    )
    db.add(row)
    db.commit()
    return row


# ---------------------------------------------------------------------------
# Pure: the record and its events
# ---------------------------------------------------------------------------


def _fresh_plan() -> day_plan.DayPlan:
    return day_plan.new_plan(
        journey_id="j", local_date="2026-03-10", scene_seconds=420, grammar_items=12, words_new=17, words_reviews=3
    )


def test_a_new_plan_is_the_three_working_steps_in_the_owners_order() -> None:
    plan = _fresh_plan()
    assert [step.kind for step in plan.steps] == ["scene", "grammar", "words"]
    assert [step.id for step in plan.steps] == ["2026-03-10:scene", "2026-03-10:grammar", "2026-03-10:words"]
    assert _statuses(plan) == {"scene": "todo", "grammar": "todo", "words": "todo"}
    assert plan.step("grammar").size == 12 and plan.step("grammar").minutes == 5
    assert plan.step("words").size == 20
    assert plan.minutes_left == 7 + 5 + plan.step("words").minutes
    assert day_plan.DayPlan.from_json(plan.to_json()) == plan


@pytest.mark.parametrize(
    ("event", "kind", "moved", "to"),
    [
        ("step_started", "scene", "scene", "doing"),
        ("step_finished", "grammar", "grammar", "done"),
        ("step_skipped", "scene", "scene", "skipped"),
        ("words_done", "words", "words", "done"),
    ],
)
def test_each_event_moves_exactly_one_steps_status(event: str, kind: str, moved: str, to: str) -> None:
    plan = _fresh_plan()
    before = _statuses(plan)
    assert day_plan.apply_event(plan, event, kind) is True  # type: ignore[arg-type]
    after = _statuses(plan)
    assert [k for k in after if after[k] != before[k]] == [moved]
    assert after[moved] == to


def test_the_same_finish_twice_changes_nothing_the_second_time() -> None:
    plan = _fresh_plan()
    assert day_plan.apply_event(plan, "step_finished", "grammar", key="forge:done:a") is True
    snapshot = plan.to_json()
    assert day_plan.apply_event(plan, "step_finished", "grammar", key="forge:done:a") is False
    # Another séance finished the same day: still done, still one entry.
    assert day_plan.apply_event(plan, "step_finished", "grammar", key="forge:done:b") is False
    assert plan.to_json() == snapshot
    # A finished step is never pulled back by a late start or skip.
    assert day_plan.apply_event(plan, "step_started", "grammar") is False
    assert day_plan.apply_event(plan, "step_skipped", "grammar") is False
    assert plan.step("grammar").status == "done"


def test_compare_names_each_field_that_differs() -> None:
    plan = _fresh_plan()
    inputs = SessionInputs(
        pace="normal", scene_done=True, scene_seconds=420, quota=20, introduced=0, reviews_due=3,
        words_marked_done=False, forge_seconds=300, forge_blocks_today=0, forge_href="/atelier",
        exercises_today=0, deck=(17, 3),
    )
    view = session_view(inputs)
    diffs = day_plan.compare(plan, view)
    # The view saw a finished scene the plan was never told about.
    assert set(diffs) == {"done.scene", "minutes_left"}
    day_plan.apply_event(plan, "step_finished", "scene")
    assert day_plan.compare(plan, view) == {}


# ---------------------------------------------------------------------------
# Through the API: the plan is made with the day and written by its events
# ---------------------------------------------------------------------------


def test_the_plan_is_created_with_the_day_and_the_scene_is_started(
    assembled_client: TestClient, db_session: Session, journey_enabled: None, clock: Clock, plan_stored: None
) -> None:
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.today()
    driver.create(expect=(201,))

    plan = _plan_of(db_session, driver.id)
    assert plan is not None
    assert plan.journey_id == driver.id
    assert _statuses(plan) == {"scene": "doing", "grammar": "todo", "words": "todo"}
    # The sizes the day was planned with are today's view's sizes: no mismatch on a fresh day.
    session = driver.today()["session"]
    row = db_session.get(DailyJourney, uuid.UUID(driver.id))
    assert day_plan.compare(day_plan.read_plan(row), session) == {}


def test_a_paused_and_resumed_day_keeps_the_scene_open(
    assembled_client: TestClient, db_session: Session, journey_enabled: None, clock: Clock, plan_stored: None
) -> None:
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))

    _revision_call(assembled_client, driver, "pause")
    paused = _plan_of(db_session, driver.id)
    assert paused.step("scene").status == "doing"
    assert paused.step("scene").paused_at is not None and paused.step("scene").pauses == 1

    _revision_call(assembled_client, driver, "resume")
    resumed = _plan_of(db_session, driver.id)
    assert resumed.step("scene").status == "doing"
    assert resumed.step("scene").paused_at is None and resumed.step("scene").pauses == 1
    assert _statuses(resumed) == {"scene": "doing", "grammar": "todo", "words": "todo"}

    driver.play(answer=CAFE_ANSWER)
    assert driver.finish("complete").status_code == 200
    assert _plan_of(db_session, driver.id).step("scene").status == "done"


def test_a_day_finished_early_skips_the_scene_and_a_second_finish_is_refused(
    assembled_client: TestClient, db_session: Session, journey_enabled: None, clock: Clock, plan_stored: None
) -> None:
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))

    assert driver.finish("early").status_code == 200
    plan = _plan_of(db_session, driver.id)
    assert plan.step("scene").status == "skipped" and plan.step("scene").reason == "ended_early"
    events = list(plan.events)

    assert driver.finish("early").status_code == 409
    again = _plan_of(db_session, driver.id)
    assert again.events == events
    # Today's view calls a scene left early «done»; the plan's «closed» agrees.
    session = driver.today()["session"]
    assert {step["kind"]: step["state"] for step in session["steps"]}["scene"] == "done"
    assert "done.scene" not in day_plan.compare(again, session)


def test_forge_and_words_events_write_their_steps(
    assembled_client: TestClient, db_session: Session, journey_enabled: None, clock: Clock, plan_stored: None
) -> None:
    headers, user_id = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))
    driver.play(answer=CAFE_ANSWER)
    assert driver.finish("complete").status_code == 200

    seance = _forge_session(db_session, user_id)
    assert _plan_of(db_session, driver.id).step("grammar").status == "doing"
    seance.status = "completed"
    seance.completed_at = clock()
    db_session.commit()
    plan = _plan_of(db_session, driver.id)
    assert plan.step("grammar").status == "done"
    # The same séance flushed again moves nothing.
    seance.recap_payload = {"again": True}
    db_session.commit()
    assert _plan_of(db_session, driver.id).events == plan.events

    response = assembled_client.post("/api/v1/daily-journeys/session/words-done", headers=headers)
    assert response.status_code == 200, response.text
    plan = _plan_of(db_session, driver.id)
    assert _statuses(plan) == {"scene": "done", "grammar": "done", "words": "done"}
    assert plan.done and plan.minutes_left == 0
    assert response.json()["done"] is True
    assert day_plan.compare(plan, response.json()) == {}


def test_a_mismatch_is_logged_with_the_field_and_the_view_is_unchanged(
    assembled_client: TestClient,
    db_session: Session,
    journey_enabled: None,
    clock: Clock,
    plan_stored: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))
    before = driver.today()["session"]

    # Simulate a defect: the stored plan claims the grammar step is done.
    row = db_session.get(DailyJourney, uuid.UUID(driver.id))
    plan = day_plan.read_plan(row)
    day_plan.apply_event(plan, "step_finished", "grammar")
    day_plan.store_plan(row, plan)
    db_session.commit()

    with caplog.at_level(logging.WARNING, logger="app.services.day_plan"):
        after = driver.today()["session"]
    assert after == before
    records = [r for r in caplog.records if getattr(r, "event", None) == day_plan.MISMATCH_EVENT]
    assert records, "a mismatch must be logged"
    assert "done.grammar" in records[-1].day_plan_mismatch


# ---------------------------------------------------------------------------
# Flag off and old rows
# ---------------------------------------------------------------------------


def test_flag_off_stores_nothing_and_never_compares(
    assembled_client: TestClient,
    db_session: Session,
    journey_enabled: None,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", False)
    called: list[str] = []
    monkeypatch.setattr(day_plan, "note_flush", lambda *a, **k: called.append("note"))
    monkeypatch.setattr(day_plan, "apply_flush", lambda *a, **k: called.append("flush"))
    monkeypatch.setattr(day_plan, "shadow_compare", lambda *a, **k: called.append("compare"))
    monkeypatch.setattr(day_plan, "apply_to_journey", lambda *a, **k: called.append("apply"))

    headers, user_id = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.today()
    driver.create(expect=(201,))
    _revision_call(assembled_client, driver, "pause")
    _revision_call(assembled_client, driver, "resume")
    driver.play(answer=CAFE_ANSWER)
    assert driver.finish("complete").status_code == 200
    _forge_session(db_session, user_id, status="completed")
    assembled_client.post("/api/v1/daily-journeys/session/words-done", headers=headers)
    driver.today()

    assert called == []
    row = db_session.get(DailyJourney, uuid.UUID(driver.id))
    db_session.refresh(row)
    assert day_plan.PLAN_KEY not in (row.plan_selection or {})


def test_the_session_payload_is_the_same_with_the_flag_on_and_off(
    assembled_client: TestClient, db_session: Session, journey_enabled: None, clock: Clock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", True)
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))
    on = driver.today()
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", False)
    off = driver.today()
    for envelope in (on, off):
        envelope.pop("server_time", None)
    assert on["session"] == off["session"]
    assert on["time_estimate"] == off["time_estimate"]


def test_an_old_row_has_no_plan_and_reads_through_the_view(
    assembled_client: TestClient,
    db_session: Session,
    journey_enabled: None,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Planned before the flag: no plan is made.
    monkeypatch.setattr(settings, "DAY_PLAN_STORED", False)
    headers, _user = _learner(assembled_client, db_session)
    driver = Driver(assembled_client, headers, db=db_session)
    driver.create(expect=(201,))
    off = driver.today()["session"]

    monkeypatch.setattr(settings, "DAY_PLAN_STORED", True)
    with caplog.at_level(logging.WARNING, logger="app.services.day_plan"):
        on = driver.today()["session"]
        driver.play(answer=CAFE_ANSWER)
        assert driver.finish("complete").status_code == 200
        done = driver.today()["session"]
    assert on == off
    assert {step["kind"]: step["state"] for step in done["steps"]}["scene"] == "done"
    row = db_session.get(DailyJourney, uuid.UUID(driver.id))
    db_session.refresh(row)
    # Never backfilled, not even by the finish.
    assert day_plan.PLAN_KEY not in (row.plan_selection or {})
    assert not [r for r in caplog.records if getattr(r, "event", None) == day_plan.MISMATCH_EVENT]


def test_the_plan_survives_a_planner_that_rewrites_plan_selection(
    db_session: Session, plan_stored: None
) -> None:
    from app.db.models.user import User

    user = User(email=f"s21-raw-{uuid.uuid4().hex[:6]}@example.com", hashed_password="x")
    db_session.add(user)
    db_session.flush()
    journey = DailyJourney(
        user_id=user.id, local_date=datetime(2026, 3, 10, tzinfo=UTC).date(), timezone="UTC",
        contract_version=1, content_version="t", level_band="A1", status="active", revision=1,
        budget_seconds=600, estimated_active_seconds=0, scenario_snapshot={}, plan_selection={},
    )
    db_session.add(journey)
    db_session.commit()
    assert day_plan.read_plan(journey) is not None
    journey.plan_selection = {"rationale": "rewritten"}
    db_session.commit()
    db_session.refresh(journey)
    assert day_plan.read_plan(journey) is not None
    assert journey.plan_selection["rationale"] == "rewritten"
