"""Session management endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user, get_session_service
from app.api.v1.endpoints.session_utils import (
    assistant_turn_to_schema,
    error_feedback_from_result,
    message_to_schema,
    session_to_overview,
    word_feedback_to_schema,
)
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.schemas import (
    SessionCreateRequest,
    SessionMessageListResponse,
    SessionMessageRequest,
    SessionOverview,
    SessionStartResponse,
    SessionStatusUpdate,
    SessionSummaryResponse,
    SessionTurnResponse,
    WordExposureRequest,
)
from app.services.session_service import SessionService


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionStartResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreateRequest,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionStartResponse:
    """Create a new learning session."""

    result = service.create_session(
        user=current_user,
        planned_duration_minutes=payload.planned_duration_minutes,
        topic=payload.topic,
        conversation_style=payload.conversation_style,
        difficulty_preference=payload.difficulty_preference,
        generate_greeting=payload.generate_greeting,
    )
    session_schema = session_to_overview(result.session)
    assistant_schema = assistant_turn_to_schema(
        result.assistant_turn,
        target_details=result.assistant_turn.target_details if result.assistant_turn else None,
    )
    return SessionStartResponse(session=session_schema, assistant_turn=assistant_schema)


@router.get("", response_model=list[SessionOverview])
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> list[SessionOverview]:
    records = service.list_sessions(user=current_user, limit=limit, offset=offset)
    return [session_to_overview(record) for record in records]


def _resolve_session(
    service: SessionService, session_id: UUID, user: User
) -> LearningSession:
    try:
        return service.get_session(session_id=session_id, user=user)
    except ValueError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{session_id}", response_model=SessionOverview)
def get_session(
    session_id: UUID,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionOverview:
    session = _resolve_session(service, session_id, current_user)
    return session_to_overview(session)


@router.get("/{session_id}/messages", response_model=SessionMessageListResponse)
def list_session_messages(
    session_id: UUID,
    *,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionMessageListResponse:
    session = _resolve_session(service, session_id, current_user)
    messages = service.list_messages(session=session, limit=limit, offset=offset)
    target_map = service.build_message_target_map(
        user=current_user,
        message_ids=[message.id for message in messages],
    )
    items = [
        message_to_schema(message, target_details=target_map.get(message.id, []))
        for message in messages
    ]
    return SessionMessageListResponse(items=items, total=len(items))


@router.post("/{session_id}/messages", response_model=SessionTurnResponse)
def post_session_message(
    session_id: UUID,
    payload: SessionMessageRequest,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionTurnResponse:
    session = _resolve_session(service, session_id, current_user)
    try:
        result = service.process_user_message(
            session=session,
            user=current_user,
            content=payload.content,
            suggested_word_ids=payload.suggested_word_ids or [],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session_schema = session_to_overview(result.session)
    user_message = message_to_schema(result.user_message)
    assistant_schema = assistant_turn_to_schema(
        result.assistant_turn,
        target_details=result.assistant_turn.target_details if result.assistant_turn else None,
    )
    error_feedback = error_feedback_from_result(result)
    word_feedback = word_feedback_to_schema(result.word_feedback)
    return SessionTurnResponse(
        session=session_schema,
        user_message=user_message,
        assistant_turn=assistant_schema,
        xp_awarded=result.xp_awarded,
        error_feedback=error_feedback,
        word_feedback=word_feedback,
    )


@router.post("/{session_id}/exposures", status_code=status.HTTP_204_NO_CONTENT)
def log_word_exposure(
    session_id: UUID,
    payload: WordExposureRequest,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    session = _resolve_session(service, session_id, current_user)
    service.record_word_exposure(
        session=session,
        user=current_user,
        word_id=payload.word_id,
        exposure_type=payload.exposure_type,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/difficult_words", status_code=status.HTTP_204_NO_CONTENT)
def mark_word_difficult(
    session_id: UUID,
    payload: WordExposureRequest,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    session = _resolve_session(service, session_id, current_user)
    service.mark_word_difficult(
        session=session,
        user=current_user,
        word_id=payload.word_id,
        reason=payload.exposure_type,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{session_id}", response_model=SessionOverview)
def update_session_status(
    session_id: UUID,
    payload: SessionStatusUpdate,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionOverview:
    session = _resolve_session(service, session_id, current_user)
    try:
        updated = service.update_status(session, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return session_to_overview(updated)


@router.get("/{session_id}/summary", response_model=SessionSummaryResponse)
def get_session_summary(
    session_id: UUID,
    *,
    service: SessionService = Depends(get_session_service),
    current_user: User = Depends(get_current_user),
) -> SessionSummaryResponse:
    session = _resolve_session(service, session_id, current_user)
    summary = service.session_summary(session)
    return SessionSummaryResponse(**summary)
