"""WP-16 / decision D-0 — one daily Séance, one source of evidence.

The daily journey is the day's Séance; the legacy exercise loop is the explicit
«Plus de pratique» drill activity. Both write into the same LearningSession /
SessionLearningMoment / SRS records, so a word or a concept practised in both on
one day must be credited once, and the practice streak must move once.

The legacy side is exercised through the very services `app/services/atelier.py`
calls at session completion — `GrammarService.record_review` and
`VocabularyCreditService.apply` — rather than through a whole HTTP session, so
the assertion is about the shared credit path and not about the drill loop's
own bookkeeping. That file is under a concurrent lease and is deliberately
untouched by this package; the policy lives in the WP-05 adapters.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.grammar import GrammarService
from app.services.journey_contracts import (
    AssistanceLevel,
    EvidenceKind,
    InputMode,
    ResponseEvaluation,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.services.journey_learning import (
    JOURNEY_SOURCE_TYPE,
    apply_learning_evidence,
    ensure_journey_learning_session,
    journey_credited_today,
    record_daily_practice_streak,
)
from app.services.vocabulary_credit import VocabularyCreditService

# --------------------------------------------------------------------------
# Builders
# --------------------------------------------------------------------------

def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"wp16-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
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


def _concept(db_session) -> GrammarConcept:
    concept = GrammarConcept(
        external_id=f"FR_A2_{uuid4().hex[:8]}",
        language="fr",
        name="Le passé composé",
        level="A2",
        category="Verbes",
        active=True,
    )
    db_session.add(concept)
    db_session.flush()
    return concept


def _due_word_progress(db_session, user, word) -> UserVocabularyProgress:
    now = datetime.now(UTC)
    progress = UserVocabularyProgress(
        user_id=user.id,
        word_id=word.id,
        state="review",
        stability=3.0,
        difficulty=5.0,
        reps=2,
        due_at=now - timedelta(days=2),
        next_review_date=now - timedelta(days=2),
        due_date=(now - timedelta(days=2)).date(),
    )
    db_session.add(progress)
    db_session.flush()
    return progress


def _grammar_progress(db_session, user, concept) -> UserGrammarProgress:
    return GrammarService(db_session).get_or_create_progress(
        user_id=user.id, concept_id=concept.id
    )


def _journey_respond(db_session, *, user, observations) -> tuple[LearningSession, object]:
    """One journey respond step, applied through the real WP-05 adapter."""

    journey_id = uuid4()
    session = ensure_journey_learning_session(
        db_session, user=user, journey_id=journey_id, scenario_key="order_at_cafe"
    )
    applied = apply_learning_evidence(
        db_session,
        user=user,
        journey_id=journey_id,
        step_id=uuid4(),
        session=session,
        evaluation=ResponseEvaluation(
            outcome=TaskOutcome.MET,
            assistance=AssistanceLevel.NONE,
            observations=observations,
        ),
        modality=InputMode.TEXT,
    )
    return session, applied


def _vocab_observation(word: VocabularyWord) -> TargetObservation:
    return TargetObservation(
        target=TargetRef(
            kind=TargetKind.VOCABULARY,
            id=str(word.id),
            label_fr=word.word,
            label_native=word.english_translation,
        ),
        evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
        assistance=AssistanceLevel.NONE,
        modality=InputMode.TEXT,
        learner_text="Un café, s'il vous plaît",
    )


def _grammar_observation(concept: GrammarConcept) -> TargetObservation:
    return TargetObservation(
        target=TargetRef(
            kind=TargetKind.GRAMMAR,
            id=str(concept.id),
            label_fr=concept.name,
            label_native="the perfect tense",
        ),
        evidence_kind=EvidenceKind.PRODUCED_INDEPENDENT,
        assistance=AssistanceLevel.NONE,
        modality=InputMode.TEXT,
        learner_text="J'ai pris un café",
    )


def _schedule(progress) -> tuple:
    def naive(value):
        return value.replace(tzinfo=None) if hasattr(value, "tzinfo") and value else value

    return (
        naive(getattr(progress, "due_at", None)),
        naive(getattr(progress, "next_review_date", None)),
        naive(getattr(progress, "next_review", None)),
        getattr(progress, "due_date", None),
        progress.reps,
        progress.score if hasattr(progress, "score") else None,
    )


# --------------------------------------------------------------------------
# 1. One evidence source: the journey writes where the legacy loop reads
# --------------------------------------------------------------------------

def test_journey_evidence_lands_in_the_shared_learning_records(db_session):
    user = _user(db_session)
    word = _word(db_session)
    _due_word_progress(db_session, user, word)

    session, applied = _journey_respond(
        db_session, user=user, observations=[_vocab_observation(word)]
    )

    # A real LearningSession, not a journey-private table.
    assert isinstance(session, LearningSession)
    assert applied.learning_session_id == session.id

    moments = (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .all()
    )
    assert len(moments) == 1
    assert moments[0].source_type == JOURNEY_SOURCE_TYPE
    assert moments[0].srs_credit_applied is True
    assert moments[0].session_id == session.id
    assert journey_credited_today(
        db_session, user=user, target_kind="vocabulary", target_id=str(word.id)
    )


# --------------------------------------------------------------------------
# 2. One credit — a word practised in both surfaces on one day
# --------------------------------------------------------------------------

def test_a_word_practised_in_journey_and_drill_loop_is_credited_once(db_session):
    user = _user(db_session)
    word = _word(db_session, "addition")
    progress = _due_word_progress(db_session, user, word)

    _journey_respond(db_session, user=user, observations=[_vocab_observation(word)])
    db_session.refresh(progress)
    after_journey = _schedule(progress)

    # The learner then drills the same word in «Plus de pratique». This is the
    # exact call `AtelierService` makes when a target word is used correctly.
    VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="produced_correct",
        source_type="atelier",
        learner_text="L'addition, s'il vous plaît",
    )
    db_session.refresh(progress)

    assert _schedule(progress) == after_journey, (
        "the drill loop advanced a schedule the daily journey had already set today"
    )


def test_a_concept_practised_in_journey_and_drill_loop_is_credited_once(db_session):
    user = _user(db_session)
    concept = _concept(db_session)

    _journey_respond(db_session, user=user, observations=[_grammar_observation(concept)])
    progress = _grammar_progress(db_session, user, concept)
    after_journey = _schedule(progress)
    assert progress.reps >= 1

    # The legacy session's completion recap credits every selected concept.
    GrammarService(db_session).record_review(
        user=user,
        concept_id=concept.id,
        score=8.0,
        notes=f"Atelier session {uuid4()}",
    )
    db_session.refresh(progress)

    assert _schedule(progress) == after_journey, (
        "the drill loop advanced a concept the daily journey had already credited today"
    )


# --------------------------------------------------------------------------
# 3. The guard is day-scoped, target-scoped and failure-transparent
# --------------------------------------------------------------------------

def test_the_guard_does_not_touch_a_target_the_journey_did_not_credit(db_session):
    user = _user(db_session)
    practised = _word(db_session, "serveur")
    other = _word(db_session, "terrasse")
    other_progress = _due_word_progress(db_session, user, other)
    _due_word_progress(db_session, user, practised)

    _journey_respond(db_session, user=user, observations=[_vocab_observation(practised)])
    before = _schedule(other_progress)

    VocabularyCreditService(db_session).apply(
        user=user,
        word=other,
        event_type="produced_correct",
        source_type="atelier",
        learner_text="En terrasse",
    )
    db_session.refresh(other_progress)
    assert _schedule(other_progress) != before


def test_a_failure_in_the_drill_loop_is_never_folded_away(db_session):
    """A real mistake has to reach the schedule whenever it happens."""

    user = _user(db_session)
    word = _word(db_session, "pourboire")
    progress = _due_word_progress(db_session, user, word)

    _journey_respond(db_session, user=user, observations=[_vocab_observation(word)])
    db_session.refresh(progress)
    after_journey = _schedule(progress)

    VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="produced_incorrect",
        source_type="atelier",
        learner_text="le pourboir",
        corrected_text="le pourboire",
    )
    db_session.refresh(progress)
    assert _schedule(progress) != after_journey
    assert progress.state == "relearning"


def test_yesterdays_journey_credit_does_not_fold_todays_practice(db_session):
    user = _user(db_session)
    word = _word(db_session, "carafe")
    progress = _due_word_progress(db_session, user, word)

    _journey_respond(db_session, user=user, observations=[_vocab_observation(word)])
    # Re-date the journey's evidence to yesterday, as an overnight run would.
    moment = (
        db_session.query(SessionLearningMoment)
        .filter(SessionLearningMoment.user_id == user.id)
        .one()
    )
    payload = dict(moment.prompt_payload or {})
    payload["observed_on"] = (date.today() - timedelta(days=1)).isoformat()
    moment.prompt_payload = payload
    db_session.add(moment)
    db_session.flush()

    assert not journey_credited_today(
        db_session, user=user, target_kind="vocabulary", target_id=str(word.id)
    )
    before = _schedule(progress)
    VocabularyCreditService(db_session).apply(
        user=user,
        word=word,
        event_type="produced_correct",
        source_type="atelier",
        learner_text="Une carafe d'eau",
    )
    db_session.refresh(progress)
    assert _schedule(progress) != before


# --------------------------------------------------------------------------
# 4. One streak increment for the day, whichever surfaces the learner used
# --------------------------------------------------------------------------

def test_journey_then_drill_loop_moves_the_streak_once(db_session):
    user = _user(db_session)
    user.grammar_streak_days = 4
    user.grammar_last_review_date = date.today() - timedelta(days=1)
    db_session.flush()

    # The journey finishing marks the day.
    assert record_daily_practice_streak(db_session, user) == 5
    assert user.grammar_last_review_date == date.today()

    # «Plus de pratique» afterwards is the same day: the legacy rule
    # (`AtelierService._update_streak`) short-circuits on the same marker, and
    # so does a second call here.
    assert record_daily_practice_streak(db_session, user) == 5
    assert user.grammar_streak_days == 5
    assert user.grammar_longest_streak >= 5


def test_a_broken_streak_restarts_at_one(db_session):
    user = _user(db_session)
    user.grammar_streak_days = 9
    user.grammar_longest_streak = 9
    user.grammar_last_review_date = date.today() - timedelta(days=3)
    db_session.flush()

    assert record_daily_practice_streak(db_session, user) == 1
    assert user.grammar_longest_streak >= 9


# --------------------------------------------------------------------------
# 5. The «Plus de pratique» entry names a concept, never "today"
# --------------------------------------------------------------------------

def test_the_practice_href_seats_the_learners_own_due_concept(db_session):
    """`get_due_concepts` yields (concept, progress) pairs — unpack them.

    Regression: the first version read `.id` off the tuple and silently
    produced the bare `/atelier?mode=practice`, which drops the learner into a
    generic drill set instead of the rule the scheduler thinks is fragile.
    """

    from app.services.daily_journey import DailyJourneyService

    user = _user(db_session)
    concept = _concept(db_session)
    progress = GrammarService(db_session).get_or_create_progress(
        user_id=user.id, concept_id=concept.id
    )
    progress.state = "ausbaufähig"
    progress.next_review = datetime.now(UTC) - timedelta(days=2)
    db_session.flush()

    service = DailyJourneyService(db_session, adapters=None)
    assert service._practice_href(user) == f"/atelier?mode=practice&concept={concept.id}"


def test_the_practice_href_falls_back_to_the_bare_entry(db_session, monkeypatch):
    from app.services import daily_journey as daily_journey_module
    from app.services.daily_journey import DailyJourneyService

    user = _user(db_session)

    def boom(*args, **kwargs):
        raise RuntimeError("scheduler down")

    monkeypatch.setattr(
        daily_journey_module.GrammarService, "get_due_concepts", boom, raising=True
    )
    service = DailyJourneyService(db_session, adapters=None)
    assert service._practice_href(user) == "/atelier?mode=practice"


def test_drill_first_word_keeps_journey_evidence_without_double_credit(db_session):
    user = _user(db_session)
    word = _word(db_session)
    progress = _due_word_progress(db_session, user, word)
    VocabularyCreditService(db_session).apply(
        user=user, word=word, event_type="produced_correct", source_type="atelier",
    )
    before = _schedule(progress)
    _journey_respond(db_session, user=user, observations=[_vocab_observation(word)])
    db_session.refresh(progress)
    assert _schedule(progress) == before
    moment = db_session.query(SessionLearningMoment).filter_by(
        user_id=user.id, source_type=JOURNEY_SOURCE_TYPE
    ).one()
    assert not moment.srs_credit_applied
    assert moment.result_payload["credit"]["skipped"] == "credited_in_drill_today"


def test_drill_first_grammar_keeps_journey_evidence_without_double_credit(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    progress = GrammarService(db_session).record_review(
        user=user, concept_id=concept.id, score=8.0, source_type="atelier",
    )
    before = _schedule(progress)
    _journey_respond(db_session, user=user, observations=[_grammar_observation(concept)])
    db_session.refresh(progress)
    assert _schedule(progress) == before


def test_drill_claim_is_idempotent_and_expires_tomorrow(db_session):
    from app.services.journey_learning import record_drill_credit
    user = _user(db_session)
    word = _word(db_session)
    now = datetime.now(UTC)
    for _ in range(2):
        record_drill_credit(db_session, user=user, target_kind="vocabulary",
                           target_id=str(word.id), now=now)
    claims = db_session.query(SessionLearningMoment).filter_by(source_type="atelier", user_id=user.id).all()
    assert len(claims) == 1
    assert not journey_credited_today(
        db_session, user=user, target_kind="vocabulary", target_id=str(word.id),
        source_type="atelier", on_date=now.date() + timedelta(days=1),
    )


def test_failed_drill_does_not_claim_success_and_later_journey_can_credit(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    progress = GrammarService(db_session).record_review(
        user=user, concept_id=concept.id, score=2.0, source_type="atelier",
    )
    assert not journey_credited_today(
        db_session, user=user, target_kind="grammar", target_id=str(concept.id),
        source_type="atelier",
    )
    before = _schedule(progress)
    _journey_respond(db_session, user=user, observations=[_grammar_observation(concept)])
    db_session.refresh(progress)
    assert _schedule(progress) != before


def test_journey_failure_after_drill_still_reaches_schedule(db_session):
    from dataclasses import replace
    user = _user(db_session)
    concept = _concept(db_session)
    progress = GrammarService(db_session).record_review(
        user=user, concept_id=concept.id, score=8.0, source_type="atelier",
    )
    before = _schedule(progress)
    observation = replace(_grammar_observation(concept), evidence_kind=EvidenceKind.NOT_YET)
    _journey_respond(db_session, user=user, observations=[observation])
    db_session.refresh(progress)
    assert _schedule(progress) != before
    assert progress.score == 2.0


def test_grammar_failure_after_journey_is_not_folded(db_session):
    user = _user(db_session)
    concept = _concept(db_session)
    _journey_respond(db_session, user=user, observations=[_grammar_observation(concept)])
    progress = GrammarService(db_session).record_review(
        user=user, concept_id=concept.id, score=2.0, source_type="atelier",
    )
    assert progress.score == 2.0
