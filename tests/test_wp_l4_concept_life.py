# ruff: noqa: F811 - the WP-12 fixtures are imported by name and requested as arguments
"""WP-L4 — the concept's life inside the day.

* The intake plan: the rhythm's weekly quota, spread out, through the one
  new-concept picker (band, teaching order, prerequisites).
* An introduction day at Régulier: scene → rule card → three or four guided
  items (recognise → choose → build → transform) → a reply that asks for the
  unit, inside the ten-minute budget; the Règle step validates on the wire.
* «Emploi»: the unit's detector grades the reply — correct, error (one lapse,
  not two) or avoided (neutral).
* «Rappel»: a due unit is one warm-up whose format scales with stability; a
  strong one is asked for in the reply instead.
* «Tenue»: held after free use on two days ≥ 7 apart plus a correct spaced
  item ≥ 14 days after the introduction.
* One unit followed over 21 simulated days, on catalogue v1 (the default) and
  v2 (the flag): introduced, practised, used, lapsed, repaired, held.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.schemas.daily_journey import RulePrompt, RuleStep
from app.services import concept_life, grammar_items
from app.services import journey_planner as planner
from app.services.concept_evidence import (
    OUTCOME_AVOIDED,
    OUTCOME_CORRECT,
    OUTCOME_ERROR,
    classify_reply,
    with_concept_evidence,
)
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    Correction,
    EvidenceKind,
    InputMode,
    ResponseEvaluation,
    ResponseTask,
    StepKind,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_day_shapes import DayShapeInputs
from app.services.journey_learning import (
    apply_learning_evidence,
    ensure_journey_learning_session,
    evaluate_recall,
    select_learning_candidates,
)
from tests.test_journey_end_to_end import (
    Driver,
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
)
from tests.test_journey_planner import _brief

DAY0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
REGULIER = 600


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed(db: Session, version: str) -> None:
    FrenchCoreGrammarCatalog(db, version).ensure_catalog()


@pytest.fixture(params=["v1", "v2"])
def catalogue(request, monkeypatch, db_session: Session):
    """The live catalogue under test, seeded; v1 is restored afterwards."""

    version = request.param
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", version)
    _seed(db_session, version)
    yield version
    if version != "v1":
        monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v1")
        _seed(db_session, "v1")


def _learner(db: Session, *, minutes: int = 10) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"wp-l4-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
        cefr_estimate="A1.1",
        daily_goal_minutes=minutes,
    )
    db.add(user)
    db.commit()
    return user


def _progress(db: Session, user: User, concept_id: int) -> UserGrammarProgress | None:
    db.expire_all()
    return (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept_id)
        .first()
    )


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _answer(task: Any, *, correct: bool = True) -> AttemptAnswer:
    if task.task_type in {"choice", "classify", "listen_tap"}:
        option = next(o for o in task.options if (o["id"] == task.correct_option_id) is correct)
        return AttemptAnswer(mode=InputMode.TEXT, text="", option_id=option["id"])
    if task.task_type in {"tiles", "word_bank", "unscramble"}:
        order = list(task.correct_tile_order)
        return AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=order if correct else order[::-1])
    return AttemptAnswer(mode=InputMode.TEXT, text=task.accepted_answers[0] if correct else "euh")


class Day:
    """One simulated day of one learner, through the real planner and learning layer."""

    def __init__(self, db: Session, user: User, now: datetime) -> None:
        self.db, self.user, self.now = db, user, now
        self.journey_id = uuid.uuid4()
        self.session = ensure_journey_learning_session(
            db, user=user, journey_id=self.journey_id, scenario_key="order_at_cafe"
        )

    def plan(self, *, introduction: dict | None = None):
        candidates = select_learning_candidates(
            self.db, user=self.user, scenario=_brief(), limit=16, now=self.now,
            budget_seconds=REGULIER,
        )
        plan = planner.plan_journey(
            scenario=_brief(),
            candidates=candidates,
            budget_seconds=REGULIER,
            practice=True,
            dice=DayShapeInputs(user_id=str(self.user.id), local_date=self.now.date()),
            introduction=introduction,
        )
        plan.validate()
        return plan

    def answer(self, step, *, correct: bool = True):
        task = step.private_task
        evaluation = evaluate_recall(
            self.db, user=self.user, task=task, answer=_answer(task, correct=correct),
            assistance=AssistanceLevel.NONE,
        )
        apply_learning_evidence(
            self.db, user=self.user, journey_id=self.journey_id, step_id=uuid.uuid4(),
            session=self.session, evaluation=evaluation, modality=InputMode.TEXT, now=self.now,
        )
        self.db.flush()
        return evaluation

    def reply(self, concept_id: int, text: str, *, correction: Correction | None = None):
        task = ResponseTask(
            objective_native="Order a drink.",
            character_id="margaux_barman",
            character_name="Margaux",
            opening_line_fr="Bonjour !",
            targets=[TargetRef(kind=TargetKind.GRAMMAR, id=str(concept_id), label_fr="", concept_title=True)],
        )
        evaluation = with_concept_evidence(
            self.db,
            evaluation=ResponseEvaluation(
                outcome=TaskOutcome.MET, assistance=AssistanceLevel.NONE, observations=[],
                correction=correction,
            ),
            task=task,
            text=text,
            modality=InputMode.TEXT,
        )
        apply_learning_evidence(
            self.db, user=self.user, journey_id=self.journey_id, step_id=uuid.uuid4(),
            session=self.session, evaluation=evaluation, modality=InputMode.TEXT, now=self.now,
        )
        self.db.flush()
        return evaluation


def _grammar_steps(plan, concept_id: int) -> list:
    return [
        step for step in plan.steps
        if step.kind is StepKind.RECALL
        and step.target is not None
        and step.target.kind is TargetKind.GRAMMAR
        and step.target.id == str(concept_id)
    ]


def _free_use_sentence(brief: dict) -> str:
    for sentence in [*(pair["right"] for pair in brief["contrast_pairs"]), *brief["examples"]]:
        if grammar_items.detector_span(brief["detectors"], sentence):
            return sentence
    raise AssertionError(f"no sentence of {brief['external_id']} matches its detector")


# ---------------------------------------------------------------------------
# 1. Intake
# ---------------------------------------------------------------------------


def test_the_weekly_quota_follows_the_rhythm_and_is_spread_out(db_session: Session) -> None:
    for minutes, quota in ((5, 1), (10, 2), (20, 3), (30, 4)):
        user = _learner(db_session, minutes=minutes)
        assert concept_life.weekly_concept_quota(db_session, user, now=DAY0) == quota
        assert concept_life.NEW_CONCEPTS_PER_WEEK[
            {5: "leger", 10: "regulier", 20: "soutenu", 30: "intensif"}[minutes]
        ] == quota

    user = _learner(db_session, minutes=10)
    concept = GrammarConcept(name="WP-L4 quota probe", level="A1", language="xx", active=False)
    db_session.add(concept)
    db_session.flush()
    assert concept_life.introduction_due(db_session, user, now=DAY0)
    concept_life.mark_introduced(db_session, user=user, concept_id=concept.id, now=DAY0)
    # Régulier: two a week, at least three days apart.
    assert not concept_life.introduction_due(db_session, user, now=DAY0 + timedelta(days=1))
    assert not concept_life.introduction_due(db_session, user, now=DAY0 + timedelta(days=2))
    assert concept_life.introduction_due(db_session, user, now=DAY0 + timedelta(days=3))


def test_the_intake_uses_the_one_picker_and_its_prerequisites(db_session: Session, catalogue: str) -> None:
    from app.services.atelier import AtelierScheduler

    user = _learner(db_session)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="de")
    assert brief is not None
    picked = AtelierScheduler(db_session).next_new_concepts(user, limit=1, language="fr")[0]
    assert brief["concept_id"] == picked.id
    concept = db_session.get(GrammarConcept, picked.id)
    assert concept.level == "A1" and concept.is_foundation
    assert not concept.prerequisites, "the first unit has nothing to wait for"
    # The rule card speaks the learner's language, whatever the catalogue.
    assert brief["rule_card"]["rule"].get("de") or brief["rule_card"]["rule"].get("en")
    assert brief["title_native"]
    if catalogue == "v2":
        assert brief["rule_card"]["rule"]["de"], "v2 cards are built from rule_short per locale"
        assert brief["rule_card"]["contrast"], "the first trap is the contrast pair"


# ---------------------------------------------------------------------------
# 2. The introduction day
# ---------------------------------------------------------------------------


def test_an_introduction_day_stays_inside_the_regulier_budget(db_session: Session, catalogue: str) -> None:
    user = _learner(db_session)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    plan = Day(db_session, user, DAY0).plan(introduction=brief)

    assert plan.estimated_active_seconds <= REGULIER, plan.rationale
    kinds = [step.kind for step in plan.steps]
    scene_at, rule_at, respond_at = (
        kinds.index(StepKind.SCENE), kinds.index(StepKind.RULE), kinds.index(StepKind.RESPOND)
    )
    assert scene_at < rule_at < respond_at
    guided = _grammar_steps(plan, brief["concept_id"])
    assert 3 <= len(guided) <= 4
    assert [step.ordinal for step in guided] == list(range(rule_at + 1, rule_at + 1 + len(guided)))
    formats = [step.private_task.task_type for step in guided]
    assert formats[:2] == ["choice", "choice"], "recognise, then choose"
    assert formats[2] in {"word_bank", "tiles"}, "then build"
    if len(formats) == 4:
        assert formats[3] == "transform"
    # No prompt prints its own answer.
    for step in guided:
        task = step.private_task
        assert task.prompt_fr is None or grammar_items._fold(task.prompt_fr) != grammar_items._fold(task.solution_fr)
    # The reply asks for the unit, first.
    respond = plan.steps[respond_at]
    assert respond.public_prompt["targets"][0]["id"] == str(brief["concept_id"])
    assert respond.public_prompt["targets"][0]["kind"] == "grammar"
    # The Règle validates on the wire.
    rule = plan.steps[rule_at]
    prompt = RulePrompt.model_validate(rule.public_prompt)
    assert prompt.concept_id == brief["concept_id"]
    RuleStep.model_validate(
        {"id": "x", "ordinal": rule.ordinal, "status": "pending",
         "estimated_seconds": rule.estimated_seconds, "prompt": rule.public_prompt}
    )
    assert rule.estimated_seconds >= planner.RULE_CARD_SECONDS


def test_leger_fits_an_introduction_inside_five_minutes(db_session: Session, catalogue: str) -> None:
    user = _learner(db_session, minutes=5)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    plan = planner.plan_journey(
        scenario=_brief(), candidates=[], budget_seconds=300, practice=True,
        dice=DayShapeInputs(user_id="leger", local_date=DAY0.date()), introduction=brief,
    )
    plan.validate()
    assert plan.estimated_active_seconds <= 300
    assert StepKind.RULE in [step.kind for step in plan.steps]


def test_a_classic_day_never_introduces(db_session: Session) -> None:
    brief = {
        "concept_id": 1, "title_fr": "t", "title_native": "t", "detectors": [],
        "examples": ["Je suis ici."], "contrast_pairs": [{"wrong": "Je es ici.", "right": "Je suis ici."}],
        "rule_card": {"example": {"fr": "Je suis ici."}, "rule": {"en": "r"}},
    }
    plan = planner.plan_journey(
        scenario=_brief(), candidates=[], budget_seconds=300, practice=False, introduction=brief,
    )
    assert StepKind.RULE not in [step.kind for step in plan.steps]


# ---------------------------------------------------------------------------
# 3. «Emploi»: the reply's concept evidence
# ---------------------------------------------------------------------------


def test_the_detector_reads_a_reply_as_correct_error_or_avoided() -> None:
    patterns = [r"\b(?:je suis|tu es|nous sommes|vous êtes)\b"]
    assert classify_reply(patterns, "Je suis là, un café.", None)[0] == OUTCOME_CORRECT
    wrong = Correction(span_fr="Je es", corrected_fr="Je suis", note_native="être: je suis")
    assert classify_reply(patterns, "Je es là.", wrong)[0] == OUTCOME_ERROR
    assert classify_reply(patterns, "Un café, s’il vous plaît.", None)[0] == OUTCOME_AVOIDED
    unrelated = Correction(span_fr="un bière", corrected_fr="une bière", note_native="genre")
    assert classify_reply(patterns, "Je suis là, un bière.", unrelated)[0] == OUTCOME_CORRECT


def test_an_error_in_the_reply_is_one_lapse_not_two(db_session: Session, catalogue: str) -> None:
    user = _learner(db_session)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    day = Day(db_session, user, DAY0)
    concept_life.mark_introduced(db_session, user=user, concept_id=brief["concept_id"], now=DAY0)
    day.answer(_grammar_steps(day.plan(introduction=brief), brief["concept_id"])[0])
    lapses_before = _progress(db_session, user, brief["concept_id"]).lapses

    later = Day(db_session, user, DAY0 + timedelta(days=3))
    pair = brief["contrast_pairs"][0]
    evaluation = later.reply(
        brief["concept_id"], f"{pair['wrong']} Un café.",
        correction=Correction(span_fr=pair["wrong"], corrected_fr=pair["right"], note_native="…"),
    )
    assert evaluation.concept_evidence[0]["outcome"] == OUTCOME_ERROR
    progress = _progress(db_session, user, brief["concept_id"])
    assert progress.lapses == lapses_before + 1, "the detector and the correction book one lapse"
    assert _aware(progress.next_review) <= later.now + timedelta(days=1, minutes=1)
    erratum = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert erratum.concept_id == brief["concept_id"], "the erratum is the unit's"


def test_an_avoided_form_is_neutral(db_session: Session, catalogue: str) -> None:
    user = _learner(db_session)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    concept_life.mark_introduced(db_session, user=user, concept_id=brief["concept_id"], now=DAY0)
    before = _progress(db_session, user, brief["concept_id"])
    reps, due = before.reps, before.next_review
    evaluation = Day(db_session, user, DAY0).reply(brief["concept_id"], "Merci, au revoir.")
    assert evaluation.concept_evidence[0]["outcome"] in {OUTCOME_AVOIDED}
    after = _progress(db_session, user, brief["concept_id"])
    assert (after.reps, after.next_review, after.lapses) == (reps, due, 0)


# ---------------------------------------------------------------------------
# 4. «Rappel» formats and «Tenue»
# ---------------------------------------------------------------------------


def _brief_with(stability: float) -> dict:
    return {
        "concept_id": 7, "title_fr": "Être", "title_native": "Être",
        "detectors": [r"\b(?:je suis|il est)\b"],
        "examples": ["Je suis étudiante.", "Il est à Lyon."],
        "contrast_pairs": [{"wrong": "Je es français.", "right": "Je suis français."}],
        "pattern_forms": [], "rule_short_native": None, "stability": stability,
        "rule_card": {"example": {"fr": "[Je suis] ici."}, "rule": {"en": "r"}},
    }


@pytest.mark.parametrize(
    ("stability", "formats"),
    [(1.0, {"choice"}), (5.0, {"transform", "word_bank"}), (20.0, set())],
)
def test_rappel_formats_scale_with_stability(stability: float, formats: set[str]) -> None:
    seen = set()
    for day in range(6):
        task = grammar_items.review_item(
            _brief_with(stability), sentences=["Il pleut."], language="en", day_key=str(day)
        )
        if task is not None:
            seen.add(task.task_type)
    assert seen == formats


def test_a_strong_unit_is_asked_for_in_the_reply_not_drilled() -> None:
    from tests.test_journey_planner import _candidate

    strong = _candidate(
        kind=TargetKind.GRAMMAR, identifier="7", label_fr="Être", label_native="Être",
        metadata={"grammar_brief": _brief_with(20.0), "stability": 20.0},
    )
    plan = planner.plan_journey(
        scenario=_brief(), candidates=[strong], budget_seconds=REGULIER, practice=True,
        dice=DayShapeInputs(user_id="strong", local_date=DAY0.date()),
    )
    respond = next(step for step in plan.steps if step.kind is StepKind.RESPOND)
    assert {"kind": "grammar", "id": "7"}.items() <= respond.public_prompt["targets"][0].items()
    assert not [s for s in plan.steps if s.target is not None and s.target.id == "7" and s.kind is StepKind.RECALL]


def test_held_needs_two_free_uses_a_week_apart_and_a_late_spaced_item() -> None:
    class Row:
        reps = 1
        created_at = None
        introduced_at = DAY0
        free_use_first_at = free_use_last_at = spaced_success_at = held_at = None

    row = Row()
    free = Evidence(EvidenceFormat.PRODUCE, correct=True)
    concept_life.note_concept_evidence(row, free, now=DAY0)
    concept_life.note_concept_evidence(row, free, now=DAY0 + timedelta(days=6))
    assert concept_life.held_conditions(row) == (False, False)
    concept_life.note_concept_evidence(row, free, now=DAY0 + timedelta(days=7))
    concept_life.note_concept_evidence(
        row, Evidence(EvidenceFormat.RECOGNISE), now=DAY0 + timedelta(days=13)
    )
    assert concept_life.held_conditions(row) == (True, False), "13 days is not yet spaced"
    concept_life.note_concept_evidence(
        row, Evidence(EvidenceFormat.PRODUCE, correct=True, assisted=True), now=DAY0 + timedelta(days=15)
    )
    assert row.held_at is None, "a helped reply is not free use, nor a spaced item"
    concept_life.note_concept_evidence(
        row, Evidence(EvidenceFormat.TRANSFORM), now=DAY0 + timedelta(days=14)
    )
    assert row.held_at == DAY0 + timedelta(days=14)
    assert concept_life.concept_stage(row) == concept_life.STAGE_HELD


# ---------------------------------------------------------------------------
# 5. One unit over 21 simulated days
# ---------------------------------------------------------------------------


def test_one_unit_over_twenty_one_days(db_session: Session, catalogue: str) -> None:
    user = _learner(db_session)
    brief = concept_life.introduction_for_today(db_session, user, now=DAY0, control_language="en")
    assert brief is not None and brief["detectors"], brief
    concept_id = brief["concept_id"]
    assert concept_life.concept_stage(_progress(db_session, user, concept_id)) == concept_life.STAGE_NEW

    # Day 0 — Rencontre, Règle, Essai, Emploi.
    day = Day(db_session, user, DAY0)
    plan = day.plan(introduction=brief)
    assert plan.estimated_active_seconds <= REGULIER
    concept_life.mark_introduced(db_session, user=user, concept_id=concept_id, now=DAY0)
    assert concept_life.concept_stage(_progress(db_session, user, concept_id)) == concept_life.STAGE_INTRODUCED
    guided = _grammar_steps(plan, concept_id)
    for step in guided:
        assert day.answer(step).outcome is TaskOutcome.MET
    progress = _progress(db_session, user, concept_id)
    assert progress.reps == 1, "one day, one success on the schedule"
    assert DAY0 + timedelta(days=1) <= _aware(progress.next_review) <= DAY0 + timedelta(days=2, minutes=1)
    evaluation = day.reply(concept_id, _free_use_sentence(brief))
    assert evaluation.concept_evidence[0]["outcome"] == OUTCOME_CORRECT
    progress = _progress(db_session, user, concept_id)
    assert _aware(progress.free_use_first_at) == DAY0
    assert progress.reps == 1, "the reply's free use folds into the day's credit"
    assert concept_life.concept_stage(progress) == concept_life.STAGE_PRACTISING

    lapse_day, second_use_day = 3, 10
    rappel_formats: list[tuple[int, str, float]] = []
    lapsed = repaired = False
    for offset in range(1, 22):
        today = Day(db_session, user, DAY0 + timedelta(days=offset))
        before = _progress(db_session, user, concept_id)
        due = _aware(before.next_review) <= today.now
        if due:
            items = _grammar_steps(today.plan(), concept_id)
            band = grammar_items.review_band(before.stability)
            if band == "high":
                assert not items, "a strong unit is asked for in the reply"
            else:
                assert len(items) == 1, "one interleaved Rappel item a day"
                assert items[0].ordinal < [s.kind for s in today.plan().steps].index(StepKind.SCENE)
                rappel_formats.append((offset, items[0].private_task.task_type, before.stability))
                today.answer(items[0])
                if lapsed and not repaired:
                    repaired = True
        if offset == lapse_day:
            pair = brief["contrast_pairs"][0]
            today.reply(
                concept_id, f"{pair['wrong']} Un café.",
                correction=Correction(span_fr=pair["wrong"], corrected_fr=pair["right"], note_native="…"),
            )
            lapsed = True
            progress = _progress(db_session, user, concept_id)
            assert progress.lapses == 1
            assert _aware(progress.next_review) <= today.now + timedelta(days=1, minutes=1)
        if offset == lapse_day + 1:
            # The erratum is repaired the next day; the repair credits the unit.
            erratum = db_session.query(UserError).filter(UserError.user_id == user.id).one()
            assert erratum.concept_id == concept_id
            apply_learning_evidence(
                db_session, user=user, journey_id=today.journey_id, step_id=uuid.uuid4(),
                session=today.session, modality=InputMode.TEXT, now=today.now,
                evaluation=ResponseEvaluation(
                    outcome=TaskOutcome.MET, assistance=AssistanceLevel.NONE,
                    observations=[TargetObservation(
                        target=TargetRef(kind=TargetKind.ERROR, id=str(erratum.id), label_fr=""),
                        evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                        assistance=AssistanceLevel.NONE, modality=InputMode.TEXT,
                        learner_text=brief["contrast_pairs"][0]["right"],
                    )],
                ),
            )
        if offset == second_use_day:
            today.reply(concept_id, _free_use_sentence(brief))

    progress = _progress(db_session, user, concept_id)
    assert lapsed and repaired, rappel_formats
    assert (_aware(progress.free_use_last_at) - _aware(progress.free_use_first_at)).days >= 7
    assert progress.spaced_success_at is not None, rappel_formats
    assert progress.held_at is not None, rappel_formats
    assert concept_life.concept_stage(progress) == concept_life.STAGE_HELD
    assert concept_id in concept_life.held_concept_ids(db_session, user.id)
    # The formats grew more productive as the unit got stronger.
    assert rappel_formats[0][1] == "choice"
    assert any(fmt in {"word_bank", "tiles", "transform"} for _d, fmt, _s in rappel_formats), rappel_formats


# ---------------------------------------------------------------------------
# 6. The Règle through the real HTTP surface
# ---------------------------------------------------------------------------


def test_the_rule_step_is_served_advanced_and_introduces_the_unit(
    assembled_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    _seed(db_session, "v1")
    email = f"wp-l4-api-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    driver = Driver(assembled_client, headers, db=db_session)
    journey = driver.create()
    rules = [step for step in journey["steps"] if step["kind"] == "rule"]
    assert len(rules) == 1, [step["kind"] for step in journey["steps"]]
    assert journey["estimated_active_seconds"] <= journey["budget_seconds"] == REGULIER
    concept_id = rules[0]["prompt"]["concept_id"]
    assert rules[0]["prompt"]["rule_card"]["example"]["fr"]
    user = db_session.get(User, learner_id(db_session, email))
    assert concept_life.concept_stage(_progress(db_session, user, concept_id)) == concept_life.STAGE_NEW

    for _ in range(60):
        step = driver.current()
        if step is None or step["kind"] == "rule":
            break
        if step["kind"] == "recall":
            driver.attempt(driver.recall_answer(step, correct=True))
            if driver.journey.get("current_step_id") == step["id"]:
                driver.advance()
        else:
            driver.advance()
    assert driver.current()["kind"] == "rule"
    driver.advance()
    progress = _progress(db_session, user, concept_id)
    assert progress is not None and progress.introduced_at is not None
    assert concept_life.concept_stage(progress) == concept_life.STAGE_INTRODUCED
    assert driver.current()["kind"] == "recall"
    assert driver.current()["prompt"]["target"]["kind"] == "grammar"
    assert not driver.private_leaks


def test_the_new_migration_follows_the_wp_l9_head() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "alembic" / "versions" / "f2a4c6e8b0d1_wpl4_concept_life.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "f2a4c6e8b0d1"' in source
    assert 'down_revision = "e1f3a5b7c9d2"' in source
    for column in ("introduced_at", "free_use_first_at", "free_use_last_at", "spaced_success_at", "held_at"):
        assert column in UserGrammarProgress.__table__.columns
        assert f'"{column}"' in source


def test_grammar_items_stay_pure() -> None:
    import ast
    from pathlib import Path

    source = Path(grammar_items.__file__).read_text(encoding="utf-8")
    imported = {
        node.module for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported <= {"__future__", "typing", "app.services.journey_contracts"}, imported

