"""Analytics service exposing learner progress insights."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.session import LearningSession, WordInteraction
from app.db.models.user import User
from app.services.progress import ProgressService
from app.utils.cache import cache_backend


def _duration_expr() -> Any:
    """Return a SQLAlchemy expression for session minutes."""

    return func.coalesce(
        LearningSession.actual_duration_minutes,
        LearningSession.planned_duration_minutes,
        0,
    )


def _coerce_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date payload: {value!r}")


def _iso_day(value: Any) -> str:
    return _coerce_day(value).isoformat()


@dataclass(slots=True)
class StreakStats:
    current: int
    longest: int


class AnalyticsService:
    """Aggregate learner metrics for dashboards and reports."""

    def __init__(self, db: Session, *, progress_service: ProgressService | None = None) -> None:
        self.db = db
        self.progress_service = progress_service or ProgressService(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_user_summary(self, *, user: User, days: int = 30) -> dict[str, Any]:
        """Return headline metrics for the learner dashboard."""

        key = f"{user.id}:{days}"
        cached = cache_backend.get("analytics:summary", key)
        if cached is not None:
            return cached

        duration = _duration_expr()
        session_stats = (
            self.db.query(
                func.count(LearningSession.id),
                func.coalesce(func.sum(duration), 0),
                func.avg(LearningSession.accuracy_rate),
                func.coalesce(func.sum(LearningSession.xp_earned), 0),
                func.max(LearningSession.completed_at),
            )
            .filter(LearningSession.user_id == user.id)
            .one()
        )

        total_sessions = int(session_stats[0] or 0)
        total_minutes = int(session_stats[1] or 0)
        avg_accuracy = float(session_stats[2]) if session_stats[2] is not None else None
        total_xp = int(session_stats[3] or 0)
        last_session_at = session_stats[4]

        state_counts = (
            self.db.query(
                func.coalesce(UserVocabularyProgress.state, "unknown"),
                func.count(UserVocabularyProgress.id),
            )
            .filter(UserVocabularyProgress.user_id == user.id)
            .group_by(UserVocabularyProgress.state)
            .all()
        )
        state_totals = {state: int(count or 0) for state, count in state_counts}
        words_mastered = state_totals.get("mastered", 0)
        words_learning = sum(
            count
            for state, count in state_totals.items()
            if state not in {"new", "mastered"}
        )

        now = datetime.now(timezone.utc)
        due_today = self.progress_service.count_due_reviews(user.id, now=now)
        upcoming = (
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(UserVocabularyProgress.user_id == user.id)
            .filter(
                UserVocabularyProgress.due_date.isnot(None),
            )
            .filter(UserVocabularyProgress.due_date <= (now + timedelta(days=7)).date())
            .scalar()
        )
        due_week = int(upcoming or 0)

        streaks = self._calculate_streaks(user.id)

        summary = {
            "sessions_completed": total_sessions,
            "total_minutes": total_minutes,
            "average_minutes": total_minutes / total_sessions if total_sessions else 0,
            "xp_earned": total_xp,
            "total_xp": total_xp,
            "accuracy_rate": avg_accuracy,
            "current_streak": streaks.current,
            "longest_streak": streaks.longest,
            "words_learning": words_learning,
            "words_mastered": words_mastered,
            "reviews_due_today": due_today,
            "reviews_due_week": due_week,
            "last_session_at": last_session_at,
        }

        cache_backend.set("analytics:summary", key, summary, ttl_seconds=900)
        return summary

    def get_statistics(self, *, user: User, days: int = 30) -> dict[str, Any]:
        """Return rolling statistics for the provided window."""

        key = f"{user.id}:{days}"
        cached = cache_backend.get("analytics:statistics", key)
        if cached is not None:
            return cached

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=days - 1)
        duration = _duration_expr()

        session_rows = (
            self.db.query(
                func.date(LearningSession.started_at).label("day"),
                func.avg(LearningSession.accuracy_rate).label("accuracy"),
                func.coalesce(func.sum(LearningSession.xp_earned), 0).label("xp"),
                func.coalesce(func.sum(duration), 0).label("minutes"),
            )
            .filter(LearningSession.user_id == user.id)
            .filter(LearningSession.started_at >= window_start)
            .group_by(func.date(LearningSession.started_at))
            .order_by(func.date(LearningSession.started_at))
            .all()
        )

        review_rows = (
            self.db.query(
                func.date(ReviewLog.review_date).label("day"),
                func.count(ReviewLog.id).label("count"),
            )
            .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
            .filter(UserVocabularyProgress.user_id == user.id)
            .filter(ReviewLog.review_date >= window_start)
            .group_by(func.date(ReviewLog.review_date))
            .order_by(func.date(ReviewLog.review_date))
            .all()
        )

        accuracy = [
            {"date": _iso_day(row.day), "value": float(row.accuracy or 0)}
            for row in session_rows
            if row.day is not None
        ]
        xp = [
            {"date": _iso_day(row.day), "value": int(row.xp or 0)}
            for row in session_rows
            if row.day is not None
        ]
        minutes = [
            {"date": _iso_day(row.day), "value": int(row.minutes or 0)}
            for row in session_rows
            if row.day is not None
        ]
        reviews = [
            {"date": _iso_day(row.day), "value": int(row.count or 0)}
            for row in review_rows
            if row.day is not None
        ]

        payload = {
            "accuracy": accuracy,
            "xp_earned": xp,
            "minutes_practiced": minutes,
            "reviews_completed": reviews,
        }
        cache_backend.set("analytics:statistics", key, payload, ttl_seconds=900)
        return payload

    def get_streak_info(self, *, user: User, window_days: int = 90) -> dict[str, Any]:
        """Return streak counts and calendar data for heatmaps."""

        key = f"{user.id}:{window_days}"
        cached = cache_backend.get("analytics:streak", key)
        if cached is not None:
            return cached

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=window_days - 1)

        calendar_rows = (
            self.db.query(
                func.date(LearningSession.started_at).label("day"),
                func.count(LearningSession.id).label("count"),
            )
            .filter(LearningSession.user_id == user.id)
            .filter(LearningSession.started_at >= window_start)
            .group_by(func.date(LearningSession.started_at))
            .order_by(func.date(LearningSession.started_at))
            .all()
        )

        streaks = self._calculate_streaks(user.id)
        calendar = [
            {"date": _iso_day(row.day), "completed": int(row.count or 0)}
            for row in calendar_rows
            if row.day is not None
        ]
        payload = {
            "current_streak": streaks.current,
            "longest_streak": streaks.longest,
            "calendar": calendar,
        }
        cache_backend.set("analytics:streak", key, payload, ttl_seconds=900)
        return payload

    def get_vocabulary_heatmap(self, *, user: User) -> dict[str, Any]:
        """Return counts per vocabulary state for mastery visualisations."""

        key = f"{user.id}:heatmap"
        cached = cache_backend.get("analytics:heatmap", key)
        if cached is not None:
            return cached

        rows = (
            self.db.query(
                func.coalesce(UserVocabularyProgress.state, "unknown"),
                func.count(UserVocabularyProgress.id),
            )
            .filter(UserVocabularyProgress.user_id == user.id)
            .group_by(UserVocabularyProgress.state)
            .all()
        )
        payload = {
            "total": sum(int(count or 0) for _, count in rows),
            "states": [
                {"state": state or "unknown", "count": int(count or 0)} for state, count in rows
            ],
        }
        cache_backend.set("analytics:heatmap", key, payload, ttl_seconds=900)
        return payload

    def get_error_patterns(self, *, user: User, limit: int = 10) -> dict[str, Any]:
        """Return the most common learner error types."""

        key = f"{user.id}:{limit}"
        cached = cache_backend.get("analytics:error_patterns", key)
        if cached is not None:
            return cached

        rows = (
            self.db.query(
                WordInteraction.error_type,
                func.count(WordInteraction.id).label("count"),
                func.max(WordInteraction.error_description).label("example"),
            )
            .filter(WordInteraction.user_id == user.id)
            .filter(WordInteraction.error_type.isnot(None))
            .group_by(WordInteraction.error_type)
            .order_by(func.count(WordInteraction.id).desc())
            .limit(limit)
            .all()
        )
        total = sum(int(row.count or 0) for row in rows)
        payload = {
            "total": total,
            "items": [
                {
                    "error_type": row.error_type or "unknown",
                    "count": int(row.count or 0),
                    "severity": None,
                    "example": row.example,
                }
                for row in rows
            ],
        }
        cache_backend.set("analytics:error_patterns", key, payload, ttl_seconds=900)
        return payload

    def generate_daily_snapshot(self, *, user: User, snapshot_date: date | None = None) -> AnalyticsSnapshot:
        """Persist a daily analytics snapshot for offline analysis."""

        snapshot_day = snapshot_date or datetime.now(timezone.utc).date()
        summary = self.get_user_summary(user=user)

        calendar = self.get_streak_info(user=user)
        streak_length = calendar["current_streak"]

        existing = (
            self.db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.user_id == user.id)
            .filter(AnalyticsSnapshot.snapshot_date == snapshot_day)
            .first()
        )
        snapshot = existing or AnalyticsSnapshot(user_id=user.id, snapshot_date=snapshot_day)

        snapshot.total_words_seen = summary["words_learning"] + summary["words_mastered"]
        snapshot.words_learning = summary["words_learning"]
        snapshot.words_mastered = summary["words_mastered"]
        snapshot.reviews_completed = self._reviews_on_day(user.id, snapshot_day)
        snapshot.new_words_today = self._new_words_on_day(user.id, snapshot_day)
        snapshot.average_accuracy = summary["accuracy_rate"]
        snapshot.streak_length = streak_length

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """Clear cached analytics entries for the learner."""

        prefix = f"{user_id}:"
        for namespace in (
            "analytics:summary",
            "analytics:statistics",
            "analytics:streak",
            "analytics:heatmap",
            "analytics:error_patterns",
        ):
            cache_backend.invalidate(namespace, prefix=prefix)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _calculate_streaks(self, user_id: uuid.UUID) -> StreakStats:
        dates = (
            self.db.query(func.date(LearningSession.started_at))
            .filter(LearningSession.user_id == user_id)
            .filter(LearningSession.started_at.isnot(None))
            .distinct()
            .all()
        )
        day_set = {_coerce_day(row[0]) for row in dates if row[0] is not None}
        if not day_set:
            return StreakStats(current=0, longest=0)

        today = datetime.now(timezone.utc).date()
        current = 0
        check_day = today
        while check_day in day_set:
            current += 1
            check_day -= timedelta(days=1)

        sorted_days = sorted(day_set)
        longest = 1
        streak = 1
        for previous, current_day in zip(sorted_days, sorted_days[1:]):
            if current_day - previous == timedelta(days=1):
                streak += 1
            else:
                longest = max(longest, streak)
                streak = 1
        longest = max(longest, streak)
        return StreakStats(current=current, longest=longest)

    def _reviews_on_day(self, user_id: uuid.UUID, snapshot_day: date) -> int:
        count = (
            self.db.query(func.count(ReviewLog.id))
            .join(UserVocabularyProgress, ReviewLog.progress_id == UserVocabularyProgress.id)
            .filter(UserVocabularyProgress.user_id == user_id)
            .filter(func.date(ReviewLog.review_date) == snapshot_day)
            .scalar()
        )
        return int(count or 0)

    def _new_words_on_day(self, user_id: uuid.UUID, snapshot_day: date) -> int:
        rows = (
            self.db.query(
                func.date(LearningSession.started_at).label("day"),
                func.coalesce(func.sum(LearningSession.new_words_introduced), 0),
            )
            .filter(LearningSession.user_id == user_id)
            .filter(func.date(LearningSession.started_at) == snapshot_day)
            .group_by(func.date(LearningSession.started_at))
            .first()
        )
        return int(rows[1]) if rows else 0


__all__ = ["AnalyticsService"]
