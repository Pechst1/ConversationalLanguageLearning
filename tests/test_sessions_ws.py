from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect

import spacy

from app.api import deps
from app.services.realtime import SessionConnectionManager
from app.services.progress import ProgressService
from app.services.session_service import SessionService
from app.core.conversation import ConversationGenerator

from tests.test_sessions import StubErrorDetector, StubLLMService, register_and_login


@pytest.fixture()
def websocket_dependencies(client: TestClient, db_session):
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

    def override_connection_manager():
        return SessionConnectionManager(redis_url=None)

    client.app.dependency_overrides[deps.get_llm_service] = override_llm_service
    client.app.dependency_overrides[deps.get_error_detector] = override_error_detector
    client.app.dependency_overrides[deps.get_session_service] = override_session_service
    client.app.dependency_overrides[deps.get_connection_manager] = override_connection_manager
    deps._llm_service_singleton = None
    deps._error_detector_singleton = None
    deps._connection_manager_singleton = None

    try:
        yield {"llm": stub_llm, "detector": stub_detector}
    finally:
        client.app.dependency_overrides.pop(deps.get_session_service, None)
        client.app.dependency_overrides.pop(deps.get_error_detector, None)
        client.app.dependency_overrides.pop(deps.get_llm_service, None)
        client.app.dependency_overrides.pop(deps.get_connection_manager, None)
        deps._llm_service_singleton = None
        deps._error_detector_singleton = None
        deps._connection_manager_singleton = None


def test_websocket_turn_flow(client: TestClient, websocket_dependencies, french_vocabulary):
    token = register_and_login(client, "ws-flow@example.com", "strongpass")
    headers = {"Authorization": f"Bearer {token}"}

    start = client.post(
        "/api/v1/sessions",
        json={"planned_duration_minutes": 15},
        headers=headers,
    )
    session_payload = start.json()
    session_id = UUID(session_payload["session"]["id"])

    with client.websocket_connect(f"/api/v1/sessions/{session_id}/ws?token={token}") as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session_ready"
        assert ready["data"]["session"]["id"] == str(session_id)

        websocket.send_json(
            {
                "type": "typing",
                "is_typing": True,
            }
        )
        typing_event = websocket.receive_json()
        assert typing_event["type"] == "typing"
        assert typing_event["data"]["is_typing"] is True

        websocket.send_json(
            {
                "type": "user_message",
                "content": "J'aime beaucoup la baguette croustillante.",
                "suggested_words": [],
            }
        )
        turn_result = websocket.receive_json()
        assert turn_result["type"] == "turn_result"
        payload = turn_result["data"]
        assert payload["session"]["id"] == str(session_id)
        assert payload["xp_awarded"] >= 10
        assert payload["assistant_turn"]["message"]["sender"] == "assistant"
        assert payload["word_feedback"]

        websocket.send_json({"type": "heartbeat"})
        heartbeat = websocket.receive_json()
        assert heartbeat["type"] == "heartbeat"
        assert "server_time" in heartbeat["data"]


def test_websocket_rejects_missing_token(client: TestClient, websocket_dependencies):
    try:
        with client.websocket_connect(
            "/api/v1/sessions/00000000-0000-0000-0000-000000000000/ws"
        ) as websocket:
            with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect, RuntimeError)):
                websocket.receive_json()
    except (WebSocketDenialResponse, WebSocketDisconnect):
        # Some transports raise at connect time; both cases are acceptable.
        pass
