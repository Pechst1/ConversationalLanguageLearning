"""WP-05 — the foreground correction policy (CONTRACTS §7).

One actionable correction per turn, chosen by relevance. No punishment event
for a no-op, a fabricated span, a stylistic re-punctuation, or model output
that cannot be validated. The learner's stored corrector preference bounds how
many *additional* validated errors reach memory; it never silently removes the
detailed view.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.error import UserError
from app.db.models.session import SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    Correction,
    EvidenceKind,
    InputMode,
    RecallTask,
    ResponseEvaluation,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import (
    JOURNEY_SOURCE_TYPE,
    apply_learning_evidence,
    build_correction,
    correction_relevance,
    ensure_journey_learning_session,
    evaluate_recall,
    select_foreground_correction,
    validate_correction,
)

LEARNER_TEXT = "Je veux un café s'il vous plaît et je suis allé au marché hier"


def _user(db_session, *, correction_level: str = "moderate") -> User:
    user = User(
        id=uuid4(),
        email=f"correction-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        grammar_correction_level=correction_level,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _word(db_session, word: str = "café") -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word.lower(),
        english_translation=f"{word}-en",
        difficulty_level=1,
        frequency_rank=10,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _target(word: VocabularyWord) -> TargetRef:
    return TargetRef(kind=TargetKind.VOCABULARY, id=str(word.id), label_fr=word.word)


def _errata(db_session, user) -> list[UserError]:
    return (
        db_session.query(UserError)
        .filter(UserError.user_id == user.id, UserError.source_type == JOURNEY_SOURCE_TYPE)
        .all()
    )


def _moments(db_session, user, *, kind: str | None = None):
    """Learning moments for THIS test's user only.

    The SQLite engine is session-scoped and `db_session` does not roll back, so
    an unscoped count picks up rows from every other test module.
    """

    query = db_session.query(SessionLearningMoment).filter(
        SessionLearningMoment.user_id == user.id
    )
    if kind is not None:
        query = query.filter(SessionLearningMoment.kind == kind)
    return query.all()


def _apply(db_session, *, user, session, evaluation, journey_id, step_id):
    return apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=evaluation,
        modality=InputMode.TEXT,
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def test_a_no_op_correction_is_rejected():
    identical = Correction(
        span_fr="Je veux un café", corrected_fr="Je veux un café", note_native="n/a"
    )
    assert identical.is_valid_for(LEARNER_TEXT) is False
    assert validate_correction(identical, LEARNER_TEXT) is False
    assert build_correction(
        learner_text="Je veux un café",
        corrected_fr="Je veux un café",
        note_native="n/a",
    ) is None


def test_a_correction_that_only_re_punctuates_is_rejected():
    """ASR invents commas and full stops. That is not a learner mistake."""

    asr = Correction(
        span_fr="je suis allé au marché hier",
        corrected_fr="Je suis allé au marché, hier.",
        note_native="Punctuation",
    )
    assert validate_correction(asr, LEARNER_TEXT) is False
    foreground, background = select_foreground_correction(
        user=User(email="x@example.com", hashed_password="t"),
        learner_text=LEARNER_TEXT,
        candidates=[asr],
    )
    assert foreground is None
    assert background == []


def test_a_correction_that_only_restores_an_accent_is_rejected():
    accents_only = Correction(
        span_fr="je suis allé au marché hier",
        corrected_fr="je suis alle au marche hier",
        note_native="Accents",
    )
    assert validate_correction(accents_only, LEARNER_TEXT) is False


def test_a_fabricated_quote_span_is_rejected():
    """A span the learner never wrote cannot become an erratum."""

    fabricated = Correction(
        span_fr="je vais à la piscine",
        corrected_fr="je vais à la piscine municipale",
        note_native="Invented by the model",
    )
    assert fabricated.is_valid_for(LEARNER_TEXT) is False
    assert validate_correction(fabricated, LEARNER_TEXT) is False


@pytest.mark.parametrize(
    "span,corrected",
    [("", "Je voudrais"), ("Je veux", ""), ("   ", "   ")],
)
def test_empty_spans_are_rejected(span, corrected):
    assert validate_correction(
        Correction(span_fr=span, corrected_fr=corrected, note_native=""), LEARNER_TEXT
    ) is False


def test_model_output_that_cannot_be_validated_yields_nothing():
    assert validate_correction(None, LEARNER_TEXT) is False
    assert build_correction(learner_text=None, corrected_fr="Je voudrais", note_native="") is None
    assert build_correction(learner_text="Je veux", corrected_fr=None, note_native="") is None


def test_build_correction_folds_smart_quotes_before_deciding():
    """iOS types U+2019; that is the same sentence, not an error."""

    assert build_correction(
        learner_text="s’il vous plait",
        corrected_fr="s'il vous plaît",
        note_native="Apostrophe",
    ) is None


# --------------------------------------------------------------------------
# One foreground correction, chosen by relevance
# --------------------------------------------------------------------------

def test_only_one_correction_is_foregrounded(db_session):
    user = _user(db_session, correction_level="strict")
    candidates = [
        Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness"),
        Correction(span_fr="je suis allé", corrected_fr="je suis allée", note_native="Agreement"),
        Correction(span_fr="hier", corrected_fr="hier soir", note_native="Precision"),
    ]
    foreground, background = select_foreground_correction(
        user=user, learner_text=LEARNER_TEXT, candidates=candidates
    )
    assert foreground is not None
    assert isinstance(foreground, Correction)
    assert len(background) == 2, "strict keeps the detailed view"
    assert foreground not in background


def test_the_foreground_correction_is_the_one_closest_to_the_learning_target(db_session):
    user = _user(db_session)
    targets = [TargetRef(kind=TargetKind.GRAMMAR, id="7", label_fr="voudrais")]
    unrelated = Correction(span_fr="hier", corrected_fr="hier soir", note_native="Precision")
    on_target = Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness")
    assert correction_relevance(on_target, targets) > correction_relevance(unrelated, targets)

    foreground, _ = select_foreground_correction(
        user=user,
        learner_text=LEARNER_TEXT,
        candidates=[unrelated, on_target],
        targets=targets,
    )
    assert foreground == on_target


@pytest.mark.parametrize(
    "level,expected_background",
    [("lenient", 0), ("moderate", 1), ("strict", 2)],
)
def test_the_stored_corrector_preference_bounds_the_background_not_the_foreground(
    db_session, level, expected_background
):
    user = _user(db_session, correction_level=level)
    candidates = [
        Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness"),
        Correction(span_fr="je suis allé", corrected_fr="je suis allée", note_native="Agreement"),
        Correction(span_fr="hier", corrected_fr="hier soir", note_native="Precision"),
    ]
    foreground, background = select_foreground_correction(
        user=user, learner_text=LEARNER_TEXT, candidates=candidates
    )
    assert foreground is not None, "a stored preference never silently removes the correction"
    assert len(background) == expected_background


def test_an_unset_corrector_preference_falls_back_to_moderate(db_session):
    user = _user(db_session)
    user.grammar_correction_level = None
    db_session.flush()
    _, background = select_foreground_correction(
        user=user,
        learner_text=LEARNER_TEXT,
        candidates=[
            Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="a"),
            Correction(span_fr="hier", corrected_fr="hier soir", note_native="b"),
            Correction(span_fr="je suis allé", corrected_fr="je suis allée", note_native="c"),
        ],
    )
    assert len(background) == 1


# --------------------------------------------------------------------------
# Persistence: one punishment event per turn, deduplicated
# --------------------------------------------------------------------------

def _evaluation_with_correction(correction: Correction | None) -> ResponseEvaluation:
    return ResponseEvaluation(
        outcome=TaskOutcome.MET,
        assistance=AssistanceLevel.NONE,
        observations=[],
        correction=correction,
    )


def test_one_response_records_exactly_one_erratum(db_session):
    user = _user(db_session, correction_level="strict")
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    correction = Correction(
        span_fr="Je veux", corrected_fr="Je voudrais", note_native="Use the polite conditional."
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=_evaluation_with_correction(correction),
        journey_id=journey_id,
        step_id=step_id,
    )
    errata = _errata(db_session, user)
    assert len(errata) == 1, "one response must not manufacture several punishment events"
    assert errata[0].original_text == "Je veux"
    assert errata[0].correction == "Je voudrais"
    assert errata[0].occurrences == 1


def test_replaying_a_correction_does_not_punish_twice(db_session):
    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    evaluation = _evaluation_with_correction(
        Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness")
    )
    first = _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=journey_id, step_id=step_id,
    )
    second = _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=journey_id, step_id=step_id,
    )
    errata = _errata(db_session, user)
    assert len(errata) == 1
    assert errata[0].occurrences == 1, "a replay is not a second mistake"
    assert errata[0].lapses == 0
    assert second.deduplicated_source_keys == first.source_keys
    assert len(_moments(db_session, user, kind="journey_correction")) == 1


def test_a_no_op_correction_never_reaches_error_memory(db_session):
    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=_evaluation_with_correction(
            Correction(span_fr="Je veux", corrected_fr="Je veux", note_native="n/a")
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    assert _errata(db_session, user) == []
    assert _moments(db_session, user, kind="journey_correction") == []
    # The turn itself is still capability evidence, and it still carries no
    # credit: a no-op correction changes neither of those.
    objective = _moments(db_session, user, kind="journey_objective")
    assert len(objective) == 1
    assert objective[0].srs_credit_applied is False
    assert objective[0].score_0_10 is None


def test_asr_punctuation_never_reaches_error_memory(db_session):
    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=_evaluation_with_correction(
            Correction(
                span_fr="je suis allé au marché hier",
                corrected_fr="Je suis allé au marché, hier.",
                note_native="Punctuation",
            )
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    assert _errata(db_session, user) == []


def test_a_recall_miss_produces_one_validated_correction(db_session):
    user = _user(db_session)
    word = _word(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    task = RecallTask(
        task_type="short_answer",
        instruction_native="Ask for a coffee.",
        prompt_fr="Comment demandez-vous un café ?",
        options=[],
        target=_target(word),
        optional=False,
        accepted_answers=["un café, s'il vous plaît"],
        solution_fr="un café, s'il vous plaît",
        hint_native="Start with 'un'.",
    )
    evaluation = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="je veux un marteau"),
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.correction is not None
    assert evaluation.correction.is_valid_for("je veux un marteau")

    _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=journey_id, step_id=step_id,
    )
    errata = _errata(db_session, user)
    assert len(errata) == 1, "the lapse and its correction are one punishment event"
    assert errata[0].original_text == "je veux un marteau"
    assert errata[0].correction == "un café, s'il vous plaît"


def test_a_correct_recall_produces_no_correction(db_session):
    user = _user(db_session)
    word = _word(db_session)
    task = RecallTask(
        task_type="short_answer",
        instruction_native="Ask for a coffee.",
        prompt_fr="Comment demandez-vous un café ?",
        options=[],
        target=_target(word),
        optional=False,
        accepted_answers=["un café, s'il vous plaît"],
        solution_fr="un café, s'il vous plaît",
    )
    evaluation = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un cafe, s il vous plait."),
        assistance=AssistanceLevel.NONE,
    )
    assert evaluation.outcome is TaskOutcome.MET
    assert evaluation.correction is None


def test_an_unscored_turn_records_no_correction(db_session):
    """Infrastructure failure is never a correction, and never a punishment."""

    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.UNSCORED,
            assistance=AssistanceLevel.NONE,
            observations=[],
            correction=Correction(
                span_fr="je veux", corrected_fr="je voudrais", note_native="Politeness"
            ),
            pending=True,
            failure_reason="provider_timeout",
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    assert _errata(db_session, user) == []
    assert _moments(db_session, user) == []


def test_the_journey_erratum_renders_a_mapped_source_label(db_session):
    """An unmapped source_type printed the raw key on the repair card."""

    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=_evaluation_with_correction(
            Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness")
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    erratum = _errata(db_session, user)[0]
    payload = serialize_error_memory(erratum)
    assert payload["source_label"] == "La séance du jour"
    assert payload["source_label"] != JOURNEY_SOURCE_TYPE

    task = ErrorMemoryService(db_session).build_review_task(user=user, error_id=erratum.id)
    assert task is not None
    assert task["source_label"] == "La séance du jour"
    assert "target_answer" not in task, "the repair card must not ship the answer"


def test_the_journey_correction_becomes_a_reviewable_erratum(db_session):
    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=_evaluation_with_correction(
            Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness")
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    erratum = _errata(db_session, user)[0]
    erratum.next_review_date = datetime.now(UTC) - timedelta(hours=1)
    db_session.flush()

    due = ErrorMemoryService(db_session).due_error_records(user)
    assert erratum.id in {row.id for row in due}


def test_a_second_distinct_correction_in_a_later_step_is_recorded(db_session):
    """Bounding per turn is not the same as never correcting again."""

    user = _user(db_session)
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    for correction in (
        Correction(span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness"),
        Correction(span_fr="je suis allé", corrected_fr="je suis allée", note_native="Agreement"),
    ):
        _apply(
            db_session,
            user=user,
            session=session,
            evaluation=_evaluation_with_correction(correction),
            journey_id=journey_id,
            step_id=uuid4(),
        )
    assert len(_errata(db_session, user)) == 2


def test_a_correction_does_not_by_itself_credit_or_punish_a_target(db_session):
    """A form error next to a communicative success is not a vocabulary lapse."""

    user = _user(db_session)
    word = _word(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    applied = _apply(
        db_session,
        user=user,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je veux un café",
                )
            ],
            correction=Correction(
                span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness"
            ),
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    kinds = {
        key.rsplit(":", 1)[-1] for key in applied.source_keys
    }
    assert "produced_independent" in kinds
    assert len(_errata(db_session, user)) == 1
    (vocabulary_moment,) = _moments(db_session, user, kind="journey_vocabulary")
    assert vocabulary_moment.result_payload["evidence_kind"] == "produced_independent", (
        "the communicative success stands even though the form was corrected"
    )


def test_a_fabricated_span_is_rejected_at_write_time_too(db_session):
    """Defence in depth: the span is re-checked against the recorded answer."""

    user = _user(db_session)
    word = _word(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je voudrais un café",
                )
            ],
            correction=Correction(
                span_fr="je vais à la piscine",
                corrected_fr="je vais à la piscine municipale",
                note_native="Invented by the model",
            ),
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    assert _errata(db_session, user) == []
    assert _moments(db_session, user, kind="journey_correction") == []


def test_a_correction_quoting_the_recorded_answer_is_kept(db_session):
    user = _user(db_session)
    word = _word(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session,
        user=user,
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je veux un café",
                )
            ],
            correction=Correction(
                span_fr="Je veux", corrected_fr="Je voudrais", note_native="Politeness"
            ),
        ),
        journey_id=journey_id,
        step_id=step_id,
    )
    errata = _errata(db_session, user)
    assert len(errata) == 1
    assert errata[0].correction == "Je voudrais"
