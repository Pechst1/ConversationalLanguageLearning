"""Session management endpoints."""
from __future__ import annotations

from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_session_service
from app.db.models.session import ConversationMessage, LearningSession
from app.db.models.user import User
from app.schemas import (
    AssistantTurnRead,
    DetectedErrorRead,
    ErrorFeedback,
    SessionCreateRequest,
    SessionMessageListResponse,
    SessionMessageRead,
    SessionMessageRequest,
    SessionOverview,
    SessionStartResponse,
    SessionStatusUpdate,
    SessionSummaryResponse,
    SessionTurnResponse,
    SessionTurnWordFeedback,
    TargetWordRead,
)
from app.services.session_service import AssistantTurn, SessionService, SessionTurnResult, WordFeedback


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_to_overview(session: LearningSession) -> SessionOverview:
    return SessionOverview(
        id=session.id,
        status=session.status,
        topic=session.topic,
        conversation_style=session.conversation_style,
        planned_duration_minutes=session.planned_duration_minutes,
        xp_earned=session.xp_earned or 0,
        words_practiced=session.words_practiced or 0,
        accuracy_rate=session.accuracy_rate,
        started_at=session.started_at,
        completed_at=session.completed_at,
    )


def _message_to_schema(message: ConversationMessage) -> SessionMessageRead:
    payload = message.errors_detected or {}
    error_feedback = None
    if isinstance(payload, dict) and payload.get("summary"):
        error_feedback = ErrorFeedback(
            summary=payload.get("summary", ""),
            errors=[DetectedErrorRead(**entry) for entry in payload.get("errors", [])],
            review_vocabulary=payload.get("review_vocabulary", []) or [],
            metadata=payload.get("metadata", {}) or {},
        )
    return SessionMessageRead(
        id=message.id,
        sender=message.sender,  # type: ignore[arg-type]
        content=message.content,
        sequence_number=message.sequence_number,
        created_at=message.created_at,
        xp_earned=message.xp_earned or 0,
        target_words=message.target_words or [],
        words_used=message.words_used or [],
        suggested_words_used=message.suggested_words_used or [],
        error_feedback=error_feedback,
    )


def _assistant_turn_to_schema(turn: AssistantTurn | None) -> AssistantTurnRead | None:
    if not turn:
        return None
    message_schema = _message_to_schema(turn.message)
    targets = [
        TargetWordRead(
            word_id=target.id,
            word=target.surface,
            translation=target.translation,
            is_new=target.is_new,
        )
        for target in turn.plan.target_words
    ]
    return AssistantTurnRead(message=message_schema, targets=targets)


def _feedback_to_schema(items: Iterable[WordFeedback]) -> list[SessionTurnWordFeedback]:
    payload: list[SessionTurnWordFeedback] = []
    for item in items:
        error_schema = None
        if item.error:
            error_schema = DetectedErrorRead(
                code=item.error.code,
                message=item.error.message,
                span=item.error.span,
                suggestion=item.error.suggestion,
                category=item.error.category,
                severity=item.error.severity,
                confidence=item.error.confidence,
            )
        payload.append(
            SessionTurnWordFeedback(
                word_id=item.word.id,
                word=item.word.word,
                translation=item.word.english_translation,
                is_new=item.is_new,
                was_used=item.was_used,
                rating=item.rating,
                had_error=item.had_error,
                error=error_schema,
            )
        )
    return payload


def _error_feedback_from_result(result: SessionTurnResult) -> ErrorFeedback:
    return ErrorFeedback(
        summary=result.error_result.summary,
        errors=[
            DetectedErrorRead(
                code=error.code,
                message=error.message,
                span=error.span,
                suggestion=error.suggestion,
                category=error.category,
                severity=error.severity,
                confidence=error.confidence,
            )
            for error in result.error_result.errors
        ],
        review_vocabulary=result.error_result.review_vocabulary,
        metadata=result.error_result.metadata,
    )


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
    session_schema = _session_to_overview(result.session)
    assistant_schema = _assistant_turn_to_schema(result.assistant_turn)
    return SessionStartResponse(session=session_schema, assistant_turn=assistant_schema)


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
    return _session_to_overview(session)


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
    items = [_message_to_schema(message) for message in messages]
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

    session_schema = _session_to_overview(result.session)
    user_message = _message_to_schema(result.user_message)
    assistant_schema = _assistant_turn_to_schema(result.assistant_turn)
    error_feedback = _error_feedback_from_result(result)
    word_feedback = _feedback_to_schema(result.word_feedback)
    return SessionTurnResponse(
        session=session_schema,
        user_message=user_message,
        assistant_turn=assistant_schema,
        xp_awarded=result.xp_awarded,
        error_feedback=error_feedback,
        word_feedback=word_feedback,
    )


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
    return _session_to_overview(updated)


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

