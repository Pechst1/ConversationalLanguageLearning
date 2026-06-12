from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.core.error_detection import ErrorDetectionResult
from app.core.error_detection.rules import DetectedError
from app.core.conversation.generator import ConversationPlan
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.session import LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.brief_exercise_service import BriefExerciseService
from app.services.grammar import GrammarService
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService, QueueItem
from app.services.session_moment_planner import SessionMomentPlanner


class RejectingLLMService:
    """Return an over-strict grammar evaluation to exercise local overrides."""

    def generate_chat_completion(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        return LLMResult(
            provider="stub",
            model="stub-model",
            content=json.dumps(
                {
                    "is_correct": False,
                    "feedback": "Die Antwort bezieht sich nicht auf die Aufgabe.",
                    "explanation": "Die Schueler-Antwort hat nichts mit der Aufgabe zu tun.",
                    "sample_solution": "Si tu etudies, tu reussiras.",
                    "score": 1,
                    "detected_error_category": "Grammar",
                    "detected_subcategory": "Si-Saetze",
                }
            ),
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            cost=0.0,
            raw_response={"messages": messages},
        )


def test_brief_exercise_service_accepts_valid_alternative_si_sentence(db_session) -> None:
    concept = GrammarConcept(
        name="Si-Saetze Typ 1: si + present -> futur",
        level="B1",
        description="Use si + present with futur simple in the result clause.",
        examples="Si tu etudies, tu reussiras.",
    )
    db_session.add(concept)
    db_session.commit()

    service = BriefExerciseService(db_session, llm_service=RejectingLLMService())
    result = asyncio.run(
        service.check_answer(
            exercise_type="short_answer",
            prompt="Bilde einen Satz mit si + present -> futur.",
            correct_answer="Si tu etudies, tu reussiras.",
            user_answer="Si tu es la-bas, tu pourras venir.",
            concept_id=concept.id,
        )
    )

    assert result["is_correct"] is True
    assert result["score"] >= 8
    assert "passt" in result["feedback"].lower()


def test_brief_exercise_accepts_non_tense_concept_with_shared_detector(db_session) -> None:
    concept = GrammarConcept(
        name="Relative pronouns: qui, que, dont",
        level="B1",
        category="Pronouns",
        subskill="relative clauses",
        core_rule="Use dont when the relative clause needs a de-complement.",
        examples="Le dossier dont je parle reste ici.",
        exercise_tags=["relative_pronoun", "dont", "de_complement"],
    )
    db_session.add(concept)
    db_session.commit()

    service = BriefExerciseService(db_session, llm_service=RejectingLLMService())
    result = asyncio.run(
        service.check_answer(
            exercise_type="short_answer",
            prompt="Bilde einen Satz mit einem Relativpronomen.",
            correct_answer="Le dossier dont je parle reste ici.",
            user_answer="La personne dont je parle arrive demain.",
            concept_id=concept.id,
        )
    )

    assert result["is_correct"] is True
    assert result["score"] >= 8


def test_context_evaluator_accepts_non_tense_concept_pattern(db_session) -> None:
    concept = GrammarConcept(
        name="Subjonctif present",
        level="B1",
        description="Use the subjunctive after expressions of necessity.",
        examples="Il faut que tu viennes.",
        exercise_tags=["subjonctif", "mood"],
    )
    db_session.add(concept)
    db_session.commit()
    evaluator = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
        llm_service=None,
    ).grammar_evaluator

    result = evaluator.evaluate(
        concept=concept,
        assistant_prompt="Use the target concept in one sentence.",
        learner_reply="Il faut que tu viennes demain.",
        error_result=ErrorDetectionResult(errors=[], summary=""),
    )

    assert result.used_target_concept is True
    assert result.retry_needed is False


def test_immediate_repair_skips_without_generated_exercise(db_session) -> None:
    planner = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
        llm_service=None,
    )
    error_result = ErrorDetectionResult(
        errors=[
            DetectedError(
                code="article_rule",
                message="Im Franzoesischen wird 'voyage' mit dem bestimmten Artikel 'le' verwendet.",
                span="la voyage",
                suggestion="le voyage",
                category="grammar",
                severity="medium",
                confidence=0.8,
            )
        ],
        summary="Review this grammar point.",
    )

    planned = planner._plan_immediate_repair(  # type: ignore[attr-defined]
        due_grammar=[(SimpleNamespace(id=7, name="Si-Saetze Typ 1"), None)],
        last_error_result=error_result,
    )

    assert planned is None


def test_due_grammar_prioritizes_started_concepts_over_unseen_ones(db_session) -> None:
    user = User(
        email="grammar-priority@example.com",
        hashed_password="hashed",
        target_language="fr",
        native_language="de",
    )
    db_session.add(user)
    db_session.flush()

    unseen = GrammarConcept(
        name="Subjonctif present",
        level="B1",
        description="Use the subjunctive after expressions of necessity.",
        examples="Il faut que tu viennes.",
        difficulty_order=5,
    )
    started = GrammarConcept(
        name="Conditionnel present",
        level="B1",
        description="Use the conditional for polite requests.",
        examples="Je voudrais un cafe.",
        difficulty_order=10,
    )
    db_session.add_all([unseen, started])
    db_session.flush()
    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=started.id,
            score=4.0,
            reps=1,
            state="in_arbeit",
            next_review=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    )
    db_session.commit()

    service = GrammarService(db_session)
    due = service.get_due_concepts(user=user, limit=2)

    assert due
    assert due[0][0].id == started.id


def test_vocab_check_prompt_uses_example_sentence_context(db_session) -> None:
    word = VocabularyWord(
        language="fr",
        word="abaisser",
        normalized_word="abaisser",
        german_translation="herabsetzen, senken",
        example_sentence="Il faut abaisser le prix avant vendredi.",
        example_translation="Der Preis muss vor Freitag gesenkt werden.",
        deck_name="Französisch 5000::1. FR → DE",
    )
    db_session.add(word)
    db_session.flush()
    planner = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
        llm_service=None,
    )

    prompt, accepted = planner._build_vocab_check_prompt(word)  # type: ignore[attr-defined]

    assert "Il faut abaisser le prix" in prompt
    assert "what does `abaisser` mean" in prompt
    assert accepted == ["herabsetzen", "senken"]


def test_vocab_boost_carries_example_sentence_metadata(db_session) -> None:
    user = User(
        email="vocab-boost@example.com",
        hashed_password="hashed",
        target_language="fr",
        native_language="de",
    )
    word = VocabularyWord(
        language="fr",
        word="prévenir",
        normalized_word="prevenir",
        german_translation="benachrichtigen",
        example_sentence="Je voulais vous prévenir que le train aura du retard.",
        example_translation="Ich wollte Sie informieren, dass der Zug Verspätung haben wird.",
        deck_name="Französisch 5000::1. FR → DE",
    )
    db_session.add_all([user, word])
    db_session.flush()
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=10,
        conversation_style="tutor",
        status="in_progress",
    )
    db_session.add(session)
    db_session.flush()
    planner = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
        llm_service=None,
    )
    plan = ConversationPlan(
        queue_items=(QueueItem(word=word, progress=None, is_new=False),),
        review_targets=[],
        new_targets=[],
    )

    planned = planner._plan_vocab_boost(session=session, conversation_plan=plan)  # type: ignore[attr-defined]

    assert planned is not None
    assert "Je voulais vous prévenir" in planned.body
    assert planned.metadata["example_sentence"] == word.example_sentence
    assert planned.metadata["example_translation"] == word.example_translation


def test_vocab_boost_missed_target_creates_vocabulary_erratum(db_session) -> None:
    user = User(
        email="vocab-boost-missed@example.com",
        hashed_password="hashed",
        target_language="fr",
        native_language="de",
    )
    word = VocabularyWord(
        language="fr",
        word="prévenir",
        normalized_word="prevenir",
        german_translation="benachrichtigen",
        example_sentence="Je voulais vous prévenir que le train aura du retard.",
        example_translation="Ich wollte Sie informieren, dass der Zug Verspätung haben wird.",
        deck_name="Französisch 5000::1. FR → DE",
    )
    db_session.add_all([user, word])
    db_session.flush()
    session = LearningSession(
        user_id=user.id,
        planned_duration_minutes=10,
        conversation_style="tutor",
        status="in_progress",
    )
    db_session.add(session)
    db_session.flush()
    moment = SessionLearningMoment(
        session_id=session.id,
        user_id=user.id,
        kind="vocab_boost",
        source_type="vocabulary",
        source_id=str(word.id),
        source_deck_name=word.deck_name,
        status="pending",
        prompt_payload={
            "title": f"Use {word.word}",
            "body": f"Answer in French and naturally include `{word.word}`.",
            "input_mode": "chips",
            "choices": [],
            "prefill_text": None,
            "metadata": {"word_id": word.id, "word": word.word},
        },
    )
    db_session.add(moment)
    db_session.flush()
    planner = SessionMomentPlanner(
        db_session,
        progress_service=ProgressService(db_session),
        grammar_service=GrammarService(db_session),
        llm_service=None,
    )

    result = planner._resolve_vocab_boost_from_feedback(  # type: ignore[attr-defined]
        session=session,
        user=user,
        moment=moment,
        learner_reply="Je vais envoyer le message demain.",
        word_feedback=[
            SimpleNamespace(
                word=word,
                was_used=False,
                had_error=False,
                error=None,
            )
        ],
    )

    erratum = (
        db_session.query(UserError)
        .filter(
            UserError.user_id == user.id,
            UserError.linked_word_id == word.id,
            UserError.task_error_type == "vocabulary_missing_target",
        )
        .one()
    )

    assert result is not None
    assert result.is_correct is False
    assert moment.status == "completed"
    assert erratum.review_mode == "vocabulary"
    assert erratum.source_type == "session"
