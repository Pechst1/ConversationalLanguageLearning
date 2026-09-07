"""Confidence scheduling and generated-exercise quality flywheel tests."""
from __future__ import annotations

from uuid import uuid4

from app.db.models.atelier import (
    AtelierAttempt,
    AtelierGenerationEvent,
    AtelierSession,
)
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services.atelier import (
    AtelierExerciseGenerator,
    AtelierExerciseQualityService,
    AtelierScheduler,
    AtelierSRSService,
    session_exercise_set,
)


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _concept(db_session) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return (
        db_session.query(GrammarConcept)
        .filter(GrammarConcept.external_id == "FR_A2_NEG_001")
        .one()
    )


def _complete_one_attempt(db_session, concept: GrammarConcept, confidence: str | None) -> UserGrammarProgress:
    user = _user(db_session)
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id],
        quote_payload={},
        recap_payload={},
    )
    db_session.add(session)
    db_session.flush([session])
    answer_payload = {"text": "Je ne sais pas."}
    if confidence:
        answer_payload["confidence"] = confidence
    db_session.add(
        AtelierAttempt(
            atelier_session_id=session.id,
            user_id=user.id,
            concept_id=concept.id,
            round="sentence",
            mode="guided",
            exercise_id=f"confidence-{confidence or 'none'}",
            prompt_payload={},
            answer_payload=answer_payload,
            correction_payload={},
            verdict="partial",
            score_0_4=2.0,
        )
    )
    db_session.commit()

    AtelierSRSService(db_session).complete_session(session=session, user=user)
    return (
        db_session.query(UserGrammarProgress)
        .filter(
            UserGrammarProgress.user_id == user.id,
            UserGrammarProgress.concept_id == concept.id,
        )
        .one()
    )


def test_confidence_calibration_diverges_atelier_scheduling(db_session):
    concept = _concept(db_session)

    confident_miss = _complete_one_attempt(db_session, concept, "sure")
    hesitant_miss = _complete_one_attempt(db_session, concept, "unsure")
    no_signal = _complete_one_attempt(db_session, concept, None)

    assert confident_miss.score < no_signal.score < hesitant_miss.score
    confident_interval = confident_miss.next_review - confident_miss.last_review
    hesitant_interval = hesitant_miss.next_review - hesitant_miss.last_review
    neutral_interval = no_signal.next_review - no_signal.last_review
    assert confident_interval < hesitant_interval < neutral_interval


def test_confident_hit_gets_small_mastery_and_interval_lift(db_session):
    concept = _concept(db_session)
    user = _user(db_session)
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id],
        quote_payload={},
        recap_payload={},
    )
    db_session.add(session)
    db_session.flush([session])
    db_session.add(
        AtelierAttempt(
            atelier_session_id=session.id,
            user_id=user.id,
            concept_id=concept.id,
            round="sentence",
            mode="guided",
            exercise_id="confident-hit",
            prompt_payload={},
            answer_payload={"text": "Je ne viens pas.", "confidence": "sure"},
            correction_payload={},
            verdict="correct",
            score_0_4=4.0,
        )
    )
    db_session.commit()

    AtelierSRSService(db_session).complete_session(session=session, user=user)
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )

    assert progress.score == 10.0
    assert (progress.next_review - progress.last_review).days >= 34


def test_quality_threshold_retires_and_regenerates_exercise_set(db_session):
    concept = _concept(db_session)
    user = _user(db_session)
    exercise_set = AtelierExerciseGenerator(db_session).get_or_create(
        concept,
        reuse_shared_cache=True,
        skip_llm=True,
    )
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id],
        quote_payload={"exercise_set_ids": {str(concept.id): str(exercise_set.id)}},
        recap_payload={},
    )
    db_session.add(session)
    db_session.flush([session])
    for index in range(3):
        db_session.add(
            AtelierGenerationEvent(
                user_id=user.id,
                concept_id=concept.id,
                atelier_session_id=session.id,
                exercise_set_id=exercise_set.id,
                generator_version=exercise_set.generator_version,
                event_type="user_report",
                source="human",
                passed=False,
                payload={"reason": f"bad item {index}"},
            )
        )
    db_session.commit()

    replacement = AtelierExerciseQualityService(db_session).evaluate_and_retire(exercise_set)
    db_session.refresh(exercise_set)

    assert exercise_set.retired_at is not None
    assert replacement is not None
    assert replacement.id != exercise_set.id
    assert replacement.retired_at is None
    assert (
        db_session.query(AtelierGenerationEvent)
        .filter(
            AtelierGenerationEvent.exercise_set_id == exercise_set.id,
            AtelierGenerationEvent.event_type == "exercise_retired",
        )
        .count()
        == 1
    )

    assembled = session_exercise_set(
        db_session,
        user=user,
        session=session,
        concept=concept,
        fast_path=True,
    )
    assert assembled.id == replacement.id


def test_quality_sweep_keeps_retirement_when_replacement_provider_fails(
    db_session,
    monkeypatch,
):
    concept = _concept(db_session)
    user = _user(db_session)
    exercise_set = AtelierExerciseGenerator(db_session).get_or_create(
        concept,
        reuse_shared_cache=True,
        skip_llm=True,
    )
    for index in range(3):
        db_session.add(
            AtelierGenerationEvent(
                user_id=user.id,
                concept_id=concept.id,
                exercise_set_id=exercise_set.id,
                generator_version=exercise_set.generator_version,
                event_type="user_report",
                source="human",
                passed=False,
                payload={"reason": f"bad item {index}"},
            )
        )
    db_session.commit()
    monkeypatch.setattr(
        "app.services.atelier.AtelierExerciseGenerator.get_or_create",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    retired_ids = AtelierExerciseQualityService(db_session).run()

    db_session.refresh(exercise_set)
    assert exercise_set.id in retired_ids  # The sweep also examines other persisted sets.
    assert exercise_set.retired_at is not None
