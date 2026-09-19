"""WP-24 — the mistake loop, end to end.

Four things are pinned here, because each of them was broken or absent before
this package:

1. **A mistake can be finished.** Before WP-24 no ``UserError`` could reach
   ``mastered``, so errata accumulated for the life of the account.
2. **The scheduler is a scheduler.** Intervals compound with the item's history
   and collapse on a lapse, instead of being read out of a day table.
3. **Tomorrow's scene is chosen from the learner's due errata**, and the plan
   says which one (``target_reason``).
4. **The learner is told**, in French, on Home.
"""
from __future__ import annotations

import ast
import pathlib
import re
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.srs.schedule import (
    LAPSE_INTERVAL_DAYS,
    ScheduleState,
    interval_for_score,
    quality_from_score,
    schedule_next,
)
from app.db.models.error import UserError
from app.db.models.user import User
from app.services.error_memory import (
    ERROR_STATE_MASTERED,
    ERROR_STATE_OPEN,
    ERROR_STATE_REPAIRING,
    MASTERY_REQUIRED_REPAIRS,
    ErrorMemoryService,
    normalize_error_state,
    serialize_error_memory,
)
from app.services.journey_errata import (
    build_errata_target,
    errata_targets_for_user,
    parse_reason,
    rank_errata_targets,
    reason_for,
)

NOW = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
HOME_SCREEN = REPO_ROOT / "web-frontend/components/atelier-v2/home/HomeScreen.tsx"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
        native_language="en",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _record(
    db_session,
    user: User,
    *,
    label: str = "Accord du participe passé",
    task_type: str = "agreement",
    learner_text: str = "une homme",
    corrected: str = "un homme",
    severity: int = 2,
) -> UserError:
    """Record a mistake the way the product records one, then read the row back.

    Going through the service (rather than inserting a row by hand) is what
    makes the recurrence tests honest: the dedupe key that decides "this is the
    same mistake again" is computed here, not chosen by the test.
    """

    ErrorMemoryService(db_session).record_erratum(
        user=user,
        erratum={
            "display_label": label,
            "learner_text": learner_text,
            "corrected_target": corrected,
            "why_wrong": "homme is masculine",
            "repair_hint": corrected,
            "task_error_type": task_type,
            "severity": severity,
        },
        source_type="daily_journey",
    )
    db_session.commit()
    return (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.display_label == label)
        .order_by(UserError.created_at.desc())
        .first()
    )


def _erratum(
    db_session,
    user: User,
    *,
    label: str = "Accord du participe passé",
    memory_key: str | None = None,
    state: str | None = ERROR_STATE_OPEN,
    concept_id: int | None = None,
    occurrences: int = 1,
    lapses: int = 0,
    next_review_date: datetime | None = None,
    mastery_streak: int = 0,
    severity: int = 2,
) -> UserError:
    error = _record(db_session, user, label=label, task_type=label, severity=severity)
    error.state = state
    error.concept_id = concept_id
    error.occurrences = occurrences
    error.lapses = lapses
    error.mastery_streak = mastery_streak
    error.next_review_date = next_review_date or (NOW - timedelta(days=1))
    if memory_key:
        error.memory_key = memory_key
    db_session.commit()
    return error


def _repair(db_session, user: User, error: UserError, *, when: datetime, correct: bool = True):
    return ErrorMemoryService(db_session).review_error(
        user=user,
        error_id=error.id,
        rating=4 if correct else 1,
        repaired=correct,
        now=when,
    )


# ---------------------------------------------------------------------------
# 1. Lifecycle transitions
# ---------------------------------------------------------------------------


def test_a_fresh_erratum_starts_open(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    assert normalize_error_state(error.state) == ERROR_STATE_OPEN
    assert serialize_error_memory(error)["mastered"] is False


def test_one_repair_moves_open_to_repairing_not_to_mastered(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    repaired = _repair(db_session, user, error, when=NOW)
    assert repaired.state == ERROR_STATE_REPAIRING
    assert repaired.mastery_streak == 1
    assert repaired.mastered_at is None


def test_three_spaced_repairs_master_the_erratum_and_it_leaves_the_queue(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    for day in range(MASTERY_REQUIRED_REPAIRS):
        repaired = _repair(db_session, user, error, when=NOW + timedelta(days=day * 3))
    assert repaired.state == ERROR_STATE_MASTERED
    assert repaired.mastery_streak == MASTERY_REQUIRED_REPAIRS
    assert repaired.mastered_at is not None
    db_session.commit()

    due = ErrorMemoryService(db_session).due_error_records(user)
    assert [row.id for row in due] == []
    assert serialize_error_memory(repaired)["mastered"] is True


def test_repairs_in_one_sitting_do_not_buy_mastery(db_session) -> None:
    """Three correct answers in one minute prove recall, not retention."""

    user = _user(db_session)
    error = _erratum(db_session, user)
    for minute in range(6):
        repaired = _repair(db_session, user, error, when=NOW + timedelta(minutes=minute))
    assert repaired.mastery_streak == 1
    assert repaired.state == ERROR_STATE_REPAIRING


def test_a_failed_repair_resets_the_streak_and_the_interval(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    _repair(db_session, user, error, when=NOW)
    _repair(db_session, user, error, when=NOW + timedelta(days=1))
    assert error.mastery_streak == 2

    failed = _repair(db_session, user, error, when=NOW + timedelta(days=2), correct=False)
    assert failed.state == ERROR_STATE_REPAIRING
    assert failed.mastery_streak == 0
    assert failed.scheduled_days == LAPSE_INTERVAL_DAYS


def test_a_recurrence_reopens_a_mastered_erratum(db_session) -> None:
    """The same mistake, made again, destroys the mastery evidence."""

    user = _user(db_session)
    error = _erratum(db_session, user)
    for day in range(MASTERY_REQUIRED_REPAIRS):
        _repair(db_session, user, error, when=NOW + timedelta(days=day * 3))
    assert error.state == ERROR_STATE_MASTERED
    db_session.commit()

    _record(db_session, user, task_type="Accord du participe passé", severity=3)
    db_session.refresh(error)
    assert error.state == ERROR_STATE_REPAIRING
    assert error.mastery_streak == 0
    assert error.mastered_at is None
    # And it is back in the queue: rescheduled for tomorrow, not retired.
    assert error.next_review_date is not None
    # SQLite hands the column back naive; the value is UTC either way.
    scheduled = error.next_review_date
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=UTC)
    assert scheduled <= datetime.now(UTC) + timedelta(days=1, minutes=1)
    error.next_review_date = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    assert [row.id for row in ErrorMemoryService(db_session).due_error_records(user)] == [error.id]


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("new", ERROR_STATE_OPEN),
        ("learning", ERROR_STATE_OPEN),
        ("relearning", ERROR_STATE_REPAIRING),
        # A merely *scheduled* legacy row is not a proven one.
        ("review", ERROR_STATE_REPAIRING),
        ("mastered", ERROR_STATE_MASTERED),
        (None, ERROR_STATE_OPEN),
        ("nonsense", ERROR_STATE_OPEN),
    ],
)
def test_legacy_states_are_read_not_rewritten(stored, expected) -> None:
    assert normalize_error_state(stored) == expected


def test_a_legacy_row_with_no_state_is_still_due(db_session) -> None:
    """`state != 'mastered'` alone drops NULL rows in SQL; most legacy rows are NULL."""

    user = _user(db_session)
    error = _erratum(db_session, user, state=None)
    assert [row.id for row in ErrorMemoryService(db_session).due_error_records(user)] == [error.id]


# ---------------------------------------------------------------------------
# 2. The scheduler
# ---------------------------------------------------------------------------


def test_a_repeated_success_compounds_instead_of_repeating_one_day(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    intervals = []
    for day in range(4):
        _repair(db_session, user, error, when=NOW + timedelta(days=day * 30))
        intervals.append(error.scheduled_days)
    assert intervals == sorted(intervals), intervals
    assert intervals[-1] > intervals[0], intervals


def test_a_lapse_costs_ease_as_well_as_interval() -> None:
    state = ScheduleState(reps=5, interval_days=30, ease_factor=2.5, phase="review")
    lapsed = schedule_next(now=NOW, quality=0, state=state, min_interval_days=1)
    assert lapsed.interval_days == LAPSE_INTERVAL_DAYS
    assert lapsed.ease_factor < state.ease_factor
    assert lapsed.lapses == 1


def test_the_interval_depends_on_history_not_only_on_the_score() -> None:
    """The bug this replaces: two items with the same score, same interval."""

    young = interval_for_score(7, previous_interval_days=1, reps=1)
    old = interval_for_score(7, previous_interval_days=30, reps=9)
    assert old > young


def test_a_first_review_still_grants_the_historic_seed_interval() -> None:
    """Backwards compatibility: WP-24 re-dates nothing that already exists."""

    assert interval_for_score(10) == timedelta(days=30)
    assert interval_for_score(8) == timedelta(days=14)
    assert interval_for_score(6) == timedelta(days=7)
    assert interval_for_score(4) == timedelta(days=3)
    assert interval_for_score(1) == timedelta(days=1)


def test_five_is_a_pass_everywhere_including_the_scheduler() -> None:
    assert quality_from_score(5) >= 3
    assert quality_from_score(4.9) < 3
    assert quality_from_score(10) == 4
    assert quality_from_score(0) == 0


def test_the_scheduler_never_files_an_item_for_this_instant() -> None:
    for quality in range(5):
        decision = schedule_next(now=NOW, quality=quality, min_interval_days=1)
        assert decision.due_at > NOW


def test_grammar_review_no_longer_uses_a_five_branch_day_table() -> None:
    source = (REPO_ROOT / "app/services/grammar.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "calculate_next_review"
    )
    literals = {
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
    }
    assert {30, 14, 7, 3}.isdisjoint(literals), literals
    assert "interval_for_score" in source


# ---------------------------------------------------------------------------
# 3. Errata targets and the planner
# ---------------------------------------------------------------------------


def test_a_reason_round_trips(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    target = build_errata_target(error, now=NOW)
    assert target is not None
    assert target.reason == reason_for(error.id)
    assert parse_reason(target.reason) == str(error.id)
    assert parse_reason("chapter:3") is None


def test_a_mastered_erratum_is_never_a_target(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user, state=ERROR_STATE_MASTERED)
    assert build_errata_target(error, now=NOW) is None
    assert errata_targets_for_user(db_session, user, now=NOW) == []


def test_ranking_prefers_the_recurring_overdue_mistake(db_session) -> None:
    user = _user(db_session)
    quiet = _erratum(
        db_session,
        user,
        label="Orthographe",
        memory_key="spelling:one",
        next_review_date=NOW,
    )
    loud = _erratum(
        db_session,
        user,
        label="Accord",
        memory_key="grammar:two",
        state=ERROR_STATE_REPAIRING,
        occurrences=4,
        lapses=3,
        next_review_date=NOW - timedelta(days=9),
    )
    ranked = rank_errata_targets([quiet, loud], now=NOW)
    assert [target.error_id for target in ranked][0] == str(loud.id)
    assert ranked[0].priority > ranked[1].priority


def test_one_lesson_per_concept_not_one_per_slip(db_session) -> None:
    user = _user(db_session)
    first = _erratum(db_session, user, label="Accord", memory_key="grammar:a", concept_id=7)
    second = _erratum(
        db_session, user, label="Genre", memory_key="grammar:b", concept_id=7, occurrences=3
    )
    ranked = rank_errata_targets([first, second], now=NOW)
    assert len(ranked) == 1
    assert ranked[0].error_id == str(second.id)


def test_the_ranked_set_stays_small(db_session) -> None:
    user = _user(db_session)
    errors = [
        _erratum(
            db_session,
            user,
            label=f"Faute {index}",
            memory_key=f"grammar:{index}",
            occurrences=index + 1,
        )
        for index in range(12)
    ]
    assert len(rank_errata_targets(errors, now=NOW)) == 3
    assert len(errata_targets_for_user(db_session, user, limit=2, now=NOW)) == 2


def test_reading_the_queue_does_not_reschedule_anything(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    before = (error.next_review_date, error.state, error.reps)
    errata_targets_for_user(db_session, user, now=NOW)
    db_session.refresh(error)
    assert (error.next_review_date, error.state, error.reps) == before


def test_the_target_carries_the_example_and_the_reason(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user)
    target = build_errata_target(error, now=NOW)
    assert target.example == "une homme → un homme"
    candidate = target.as_candidate()
    assert candidate.metadata["target_reason"] == target.reason
    assert candidate.is_new is False
    because = target.as_because()
    assert because["kind"] == "erratum"
    assert because["label"] == "Accord du participe passé"


def test_the_planner_plans_the_erratum_and_says_why(db_session) -> None:
    from app.services.journey_planner import (
        merge_errata_candidates,
        plan_because,
        plan_journey,
        plan_target_reasons,
        target_identity,
    )
    from tests.test_journey_planner import _brief, _candidate  # reuse the real builders

    user = _user(db_session)
    error = _erratum(db_session, user)
    targets = errata_targets_for_user(db_session, user, now=NOW)
    assert targets

    ordinary = _candidate(identifier="9001", label_fr="le pourboire")
    candidates = merge_errata_candidates([ordinary], targets)
    assert target_identity(candidates[0].target) == f"error:{error.id}"

    plan = plan_journey(scenario=_brief(), candidates=[ordinary], errata_targets=targets)
    identity = f"error:{error.id}"
    assert identity in plan.selected_target_ids
    reasons = plan_target_reasons(plan, candidates)
    assert reasons[identity] == reason_for(error.id)
    assert reason_for(error.id) in plan.rationale

    because = plan_because(plan, candidates, targets)
    assert because is not None and because["reason"] == reason_for(error.id)


def test_a_plan_with_no_errata_says_nothing_rather_than_inventing_a_reason() -> None:
    from app.services.journey_planner import plan_because, plan_journey, plan_target_reasons
    from tests.test_journey_planner import _brief, _candidate

    ordinary = _candidate(identifier="9001", label_fr="le pourboire")
    plan = plan_journey(scenario=_brief(), candidates=[ordinary])
    assert plan_target_reasons(plan, [ordinary]) == {}
    assert plan_because(plan, [ordinary], []) is None


def test_the_public_prompts_still_carry_no_reason() -> None:
    """The wire contract forbids extra keys; the reason must not travel in it."""

    from app.services.journey_planner import plan_journey
    from tests.test_journey_planner import _brief, _candidate

    plan = plan_journey(scenario=_brief(), candidates=[_candidate(identifier="v-cafe", label_fr="un café")])
    for step in plan.steps:
        assert "target_reason" not in (step.public_prompt or {})
        assert "because" not in (step.public_prompt or {})


# ---------------------------------------------------------------------------
# 4. The because-line on Home
# ---------------------------------------------------------------------------


def test_home_renders_the_because_line_in_french() -> None:
    source = HOME_SCREEN.read_text(encoding="utf-8")
    assert "HomeBecause" in source
    assert "because" in source
    assert "function BecauseLine" in source
    assert "<BecauseLine because={because} />" in source
    # The sentence itself: French, sentence case, naming the mistake.
    assert "Cette scène reprend une faute notée" in source
    assert "{label}" in source


def test_the_because_line_prints_nothing_it_was_not_given() -> None:
    source = HOME_SCREEN.read_text(encoding="utf-8")
    body = source.split("function BecauseLine", 1)[1].split("\nfunction ", 1)[0]
    assert "if (!because || because.kind !== 'erratum') return null;" in body
    assert "if (!label) return null;" in body


def test_the_because_line_is_not_english_and_is_not_shouted() -> None:
    source = HOME_SCREEN.read_text(encoding="utf-8")
    body = source.split("function BecauseLine", 1)[1].split("\nfunction ", 1)[0]
    printed = re.findall(r">\s*([A-Za-zÀ-ÿ][^<{]*)", body)
    for fragment in printed:
        assert not re.search(r"\b(because|mistake|error|scene)\b", fragment, re.IGNORECASE), fragment
        assert fragment.strip() == "" or not fragment.strip().isupper(), fragment


# --------------------------------------------------------------------------
# 2026-09-19: the target's French label is the correction, never the category
# --------------------------------------------------------------------------


def test_the_candidate_elicits_the_french_correction_not_the_category_label(db_session) -> None:
    """Owner screenshot 2026-09-19: «How do you say "Im Französischen ist die
    korrekte Wortstellung…" in French?» with the answer "grammar". The display
    label is a category; the string a recall step elicits is the correction."""

    user = _user(db_session)
    error = _erratum(db_session, user, label="grammar")
    target = build_errata_target(error, now=NOW)
    candidate = target.as_candidate()
    assert candidate.target.label_fr == "un homme"
    assert candidate.target.label_native == "homme is masculine"
    assert candidate.metadata["erratum_learner"] == "une homme"
    assert target.label == "grammar", "the because-line keeps the stored label"


def test_a_row_without_a_stored_correction_is_never_a_target(db_session) -> None:
    user = _user(db_session)
    error = _erratum(db_session, user, label="grammar")
    error.correction = None
    db_session.commit()
    assert build_errata_target(error, now=NOW) is None
    assert errata_targets_for_user(db_session, user, now=NOW) == []
