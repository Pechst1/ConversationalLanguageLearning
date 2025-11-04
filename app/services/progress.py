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
        upcoming_window_days: int = 2,
    ) -> list[QueueItem]:
        """Return due and new words for a learner.

        Args:
            user: Learner whose queue is being built.
            limit: Maximum number of queue items to return.
            now: Reference time for scheduling cut-offs.
            new_word_budget: Optional cap on newly introduced vocabulary.
            exclude_ids: Vocabulary identifiers that should be skipped.
            direction: Filter vocabulary by card direction (e.g. ``"fr_to_de"``).
            upcoming_window_days: Number of days ahead to treat reviews as "due".
        """

        now = now or datetime.now(timezone.utc)
        exclude_ids = exclude_ids or set()
        upcoming_window_days = max(0, upcoming_window_days)
        due_cutoff_date = now.date() + timedelta(days=upcoming_window_days)
        due_cutoff_dt = now + timedelta(days=upcoming_window_days)
        # Basic stopword/length filter to avoid proposing ultra-common function words
        stopwords = {
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
        def _is_skippable_word(w: str | None) -> bool:
            if not w:
                return True
            lw = w.strip().lower()
            return len(lw) <= 2 or lw in stopwords
        due_stmt = (
            select(UserVocabularyProgress)
            .options(joinedload(UserVocabularyProgress.word))
            .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
            .where(UserVocabularyProgress.user_id == user.id)
            .where(VocabularyWord.is_anki_card.is_(True))
            .where(
                or_(
                    UserVocabularyProgress.due_date.is_(None),
                    UserVocabularyProgress.due_date <= due_cutoff_date,
                    UserVocabularyProgress.next_review_date <= due_cutoff_dt,
                    UserVocabularyProgress.due_at <= due_cutoff_dt,
                )
            )
        )
        if direction:
            due_stmt = due_stmt.where(VocabularyWord.direction == direction)
        due_stmt = due_stmt.order_by(
            UserVocabularyProgress.due_date.nullsfirst(),
            UserVocabularyProgress.next_review_date.nullsfirst(),
            UserVocabularyProgress.created_at,
        ).limit(limit)
        if exclude_ids:
            due_stmt = due_stmt.where(UserVocabularyProgress.word_id.notin_(exclude_ids))
        due_progress = list(self.db.scalars(due_stmt))
        seen_progress_ids = {progress.id for progress in due_progress}
        items: list[QueueItem] = [
            QueueItem(word=progress.word, progress=progress, is_new=False)
            for progress in due_progress
            if progress.word is not None and not _is_skippable_word(progress.word.word)
        ]

        if len(items) < limit:
            missing = limit - len(items)
            upcoming_stmt = (
                select(UserVocabularyProgress)
                .options(joinedload(UserVocabularyProgress.word))
                .join(VocabularyWord, VocabularyWord.id == UserVocabularyProgress.word_id)
                .where(UserVocabularyProgress.user_id == user.id)
                .where(VocabularyWord.is_anki_card.is_(True))
            )
            if direction:
                upcoming_stmt = upcoming_stmt.where(VocabularyWord.direction == direction)
            if exclude_ids:
                upcoming_stmt = upcoming_stmt.where(
                    UserVocabularyProgress.word_id.notin_(exclude_ids)
                )
            if seen_progress_ids:
                upcoming_stmt = upcoming_stmt.where(
                    UserVocabularyProgress.id.notin_(seen_progress_ids)
                )
            upcoming_stmt = upcoming_stmt.order_by(
                UserVocabularyProgress.due_date.nullslast(),
                UserVocabularyProgress.next_review_date.nullslast(),
                UserVocabularyProgress.created_at,
            ).limit(missing)
            upcoming_progress = list(self.db.scalars(upcoming_stmt))
            for progress in upcoming_progress:
                if not progress.word or _is_skippable_word(progress.word.word):
                    continue
                items.append(QueueItem(word=progress.word, progress=progress, is_new=False))
                seen_progress_ids.add(progress.id)
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

        new_conditions = [not_(VocabularyWord.id.in_(words_seen_subquery))]
        new_word_stmt = select(VocabularyWord).where(and_(*new_conditions))
        new_word_stmt = new_word_stmt.where(VocabularyWord.is_anki_card.is_(True))
        if direction:
            new_word_stmt = new_word_stmt.where(VocabularyWord.direction == direction)
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

    def sample_vocabulary(
        self,
        *,
        user: User,
        limit: int,
        exclude_ids: set[int] | None = None,
        direction: str | None = None,
    ) -> list[VocabularyWord]:
        stopwords = {
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
        query = (
            self.db.query(VocabularyWord)
            .filter(func.length(VocabularyWord.word) > 2)
            .filter(func.lower(VocabularyWord.word).notin_(stopwords))
            .filter(VocabularyWord.is_anki_card.is_(True))
        )
        if direction:
            query = query.filter(VocabularyWord.direction == direction)
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
    ) -> int:
        """Return how many reviews are currently due for the learner."""

        now = now or datetime.now(timezone.utc)
        include_upcoming_days = max(0, include_upcoming_days)
        date_cutoff = now.date() + timedelta(days=include_upcoming_days)
        datetime_cutoff = now + timedelta(days=include_upcoming_days)
        today = now.date()
        cache_key = f"{user_id}:{direction or 'all'}:{today.isoformat()}:{include_upcoming_days}"
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
                    UserVocabularyProgress.due_date <= date_cutoff,
                    UserVocabularyProgress.next_review_date <= datetime_cutoff,
                    UserVocabularyProgress.due_at <= datetime_cutoff,
                ),
            )
        )
        if direction:
            query = query.filter(VocabularyWord.direction == direction)
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
    ) -> int:
        """Determine how many new words can be introduced in the current session."""

        due_reviews = self.count_due_reviews(
            user_id,
            now=now,
            direction=direction,
            include_upcoming_days=2,
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
    ) -> float:
        """Return the desired review ratio based on learner performance."""

        performance = self.calculate_review_performance(user_id, direction=direction)
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

    # ------------------------------------------------------------------
    # Aggregation helpers
    # ------------------------------------------------------------------
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
