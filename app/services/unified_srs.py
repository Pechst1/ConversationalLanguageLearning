"""Unified SRS Service - combines vocab, grammar, and error items into single practice queue.

Research-backed design:
- Interleaving is the DEFAULT (superior for long-term retention)
- User can switch to blocked mode if preferred
- Priority based on overdue days + item fragility
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from typing import Any, Literal
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.enhanced_srs import EnhancedSRSService
from app.services.grammar import GrammarService


class ItemType(str, Enum):
    VOCAB = "vocab"
    GRAMMAR = "grammar"
    ERROR = "error"


class InterleavingMode(str, Enum):
    RANDOM = "random"  # Mix all types (research-recommended default)
    BLOCKS = "blocks"  # Complete one type before next
    PRIORITY = "priority"  # Strict priority order


@dataclass
class DueLearningItem:
    """Normalized representation of any learning item."""
    
    id: str
    item_type: ItemType
    priority_score: float  # 0-100, higher = more urgent
    display_title: str
    display_subtitle: str
    level: str  # A1-C2 or difficulty
    due_since_days: int  # Negative = future, 0 = today, positive = overdue
    estimated_seconds: int
    
    # Original data for routing to correct review component
    original_id: int | UUID = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyPracticeSummary:
    """Overview of today's practice workload."""
    
    total_due: int
    total_new: int
    estimated_minutes: int
    by_type: dict[str, dict[str, int]]  # {vocab: {due: 30, new: 5, minutes: 28}, ...}


@dataclass 
class DailyPracticeSession:
    """Complete session with queue and settings."""
    
    summary: DailyPracticeSummary
    queue: list[DueLearningItem]
    interleaving_mode: InterleavingMode
    time_budget_minutes: int | None  # None = unlimited


# Time estimates in seconds
TIME_ESTIMATES = {
    ItemType.VOCAB: 8,      # Quick flashcard
    ItemType.GRAMMAR: 180,  # 3 min for 9 exercises
    ItemType.ERROR: 15,     # Error review
}

# Base priority by type (errors are most urgent - fragile memory)
BASE_PRIORITY = {
    ItemType.ERROR: 30,
    ItemType.GRAMMAR: 20,
    ItemType.VOCAB: 10,
}


class UnifiedSRSService:
    """Service for unified spaced repetition across all learning types."""
    
    def __init__(self, db: Session) -> None:
        self.db = db
    
    def get_due_summary(self, user_id: UUID) -> DailyPracticeSummary:
        """Get summary of all due items for today."""
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Count vocab due
        vocab_due = self.db.query(UserVocabularyProgress).filter(
            UserVocabularyProgress.user_id == user_id,
            UserVocabularyProgress.due_date <= today
        ).count()
        
        # Count grammar due
        grammar_due = self.db.query(UserGrammarProgress).filter(
            UserGrammarProgress.user_id == user_id,
            or_(
                UserGrammarProgress.next_review <= now,
                UserGrammarProgress.next_review.is_(None)
            )
        ).count()
        
        # Count errors due
        errors_due = self.db.query(UserError).filter(
            UserError.user_id == user_id,
            or_(
                UserError.next_review_date <= now,
                UserError.next_review_date.is_(None)
            )
        ).count()
        
        by_type = {
            "vocab": {
                "due": vocab_due,
                "new": 0,  # TODO: track new items separately
                "minutes": round(vocab_due * TIME_ESTIMATES[ItemType.VOCAB] / 60)
            },
            "grammar": {
                "due": grammar_due,
                "new": 0,
                "minutes": round(grammar_due * TIME_ESTIMATES[ItemType.GRAMMAR] / 60)
            },
            "errors": {
                "due": errors_due,
                "new": 0,
                "minutes": round(errors_due * TIME_ESTIMATES[ItemType.ERROR] / 60)
            }
        }
        
        total_due = vocab_due + grammar_due + errors_due
        total_minutes = sum(t["minutes"] for t in by_type.values())
        
        return DailyPracticeSummary(
            total_due=total_due,
            total_new=0,
            estimated_minutes=total_minutes,
            by_type=by_type
        )
    
    def get_daily_practice_queue(
        self,
        user_id: UUID,
        time_budget_minutes: int | None = None,  # None = unlimited
        new_vocab_limit: int = 10,
        new_grammar_limit: int = 5,
        new_errors_limit: int = 0,  # Errors come from conversations
        interleaving_mode: InterleavingMode = InterleavingMode.RANDOM,
    ) -> DailyPracticeSession:
        """
        Build prioritized practice queue.
        
        Priority algorithm:
        1. Overdue items (sorted by days overdue × fragility)
        2. Due today 
        3. New items (up to daily limits)
        
        Returns queue that optionally fits within time budget.
        """
        now = datetime.now(timezone.utc)
        today = now.date()
        
        items: list[DueLearningItem] = []
        
        # Fetch all due items
        items.extend(self._fetch_due_vocab(user_id, today, now))
        items.extend(self._fetch_due_grammar(user_id, now))
        items.extend(self._fetch_due_errors(user_id, now))
        
        # Calculate priority scores
        for item in items:
            item.priority_score = self._calculate_priority(item)
        
        # Sort by priority (highest first)
        items.sort(key=lambda x: x.priority_score, reverse=True)
        
        # Apply interleaving mode
        if interleaving_mode == InterleavingMode.RANDOM:
            items = self._interleave_random(items)
        elif interleaving_mode == InterleavingMode.BLOCKS:
            pass  # Already sorted by priority within blocks
        
        # Apply time budget if specified
        if time_budget_minutes:
            items = self._apply_time_budget(items, time_budget_minutes * 60)
        
        summary = self.get_due_summary(user_id)
        
        return DailyPracticeSession(
            summary=summary,
            queue=items,
            interleaving_mode=interleaving_mode,
            time_budget_minutes=time_budget_minutes
        )

    def complete_item(
        self,
        *,
        user_id: UUID,
        item_type: ItemType,
        item_id: str,
        rating: int,
        response_time_ms: int | None = None,
    ) -> dict[str, Any]:
        """Persist completion for a daily-practice item and return scheduling info."""
        if rating < 1 or rating > 4:
            raise ValueError("rating must be between 1 and 4")

        fsrs_rating = rating - 1  # 0=Again, 1=Hard, 2=Good, 3=Easy

        if item_type == ItemType.VOCAB:
            return self._complete_vocab_item(
                user_id=user_id,
                progress_id=item_id,
                fsrs_rating=fsrs_rating,
                response_time_ms=response_time_ms,
            )
        if item_type == ItemType.GRAMMAR:
            return self._complete_grammar_item(
                user_id=user_id,
                concept_id=item_id,
                fsrs_rating=fsrs_rating,
            )
        if item_type == ItemType.ERROR:
            return self._complete_error_item(
                user_id=user_id,
                error_id=item_id,
                fsrs_rating=fsrs_rating,
            )

        raise ValueError(f"Unsupported item type: {item_type}")
    
    def _fetch_due_vocab(
        self, user_id: UUID, today, now: datetime
    ) -> list[DueLearningItem]:
        """Fetch vocabulary items due for review."""
        items = []
        
        progress_items = self.db.query(UserVocabularyProgress, VocabularyWord).join(
            VocabularyWord, UserVocabularyProgress.word_id == VocabularyWord.id
        ).filter(
            UserVocabularyProgress.user_id == user_id,
            UserVocabularyProgress.due_date <= today
        ).limit(100).all()
        
        for progress, word in progress_items:
            due_since = (today - progress.due_date).days if progress.due_date else 0
            translation = word.german_translation or word.english_translation or ""
            
            items.append(DueLearningItem(
                id=f"vocab_{progress.id}",
                item_type=ItemType.VOCAB,
                priority_score=0,  # Calculated later
                display_title=word.word,
                display_subtitle="Was bedeutet dieses Wort?",  # Prompt instead of answer
                level=f"Diff {word.difficulty_level}" if word.difficulty_level else "—",
                due_since_days=due_since,
                estimated_seconds=TIME_ESTIMATES[ItemType.VOCAB],
                original_id=progress.id,
                metadata={
                    "word_id": word.id,
                    "stability": progress.stability or 0,
                    "direction": word.direction,
                    "answer": translation,  # Hidden answer for reveal
                    "part_of_speech": getattr(word, 'part_of_speech', None),
                    "example_sentence": getattr(word, 'example_sentence', None),
                }
            ))
        
        return items

    def _complete_vocab_item(
        self,
        *,
        user_id: UUID,
        progress_id: str,
        fsrs_rating: int,
        response_time_ms: int | None = None,
    ) -> dict[str, Any]:
        """Complete a vocabulary review via the configured scheduler."""
        now = datetime.now(timezone.utc)
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        try:
            progress_uuid = UUID(progress_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid vocabulary progress id: {progress_id}") from exc

        progress = (
            self.db.query(UserVocabularyProgress)
            .filter(
                UserVocabularyProgress.id == progress_uuid,
                UserVocabularyProgress.user_id == user_id,
            )
            .first()
        )
        if not progress:
            raise ValueError(f"Vocabulary progress {progress_id} not found")
        if not progress.word:
            raise ValueError(f"Vocabulary word missing for progress {progress_id}")

        srs_service = EnhancedSRSService(self.db)
        srs_service.process_review(
            progress=progress,
            rating=fsrs_rating,
            response_time_ms=response_time_ms,
            now=now,
        )
        progress.updated_at = now
        self.db.commit()
        self.db.refresh(progress)

        next_review = progress.due_at or progress.next_review_date
        next_review_days = (next_review.date() - now.date()).days if next_review else None
        return {
            "next_review_days": next_review_days,
            "state": progress.state,
            "message": f"Reviewed vocabulary: {progress.word.word}",
        }

    def _complete_grammar_item(
        self,
        *,
        user_id: UUID,
        concept_id: str,
        fsrs_rating: int,
    ) -> dict[str, Any]:
        """Complete a grammar review by mapping rating to grammar score."""
        now = datetime.now(timezone.utc)
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        try:
            concept_id_int = int(concept_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid grammar concept id: {concept_id}") from exc

        grammar_service = GrammarService(self.db)
        concept = grammar_service.get_concept(concept_id_int)
        if not concept:
            raise ValueError(f"Grammar concept {concept_id_int} not found")

        score_map = {0: 1.0, 1: 4.0, 2: 7.0, 3: 9.5}
        progress = grammar_service.record_review(
            user=user,
            concept_id=concept_id_int,
            score=score_map[fsrs_rating],
            notes="daily_practice",
        )

        next_review = progress.next_review
        next_review_days = (next_review.date() - now.date()).days if next_review else None
        return {
            "next_review_days": next_review_days,
            "state": progress.state,
            "message": f"Reviewed grammar: {concept.name}",
        }

    def _complete_error_item(
        self,
        *,
        user_id: UUID,
        error_id: str,
        fsrs_rating: int,
    ) -> dict[str, Any]:
        """Complete an error-recall review and update the error SRS fields."""
        now = datetime.now(timezone.utc)
        try:
            error_uuid = UUID(error_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid error id: {error_id}") from exc
        error = (
            self.db.query(UserError)
            .filter(
                UserError.id == error_uuid,
                UserError.user_id == user_id,
            )
            .first()
        )
        if not error:
            raise ValueError(f"Error item {error_id} not found")

        current_interval = error.scheduled_days or 1
        difficulty = error.difficulty or 5.0
        stability = error.stability or 0.0

        if fsrs_rating == 0:  # Again
            next_interval = 1
            error.state = "learning"
            error.lapses = (error.lapses or 0) + 1
            difficulty = min(10.0, difficulty + 0.8)
            stability = max(0.0, stability * 0.8)
        elif fsrs_rating == 1:  # Hard
            next_interval = max(1, current_interval)
            error.state = "learning"
            difficulty = min(10.0, difficulty + 0.2)
            stability = max(0.0, stability + 0.3)
        elif fsrs_rating == 2:  # Good
            next_interval = max(2, int(current_interval * 2.0))
            error.state = "review"
            difficulty = max(1.0, difficulty - 0.2)
            stability = stability + 1.0
        else:  # Easy
            next_interval = max(4, int(current_interval * 3.0))
            error.state = "review"
            difficulty = max(1.0, difficulty - 0.4)
            stability = stability + 1.5

        error.stability = stability
        error.difficulty = difficulty
        error.elapsed_days = current_interval
        error.scheduled_days = next_interval
        error.reps = (error.reps or 0) + 1
        error.last_review_date = now
        error.next_review_date = now + timedelta(days=next_interval)
        error.updated_at = now

        self.db.commit()
        self.db.refresh(error)
        return {
            "next_review_days": next_interval,
            "state": error.state,
            "message": f"Reviewed error: {error.error_category}",
        }
    
    def _fetch_due_grammar(
        self, user_id: UUID, now: datetime
    ) -> list[DueLearningItem]:
        """Fetch grammar concepts due for review."""
        items = []
        
        progress_items = self.db.query(UserGrammarProgress, GrammarConcept).join(
            GrammarConcept, UserGrammarProgress.concept_id == GrammarConcept.id
        ).filter(
            UserGrammarProgress.user_id == user_id,
            or_(
                UserGrammarProgress.next_review <= now,
                UserGrammarProgress.next_review.is_(None)
            )
        ).limit(50).all()
        
        for progress, concept in progress_items:
            if progress.next_review:
                due_since = (now - progress.next_review).days
            else:
                due_since = 0  # New item
            
            items.append(DueLearningItem(
                id=f"grammar_{concept.id}",
                item_type=ItemType.GRAMMAR,
                priority_score=0,
                display_title=concept.name,
                display_subtitle=concept.category or "Grammatik",
                level=concept.level,
                due_since_days=due_since,
                estimated_seconds=TIME_ESTIMATES[ItemType.GRAMMAR],
                original_id=concept.id,
                metadata={
                    "score": progress.score,
                    "state": progress.state,
                    "reps": progress.reps
                }
            ))
        
        return items
    
    def _fetch_due_errors(
        self, user_id: UUID, now: datetime
    ) -> list[DueLearningItem]:
        """Fetch conversation errors due for review."""
        items = []
        
        errors = self.db.query(UserError).filter(
            UserError.user_id == user_id,
            or_(
                UserError.next_review_date <= now,
                UserError.next_review_date.is_(None)
            )
        ).order_by(
            UserError.lapses.desc(),  # Most lapsed first
            UserError.next_review_date.asc()
        ).limit(30).all()
        
        # Category labels for better display
        CATEGORY_LABELS = {
            "grammar": "Grammatikfehler",
            "spelling": "Rechtschreibfehler",
            "vocabulary": "Vokabelfehler",
            "gender": "Genusfehler",
            "conjugation": "Konjugationsfehler",
            "agreement": "Kongruenzfehler",
        }
        
        for error in errors:
            if error.next_review_date:
                due_since = (now - error.next_review_date).days
            else:
                due_since = 0
            
            # Build display title from original_text or fallback to category
            if error.original_text:
                display_title = f"❌ {error.original_text}"
            else:
                category_label = CATEGORY_LABELS.get(error.error_category, error.error_category or "Fehler")
                display_title = category_label
            
            # Build subtitle as hint about error type
            if error.subcategory:
                display_subtitle = f"Fehlertyp: {error.subcategory}"
            elif error.error_category:
                display_subtitle = CATEGORY_LABELS.get(error.error_category, error.error_category)
            else:
                display_subtitle = "Finde und korrigiere den Fehler"
            
            items.append(DueLearningItem(
                id=f"error_{error.id}",
                item_type=ItemType.ERROR,
                priority_score=0,
                display_title=display_title,
                display_subtitle=display_subtitle,
                level=f"Lapses: {error.lapses}",
                due_since_days=due_since,
                estimated_seconds=TIME_ESTIMATES[ItemType.ERROR],
                original_id=error.id,
                metadata={
                    "stability": error.stability or 0,
                    "difficulty": error.difficulty or 5,
                    "lapses": error.lapses or 0,
                    "original_text": error.original_text,
                    "correction": error.correction,
                    "context": error.context_snippet,
                    "error_category": error.error_category,
                    "subcategory": error.subcategory,
                }
            ))
        
        return items
    
    def _calculate_priority(self, item: DueLearningItem) -> float:
        """
        Calculate priority score (0-100).
        
        Formula:
        priority = base_type_priority + overdue_bonus + fragility_bonus
        
        - Base: errors (30) > grammar (20) > vocab (10)
        - Overdue: +3 points per day overdue
        - Fragility: low stability = higher priority
        """
        base = BASE_PRIORITY.get(item.item_type, 10)
        
        # Overdue bonus: +3 per day, capped at +30
        overdue_bonus = min(item.due_since_days * 3, 30) if item.due_since_days > 0 else 0
        
        # Fragility bonus based on stability (lower = more fragile = higher priority)
        stability = item.metadata.get("stability", 0)
        if stability > 0:
            fragility_bonus = max(0, 20 - stability)  # 0-20 points
        else:
            fragility_bonus = 10  # New items get medium boost
        
        # Lapse penalty for errors (more lapses = needs more attention)
        lapse_bonus = min(item.metadata.get("lapses", 0) * 2, 10)
        
        priority = base + overdue_bonus + fragility_bonus + lapse_bonus
        return min(priority, 100)  # Cap at 100
    
    def _interleave_random(self, items: list[DueLearningItem]) -> list[DueLearningItem]:
        """
        Interleave items from different types while respecting priority.
        
        Research shows interleaving improves long-term retention by:
        - Creating "desirable difficulty"
        - Forcing discrimination between concepts
        - Preventing blocked repetition fatigue
        """
        import random
        
        # Group by type
        by_type: dict[ItemType, list[DueLearningItem]] = {t: [] for t in ItemType}
        for item in items:
            by_type[item.item_type].append(item)
        
        # Build interleaved queue
        result = []
        type_cycle = list(ItemType)
        random.shuffle(type_cycle)
        
        while any(by_type.values()):
            for item_type in type_cycle:
                if by_type[item_type]:
                    result.append(by_type[item_type].pop(0))
        
        return result
    
    def _apply_time_budget(
        self, items: list[DueLearningItem], budget_seconds: int
    ) -> list[DueLearningItem]:
        """Filter queue to fit within time budget."""
        result = []
        total_time = 0
        
        for item in items:
            if total_time + item.estimated_seconds <= budget_seconds:
                result.append(item)
                total_time += item.estimated_seconds
            else:
                break  # Stop when budget exceeded
        
        logger.info(f"Applied time budget: {len(result)}/{len(items)} items fit in {budget_seconds}s")
        return result


__all__ = [
    "UnifiedSRSService",
    "DueLearningItem", 
    "DailyPracticeSummary",
    "DailyPracticeSession",
    "ItemType",
    "InterleavingMode",
]
