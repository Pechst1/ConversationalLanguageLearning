"""Unified SRS Service - combines vocab, grammar, and error items into single practice queue.

Research-backed design:
- Interleaving is the DEFAULT (superior for long-term retention)
- User can switch to blocked mode if preferred
- Priority based on overdue days + item fragility
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import and_, desc, not_, or_
from sqlalchemy.orm import Session

from app.core.srs.memory import Evidence, EvidenceFormat
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, GrammarConceptLocalization, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import UserConjugationProgress, VocabularyWord
from app.services.conjugation import DISPLAY_TENSES, ConjugationService
from app.services.enhanced_srs import EnhancedSRSService
from app.services.error_memory import ErrorMemoryService
from app.services.glosses import normalize_language, word_gloss
from app.services.grammar import GrammarService
from app.services.progress import (
    ProgressService,
    vocabulary_due_filter,
    vocabulary_progress_due_at,
)


class ItemType(StrEnum):
    VOCAB = "vocab"
    GRAMMAR = "grammar"
    ERROR = "error"
    CONJUGATION = "conjugation"


class InterleavingMode(StrEnum):
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
    ItemType.CONJUGATION: 20,  # Typed irregular form
}

# Base priority by type (errors are most urgent - fragile memory)
BASE_PRIORITY = {
    ItemType.ERROR: 30,
    ItemType.GRAMMAR: 20,
    ItemType.CONJUGATION: 15,
    ItemType.VOCAB: 10,
}

MASTERED_STATES = {"mastered", "gemeistert"}
TASK_COMPLIANCE = "task_compliance"
ERROR_SOURCE_LABELS = {
    "atelier": "Atelier",
    "mission": "Mission",
    "graphic_novel": "Feuilleton",
    "conversation": "Conversation",
    "audio": "Audio",
    "story": "Reading",
    "brief_exercise": "Exercise",
    # An unmapped source_type prints raw on the repair card; the daily journey
    # writes errata with source_type="daily_journey" (WP-05).
    "daily_journey": "Daily journey",
}

# Item types the daily journey can express as a typed learning target. A
# conjugation drill has no `TargetKind`, so it stays out of the journey pool
# and keeps its own schedule untouched.
JOURNEY_CANDIDATE_ITEM_TYPES = (ItemType.VOCAB, ItemType.GRAMMAR, ItemType.ERROR)

# ---------------------------------------------------------------------------
# WP-L3: the Rappel — one queue, interleaved
# ---------------------------------------------------------------------------

#: Seconds one interleaved Rappel item takes. A Rappel item is a single card or
#: prompt, not the 3-minute grammar drill `TIME_ESTIMATES` sizes for «Plus de
#: pratique»; the day planner budgets in these.
RAPPEL_ITEM_SECONDS: dict[ItemType, int] = {
    ItemType.VOCAB: 10,
    ItemType.GRAMMAR: 40,
    ItemType.ERROR: 25,
    ItemType.CONJUGATION: 20,
}

#: A Rappel block: this many consecutive items, drawn from at least
#: `RAPPEL_MIN_SOURCES` different sources whenever that many have items left.
RAPPEL_BLOCK_SIZE = 6
RAPPEL_MIN_SOURCES = 3

#: A concept's contrast partner comes back at least this often once both are
#: introduced (WP-L3). Partners are data (WP-L2); without them this is a no-op.
CONTRAST_WINDOW_DAYS = 7


def review_concept_key(item: DueLearningItem) -> str:
    """What "the same concept" means for the back-to-back rule.

    An erratum linked to a grammar concept *is* that concept (repairing «au le»
    right after the articles card is the same item twice); otherwise its linked
    word, otherwise itself.
    """

    metadata = item.metadata or {}
    if item.item_type == ItemType.GRAMMAR:
        return f"grammar:{metadata.get('concept_id') or item.original_id}"
    if item.item_type == ItemType.ERROR:
        if metadata.get("concept_id"):
            return f"grammar:{metadata['concept_id']}"
        if metadata.get("linked_word_id"):
            return f"word:{metadata['linked_word_id']}"
        return f"error:{item.original_id}"
    if item.item_type == ItemType.VOCAB:
        return f"word:{metadata.get('word_id') or item.original_id}"
    if item.item_type == ItemType.CONJUGATION:
        return f"conjugation:{metadata.get('normalized_lemma') or item.original_id}"
    return f"{item.item_type}:{item.id}"


def interleave_review_items(
    items: list[DueLearningItem],
    *,
    budget_seconds: int | None = None,
    block_size: int = RAPPEL_BLOCK_SIZE,
    min_sources: int = RAPPEL_MIN_SOURCES,
) -> list[DueLearningItem]:
    """Order review items into interleaved blocks, within a time budget.

    Greedy and deterministic. Inside each source the order is priority
    (highest first, stable). Each pick:

    1. while the current block has fewer than ``min_sources`` sources and a
       source not yet in it still has an item that fits, pick from those;
    2. never the same concept as the previous item (`review_concept_key`),
       unless nothing else fits;
    3. among the allowed items, the highest priority.

    ``budget_seconds`` stops the list when no remaining item fits; ``None`` is
    unlimited. An item that does not fit is skipped, a smaller one may follow.
    """

    pools: dict[ItemType, list[DueLearningItem]] = {}
    for item in sorted(items, key=lambda entry: entry.priority_score, reverse=True):
        pools.setdefault(item.item_type, []).append(item)
    remaining = None if budget_seconds is None else max(0, int(budget_seconds))

    def fits(item: DueLearningItem) -> bool:
        return remaining is None or int(item.estimated_seconds or 0) <= remaining

    def best(
        candidate_sources: list[ItemType], *, avoid_key: str | None
    ) -> DueLearningItem | None:
        chosen: DueLearningItem | None = None
        for source in candidate_sources:
            for item in pools[source]:
                if not fits(item):
                    continue
                if avoid_key is not None and review_concept_key(item) == avoid_key:
                    continue
                if chosen is None or item.priority_score > chosen.priority_score:
                    chosen = item
                break  # pools are priority-sorted: the first allowed is the best
        return chosen

    result: list[DueLearningItem] = []
    block_sources: set[ItemType] = set()
    block_len = 0
    last_key: str | None = None
    while True:
        available = [source for source, pool in pools.items() if any(fits(item) for item in pool)]
        if not available:
            break
        if block_len >= block_size:
            block_sources, block_len = set(), 0
        unused = [source for source in available if source not in block_sources]
        sources = unused if (len(block_sources) < min_sources and unused) else available

        pick = (
            best(sources, avoid_key=last_key)
            or best(available, avoid_key=last_key)
            or best(sources, avoid_key=None)
            or best(available, avoid_key=None)
        )
        if pick is None:  # pragma: no cover - `available` guarantees a fit
            break
        pools[pick.item_type].remove(pick)
        result.append(pick)
        block_sources.add(pick.item_type)
        block_len += 1
        last_key = review_concept_key(pick)
        if remaining is not None:
            remaining -= int(pick.estimated_seconds or 0)
    return result


def contrast_partner_refs(concept: GrammarConcept) -> list[int | str]:
    """A concept's contrast partners, as ids or external ids. ``[]`` when unknown.

    Read from a ``contrast_partners`` attribute when the catalogue has one
    (WP-L2), else from ``source_refs["contrast_partners"]``.
    """

    raw = getattr(concept, "contrast_partners", None)
    if raw is None:
        refs = getattr(concept, "source_refs", None)
        if isinstance(refs, dict):
            raw = refs.get("contrast_partners")
            if raw is None:
                # The v2 catalogue (WP-L2) keeps them in its syllabus block; missing
                # this made the forge never seat a contrast rule on v2.
                syllabus = refs.get("syllabus")
                raw = syllabus.get("contrast_partners") if isinstance(syllabus, dict) else None
    if not isinstance(raw, list | tuple):
        return []
    partners: list[int | str] = []
    for value in raw:
        if isinstance(value, int) and not isinstance(value, bool):
            partners.append(value)
        elif isinstance(value, str) and value.strip():
            partners.append(value.strip())
    return partners



class UnifiedSRSService:
    """Service for unified spaced repetition across all learning types."""
    
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def serialize_item(item: DueLearningItem) -> dict[str, Any]:
        """Return an API-safe dict for a unified queue item."""
        payload = asdict(item)
        payload["item_type"] = item.item_type.value
        if isinstance(item.original_id, UUID):
            payload["original_id"] = str(item.original_id)
        return payload
    
    def get_due_summary(self, user_id: UUID) -> DailyPracticeSummary:
        """Get summary of all due items for today."""
        now = datetime.now(UTC)
        today = now.date()
        target_language = self._target_language(user_id)

        vocab_due = self._due_vocab_query(user_id, today, now, target_language).count()
        grammar_due = self._due_grammar_query(user_id, now, target_language).count()
        errors_due = self._due_error_query(user_id, now).count()
        conjugation_due = self._due_conjugation_query(user_id, now).count()
        
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
            },
            "conjugation": {
                "due": conjugation_due,
                "new": 0,
                "minutes": round(conjugation_due * TIME_ESTIMATES[ItemType.CONJUGATION] / 60)
            }
        }
        
        total_due = vocab_due + grammar_due + errors_due + conjugation_due
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
        interleaving_mode: InterleavingMode = InterleavingMode.RANDOM,
    ) -> DailyPracticeSession:
        """
        Build prioritized practice queue.
        
        Priority algorithm:
        1. Overdue items (sorted by days overdue × fragility)
        2. Due today

        Only due reviews: new material is introduced by the daily journey and
        the Atelier, never by this queue (the old `new_*_limit` parameters were
        accepted and ignored, so they were removed in WP-L1).
        
        Returns queue that optionally fits within time budget.
        """
        now = datetime.now(UTC)
        today = now.date()
        target_language = self._target_language(user_id)
        
        items: list[DueLearningItem] = []
        
        # Fetch all due items
        items.extend(self._fetch_due_vocab(user_id, today, now, target_language))
        items.extend(self._fetch_due_grammar(user_id, now, target_language))
        items.extend(self._fetch_due_errors(user_id, now))
        items.extend(self._fetch_due_conjugations(user_id, now))
        
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

    def get_journey_candidate_pool(
        self,
        user_id: UUID,
        *,
        now: datetime | None = None,
        limit: int = 60,
    ) -> list[DueLearningItem]:
        """Read-only, priority-sorted pool of due vocab/grammar/error items.

        Added for WP-05's candidate adapter. It reuses the same due queries and
        the same `_calculate_priority` formula as `get_daily_practice_queue`,
        but skips the summary counts and the interleaving shuffle so the caller
        can rank by scenario relevance itself. It never writes and never moves a
        due date: an item this pool returns and the journey then omits stays
        exactly as due as it was.
        """

        now = now or datetime.now(UTC)
        today = now.date()
        target_language = self._target_language(user_id)

        items: list[DueLearningItem] = []
        items.extend(self._fetch_due_vocab(user_id, today, now, target_language))
        items.extend(self._fetch_due_grammar(user_id, now, target_language))
        items.extend(self._fetch_due_errors(user_id, now))

        items = [item for item in items if item.item_type in JOURNEY_CANDIDATE_ITEM_TYPES]
        for item in items:
            item.priority_score = self._calculate_priority(item)
        items.sort(key=lambda entry: entry.priority_score, reverse=True)
        return items[: max(1, limit)]

    def plan_review_items(
        self,
        user_id: UUID,
        *,
        budget_seconds: int,
        now: datetime | None = None,
    ) -> list[DueLearningItem]:
        """The day's Rappel: an ordered, interleaved list of review items.

        WP-L3's single source of review candidates for the day planner, «Encore
        5 minutes» and «Plus de pratique». Every due item of every source
        (vocabulary, grammar, errata, conjugation), ranked by the shared
        priority, plus the contrast partner of a due concept when both are
        introduced and the partner has not been seen for
        `CONTRAST_WINDOW_DAYS`; then `interleave_review_items` within
        ``budget_seconds`` (sized in `RAPPEL_ITEM_SECONDS`). Read-only.
        """

        now = now or datetime.now(UTC)
        today = now.date()
        target_language = self._target_language(user_id)
        items: list[DueLearningItem] = []
        items.extend(self._fetch_due_vocab(user_id, today, now, target_language))
        items.extend(self._fetch_due_grammar(user_id, now, target_language))
        items.extend(self._fetch_due_errors(user_id, now))
        items.extend(self._fetch_due_conjugations(user_id, now))
        for item in items:
            item.priority_score = self._calculate_priority(item)
        items.extend(self._contrast_partner_items(user_id, items, now, target_language))
        for item in items:
            item.estimated_seconds = RAPPEL_ITEM_SECONDS.get(item.item_type, item.estimated_seconds)
        return interleave_review_items(items, budget_seconds=budget_seconds)

    def _contrast_partner_items(
        self,
        user_id: UUID,
        items: list[DueLearningItem],
        now: datetime,
        target_language: str,
    ) -> list[DueLearningItem]:
        """Contrast partners owed a review this week. ``[]`` without partner data."""

        anchors = {
            int(item.metadata["concept_id"]): item
            for item in items
            if item.item_type == ItemType.GRAMMAR and item.metadata.get("concept_id")
        }
        if not anchors:
            return []
        partner_refs: dict[int, list[int | str]] = {}
        for concept in self.db.query(GrammarConcept).filter(GrammarConcept.id.in_(list(anchors))).all():
            refs = contrast_partner_refs(concept)
            if refs:
                partner_refs[concept.id] = refs
        if not partner_refs:
            return []
        ids = {ref for refs in partner_refs.values() for ref in refs if isinstance(ref, int)}
        external_ids = {ref for refs in partner_refs.values() for ref in refs if isinstance(ref, str)}
        filters = []
        if ids:
            filters.append(GrammarConcept.id.in_(ids))
        if external_ids:
            filters.append(GrammarConcept.external_id.in_(external_ids))
        rows = (
            self.db.query(UserGrammarProgress, GrammarConcept)
            .join(GrammarConcept, UserGrammarProgress.concept_id == GrammarConcept.id)
            .filter(
                UserGrammarProgress.user_id == user_id,
                GrammarConcept.active.is_(True),
                GrammarConcept.language == target_language,
                UserGrammarProgress.reps > 0,  # introduced
                or_(*filters),
            )
            .all()
        )
        by_ref: dict[int | str, tuple[UserGrammarProgress, GrammarConcept]] = {}
        for progress, concept in rows:
            by_ref[concept.id] = (progress, concept)
            if concept.external_id:
                by_ref[concept.external_id] = (progress, concept)
        window_start = now - timedelta(days=CONTRAST_WINDOW_DAYS)
        native_language = self._native_language(user_id)
        present = set(anchors)
        extra: list[DueLearningItem] = []
        for anchor_id, refs in partner_refs.items():
            for ref in refs:
                found = by_ref.get(ref)
                if found is None:
                    continue
                progress, concept = found
                if concept.id in present:
                    continue
                last = progress.last_review
                if last is not None and last.tzinfo is None:
                    last = last.replace(tzinfo=UTC)
                if last is not None and last >= window_start:
                    continue  # seen this week
                titles = self._concept_titles([concept.id], locales={"fr", native_language})
                item = self._grammar_item(progress, concept, titles, native_language, now)
                item.metadata["contrast_for"] = anchor_id
                item.priority_score = max(0.0, anchors[anchor_id].priority_score - 0.5)
                extra.append(item)
                present.add(concept.id)
        return extra

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
        if item_type == ItemType.CONJUGATION:
            return self._complete_conjugation_item(
                user_id=user_id,
                item_id=item_id,
                fsrs_rating=fsrs_rating,
                response_time_ms=response_time_ms,
            )

        raise ValueError(f"Unsupported item type: {item_type}")
    
    def _fetch_due_vocab(
        self, user_id: UUID, today: date, now: datetime, target_language: str
    ) -> list[DueLearningItem]:
        """Fetch vocabulary items due for review."""
        items = []
        
        progress_items = (
            self._due_vocab_query(user_id, today, now, target_language)
            .order_by(
                UserVocabularyProgress.due_at.asc().nullsfirst(),
                UserVocabularyProgress.next_review_date.asc().nullsfirst(),
                UserVocabularyProgress.due_date.asc().nullsfirst(),
                desc(UserVocabularyProgress.lapses),
            )
            .limit(100)
            .all()
        )
        
        for progress, word in progress_items:
            due_since = self._due_since_days(self._vocab_due_at(progress, now), now)
            translation = word_gloss(word, self._native_language(user_id))
            topic_tags = set(word.topic_tags or [])
            is_mission_phrase = "mission_phrase" in topic_tags
            
            items.append(DueLearningItem(
                id=f"vocab_{progress.id}",
                item_type=ItemType.VOCAB,
                priority_score=0,  # Calculated later
                display_title=word.word,
                display_subtitle="Mission phrase from Missions" if is_mission_phrase else "Vocabulary review",
                level="Mission phrase" if is_mission_phrase else (f"Diff {word.difficulty_level}" if word.difficulty_level else "—"),
                due_since_days=due_since,
                estimated_seconds=TIME_ESTIMATES[ItemType.VOCAB],
                original_id=progress.id,
                metadata={
                    "word_id": word.id,
                    "stability": progress.stability or 0,
                    "difficulty": progress.difficulty or 5,
                    "lapses": progress.lapses or 0,
                    "direction": word.direction,
                    "answer": translation,  # Hidden answer for reveal
                    "part_of_speech": getattr(word, 'part_of_speech', None),
                    "example_sentence": getattr(word, 'example_sentence', None),
                    "state": progress.state or "new",
                    "review_mode": "mission_phrase" if is_mission_phrase else "vocabulary",
                    "due_at": self._iso(progress.due_at),
                    "next_review_date": self._iso(progress.next_review_date),
                    "due_date": progress.due_date.isoformat() if progress.due_date else None,
                    # Both destinations must exist in the current product shell;
                    # /daily-practice is a retired home screen.
                    "route": "/vocabulary/review?focus=mission" if is_mission_phrase else f"/vocabulary?word={word.id}",
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
        now = datetime.now(UTC)
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
        now = datetime.now(UTC)
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
            # WP-L3: a self-rated Rappel card carries the learner's own rating.
            evidence=Evidence.rated(fsrs_rating),
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
        now = datetime.now(UTC)
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

        # WP-L3: errata are scheduled by the one memory model and keep the
        # retirement rule (three correct repairs on separate days); the ad-hoc
        # interval table that used to live here bypassed both.
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        ErrorMemoryService(self.db).review_error(
            user=user,
            error_id=error.id,
            rating=fsrs_rating + 1,
            repaired=fsrs_rating >= 2,
            now=now,
            evidence=Evidence.rated(fsrs_rating),
        )
        next_interval = int(error.scheduled_days or 1)

        if error.concept_id:
            self._credit_linked_grammar_from_error(
                user_id=user_id,
                concept_id=error.concept_id,
                fsrs_rating=fsrs_rating,
                error=error,
            )
        if error.linked_word_id:
            self._credit_linked_vocabulary_from_error(
                user_id=user_id,
                word_id=error.linked_word_id,
                fsrs_rating=fsrs_rating,
                now=now,
            )

        self.db.commit()
        self.db.refresh(error)
        return {
            "next_review_days": next_interval,
            "state": error.state,
            "message": f"Reviewed error: {error.error_category}",
        }

    def _complete_conjugation_item(
        self,
        *,
        user_id: UUID,
        item_id: str,
        fsrs_rating: int,
        response_time_ms: int | None = None,
    ) -> dict[str, Any]:
        """Complete an irregular conjugation review."""

        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        normalized, separator, tense = item_id.partition(":")
        if not separator:
            raise ValueError(f"Invalid conjugation item id: {item_id}")
        progress = (
            self.db.query(UserConjugationProgress)
            .filter(
                UserConjugationProgress.user_id == user_id,
                UserConjugationProgress.normalized_lemma == normalized,
                UserConjugationProgress.tense == tense,
            )
            .first()
        )
        lemma = progress.verb_lemma if progress else normalized
        updated = ConjugationService(self.db).review(
            user=user,
            lemma=lemma,
            tense=tense,
            rating=fsrs_rating,
            response_time_ms=response_time_ms,
        )
        next_review = updated.next_review_date
        next_review_days = (next_review.date() - datetime.now(UTC).date()).days if next_review else None
        return {
            "next_review_days": next_review_days,
            "state": updated.state,
            "message": f"Reviewed conjugation: {updated.verb_lemma} · {DISPLAY_TENSES.get(updated.tense, updated.tense)}",
        }
    
    def _fetch_due_grammar(
        self, user_id: UUID, now: datetime, target_language: str
    ) -> list[DueLearningItem]:
        """Fetch grammar concepts due for review."""
        items = []
        
        progress_items = (
            self._due_grammar_query(user_id, now, target_language)
            .order_by(
                UserGrammarProgress.next_review.asc().nullsfirst(),
                UserGrammarProgress.score.asc(),
                UserGrammarProgress.reps.asc(),
                GrammarConcept.difficulty_order.asc(),
            )
            .limit(50)
            .all()
        )
        # WP-L1: the catalogue `name` is English. The journey shows a grammar
        # target as a French chip with the learner's own-language title beside
        # it, so both localized titles travel in the metadata.
        native_language = self._native_language(user_id)
        titles = self._concept_titles(
            [concept.id for _progress, concept in progress_items],
            locales={"fr", native_language},
        )

        for progress, concept in progress_items:
            items.append(self._grammar_item(progress, concept, titles, native_language, now))

        return items

    def _grammar_item(
        self,
        progress: UserGrammarProgress,
        concept: GrammarConcept,
        titles: dict[int, dict[str, str]],
        native_language: str,
        now: datetime,
    ) -> DueLearningItem:
        due_since = self._due_since_days(progress.next_review, now)
        concept_titles = titles.get(concept.id, {})
        return DueLearningItem(
            id=f"grammar_{concept.id}",
            item_type=ItemType.GRAMMAR,
            priority_score=0,
            display_title=concept.name,
            display_subtitle=concept.category or "Grammar",
            level=concept.level or "—",
            due_since_days=due_since,
            estimated_seconds=TIME_ESTIMATES[ItemType.GRAMMAR],
            original_id=concept.id,
            metadata={
                "concept_id": concept.id,
                "external_id": concept.external_id,
                "category": concept.category,
                "subskill": concept.subskill,
                "score": progress.score,
                "state": progress.state,
                "reps": progress.reps,
                # WP-L3: the concept's memory, as vocabulary and errata carry it.
                "stability": float(progress.stability or 0.0),
                "difficulty": float(progress.difficulty or 5.0),
                "lapses": int(progress.lapses or 0),
                "title_fr": concept_titles.get("fr") or concept.name,
                "title_native": concept_titles.get(native_language) or concept.name,
                "review_mode": "grammar",
                "next_review": self._iso(progress.next_review),
                "route": f"/grammar?concept={concept.id}",
            },
        )

    def _fetch_due_errors(
        self, user_id: UUID, now: datetime
    ) -> list[DueLearningItem]:
        """Fetch conversation errors due for review."""
        items = []
        
        errors = (
            self._due_error_query(user_id, now)
            .order_by(
                UserError.lapses.desc(),
                UserError.occurrences.desc(),
                UserError.next_review_date.asc().nullsfirst(),
            )
            .limit(30)
            .all()
        )
        
        for error in errors:
            due_since = self._due_since_days(error.next_review_date, now)
            
            display_title = error.display_label or error.error_pattern or error.original_text or "Language repair"
            
            source_label = ERROR_SOURCE_LABELS.get(error.source_type or "", error.source_type or "Practice")
            review_mode = error.review_mode or "grammar"
            display_subtitle = f"{source_label} · {review_mode.replace('_', ' ')}"
            severity = self._error_severity(error)
            
            items.append(DueLearningItem(
                id=f"error_{error.id}",
                item_type=ItemType.ERROR,
                priority_score=0,
                display_title=display_title,
                display_subtitle=display_subtitle,
                level=f"{review_mode} · {error.occurrences or 1}×",
                due_since_days=due_since,
                estimated_seconds=TIME_ESTIMATES[ItemType.ERROR],
                original_id=error.id,
                metadata={
                    "concept_id": error.concept_id,
                    "linked_word_id": error.linked_word_id,
                    "stability": error.stability or 0,
                    "difficulty": error.difficulty or 5,
                    "lapses": error.lapses or 0,
                    "occurrences": error.occurrences or 1,
                    "severity": severity,
                    "original_text": error.original_text,
                    "correction": error.correction,
                    "context": error.context_snippet,
                    "why_wrong": error.why_wrong,
                    "repair_hint": error.repair_hint,
                    "display_label": error.display_label,
                    "task_error_type": error.task_error_type,
                    "error_category": error.error_category,
                    "subcategory": error.subcategory,
                    "review_mode": review_mode,
                    "source_type": error.source_type,
                    "source_label": source_label,
                    "next_review_date": self._iso(error.next_review_date),
                    "route": (
                        f"/grammar?concept={error.concept_id}"
                        if error.concept_id
                        else "/atelier"
                    ),
                }
            ))
        
        return items

    def _fetch_due_conjugations(self, user_id: UUID, now: datetime) -> list[DueLearningItem]:
        """Fetch irregular conjugation SRS items due for review."""

        items: list[DueLearningItem] = []
        rows = (
            self._due_conjugation_query(user_id, now)
            .order_by(
                UserConjugationProgress.next_review_date.asc().nullsfirst(),
                UserConjugationProgress.due_date.asc().nullsfirst(),
                UserConjugationProgress.lapses.desc(),
            )
            .limit(40)
            .all()
        )
        for progress in rows:
            due_at = progress.next_review_date
            if due_at is None and progress.due_date:
                due_at = datetime.combine(progress.due_date, time.min, tzinfo=UTC)
            due_since = self._due_since_days(due_at or now, now)
            tense_label = DISPLAY_TENSES.get(progress.tense, progress.tense)
            items.append(
                DueLearningItem(
                    id=f"conjugation_{progress.normalized_lemma}:{progress.tense}",
                    item_type=ItemType.CONJUGATION,
                    priority_score=0,
                    display_title=f"{progress.verb_lemma} · {tense_label}",
                    display_subtitle="Irregular conjugation drill",
                    level=progress.cefr_band or "A1",
                    due_since_days=due_since,
                    estimated_seconds=TIME_ESTIMATES[ItemType.CONJUGATION],
                    original_id=f"{progress.normalized_lemma}:{progress.tense}",
                    metadata={
                        "lemma": progress.verb_lemma,
                        "normalized_lemma": progress.normalized_lemma,
                        "tense": progress.tense,
                        "tense_label": tense_label,
                        "stability": progress.stability or 0,
                        "difficulty": progress.difficulty or 5,
                        "lapses": progress.lapses or 0,
                        "state": progress.state or "new",
                        "review_mode": "conjugation",
                        "route": "/vocabulary/conjugation",
                    },
                )
            )
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
        
        if item.item_type == ItemType.GRAMMAR:
            score = float(item.metadata.get("score") or 0)
            fragility_bonus = max(fragility_bonus, (10 - score) * 2)

        severity_bonus = 0
        if item.item_type == ItemType.ERROR:
            severity_bonus = min(int(item.metadata.get("severity") or 0) * 3, 12)

        lapse_bonus = min(item.metadata.get("lapses", 0) * 2, 10)
        
        priority = base + overdue_bonus + fragility_bonus + lapse_bonus + severity_bonus
        return min(priority, 100)  # Cap at 100
    
    def _interleave_random(self, items: list[DueLearningItem]) -> list[DueLearningItem]:
        """Interleave with the Rappel rules (WP-L3), without a budget.

        Research shows interleaving improves long-term retention by creating
        "desirable difficulty" and forcing discrimination between concepts.
        """
        return interleave_review_items(items)

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

    def _concept_titles(
        self, concept_ids: list[int], *, locales: set[str]
    ) -> dict[int, dict[str, str]]:
        """Localized concept titles, ``{concept_id: {locale: title}}``."""

        if not concept_ids:
            return {}
        rows = (
            self.db.query(GrammarConceptLocalization)
            .filter(
                GrammarConceptLocalization.concept_id.in_(concept_ids),
                GrammarConceptLocalization.locale.in_(sorted(locales)),
            )
            .all()
        )
        titles: dict[int, dict[str, str]] = {}
        for row in rows:
            if row.title:
                titles.setdefault(row.concept_id, {})[row.locale] = row.title
        return titles

    def _native_language(self, user_id: UUID) -> str:
        """The language this learner reads glosses in."""
        user = self.db.get(User, user_id)
        return normalize_language(getattr(user, "native_language", None))

    def _target_language(self, user_id: UUID) -> str:
        user = self.db.get(User, user_id)
        if not user:
            return "fr"
        return (user.target_language or "fr").strip() or "fr"

    def _due_vocab_query(
        self,
        user_id: UUID,
        today: date,
        now: datetime,
        target_language: str,
    ):
        return (
            self.db.query(UserVocabularyProgress, VocabularyWord)
            .join(VocabularyWord, UserVocabularyProgress.word_id == VocabularyWord.id)
            .filter(
                UserVocabularyProgress.user_id == user_id,
                VocabularyWord.language == target_language,
                vocabulary_due_filter(now),
            )
        )

    def _due_grammar_query(self, user_id: UUID, now: datetime, target_language: str):
        return (
            self.db.query(UserGrammarProgress, GrammarConcept)
            .join(GrammarConcept, UserGrammarProgress.concept_id == GrammarConcept.id)
            .filter(
                UserGrammarProgress.user_id == user_id,
                GrammarConcept.active.is_(True),
                GrammarConcept.language == target_language,
                # WP-L1: a mastered concept stays reviewable at its (long)
                # interval; only an unscheduled one is never pulled back in.
                or_(
                    UserGrammarProgress.next_review <= now,
                    and_(
                        UserGrammarProgress.next_review.is_(None),
                        or_(
                            UserGrammarProgress.state.is_(None),
                            not_(UserGrammarProgress.state.in_(MASTERED_STATES)),
                        ),
                    ),
                ),
            )
        )

    def _due_error_query(self, user_id: UUID, now: datetime):
        return self.db.query(UserError).filter(
            UserError.user_id == user_id,
            or_(UserError.state.is_(None), not_(UserError.state.in_(MASTERED_STATES))),
            or_(UserError.next_review_date <= now, UserError.next_review_date.is_(None)),
            or_(
                UserError.task_error_type.is_(None),
                UserError.task_error_type != TASK_COMPLIANCE,
                UserError.occurrences > 1,
                UserError.lapses > 0,
            ),
        )

    def _due_conjugation_query(self, user_id: UUID, now: datetime):
        today = now.date()
        return self.db.query(UserConjugationProgress).filter(
            UserConjugationProgress.user_id == user_id,
            or_(UserConjugationProgress.state.is_(None), not_(UserConjugationProgress.state.in_(MASTERED_STATES))),
            or_(
                UserConjugationProgress.next_review_date <= now,
                UserConjugationProgress.due_date <= today,
                and_(
                    UserConjugationProgress.next_review_date.is_(None),
                    UserConjugationProgress.due_date.is_(None),
                ),
            ),
        )

    @staticmethod
    def _vocab_due_at(progress: UserVocabularyProgress, now: datetime) -> datetime:
        return vocabulary_progress_due_at(progress) or now

    @staticmethod
    def _due_since_days(due_at: datetime | None, now: datetime) -> int:
        if due_at is None:
            return 0
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=UTC)
        return max(0, (now - due_at).days)

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    @staticmethod
    def _error_severity(error: UserError) -> int:
        metadata = error.error_metadata or {}
        severity = metadata.get("severity") if isinstance(metadata, dict) else None
        try:
            return max(1, min(4, int(severity)))
        except (TypeError, ValueError):
            if (error.lapses or 0) >= 2 or (error.occurrences or 0) >= 3:
                return 3
            return 2

    def _credit_linked_grammar_from_error(
        self,
        *,
        user_id: UUID,
        concept_id: int,
        fsrs_rating: int,
        error: UserError,
    ) -> None:
        user = self.db.get(User, user_id)
        if not user:
            return
        concept = self.db.get(GrammarConcept, concept_id)
        if not concept or not concept.active:
            return
        score_map = {0: 2.0, 1: 4.0, 2: 7.5, 3: 9.0}
        GrammarService(self.db).record_context_review(
            user=user,
            concept_id=concept_id,
            score=score_map[fsrs_rating],
            notes=error.display_label or error.task_error_type or "errata review",
            source="unified_srs",
            # An erratum repair is a transform of the learner's own line; «Bien»
            # is a repair with effort, «Facile» without.
            evidence=Evidence(
                EvidenceFormat.TRANSFORM,
                correct=fsrs_rating >= 2,
                assisted=fsrs_rating == 2,
            ),
        )

    def _credit_linked_vocabulary_from_error(
        self,
        *,
        user_id: UUID,
        word_id: int,
        fsrs_rating: int,
        now: datetime,
    ) -> None:
        word = self.db.get(VocabularyWord, word_id)
        if not word:
            return
        progress = ProgressService(self.db).get_or_create_progress(user_id=user_id, word_id=word_id)
        EnhancedSRSService(self.db).process_review(
            progress=progress,
            rating=fsrs_rating,
            response_time_ms=None,
            now=now,
        )


__all__ = [
    "UnifiedSRSService",
    "DueLearningItem", 
    "DailyPracticeSummary",
    "DailyPracticeSession",
    "ItemType",
    "InterleavingMode",
    "RAPPEL_ITEM_SECONDS",
    "contrast_partner_refs",
    "interleave_review_items",
    "review_concept_key",
]
