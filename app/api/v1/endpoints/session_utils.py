"""Helper utilities shared between session endpoints."""
from __future__ import annotations

from typing import Iterable

from app.db.models.session import ConversationMessage, LearningSession
from app.schemas import (
    AssistantTurnRead,
    DetectedErrorRead,
    ErrorFeedback,
    ErrorOccurrenceStats,
    SessionMessageRead,
    SessionOverview,
    SessionTurnWordFeedback,
    TargetedErrorRead,
    TargetWordRead,
)
from app.services.session_service import AssistantTurn, SessionTurnResult, WordFeedback
from app.db.models.error import UserError


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
        anki_direction=session.anki_direction,
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
    targeted_errors: list[UserError] | None = None,
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
    
    # Build targeted error schemas
    targeted_error_schemas = []
    if targeted_errors:
        for err in targeted_errors[:3]:  # Limit to top 3
            targeted_error_schemas.append(
                TargetedErrorRead(
                    category=err.error_category,
                    pattern=err.error_pattern,
                    context=err.context_snippet,
                    correction=err.correction,
                    lapses=err.lapses or 0,
                    reps=err.reps or 0,
                )
            )
    
    return AssistantTurnRead(
        message=message_schema,
        targets=details,
        targeted_errors=targeted_error_schemas,
    )


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
                translation=(
                    item.word.german_translation
                    if item.word.direction == "fr_to_de"
                    else item.word.french_translation
                    if item.word.direction == "de_to_fr"
                    else item.word.english_translation
                ),
                is_new=item.is_new,
                was_used=item.was_used,
                rating=item.rating,
                had_error=item.had_error,
                error=error_schema,
            )
        )
    return payload


def error_feedback_from_result(result: SessionTurnResult) -> ErrorFeedback:
    # Build a map of error stats by category+pattern for enriching individual errors
    stats_map: dict[tuple[str, str | None], tuple[int, bool]] = {}
    for stat in result.error_stats:
        key = (stat.category, stat.pattern)
        stats_map[key] = (stat.total_occurrences, stat.total_occurrences > 1)

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
                # Include occurrence info from stats
                occurrence_count=stats_map.get((error.category, error.code), (1, False))[0],
                is_recurring=stats_map.get((error.category, error.code), (1, False))[1],
            )
            for error in result.error_result.errors
        ],
        review_vocabulary=result.error_result.review_vocabulary,
        metadata=result.error_result.metadata,
        error_stats=[
            ErrorOccurrenceStats(
                category=stat.category,
                pattern=stat.pattern,
                total_occurrences=stat.total_occurrences,
                occurrences_today=stat.occurrences_today,
                last_seen=stat.last_seen,
                next_review=stat.next_review,
                state=stat.state,
            )
            for stat in result.error_stats
        ],
    )


__all__ = [
    "assistant_turn_to_schema",
    "error_feedback_from_result",
    "message_to_schema",
    "session_to_overview",
    "word_feedback_to_schema",
]

