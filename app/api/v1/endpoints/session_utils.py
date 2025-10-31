"""Helper utilities shared between session endpoints."""
from __future__ import annotations

from typing import Iterable

from app.db.models.session import ConversationMessage, LearningSession
from app.schemas import (
    AssistantTurnRead,
    DetectedErrorRead,
    ErrorFeedback,
    SessionMessageRead,
    SessionOverview,
    SessionTurnWordFeedback,
    TargetWordRead,
)
from app.services.session_service import AssistantTurn, SessionTurnResult, WordFeedback


def session_to_overview(session: LearningSession) -> SessionOverview:
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


def message_to_schema(
    message: ConversationMessage,
    *,
    target_details: list[TargetWordRead] | None = None,
) -> SessionMessageRead:
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
        target_details=target_details or [],
    )


def assistant_turn_to_schema(
    turn: AssistantTurn | None,
    *,
    target_details: list[TargetWordRead] | None = None,
) -> AssistantTurnRead | None:
    if not turn:
        return None
    details = target_details
    if details is None:
        details = [
            TargetWordRead(
                word_id=target.id,
                word=target.surface,
                translation=target.translation,
                is_new=target.is_new,
            )
            for target in turn.plan.target_words
        ]
    message_schema = message_to_schema(turn.message, target_details=details)
    return AssistantTurnRead(message=message_schema, targets=details)


def word_feedback_to_schema(items: Iterable[WordFeedback]) -> list[SessionTurnWordFeedback]:
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


def error_feedback_from_result(result: SessionTurnResult) -> ErrorFeedback:
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


__all__ = [
    "assistant_turn_to_schema",
    "error_feedback_from_result",
    "message_to_schema",
    "session_to_overview",
    "word_feedback_to_schema",
]
