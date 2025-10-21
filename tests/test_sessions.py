from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import spacy

from app.api import deps
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.db.models.progress import UserVocabularyProgress
from app.services.llm_service import LLMResult
from app.services.progress import ProgressService
from app.services.session_service import SessionService
from app.core.conversation import ConversationGenerator
from app.core.error_detection import ErrorDetectionResult


class StubLLMService:
    """Return deterministic completions for tests."""

    def __init__(self) -> None:
        self.counter = 0

    def generate_chat_completion(self, messages, *, temperature=0.0, max_tokens=0, response_format=None, system_prompt=None):  # type: ignore[override]
        self.counter += 1
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

    def analyze(self, learner_message: str, *, learner_level: str = "B1", target_vocabulary=None, use_llm: bool = True) -> ErrorDetectionResult:  # type: ignore[override]
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
            nlp=spacy.blank("fr"),
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


@pytest.fixture()
def french_vocabulary(db_session):
    words = [
        VocabularyWord(
            language="fr",
            word="baguette",
            normalized_word="baguette",
            part_of_speech="noun",
            frequency_rank=10,
            english_translation="baguette",
            difficulty_level=1,
        ),
        VocabularyWord(
            language="fr",
            word="fromage",
            normalized_word="fromage",
            part_of_speech="noun",
            frequency_rank=11,
            english_translation="cheese",
            difficulty_level=1,
        ),
        VocabularyWord(
            language="fr",
            word="bonjour",
            normalized_word="bonjour",
            part_of_speech="interjection",
            frequency_rank=5,
            english_translation="hello",
            difficulty_level=1,
        ),
    ]
    db_session.add_all(words)
    db_session.commit()
    try:
        yield words
    finally:
        db_session.query(VocabularyWord).delete()
        db_session.commit()


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
