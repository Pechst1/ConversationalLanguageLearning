"""Real-time WebSocket endpoint for session messaging."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import TypeAdapter, ValidationError

from app.api.deps import get_connection_manager, get_session_service
from app.api.v1.endpoints.session_utils import (
    assistant_turn_to_schema,
    error_feedback_from_result,
    message_to_schema,
    session_to_overview,
    word_feedback_to_schema,
)
from app.core.security import InvalidTokenError, decode_token
from app.db.models.user import User
from app.schemas import SessionTurnResponse, TokenPayload
from app.schemas.realtime import (
    SessionClientMessage,
    SessionHeartbeatMessage,
    SessionTypingMessage,
    SessionUserMessage,
)
from app.services.realtime import SessionConnectionManager
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])

client_message_adapter = TypeAdapter(SessionClientMessage)


def _extract_token(websocket: WebSocket) -> str | None:
    header = websocket.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header.split(" ", 1)[1]
    query_token = websocket.query_params.get("token")
    return query_token


def _resolve_user(token: str, service: SessionService) -> User | None:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise InvalidTokenError("Token must be an access token")
        token_data = TokenPayload.model_validate(payload)
    except (InvalidTokenError, ValidationError, ValueError, KeyError):
        return None
    user_id = uuid.UUID(str(token_data.sub))
    return service.db.get(User, user_id)


@router.websocket("/{session_id}/ws")
async def session_stream(
    websocket: WebSocket,
    session_id: uuid.UUID,
    connection_manager: SessionConnectionManager = Depends(get_connection_manager),
    service: SessionService = Depends(get_session_service),
) -> None:
    token = _extract_token(websocket)
    if not token:
        await websocket.close(code=1008)
        return

    user = _resolve_user(token, service)
    if not user:
        await websocket.close(code=1008)
        return

    try:
        session = service.get_session(session_id=session_id, user=user)
    except ValueError:
        await websocket.close(code=1008)
        return

    await connection_manager.connect(websocket=websocket, session_id=session.id, user_id=user.id)

    overview = session_to_overview(session)
    active_users = await connection_manager.list_active_users(session.id)
    await connection_manager.send_personal_message(
        session_id=session.id,
        user_id=user.id,
        message={
            "type": "session_ready",
            "data": {
                "session": overview.model_dump(mode="json"),
                "active_user_ids": active_users,
            },
        },
    )

    try:
        while True:
            try:
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                break

            try:
                message = client_message_adapter.validate_python(data)
            except ValidationError as exc:
                await connection_manager.send_personal_message(
                    session_id=session.id,
                    user_id=user.id,
                    message={
                        "type": "error",
                        "data": {
                            "detail": "invalid_payload",
                            "errors": exc.errors(),
                        },
                    },
                )
                continue

            if isinstance(message, SessionHeartbeatMessage):
                await connection_manager.mark_heartbeat(session_id=session.id, user_id=user.id)
                await connection_manager.send_personal_message(
                    session_id=session.id,
                    user_id=user.id,
                    message={
                        "type": "heartbeat",
                        "data": {"server_time": datetime.now(timezone.utc).isoformat()},
                    },
                )
                continue

            if isinstance(message, SessionTypingMessage):
                await connection_manager.broadcast(
                    session_id=session.id,
                    message={
                        "type": "typing",
                        "data": {
                            "user_id": str(user.id),
                            "is_typing": message.is_typing,
                        },
                    },
                )
                continue

            if isinstance(message, SessionUserMessage):
                try:
                    result = service.process_user_message(
                        session=session,
                        user=user,
                        content=message.content,
                        suggested_word_ids=message.suggested_words,
                    )
                except ValueError as exc:
                    await connection_manager.send_personal_message(
                        session_id=session.id,
                        user_id=user.id,
                        message={
                            "type": "error",
                            "data": {
                                "detail": "processing_failed",
                                "message": str(exc),
                            },
                        },
                    )
                    continue

                session = result.session
                response = SessionTurnResponse(
                    session=session_to_overview(result.session),
                    user_message=message_to_schema(result.user_message),
                    assistant_turn=assistant_turn_to_schema(result.assistant_turn),
                    xp_awarded=result.xp_awarded,
                    error_feedback=error_feedback_from_result(result),
                    word_feedback=word_feedback_to_schema(result.word_feedback),
                )
                await connection_manager.broadcast(
                    session_id=session.id,
                    message={
                        "type": "turn_result",
                        "data": response.model_dump(mode="json"),
                    },
                )
                continue

            logger.debug("Unhandled WebSocket message", payload=data)
    finally:
        await connection_manager.disconnect(session_id=session.id, user_id=user.id)
