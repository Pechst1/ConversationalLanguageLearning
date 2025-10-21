"""Service layer for orchestrating learning sessions."""
from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings

from app.core.conversation import ConversationGenerator, ConversationHistoryMessage, ConversationPlan
from app.core.error_detection import ErrorDetectionResult, ErrorDetector
from app.core.error_detection.rules import DetectedError
from app.db.models.session import ConversationMessage, LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.llm_service import LLMResult, LLMService
from app.services.progress import ProgressService

try:  # pragma: no cover - imported for typing
    from spacy.language import Language
except ImportError:  # pragma: no cover
    Language = object  # type: ignore[misc,assignment]


@dataclass(slots=True)
class XPConfig:
    """Configuration knobs for XP calculations."""

    base_message: int = 10
    correct_review: int = 15
    correct_new: int = 12
    partial_credit: int = 6
    difficulty_multipliers: dict[int, float] = field(
        default_factory=lambda: {1: 1.0, 2: 1.2, 3: 1.5, 4: 1.8, 5: 2.0}
    )


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
        nlp: Language | None = None,
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
        if nlp is None:
            try:
                import spacy

                self.nlp = spacy.load(settings.FRENCH_NLP_MODEL)
            except Exception:  # pragma: no cover - fallback if model missing
                import spacy

                self.nlp = spacy.blank("fr")
        else:
            self.nlp = nlp

    # ------------------------------------------------------------------
    # Session lifecycle helpers
    # ------------------------------------------------------------------
    def _calculate_session_capacity(self, planned_duration_minutes: int) -> dict[str, int]:
        """Estimate how many turns and target words to surface for a session."""

        minutes = max(planned_duration_minutes, 1)
        minutes_per_turn = 3.0
        estimated_turns = max(1, int(minutes / minutes_per_turn))

        if minutes <= 10:
            words_per_turn = 4
        elif minutes <= 20:
            words_per_turn = 6
        else:
            words_per_turn = 8

        total_capacity = estimated_turns * words_per_turn
        return {
            "estimated_turns": estimated_turns,
            "words_per_turn": words_per_turn,
            "total_capacity": total_capacity,
        }

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

        session_capacity = self._calculate_session_capacity(planned_duration_minutes)

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
            assistant_turn = self._generate_and_persist_assistant_turn_with_context(
                session=session,
                user=user,
                history=[],
                session_capacity=session_capacity,
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

    def _lemmatize_with_context(self, text: str) -> set[str]:
        """Return a set of lemmas and surface forms from the learner text."""

        doc = self.nlp(text)
        lemmas: set[str] = set()
        for token in doc:
            if token.lemma_:
                lemmas.add(token.lemma_.lower())
            lemmas.add(token.text.lower())
        return lemmas

    def _check_word_usage(
        self,
        target_word: VocabularyWord,
        learner_text: str,
        learner_lemmas: set[str],
    ) -> tuple[bool, str | None]:
        """Determine whether the learner used the target vocabulary word."""

        word_base = target_word.word.lower()
        word_normalized = _normalize_text(word_base)
        word_lemma = (target_word.normalized_word or target_word.word).lower()

        lower_text = learner_text.lower()
        if word_base in lower_text:
            return True, word_base

        normalized_text = _normalize_text(lower_text)
        if word_normalized in normalized_text:
            doc = self.nlp(learner_text)
            for token in doc:
                if _normalize_text(token.text.lower()) == word_normalized:
                    return True, token.text

        if word_lemma in learner_lemmas:
            doc = self.nlp(learner_text)
            for token in doc:
                if token.lemma_ and token.lemma_.lower() == word_lemma:
                    return True, token.text

        return False, None

    def _calculate_word_rating(
        self,
        *,
        was_used: bool,
        is_new: bool,
        had_error: bool,
        error_severity: str | None,
    ) -> int | None:
        """Map usage and error severity to an FSRS rating value."""

        if not was_used:
            if is_new:
                return None
            return 1

        if not had_error:
            return 3

        if error_severity == "low":
            return 2
        if error_severity == "medium":
            return 1
        return 0

    def _detect_unknown_words_used(
        self,
        learner_text: str,
        learner_lemmas: set[str],
        known_word_ids: set[int],
        user: User,
    ) -> list[tuple[VocabularyWord, str]]:
        """Return vocabulary entries the learner used without being prompted."""

        doc = self.nlp(learner_text)
        unknown_words: list[tuple[VocabularyWord, str]] = []
        for token in doc:
            if token.is_stop or token.is_punct or token.is_space:
                continue

            lemma = token.lemma_.lower() if token.lemma_ else token.text.lower()
            if lemma not in learner_lemmas and token.text.lower() not in learner_lemmas:
                continue
            vocab_word = (
                self.db.query(VocabularyWord)
                .filter(
                    VocabularyWord.language == user.target_language,
                    or_(
                        VocabularyWord.normalized_word == lemma,
                        VocabularyWord.word == token.text.lower(),
                    ),
                )
                .first()
            )
            if vocab_word and vocab_word.id not in known_word_ids:
                unknown_words.append((vocab_word, token.text))

        return unknown_words

    def _evaluate_unknown_word(
        self,
        word: VocabularyWord,
        matched_form: str,
        error_result: ErrorDetectionResult,
    ) -> tuple[int, int]:
        """Assign a rating and initial difficulty for spontaneous vocabulary usage."""

        matching_errors = [
            err
            for err in error_result.errors
            if matched_form.lower() in err.span.lower()
        ]

        if not matching_errors:
            return 3, 1

        severities = {err.severity for err in matching_errors}
        if "high" in severities:
            return 0, 5
        if "medium" in severities:
            return 1, 3
        return 2, 2

    def _determine_word_feedback(
        self,
        *,
        user_message: ConversationMessage,
        learner_text: str,
        error_result: ErrorDetectionResult,
        previous_targets: list[tuple[VocabularyWord, bool]],
        learner_lemmas: set[str] | None = None,
    ) -> list[WordFeedback]:
        learner_lemmas = learner_lemmas or self._lemmatize_with_context(learner_text)
        feedback: list[WordFeedback] = []

        for word, is_new in previous_targets:
            was_used, matched_form = self._check_word_usage(
                word, learner_text, learner_lemmas
            )
            matching_error: DetectedError | None = None
            if was_used and matched_form:
                for error in error_result.errors:
                    if matched_form.lower() in error.span.lower():
                        matching_error = error
                        break

            had_error = matching_error is not None
            rating = self._calculate_word_rating(
                was_used=was_used,
                is_new=is_new,
                had_error=had_error,
                error_severity=matching_error.severity if matching_error else None,
            )

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

            difficulty = item.word.difficulty_level or 1
            multiplier = self.xp_config.difficulty_multipliers.get(difficulty, 1.0)

            if item.rating and item.rating >= 3:
                base_xp = self.xp_config.correct_new if item.is_new else self.xp_config.correct_review
            elif item.rating and item.rating >= 2:
                base_xp = self.xp_config.partial_credit
            else:
                base_xp = 0

            scaled_xp = int(base_xp * multiplier)
            xp += scaled_xp

            logger.debug(
                "Word XP calculated",
                word=item.word.word,
                rating=item.rating,
                difficulty=difficulty,
                base=base_xp,
                multiplier=multiplier,
                scaled=scaled_xp,
            )
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
        session_capacity = self._calculate_session_capacity(session.planned_duration_minutes or 15)
        return self._generate_and_persist_assistant_turn_with_context(
            session=session,
            user=user,
            history=history,
            session_capacity=session_capacity,
        )

    def _generate_and_persist_assistant_turn_with_context(
        self,
        *,
        session: LearningSession,
        user: User,
        history: Sequence[ConversationHistoryMessage],
        session_capacity: dict[str, int],
    ) -> AssistantTurn:
        generated = self.conversation_generator.generate_turn_with_context(
            user=user,
            learner_level=user.proficiency_level or "B1",
            style=session.conversation_style or "tutor",
            session_capacity=session_capacity,
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

        session_capacity = self._calculate_session_capacity(session.planned_duration_minutes or 15)
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

        learner_lemmas = self._lemmatize_with_context(content)
        feedback = self._determine_word_feedback(
            user_message=user_message,
            learner_text=content,
            error_result=error_result,
            previous_targets=previous_targets,
            learner_lemmas=learner_lemmas,
        )

        self._apply_progress_updates(user=user, feedback=feedback)
        self._update_word_interactions(
            session=session,
            user=user,
            user_message=user_message,
            feedback=feedback,
            learner_text=content,
        )

        known_word_ids = {word.id for word, _ in previous_targets}
        unknown_words = self._detect_unknown_words_used(
            content,
            learner_lemmas,
            known_word_ids,
            user,
        )

        processed_spontaneous: set[int] = set()
        for vocab_word, matched_form in unknown_words:
            if vocab_word.id in processed_spontaneous:
                continue
            rating, suggested_difficulty = self._evaluate_unknown_word(
                vocab_word,
                matched_form,
                error_result,
            )

            progress = self.progress_service.get_or_create_progress(
                user_id=user.id,
                word_id=vocab_word.id,
            )
            if progress.reps == 0:
                progress.difficulty = float(suggested_difficulty)

            self.progress_service.record_review(
                user=user,
                word=vocab_word,
                rating=rating,
            )

            interaction = WordInteraction(
                session_id=session.id,
                user_id=user.id,
                word_id=vocab_word.id,
                message_id=user_message.id,
                interaction_type="spontaneous_use",
                user_response=content,
                was_suggested=False,
            )
            self.db.add(interaction)
            processed_spontaneous.add(vocab_word.id)

            logger.info(
                "User spontaneously used unknown word",
                word=vocab_word.word,
                rating=rating,
                difficulty=suggested_difficulty,
            )

        xp_awarded = self._calculate_xp(feedback)
        user_message.xp_earned = xp_awarded
        self._refresh_session_stats(session=session, feedback=feedback, xp_awarded=xp_awarded)
        self._apply_user_xp(user, session, xp_awarded)

        history.append(ConversationHistoryMessage(role="user", content=content))
        assistant_turn = self._generate_and_persist_assistant_turn_with_context(
            session=session,
            user=user,
            history=history,
            session_capacity=session_capacity,
        )

        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_turn.message)
        self.db.refresh(session)
        self.db.refresh(user)

        logger.info(
            "Message processed with adaptive features",
            session_id=str(session.id),
            words_used=len([fb for fb in feedback if fb.was_used]),
            spontaneous_words=len(processed_spontaneous),
            xp_awarded=xp_awarded,
        )

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

