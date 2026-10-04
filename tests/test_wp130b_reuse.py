# ruff: noqa: F811 - the WP-L4 fixtures are imported by name and requested as arguments
"""WP-130 B — timely grammar reuse: «Tenue» reachable in about three weeks.

«Tenue» is unchanged (two correct *independent* uses on days ≥ 7 apart, plus a
correct spaced item ≥ 14 days after the introduction). What changes is that
the journey now *offers* that evidence on time:

1. a free-use opportunity from 7 days after the introduction (and 7 days
   after the first free use) once the unit was used successfully — the reply
   asks for it («Réemploi») and the Rappel slot poses the coach's two-line
   scene, never an item that shows the form first;
2. a spaced item from 14 days after the introduction;
3. neither waits for a stability threshold;
4. a missed or failed opportunity changes nothing and the unit is offered again;
5. hints, copied suggestions, transforms and displayed examples keep their own
   category: assisted or insufficiently spaced evidence never holds a unit;
6. a deterministic successful learner holds a unit between days 14 and 21;
7. WP-129's B1+ free sentence («Écrivez une phrase à vous…») is an
   independent use when the learner writes a sentence of their own without
   help (no model sentence is shown before the answer, one attempt). With the
   hint or the solution, or when the answer is a sentence the app displayed for
   the unit (the model shown after a miss, a rule-card example, a contrast
   pair's ✓), it is supported production: met and scheduled, never a free use;
8. the life-walk check (tests/walk_checks_wp130b.py) fires on a bad chain.
"""
from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items, journey_learning
from app.services import journey_planner as planner
from app.services.concept_evidence import OUTCOME_CORRECT
from app.services.grammar_units import unit_brief
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    EvidenceKind,
    InputMode,
    StepKind,
    TargetKind,
    TaskOutcome,
)
from tests.test_wp_l4_concept_life import (
    DAY0,
    Day,
    _free_use_sentence,
    _grammar_steps,
    _learner,
    _progress,
    catalogue,  # noqa: F401 - fixture
)
from tests.walk_checks_wp130b import check_held_evidence_chain

FREE = Evidence(EvidenceFormat.PRODUCE, correct=True)


def _row(**fields: Any) -> SimpleNamespace:
    base = {
        "reps": 1,
        "created_at": None,
        "introduced_at": DAY0,
        "free_use_first_at": None,
        "free_use_last_at": None,
        "spaced_success_at": None,
        "held_at": None,
        "stability": 2.0,
    }
    return SimpleNamespace(**{**base, **fields})


# ---------------------------------------------------------------------------
# 1–3. Which opportunity a unit is owed, from the held fields alone
# ---------------------------------------------------------------------------


def test_the_free_use_opportunity_opens_a_week_after_a_successful_use() -> None:
    row = _row(free_use_first_at=DAY0, free_use_last_at=DAY0)
    for offset in range(7):
        assert concept_life.held_opportunity(row, now=DAY0 + timedelta(days=offset)) is None, offset
    for offset in (7, 8, 10):
        assert (
            concept_life.held_opportunity(row, now=DAY0 + timedelta(days=offset))
            == concept_life.OPPORTUNITY_FREE_USE
        ), offset
    # A first free use on day 3: the second can count from day 10 only.
    later = _row(free_use_first_at=DAY0 + timedelta(days=3), free_use_last_at=DAY0 + timedelta(days=3))
    assert concept_life.free_use_opens_on(later) == (DAY0 + timedelta(days=10)).date()
    assert concept_life.held_opportunity(later, now=DAY0 + timedelta(days=9)) is None
    # Never used successfully: the ordinary practice comes first.
    assert concept_life.held_opportunity(_row(reps=0), now=DAY0 + timedelta(days=9)) is None


def test_a_practised_unit_without_a_free_use_is_offered_one_too() -> None:
    row = _row(reps=2)
    assert concept_life.held_opportunity(row, now=DAY0 + timedelta(days=6)) is None
    assert concept_life.held_opportunity(row, now=DAY0 + timedelta(days=7)) == concept_life.OPPORTUNITY_FREE_USE


def test_the_spaced_item_is_owed_from_fourteen_days_on_the_clock() -> None:
    done = _row(free_use_first_at=DAY0, free_use_last_at=DAY0 + timedelta(days=7))
    assert concept_life.held_opportunity(done, now=DAY0 + timedelta(days=13)) is None
    # Day 14, an hour before the introduction's hour: a success would not count yet.
    assert concept_life.held_opportunity(done, now=DAY0 + timedelta(days=14, hours=-1)) is None
    assert concept_life.held_opportunity(done, now=DAY0 + timedelta(days=14)) == concept_life.OPPORTUNITY_SPACED
    spaced = _row(**{**vars(done), "spaced_success_at": DAY0 + timedelta(days=15)})
    assert concept_life.held_opportunity(spaced, now=DAY0 + timedelta(days=16)) is None


def test_both_owed_alternate_by_day() -> None:
    row = _row(free_use_first_at=DAY0, free_use_last_at=DAY0)
    kinds = {
        concept_life.held_opportunity(row, now=DAY0 + timedelta(days=offset)) for offset in (14, 15)
    }
    assert kinds == {concept_life.OPPORTUNITY_FREE_USE, concept_life.OPPORTUNITY_SPACED}


@pytest.mark.parametrize("stability", [0.5, 3.0, 9.9, 10.0, 45.0])
def test_stability_never_gates_an_opportunity(stability: float) -> None:
    row = _row(free_use_first_at=DAY0, free_use_last_at=DAY0, stability=stability)
    assert concept_life.held_opportunity(row, now=DAY0 + timedelta(days=7)) == concept_life.OPPORTUNITY_FREE_USE
    brief = journey_learning._with_held_opportunity_brief(
        {"concept_id": 1, "stability": stability}, concept_life.OPPORTUNITY_FREE_USE
    )
    assert grammar_items.review_band(brief["stability"]) == "high", "the reply asks for it"
    assert brief["stability_measured"] == stability
    spaced = journey_learning._with_held_opportunity_brief(
        {"concept_id": 1, "stability": stability}, concept_life.OPPORTUNITY_SPACED
    )
    assert grammar_items.review_band(spaced["stability"]) != "high", "a spaced item is posed"


def test_a_held_unit_is_owed_nothing() -> None:
    row = _row(free_use_first_at=DAY0, free_use_last_at=DAY0, held_at=DAY0 + timedelta(days=20))
    assert concept_life.held_opportunity(row, now=DAY0 + timedelta(days=21)) is None


# ---------------------------------------------------------------------------
# 5. The held conditions and the evidence categories, unchanged
# ---------------------------------------------------------------------------


def test_held_conditions_are_untouched() -> None:
    assert concept_life.HELD_FREE_USE_GAP_DAYS == 7
    assert concept_life.HELD_SPACED_AFTER_DAYS == 14
    row = _row(
        free_use_first_at=DAY0,
        free_use_last_at=DAY0 + timedelta(days=6),
        spaced_success_at=DAY0 + timedelta(days=14),
    )
    assert concept_life.held_conditions(row) == (False, True), "six days apart is not spaced free use"


@pytest.mark.parametrize(
    "kind, task_format, assistance, free_use",
    [
        (EvidenceKind.PRODUCED_INDEPENDENT, None, AssistanceLevel.NONE, True),  # a reply
        (EvidenceKind.PRODUCED_SUPPORTED, None, AssistanceLevel.SUGGESTED_RESPONSE, False),  # copied
        (EvidenceKind.PRODUCED_SUPPORTED, None, AssistanceLevel.HINT, False),  # hinted reply
        (EvidenceKind.PRODUCED_INDEPENDENT, "transform", AssistanceLevel.NONE, False),
        (EvidenceKind.PRODUCED_INDEPENDENT, "short_answer", AssistanceLevel.NONE, False),
        (EvidenceKind.RECOGNIZED, "choice", AssistanceLevel.NONE, False),
        (EvidenceKind.PRODUCED_INDEPENDENT, "conversation", AssistanceLevel.NONE, True),  # coach scene
        (EvidenceKind.PRODUCED_SUPPORTED, "conversation", AssistanceLevel.SOLUTION, False),
        (EvidenceKind.PRODUCED_INDEPENDENT, "sentence", AssistanceLevel.NONE, True),  # WP-129, unaided
        (EvidenceKind.PRODUCED_SUPPORTED, "sentence", AssistanceLevel.HINT, False),
        (EvidenceKind.PRODUCED_SUPPORTED, "sentence", AssistanceLevel.SOLUTION, False),
    ],
)
def test_each_evidence_keeps_its_category(
    kind: EvidenceKind, task_format: str | None, assistance: AssistanceLevel, free_use: bool
) -> None:
    evidence = journey_learning.grammar_journey_evidence(kind, task_format=task_format, assistance=assistance)
    assert concept_life.is_free_use(evidence) is free_use


def test_assisted_or_unspaced_evidence_never_holds_a_unit() -> None:
    supported = journey_learning.grammar_journey_evidence(
        EvidenceKind.PRODUCED_SUPPORTED, assistance=AssistanceLevel.SUGGESTED_RESPONSE
    )
    transform = journey_learning.grammar_journey_evidence(
        EvidenceKind.PRODUCED_INDEPENDENT, task_format="transform"
    )
    # Copied replies and transforms every day for thirty days: never held.
    row = _row()
    for offset in range(31):
        now = DAY0 + timedelta(days=offset)
        concept_life.note_concept_evidence(row, supported, now=now)
        concept_life.note_concept_evidence(row, transform, now=now)
    assert row.spaced_success_at is not None and row.free_use_first_at is None
    assert row.held_at is None
    # Free uses six days apart plus a spaced item: still not held.
    row = _row()
    concept_life.note_concept_evidence(row, FREE, now=DAY0)
    concept_life.note_concept_evidence(row, FREE, now=DAY0 + timedelta(days=6))
    concept_life.note_concept_evidence(row, transform, now=DAY0 + timedelta(days=20))
    assert row.held_at is None
    # A spaced item before day 14 does not count either.
    row = _row()
    concept_life.note_concept_evidence(row, FREE, now=DAY0)
    concept_life.note_concept_evidence(row, transform, now=DAY0 + timedelta(days=13))
    concept_life.note_concept_evidence(row, FREE, now=DAY0 + timedelta(days=13))
    assert row.held_at is None and row.spaced_success_at is None


# ---------------------------------------------------------------------------
# 7. WP-129's free sentence, graded end to end
# ---------------------------------------------------------------------------


def _free_sentence(db: Session) -> tuple[Any, dict]:
    concept = (
        db.query(GrammarConcept)
        .filter(GrammarConcept.external_id.in_(["FR2_A11_NEGATION", "FR_A1_NEGATION_NE_PAS"]))
        .first()
    )
    if concept is None:  # pragma: no cover - any unit with a detector will do
        concept = next(c for c in db.query(GrammarConcept).all() if unit_brief(c, control_language="en").get("detectors"))
    brief = unit_brief(concept, control_language="en", stability=5.0)
    task = grammar_items.free_sentence_item(brief, language="en")
    assert task is not None
    return task, brief


def test_the_free_sentence_is_an_independent_use_only_without_help(
    db_session: Session, catalogue: str
) -> None:
    user = _learner(db_session)
    task, brief = _free_sentence(db_session)
    # Nothing shown before the answer gives the sentence away: no prompt line,
    # and the model sentence is the correction after a miss, never the prompt.
    assert task.prompt_fr is None and task.source_fr is None
    assert task.solution_fr not in str(task.instruction_native) + str(task.goal_native or "")
    pool = [*(pair["right"] for pair in brief["contrast_pairs"]), *brief["examples"], task.solution_fr]
    shown = next(
        grammar_items.plain(text) for text in pool
        if grammar_items.free_sentence_uses_unit(brief, grammar_items.plain(text))
    )
    # The learner's own sentence: one the app never displayed for the unit.
    own = shown.rstrip(" .!?") + ", je crois."
    assert grammar_items.free_sentence_uses_unit(brief, own)
    for assistance, expected in (
        (AssistanceLevel.NONE, EvidenceKind.PRODUCED_INDEPENDENT),
        (AssistanceLevel.HINT, EvidenceKind.PRODUCED_SUPPORTED),
        (AssistanceLevel.SOLUTION, EvidenceKind.PRODUCED_SUPPORTED),
    ):
        evaluation = journey_learning.evaluate_recall(
            db_session, user=user, task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text=own), assistance=assistance,
        )
        (observation,) = evaluation.observations
        assert observation.evidence_kind is expected, assistance
        evidence = journey_learning.grammar_journey_evidence(
            observation.evidence_kind, task_format=observation.task_format, assistance=observation.assistance
        )
        assert concept_life.is_free_use(evidence) is (assistance is AssistanceLevel.NONE)


def test_a_free_sentence_that_types_back_a_shown_sentence_is_not_a_free_use(
    db_session: Session, catalogue: str
) -> None:
    """The model (shown after a miss), the rule card's examples and the ✓ of the
    contrast pairs are displayed sentences: typed back, they are met and
    scheduled, as supported production — never an independent use."""

    user = _learner(db_session)
    task, brief = _free_sentence(db_session)
    shown = [task.solution_fr, *brief["examples"], *(pair["right"] for pair in brief["contrast_pairs"])]
    for text in shown:
        evaluation = journey_learning.evaluate_recall(
            db_session, user=user, task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text=grammar_items.plain(text)),
            assistance=AssistanceLevel.NONE,
        )
        for observation in evaluation.observations:
            assert observation.evidence_kind is not EvidenceKind.PRODUCED_INDEPENDENT, text
            evidence = journey_learning.grammar_journey_evidence(
                observation.evidence_kind, task_format=observation.task_format,
                assistance=observation.assistance,
            )
            assert not concept_life.is_free_use(evidence), text
    model = journey_learning.evaluate_recall(
        db_session, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text=task.solution_fr), assistance=AssistanceLevel.NONE,
    )
    assert model.outcome is TaskOutcome.MET, "still right: it schedules the unit"
    assert model.observations[0].evidence_kind is EvidenceKind.PRODUCED_SUPPORTED


def test_the_coach_scene_stays_at_the_learner_level(monkeypatch) -> None:
    from app.services import practice_level

    brief = {"external_id": "FR2_A11_ETRE", "concept_id": 1, "title_fr": "Être"}
    task = journey_learning.coach_scene_review_task(brief, language="en", day_key="d", level="A1")
    if task is not None:
        assert all(practice_level.within_band(text, "A1") for text in task.accepted_answers)
    monkeypatch.setattr(practice_level, "within_band", lambda text, level, **_k: False)
    assert journey_learning.coach_scene_review_task(brief, language="en", day_key="d", level="A1") is None
    assert journey_learning.coach_scene_review_task(brief, language="en", day_key="d") is not None or task is None

# ---------------------------------------------------------------------------
# 1–6. Through the real learning adapter and planner, day by day
# ---------------------------------------------------------------------------


def _reply_targets(plan) -> set[str]:
    step = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    return {t.id for t in step.private_task.targets if t.kind is TargetKind.GRAMMAR}


def _introduce(db: Session, user) -> tuple[int, dict]:
    brief = concept_life.introduction_for_today(db, user, now=DAY0, control_language="en")
    assert brief is not None and brief["detectors"], brief
    concept_id = brief["concept_id"]
    day = Day(db, user, DAY0)
    plan = day.plan(introduction=brief)
    concept_life.mark_introduced(db, user=user, concept_id=concept_id, now=DAY0)
    for step in _grammar_steps(plan, concept_id):
        day.answer(step)
    assert day.reply(concept_id, _free_use_sentence(brief)).concept_evidence[0]["outcome"] == OUTCOME_CORRECT
    return concept_id, brief


def _live(db: Session, user, concept_id: int, brief: dict, *, days: int, avoid: set[int] = frozenset()):
    """A successful learner: right on every item of the unit, and uses it in the
    reply whenever the reply asks for it — except on the ``avoid`` days, when
    the reply avoids the form and the unit's items are answered wrong."""

    log: dict[int, dict[str, Any]] = {}
    for offset in range(1, days + 1):
        today = Day(db, user, DAY0 + timedelta(days=offset))
        before = _progress(db, user, concept_id)
        if before.held_at is not None:
            break
        plan = today.plan()
        items = _grammar_steps(plan, concept_id)
        asked = str(concept_id) in _reply_targets(plan)
        scene = any(step.private_task.evidence_format == "conversation" for step in items)
        log[offset] = {
            "asked": asked,
            # The opportunity: the reply asks for the unit, or (when the reply
            # cannot hold its sentence in the budget) the coach's scene does.
            "offered": asked or scene,
            "items": [step.private_task.task_type for step in items],
            "stability": before.stability,
        }
        for step in items:
            # A missed day: the coach's scene is answered wrong too.
            today.answer(step, correct=offset not in avoid)
        if asked and offset not in avoid:
            today.reply(concept_id, _free_use_sentence(brief))
        elif asked:
            today.reply(concept_id, "Oui, merci.")
    return log


def test_a_successful_learner_holds_the_unit_between_days_14_and_21(
    db_session: Session, catalogue: str
) -> None:
    user = _learner(db_session)
    concept_id, brief = _introduce(db_session, user)
    log = _live(db_session, user, concept_id, brief, days=21)

    # Nothing is asked again in the week after the introduction's free use…
    assert not any(log[d]["offered"] for d in range(1, 7)), log
    # …and the opportunity comes on day 7, whatever the stability: the reply
    # or the coach's scene, never an item that shows the form first.
    assert log[7]["offered"] and log[7]["stability"] < grammar_items.REEMPLOI_STABILITY_DAYS, log
    assert not log[7]["items"] or set(log[7]["items"]) <= {"short_answer"}, "only the coach's scene"
    progress = _progress(db_session, user, concept_id)
    assert progress.held_at is not None, log
    held_day = (progress.held_at.date() - DAY0.date()).days
    assert 14 <= held_day <= 21, (held_day, log)
    free_use, spaced = concept_life.held_conditions(progress)
    assert free_use and spaced
    assert concept_life.progress_stage(progress) == concept_life.STAGE_HELD


def test_a_missed_opportunity_leaves_the_unit_in_progress_and_comes_back(
    db_session: Session, catalogue: str
) -> None:
    user = _learner(db_session)
    concept_id, brief = _introduce(db_session, user)
    log = _live(db_session, user, concept_id, brief, days=9, avoid={7})
    assert log[7]["offered"], log
    progress = _progress(db_session, user, concept_id)
    # Day 7 was missed: no free use was written for it; day 8 offered it again
    # and the use landed then.
    assert log[8]["offered"], log
    assert (progress.free_use_last_at.date() - DAY0.date()).days == 8
    assert progress.held_at is None
    assert concept_life.progress_stage(progress) == concept_life.STAGE_PRACTISING


def test_a_spaced_item_is_posed_once_fourteen_days_have_passed(
    db_session: Session, catalogue: str
) -> None:
    user = _learner(db_session)
    concept_id, _brief = _introduce(db_session, user)
    progress = _progress(db_session, user, concept_id)
    # The second free use is already in; only the spaced item is owed.
    progress.free_use_last_at = DAY0 + timedelta(days=8)
    progress.stability = 30.0
    progress.next_review = DAY0 + timedelta(days=60)
    db_session.flush()
    early = Day(db_session, user, DAY0 + timedelta(days=13)).plan()
    assert not _grammar_steps(early, concept_id), "not due and nothing owed yet"
    day = Day(db_session, user, DAY0 + timedelta(days=14, hours=1))
    items = _grammar_steps(day.plan(), concept_id)
    assert len(items) == 1, "a strong, not-due unit still gets its spaced item"
    fmt = journey_learning.grammar_journey_evidence(
        EvidenceKind.PRODUCED_INDEPENDENT, task_format=items[0].private_task.evidence_format or items[0].private_task.task_type
    ).format
    assert fmt in concept_life.SPACED_ITEM_FORMATS
    day.answer(items[0])
    progress = _progress(db_session, user, concept_id)
    assert progress.spaced_success_at is not None and progress.held_at is not None


def test_the_reply_asks_an_owed_unit_before_another_strong_one() -> None:
    def entry(concept_id: int, **brief: Any):
        return SimpleNamespace(
            candidate=SimpleNamespace(metadata={"grammar_brief": {"concept_id": concept_id, **brief}})
        )

    strong = entry(1, stability=20.0)
    owed = entry(2, stability=10.0, held_opportunity="free_use")
    word = SimpleNamespace(candidate=SimpleNamespace(metadata={}))
    assert planner.reemploi_order([strong, word, owed]) == [owed, strong, word]


# ---------------------------------------------------------------------------
# 8. The life-walk check
# ---------------------------------------------------------------------------


def _life(**unit: Any) -> dict:
    base = {
        "unit": "FR2_A11_ETRE",
        "introduced": "2026-10-01",
        "free_use_first": "2026-10-01",
        "free_use_last": "2026-10-08",
        "spaced_success": "2026-10-15",
        "held": "2026-10-15",
    }
    return {"persona": "a1-de-fresh", "quality": "strong", "days": [{"day": 30, "grammar_life": [{**base, **unit}]}]}


def test_the_walk_check_is_quiet_on_a_sound_chain() -> None:
    assert check_held_evidence_chain(_life()) == []
    assert check_held_evidence_chain(_life(held=None, free_use_last="2026-10-03")) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"free_use_last": "2026-10-06"},  # six days apart
        {"free_use_first": None, "free_use_last": None},  # no unassisted use at all
        {"spaced_success": None},
        {"held": "2026-10-14", "spaced_success": "2026-10-14"},  # day 13
        {"spaced_success": "2026-10-10"},  # a spaced item before day 14 (the latest one)
    ],
)
def test_the_walk_check_fires_on_a_bad_chain(bad: dict) -> None:
    assert check_held_evidence_chain(_life(**bad)), bad
