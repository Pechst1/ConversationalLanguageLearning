"""WP-05 — canonical learning evidence, review, and dedup policy."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.journey_contracts import (
    AssistanceLevel,
    AttemptAnswer,
    CapabilityKey,
    EvidenceKind,
    InputMode,
    RecallTask,
    ResponseEvaluation,
    ResponseTask,
    ScenarioBrief,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
    evidence_source_key,
)
from app.services.journey_learning import (
    EVIDENCE_HISTORY_NONE,
    EVIDENCE_HISTORY_RECORDED,
    EVIDENCE_HISTORY_UNKNOWN,
    JOURNEY_SOURCE_TYPE,
    answer_matches,
    apply_learning_evidence,
    classify_observation,
    ensure_journey_learning_session,
    evaluate_recall,
    journey_session_topic,
    read_journey_evidence,
    select_learning_candidates,
)
from app.services.session_moment_planner import (
    JOURNEY_MOMENT_SOURCE_TYPE,
    SessionMomentPlanner,
)

# --------------------------------------------------------------------------
# Fixtures / builders
# --------------------------------------------------------------------------

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


def _naive(value):
    """SQLite drops tzinfo on refresh; compare wall-clock values."""

    return value.replace(tzinfo=None) if hasattr(value, "tzinfo") else value


def _schedule_snapshot(progress) -> tuple:
    return (
        _naive(progress.due_at),
        _naive(progress.next_review_date),
        progress.due_date,
        progress.reps,
        progress.lapses,
    )


def _user(db_session, **kwargs) -> User:
    user = User(
        id=uuid4(),
        email=f"journey-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
        **kwargs,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _word(db_session, word: str, *, difficulty: int = 1, rank: int = 100) -> VocabularyWord:
    row = VocabularyWord(
        language="fr",
        word=word,
        normalized_word=word.lower(),
        english_translation=f"{word}-en",
        difficulty_level=difficulty,
        frequency_rank=rank,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _due_progress(db_session, user, word, *, days_overdue: int = 2) -> UserVocabularyProgress:
    now = datetime.now(UTC)
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        state="review",
        stability=3.0,
        difficulty=5.0,
        reps=2,
        due_at=now - timedelta(days=days_overdue),
        next_review_date=now - timedelta(days=days_overdue),
        due_date=(now - timedelta(days=days_overdue)).date(),
    )
    db_session.add(progress)
    db_session.flush()
    return progress


def _concept(db_session, name: str = "Partitive article") -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A2_{uuid4().hex[:8]}",
        language="fr",
        name=name,
        level="A2",
        category="Articles",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    return concept


def _error(db_session, user, *, correction: str = "je voudrais") -> UserError:
    row = UserError(
        user_id=user.id,
        error_category="grammar",
        error_pattern="conditional_politeness",
        original_text="je veux",
        correction=correction,
        display_label="Politesse au comptoir",
        task_error_type="grammar_target",
        source_type="atelier",
        review_mode="grammar",
        memory_key=f"grammar:concept-none:grammar_target:{uuid4().hex[:8]}",
        state="new",
        next_review_date=datetime.now(UTC) - timedelta(days=1),
        occurrences=1,
        lapses=0,
        reps=0,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _scenario(**overrides) -> ScenarioBrief:
    task = ResponseTask(
        objective_native="Order a coffee at the counter.",
        character_id="margaux_barman",
        character_name="Margaux",
        opening_line_fr="Bonjour, qu'est-ce que je vous sers ?",
        targets=overrides.pop("targets", []),
        required_intents=["order_drink"],
        allowed_outcomes=["served_at_terrace"],
        rubric_native="The learner orders a drink politely.",
        suggested_response_fr="Un café, s'il vous plaît.",
    )
    base = {
        "scenario_key": CapabilityKey.ORDER_AT_CAFE,
        "content_version": "journey-content-v1",
        "title_fr": "Au comptoir du Mistral",
        "objective_key": "order_at_cafe.counter_drink",
        "objective_native": "Order a coffee at the counter.",
        "level_band": "A2",
        "character_id": "margaux_barman",
        "character_name": "Margaux",
        "location_id": "le_mistral",
        "location_name": "Le Mistral",
        "image_url": None,
        "setup_fr": "Vous entrez au Mistral et vous commandez un café au comptoir.",
        "setup_native": "You walk into Le Mistral and order a coffee at the counter.",
        "opening_line_fr": "Bonjour, qu'est-ce que je vous sers ?",
        "response_task": task,
    }
    base.update(overrides)
    return ScenarioBrief(**base)


def _recall_task(target: TargetRef, **overrides) -> RecallTask:
    base = {
        "task_type": "short_answer",
        "instruction_native": "Ask for a coffee.",
        "prompt_fr": "Comment demandez-vous un café ?",
        "options": [],
        "target": target,
        "optional": False,
        "accepted_answers": ["un café, s'il vous plaît"],
        "solution_fr": "un café, s'il vous plaît",
        "hint_native": "Start with 'un'.",
    }
    base.update(overrides)
    return RecallTask(**base)


def _target_for(word: VocabularyWord) -> TargetRef:
    return TargetRef(
        kind=TargetKind.VOCABULARY,
        id=str(word.id),
        label_fr=word.word,
        label_native=word.english_translation,
    )


def _apply(db_session, *, user, session, evaluation, journey_id, step_id, modality=InputMode.TEXT, **kw):
    return apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=step_id,
        session=session,
        evaluation=evaluation,
        modality=modality,
        **kw,
    )


# --------------------------------------------------------------------------
# 1. Candidate adapter
# --------------------------------------------------------------------------

def test_candidates_prefer_scenario_relevance_and_cap_at_two_due_plus_one_new(db_session):
    user = _user(db_session)
    relevant = _word(db_session, "café", rank=5)
    unrelated_a = _word(db_session, "marteau", rank=6)
    unrelated_b = _word(db_session, "charrue", rank=7)
    _word(db_session, "comptoir", rank=8)  # in the scene, never practised -> new anchor

    _due_progress(db_session, user, relevant, days_overdue=1)
    _due_progress(db_session, user, unrelated_a, days_overdue=30)
    _due_progress(db_session, user, unrelated_b, days_overdue=40)

    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())

    assert len(candidates) <= 3
    due = [c for c in candidates if not c.is_new]
    new = [c for c in candidates if c.is_new]
    assert len(due) <= 2
    assert len(new) <= 1
    assert candidates[0].target.id == str(relevant.id), "scene fit beats raw overdue urgency"
    assert candidates[0].relevance > 0


def test_omitted_candidates_keep_their_due_dates(db_session):
    user = _user(db_session)
    words = [_word(db_session, name, rank=i) for i, name in enumerate(
        ["café", "marteau", "charrue", "enclume", "brouette"], start=1
    )]
    progresses = [_due_progress(db_session, user, word, days_overdue=5 + i) for i, word in enumerate(words)]
    before = {p.word_id: _schedule_snapshot(p) for p in progresses}

    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())
    selected_ids = {c.target.id for c in candidates}
    assert len(selected_ids) < len(words), "not every due word can be selected"

    db_session.flush()
    for progress in progresses:
        db_session.refresh(progress)
        assert _schedule_snapshot(progress) == before[progress.word_id], (
            "an omitted candidate stays exactly as due as it was"
        )


def test_empty_queue_returns_an_empty_list_and_invents_nothing(db_session):
    user = _user(db_session)
    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())
    assert candidates == []


def test_new_anchor_is_marked_new_and_never_claimed_due(db_session):
    user = _user(db_session)
    _word(db_session, "comptoir", rank=3)
    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())
    assert len(candidates) == 1
    anchor = candidates[0]
    assert anchor.is_new is True
    assert anchor.due_since_days == 0
    assert anchor.priority_score == 0.0


def test_grammar_and_error_targets_reach_the_candidate_pool(db_session):
    user = _user(db_session)
    concept = _concept(db_session, name="Café order politeness")
    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            score=2.0,
            reps=1,
            state="in_arbeit",
            next_review=datetime.now(UTC) - timedelta(days=2),
        )
    )
    _error(db_session, user)
    db_session.flush()

    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario(), limit=3)
    kinds = {candidate.target.kind for candidate in candidates}
    assert kinds <= {TargetKind.GRAMMAR, TargetKind.ERROR, TargetKind.VOCABULARY}
    assert candidates, "a due grammar concept and a due erratum are real candidates"


# --------------------------------------------------------------------------
# 2. Canonical learning session
# --------------------------------------------------------------------------

def test_journey_learning_session_is_idempotent_per_journey(db_session):
    user = _user(db_session)
    journey_id = uuid4()
    first = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    second = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    assert first.id == second.id
    assert first.topic == journey_session_topic(journey_id)
    assert (
        db_session.query(LearningSession)
        .filter(LearningSession.user_id == user.id, LearningSession.topic == first.topic)
        .count()
        == 1
    )


def test_journey_learning_session_does_not_commit(db_session, monkeypatch):
    user = _user(db_session)

    def _boom(*args, **kwargs):
        raise AssertionError("journey_learning must not commit; the caller owns the transaction")

    monkeypatch.setattr(db_session, "commit", _boom)
    ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )


# --------------------------------------------------------------------------
# 3. Evidence classification rubric
# --------------------------------------------------------------------------

def test_choice_selection_is_recognition_never_production(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    task = _recall_task(
        _target_for(word),
        task_type="choice",
        options=[{"id": "a", "text_fr": "un café"}, {"id": "b", "text_fr": "un marteau"}],
        correct_option_id="a",
    )
    result = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="un café", option_id="a"),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.MET
    assert result.observations[0].evidence_kind is EvidenceKind.RECOGNIZED


def test_tile_drag_is_recognition_never_production(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    task = _recall_task(
        _target_for(word),
        task_type="tiles",
        correct_tile_order=["t1", "t2", "t3"],
    )
    result = evaluate_recall(
        db_session,
        user=user,
        task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="", tile_ids=["t1", "t2", "t3"]),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.MET
    assert result.observations[0].evidence_kind is EvidenceKind.RECOGNIZED


def test_unassisted_open_production_is_independent(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
        assistance=AssistanceLevel.NONE,
    )
    assert result.observations[0].evidence_kind is EvidenceKind.PRODUCED_INDEPENDENT


@pytest.mark.parametrize(
    "assistance",
    [
        AssistanceLevel.HINT,
        AssistanceLevel.TRANSLATION,
        AssistanceLevel.SOLUTION,
        AssistanceLevel.SUGGESTED_RESPONSE,
    ],
)
def test_assisted_open_production_is_supported_not_independent(db_session, assistance):
    user = _user(db_session)
    word = _word(db_session, "café")
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
        assistance=assistance,
    )
    assert result.observations[0].evidence_kind is EvidenceKind.PRODUCED_SUPPORTED


def test_copied_suggested_response_is_never_independent(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        # verbatim copy of ScenarioBrief.response_task.suggested_response_fr
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît."),
        assistance=AssistanceLevel.SUGGESTED_RESPONSE,
    )
    assert result.observations[0].evidence_kind is EvidenceKind.PRODUCED_SUPPORTED


@pytest.mark.parametrize(
    "text",
    [
        "un café, s'il vous plaît",
        "Un cafe s il vous plait",          # no accents, apostrophe as a space
        "un café, s’il vous plaît",    # iOS smart apostrophe
        "Un café, s'il vous plaît !!",      # ASR punctuation
        "Bonjour, un café, s'il vous plaît, merci.",  # extra politeness
    ],
)
def test_differently_worded_french_is_not_penalised(db_session, text):
    user = _user(db_session)
    word = _word(db_session, "café")
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text=text),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.MET, text
    assert result.observations[0].evidence_kind is EvidenceKind.PRODUCED_INDEPENDENT


def test_wrong_answer_is_not_yet(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="je veux un marteau"),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.observations[0].evidence_kind is EvidenceKind.NOT_YET
    assert result.pending is False


def test_answer_matches_rejects_unrelated_text():
    assert answer_matches("un café", ["un café, s'il vous plaît"]) is False
    assert answer_matches("", ["un café"]) is False


# --------------------------------------------------------------------------
# Empty text and infrastructure failure
# --------------------------------------------------------------------------

def test_empty_text_records_no_evidence_and_no_lapse(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    before = _schedule_snapshot(progress)

    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="   "),
        assistance=AssistanceLevel.NONE,
    )
    assert result.outcome is TaskOutcome.NOT_YET
    assert result.failure_reason == "empty_answer"
    assert result.observations == []

    applied = _apply(
        db_session,
        user=user,
        session=session,
        evaluation=result,
        journey_id=uuid4(),
        step_id=uuid4(),
    )
    assert applied.source_keys == []
    db_session.refresh(progress)
    assert _schedule_snapshot(progress) == before


def test_voice_transcription_failure_is_unscored_and_mutates_nothing(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    before = (*_schedule_snapshot(progress), progress.state)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )

    # No transcript_ref: contract revision 1 makes it optional, so the modality
    # plus an empty transcript is the infrastructure signal.
    result = evaluate_recall(
        db_session,
        user=user,
        task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.VOICE, text=""),
        assistance=AssistanceLevel.NONE,
    )
    assert result.pending is True
    assert result.outcome is TaskOutcome.UNSCORED
    assert result.failure_reason == "transcription_unavailable"
    assert result.observations == []

    applied = _apply(
        db_session,
        user=user,
        session=session,
        evaluation=result,
        journey_id=journey_id,
        step_id=step_id,
        modality=InputMode.VOICE,
    )
    assert applied.source_keys == []
    assert applied.learning_moment_id is None
    db_session.refresh(progress)
    assert (*_schedule_snapshot(progress), progress.state) == before
    assert _moments(db_session, user) == []


def test_delayed_grading_pending_then_scored(db_session):
    """A pending grade writes nothing; the later real grade writes once."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    target = _target_for(word)

    pending = ResponseEvaluation(
        outcome=TaskOutcome.UNSCORED,
        assistance=AssistanceLevel.NONE,
        observations=[
            TargetObservation(
                target=target,
                evidence_kind=EvidenceKind.UNSCORED,
                assistance=AssistanceLevel.NONE,
                modality=InputMode.VOICE,
            )
        ],
        pending=True,
        failure_reason="provider_timeout",
    )
    assert _apply(
        db_session, user=user, session=session, evaluation=pending,
        journey_id=journey_id, step_id=step_id,
    ).source_keys == []
    assert _moments(db_session, user) == []

    scored = ResponseEvaluation(
        outcome=TaskOutcome.MET,
        assistance=AssistanceLevel.NONE,
        observations=[
            TargetObservation(
                target=target,
                evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                assistance=AssistanceLevel.NONE,
                modality=InputMode.VOICE,
                learner_text="Un café, s'il vous plaît",
            )
        ],
    )
    applied = _apply(
        db_session, user=user, session=session, evaluation=scored,
        journey_id=journey_id, step_id=step_id, modality=InputMode.VOICE,
    )
    assert len(applied.source_keys) == 1
    assert len(_moments(db_session, user)) == 1


# --------------------------------------------------------------------------
# 4. Retry, dedup, replay
# --------------------------------------------------------------------------

def test_retry_after_a_reveal_does_not_erase_the_first_attempt(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    task = _recall_task(_target_for(word))

    first = evaluate_recall(
        db_session, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="je veux un marteau"),
        assistance=AssistanceLevel.NONE,
    )
    _apply(db_session, user=user, session=session, evaluation=first,
           journey_id=journey_id, step_id=step_id)

    # Learner opens the solution, then answers correctly.
    second = evaluate_recall(
        db_session, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
        assistance=AssistanceLevel.SOLUTION,
    )
    _apply(db_session, user=user, session=session, evaluation=second,
           journey_id=journey_id, step_id=step_id)

    kinds = {
        (row.result_payload or {}).get("evidence_kind")
        for row in _moments(db_session, user, kind="journey_vocabulary")
    }
    assert kinds == {"not_yet", "produced_supported"}
    assert "produced_independent" not in kinds


def test_a_later_independent_attempt_in_an_assisted_step_stays_supported(db_session):
    """Assistance already revealed in this step is never downgraded to none."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    task = _recall_task(_target_for(word))

    _apply(
        db_session, user=user, session=session,
        evaluation=evaluate_recall(
            db_session, user=user, task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text="un marteau"),
            assistance=AssistanceLevel.SOLUTION,
        ),
        journey_id=journey_id, step_id=step_id,
    )
    # The client now claims an unassisted correct retry on the same step.
    applied = _apply(
        db_session, user=user, session=session,
        evaluation=evaluate_recall(
            db_session, user=user, task=task,
            answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
            assistance=AssistanceLevel.NONE,
        ),
        journey_id=journey_id, step_id=step_id,
    )
    assert applied.source_keys[0].endswith(":produced_supported")


def test_the_same_source_key_credits_exactly_once(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    evaluation = evaluate_recall(
        db_session, user=user, task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
        assistance=AssistanceLevel.NONE,
    )

    first = _apply(db_session, user=user, session=session, evaluation=evaluation,
                   journey_id=journey_id, step_id=step_id)
    db_session.refresh(progress)
    reps_after_first = progress.reps

    # Route 2: the same evidence resubmitted (HTTP retry / worker retry / other surface).
    second = _apply(db_session, user=user, session=session, evaluation=evaluation,
                    journey_id=journey_id, step_id=step_id)
    db_session.refresh(progress)

    assert second.source_keys == first.source_keys
    assert second.evidence_ref == first.evidence_ref
    assert second.learning_moment_id == first.learning_moment_id
    assert second.applied_target_ids == first.applied_target_ids
    assert second.deduplicated_source_keys == first.source_keys
    assert first.deduplicated_source_keys == []
    assert progress.reps == reps_after_first, "no second credit"
    assert len(_moments(db_session, user)) == 1


def test_crash_retry_replay_is_stable_across_three_attempts(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    evaluation = evaluate_recall(
        db_session, user=user, task=_recall_task(_target_for(word)),
        answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
        assistance=AssistanceLevel.NONE,
    )
    results = [
        _apply(db_session, user=user, session=session, evaluation=evaluation,
               journey_id=journey_id, step_id=step_id)
        for _ in range(3)
    ]
    db_session.refresh(progress)
    assert progress.reps == 3, "2 seeded reps + exactly one credited review"
    assert {r.evidence_ref for r in results} == {f"journey:{journey_id}:{step_id}"}
    assert len(_moments(db_session, user)) == 1


def test_source_key_matches_the_frozen_grammar(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    applied = _apply(
        db_session, user=user, session=session,
        evaluation=evaluate_recall(
            db_session, user=user, task=_recall_task(_target_for(word)),
            answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
            assistance=AssistanceLevel.NONE,
        ),
        journey_id=journey_id, step_id=step_id,
    )
    assert applied.source_keys == [
        evidence_source_key(
            journey_id=journey_id,
            step_id=step_id,
            target_kind="vocabulary",
            target_id=str(word.id),
            evidence_kind="produced_independent",
        )
    ]


def test_concurrent_standalone_review_is_applied_to_current_state(db_session):
    """Independent practice between planning and submission is not overwritten."""

    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word, days_overdue=3)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())
    assert candidates and candidates[0].target.id == str(word.id)

    # The learner reviews the same word in the standalone vocabulary surface.
    from app.services.progress import ProgressService

    ProgressService(db_session).record_review(user=user, word=word, rating=3)
    db_session.flush()
    db_session.refresh(progress)
    reps_after_standalone = progress.reps
    due_after_standalone = progress.due_at

    _apply(
        db_session, user=user, session=session,
        evaluation=evaluate_recall(
            db_session, user=user, task=_recall_task(_target_for(word)),
            answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
            assistance=AssistanceLevel.NONE,
        ),
        journey_id=journey_id, step_id=step_id,
    )
    db_session.refresh(progress)
    assert progress.reps == reps_after_standalone + 1, "credit stacks on the current state"
    assert progress.due_at > due_after_standalone, "scheduling moved forward, not backward"


# --------------------------------------------------------------------------
# 5. Elicitation obligation
# --------------------------------------------------------------------------

def test_missing_optional_target_is_not_a_lapse(db_session):
    user = _user(db_session)
    word = _word(db_session, "terrasse")
    progress = _due_progress(db_session, user, word)
    before = _schedule_snapshot(progress)

    observation = classify_observation(
        target=_target_for(word),
        opportunity="open_production",
        is_correct=False,
        assistance=AssistanceLevel.NONE,
        modality=InputMode.TEXT,
        elicited=False,
        learner_text="Un café, s'il vous plaît",
    )
    assert observation is None, "an unelicited optional target produces no observation"

    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    applied = _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[],
        ),
        journey_id=journey_id, step_id=step_id,
    )
    # The turn still happened, so it leaves the objective-level capability
    # record — and nothing else. No target key, no credit, no schedule change.
    assert applied.applied_target_ids == []
    assert applied.source_keys == [
        f"journey:{journey_id}:{step_id}:objective:order_at_cafe:produced_independent"
    ]
    db_session.refresh(progress)
    assert _schedule_snapshot(progress) == before


def test_missing_required_target_is_recorded_as_a_lapse(db_session):
    user = _user(db_session)
    word = _word(db_session, "terrasse")
    progress = _due_progress(db_session, user, word)
    lapses_before = progress.lapses

    observation = classify_observation(
        target=_target_for(word),
        opportunity="open_production",
        is_correct=False,
        assistance=AssistanceLevel.NONE,
        modality=InputMode.TEXT,
        elicited=True,
        learner_text="Un café, s'il vous plaît",
    )
    assert observation is not None
    assert observation.evidence_kind is EvidenceKind.NOT_YET

    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.PARTIALLY_MET,
            assistance=AssistanceLevel.NONE,
            observations=[observation],
        ),
        journey_id=journey_id, step_id=step_id,
    )
    db_session.refresh(progress)
    assert progress.lapses > lapses_before


def test_a_not_yet_without_any_learner_utterance_does_not_punish(db_session):
    user = _user(db_session)
    word = _word(db_session, "terrasse")
    progress = _due_progress(db_session, user, word)
    before = (progress.reps, progress.lapses)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.NOT_YET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.NOT_YET,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text=None,
                )
            ],
        ),
        journey_id=journey_id, step_id=step_id,
    )
    db_session.refresh(progress)
    assert (progress.reps, progress.lapses) == before
    (moment,) = _moments(db_session, user)
    assert moment.srs_credit_applied is False


# --------------------------------------------------------------------------
# 6. Canonical storage, transactions, credit routing
# --------------------------------------------------------------------------

def test_evidence_is_stored_on_the_canonical_records(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    applied = _apply(
        db_session, user=user, session=session,
        evaluation=evaluate_recall(
            db_session, user=user, task=_recall_task(_target_for(word)),
            answer=AttemptAnswer(mode=InputMode.TEXT, text="Un café, s'il vous plaît"),
            assistance=AssistanceLevel.NONE,
        ),
        journey_id=journey_id, step_id=step_id, timezone="Europe/Paris",
    )
    (moment,) = _moments(db_session, user)
    assert moment.session_id == session.id
    assert moment.source_type == JOURNEY_SOURCE_TYPE
    assert moment.status == "completed"
    assert moment.srs_credit_applied is True
    assert moment.prompt_payload["source_key"] == applied.source_keys[0]
    assert moment.prompt_payload["assistance_level"] == "none"
    assert moment.prompt_payload["modality"] == "text"
    assert moment.prompt_payload["timezone"] == "Europe/Paris"
    assert moment.result_payload["evidence_kind"] == "produced_independent"
    assert len(moment.source_id) <= 64, "source_id must fit the existing column"


def test_apply_learning_evidence_never_commits(db_session, monkeypatch):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    concept = _concept(db_session)
    error = _error(db_session, user)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )

    def _boom(*args, **kwargs):
        raise AssertionError("the journey state machine owns the transaction boundary")

    monkeypatch.setattr(db_session, "commit", _boom)
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Un café, s'il vous plaît",
                ),
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr=concept.name
                    ),
                    evidence_kind=EvidenceKind.PRODUCED_SUPPORTED,
                    assistance=AssistanceLevel.HINT,
                    modality=InputMode.TEXT,
                    learner_text="Un café, s'il vous plaît",
                ),
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.ERROR, id=str(error.id), label_fr="je voudrais"
                    ),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je voudrais un café",
                ),
            ],
        ),
        journey_id=journey_id, step_id=step_id,
    )
    assert len(_moments(db_session, user)) == 3


def test_credit_routes_to_the_existing_grammar_and_error_records(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    error = _error(db_session, user)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.GRAMMAR, id=str(concept.id), label_fr=concept.name
                    ),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je voudrais un café",
                ),
                TargetObservation(
                    target=TargetRef(
                        kind=TargetKind.ERROR, id=str(error.id), label_fr="je voudrais"
                    ),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Je voudrais un café",
                ),
            ],
        ),
        journey_id=journey_id, step_id=step_id,
    )
    grammar = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert grammar.reps == 1
    assert grammar.next_review is not None

    db_session.refresh(error)
    assert error.state == "review"
    assert error.lapses == 0
    assert _naive(error.next_review_date) > datetime.now(UTC).replace(tzinfo=None)


def test_supported_production_credits_below_independent_production(db_session):
    user = _user(db_session)
    supported_word = _word(db_session, "café")
    independent_word = _word(db_session, "thé")
    supported = _due_progress(db_session, user, supported_word)
    independent = _due_progress(db_session, user, independent_word)
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    for word, kind, assistance in (
        (supported_word, EvidenceKind.PRODUCED_SUPPORTED, AssistanceLevel.SOLUTION),
        (independent_word, EvidenceKind.PRODUCED_INDEPENDENT, AssistanceLevel.NONE),
    ):
        _apply(
            db_session, user=user, session=session,
            evaluation=ResponseEvaluation(
                outcome=TaskOutcome.MET,
                assistance=assistance,
                observations=[
                    TargetObservation(
                        target=_target_for(word),
                        evidence_kind=kind,
                        assistance=assistance,
                        modality=InputMode.TEXT,
                        learner_text="Un café, s'il vous plaît",
                    )
                ],
            ),
            journey_id=journey_id, step_id=uuid4(),
        )
    db_session.refresh(supported)
    db_session.refresh(independent)
    assert independent.due_at > supported.due_at, "assisted success schedules more conservatively"


# --------------------------------------------------------------------------
# 7. Evidence metadata for WP-09
# --------------------------------------------------------------------------

def test_read_journey_evidence_exposes_the_rubric_inputs(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.VOICE,
                    learner_text="Un café, s'il vous plaît",
                )
            ],
        ),
        journey_id=journey_id, step_id=step_id,
        modality=InputMode.VOICE, timezone="Pacific/Auckland",
    )
    records = read_journey_evidence(db_session, user=user)
    assert len(records) == 1
    record = records[0]
    assert record.target.kind is TargetKind.VOCABULARY
    assert record.evidence_kind is EvidenceKind.PRODUCED_INDEPENDENT
    assert record.assistance is AssistanceLevel.NONE
    assert record.modality is InputMode.VOICE
    assert record.is_open_production is True
    assert record.journey_id == journey_id
    assert record.step_id == step_id
    assert record.capability_key is CapabilityKey.ORDER_AT_CAFE
    assert record.timezone == "Pacific/Auckland"
    assert record.assistance_known is True
    assert record.observed_on == datetime.now(UTC).astimezone(
        __import__("zoneinfo").ZoneInfo("Pacific/Auckland")
    ).date()

    assert read_journey_evidence(db_session, user=user, journey_ids=[uuid4()]) == []


def test_a_written_result_never_reports_as_voice_evidence(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Un café",
                )
            ],
        ),
        journey_id=journey_id, step_id=uuid4(), modality=InputMode.TEXT,
    )
    assert read_journey_evidence(db_session, user=user)[0].modality is InputMode.TEXT


def test_legacy_moments_report_as_unknown_never_independent(db_session):
    user = _user(db_session)
    legacy_session = LearningSession(
        user_id=user.id, planned_duration_minutes=10, topic="Conversation", status="completed"
    )
    db_session.add(legacy_session)
    db_session.flush()
    db_session.add(
        SessionLearningMoment(
            session_id=legacy_session.id,
            user_id=user.id,
            kind="vocab_check",
            source_type="vocabulary",
            source_id="4242",
            status="completed",
            prompt_payload={"title": "café"},
            result_payload={"is_correct": True, "score_0_10": 10},
            completed_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    assert read_journey_evidence(db_session, user=user) == []
    records = read_journey_evidence(db_session, user=user, include_legacy=True)
    assert len(records) == 1
    legacy = records[0]
    assert legacy.is_legacy is True
    assert legacy.evidence_kind is None
    assert legacy.assistance is None
    assert legacy.assistance_known is False
    assert legacy.is_open_production is False


# --------------------------------------------------------------------------
# 8. No interference with the legacy inline-moment planner
# --------------------------------------------------------------------------

def test_journey_moments_never_surface_as_a_pending_inline_moment(db_session):
    from app.services.grammar import GrammarService
    from app.services.journey_learning import JOURNEY_SOURCE_TYPE as journey_source
    from app.services.progress import ProgressService

    assert JOURNEY_MOMENT_SOURCE_TYPE == journey_source

    user = _user(db_session)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )
    db_session.add(
        SessionLearningMoment(
            session_id=session.id,
            user_id=user.id,
            kind="journey_vocabulary",
            source_type=JOURNEY_SOURCE_TYPE,
            source_id="dj-deadbeef",
            status="pending",
            prompt_payload={},
        )
    )
    db_session.flush()

    planner = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
    )
    assert planner.get_pending_moment(session_id=session.id, user_id=user.id) is None


def test_the_journey_session_is_not_a_conversation_session(db_session):
    user = _user(db_session)
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    assert session.conversation_style == "daily_journey"
    assert session.scenario == "order_at_cafe"
    assert isinstance(session.id, UUID)


# --------------------------------------------------------------------------
# 9. Prior-evidence metadata for WP-04's redundant-recall skip
# --------------------------------------------------------------------------

def _force_due(db_session, progress, *, days_overdue: int = 1) -> None:
    """Put a credited word back in the queue, as the next day's run would."""

    when = datetime.now(UTC) - timedelta(days=days_overdue)
    progress.due_at = when
    progress.next_review_date = when
    progress.due_date = when.date()
    db_session.flush()


def _record_evidence(db_session, *, user, word, evidence_kind, assistance=AssistanceLevel.NONE):
    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    outcome = TaskOutcome.NOT_YET if evidence_kind is EvidenceKind.NOT_YET else TaskOutcome.MET
    return apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=uuid4(),
        session=session,
        evaluation=ResponseEvaluation(
            outcome=outcome,
            assistance=assistance,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=evidence_kind,
                    assistance=assistance,
                    modality=InputMode.TEXT,
                    learner_text="Un café, s'il vous plaît",
                )
            ],
        ),
        modality=InputMode.TEXT,
    )


def _candidate_for(candidates, word):
    return next(c for c in candidates if c.target.id == str(word.id))


def test_a_candidate_with_no_history_reports_none_and_omits_the_evidence_key(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert "last_evidence_kind" not in candidate.metadata
    assert candidate.metadata["evidence_history"] == EVIDENCE_HISTORY_NONE


def test_a_recorded_independent_demonstration_is_reported(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)

    _record_evidence(
        db_session, user=user, word=word, evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT
    )
    _force_due(db_session, progress)

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert candidate.metadata["last_evidence_kind"] == "produced_independent"
    assert candidate.metadata["evidence_history"] == EVIDENCE_HISTORY_RECORDED


def test_supported_production_is_reported_but_does_not_claim_independence(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)

    _record_evidence(
        db_session,
        user=user,
        word=word,
        evidence_kind=EvidenceKind.PRODUCED_SUPPORTED,
        assistance=AssistanceLevel.SOLUTION,
    )
    _force_due(db_session, progress)

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert candidate.metadata["last_evidence_kind"] == "produced_supported"


def test_legacy_history_with_unknown_help_usage_never_reports_a_demonstration(db_session):
    """A pre-V2 success boolean is not evidence of independent production."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)

    legacy_session = LearningSession(
        user_id=user.id, planned_duration_minutes=10, topic="Conversation", status="completed"
    )
    db_session.add(legacy_session)
    db_session.flush()
    db_session.add(
        SessionLearningMoment(
            session_id=legacy_session.id,
            user_id=user.id,
            kind="vocab_check",
            source_type="vocabulary",
            source_id=str(word.id),
            status="completed",
            prompt_payload={"title": word.word},
            result_payload={"is_correct": True, "score_0_10": 10},
            completed_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert "last_evidence_kind" not in candidate.metadata
    assert candidate.metadata["evidence_history"] == EVIDENCE_HISTORY_UNKNOWN


def test_a_later_failure_supersedes_an_earlier_demonstration(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)

    _record_evidence(
        db_session, user=user, word=word, evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT
    )
    _record_evidence(db_session, user=user, word=word, evidence_kind=EvidenceKind.NOT_YET)
    _force_due(db_session, progress)

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert candidate.metadata["last_evidence_kind"] == "not_yet"
    assert candidate.metadata["last_evidence_kind"] != "produced_independent"


def test_an_unscored_observation_is_not_reported_as_evidence(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)

    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=uuid4(),
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.UNSCORED,
            assistance=AssistanceLevel.NONE,
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.UNSCORED,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.VOICE,
                )
            ],
            pending=True,
            failure_reason="transcription_unavailable",
        ),
        modality=InputMode.VOICE,
    )

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert "last_evidence_kind" not in candidate.metadata
    assert candidate.metadata["evidence_history"] == EVIDENCE_HISTORY_NONE


def test_reading_prior_evidence_changes_no_schedule(db_session):
    """The history lookup is read-only: selecting twice is byte-identical."""

    user = _user(db_session)
    words = [_word(db_session, name, rank=i) for i, name in enumerate(
        ["café", "marteau", "charrue"], start=1
    )]
    progresses = [_due_progress(db_session, user, word, days_overdue=5 + i)
                  for i, word in enumerate(words)]
    for word in words:
        _record_evidence(
            db_session, user=user, word=word, evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT
        )
    for progress in progresses:
        _force_due(db_session, progress)
    before = {p.word_id: _schedule_snapshot(p) for p in progresses}

    first = select_learning_candidates(db_session, user=user, scenario=_scenario())
    second = select_learning_candidates(db_session, user=user, scenario=_scenario())

    assert [(c.target.id, c.priority_score, c.due_since_days, c.relevance, c.metadata)
            for c in first] == [
        (c.target.id, c.priority_score, c.due_since_days, c.relevance, c.metadata)
        for c in second
    ]
    db_session.flush()
    for progress in progresses:
        db_session.refresh(progress)
        assert _schedule_snapshot(progress) == before[progress.word_id]


def test_the_new_anchor_reports_no_prior_evidence(db_session):
    user = _user(db_session)
    _word(db_session, "comptoir", rank=3)
    candidates = select_learning_candidates(db_session, user=user, scenario=_scenario())
    assert len(candidates) == 1
    assert candidates[0].is_new is True
    assert "last_evidence_kind" not in candidates[0].metadata
    assert candidates[0].metadata["evidence_history"] == EVIDENCE_HISTORY_NONE


def test_a_simultaneous_success_and_failure_resolves_to_not_yet(db_session):
    """Ties break towards the safe answer: never over-claim a demonstration."""

    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    instant = datetime.now(UTC) - timedelta(hours=1)

    for kind in (EvidenceKind.PRODUCED_INDEPENDENT, EvidenceKind.NOT_YET):
        journey_id = uuid4()
        session = ensure_journey_learning_session(
            db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
        )
        apply_learning_evidence(
            db_session,
            user=user,
            journey_id=journey_id,
            step_id=uuid4(),
            session=session,
            evaluation=ResponseEvaluation(
                outcome=TaskOutcome.MET if kind is EvidenceKind.PRODUCED_INDEPENDENT
                else TaskOutcome.NOT_YET,
                assistance=AssistanceLevel.NONE,
                observations=[
                    TargetObservation(
                        target=_target_for(word),
                        evidence_kind=kind,
                        assistance=AssistanceLevel.NONE,
                        modality=InputMode.TEXT,
                        learner_text="Un café, s'il vous plaît",
                    )
                ],
            ),
            modality=InputMode.TEXT,
            now=instant,
        )
    _force_due(db_session, progress)

    candidate = _candidate_for(
        select_learning_candidates(db_session, user=user, scenario=_scenario()), word
    )
    assert candidate.metadata["last_evidence_kind"] == "not_yet"


def test_read_journey_evidence_reports_the_exact_instant(db_session):
    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    _record_evidence(
        db_session, user=user, word=word, evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT
    )
    record = read_journey_evidence(db_session, user=user)[0]
    assert record.observed_at is not None
    assert record.observed_at.tzinfo is not None
    assert record.observed_at.date() == record.observed_on


# --------------------------------------------------------------------------
# 9. The turn-level objective record (capability evidence, never credit)
# --------------------------------------------------------------------------

def _objective_response(
    *,
    outcome: TaskOutcome = TaskOutcome.MET,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
    observations: list | None = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        outcome=outcome, assistance=assistance, observations=observations or []
    )


def test_a_respond_turn_without_a_tracked_target_still_records_the_turn(db_session):
    """The gap that reported a finished journey as `not_tried`.

    A brand-new learner has no due vocabulary, so the response task carries no
    target and the turn produced no observation. The turn still happened.
    """

    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )

    applied = _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(),
        journey_id=journey_id, step_id=step_id,
    )

    assert applied.source_keys == [
        f"journey:{journey_id}:{step_id}:objective:order_at_cafe:produced_independent"
    ]
    assert applied.applied_target_ids == []

    record = read_journey_evidence(db_session, user=user)[0]
    assert record.is_objective is True
    assert record.target is None
    assert record.evidence_kind is EvidenceKind.PRODUCED_INDEPENDENT
    assert record.is_open_production is True
    assert record.assistance is AssistanceLevel.NONE
    assert record.assistance_known is True
    assert record.modality is InputMode.TEXT
    assert record.task_outcome is TaskOutcome.MET
    assert record.capability_key is CapabilityKey.ORDER_AT_CAFE
    assert record.journey_id == journey_id
    assert record.step_id == step_id
    assert record.observed_at is not None


def test_the_objective_record_never_credits_a_schedule(db_session):
    """Capability evidence only: no SRS row, no lapse, no vocabulary credit."""

    user = _user(db_session)
    word = _word(db_session, "café")
    progress = _due_progress(db_session, user, word)
    before = _schedule_snapshot(progress)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )

    _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(),
        journey_id=uuid4(), step_id=uuid4(),
    )

    db_session.refresh(progress)
    assert _schedule_snapshot(progress) == before
    moment = _moments(db_session, user, kind="journey_objective")[0]
    assert moment.srs_credit_applied is False
    assert moment.score_0_10 is None
    assert moment.result_payload["credit"] == {
        "skipped": "objective_evidence_is_not_scheduled"
    }


def test_the_objective_record_is_replay_safe(db_session):
    user = _user(db_session)
    journey_id, step_id = uuid4(), uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    evaluation = _objective_response()

    first = _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=journey_id, step_id=step_id,
    )
    second = _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=journey_id, step_id=step_id,
    )

    assert second.source_keys == first.source_keys
    assert second.deduplicated_source_keys == first.source_keys
    assert len(_moments(db_session, user, kind="journey_objective")) == 1


def test_help_in_the_turn_keeps_the_objective_record_supported(db_session):
    user = _user(db_session)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )

    _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(assistance=AssistanceLevel.SUGGESTED_RESPONSE),
        journey_id=uuid4(), step_id=uuid4(),
    )

    record = read_journey_evidence(db_session, user=user)[0]
    assert record.evidence_kind is EvidenceKind.PRODUCED_SUPPORTED
    assert record.assistance is AssistanceLevel.SUGGESTED_RESPONSE


def test_an_unmet_objective_is_recorded_as_not_yet_not_as_production(db_session):
    user = _user(db_session)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )

    _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(outcome=TaskOutcome.NOT_YET),
        journey_id=uuid4(), step_id=uuid4(),
    )

    record = read_journey_evidence(db_session, user=user)[0]
    assert record.evidence_kind is EvidenceKind.NOT_YET
    assert record.is_open_production is False


def test_an_unscored_respond_turn_records_no_objective_evidence(db_session):
    """An infrastructure failure is not an opportunity."""

    user = _user(db_session)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )

    applied = _apply(
        db_session, user=user, session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.UNSCORED,
            assistance=AssistanceLevel.NONE,
            observations=[],
            pending=True,
            failure_reason="provider_timeout",
        ),
        journey_id=uuid4(), step_id=uuid4(),
    )

    assert applied.source_keys == []
    assert _moments(db_session, user) == []


def test_a_recall_step_never_writes_an_objective_record(db_session):
    """Only the scenario's response turn is the capability opportunity."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )
    task = RecallTask(
        task_type="short_answer",
        instruction_native="Ask for a coffee.",
        prompt_fr="Comment demandez-vous un café ?",
        options=[],
        target=_target_for(word),
        optional=False,
        accepted_answers=["un café"],
    )
    evaluation = evaluate_recall(
        db_session, user=user, task=task,
        answer=AttemptAnswer(mode=InputMode.TEXT, text="un café"),
        assistance=AssistanceLevel.NONE,
    )

    _apply(
        db_session, user=user, session=session, evaluation=evaluation,
        journey_id=uuid4(), step_id=uuid4(),
    )

    assert _moments(db_session, user, kind="journey_objective") == []


def test_a_turn_with_target_observations_writes_no_extra_objective_record(db_session):
    """The observations already describe the turn; nothing is double-counted."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )

    _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(
            observations=[
                TargetObservation(
                    target=_target_for(word),
                    evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
                    assistance=AssistanceLevel.NONE,
                    modality=InputMode.TEXT,
                    learner_text="Un café, s'il vous plaît",
                )
            ]
        ),
        journey_id=uuid4(), step_id=uuid4(),
    )

    assert _moments(db_session, user, kind="journey_objective") == []


def test_an_objective_record_never_reaches_candidate_selection(db_session):
    """A target-less record must not decide whether a word is practised."""

    user = _user(db_session)
    word = _word(db_session, "café")
    _due_progress(db_session, user, word)
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=uuid4(), scenario_key="order_at_cafe"
    )
    _apply(
        db_session, user=user, session=session,
        evaluation=_objective_response(),
        journey_id=uuid4(), step_id=uuid4(),
    )

    candidates = select_learning_candidates(
        db_session, user=user, scenario=_scenario(), limit=3
    )
    candidate = _candidate_for(candidates, word)
    assert candidate.metadata["evidence_history"] == EVIDENCE_HISTORY_NONE
