"""Business logic for learner vocabulary progress."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.srs import FSRSScheduler, ReviewOutcome, SchedulerState


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
    ) -> list[QueueItem]:
        """Return due and new words for a learner."""

        now = now or datetime.now(timezone.utc)
        due_stmt = (
            select(UserVocabularyProgress)
            .options(joinedload(UserVocabularyProgress.word))
            .where(UserVocabularyProgress.user_id == user.id)
            .where(
                or_(
                    UserVocabularyProgress.due_date.is_(None),
                    UserVocabularyProgress.due_date <= now.date(),
                )
            )
            .order_by(
                UserVocabularyProgress.due_date.nullsfirst(),
                UserVocabularyProgress.created_at,
            )
            .limit(limit)
        )
        due_progress = list(self.db.scalars(due_stmt))
        items: list[QueueItem] = [QueueItem(word=progress.word, progress=progress, is_new=False) for progress in due_progress]

        if len(items) >= limit:
            return items

        words_seen_subquery = select(UserVocabularyProgress.word_id).where(
            UserVocabularyProgress.user_id == user.id
        )

        missing = limit - len(items)
        new_conditions = [not_(VocabularyWord.id.in_(words_seen_subquery))]
        if user.target_language:
            new_conditions.append(VocabularyWord.language == user.target_language)
        new_word_stmt = (
            select(VocabularyWord)
            .where(and_(*new_conditions))
            .order_by(VocabularyWord.frequency_rank)
            .limit(missing)
        )
        new_words = list(self.db.scalars(new_word_stmt))

        items.extend(QueueItem(word=word, progress=None, is_new=True) for word in new_words)
        return items

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
