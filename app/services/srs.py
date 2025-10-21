"""FSRS-inspired scheduling helpers.

This module implements a lightweight variant of the Free Spaced Repetition
Scheduler (FSRS) tailored for vocabulary reviews. The goal is to provide a
deterministic scheduling algorithm that reacts to learner feedback while
keeping the implementation approachable for unit testing.

The scheduler operates on the stability/difficulty fields stored on the
``UserVocabularyProgress`` model. A successful review increases stability and
pushes the next review further into the future, while failed reviews reset the
interval and bump the difficulty.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(slots=True)
class SchedulerState:
    """State parameters required by the scheduler."""

    stability: float
    difficulty: float
    reps: int
    lapses: int
    scheduled_days: int
    state: str


@dataclass(slots=True)
class ReviewOutcome:
    """Result returned after processing a review."""

    stability: float
    difficulty: float
    scheduled_days: int
    elapsed_days: int
    state: str
    next_review: datetime


class FSRSScheduler:
    """A condensed FSRS-like scheduler used for vocabulary reviews."""

    request_retention: float = 0.9

    def __init__(self, *, maximum_interval_days: int = 365) -> None:
        self.maximum_interval_days = maximum_interval_days

    @staticmethod
    def _ensure_timezone(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _initial_interval(self, rating: int) -> timedelta:
        """Return an initial interval for new vocabulary."""

        if rating <= 0:
            return timedelta(minutes=10)
        if rating == 1:
            return timedelta(days=1)
        if rating == 2:
            return timedelta(days=3)
        return timedelta(days=4)

    def _adjust_existing(self, state: SchedulerState, rating: int) -> tuple[float, float, int, str]:
        """Adjust difficulty/stability for an existing card."""

        previous_stability = max(0.1, state.stability or 0.1)
        previous_difficulty = state.difficulty or 5.0

        if rating <= 0:
            # Complete lapse, reset the card.
            new_state = "relearning"
            difficulty = self._clamp(previous_difficulty + 1.0, 1.0, 10.0)
            stability = max(0.2, previous_stability * 0.2)
            scheduled_days = 0
        elif rating == 1:
            new_state = "relearning"
            difficulty = self._clamp(previous_difficulty + 0.4, 1.0, 10.0)
            stability = max(0.3, previous_stability * 0.7)
            scheduled_days = max(1, round(stability))
        elif rating == 2:
            new_state = "reviewing"
            difficulty = self._clamp(previous_difficulty - 0.1, 1.0, 10.0)
            stability = min(
                self.maximum_interval_days,
                previous_stability * 1.3 + 1.0,
            )
            scheduled_days = max(1, round(stability))
        else:
            new_state = "reviewing"
            difficulty = self._clamp(previous_difficulty - 0.4, 1.0, 10.0)
            stability = min(
                self.maximum_interval_days,
                previous_stability * 1.6 + 1.5,
            )
            scheduled_days = max(1, round(stability * 1.1))

        return stability, difficulty, scheduled_days, new_state

    def review(
        self,
        *,
        state: SchedulerState,
        rating: int,
        last_review_at: datetime | None,
        now: datetime | None = None,
    ) -> ReviewOutcome:
        """Return a review outcome based on the supplied state and rating."""

        if rating < 0 or rating > 3:
            raise ValueError("Rating must be between 0 and 3 inclusive")

        now = self._ensure_timezone(now or datetime.now(timezone.utc))
        last_review_at = self._ensure_timezone(last_review_at)

        elapsed_days = 0
        if last_review_at is not None:
            elapsed_days = max(0, (now - last_review_at).days)

        if state.reps <= 0:
            interval = self._initial_interval(rating)
            stability = min(self.maximum_interval_days, max(interval.days, 0.3))
            difficulty = self._clamp(5.0 - rating * 0.5, 1.0, 10.0)
            scheduled_days = max(0, interval.days)
            new_state = "learning" if rating <= 1 else "reviewing"
        else:
            stability, difficulty, scheduled_days, new_state = self._adjust_existing(state, rating)
            interval = timedelta(days=scheduled_days)
            if scheduled_days == 0:
                interval = timedelta(minutes=10)

        next_review = now + interval
        return ReviewOutcome(
            stability=stability,
            difficulty=difficulty,
            scheduled_days=scheduled_days,
            elapsed_days=elapsed_days,
            state=new_state,
            next_review=next_review,
        )
