"""Helper utilities shared between session endpoints."""
from __future__ import annotations

from typing import Any, Iterable

from app.db.models.session import ConversationMessage, LearningSession, SessionLearningMoment
from app.schemas import (
    AssistantTurnRead,
    DetectedErrorRead,
    ErrorFeedback,
    ErrorOccurrenceStats,
    LearningFocusRead,
    LearningMomentRead,
    LearningMomentResultRead,
    SessionMessageRead,
    SessionOverview,
    SessionTurnWordFeedback,
    TargetedErrorRead,
    TargetWordRead,
)
from app.services.session_moment_planner import MomentEvaluation
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
    pending_moment: SessionLearningMoment | dict[str, Any] | None = None,
) -> SessionMessageRead:
    payload = message.errors_detected or {}
    error_feedback = None
    learning_focus = []
    pending_moment_schema = None
    if isinstance(payload, dict) and payload.get("summary"):
        error_feedback = ErrorFeedback(
            summary=payload.get("summary", ""),
            errors=[DetectedErrorRead(**entry) for entry in payload.get("errors", [])],
            review_vocabulary=payload.get("review_vocabulary", []) or [],
            metadata=payload.get("metadata", {}) or {},
        )
    if isinstance(payload, dict):
        learning_focus = [
            LearningFocusRead(**entry)
            for entry in payload.get("learning_focus", []) or []
        ]
        if pending_moment is None:
            pending_moment_schema = learning_moment_to_schema(payload.get("pending_moment"))
    if pending_moment is not None:
        pending_moment_schema = learning_moment_to_schema(pending_moment)
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
        learning_focus=learning_focus,
        pending_moment=pending_moment_schema,
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
    message_schema = message_to_schema(
        turn.message,
        target_details=details,
        pending_moment=turn.pending_moment,
    )

    # Build targeted error schemas
    targeted_error_schemas = []
    error_items = targeted_errors if targeted_errors is not None else turn.targeted_errors
    if error_items:
        for err in error_items[:3]:  # Limit to top 3
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

    learning_focus = message_schema.learning_focus or _build_learning_focus(
        target_details=details,
        targeted_errors=error_items or [],
        targeted_grammar=turn.targeted_grammar,
    )

    return AssistantTurnRead(
        message=message_schema,
        targets=details,
        targeted_errors=targeted_error_schemas,
        learning_focus=learning_focus,
        pending_moment=message_schema.pending_moment,
    )


def learning_moment_to_schema(
    moment: SessionLearningMoment | dict[str, Any] | None,
) -> LearningMomentRead | None:
    if not moment:
        return None

    if isinstance(moment, dict):
        payload = dict(moment)
    else:
        payload = dict(moment.prompt_payload or {})
        payload.update(
            {
                "id": moment.id,
                "kind": moment.kind,
                "source_type": moment.source_type,
                "status": moment.status,
            }
        )

    return LearningMomentRead(
        id=payload.get("id"),
        kind=payload.get("kind"),
        source_type=payload.get("source_type"),
        title=payload.get("title") or "",
        body=payload.get("body") or "",
        input_mode=payload.get("input_mode") or "free_text",
        choices=payload.get("choices") or [],
        prefill_text=payload.get("prefill_text"),
        metadata=payload.get("metadata") or {},
        status=payload.get("status") or "pending",
    )


def learning_moment_result_to_schema(
    result: MomentEvaluation | dict[str, Any] | None,
) -> LearningMomentResultRead | None:
    if not result:
        return None

    if isinstance(result, dict):
        payload = result
    else:
        payload = {
            "moment_id": result.moment.id,
            "is_correct": result.is_correct,
            "score_0_10": result.score_0_10,
            "feedback_summary": result.feedback_summary,
            "next_step_hint": result.next_step_hint,
        }

    return LearningMomentResultRead(
        moment_id=payload.get("moment_id"),
        is_correct=payload.get("is_correct"),
        score_0_10=payload.get("score_0_10"),
        feedback_summary=payload.get("feedback_summary") or "",
        next_step_hint=payload.get("next_step_hint"),
    )


def _build_learning_focus(
    *,
    target_details: list[TargetWordRead],
    targeted_errors: list[UserError],
    targeted_grammar: list[tuple[object, object | None]],
) -> list[LearningFocusRead]:
    items: list[LearningFocusRead] = []

    for index, error in enumerate(targeted_errors[:3]):
        subtitle_bits = [error.error_pattern, f"{error.lapses or 0} lapses"]
        subtitle = " • ".join(bit for bit in subtitle_bits if bit)
        items.append(
            LearningFocusRead(
                kind="error",
                key=f"error:{error.id}",
                title=error.error_category,
                subtitle=subtitle or None,
                state=error.state,
                priority=300 - index,
                metadata={
                    "correction": error.correction,
                    "context": error.context_snippet,
                    "reps": error.reps or 0,
                    "lapses": error.lapses or 0,
                },
            )
        )

    for index, entry in enumerate(targeted_grammar[:2]):
        concept, progress = entry
        state = getattr(progress, "state", "neu")
        state_label = getattr(progress, "state_label", state)
        items.append(
            LearningFocusRead(
                kind="grammar",
                key=f"grammar:{getattr(concept, 'id', index)}",
                title=getattr(concept, "name", "Grammar focus"),
                subtitle=f"{getattr(concept, 'level', 'A1')} • {state_label}",
                state=state,
                priority=200 - index,
                metadata={
                    "concept_id": getattr(concept, "id", None),
                    "level": getattr(concept, "level", None),
                    "description": getattr(concept, "description", None),
                    "examples": getattr(concept, "examples", None),
                },
            )
        )

    for index, target in enumerate(target_details):
        subtitle = target.translation or ("New word" if target.is_new else "Review word")
        items.append(
            LearningFocusRead(
                kind="vocabulary",
                key=f"word:{target.word_id}",
                title=target.word,
                subtitle=subtitle,
                state=target.familiarity,
                priority=(120 if target.is_new else 100) - index,
                metadata={
                    "word_id": target.word_id,
                    "is_new": target.is_new,
                    "translation": target.translation,
                    "hint_sentence": target.hint_sentence,
                    "hint_translation": target.hint_translation,
                },
            )
        )

    items.sort(key=lambda item: (-item.priority, item.title.lower()))
    return items


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
    "learning_moment_result_to_schema",
    "learning_moment_to_schema",
    "message_to_schema",
    "session_to_overview",
    "word_feedback_to_schema",
]
