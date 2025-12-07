"""Service layer for orchestrating learning sessions."""
from __future__ import annotations

import csv
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
from typing import Sequence, TYPE_CHECKING

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.core.conversation import (
    ConversationGenerator,
    ConversationHistoryMessage,
    ConversationPlan,
    GeneratedTurn,
    TargetWord,
)
from app.core.error_detection import ErrorDetectionResult, ErrorDetector
from app.core.error_detection.rules import DetectedError
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import ConversationMessage, LearningSession, WordInteraction
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.achievement import AchievementService
from app.services.llm_service import LLMResult, LLMService
from app.services.progress import ProgressService
from app.utils.cache import cache_backend, build_cache_key
from app.schemas import PracticeIssue, TargetWordRead

if TYPE_CHECKING:
    from spacy.language import Language


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
    difficulty: float = 1.0


@dataclass(slots=True)
class AssistantTurn:
    """Persisted assistant message paired with the generation plan."""

    message: ConversationMessage
    plan: ConversationPlan
    llm_result: LLMResult
    target_details: list[TargetWordRead] | None = None


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
    COMMON_STOPWORDS = {
        "le",
        "la",
        "les",
        "de",
        "des",
        "du",
        "un",
        "une",
        "et",
        "a",
        "au",
        "aux",
        "en",
        "dans",
        "que",
        "qui",
        "ce",
        "cet",
        "cette",
        "pour",
    }

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
                try:
                    self.nlp = spacy.load(settings.FRENCH_NLP_MODEL)
                except Exception:
                    self.nlp = spacy.blank("fr")
            except Exception as e:
                # Fallback for when spacy import itself fails (e.g. pydantic conflict)
                class DummyDoc:
                    def __iter__(self): return iter([])
                    def __len__(self): return 0
                class DummyNLP:
                    def __call__(self, text): return DummyDoc()
                self.nlp = DummyNLP()
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

    def _ensure_vocabulary_seeded(self) -> None:
        existing_count = self.db.query(VocabularyWord.id).count()
        minimum_required = 50
        if existing_count >= minimum_required:
            return
        existing_ids = {
            row[0] for row in self.db.query(VocabularyWord.id).all()
        }
        sample_path = Path(__file__).resolve().parents[2] / "vocabulary_fr_sample.csv"
        if not sample_path.exists():
            logger.warning("Vocabulary sample file missing", path=str(sample_path))
            return

        with sample_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            records: list[VocabularyWord] = []
            for row in reader:
                try:
                    word = VocabularyWord(
                        id=int(row["rank"]),
                        language="fr",
                        word=row["word"],
                        normalized_word=row["word"].lower(),
                        part_of_speech=row.get("part_of_speech"),
                        gender=row.get("gender"),
                        frequency_rank=int(row["rank"]),
                        english_translation=row.get("translation"),
                        definition=row.get("definition"),
                        example_sentence=row.get("example"),
                        example_translation=row.get("example_translation"),
                        usage_notes=None,
                        difficulty_level=1,
                        topic_tags=[tag.strip() for tag in (row.get("topics") or "").split(";") if tag.strip()],
                    )
                    records.append(word)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to seed vocabulary word", row=row, error=str(exc))
            if records:
                filtered: list[VocabularyWord] = []
                for word in records:
                    if word.id in existing_ids:
                        continue
                    filtered.append(word)
                if not filtered:
                    logger.info("No new vocabulary words to seed from sample")
                    return
                logger.info("Seeding vocabulary sample", count=len(filtered))
                self.db.bulk_save_objects(filtered, return_defaults=False)
                self.db.commit()
                self.db.flush()

    def _invalidate_analytics_cache(self, user_id: User.id) -> None:
        prefix = f"{user_id}:"
        for namespace in (
            "analytics:summary",
            "analytics:statistics",
            "analytics:streak",
            "analytics:heatmap",
            "analytics:error_patterns",
        ):
            cache_backend.invalidate(namespace, prefix=prefix)

    def create_session(
        self,
        *,
        user: User,
        planned_duration_minutes: int,
        topic: str | None = None,
        conversation_style: str | None = None,
        difficulty_preference: str | None = None,
        generate_greeting: bool = True,
        anki_direction: str | None = None,
        scenario: str | None = None,
    ) -> SessionStartResult:
        """Create a new session and optionally bootstrap the greeting turn."""

        self._ensure_vocabulary_seeded()
        session_capacity = self._calculate_session_capacity(planned_duration_minutes)

        direction_choice = anki_direction if anki_direction in {"fr_to_de", "de_to_fr", "both"} else None

        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=planned_duration_minutes,
            topic=topic,
            conversation_style=conversation_style or "tutor",
            difficulty_preference=difficulty_preference,
            status="in_progress",
            level_before=user.level,
            level_after=user.level,
            anki_direction=direction_choice,
            scenario=scenario,
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
        self._invalidate_analytics_cache(user.id)
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
        """Return vocabulary entries the learner used without being prompted.

        Optimized to avoid N+1 queries by batching vocabulary lookups.
        """

        doc = self.nlp(learner_text)

        # Build a set of query terms and a surface-form map in one pass
        token_map: dict[str, str] = {}
        query_terms: set[str] = set()
        for token in doc:
            if token.is_stop or token.is_punct or token.is_space:
                continue

            lemma = token.lemma_.lower() if token.lemma_ else token.text.lower()
            text_lower = token.text.lower()

            # Only try to match words that our lemmatizer deemed relevant
            if lemma not in learner_lemmas and text_lower not in learner_lemmas:
                continue

            query_terms.add(lemma)
            query_terms.add(text_lower)
            token_map.setdefault(lemma, token.text)
            token_map.setdefault(text_lower, token.text)

        if not query_terms:
            return []

        # Single DB query for all potential matches
        target_lang = user.target_language or "fr"
        matched_vocab = (
            self.db.query(VocabularyWord)
            .filter(
                VocabularyWord.language == target_lang,
                or_(
                    VocabularyWord.normalized_word.in_(query_terms),
                    VocabularyWord.word.in_(query_terms),
                ),
            )
            .all()
        )

        unknown_words: list[tuple[VocabularyWord, str]] = []
        seen_ids: set[int] = set()
        for word in matched_vocab:
            if word.id in known_word_ids or word.id in seen_ids:
                continue
            surface = token_map.get(word.normalized_word) or token_map.get((word.word or "").lower())
            if surface:
                unknown_words.append((word, surface))
                seen_ids.add(word.id)

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
        user: User,
        user_message: ConversationMessage,
        learner_text: str,
        error_result: ErrorDetectionResult,
        previous_targets: list[tuple[VocabularyWord, bool]],
        learner_lemmas: set[str] | None = None,
    ) -> list[WordFeedback]:
        learner_lemmas = learner_lemmas or self._lemmatize_with_context(learner_text)
        feedback: list[WordFeedback] = []

        # Pre-fetch progress for difficulty calculation
        word_ids = [w.id for w, _ in previous_targets]
        progress_map = self._load_progress_map(user_id=user.id, word_ids=word_ids)

        for word, is_new in previous_targets:
            was_used, matched_form = self._check_word_usage(
                word, learner_text, learner_lemmas
            )
            matching_error: DetectedError | None = None
            if was_used and matched_form:
                # Check if the specific usage has an error associated with it
                for err in error_result.errors:
                    if matched_form in err.span:
                        matching_error = err
                        break

            rating = self._calculate_word_rating(
                was_used=was_used,
                is_new=is_new,
                had_error=matching_error is not None,
                error_severity=matching_error.severity if matching_error else None,
            )

            # Calculate difficulty multiplier
            difficulty_multiplier = 1.0
            progress = progress_map.get(word.id)
            if progress:
                if progress.scheduler == "anki":
                    # Anki: Lower ease factor = harder word (standard is 2.5)
                    if (progress.ease_factor or 2.5) < 2.0:
                        difficulty_multiplier = 1.5
                    elif (progress.ease_factor or 2.5) < 2.4:
                        difficulty_multiplier = 1.2
                else:
                    # FSRS: Higher difficulty = harder word (scale 1-10, default 5)
                    if (progress.difficulty or 5.0) > 7.0:
                        difficulty_multiplier = 1.5
                    elif (progress.difficulty or 5.0) > 5.5:
                        difficulty_multiplier = 1.2
            
            # Fallback to static difficulty if no progress or neutral stats
            if difficulty_multiplier == 1.0 and word.difficulty_level:
                difficulty_multiplier = self.xp_config.difficulty_multipliers.get(
                    word.difficulty_level, 1.0
                )

            feedback.append(
                WordFeedback(
                    word=word,
                    is_new=is_new,
                    was_used=was_used,
                    rating=rating,
                    had_error=matching_error is not None,
                    error=matching_error,
                    difficulty=difficulty_multiplier,
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
            progress.record_usage(correct=is_correct, is_new=item.is_new)

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

    def _calculate_xp(
        self,
        feedback: Sequence[WordFeedback],
        *,
        creative_count: int = 0,
        error_result: ErrorDetectionResult,
    ) -> int:
        xp = 5  # base engagement bonus
        suggested_used = [item for item in feedback if item.was_used]

        for item in suggested_used:
            if item.is_new:
                gain = 15 if not item.had_error else 5
            else:
                gain = 10 if not item.had_error else 4
            
            # Apply difficulty multiplier
            gain = int(gain * item.difficulty)
            
            xp += gain
            logger.debug(
                "XP for suggested word",
                word=item.word.word,
                is_new=item.is_new,
                had_error=item.had_error,
                difficulty_mult=item.difficulty,
                gained=gain,
            )

        if creative_count:
            creative_gain = creative_count * 8
            xp += creative_gain
            logger.debug(
                "XP for creative vocabulary",
                count=creative_count,
                gained=creative_gain,
            )

        if feedback:
            required = min(3, len(feedback))
            if len(suggested_used) >= required:
                xp += 5
            else:
                xp = max(0, xp - 5)

        # Combo Bonus: Award extra XP for using multiple target words in a single turn
        combo_count = len(suggested_used)
        if combo_count >= 2:
            combo_bonus = (combo_count - 1) * 10  # 10 XP for 2 words, 20 XP for 3 words, etc.
            xp += combo_bonus
            logger.debug(
                "XP for combo",
                combo_count=combo_count,
                bonus=combo_bonus,
            )

        if not error_result.errors:
            xp = int(xp * 1.5)

        return max(0, xp)

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
        cache_backend.invalidate("user:profile", key=build_cache_key(user_id=str(user.id)))

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

    def _load_progress_map(
        self,
        *,
        user_id: User.id,
        word_ids: Sequence[int],
    ) -> dict[int, UserVocabularyProgress]:
        unique_ids = {word_id for word_id in word_ids if word_id}
        if not unique_ids:
            return {}
        rows = (
            self.db.query(UserVocabularyProgress)
            .filter(
                UserVocabularyProgress.user_id == user_id,
                UserVocabularyProgress.word_id.in_(unique_ids),
            )
            .all()
        )
        return {row.word_id: row for row in rows}

    def _classify_familiarity(
        self,
        *,
        is_new: bool,
        progress: UserVocabularyProgress | None,
    ) -> str:
        if is_new:
            return "new"
        if progress and (progress.proficiency_score or 0) >= 70:
            return "familiar"
        return "learning"

    def _build_target_details_from_plan(
        self,
        *,
        user: User,
        targets: Sequence[TargetWord],
    ) -> list[TargetWordRead]:
        if not targets:
            return []
        word_ids = [target.id for target in targets]
        progress_map = self._load_progress_map(user_id=user.id, word_ids=word_ids)
        vocab_map = {
            word.id: word
            for word in self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
        }
        details: list[TargetWordRead] = []
        for target in targets:
            vocab = vocab_map.get(target.id)
            progress = progress_map.get(target.id)
            translation = (
                vocab.english_translation
                if vocab and vocab.english_translation
                else target.translation
            )
            hint_sentence = vocab.example_sentence if vocab else None
            hint_translation = None
            if vocab:
                if vocab.example_translation:
                    hint_translation = vocab.example_translation
                elif vocab.english_translation:
                    hint_translation = vocab.english_translation
            familiarity = self._classify_familiarity(is_new=target.is_new, progress=progress)
            word_text = vocab.word if vocab else target.surface
            details.append(
                TargetWordRead(
                    word_id=target.id,
                    word=word_text,
                    translation=translation,
                    is_new=target.is_new,
                    familiarity=familiarity,
                    hint_sentence=hint_sentence,
                    hint_translation=hint_translation,
                )
            )
        return details

    def build_message_target_map(
        self,
        *,
        user: User,
        message_ids: Sequence[UUID],
    ) -> dict[UUID, list[TargetWordRead]]:
        if not message_ids:
            return {}
        # Fetch assistant interactions
        interactions = (
            self.db.query(WordInteraction)
            .filter(WordInteraction.message_id.in_(message_ids))
            .filter(WordInteraction.interaction_type.in_(["target_new", "target_review"]))
            .all()
        )

        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.id.in_(message_ids))
            .all()
        )
        message_map = {m.id: m for m in messages}

        word_ids = {interaction.word_id for interaction in interactions}
        vocab_map = {
            word.id: word
            for word in self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
        }
        progress_map = self._load_progress_map(user_id=user.id, word_ids=word_ids)
        payload: dict[UUID, list[TargetWordRead]] = {}
        for interaction in interactions:
            vocab = vocab_map.get(interaction.word_id)
            progress = progress_map.get(interaction.word_id)
            is_new = interaction.interaction_type == "target_new"
            familiarity = self._classify_familiarity(is_new=is_new, progress=progress)
            hint_sentence = vocab.example_sentence if vocab else None
            hint_translation = None
            if vocab:
                if vocab.example_translation:
                    hint_translation = vocab.example_translation
                elif vocab.english_translation:
                    hint_translation = vocab.english_translation
            translation = vocab.english_translation if vocab else None
            word_text = vocab.word if vocab else ""
            item = TargetWordRead(
                word_id=interaction.word_id,
                word=word_text,
                translation=translation,
                is_new=is_new,
                familiarity=familiarity,
                hint_sentence=hint_sentence,
                hint_translation=hint_translation,
            )
            payload.setdefault(interaction.message_id, []).append(item)

        # Augment assistant messages with any vocabulary words present in text
        # (limited scan of top-frequency words to avoid heavy queries)
        extra_vocab = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.language == (user.target_language or "fr"))
            .filter(func.length(VocabularyWord.word) > 2)
            .filter(func.lower(VocabularyWord.word).notin_(self.COMMON_STOPWORDS))
            .order_by(func.random())
            .limit(800)
            .all()
        )
        for msg_id, message in message_map.items():
            if message.sender != "assistant" or not message.content:
                continue
            existing_ids = {d.word_id for d in payload.get(msg_id, [])}
            text_lower = message.content.lower()
            additions: list[TargetWordRead] = []
            for vocab in extra_vocab:
                if vocab.id in existing_ids:
                    continue
                w = vocab.word.lower()
                if w in self.COMMON_STOPWORDS:
                    continue
                if re.search(rf"\b{re.escape(w)}\b", text_lower):
                    progress = self.progress_service.get_progress(user_id=user.id, word_id=vocab.id)
                    familiarity = self._classify_familiarity(is_new=(progress is None), progress=progress)
                    additions.append(
                        TargetWordRead(
                            word_id=vocab.id,
                            word=vocab.word,
                            translation=vocab.english_translation,
                            is_new=progress is None,
                            familiarity=familiarity,
                            hint_sentence=vocab.example_sentence,
                            hint_translation=vocab.example_translation or vocab.english_translation,
                        )
                    )
            if additions:
                payload.setdefault(msg_id, []).extend(additions)

        return payload

    def _compute_review_focus(self, *, session: LearningSession, user: User) -> float | None:
        preference = (session.difficulty_preference or "").lower()
        mapping = {
            "review": 0.85,
            "balanced": 0.6,
            "new": 0.35,
        }
        return mapping.get(preference)

    def _build_target_details_from_ids(
        self,
        *,
        user: User,
        word_ids: Sequence[int],
    ) -> list[TargetWordRead]:
        unique_ids = [word_id for word_id in dict.fromkeys(word_ids) if word_id]
        if not unique_ids:
            return []
        vocab_map = {
            word.id: word
            for word in self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(unique_ids)).all()
        }
        progress_map = self._load_progress_map(user_id=user.id, word_ids=unique_ids)
        details: list[TargetWordRead] = []
        for word_id in unique_ids:
            vocab = vocab_map.get(word_id)
            progress = progress_map.get(word_id)
            is_new = not progress or (progress.reps or 0) == 0
            familiarity = self._classify_familiarity(is_new=is_new, progress=progress)
            hint_sentence = vocab.example_sentence if vocab else None
            hint_translation = None
            if vocab:
                if vocab.example_translation:
                    hint_translation = vocab.example_translation
                elif vocab.english_translation:
                    hint_translation = vocab.english_translation
            translation = vocab.english_translation if vocab else None
            word_text = vocab.word if vocab else ""
            details.append(
                TargetWordRead(
                    word_id=word_id,
                    word=word_text,
                    translation=translation,
                    is_new=is_new,
                    familiarity=familiarity,
                    hint_sentence=hint_sentence,
                    hint_translation=hint_translation,
                )
            )
        return details

    def record_word_exposure(
        self,
        *,
        session: LearningSession,
        user: User,
        word_id: int,
        exposure_type: str,
    ) -> None:
        exposure_key = exposure_type if exposure_type in {"hint", "translation"} else "hint"
        vocab = self.db.get(VocabularyWord, word_id)
        if not vocab:
            return
        interaction = WordInteraction(
            session_id=session.id,
            user_id=user.id,
            word_id=word_id,
            interaction_type=f"exposure_{exposure_key}",
            was_suggested=False,
        )
        self.db.add(interaction)

        progress = self.progress_service.get_or_create_progress(user_id=user.id, word_id=word_id)
        penalty = -5 if exposure_key == "translation" else -3
        progress.hint_count = (progress.hint_count or 0) + 1
        progress.times_seen = (progress.times_seen or 0) + 1
        progress.adjust_proficiency(penalty)
        now = datetime.now(timezone.utc)
        progress.next_review_date = now
        progress.due_date = now.date()

        self.db.commit()
        self._invalidate_analytics_cache(user.id)

    def mark_word_difficult(
        self,
        *,
        session: LearningSession,
        user: User,
        word_id: int,
        reason: str | None = None,
    ) -> None:
        vocab = self.db.get(VocabularyWord, word_id)
        if not vocab:
            return
        progress = self.progress_service.get_or_create_progress(user_id=user.id, word_id=word_id)
        if (progress.difficulty or 0) < 5.0:
            progress.difficulty = 5.0
        progress.state = "learning"
        progress.adjust_proficiency(-20)
        now = datetime.now(timezone.utc)
        progress.next_review_date = now
        progress.due_date = now.date()
        progress.updated_at = now

        if reason != "summary":
            interaction = WordInteraction(
                session_id=session.id,
                user_id=user.id,
                word_id=word_id,
                interaction_type="flag_difficult",
                context_sentence=None,
                was_suggested=True,
                error_type=reason,
            )
            self.db.add(interaction)
        self.db.commit()
        self._invalidate_analytics_cache(user.id)

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
        exclude_word_ids: Sequence[int] | None = None,
    ) -> AssistantTurn:
        review_focus = self._compute_review_focus(session=session, user=user)
        exclude_set: set[int] = set()
        if exclude_word_ids:
            for word_id in exclude_word_ids:
                try:
                    exclude_set.add(int(word_id))
                except (TypeError, ValueError):
                    logger.debug("Skipping non-numeric exclude id", value=word_id)
        direction_pref = getattr(session, "anki_direction", None)
        if direction_pref not in {"fr_to_de", "de_to_fr"}:
            direction_pref = None
        generated = self.conversation_generator.generate_turn_with_context(
            user=user,
            learner_level=user.proficiency_level or "B1",
            style=session.conversation_style or "tutor",
            session_capacity=session_capacity,
            history=history,
            review_focus=review_focus,
            topic=session.topic,
            exclude_ids=exclude_set,
            anki_direction=direction_pref,
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
                user_id=user.id,
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
            review_focus=review_focus,
        )
        target_details = None
        if generated.plan.target_words:
            target_details = self._build_target_details_from_plan(
                user=user,
                targets=generated.plan.target_words,
            )
        return AssistantTurn(
            message=message,
            plan=generated.plan,
            llm_result=generated.llm_result,
            target_details=target_details,
        )

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
            user=user,
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
            progress.record_usage(correct=rating >= 2, is_new=False)

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

        xp_awarded = self._calculate_xp(feedback, creative_count=len(processed_spontaneous), error_result=error_result)
        user_message.xp_earned = xp_awarded
        self._refresh_session_stats(session=session, feedback=feedback, xp_awarded=xp_awarded)
        self._apply_user_xp(user, session, xp_awarded)

        history.append(ConversationHistoryMessage(role="user", content=content))
        used_target_ids = {item.word.id for item in feedback if item.was_used}
        exclude_ids: set[int] = set()
        if suggested_word_ids:
            for word_id in suggested_word_ids:
                try:
                    exclude_ids.add(int(word_id))
                except (TypeError, ValueError):
                    logger.debug("Skipping non-numeric suggested id", value=word_id)
        exclude_ids.update(used_target_ids)

        assistant_turn = self._generate_and_persist_assistant_turn_with_context(
            session=session,
            user=user,
            history=history,
            session_capacity=session_capacity,
            exclude_word_ids=exclude_ids,
        )

        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(assistant_turn.message)
        self.db.refresh(session)
        self.db.refresh(user)
        self._invalidate_analytics_cache(user.id)

        self._trigger_achievement_check(user)

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

    def _trigger_achievement_check(self, user: User) -> None:
        """Trigger achievement evaluation for the learner."""

        try:
            achievement_service = AchievementService(self.db)
            newly_unlocked = achievement_service.check_and_unlock(user=user)
            if newly_unlocked:
                logger.info(
                    "Achievements unlocked",
                    user_id=str(user.id),
                    count=len(newly_unlocked),
                    achievements=[item.achievement_key for item in newly_unlocked],
                )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "Achievement check failed",
                user_id=str(user.id),
                error=str(exc),
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

    def list_sessions(
        self,
        *,
        user: User,
        limit: int = 20,
        offset: int = 0,
    ) -> list[LearningSession]:
        query = (
            self.db.query(LearningSession)
            .filter(LearningSession.user_id == user.id)
            .order_by(LearningSession.started_at.desc())
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
        self._invalidate_analytics_cache(session.user_id)
        return session

    def session_summary(self, session: LearningSession) -> dict:
        user = session.user or self.db.get(User, session.user_id)
        interactions = (
            self.db.query(WordInteraction)
            .filter(WordInteraction.session_id == session.id)
            .order_by(WordInteraction.created_at)
            .all()
        )
        messages = (
            self.db.query(ConversationMessage)
            .filter(ConversationMessage.session_id == session.id)
            .all()
        )
        message_map = {message.id: message.content for message in messages}
        success_examples: list[dict] = []
        error_examples: list[dict] = []
        flashcard_word_ids: set[int] = set()

        vocab_map: dict[int, VocabularyWord] = {}
        if interactions:
            word_ids = {interaction.word_id for interaction in interactions}
            vocab_map = {
                word.id: word
                for word in self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
            }

        for interaction in interactions:
            vocab = vocab_map.get(interaction.word_id)
            word_text = vocab.word if vocab else ""
            translation = vocab.english_translation if vocab else None

            if (
                interaction.interaction_type == "learner_use"
                and not interaction.error_type
                and len(success_examples) < 3
            ):
                success_examples.append(
                    {
                        "word": word_text,
                        "translation": translation,
                        "sentence": interaction.user_response,
                    }
                )

            if interaction.error_type and len(error_examples) < 5:
                error_examples.append(
                    {
                        "word": word_text,
                        "issue": interaction.error_description or interaction.error_type,
                        "correction": interaction.correction,
                        "category": interaction.error_type,
                    }
                )
                flashcard_word_ids.add(interaction.word_id)

            if interaction.interaction_type in {"learner_skip", "exposure_hint", "exposure_translation"}:
                flashcard_word_ids.add(interaction.word_id)

        practice_items: list[PracticeIssue] = []
        seen_practice: set[tuple] = set()
        difficult_ids: set[int] = set()
        for interaction in interactions:
            if not interaction.error_type or interaction.error_type == "flag":
                continue
            vocab = vocab_map.get(interaction.word_id)
            sentence = message_map.get(interaction.message_id) if interaction.message_id else None
            key = (interaction.word_id, interaction.error_type, interaction.error_description)
            if key in seen_practice:
                continue
            seen_practice.add(key)
            practice_items.append(
                PracticeIssue(
                    word=vocab.word if vocab else interaction.error_type,
                    translation=vocab.english_translation if vocab else None,
                    category=interaction.error_type,
                    issue=interaction.error_description,
                    correction=interaction.correction,
                    sentence=sentence,
                )
            )
            difficult_ids.add(interaction.word_id)

        # Include errors detected but not tied to vocab words
        for message in messages:
            payload = message.errors_detected or {}
            for error in payload.get("errors", []):
                key = (error.get("span"), error.get("category"), error.get("message"))
                if key in seen_practice:
                    continue
                seen_practice.add(key)
                practice_items.append(
                    PracticeIssue(
                        word=error.get("span", ""),
                        translation=None,
                        category=error.get("category"),
                        issue=error.get("message"),
                        correction=error.get("suggestion"),
                        sentence=message.content,
                    )
                )

        flashcard_words: list[TargetWordRead] = []
        if user and (flashcard_word_ids or difficult_ids):
            combined_ids = list(flashcard_word_ids.union(difficult_ids))
            fl_detail = self._build_target_details_from_ids(user=user, word_ids=combined_ids)
            flashcard_words = fl_detail
            for word_detail in fl_detail:
                difficult_ids.add(word_detail.word_id)

        if user and difficult_ids:
            for word_id in difficult_ids:
                self.mark_word_difficult(session=session, user=user, word_id=word_id, reason="summary")

        return {
            "xp_earned": session.xp_earned,
            "words_practiced": session.words_practiced,
            "accuracy_rate": session.accuracy_rate or 0.0,
            "new_words_introduced": session.new_words_introduced,
            "words_reviewed": session.words_reviewed,
            "correct_responses": session.correct_responses,
            "incorrect_responses": session.incorrect_responses,
            "status": session.status,
            "success_examples": success_examples,
            "error_examples": error_examples,
            "flashcard_words": flashcard_words,
            "practice_items": practice_items,
        }


__all__ = [
    "AssistantTurn",
    "SessionService",
    "SessionStartResult",
    "SessionTurnResult",
    "WordFeedback",
    "XPConfig",
]
