"""Service layer for orchestrating learning sessions."""
from __future__ import annotations

import csv
import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
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
from app.db.models.error import UserError
from app.db.models.scenario import UserScenarioState
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.core.conversation.scenarios import get_scenario, Scenario
from app.services.achievement import AchievementService
from app.services.grammar import GrammarService
from app.services.llm_service import LLMResult, LLMService
from app.services.progress import ProgressService
from app.services.auto_context_service import SessionContext  # [NEW]
from app.utils.cache import cache_backend, build_cache_key
from app.schemas import PracticeIssue, TargetWordRead

if TYPE_CHECKING:
    from app.db.models.grammar import GrammarConcept, UserGrammarProgress
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
class ErrorStats:
    """Statistics for a specific error pattern from spaced repetition tracking."""

    category: str
    pattern: str | None
    total_occurrences: int
    occurrences_today: int
    last_seen: datetime | None
    next_review: datetime | None
    state: str


@dataclass(slots=True)
class SessionTurnResult:
    """Return payload after processing a learner message."""

    session: LearningSession
    user_message: ConversationMessage
    assistant_turn: AssistantTurn
    error_result: ErrorDetectionResult
    xp_awarded: int
    combo_count: int = 0
    word_feedback: list[WordFeedback] = field(default_factory=list)
    error_stats: list[ErrorStats] = field(default_factory=list)
    targeted_errors: list[UserError] = field(default_factory=list)


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
        session_context: SessionContext | None = None,  # [NEW]
    ) -> SessionStartResult:
        """Initialize a new learning session."""

        # If auto-context is provided, use its style if not explicitly overridden
        if session_context and not conversation_style:
            conversation_style = session_context.style

        scenario_context = None

        self._ensure_vocabulary_seeded()
        session_capacity = self._calculate_session_capacity(planned_duration_minutes)

        direction_choice = anki_direction if anki_direction in {"fr_to_de", "de_to_fr", "both"} else None

        scenario_def: Scenario | None = None
        if scenario:
            scenario_def = get_scenario(scenario)
            if scenario_def:
                topic = scenario_def.title
                # Initialize or fetch scenario state
                state = self.db.query(UserScenarioState).filter(
                    UserScenarioState.user_id == user.id,
                    UserScenarioState.scenario_id == scenario
                ).first()
                if not state:
                    state = UserScenarioState(user_id=user.id, scenario_id=scenario)
                    self.db.add(state)
                    self.db.commit()

        normalized_topic = topic.strip() if isinstance(topic, str) else None
        if normalized_topic:
            if len(normalized_topic) > 255:
                normalized_topic = normalized_topic[:252].rstrip() + "..."
        else:
            normalized_topic = None

        session = LearningSession(
            user_id=user.id,
            planned_duration_minutes=planned_duration_minutes,
            conversation_style=conversation_style,
            topic=normalized_topic,
            difficulty_preference=difficulty_preference,
            status="in_progress",
            level_before=user.level,
            level_after=user.level,
            anki_direction=direction_choice,
            scenario=scenario,  # Store ID in session
        )
        self.db.add(session)
        self.db.flush([session])

        assistant_turn: AssistantTurn | None = None
        if generate_greeting:
            due_errors = self._fetch_due_errors(user.id)
            due_grammar = self._fetch_due_grammar(user)
            assistant_turn = self._generate_and_persist_assistant_turn_with_context(
                session=session,
                user=user,
                history=[],
                session_capacity=session_capacity,
                due_errors=due_errors,
                due_grammar=due_grammar,
                scenario_context=scenario_context,
                session_context=session_context,  # [NEW]
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

    def _persist_errors(
        self,
        *,
        session: LearningSession,
        user: User,
        user_message: ConversationMessage,
        error_result: ErrorDetectionResult,
    ) -> None:
        """Persist detected errors to the UserError table with deduplication.
        
        If an error with the same category and pattern already exists for this user,
        we update that record (increment occurrences, increase difficulty) rather than
        creating a duplicate.
        
        Also updates the parent UserErrorConcept for concept-level SRS tracking.
        """
        # Import concept functions
        from app.core.error_concepts import get_concept_for_pattern, get_concept_for_category
        from app.db.models.error import UserErrorConcept
        
        # Track which concepts we've already updated this turn
        updated_concepts: set[str] = set()
        
        for error in error_result.errors:
            # Skip if low confidence
            if error.confidence < 0.6:
                continue
            
            # Check for existing error with same pattern
            existing = self.db.query(UserError).filter(
                UserError.user_id == user.id,
                UserError.error_category == error.category,
                UserError.error_pattern == error.code,
            ).first()
            
            if existing:
                # Update existing error - this is a repeated mistake
                existing.occurrences = (existing.occurrences or 1) + 1
                existing.lapses = (existing.lapses or 0) + 1
                existing.context_snippet = error.span  # Update to latest context
                existing.correction = error.suggestion  # Update to latest correction
                # Increase difficulty for repeated errors (max 10)
                existing.difficulty = min(10.0, (existing.difficulty or 5.0) + 0.5)
                # Schedule for immediate review (reset to learning state)
                existing.next_review_date = datetime.now(timezone.utc)
                if existing.state == "review" or existing.state == "mastered":
                    existing.state = "relearning"
                existing.updated_at = datetime.now(timezone.utc)
                
                logger.debug(
                    "Updated existing error",
                    category=error.category,
                    pattern=error.code,
                    occurrences=existing.occurrences,
                    lapses=existing.lapses,
                )
            else:
                # Create new error record
                user_error = UserError(
                    user_id=user.id,
                    session_id=session.id,
                    message_id=user_message.id,
                    error_category=error.category,
                    error_pattern=error.code,
                    subcategory=error.subcategory,
                    correction=error.suggestion,
                    context_snippet=error.span,
                    # Initialize SRS state
                    state="new",
                    stability=0.0,
                    difficulty=5.0,
                    occurrences=1,
                    next_review_date=datetime.now(timezone.utc),
                )
                self.db.add(user_error)
                
                logger.debug(
                    "Created new error record",
                    category=error.category,
                    pattern=error.code,
                )
            
            # Update parent concept (concept-level SRS)
            concept = get_concept_for_pattern(error.code)
            if not concept:
                concept = get_concept_for_category(error.category)
            
            if concept and concept.id not in updated_concepts:
                updated_concepts.add(concept.id)
                
                # Find or create the user's concept record
                user_concept = self.db.query(UserErrorConcept).filter(
                    UserErrorConcept.user_id == user.id,
                    UserErrorConcept.concept_id == concept.id,
                ).first()
                
                if user_concept:
                    user_concept.increment_occurrence()
                    logger.debug(
                        "Updated error concept",
                        concept=concept.id,
                        occurrences=user_concept.total_occurrences,
                    )
                else:
                    # Create new concept tracking record
                    user_concept = UserErrorConcept(
                        user_id=user.id,
                        concept_id=concept.id,
                        total_occurrences=1,
                        last_occurrence_date=datetime.now(timezone.utc),
                        next_review_date=datetime.now(timezone.utc),
                        state="new",
                    )
                    self.db.add(user_concept)
                    logger.debug(
                        "Created new error concept",
                        concept=concept.id,
                    )

    def _calculate_xp(
        self,
        feedback: Sequence[WordFeedback],
        *,
        creative_count: int = 0,
        error_result: ErrorDetectionResult,
    ) -> tuple[int, int]:
        """Calculate XP and combo count for this turn.
        
        Returns:
            tuple[int, int]: (xp_awarded, combo_count)
        """
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

        return max(0, xp), combo_count

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
        """Compute the review focus ratio based on session difficulty preference.
        
        Returns a ratio between 0.0 and 1.0 where:
        - 1.0 = 100% review words (no new words) - for review intensive mode
        - 0.0 = 100% new words (no reviews) - for new words only mode
        - 0.6 = balanced mix (default)
        """
        preference = (session.difficulty_preference or "").lower()
        mapping = {
            "review": 1.0,           # Review intensive: only review words
            "review_intensive": 1.0, # Same as review
            "balanced": 0.6,         # Default balanced mix
            "mixed": 0.6,            # Alias for balanced
            "new": 0.0,              # Only new words
            "new_only": 0.0,         # Alias for new
        }
        return mapping.get(preference)

    def _tokenize_for_engagement(self, text: str) -> list[str]:
        """Normalize and tokenize learner text for brevity/repetition heuristics."""
        normalized = _normalize_text(text or "")
        return re.findall(r"[a-z0-9']+", normalized)

    def _token_overlap(self, current_tokens: Sequence[str], previous_tokens: Sequence[str]) -> float:
        """Compute a lightweight token-overlap ratio between two turns."""
        current_set = set(current_tokens)
        previous_set = set(previous_tokens)
        if not current_set or not previous_set:
            return 0.0
        return len(current_set.intersection(previous_set)) / len(current_set.union(previous_set))

    def _resolve_cefr_level(self, learner_level: str | None) -> str:
        """Normalize learner level labels to CEFR buckets."""
        if not learner_level:
            return "A1"
        raw = learner_level.strip().upper().replace("_", "-")
        if raw in {"A1", "A2", "B1", "B2", "C1", "C2"}:
            return raw

        mapping = {
            "BEGINNER": "A1",
            "ELEMENTARY": "A2",
            "PRE-INTERMEDIATE": "A2",
            "INTERMEDIATE": "B1",
            "UPPER-INTERMEDIATE": "B2",
            "ADVANCED": "C1",
            "PROFICIENT": "C2",
        }
        return mapping.get(raw, "B1")

    def _grammar_challenge_hint(
        self,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None,
    ) -> str:
        """Build an instruction snippet tied to the top due grammar concept."""
        if not due_grammar:
            return ""
        concept, _ = due_grammar[0]
        if not concept:
            return ""
        return (
            f" Tie the task to this grammar concept from the grammar section: "
            f"'{concept.name}' ({concept.level})."
        )

    def _build_engagement_challenge(
        self,
        *,
        history: Sequence[ConversationHistoryMessage],
        learner_level: str | None,
        due_grammar: Sequence[tuple["GrammarConcept", "UserGrammarProgress | None"]] | None = None,
    ) -> str | None:
        """
        Return a targeted challenge when the learner is getting terse or repetitive.
        """
        cefr_level = self._resolve_cefr_level(learner_level)
        grammar_hint = self._grammar_challenge_hint(due_grammar)

        user_messages = [
            message.content.strip()
            for message in history
            if message.role == "user" and message.content and message.content.strip()
        ]
        if len(user_messages) < 2:
            return None

        recent_messages = user_messages[-3:]
        tokenized = [self._tokenize_for_engagement(text) for text in recent_messages]
        counts = [len(tokens) for tokens in tokenized]
        avg_words = (sum(counts) / len(counts)) if counts else 0.0

        last_tokens = tokenized[-1] if tokenized else []
        prev_tokens = tokenized[-2] if len(tokenized) > 1 else []

        overlap = self._token_overlap(last_tokens, prev_tokens)
        repeated_last_turn = bool(last_tokens and prev_tokens and last_tokens == prev_tokens)
        low_detail = len(last_tokens) <= 4 or avg_words <= 5.0
        repetitive = overlap >= 0.7 or repeated_last_turn
        low_variety = (
            len(last_tokens) >= 4
            and (len(set(last_tokens)) / max(1, len(last_tokens))) < 0.6
        )

        if not (low_detail or repetitive or low_variety):
            return None

        is_foundation_level = cefr_level in {"A1", "A2"}
        is_mid_level = cefr_level in {"B1", "B2"}

        if repetitive:
            if is_foundation_level:
                return (
                    "The learner is repeating themselves. Give a simple A/B choice and ask for exactly "
                    "2 short present-tense sentences with one connector (parce que)."
                    f"{grammar_hint}"
                )
            if is_mid_level:
                return (
                    "The learner is repeating themselves. Give an A/B position task and ask for 2-3 "
                    "sentences with one contrast connector (mais / cependant) and one reason."
                    f"{grammar_hint}"
                )
            return (
                "The learner is repeating themselves. Give a short argument task with a constrained stance, "
                "requiring 3 sentences: claim, counterpoint, and conclusion."
                f"{grammar_hint}"
            )
        if len(last_tokens) <= 2:
            if is_foundation_level:
                return (
                    "The learner response is very short. Ask for a 2-sentence response with one concrete "
                    "detail (time/place) and one reason using parce que."
                    f"{grammar_hint}"
                )
            if is_mid_level:
                return (
                    "The learner response is very short. Ask for 2-3 sentences including one personal "
                    "example, one reason, and one follow-up question."
                    f"{grammar_hint}"
                )
            return (
                "The learner response is very short. Ask for a compact 3-sentence response with a nuanced "
                "position and one supporting example."
                f"{grammar_hint}"
            )
        if is_foundation_level:
            return (
                "Increase specificity with a mini-task: require 2 clear sentences in present tense and "
                "one simple detail."
                f"{grammar_hint}"
            )
        if is_mid_level:
            return (
                "Increase specificity with a mini-task: require 2-3 complete sentences including one past "
                "or future reference plus a connector."
                f"{grammar_hint}"
            )
        return (
            "Increase specificity with a mini-task: require a brief structured answer with one hypothesis "
            "and one concrete example."
            f"{grammar_hint}"
        )

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
        due_errors: Sequence[UserError] | None = None,
        due_grammar: list | None = None,
        scenario_context: str | None = None,
        session_context: SessionContext | None = None,  # [NEW]
        engagement_challenge: str | None = None,
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
        # Fetch scenario state if applicable
        composed_context = scenario_context
        if session.scenario:
            state = self.db.query(UserScenarioState).filter(
                UserScenarioState.user_id == user.id,
                UserScenarioState.scenario_id == session.scenario
            ).first()
            if state:
                state_context = f"SCENARIO STATE: {state.state_data}\nCURRENT GOAL: {state.current_goal_index}"
                if composed_context:
                    composed_context += f"\n\n{state_context}"
                else:
                    composed_context = state_context

        # [NEW] Article Discussion Context
        if session.scenario and session.scenario.startswith("article:"):
            from app.db.models.story import Story
            story_id = session.scenario.split(":", 1)[1]
            story = self.db.query(Story).filter(Story.id == story_id).first()
            if story:
                text_parts = []
                # Collect text from all chapters/scenes
                # Import logic typically creates one chapter with sequential scenes
                sorted_chapters = sorted(story.chapters, key=lambda c: c.order_index)
                for ch in sorted_chapters:
                    sorted_scenes = sorted(ch.scenes, key=lambda s: s.order_index)
                    for scene in sorted_scenes:
                        # Prefer B1 level text if available, otherwise description
                        text_content = None
                        if scene.narration_variants:
                            # Try levels in order of likely availability
                            for level in ["B1", "B2", "A2", "C1", "default"]:
                                if level in scene.narration_variants:
                                    text_content = scene.narration_variants[level]
                                    break
                        
                        if not text_content:
                            text_content = scene.description
                        
                        if text_content:
                            text_parts.append(text_content)
                
                full_text = "\n\n".join(text_parts)
                # Limit length to avoid context overflow (approx 3000 chars)
                if len(full_text) > 3000:
                    full_text = full_text[:3000] + "... (truncated)"
                
                article_context = f"DISCUSSION SOURCE MATERIAL:\nTITLE: {story.title}\n\nCONTENT:\n{full_text}"
                
                if composed_context:
                    composed_context += f"\n\n{article_context}"
                else:
                    composed_context = article_context

        # Check time limit and inject wrap-up signal
        # Use started_at if available, otherwise fallback to created_at
        start_time = session.started_at or session.created_at
        if start_time and session.planned_duration_minutes:
            # Ensure awareness of timezone
            now = datetime.now(timezone.utc)
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            
            elapsed = (now - start_time).total_seconds() / 60.0
            remaining = session.planned_duration_minutes - elapsed
            
            # If less than 20% time remains or less than 1.5 minutes
            is_near_end = remaining <= 1.5 or (elapsed / session.planned_duration_minutes) > 0.85
            
            if is_near_end and remaining > -5.0:  # Don't nag if way overtime
                wrap_msg = (
                    f"TIME CHECK: {int(remaining)} minutes remaining. "
                    "Gradually wrap up the conversation. "
                    "Do not introduce complex new topics. "
                    "Find a natural stopping point soon."
                )
                if composed_context:
                    composed_context += f"\n\n{wrap_msg}"
                else:
                    composed_context = wrap_msg

        if engagement_challenge:
            challenge_context = (
                "ENGAGEMENT RESCUE:\n"
                f"- {engagement_challenge}\n"
                "- Keep tone friendly and lightweight; this should feel like a game, not a test."
            )
            if composed_context:
                composed_context += f"\n\n{challenge_context}"
            else:
                composed_context = challenge_context

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
            scenario=session.scenario,
            due_errors=due_errors,
            due_grammar=due_grammar,
            scenario_context=composed_context,
            session_context=session_context,  # [NEW]
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
        self._persist_errors(
            session=session,
            user=user,
            user_message=user_message,
            error_result=error_result,
        )

        # Update SRS for existing errors
        due_errors = self._fetch_due_errors(user.id, limit=10)
        due_grammar = self._fetch_due_grammar(user, limit=2)
        self._update_error_srs(
            user=user,
            due_errors=due_errors,
            detected_errors=error_result,
        )

        # Update Scenario Progress
        self._update_scenario_progress(
            session=session,
            user=user,
            content=content,
        )

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

        xp_awarded, combo_count = self._calculate_xp(feedback, creative_count=len(processed_spontaneous), error_result=error_result)
        user_message.xp_earned = xp_awarded
        self._refresh_session_stats(session=session, feedback=feedback, xp_awarded=xp_awarded)
        self._apply_user_xp(user, session, xp_awarded)

        history.append(ConversationHistoryMessage(role="user", content=content))
        engagement_challenge = self._build_engagement_challenge(
            history=history,
            learner_level=user.proficiency_level,
            due_grammar=due_grammar,
        )
        if engagement_challenge:
            logger.info(
                "Engagement challenge injected",
                session_id=str(session.id),
                user_id=str(user.id),
            )
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
            due_errors=due_errors,
            due_grammar=due_grammar,
            engagement_challenge=engagement_challenge,
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
            combo_count=combo_count,
        )

        # Gather error statistics for spaced repetition feedback
        error_stats = self._gather_error_stats(user, error_result)

        return SessionTurnResult(
            session=session,
            user_message=user_message,
            assistant_turn=assistant_turn,
            error_result=error_result,
            xp_awarded=xp_awarded,
            combo_count=combo_count,
            word_feedback=list(feedback),
            error_stats=error_stats,
            targeted_errors=list(due_errors),
        )

    def _update_error_srs(
        self,
        *,
        user: User,
        due_errors: Sequence[UserError],
        detected_errors: ErrorDetectionResult,
    ) -> None:
        """Update the spaced repetition state for errors based on recurrence."""
        if not due_errors:
            return

        detected_map = {
            (e.category, e.code): e for e in detected_errors.errors
        }

        now = datetime.now(timezone.utc)

        for error in due_errors:
            key = (error.error_category, error.error_pattern)
            recurrence = detected_map.get(key)

            if recurrence:
                # User made the mistake again (Fail)
                error.stability = max(0.0, (error.stability or 0.0) * 0.8)
                error.difficulty = min(10.0, (error.difficulty or 5.0) + 1.0)
                # Reset to short interval (e.g., 1 day)
                next_interval = 1
                error.state = "learning"
            else:
                # User did not make the mistake (Pass)
                # Simple exponential backoff
                error.stability = (error.stability or 0.0) + 1.0
                error.difficulty = max(1.0, (error.difficulty or 5.0) - 0.2)
                
                # Interval calculation (simplified FSRS-like)
                current_interval = (error.next_review_date - error.updated_at).days if error.updated_at else 1
                next_interval = max(1, int(current_interval * 2.5))
                error.state = "review"

            error.next_review_date = now + timedelta(days=next_interval)
            error.updated_at = now
            logger.info(
                "Updated error SRS",
                error_id=str(error.id),
                category=error.error_category,
                recurrence=bool(recurrence),
                next_interval=next_interval,
            )

    def _update_scenario_progress(
        self,
        *,
        session: LearningSession,
        user: User,
        content: str,
    ) -> None:
        """Check if the user has advanced the scenario state."""
        if not session.scenario:
            return

        scenario_def = get_scenario(session.scenario)
        if not scenario_def:
            return

        state = self.db.query(UserScenarioState).filter(
            UserScenarioState.user_id == user.id,
            UserScenarioState.scenario_id == session.scenario
        ).first()

        if not state or state.status == "completed":
            return

        current_goal_idx = state.current_goal_index
        if current_goal_idx >= len(scenario_def.goals):
            state.status = "completed"
            return

        current_goal = scenario_def.goals[current_goal_idx]
        
        # Heuristic check: Does the user's content seem to address the goal?
        # In a real system, we'd use an LLM classifier here.
        # For now, we'll use a simple keyword match or just assume progress if the turn was substantial.
        # Let's try a very lightweight LLM check if possible, otherwise fallback to length/turn count.
        
        # We'll use a simple heuristic: if the user message is > 5 words and no major errors, 
        # we assume they made an attempt. To be more robust, we'd ask the LLM.
        # Given we are already running an LLM for the response, let's assume the "Assistant" 
        # naturally guides them. We will increment the goal index every 2 user turns 
        # to simulate progression, unless we implement a specific checker.
        
        # BETTER: Let's use the LLM service to check.
        try:
            prompt = f"""
            Scenario: {scenario_def.title}
            Goal: {current_goal}
            User said: "{content}"
            
            Did the user achieve this goal? Reply YES or NO.
            """
            result = self.llm_service.generate_chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=5
            )
            if "YES" in result.content.upper():
                state.current_goal_index += 1
                if state.current_goal_index >= len(scenario_def.goals):
                    state.status = "completed"
                logger.info("Scenario goal achieved", goal=current_goal)
        except Exception:
            # Fallback: don't block flow
            pass

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

    def _fetch_due_errors(self, user_id: UUID, limit: int = 3) -> list[UserError]:
        """Retrieve errors due for review, prioritizing most problematic ones.
        
        Sorting priority:
        1. Lapses (descending) - errors the user keeps making
        2. Reps (descending) - the more attempts, the more persistent the issue
        3. Next review date (ascending) - most overdue first
        """
        now = datetime.now(timezone.utc)
        return (
            self.db.query(UserError)
            .filter(
                UserError.user_id == user_id,
                UserError.next_review_date <= now,
                UserError.state != "mastered"
            )
            .order_by(
                UserError.lapses.desc(),
                UserError.reps.desc(),
                UserError.next_review_date.asc()
            )
            .limit(limit)
            .all()
        )

    def _fetch_due_grammar(self, user: User, limit: int = 2) -> list:
        """Retrieve grammar concepts due for review to target in conversation.
        
        Returns a list of (GrammarConcept, UserGrammarProgress | None) tuples.
        These will be included in the LLM context to naturally incorporate
        grammar practice into the conversation.
        """
        grammar_service = GrammarService(self.db)
        return grammar_service.get_due_concepts(user=user, limit=limit)


    def _gather_error_stats(
        self,
        user: User,
        error_result: ErrorDetectionResult,
    ) -> list[ErrorStats]:
        """Gather statistics for detected errors for spaced repetition feedback."""
        if not error_result.errors:
            return []

        stats: list[ErrorStats] = []
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for error in error_result.errors:
            # Count total occurrences of this error pattern
            total_query = (
                self.db.query(func.count(UserError.id))
                .filter(
                    UserError.user_id == user.id,
                    UserError.error_category == error.category,
                )
            )
            if error.code:
                total_query = total_query.filter(UserError.error_pattern == error.code)
            total_occurrences = total_query.scalar() or 0

            # Count occurrences today
            today_query = (
                self.db.query(func.count(UserError.id))
                .filter(
                    UserError.user_id == user.id,
                    UserError.error_category == error.category,
                    UserError.created_at >= today_start,
                )
            )
            if error.code:
                today_query = today_query.filter(UserError.error_pattern == error.code)
            occurrences_today = today_query.scalar() or 0

            # Get the most recent occurrence for last_seen and next_review
            recent_error = (
                self.db.query(UserError)
                .filter(
                    UserError.user_id == user.id,
                    UserError.error_category == error.category,
                )
                .order_by(UserError.created_at.desc())
                .first()
            )

            last_seen = recent_error.created_at if recent_error else None
            next_review = recent_error.next_review_date if recent_error else None
            state = recent_error.state if recent_error else "new"

            # Add 1 and today +1 for the current error (not yet persisted)
            stats.append(
                ErrorStats(
                    category=error.category,
                    pattern=error.code,
                    total_occurrences=total_occurrences + 1,  # +1 for current
                    occurrences_today=occurrences_today + 1,  # +1 for current
                    last_seen=last_seen,
                    next_review=next_review,
                    state=state,
                )
            )

        return stats

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
