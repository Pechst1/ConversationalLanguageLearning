"""Business logic for learner vocabulary progress."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.schemas.anki import AnkiCardUpdate
from app.services.srs import FSRSScheduler, ReviewOutcome, SchedulerState
from app.utils.cache import cache_backend


@dataclass(slots=True)
class QueueItem:
    """Representation of a queue entry returned to the API."""

    word: VocabularyWord
    progress: UserVocabularyProgress | None
    is_new: bool


class ProgressService:
    """High level helper for vocabulary progress workflows."""

    def __init__(self, db: Session, *, scheduler: FSRSScheduler | None = None) -> None:
        self.db = db
        self.scheduler = scheduler or FSRSScheduler()

    @staticmethod
    def _queue_stopwords() -> set[str]:
        return {
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

    @staticmethod
    def _is_skippable_queue_word(word: str | None, *, stopwords: set[str]) -> bool:
        if not word:
            return True
        lowered = word.strip().lower()
        return len(lowered) <= 2 or lowered in stopwords

    @staticmethod
    def _shared_direction_filter(direction: str | None):
        if not direction:
            return None
        return or_(
            VocabularyWord.direction == direction,
            VocabularyWord.direction.is_(None),
        )

    @staticmethod
    def _shared_deck_filter(deck_name: str | None):
        if not deck_name:
            return None
        return VocabularyWord.deck_name == deck_name

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def _progress_query(self, user_id: User.id, word_id: int) -> select:
        return select(UserVocabularyProgress).where(
            and_(
                UserVocabularyProgress.user_id == user_id,
                UserVocabularyProgress.word_id == word_id,
            )
        )

    def get_progress(self, *, user_id: User.id, word_id: int) -> UserVocabularyProgress | None:
        """Return an existing progress row if present."""

        stmt = self._progress_query(user_id, word_id).options(joinedload(UserVocabularyProgress.word))
        return self.db.scalars(stmt).first()

    def get_or_create_progress(
        self, *, user_id: User.id, word_id: int
    ) -> UserVocabularyProgress:
        """Return an existing row or create a new one in-memory."""

        progress = self.db.scalars(self._progress_query(user_id, word_id)).first()
        if progress is None:
            progress = UserVocabularyProgress(user_id=user_id, word_id=word_id, state="new")
            self.db.add(progress)
            self.db.flush([progress])
            progress = self.db.get(UserVocabularyProgress, progress.id)
        return progress

    def get_learning_queue(
        self,
        *,
        user: User,
        limit: int,
        now: datetime | None = None,
        new_word_budget: int | None = None,
        exclude_ids: set[int] | None = None,
        direction: str | None = None,
        deck_name: str | None = None,
    ) -> list[QueueItem]:
        """Return due and new words for a learner."""

        now = now or datetime.now(timezone.utc)
        today = now.date()
        exclude_ids = exclude_ids or set()
        stopwords = self._queue_stopwords()
        target_language = (user.target_language or "fr").strip() or "fr"
        due_stmt = (
            select(UserVocabularyProgress)
            .options(joinedload(UserVocabularyProgress.word))
            .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
            .where(UserVocabularyProgress.user_id == user.id)
            .where(VocabularyWord.language == target_language)
            .where(
                or_(
                    UserVocabularyProgress.due_date.is_(None),
                    UserVocabularyProgress.due_date <= today,
                )
            )
        )
        direction_filter = self._shared_direction_filter(direction)
        deck_filter = self._shared_deck_filter(deck_name)
        if direction_filter is not None:
            due_stmt = due_stmt.where(direction_filter)
        if deck_filter is not None:
            due_stmt = due_stmt.where(deck_filter)
        due_stmt = due_stmt.order_by(
            UserVocabularyProgress.due_date.asc().nullsfirst(),
            UserVocabularyProgress.created_at.asc(),
        ).limit(limit)
        if exclude_ids:
            due_stmt = due_stmt.where(UserVocabularyProgress.word_id.notin_(exclude_ids))
        due_progress = list(self.db.scalars(due_stmt))
        seen_word_ids: set[int] = set()
        items: list[QueueItem] = []
        for progress in due_progress:
            word = progress.word
            if word is None or self._is_skippable_queue_word(word.word, stopwords=stopwords):
                continue
            if word.id in seen_word_ids:
                continue
            items.append(QueueItem(word=word, progress=progress, is_new=False))
            seen_word_ids.add(word.id)

        if len(items) < limit:
            upcoming_stmt = (
                select(UserVocabularyProgress)
                .options(joinedload(UserVocabularyProgress.word))
                .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
                .where(UserVocabularyProgress.user_id == user.id)
                .where(VocabularyWord.language == target_language)
                .where(UserVocabularyProgress.due_date.isnot(None))
                .where(UserVocabularyProgress.due_date > today)
            )
            if direction_filter is not None:
                upcoming_stmt = upcoming_stmt.where(direction_filter)
            if deck_filter is not None:
                upcoming_stmt = upcoming_stmt.where(deck_filter)
            if exclude_ids:
                upcoming_stmt = upcoming_stmt.where(
                    UserVocabularyProgress.word_id.notin_(exclude_ids)
                )
            if seen_word_ids:
                upcoming_stmt = upcoming_stmt.where(
                    UserVocabularyProgress.word_id.notin_(seen_word_ids)
                )
            upcoming_stmt = upcoming_stmt.order_by(
                UserVocabularyProgress.due_date.asc().nullslast(),
                UserVocabularyProgress.created_at.asc(),
            ).limit(limit - len(items))
            upcoming_progress = list(self.db.scalars(upcoming_stmt))
            for progress in upcoming_progress:
                if not progress.word or self._is_skippable_queue_word(
                    progress.word.word, stopwords=stopwords
                ):
                    continue
                items.append(QueueItem(word=progress.word, progress=progress, is_new=False))
                seen_word_ids.add(progress.word.id)
                if len(items) >= limit:
                    break

        if len(items) >= limit:
            return items

        words_seen_subquery = select(UserVocabularyProgress.word_id).where(
            UserVocabularyProgress.user_id == user.id
        )

        missing = limit - len(items)
        if new_word_budget is not None:
            missing = min(missing, new_word_budget)

        if missing <= 0:
            return items

        # New word selection below reuses the same stopword/length filter

        new_conditions = [
            not_(VocabularyWord.id.in_(words_seen_subquery)),
            VocabularyWord.language == target_language,
        ]
        if direction_filter is not None:
            new_conditions.append(direction_filter)
        if deck_filter is not None:
            new_conditions.append(deck_filter)
        new_word_stmt = select(VocabularyWord).where(and_(*new_conditions))
        if exclude_ids:
            new_word_stmt = new_word_stmt.where(VocabularyWord.id.notin_(exclude_ids))
        new_word_stmt = (
            new_word_stmt.where(func.length(VocabularyWord.word) > 2)
            .where(func.lower(VocabularyWord.word).notin_(stopwords))
            .order_by(func.random())
            .limit(missing)
        )
        new_words = list(self.db.scalars(new_word_stmt))

        items.extend(QueueItem(word=word, progress=None, is_new=True) for word in new_words)
        return items

    @staticmethod
    def _as_aware_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _progress_due_at(self, progress: UserVocabularyProgress) -> datetime | None:
        due_at = self._as_aware_datetime(progress.due_at)
        if due_at is not None:
            return due_at
        next_review = self._as_aware_datetime(progress.next_review_date)
        if next_review is not None:
            return next_review
        if progress.due_date is not None:
            return datetime.combine(progress.due_date, datetime.min.time(), tzinfo=timezone.utc)
        return None

    def _fsrs_retrievability(
        self, progress: UserVocabularyProgress, *, now: datetime
    ) -> float | None:
        stability = progress.stability or progress.interval_days or progress.scheduled_days
        last_review = self._as_aware_datetime(progress.last_review_date)
        if not stability or stability <= 0 or last_review is None:
            return None
        elapsed_days = max(0.0, (now - last_review).total_seconds() / 86_400)
        decay = -0.5
        factor = 0.9 ** (1 / decay) - 1
        return max(0.0, min(1.0, (1 + factor * elapsed_days / stability) ** decay))

    def _recommendation_priority(
        self,
        *,
        progress: UserVocabularyProgress | None,
        word: VocabularyWord,
        bucket: str,
        now: datetime,
    ) -> tuple[float, float | None]:
        if progress is None:
            frequency_rank = word.frequency_rank or 5000
            frequency_bonus = max(0.0, 24.0 - min(frequency_rank, 5000) / 220)
            difficulty_bonus = max(0.0, 8.0 - float(word.difficulty_level or 1))
            return frequency_bonus + difficulty_bonus, None

        due_at = self._progress_due_at(progress)
        days_late = 0.0
        if due_at is not None:
            days_late = max(0.0, (now - due_at).total_seconds() / 86_400)
        retrievability = self._fsrs_retrievability(progress, now=now)
        retrievability_penalty = (1.0 - retrievability) * 42 if retrievability is not None else 18
        base = 100.0 if bucket == "due" else 54.0
        lapse_bonus = float(progress.lapses or 0) * 9
        difficulty_bonus = float(progress.difficulty or 0) * 3.2
        proficiency_bonus = max(0.0, 100.0 - float(progress.proficiency_score or 0)) / 4
        phase_bonus = 12.0 if (progress.phase or "").lower() in {"learn", "learning", "relearn"} else 0.0
        return (
            base + days_late * 7 + retrievability_penalty + lapse_bonus + difficulty_bonus + proficiency_bonus + phase_bonus,
            retrievability,
        )

    def _serialize_vocabulary_recommendation(
        self,
        *,
        word: VocabularyWord,
        progress: UserVocabularyProgress | None,
        bucket: str,
        now: datetime,
    ) -> dict[str, Any]:
        priority_score, retrievability = self._recommendation_priority(
            progress=progress,
            word=word,
            bucket=bucket,
            now=now,
        )
        due_at = self._progress_due_at(progress) if progress else None
        return {
            "bucket": bucket,
            "word_id": word.id,
            "progress_id": str(progress.id) if progress else None,
            "word": word.word,
            "language": word.language,
            "direction": word.direction,
            "scheduler": progress.scheduler if progress else ("anki" if word.is_anki_card else "fsrs"),
            "state": progress.state if progress else "new",
            "phase": progress.phase if progress else None,
            "due_at": due_at,
            "next_review": progress.next_review_date if progress else None,
            "last_review": progress.last_review_date if progress else None,
            "scheduled_days": progress.scheduled_days if progress else None,
            "interval_days": progress.interval_days if progress else None,
            "stability": progress.stability if progress else None,
            "difficulty": progress.difficulty if progress else None,
            "retrievability": retrievability,
            "proficiency_score": progress.proficiency_score if progress else 0,
            "lapses": progress.lapses if progress else 0,
            "priority_score": round(priority_score, 3),
            "is_new": progress is None,
            "deck_name": word.deck_name,
            "translations": {
                "de": word.german_translation,
                "en": word.english_translation,
                "fr": word.french_translation,
            },
            "example_sentence": word.example_sentence,
            "example_translation": word.example_translation,
        }

    def get_vocabulary_recommendations(
        self,
        *,
        user: User,
        limit: int = 12,
        due_limit: int = 6,
        fragile_limit: int = 3,
        new_limit: int = 3,
        direction: str | None = None,
        deck_name: str | None = None,
        include_upcoming_days: int = 0,
        include_shared_phrases: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return due, fragile, and new words ranked by FSRS-style memory urgency."""

        now = now or datetime.now(timezone.utc)
        today = now.date()
        upcoming_limit = today + timedelta(days=max(0, include_upcoming_days))
        stopwords = self._queue_stopwords()
        target_language = (user.target_language or "fr").strip() or "fr"
        direction_filter = (
            self._shared_direction_filter(direction)
            if include_shared_phrases
            else (VocabularyWord.direction == direction if direction else None)
        )
        deck_filter = self._shared_deck_filter(deck_name)

        progress_stmt = (
            select(UserVocabularyProgress)
            .options(joinedload(UserVocabularyProgress.word))
            .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
            .where(UserVocabularyProgress.user_id == user.id)
            .where(VocabularyWord.language == target_language)
            .where(func.length(VocabularyWord.word) > 2)
            .where(func.lower(VocabularyWord.word).notin_(stopwords))
        )
        if not include_shared_phrases:
            progress_stmt = progress_stmt.where(VocabularyWord.is_anki_card.is_(True))
        if direction_filter is not None:
            progress_stmt = progress_stmt.where(direction_filter)
        if deck_filter is not None:
            progress_stmt = progress_stmt.where(deck_filter)
        progress_stmt = progress_stmt.order_by(
            UserVocabularyProgress.due_at.asc().nullsfirst(),
            UserVocabularyProgress.next_review_date.asc().nullsfirst(),
            UserVocabularyProgress.due_date.asc().nullsfirst(),
            UserVocabularyProgress.created_at.asc(),
        ).limit(max(80, limit * 6))

        progress_rows = list(self.db.scalars(progress_stmt))
        due_candidates: list[dict[str, Any]] = []
        fragile_candidates: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str | None]] = set()

        for progress in progress_rows:
            word = progress.word
            if word is None or self._is_skippable_queue_word(word.word, stopwords=stopwords):
                continue
            dedupe_key = ((word.normalized_word or word.word).strip().lower(), word.direction)
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            due_at = self._progress_due_at(progress)
            is_due = (
                due_at is not None and due_at <= now
            ) or (
                progress.due_date is not None and progress.due_date <= upcoming_limit
            ) or (
                due_at is None and (progress.reps or 0) == 0
            )
            fragile = (
                (progress.lapses or 0) > 0
                or (progress.proficiency_score or 0) < 50
                or 0 < float(progress.stability or 0) < 3
                or float(progress.difficulty or 0) >= 7
                or (progress.phase or "").lower() in {"learn", "learning", "relearn"}
            )
            if is_due:
                due_candidates.append(
                    self._serialize_vocabulary_recommendation(
                        word=word,
                        progress=progress,
                        bucket="due",
                        now=now,
                    )
                )
            elif fragile:
                fragile_candidates.append(
                    self._serialize_vocabulary_recommendation(
                        word=word,
                        progress=progress,
                        bucket="fragile",
                        now=now,
                    )
                )

        due_candidates.sort(key=lambda item: item["priority_score"], reverse=True)
        fragile_candidates.sort(key=lambda item: item["priority_score"], reverse=True)

        selected_due = due_candidates[:due_limit]
        selected_fragile = fragile_candidates[:fragile_limit]
        used_word_ids = {item["word_id"] for item in selected_due + selected_fragile}

        words_seen_subquery = select(UserVocabularyProgress.word_id).where(
            UserVocabularyProgress.user_id == user.id
        )
        new_conditions = [
            not_(VocabularyWord.id.in_(words_seen_subquery)),
            VocabularyWord.language == target_language,
            func.length(VocabularyWord.word) > 2,
            func.lower(VocabularyWord.word).notin_(stopwords),
        ]
        if not include_shared_phrases:
            new_conditions.append(VocabularyWord.is_anki_card.is_(True))
        if direction_filter is not None:
            new_conditions.append(direction_filter)
        if deck_filter is not None:
            new_conditions.append(deck_filter)

        new_count_stmt = select(func.count(VocabularyWord.id)).where(and_(*new_conditions))
        new_count = int(self.db.scalar(new_count_stmt) or 0)
        new_stmt = select(VocabularyWord).where(and_(*new_conditions))
        if used_word_ids:
            new_stmt = new_stmt.where(VocabularyWord.id.notin_(used_word_ids))
        new_stmt = new_stmt.order_by(
            VocabularyWord.frequency_rank.asc().nullslast(),
            VocabularyWord.difficulty_level.asc().nullslast(),
            func.lower(VocabularyWord.word).asc(),
        ).limit(new_limit)

        selected_new = [
            self._serialize_vocabulary_recommendation(
                word=word,
                progress=None,
                bucket="new",
                now=now,
            )
            for word in self.db.scalars(new_stmt)
        ]

        items = (selected_due + selected_fragile + selected_new)[:limit]
        return {
            "summary": {
                "due": len(due_candidates),
                "fragile": len(fragile_candidates),
                "new": new_count,
                "total": len(due_candidates) + len(fragile_candidates) + new_count,
            },
            "items": items,
            "algorithm": "fsrs_retrievability_v1",
        }

    def _serialize_vocabulary_word_for_context(
        self,
        *,
        user: User,
        word: VocabularyWord,
        bucket: str,
        now: datetime,
    ) -> dict[str, Any]:
        progress = self.get_progress(user_id=user.id, word_id=word.id)
        return self._serialize_vocabulary_recommendation(
            word=word,
            progress=progress,
            bucket=bucket,
            now=now,
        )

    def _context_word_query(
        self,
        *,
        user: User,
        direction: str | None,
    ):
        target_language = "de" if direction == "de_to_fr" else (user.target_language or "fr").strip() or "fr"
        query = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.is_anki_card.is_(True))
            .filter(VocabularyWord.language == target_language)
            .filter(func.length(VocabularyWord.word) > 2)
            .filter(func.lower(VocabularyWord.word).notin_(self._queue_stopwords()))
        )
        if direction:
            query = query.filter(VocabularyWord.direction == direction)
        return query

    def _topic_compatible_vocabulary(
        self,
        *,
        user: User,
        topic_tags: list[str],
        direction: str | None,
        limit: int,
        exclude_word_ids: set[int],
        now: datetime,
    ) -> list[dict[str, Any]]:
        normalized_tags = {tag.strip().lower() for tag in topic_tags if tag and tag.strip()}
        if limit <= 0 or not normalized_tags:
            return []

        candidates = (
            self._context_word_query(user=user, direction=direction)
            .order_by(
                VocabularyWord.frequency_rank.asc().nullslast(),
                VocabularyWord.difficulty_level.asc().nullslast(),
                func.lower(VocabularyWord.word).asc(),
            )
            .limit(max(limit * 12, 60))
            .all()
        )
        selected: list[dict[str, Any]] = []
        for word in candidates:
            if word.id in exclude_word_ids:
                continue
            word_tags = {tag.strip().lower() for tag in (word.topic_tags or []) if tag and tag.strip()}
            if not normalized_tags.intersection(word_tags):
                continue
            selected.append(
                self._serialize_vocabulary_word_for_context(
                    user=user,
                    word=word,
                    bucket="topic",
                    now=now,
                )
            )
            exclude_word_ids.add(word.id)
            if len(selected) >= limit:
                break
        return selected

    def _linked_vocabulary(
        self,
        *,
        user: User,
        linked_word_ids: list[int],
        limit: int,
        exclude_word_ids: set[int],
        now: datetime,
    ) -> list[dict[str, Any]]:
        ordered_ids = [int(word_id) for word_id in linked_word_ids if word_id]
        if limit <= 0 or not ordered_ids:
            return []

        words = (
            self.db.query(VocabularyWord)
            .filter(VocabularyWord.id.in_(ordered_ids))
            .all()
        )
        words_by_id = {word.id: word for word in words}
        selected: list[dict[str, Any]] = []
        for word_id in ordered_ids:
            word = words_by_id.get(word_id)
            if not word or word.id in exclude_word_ids:
                continue
            selected.append(
                self._serialize_vocabulary_word_for_context(
                    user=user,
                    word=word,
                    bucket="linked",
                    now=now,
                )
            )
            exclude_word_ids.add(word.id)
            if len(selected) >= limit:
                break
        return selected

    def get_vocabulary_due_context(
        self,
        *,
        user: User,
        limit: int = 12,
        due_limit: int = 4,
        fragile_limit: int = 4,
        new_limit: int = 4,
        topic_limit: int = 4,
        linked_limit: int = 4,
        direction: str | None = "fr_to_de",
        topic_tags: list[str] | None = None,
        linked_word_ids: list[int] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Return a bucketed vocabulary bundle for contextual mobile surfaces."""

        now = now or datetime.now(timezone.utc)
        recommendations = self.get_vocabulary_recommendations(
            user=user,
            limit=limit,
            due_limit=due_limit,
            fragile_limit=fragile_limit,
            new_limit=new_limit,
            direction=direction,
            now=now,
        )
        due_words = [item for item in recommendations["items"] if item["bucket"] == "due"][:due_limit]
        fragile_words = [
            item for item in recommendations["items"] if item["bucket"] == "fragile"
        ][:fragile_limit]
        new_words = [item for item in recommendations["items"] if item["bucket"] == "new"][:new_limit]
        used_word_ids = {item["word_id"] for item in due_words + fragile_words + new_words}

        linked_words = self._linked_vocabulary(
            user=user,
            linked_word_ids=linked_word_ids or [],
            limit=linked_limit,
            exclude_word_ids=used_word_ids,
            now=now,
        )
        topic_compatible_words = self._topic_compatible_vocabulary(
            user=user,
            topic_tags=topic_tags or [],
            direction=direction,
            limit=topic_limit,
            exclude_word_ids=used_word_ids,
            now=now,
        )
        total = (
            len(due_words)
            + len(fragile_words)
            + len(new_words)
            + len(topic_compatible_words)
            + len(linked_words)
        )
        return {
            "summary": {
                "due": len(due_words),
                "fragile": len(fragile_words),
                "new": len(new_words),
                "topic_compatible": len(topic_compatible_words),
                "linked": len(linked_words),
                "total": total,
            },
            "due_words": due_words,
            "fragile_words": fragile_words,
            "new_words": new_words,
            "topic_compatible_words": topic_compatible_words,
            "linked_words": linked_words,
            "algorithm": recommendations.get("algorithm", "fsrs_retrievability_v1"),
        }

    def sample_vocabulary(
        self,
        *,
        user: User,
        limit: int,
        exclude_ids: set[int] | None = None,
        direction: str | None = None,
        deck_name: str | None = None,
    ) -> list[VocabularyWord]:
        stopwords = self._queue_stopwords()
        target_language = (user.target_language or "fr").strip() or "fr"
        query = (
            self.db.query(VocabularyWord)
            .filter(func.length(VocabularyWord.word) > 2)
            .filter(func.lower(VocabularyWord.word).notin_(stopwords))
            .filter(VocabularyWord.language == target_language)
        )
        direction_filter = self._shared_direction_filter(direction)
        if direction_filter is not None:
            query = query.filter(direction_filter)
        deck_filter = self._shared_deck_filter(deck_name)
        if deck_filter is not None:
            query = query.filter(deck_filter)
        if exclude_ids:
            query = query.filter(~VocabularyWord.id.in_(exclude_ids))
        query = query.order_by(func.random()).limit(limit)
        return list(query.all())

    def list_anki_progress(self, *, user: User, direction: str | None = None) -> list[dict[str, Any]]:
        """Return Anki-imported vocabulary with the learner's progress metadata."""

        stmt = (
            select(VocabularyWord, UserVocabularyProgress)
            .select_from(VocabularyWord)
            .join(
                UserVocabularyProgress,
                and_(
                    UserVocabularyProgress.word_id == VocabularyWord.id,
                    UserVocabularyProgress.user_id == user.id,
                ),
                isouter=True,
            )
            .where(VocabularyWord.is_anki_card.is_(True))
        )
        if direction:
            stmt = stmt.where(VocabularyWord.direction == direction)
        stmt = stmt.order_by(
            VocabularyWord.direction.asc().nullsfirst(),
            func.lower(VocabularyWord.word).asc(),
        )

        rows = self.db.execute(stmt).all()
        results: list[dict[str, Any]] = []
        for word, progress in rows:
            learning_stage = "new"
            state = "new"
            ease_factor = None
            interval_days = None
            due_at = None
            next_review = None
            last_review = None
            reps = 0
            lapses = 0
            proficiency = 0
            scheduler = None
            progress_difficulty = None

            if progress is not None:
                learning_stage = progress.phase or "new"
                state = progress.state or "new"
                ease_factor = progress.ease_factor
                interval_days = progress.interval_days
                due_at = progress.due_at
                next_review = progress.next_review_date
                last_review = progress.last_review_date
                reps = progress.reps or 0
                lapses = progress.lapses or 0
                proficiency = progress.proficiency_score or 0
                scheduler = progress.scheduler
                progress_difficulty = progress.difficulty

            translation_hint = word.english_translation
            if word.direction == "fr_to_de":
                translation_hint = word.german_translation or translation_hint
            elif word.direction == "de_to_fr":
                translation_hint = word.french_translation or translation_hint

            results.append(
                {
                    "word_id": word.id,
                    "word": word.word,
                    "language": word.language,
                    "direction": word.direction,
                    "french_translation": word.french_translation,
                    "german_translation": word.german_translation,
                    "deck_name": word.deck_name,
                    "difficulty_level": word.difficulty_level,
                    "english_translation": translation_hint,
                    "learning_stage": learning_stage,
                    "state": state,
                    "ease_factor": ease_factor,
                    "interval_days": interval_days,
                    "due_at": due_at,
                    "next_review": next_review,
                    "last_review": last_review,
                    "reps": reps,
                    "lapses": lapses,
                    "proficiency_score": proficiency,
                    "scheduler": scheduler,
                    "progress_difficulty": progress_difficulty,
                }
            )

        return results

    def anki_progress_summary(self, *, user: User) -> dict[str, Any]:
        """Aggregate progress statistics for Anki cards."""

        records = self.list_anki_progress(user=user)
        now = datetime.now(timezone.utc)

        stage_map = {
            "new": {"labels": {"new"}},
            "learning": {"labels": {"learn", "learning"}},
            "review": {"labels": {"review"}},
            "relearn": {"labels": {"relearn"}},
        }

        def normalize_stage(stage: str | None) -> str:
            base = (stage or "new").lower()
            for key, info in stage_map.items():
                if base in info["labels"]:
                    return key
            return "other"

        overall_counts = {"new": 0, "learning": 0, "review": 0, "relearn": 0, "other": 0}
        overall_due = 0
        direction_keys = ["fr_to_de", "de_to_fr"]
        direction_summary: dict[str, dict[str, Any]] = {
            key: {
                "direction": key,
                "total": 0,
                "due_today": 0,
                "stage_counts": {"new": 0, "learning": 0, "review": 0, "relearn": 0, "other": 0},
            }
            for key in direction_keys
        }

        for record in records:
            direction = record.get("direction")
            stage_key = normalize_stage(record.get("learning_stage"))
            due_candidate = record.get("due_at") or record.get("next_review")
            if isinstance(due_candidate, str):
                try:
                    due_candidate = datetime.fromisoformat(due_candidate)
                except ValueError:
                    due_candidate = None

            overall_counts[stage_key] = overall_counts.get(stage_key, 0) + 1
            if due_candidate and due_candidate.date() <= now.date():
                overall_due += 1

            if direction in direction_summary:
                summary = direction_summary[direction]
                summary["total"] += 1
                summary["stage_counts"][stage_key] = summary["stage_counts"].get(stage_key, 0) + 1
                if due_candidate and due_candidate.date() <= now.date():
                    summary["due_today"] += 1

        total_cards = sum(overall_counts.values())
        chart_data = [
            {"stage": key, "value": overall_counts.get(key, 0)}
            for key in ["new", "learning", "review", "relearn", "other"]
            if overall_counts.get(key, 0) > 0
        ]

        return {
            "total_cards": total_cards,
            "due_today": overall_due,
            "stage_totals": overall_counts,
            "chart": chart_data,
            "directions": direction_summary,
        }

    def count_due_reviews(
        self,
        user_id: uuid.UUID,
        now: datetime | None = None,
        direction: str | None = None,
        include_upcoming_days: int = 0,
        deck_name: str | None = None,
    ) -> int:
        """Return how many reviews are currently due for the learner."""

        now = now or datetime.now(timezone.utc)
        today = now.date()
        upcoming_limit = today + timedelta(days=max(0, include_upcoming_days))
        cache_key = (
            f"{user_id}:{direction or 'all'}:{deck_name or 'all'}:"
            f"{today.isoformat()}:{include_upcoming_days}"
        )
        cached = cache_backend.get("progress:due_reviews", cache_key)
        if cached is not None:
            return int(cached)

        query = (
            self.db.query(func.count(UserVocabularyProgress.id))
            .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
            .filter(
                UserVocabularyProgress.user_id == user_id,
                or_(
                    UserVocabularyProgress.due_date.is_(None),
                    UserVocabularyProgress.due_date <= upcoming_limit,
                ),
            )
        )
        if direction:
            query = query.filter(VocabularyWord.direction == direction)
        if deck_name:
            query = query.filter(VocabularyWord.deck_name == deck_name)
        count = query.scalar()
        result = int(count or 0)
        cache_backend.set("progress:due_reviews", cache_key, result, ttl_seconds=60)
        return result

    def calculate_new_word_budget(
        self,
        user_id: uuid.UUID,
        session_capacity: int,
        now: datetime | None = None,
        direction: str | None = None,
        deck_name: str | None = None,
    ) -> int:
        """Determine how many new words can be introduced in the current session."""

        due_reviews = self.count_due_reviews(
            user_id,
            now=now,
            direction=direction,
            deck_name=deck_name,
        )
        if due_reviews >= session_capacity:
            return 0

        remaining_capacity = session_capacity - due_reviews
        max_new_words = int(session_capacity * 0.5)
        new_word_budget = min(remaining_capacity, max_new_words)
        return max(0, new_word_budget)

    def calculate_review_performance(
        self,
        user_id: uuid.UUID,
        lookback_days: int = 7,
        now: datetime | None = None,
        direction: str | None = None,
        deck_name: str | None = None,
    ) -> float:
        """Calculate a learner's recent review performance score."""

        now = now or datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=lookback_days)
        query = (
            self.db.query(ReviewLog)
            .join(UserVocabularyProgress)
            .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
            .filter(
                UserVocabularyProgress.user_id == user_id,
                ReviewLog.review_date >= cutoff_date,
            )
        )
        if direction:
            query = query.filter(VocabularyWord.direction == direction)
        if deck_name:
            query = query.filter(VocabularyWord.deck_name == deck_name)
        recent_reviews = query.all()

        if not recent_reviews:
            return 0.5

        rating_to_score = {3: 1.0, 2: 0.66, 1: 0.33, 0: 0.0}
        total_score = sum(rating_to_score.get(review.rating, 0.0) for review in recent_reviews)
        return total_score / len(recent_reviews)

    def calculate_adaptive_review_ratio(
        self,
        user_id: uuid.UUID,
        direction: str | None = None,
        deck_name: str | None = None,
    ) -> float:
        """Return the desired review ratio based on learner performance."""

        performance = self.calculate_review_performance(
            user_id,
            direction=direction,
            deck_name=deck_name,
        )
        if performance < 0.5:
            return 0.75
        if performance < 0.7:
            return 0.60
        return 0.45

    # ------------------------------------------------------------------
    # Review helpers
    # ------------------------------------------------------------------
    def _state_from_progress(self, progress: UserVocabularyProgress) -> SchedulerState:
        return SchedulerState(
            stability=progress.stability or 0.0,
            difficulty=progress.difficulty or 5.0,
            reps=progress.reps or 0,
            lapses=progress.lapses or 0,
            scheduled_days=progress.scheduled_days or 0,
            state=progress.state or "new",
        )

    def record_review(
        self,
        *,
        user: User,
        word: VocabularyWord,
        rating: int,
        now: datetime | None = None,
    ) -> tuple[UserVocabularyProgress, ReviewLog, ReviewOutcome]:
        """Persist a learner review and return the updated progress."""

        now = now or datetime.now(timezone.utc)
        progress = self.get_or_create_progress(user_id=user.id, word_id=word.id)
        previous_schedule = progress.scheduled_days
        state = self._state_from_progress(progress)
        outcome = self.scheduler.review(
            state=state,
            rating=rating,
            last_review_at=progress.last_review_date,
            now=now,
        )

        progress.stability = outcome.stability
        progress.difficulty = outcome.difficulty
        progress.elapsed_days = outcome.elapsed_days
        progress.scheduled_days = outcome.scheduled_days
        progress.state = outcome.state
        progress.mark_review(review_date=now, next_review=outcome.next_review, rating=rating)
        progress.updated_at = now

        review_log = ReviewLog(
            progress=progress,
            rating=rating,
            review_date=now,
            state_transition=f"{state.state}->{outcome.state}",
        )
        review_log.set_schedule_transition(before=previous_schedule, after=outcome.scheduled_days)

        self.db.add(review_log)
        self.db.flush([progress, review_log])
        cache_backend.invalidate("progress:due_reviews", prefix=f"{user.id}:")
        return progress, review_log, outcome

    def record_context_credit(
        self,
        *,
        user: User,
        word: VocabularyWord,
        event_type: str,
        now: datetime | None = None,
    ) -> UserVocabularyProgress:
        """Apply lightweight vocabulary credit from contextual use outside flashcards."""

        now = now or datetime.now(timezone.utc)
        progress = self.get_or_create_progress(user_id=user.id, word_id=word.id)
        event = str(event_type or "seen_context").lower()

        if event in {"produced_correct", "used_correctly", "free_production_correct"}:
            progress, _, _ = self.record_review(user=user, word=word, rating=3, now=now)
            progress.record_usage(correct=True, is_new=(progress.reps or 0) <= 1)
        elif event in {"recognized", "translated", "recognition"}:
            progress, _, _ = self.record_review(user=user, word=word, rating=2, now=now)
            progress.times_seen = (progress.times_seen or 0) + 1
            progress.adjust_proficiency(5)
        elif event in {"produced_incorrect", "used_incorrectly", "incorrect"}:
            progress.record_usage(correct=False)
            progress.state = "relearning"
            progress.phase = "relearn"
            progress.next_review_date = now
            progress.due_date = now.date()
            progress.updated_at = now
        else:
            progress.times_seen = (progress.times_seen or 0) + 1
            progress.adjust_proficiency(1)
            if not progress.next_review_date:
                progress.next_review_date = now + timedelta(days=3)
                progress.due_date = progress.next_review_date.date()
            if (progress.state or "new") == "new":
                progress.state = "learning"
            progress.updated_at = now

        self.db.add(progress)
        self.db.flush([progress])
        cache_backend.invalidate("progress:due_reviews", prefix=f"{user.id}:")
        return progress

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
    def sync_anki_progress(self, *, user: User, cards: list[AnkiCardUpdate]) -> dict[str, int]:
        """Sync progress from AnkiConnect updates."""
        stats = {"updated": 0, "created": 0, "skipped": 0, "errors": 0}
        now = datetime.now(timezone.utc)
        for card in cards:
            # Determine direction first to guide field extraction
            language = "fr" # Default target
            direction = "fr_to_de" # Default direction
            
            if card.deck_name:
                lower_deck = card.deck_name.lower()
                if "fr->de" in lower_deck or "fr-de" in lower_deck:
                    language = "fr"
                    direction = "fr_to_de"
                elif "de->fr" in lower_deck or "de-fr" in lower_deck:
                    language = "de"
                    direction = "de_to_fr"
                elif "german" in lower_deck or "deutsch" in lower_deck:
                    language = "de"
                    direction = "de_to_fr" 
                elif "french" in lower_deck or "francais" in lower_deck or "französisch" in lower_deck:
                    language = "fr"
                    direction = "fr_to_de"

            # Refine direction using 'ord' (template index) if available
            # For "Basic (and reversed card)", ord 0 is usually Forward, ord 1 is Reverse.
            if card.ord is not None:
                # If we defaulted to fr_to_de but ord is 1 (Reverse), it might be de_to_fr
                # This assumes standard Anki templates where 0=Forward, 1=Reverse
                if card.ord == 1:
                    if direction == "fr_to_de":
                        direction = "de_to_fr"
                        language = "de"
                elif card.ord == 0:
                     if direction == "de_to_fr": # Unlikely but possible if deck name misled us
                        direction = "fr_to_de"
                        language = "fr"

            # Helper to find field by keys
            def get_field_value(keys, fields):
                for k in keys:
                    for field_name, field_value in fields.items():
                        if field_name.lower() == k.lower() and field_value:
                            return field_value
                return None

            # Define priority keys based on user's deck screenshots
            # French = Wort, Wort mit Artikel
            # German = Definition
            
            french_keys = ["Wort", "Wort mit Artikel", "Frage", "French", "Français", "Francais", "Französisch", "Question", "Front"]
            german_keys = ["Definition", "Antwort", "German", "Deutsch", "Allemand", "Answer", "Back"]
            
            # Explicitly identify English fields to avoid them
            english_keys = ["English", "Englisch", "Meaning", "Bedeutung"]
            
            word_text = None
            translation_text = None
            
            # Extract based on direction
            if direction == "fr_to_de":
                # Word = French, Translation = German
                word_text = get_field_value(french_keys, card.fields)
                translation_text = get_field_value(german_keys, card.fields)
            else:
                # Word = German, Translation = French
                word_text = get_field_value(german_keys, card.fields)
                translation_text = get_field_value(french_keys, card.fields)

            # Fallback: If we found an "English" field but wanted German, ignore it?
            # But we don't know if "Definition" contains English or German without language detection.
            # Given the screenshot shows "Definition: Mann", we assume Definition is German.
            
            # If we still don't have texts, try generic fallback but avoid known English keys
            if not word_text:
                for k, v in card.fields.items():
                    if k not in english_keys and v and not v.isdigit():
                        word_text = v
                        break
            
            if not translation_text:
                for k, v in card.fields.items():
                    if k not in english_keys and v and not v.isdigit() and v != word_text:
                        translation_text = v
                        break

            # Heuristic: if word_text looks like an ID (pure digits), try other fields
            if word_text and word_text.isdigit():
                 candidate = None
                 for k, v in card.fields.items():
                     if v and not v.isdigit() and len(v) < 100 and k.lower() not in ["back", "english", "meaning", "definition", "id", "noteid", "cardid", "index", "rank", "frequency"]:
                         candidate = v
                         break
                 if candidate:
                     word_text = candidate

            if not word_text:
                # Fallback: try to find any field that looks like a word
                for k, v in card.fields.items():
                    if v and len(v) < 50 and k.lower() not in ["back", "english", "meaning", "definition", "id", "index", "rank", "frequency"]:
                        if not v.isdigit():
                            word_text = v
                            break
            
            if not word_text:
                stats["skipped"] += 1
                continue
                
            # Clean up word text (remove HTML, etc if needed - Anki often has HTML)
            import re
            clean_word = re.sub('<[^<]+?>', '', word_text).strip()
            if not clean_word or clean_word.isdigit(): 
                stats["skipped"] += 1
                continue

            clean_translation = ""
            if translation_text:
                clean_translation = re.sub('<[^<]+?>', '', translation_text).strip()

            # 1. Try to find existing word by Anki Card ID first
            vocab_word = self.db.scalars(
                select(VocabularyWord).where(VocabularyWord.card_id == str(card.card_id))
            ).first()

            if not vocab_word:
                # 2. If not found by ID, try to find by word text AND direction
                existing_word = self.db.scalars(
                    select(VocabularyWord).where(
                        func.lower(VocabularyWord.word) == func.lower(clean_word),
                        VocabularyWord.is_anki_card.is_(False) 
                    )
                ).first()
                
                if existing_word:
                    vocab_word = existing_word
                    vocab_word.is_anki_card = True
                    vocab_word.note_id = str(card.note_id)
                    vocab_word.card_id = str(card.card_id)
                    vocab_word.deck_name = card.deck_name
                    # Update content as well
                    vocab_word.word = clean_word
                    vocab_word.english_translation = clean_translation
                    vocab_word.direction = direction
                    vocab_word.language = language
                    if direction == "fr_to_de":
                        vocab_word.german_translation = clean_translation
                    else:
                        vocab_word.french_translation = clean_translation
                    stats["updated"] += 1
                else:
                    # Create new
                    german_trans = None
                    french_trans = None
                    english_trans = clean_translation
                    
                    if direction == "fr_to_de":
                        german_trans = clean_translation
                    else:
                        french_trans = clean_translation

                    vocab_word = VocabularyWord(
                        word=clean_word,
                        normalized_word=clean_word.lower(),
                        language=language,
                        direction=direction,
                        english_translation=english_trans, 
                        german_translation=german_trans,
                        french_translation=french_trans,
                        deck_name=card.deck_name,
                        note_id=str(card.note_id),
                        card_id=str(card.card_id),
                        is_anki_card=True,
                        created_at=now
                    )
                    self.db.add(vocab_word)
                    self.db.flush() 
                    stats["created"] += 1
            else:
                # Update existing word metadata AND content
                vocab_word.deck_name = card.deck_name
                vocab_word.word = clean_word
                vocab_word.english_translation = clean_translation
                vocab_word.direction = direction
                vocab_word.language = language
                if direction == "fr_to_de":
                    vocab_word.german_translation = clean_translation
                else:
                    vocab_word.french_translation = clean_translation
                stats["updated"] += 1
                
            # Update progress
            progress = self.get_or_create_progress(user_id=user.id, word_id=vocab_word.id)
            
            if card.interval is not None:
                progress.interval_days = card.interval
                progress.scheduled_days = card.interval
                
            if card.ease is not None:
                # Anki ease is permyriad (e.g. 2500 = 250%)
                progress.ease_factor = card.ease / 1000.0
                
            if card.reps is not None:
                progress.reps = card.reps
                
            if card.lapses is not None:
                progress.lapses = card.lapses
            
            # Handle due date logic
            if card.due:
                if card.due > 100000000:
                    # It's a timestamp
                    try:
                        due_date = datetime.fromtimestamp(card.due, tz=timezone.utc)
                        progress.due_at = due_date.date()
                        progress.next_review_date = due_date
                    except (ValueError, OSError):
                        pass
                else:
                    # It's days.
                    if card.interval:
                         progress.next_review_date = now + timedelta(days=card.interval)
                         progress.due_at = progress.next_review_date.date()

            progress.updated_at = now
            progress.scheduler = "anki"
            
            self.db.add(progress)
            
        self.db.commit()
        return stats

    def progress_summary(self, *, user_id: User.id, word_id: int) -> dict[str, int]:
        """Return aggregate counters for UI consumption."""

        progress = self.get_progress(user_id=user_id, word_id=word_id)
        if not progress:
            return {
                "reps": 0,
                "lapses": 0,
                "correct_count": 0,
                "incorrect_count": 0,
            }

        review_count = self.db.scalar(
            select(func.count()).select_from(ReviewLog).where(ReviewLog.progress_id == progress.id)
        )

        return {
            "reps": progress.reps or 0,
            "lapses": progress.lapses or 0,
            "correct_count": progress.correct_count or 0,
            "incorrect_count": progress.incorrect_count or 0,
            "reviews_logged": int(review_count or 0),
        }
