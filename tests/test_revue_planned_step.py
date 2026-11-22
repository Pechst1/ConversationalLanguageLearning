# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""``REVUE_PLANNED_STEP_ENABLED``: Le Papier as an ordinary step of its day.

* The planner: on the Papier day an offer ``papier_offer()`` becomes one optional
  ``desk`` step ``papier``, the day's last, after the ending, priced at
  ``PAPIER_DESK_SECONDS``, inside the day's core minutes (Home's figure). The story
  part stays the classic Papier day. No other shape ever holds it.
* The validator: the Papier step is optional, last, and only on the Papier day.
* The service: the Papier day's desk is the Papier while the switch is on, nothing
  while it is off; a whole week played end to end — the Papier is a step, advanced
  like any, and the day completes.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from app.config import settings
from app.schemas.daily_journey import DeskPrompt
from app.services import journey_planner as planner
from app.services.daily_journey import DailyJourneyService, _plan_time_budget
from app.services.journey_contracts import PAPIER_DESK, DayShape, StepKind, is_papier_step
from app.services.journey_day_shapes import DayShapeInputs
from tests.test_journey_planner import POLITE, SCENE_FITTING, _brief
from tests.test_season_one import (  # noqa: F401 - fixtures
    _play,
    assembled_client,
    clock,
    journey_enabled,
    season_on,
    support,
)


def _plan(budget: int, *, shape: DayShape = DayShape.REVUE, desk=None, practice: bool = True):
    return planner.plan_journey(
        scenario=_brief(),
        candidates=[SCENE_FITTING, POLITE],
        budget_seconds=budget,
        day_shape=shape,
        shape_reason="revue_weekly" if shape is DayShape.REVUE else "dice",
        practice=practice,
        dice=DayShapeInputs(user_id="learner-papier", local_date=date(2026, 10, 1)),
        desk=desk,
    )


# ---------------------------------------------------------------------------
# 1. The planner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("budget", [600, 1200, 1800])
def test_the_papier_day_ends_on_the_papier_step_priced_inside_the_day(budget: int) -> None:
    plan = _plan(budget, desk=planner.papier_offer())
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert plan.day_shape is DayShape.REVUE and plan.practice is False
    # The story part is the classic Papier day, then the Papier.
    assert kinds[-1] is StepKind.DESK and kinds[-2] is StepKind.RESOLUTION
    assert kinds.count(StepKind.DESK) == 1
    assert len(plan.steps) - 1 <= 5
    papier = plan.steps[-1]
    assert is_papier_step(papier)
    assert papier.optional and papier.private_task is None and papier.target is None
    assert papier.estimated_seconds == planner.PAPIER_DESK_SECONDS
    prompt = DeskPrompt.model_validate(papier.public_prompt)
    assert prompt.desk == PAPIER_DESK and prompt.seconds == planner.PAPIER_DESK_SECONDS
    # Honest minutes: the Papier is in the core Home and the header quote, not an extension.
    stored = _plan_time_budget(plan)
    assert stored["core_seconds"] == plan.estimated_active_seconds
    assert "desk" not in stored["extensions"]
    # The story's drills make room for it: they fill only what the rhythm leaves after
    # the story and the Papier (a day whose story and Papier alone pass the rhythm is
    # longer, and says so in its minutes).
    story = sum(s.estimated_seconds for s in plan.steps if s.kind is not StepKind.RECALL and not is_papier_step(s))
    drills = sum(s.estimated_seconds for s in plan.steps if s.kind is StepKind.RECALL)
    assert drills <= max(0, budget - story - papier.estimated_seconds)
    if budget >= 1200:
        assert plan.estimated_active_seconds <= budget
    assert "papier planned" in plan.rationale


def test_on_the_five_minute_day_the_papier_is_planned_and_said_not_hidden() -> None:
    plan = _plan(300, desk=planner.papier_offer())
    plan.validate()
    assert is_papier_step(plan.steps[-1])
    assert _plan_time_budget(plan)["core_seconds"] == plan.estimated_active_seconds
    assert plan.estimated_active_seconds > 300 >= sum(
        step.estimated_seconds for step in plan.steps if not step.optional
    )


@pytest.mark.parametrize("budget", [300, 600, 1200])
def test_without_the_offer_the_papier_day_is_exactly_what_it_was(budget: int) -> None:
    plan = _plan(budget)
    plan.validate()
    kinds = [step.kind for step in plan.steps]
    assert kinds[-1] is StepKind.RESOLUTION and StepKind.DESK not in kinds
    assert "papier" not in plan.rationale


@pytest.mark.parametrize("shape", [DayShape.STANDARD, DayShape.SHORT, DayShape.LISTENING])
def test_no_other_day_holds_the_papier(shape: DayShape) -> None:
    for practice in (True, False):
        plan = _plan(1200, shape=shape, desk=planner.papier_offer(), practice=practice)
        assert not any(is_papier_step(step) for step in plan.steps)
        assert StepKind.DESK not in [step.kind for step in plan.steps]


def test_the_validator_keeps_the_papier_optional_last_and_on_its_day() -> None:
    plan = _plan(1200, desk=planner.papier_offer())
    papier = plan.steps[-1]
    with pytest.raises(ValueError, match="optional"):
        replace(plan, steps=[*plan.steps[:-1], replace(papier, optional=False)]).validate()
    with pytest.raises(ValueError, match="only the Papier day"):
        replace(plan, day_shape=DayShape.STANDARD).validate()
    moved = [plan.steps[0], papier, *plan.steps[1:-1]]
    with pytest.raises(ValueError):
        replace(plan, steps=[replace(step, ordinal=i) for i, step in enumerate(moved)]).validate()
    twice = [*plan.steps, replace(papier, ordinal=len(plan.steps))]
    with pytest.raises(ValueError):
        replace(plan, steps=twice).validate()


def test_the_schema_names_the_papier_desk() -> None:
    prompt = DeskPrompt.model_validate(planner.papier_offer())
    assert prompt.desk == "papier" and prompt.title_fr == "Le Papier"
    with pytest.raises(ValueError):
        DeskPrompt.model_validate({**planner.papier_offer(), "desk": "kiosque"})


# ---------------------------------------------------------------------------
# 2. The service
# ---------------------------------------------------------------------------


def test_the_papier_day_desk_is_the_papier_only_while_the_switch_is_on(monkeypatch) -> None:
    host = SimpleNamespace()
    journey = SimpleNamespace(local_date=date(2026, 10, 1))
    monkeypatch.setattr(settings, "REVUE_PLANNED_STEP_ENABLED", False)
    assert DailyJourneyService._desk_for_today(host, None, journey, None, DayShape.REVUE) is None
    monkeypatch.setattr(settings, "REVUE_PLANNED_STEP_ENABLED", True)
    offer = DailyJourneyService._desk_for_today(host, None, journey, None, DayShape.REVUE)
    assert offer == planner.papier_offer()


@pytest.mark.parametrize("switch", [False, True], ids=["off", "on"])
def test_a_week_played_end_to_end_the_papier_is_a_step_and_the_day_completes(
    switch, assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
) -> None:
    from app.db.models.daily_journey import DailyJourney
    from app.services.revue import encounter as revue_encounter
    from app.services.revue.evergreen import load_evergreens

    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    monkeypatch.setattr(settings, "REVUE_PLANNED_STEP_ENABLED", switch)
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    kiosk = load_evergreens()[:3]
    monkeypatch.setattr(revue_encounter, "available_dossiers", lambda period, db=None: list(kiosk))
    provider = season_on
    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    d = support.Driver(
        assembled_client,
        support.register(assembled_client, f"papier-step-{uuid.uuid4()}@example.com", cefr="A2.1"),
        db=db_session,
    )
    papier_days = 0
    for _day in range(9):
        journey = _play(d, provider, clock, "Odile, c'est ma grand-mère.")
        row = db_session.get(DailyJourney, uuid.UUID(journey["id"]))
        desks = [step for step in journey["steps"] if step["kind"] == "desk" and step["prompt"]["desk"] == "papier"]
        if journey.get("day_shape") != "revue":
            assert not desks
            continue
        papier_days += 1
        assert journey["status"] == "completed", journey["status"]
        if not switch:
            assert not desks
            assert journey["steps"][-1]["kind"] == "resolution"
            continue
        assert len(desks) == 1 and journey["steps"][-1]["id"] == desks[0]["id"]
        assert desks[0]["status"] in ("completed", "skipped")
        assert desks[0]["estimated_seconds"] == planner.PAPIER_DESK_SECONDS
        stored = (row.plan_selection or {}).get("time_budget") or {}
        assert stored.get("core_seconds") == sum(step["estimated_seconds"] for step in journey["steps"])
    assert papier_days >= 1


# ---------------------------------------------------------------------------
# 3. A closed Papier session completes the step (integration 2026-11-22)
# ---------------------------------------------------------------------------


def _papier_day(db_session, *, papier_status: str = "active"):
    from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
    from app.db.models.user import User
    from app.services.daily_journey import learner_timezone, local_date_for

    user = User(id=uuid.uuid4(), email=f"papier-close-{uuid.uuid4().hex[:8]}@example.com", hashed_password="x",
                cefr_estimate="A2.1", native_language="de", interests="")
    db_session.add(user)
    db_session.flush()
    journey = DailyJourney(id=uuid.uuid4(), user_id=user.id, local_date=local_date_for(learner_timezone(user)),
                           status="active", revision=4)
    db_session.add(journey)
    db_session.flush()
    ending = DailyJourneyStep(id=uuid.uuid4(), journey_id=journey.id, ordinal=0, kind="resolution",
                              status="completed" if papier_status == "active" else "active")
    papier = DailyJourneyStep(id=uuid.uuid4(), journey_id=journey.id, ordinal=1, kind="desk", status=papier_status,
                              optional=True, estimated_seconds=planner.PAPIER_DESK_SECONDS,
                              public_prompt=planner.papier_offer())
    db_session.add_all([ending, papier])
    db_session.flush()
    journey.current_step_id = papier.id if papier_status == "active" else ending.id
    db_session.flush()
    return user, journey, ending, papier


@pytest.mark.parametrize("papier_status", ["active", "pending"])
def test_a_closed_papier_session_completes_the_days_papier_step(db_session, monkeypatch, papier_status) -> None:
    from app.services.daily_journey import complete_papier_step

    monkeypatch.setattr(settings, "REVUE_PLANNED_STEP_ENABLED", True)
    user, journey, ending, papier = _papier_day(db_session, papier_status=papier_status)
    assert complete_papier_step(db_session, user) is True
    db_session.refresh(papier)
    db_session.refresh(journey)
    assert papier.status == "completed" and papier.completed_at is not None
    assert journey.revision == 5, "the player refreshes: the journey moved on"
    if papier_status == "active":
        assert journey.current_step_id is None, "the Papier was the day's last step"
    else:
        assert journey.current_step_id == ending.id, "the story goes on; the Papier will not open again"
    assert complete_papier_step(db_session, user) is False, "idempotent"


def test_with_the_switch_off_a_closed_session_leaves_the_journey_alone(db_session, monkeypatch) -> None:
    from app.services.daily_journey import complete_papier_step

    monkeypatch.setattr(settings, "REVUE_PLANNED_STEP_ENABLED", False)
    user, journey, _ending, papier = _papier_day(db_session)
    assert complete_papier_step(db_session, user) is False
    db_session.refresh(papier)
    assert papier.status == "active" and journey.revision == 4
