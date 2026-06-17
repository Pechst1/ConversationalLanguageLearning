from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.session import ConversationMessage, LearningSession, SessionLearningMoment
from app.db.models.user import User
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService
from app.services.session_service import SessionService
from app.core.conversation import ConversationGenerator
from app.core.error_detection import ErrorDetectionResult
from app.core.error_detection.rules import DetectedError


class DummyToken:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lemma_ = text.lower()
        self.is_stop = False
        self.is_punct = False
        self.is_space = False


class DummyNLP:
    def __call__(self, text: str):
        return [DummyToken(part) for part in text.split() if part.strip()]


class StubLLMService:
    """Return deterministic completions for tests."""

    def __init__(self) -> None:
        self.counter = 0

    def generate_chat_completion(self, messages, *, temperature=0.0, max_tokens=0, response_format=None, system_prompt=None, **kwargs):  # type: ignore[override]
        self.counter += 1
        schema_name = ((response_format or {}).get("json_schema") or {}).get("name")
        if schema_name == "brief_grammar_exercises":
            content = {
                "exercises": [
                    {
                        "id": "generated-grammar-1",
                        "type": "short_answer",
                        "difficulty": "a",
                        "instruction": "Write one polite request in French.",
                        "prompt": "Write one French sentence with the target grammar.",
                        "correct_answer": "Je voudrais un cafe.",
                        "hint": "Use a complete French sentence.",
                    },
                    {
                        "id": "generated-grammar-2",
                        "type": "correction",
                        "difficulty": "b",
                        "instruction": "Repair the sentence.",
                        "prompt": "Je veux un cafe, s'il vous plait.",
                        "correct_answer": "Je voudrais un cafe, s'il vous plait.",
                        "hint": "Make the request more polite.",
                    },
                    {
                        "id": "generated-grammar-3",
                        "type": "translation",
                        "difficulty": "c",
                        "instruction": "Translate with the target grammar.",
                        "prompt": "I would like a coffee.",
                        "correct_answer": "Je voudrais un cafe.",
                        "hint": "Use conditionnel present.",
                    },
                ]
            }
            return LLMResult(
                provider="stub",
                model="stub-model",
                content=json.dumps(content),
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                cost=0.0,
                raw_response={"messages": messages},
            )
        if schema_name == "error_repair_exercise":
            content = {
                "exercise_type": "correction",
                "instruction": "Repair the stored mistake.",
                "prompt": "Je veux un cafe, s'il vous plait.",
                "correct_answer": "Je voudrais un cafe, s'il vous plait.",
                "explanation": "Use a polite conditional form.",
                "memory_tip": "Conditionnel can soften requests.",
            }
            return LLMResult(
                provider="stub",
                model="stub-model",
                content=json.dumps(content),
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                cost=0.0,
                raw_response={"messages": messages},
            )
        content = "Bonjour ! Parlons de baguettes et de fromages."
        if self.counter > 1:
            content = "Très bien ! Continuons notre conversation."
        return LLMResult(
            provider="stub",
            model="stub-model",
            content=content,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            cost=0.0,
            raw_response={"messages": messages},
        )


class StubErrorDetector:
    """Return empty error detections for tests."""

    def __init__(self) -> None:
        self.result: ErrorDetectionResult | None = None

    def analyze(self, learner_message: str, *, learner_level: str = "B1", target_vocabulary=None, use_llm: bool = True) -> ErrorDetectionResult:  # type: ignore[override]
        if self.result is not None:
            return self.result
        return ErrorDetectionResult(errors=[], summary="Looks great!", metadata={"stub": True})


@pytest.fixture()
def stubbed_session_service(client: TestClient, db_session):
    stub_llm = StubLLMService()
    stub_detector = StubErrorDetector()
    progress_service = ProgressService(db_session)

    def override_llm_service():
        return stub_llm

    def override_error_detector():
        return stub_detector

    def override_session_service():
        generator = ConversationGenerator(
            progress_service=progress_service,
            llm_service=stub_llm,
            target_limit=3,
        )
        return SessionService(
            db_session,
            progress_service=progress_service,
            conversation_generator=generator,
            error_detector=stub_detector,
            llm_service=stub_llm,
            nlp=DummyNLP(),
        )

    client.app.dependency_overrides[deps.get_llm_service] = override_llm_service
    client.app.dependency_overrides[deps.get_error_detector] = override_error_detector
    client.app.dependency_overrides[deps.get_session_service] = override_session_service
    deps._llm_service_singleton = None
    deps._error_detector_singleton = None

    try:
        yield {"llm": stub_llm, "detector": stub_detector}
    finally:
        client.app.dependency_overrides.pop(deps.get_session_service, None)
        client.app.dependency_overrides.pop(deps.get_error_detector, None)
        client.app.dependency_overrides.pop(deps.get_llm_service, None)
        deps._llm_service_singleton = None
        deps._error_detector_singleton = None


def register_and_login(client: TestClient, email: str, password: str) -> str:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    return response.json()["access_token"]


def test_create_session_returns_initial_turn(
    client: TestClient, french_vocabulary, stubbed_session_service
) -> None:
    token = register_and_login(client, "session-create@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 20, "conversation_style": "tutor"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["session"]["status"] == "in_progress"
    assert payload["assistant_turn"] is not None
    assert len(payload["assistant_turn"]["targets"]) >= 1
    assert payload["assistant_turn"]["learning_focus"]
    assert any(item["kind"] == "vocabulary" for item in payload["assistant_turn"]["learning_focus"])


def test_create_session_includes_unified_learning_focus_for_due_items(
    client: TestClient,
    french_vocabulary,
    stubbed_session_service,
    db_session,
) -> None:
    token = register_and_login(client, "session-focus@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "session-focus@example.com").one()

    concept = GrammarConcept(
        name="Subjonctif present",
        level="B1",
        description="Use the subjunctive after expressions of necessity.",
        examples="Il faut que tu viennes.",
    )
    db_session.add(concept)
    db_session.flush()

    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            score=4.0,
            reps=2,
            state="in_arbeit",
            next_review=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    db_session.add(
        UserError(
            user_id=user.id,
            error_category="grammar",
            error_pattern="subjunctive_after_il_faut",
            correction="Il faut que tu viennes",
            context_snippet="Il faut tu viens",
            reps=2,
            lapses=3,
            state="review",
            next_review_date=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 20, "conversation_style": "tutor"},
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    focus_kinds = {item["kind"] for item in payload["assistant_turn"]["learning_focus"]}

    assert {"vocabulary", "grammar", "error"} <= focus_kinds


def test_post_message_updates_progress_and_returns_feedback(
    client: TestClient, french_vocabulary, stubbed_session_service, db_session
) -> None:
    email = "session-flow@example.com"
    token = register_and_login(client, email, "strongpass")
    headers = {"Authorization": f"Bearer {token}"}

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = UUID(session_payload["session"]["id"])
    target_word = session_payload["assistant_turn"]["targets"][0]

    learner_message = f"J'aime la {target_word['word']} traditionnelle."
    turn = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": learner_message},
        headers=headers,
    )

    assert turn.status_code == 200
    turn_payload = turn.json()
    assert turn_payload["xp_awarded"] >= 10
    assert turn_payload["word_feedback"][0]["was_used"] is True

    user = db_session.query(User).filter(User.email == email).one()
    session_db = db_session.query(LearningSession).filter(LearningSession.id == session_id).one()
    progress_entries = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id)
        .all()
    )

    assert session_db.words_practiced > 0
    assert len(progress_entries) >= 1

    summary = client.get(f"/api/v1/sessions/{session_id}/summary", headers=headers)
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["xp_earned"] >= turn_payload["xp_awarded"]


def test_post_message_applies_tiny_seen_context_credit_for_unused_targets(
    client: TestClient, french_vocabulary, stubbed_session_service, db_session
) -> None:
    email = "session-seen-credit@example.com"
    token = register_and_login(client, email, "strongpass")
    headers = {"Authorization": f"Bearer {token}"}

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = UUID(session_payload["session"]["id"])
    target_word = session_payload["assistant_turn"]["targets"][0]

    turn = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "Je parle francais aujourd'hui."},
        headers=headers,
    )

    assert turn.status_code == 200
    first_feedback = turn.json()["word_feedback"][0]
    assert first_feedback["was_used"] is False
    assert first_feedback["rating"] is None

    user = db_session.query(User).filter(User.email == email).one()
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == target_word["word_id"],
        )
        .one()
    )

    assert progress.times_seen == 1
    assert progress.reps == 0
    assert db_session.query(ReviewLog).filter(ReviewLog.progress_id == progress.id).count() == 0


def test_post_message_creates_vocab_erratum_for_incorrect_target_use(
    client: TestClient, french_vocabulary, stubbed_session_service, db_session
) -> None:
    email = "session-vocab-error@example.com"
    token = register_and_login(client, email, "strongpass")
    headers = {"Authorization": f"Bearer {token}"}

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = UUID(session_payload["session"]["id"])
    target_word = session_payload["assistant_turn"]["targets"][0]
    stubbed_session_service["detector"].result = ErrorDetectionResult(
        errors=[
            DetectedError(
                code="lexical_choice",
                message="This target word is not natural in this sentence.",
                span=target_word["word"],
                suggestion=target_word["word"],
                category="vocabulary",
                severity="medium",
                confidence=0.95,
            )
        ],
        summary="Vocabulary needs repair.",
        metadata={"stub": True},
    )

    turn = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": f"Je utilise {target_word['word']} ici."},
        headers=headers,
    )

    assert turn.status_code == 200
    assert turn.json()["word_feedback"][0]["had_error"] is True

    user = db_session.query(User).filter(User.email == email).one()
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == target_word["word_id"],
        )
        .one()
    )
    erratum = (
        db_session.query(UserError)
        .filter(
            UserError.user_id == user.id,
            UserError.linked_word_id == target_word["word_id"],
            UserError.task_error_type == "vocabulary_incorrect_use",
        )
        .one()
    )

    assert progress.times_used_incorrectly == 1
    assert progress.state == "relearning"
    assert erratum.review_mode == "vocabulary"
    assert erratum.source_type == "session"


def test_post_message_returns_pending_grammar_moment_for_due_concept(
    client: TestClient,
    french_vocabulary,
    stubbed_session_service,
    db_session,
) -> None:
    token = register_and_login(client, "session-grammar-moment@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "session-grammar-moment@example.com").one()

    concept = GrammarConcept(
        name="Conditionnel present",
        level="B1",
        description="Use the conditional to express polite requests or hypothetical actions.",
        examples="Je voudrais un cafe.",
    )
    db_session.add(concept)
    db_session.flush()
    db_session.add(
        UserGrammarProgress(
            user_id=user.id,
            concept_id=concept.id,
            score=4.0,
            reps=1,
            state="in_arbeit",
            next_review=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    )
    db_session.commit()

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = session_payload["session"]["id"]

    turn = client.post(
        f"/api/v1/sessions/{session_id}/messages",
        json={"content": "Je parle francais tous les jours."},
        headers=headers,
    )

    assert turn.status_code == 200
    payload = turn.json()
    pending_moment = payload["assistant_turn"]["pending_moment"]
    assert pending_moment is not None
    assert pending_moment["kind"] == "grammar_challenge"
    assert pending_moment["source_type"] == "grammar"
    assert pending_moment["metadata"]["concept_id"] == concept.id


def test_session_moment_endpoints_submit_skip_and_history_reconstruction(
    client: TestClient,
    french_vocabulary,
    stubbed_session_service,
    db_session,
) -> None:
    token = register_and_login(client, "session-moment-submit@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "session-moment-submit@example.com").one()

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = UUID(session_payload["session"]["id"])

    assistant_message = (
        db_session.query(ConversationMessage)
        .filter(
            ConversationMessage.session_id == session_id,
            ConversationMessage.sender == "assistant",
        )
        .order_by(ConversationMessage.sequence_number.desc())
        .one()
    )
    vocab_word = french_vocabulary[0]

    pending_submit = SessionLearningMoment(
        session_id=session_id,
        user_id=user.id,
        anchor_message_id=assistant_message.id,
        kind="vocab_check",
        source_type="vocabulary",
        source_id=str(vocab_word.id),
        source_deck_name="Französisch 5000::1. FR → DE",
        status="pending",
        prompt_payload={
            "title": f"Quick check: {vocab_word.word}",
            "body": f"What does `{vocab_word.word}` mean?",
            "input_mode": "free_text",
            "choices": [],
            "prefill_text": None,
            "metadata": {
                "word_id": vocab_word.id,
                "word": vocab_word.word,
                "translation": vocab_word.english_translation,
                "correct_answer": vocab_word.english_translation,
                "accepted_answers": [vocab_word.english_translation],
                "deck_name": "Französisch 5000::1. FR → DE",
            },
        },
    )
    db_session.add(pending_submit)
    db_session.flush()
    SessionService(db_session).moment_planner.sync_anchor_message_snapshot(pending_submit)
    db_session.commit()

    messages_response = client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers)
    assert messages_response.status_code == 200
    assistant_payload = next(
        item for item in messages_response.json()["items"] if item["sender"] == "assistant"
    )
    assert assistant_payload["pending_moment"]["id"] == str(pending_submit.id)

    submit_response = client.post(
        f"/api/v1/sessions/{session_id}/moments/{pending_submit.id}/submit",
        json={"answer_text": vocab_word.english_translation},
        headers=headers,
    )
    assert submit_response.status_code == 200
    submit_payload = submit_response.json()
    assert submit_payload["moment_result"]["moment_id"] == str(pending_submit.id)
    assert submit_payload["moment_result"]["is_correct"] is True
    assert submit_payload["next_moment"] is None
    recognized_progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == vocab_word.id,
        )
        .one()
    )
    assert recognized_progress.reps == 1
    assert (
        db_session.query(ReviewLog)
        .filter(ReviewLog.progress_id == recognized_progress.id)
        .one()
        .rating
        == 2
    )

    pending_skip = SessionLearningMoment(
        session_id=session_id,
        user_id=user.id,
        anchor_message_id=assistant_message.id,
        kind="grammar_challenge",
        source_type="grammar",
        source_id="42",
        status="pending",
        prompt_payload={
            "title": "Practice conditionnel",
            "body": "Write one sentence using the conditionnel.",
            "input_mode": "free_text",
            "choices": [],
            "prefill_text": None,
            "metadata": {
                "concept_id": 42,
                "concept_name": "Conditionnel",
                "exercise_type": "short_answer",
                "prompt": "Write one sentence using the conditionnel.",
                "correct_answer": "Je voudrais un cafe.",
            },
        },
    )
    db_session.add(pending_skip)
    db_session.flush()
    SessionService(db_session).moment_planner.sync_anchor_message_snapshot(pending_skip)
    db_session.commit()

    skip_response = client.post(
        f"/api/v1/sessions/{session_id}/moments/{pending_skip.id}/skip",
        headers=headers,
    )
    assert skip_response.status_code == 200
    skip_payload = skip_response.json()
    assert skip_payload["moment_result"]["moment_id"] == str(pending_skip.id)
    assert skip_payload["moment_result"]["is_correct"] is None


def test_vocab_check_wrong_answer_creates_vocab_linked_erratum(
    client: TestClient,
    french_vocabulary,
    stubbed_session_service,
    db_session,
) -> None:
    token = register_and_login(client, "session-vocab-check-error@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).filter(User.email == "session-vocab-check-error@example.com").one()

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_id = UUID(start.json()["session"]["id"])
    assistant_message = (
        db_session.query(ConversationMessage)
        .filter(
            ConversationMessage.session_id == session_id,
            ConversationMessage.sender == "assistant",
        )
        .order_by(ConversationMessage.sequence_number.desc())
        .one()
    )
    vocab_word = french_vocabulary[0]
    pending_submit = SessionLearningMoment(
        session_id=session_id,
        user_id=user.id,
        anchor_message_id=assistant_message.id,
        kind="vocab_check",
        source_type="vocabulary",
        source_id=str(vocab_word.id),
        source_deck_name="Französisch 5000::1. FR → DE",
        status="pending",
        prompt_payload={
            "title": f"Quick check: {vocab_word.word}",
            "body": f"What does `{vocab_word.word}` mean?",
            "input_mode": "free_text",
            "choices": [],
            "prefill_text": None,
            "metadata": {
                "word_id": vocab_word.id,
                "word": vocab_word.word,
                "translation": vocab_word.english_translation,
                "correct_answer": vocab_word.english_translation,
                "accepted_answers": [vocab_word.english_translation],
                "deck_name": "Französisch 5000::1. FR → DE",
            },
        },
    )
    db_session.add(pending_submit)
    db_session.flush()
    SessionService(db_session).moment_planner.sync_anchor_message_snapshot(pending_submit)
    db_session.commit()

    submit_response = client.post(
        f"/api/v1/sessions/{session_id}/moments/{pending_submit.id}/submit",
        json={"answer_text": "totally different"},
        headers=headers,
    )

    assert submit_response.status_code == 200
    assert submit_response.json()["moment_result"]["is_correct"] is False

    erratum = (
        db_session.query(UserError)
        .filter(
            UserError.user_id == user.id,
            UserError.linked_word_id == vocab_word.id,
            UserError.task_error_type == "vocabulary_incorrect_use",
        )
        .one()
    )
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(UserVocabularyProgress.user_id == user.id, UserVocabularyProgress.word_id == vocab_word.id)
        .one()
    )

    assert erratum.review_mode == "vocabulary"
    assert erratum.source_type == "session"
    assert progress.times_used_incorrectly == 1
