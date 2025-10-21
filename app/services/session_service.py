"""Service layer for orchestrating learning sessions."""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.conversation import ConversationGenerator, ConversationHistoryMessage, ConversationPlan
from app.core.error_detection import ErrorDetectionResult, ErrorDetector
from app.core.error_detection.rules import DetectedError
from app.db.models.session import ConversationMessage, LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.llm_service import LLMResult, LLMService
from app.services.progress import ProgressService


@dataclass(slots=True)
class XPConfig:
    """Configuration knobs for XP calculations."""

    base_message: int = 10
    correct_review: int = 15
    correct_new: int = 12
    partial_credit: int = 6


@dataclass(slots=True)
class WordFeedback:
    """Feedback about a targeted vocabulary item for a learner turn."""

    word: VocabularyWord
    is_new: bool
    was_used: bool
    rating: int | None
    had_error: bool
    error: DetectedError | None


@dataclass(slots=True)
class AssistantTurn:
    """Persisted assistant message paired with the generation plan."""

    message: ConversationMessage
    plan: ConversationPlan
    llm_result: LLMResult


@dataclass(slots=True)
class SessionStartResult:
    """Return payload when creating a new session."""

    session: LearningSession
    assistant_turn: AssistantTurn | None


@dataclass(slots=True)
class SessionTurnResult:
    """Return payload after processing a learner message."""

    session: LearningSession
    user_message: ConversationMessage
    assistant_turn: AssistantTurn
    error_result: ErrorDetectionResult
    xp_awarded: int
    word_feedback: list[WordFeedback] = field(default_factory=list)


def _normalize_text(value: str) -> str:
    """Lowercase and strip accents from text for fuzzy comparisons."""

    normalized = unicodedata.normalize("NFKD", value)
    ascii_form = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_form.lower()


def _infer_level_from_xp(total_xp: int) -> int:
    """Map accumulated XP to a learner level."""

    step = 500
    return max(1, math.floor(total_xp / step) + 1)


class SessionService:
    """Coordinate session lifecycle, message flow, and XP updates."""

    VALID_STATUSES = {"created", "in_progress", "paused", "completed", "abandoned"}

    def __init__(
        self,
        db: Session,
        *,
        progress_service: ProgressService | None = None,
        conversation_generator: ConversationGenerator | None = None,
        error_detector: ErrorDetector | None = None,
        llm_service: LLMService | None = None,
        xp_config: XPConfig | None = None,
    ) -> None:
        self.db = db
        self.progress_service = progress_service or ProgressService(db)
        self.llm_service = llm_service or LLMService()
        self.conversation_generator = conversation_generator or ConversationGenerator(
            progress_service=self.progress_service,
            llm_service=self.llm_service,
        )
        self.error_detector = error_detector or ErrorDetector(llm_service=self.llm_service)
        self.xp_config = xp_config or XPConfig()

    # ------------------------------------------------------------------
    # Session lifecycle helpers
    # ------------------------------------------------------------------
    def create_session(
        self,
        *,
        user: User,
        planned_duration_minutes: int,
        topic: str | None = None,
        conversation_style: str | None = None,
        difficulty_preference: str | None = None,
        generate_greeting: bool = True,
    ) -> SessionStartResult:
        """Create a new session and optionally bootstrap the greeting turn."""

        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=planned_duration_minutes,
            topic=topic,
            conversation_style=conversation_style or "tutor",
            difficulty_preference=difficulty_preference,
            status="in_progress",
            level_before=user.level,
            level_after=user.level,
        )
        self.db.add(session)
        self.db.flush([session])

        assistant_turn: AssistantTurn | None = None
        if generate_greeting:
            assistant_turn = self._generate_and_persist_assistant_turn(
                session=session,
                user=user,
                history=[],
            )

        self.db.commit()
        if assistant_turn:
            self.db.refresh(assistant_turn.message)
        self.db.refresh(session)
        return SessionStartResult(session=session, assistant_turn=assistant_turn)

    def _next_sequence_number(self, session_id) -> int:
        stmt = (
            select(func.coalesce(func.max(ConversationMessage.sequence_number), 0))
            .where(ConversationMessage.session_id == session_id)
        )
        current = self.db.scalar(stmt) or 0
        return current + 1

    def _serialize_errors(self, result: ErrorDetectionResult) -> dict:
        return {
            "summary": result.summary,
            "errors": [
                {
                    "code": error.code,
                    "message": error.message,
                    "span": error.span,
                    "suggestion": error.suggestion,
                    "category": error.category,
                    "severity": error.severity,
                    "confidence": error.confidence,
                }
                for error in result.errors
            ],
            "review_vocabulary": result.review_vocabulary,
            "metadata": result.metadata,
        }

    def _target_assignments(
        self, message: ConversationMessage
    ) -> list[tuple[VocabularyWord, bool]]:
        interactions = (
            self.db.query(WordInteraction)
            .options(joinedload(WordInteraction.session))
            .filter(WordInteraction.message_id == message.id)
            .all()
        )
        assignments: list[tuple[VocabularyWord, bool]] = []
        for interaction in interactions:
            if interaction.interaction_type not in {"target_new", "target_review"}:
                continue
            word = self.db.get(VocabularyWord, interaction.word_id)
            if not word:
                continue
            assignments.append((word, interaction.interaction_type == "target_new"))
        return assignments

    def _determine_word_feedback(
        self,
        *,
        user_message: ConversationMessage,
        learner_text: str,
        error_result: ErrorDetectionResult,
        previous_targets: list[tuple[VocabularyWord, bool]],
    ) -> list[WordFeedback]:
        normalized_message = _normalize_text(learner_text)
        feedback: list[WordFeedback] = []
        for word, is_new in previous_targets:
            normalized_word = _normalize_text(word.normalized_word or word.word)
            was_used = normalized_word in normalized_message
            matching_error: DetectedError | None = None
            for error in error_result.errors:
                span = _normalize_text(error.span)
                if normalized_word and normalized_word in span:
                    matching_error = error
                    break
            had_error = matching_error is not None
            rating: int | None
            if was_used and not had_error:
                rating = 3
            elif was_used:
                rating = 2
            elif is_new:
                rating = None
            else:
                rating = 1
            feedback.append(
                WordFeedback(
                    word=word,
                    is_new=is_new,
                    was_used=was_used,
                    rating=rating,
                    had_error=had_error,
                    error=matching_error,
                )
            )
        user_message.words_used = [fb.word.id for fb in feedback if fb.was_used]
        user_message.suggested_words_used = [fb.word.id for fb in feedback if fb.was_used]
        return feedback

    def _apply_progress_updates(
        self,
        *,
        user: User,
        feedback: Sequence[WordFeedback],
    ) -> None:
        for item in feedback:
            if item.rating is None:
                continue
            progress, _, _ = self.progress_service.record_review(
                user=user,
                word=item.word,
                rating=item.rating,
            )
            is_correct = item.rating >= 2
            progress.record_usage(correct=is_correct)

    def _update_word_interactions(
        self,
        *,
        session: LearningSession,
        user: User,
        user_message: ConversationMessage,
        feedback: Sequence[WordFeedback],
        learner_text: str,
    ) -> None:
        for item in feedback:
            interaction = WordInteraction(
                session_id=session.id,
                user_id=user.id,
                word_id=item.word.id,
                message_id=user_message.id,
                interaction_type="learner_use" if item.was_used else "learner_skip",
                user_response=learner_text,
                was_suggested=True,
            )
            if item.error:
                interaction.error_type = item.error.category
                interaction.error_description = item.error.message
                interaction.correction = item.error.suggestion
            self.db.add(interaction)

    def _calculate_xp(self, feedback: Sequence[WordFeedback]) -> int:
        xp = self.xp_config.base_message
        for item in feedback:
            if not item.was_used:
                continue
            if item.rating and item.rating >= 3:
                xp += self.xp_config.correct_new if item.is_new else self.xp_config.correct_review
            elif item.rating and item.rating >= 2:
                xp += self.xp_config.partial_credit
        return xp

    def _refresh_session_stats(
        self,
        *,
        session: LearningSession,
        feedback: Sequence[WordFeedback],
        xp_awarded: int,
    ) -> None:
        session.words_practiced += len(feedback)
        session.new_words_introduced += sum(1 for item in feedback if item.is_new and item.was_used)
        session.words_reviewed += sum(1 for item in feedback if not item.is_new and item.was_used)
        correct = sum(1 for item in feedback if item.was_used and (item.rating or 0) >= 3)
        incorrect = sum(1 for item in feedback if item.was_used and (item.rating or 0) < 3)
        session.correct_responses += correct
        session.incorrect_responses += incorrect
        session.xp_earned += xp_awarded
        total_attempts = session.correct_responses + session.incorrect_responses
        if total_attempts:
            session.accuracy_rate = session.correct_responses / total_attempts

    def _apply_user_xp(self, user: User, session: LearningSession, xp_awarded: int) -> None:
        user.total_xp = (user.total_xp or 0) + xp_awarded
        new_level = _infer_level_from_xp(user.total_xp)
        if new_level > user.level:
            user.level = new_level
        session.level_after = user.level
        user.mark_activity()

    def _collect_history(self, session: LearningSession) -> list[ConversationHistoryMessage]:
        records = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session.id)
            .order_by(ConversationMessage.sequence_number)
            .all()
        )
        return [
            ConversationHistoryMessage(role=record.sender, content=record.content)
            for record in records
        ]

    def _generate_and_persist_assistant_turn(
        self,
        *,
        session: LearningSession,
        user: User,
        history: Sequence[ConversationHistoryMessage],
    ) -> AssistantTurn:
        generated = self.conversation_generator.generate_turn(
            user=user,
            learner_level=user.proficiency_level or "B1",
            style=session.conversation_style or "tutor",
            history=history,
        )
        sequence = self._next_sequence_number(session.id)
        message = ConversationMessage(
            session_id=session.id,
            sender="assistant",
            content=generated.text,
            sequence_number=sequence,
            target_words=[target.id for target in generated.plan.target_words],
            llm_model=generated.llm_result.model,
            tokens_used=generated.llm_result.total_tokens,
        )
        self.db.add(message)
        self.db.flush([message])

        for queue_item in generated.plan.queue_items:
            interaction = WordInteraction(
                session_id=session.id,
                user_id=session.user_id,
                word_id=queue_item.word.id,
                message_id=message.id,
                interaction_type="target_new" if queue_item.is_new else "target_review",
                context_sentence=generated.text,
                was_suggested=True,
            )
            self.db.add(interaction)

        logger.info(
            "Assistant message generated",
            session_id=str(session.id),
            target_count=len(generated.plan.target_words),
        )
        return AssistantTurn(message=message, plan=generated.plan, llm_result=generated.llm_result)

    def process_user_message(
        self,
        *,
        session: LearningSession,
        user: User,
        content: str,
        suggested_word_ids: Sequence[int] | None = None,
    ) -> SessionTurnResult:
        """Persist a learner message, run feedback, and return the assistant reply."""

        if session.status not in {"in_progress", "created", "paused"}:
            raise ValueError("Cannot add messages to a completed or abandoned session")

        history = self._collect_history(session)
        sequence = self._next_sequence_number(session.id)
        user_message = ConversationMessage(
            session_id=session.id,
            sender="user",
            content=content,
            sequence_number=sequence,
            target_words=list(suggested_word_ids or []),
        )
        self.db.add(user_message)
        self.db.flush([user_message])

        previous_assistant = (
            self.db.query(ConversationMessage)
            .filter(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "assistant",
            )
            .order_by(ConversationMessage.sequence_number.desc())
            .first()
        )
        previous_targets: list[tuple[VocabularyWord, bool]] = []
        if previous_assistant:
            previous_targets = self._target_assignments(previous_assistant)

        error_result = self.error_detector.analyze(
            content,
            learner_level=user.proficiency_level or "B1",
            target_vocabulary=[word.word for word, _ in previous_targets],
        )
        user_message.errors_detected = self._serialize_errors(error_result)

        feedback = self._determine_word_feedback(
            user_message=user_message,
            learner_text=content,
            error_result=error_result,
            previous_targets=previous_targets,
        )

        self._apply_progress_updates(user=user, feedback=feedback)
        self._update_word_interactions(
            session=session,
            user=user,
            user_message=user_message,
            feedback=feedback,
            learner_text=content,
        )

        xp_awarded = self._calculate_xp(feedback)
        user_message.xp_earned = xp_awarded
        self._refresh_session_stats(session=session, feedback=feedback, xp_awarded=xp_awarded)
        self._apply_user_xp(user, session, xp_awarded)

        history.append(ConversationHistoryMessage(role="user", content=content))
        assistant_turn = self._generate_and_persist_assistant_turn(
            session=session,
            user=user,
            history=history,
        )

        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_turn.message)
        self.db.refresh(session)
        self.db.refresh(user)

        return SessionTurnResult(
            session=session,
            user_message=user_message,
            assistant_turn=assistant_turn,
            error_result=error_result,
            xp_awarded=xp_awarded,
            word_feedback=list(feedback),
        )

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------
    def get_session(self, *, session_id, user: User) -> LearningSession:
        session = self.db.get(LearningSession, session_id)
        if not session or session.user_id != user.id:
            raise ValueError("Session not found")
        return session

    def list_messages(
        self,
        *,
        session: LearningSession,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ConversationMessage]:
        query = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session.id)
            .order_by(ConversationMessage.sequence_number)
        )
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return list(query.all())

    def update_status(self, session: LearningSession, status: str) -> LearningSession:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid session status: {status}")
        session.status = status
        if status in {"completed", "abandoned"}:
            session.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(session)
        return session

    def session_summary(self, session: LearningSession) -> dict:
        return {
            "xp_earned": session.xp_earned,
            "words_practiced": session.words_practiced,
            "accuracy_rate": session.accuracy_rate or 0.0,
            "new_words_introduced": session.new_words_introduced,
            "words_reviewed": session.words_reviewed,
            "correct_responses": session.correct_responses,
            "incorrect_responses": session.incorrect_responses,
            "status": session.status,
        }


__all__ = [
    "AssistantTurn",
    "SessionService",
    "SessionStartResult",
    "SessionTurnResult",
    "WordFeedback",
    "XPConfig",
]

