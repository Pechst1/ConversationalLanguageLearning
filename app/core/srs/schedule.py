"""One spaced-repetition scheduler for everything that is not a vocabulary card.

WP-24. Before this module the learner's mistakes and their grammar concepts were
scheduled by hand-written day lookups — ``error_memory._next_review`` returned
1/3/14 days from a severity branch, and ``grammar.calculate_next_review``
returned 1/3/7/14/30 days from a five-branch score table — while the real SM-2
implementation in :mod:`app.core.srs.sm2` was imported by nothing.

The lookups have two properties a scheduler must not have: an item that has been
repaired ten times is scheduled exactly like one repaired once, and a lapse
costs nothing, because no ease is carried. This module carries both: reps grow
the interval through the SM-2 ease factor, and a failure resets the interval and
lowers the ease.

It is deliberately a *pure function over a state tuple*: the caller owns the
storage. ``UserError`` persists ``ease_factor``/``scheduled_days``;
``UserGrammarProgress`` has no such column and derives the previous interval
from ``last_review``/``next_review``. Both get the same curve.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.core.srs.sm2 import (
    DEFAULT_EASE_FACTOR,
    MIN_EASE_FACTOR,
    review_card,
)

#: The phases ``review_card`` speaks. ``new``/``learn`` are pre-graduation,
#: ``review`` is graduated, ``relearn`` is a lapse being repaired.
Phase = str

#: A failed review never schedules further out than this.
LAPSE_INTERVAL_DAYS = 1

#: The scheduler never returns a same-instant due date: a repaired item has to
#: leave today, or the "due" queue would hand it straight back.
MIN_INTERVAL_MINUTES = 10


@dataclass(frozen=True, slots=True)
class ScheduleState:
    """What the caller has stored about this item's schedule so far."""

    reps: int = 0
    lapses: int = 0
    interval_days: int = 0
    ease_factor: float = DEFAULT_EASE_FACTOR
    phase: Phase = "new"

    def normalized(self) -> ScheduleState:
        ease = float(self.ease_factor or DEFAULT_EASE_FACTOR)
        return ScheduleState(
            reps=max(0, int(self.reps or 0)),
            lapses=max(0, int(self.lapses or 0)),
            interval_days=max(0, int(self.interval_days or 0)),
            ease_factor=max(MIN_EASE_FACTOR, ease),
            phase=self.phase if self.phase in {"new", "learn", "review", "relearn"} else "new",
        )


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    """The scheduler's answer: when, and the state to persist with it."""

    due_at: dt.datetime
    interval_days: int
    ease_factor: float
    reps: int
    lapses: int
    phase: Phase

    @property
    def is_lapse(self) -> bool:
        return self.phase == "relearn"


def quality_from_score(score_0_10: float) -> int:
    """Map a 0–10 review score onto SM-2's 0–4 quality rating.

    Five is the pass mark everywhere else in the product (a concept is credited
    at >= 5.0), so five is a *pass* here too — "Good", not a lapse. Nine and
    above is "Easy". Below five the review failed, mildly (3-4) or plainly.
    """

    score = max(0.0, min(10.0, float(score_0_10 or 0.0)))
    if score >= 9:
        return 4
    if score >= 5:
        return 3
    if score >= 3:
        return 1
    return 0


def schedule_next(
    *,
    now: dt.datetime,
    quality: int,
    state: ScheduleState | None = None,
    min_interval_days: int = 0,
) -> ScheduleDecision:
    """Schedule one item after a review graded ``quality`` (0–4).

    ``min_interval_days`` is a floor for callers who never want sub-day steps
    (the errata queue is a daily surface; it has no use for a ten-minute step).
    """

    current = (state or ScheduleState()).normalized()
    quality = max(0, min(4, int(quality)))
    due_at, phase, _step, ease, interval_days = review_card(
        now=now,
        phase=current.phase,
        interval_days=current.interval_days,
        ease_factor=current.ease_factor,
        step_index=0,
        quality=quality,
    )
    reps = current.reps + 1
    lapses = current.lapses + (1 if quality < 3 else 0)

    if phase == "review" and current.phase in {"new", "learn"}:
        # `sm2.review_card` reports the *graduating* interval (1) for a card
        # that left the learning steps, even when it granted the easy interval
        # of four days in `due_time`. Read the interval off the due date it
        # actually returned, or an easy first review would be filed for tomorrow.
        interval_days = max(1, (due_at - now).days)

    floor_days = max(int(min_interval_days or 0), 0)
    if floor_days >= 1 and phase == "learn" and quality >= 3:
        # A daily surface has no use for SM-2's one- and ten-minute learning
        # steps: the learner is not coming back this afternoon. A successful
        # first review graduates straight to the day scale.
        phase = "review"
        interval_days = 4 if quality >= 4 else 1
    if phase == "relearn":
        # A lapse is a lapse: back to a single day, whatever the sub-day step
        # said. Errata and grammar concepts are reviewed inside a daily loop.
        interval_days = LAPSE_INTERVAL_DAYS
    if floor_days and interval_days < floor_days:
        interval_days = floor_days
    if interval_days > 0:
        due_at = now + dt.timedelta(days=interval_days)
    elif due_at <= now + dt.timedelta(minutes=MIN_INTERVAL_MINUTES):
        due_at = now + dt.timedelta(minutes=MIN_INTERVAL_MINUTES)

    return ScheduleDecision(
        due_at=due_at,
        interval_days=int(interval_days),
        ease_factor=float(ease),
        reps=reps,
        lapses=lapses,
        phase=phase,
    )


#: The seed intervals a first review grants, by score band. Historic values,
#: kept so WP-24 re-dates nothing that already exists.
_SEED_INTERVAL_DAYS = ((9.0, 30), (7.0, 14), (5.0, 7), (3.0, 3))


def _seed_interval(score_0_10: float) -> dt.timedelta:
    score = max(0.0, min(10.0, float(score_0_10 or 0.0)))
    for threshold, days in _SEED_INTERVAL_DAYS:
        if score >= threshold:
            return dt.timedelta(days=days)
    return dt.timedelta(days=1)


def interval_for_score(
    score_0_10: float,
    *,
    previous_interval_days: int = 0,
    reps: int = 0,
    ease_factor: float | None = None,
) -> dt.timedelta:
    """SM-2 interval for a 0–10 scored review, as a :class:`~datetime.timedelta`.

    The drop-in replacement for the five-branch grammar lookup: same call shape,
    a curve that remembers. With no history at all (``reps=0``) the first
    interval is the graduating one, so a brand-new concept behaves as before.
    """

    if not (reps and previous_interval_days):
        # First review of this concept: keep the interval the product has always
        # granted (the Excel tracker's seed table). SM-2 has no history to work
        # from here either, and changing the first step would re-date every
        # concept a learner has ever met for no measurement gain. Every review
        # after this one compounds through the ease factor instead.
        return _seed_interval(score_0_10)

    now = dt.datetime.now(dt.UTC)
    phase = "review"
    decision = schedule_next(
        now=now,
        quality=quality_from_score(score_0_10),
        state=ScheduleState(
            reps=int(reps or 0),
            interval_days=int(previous_interval_days or 0),
            ease_factor=float(ease_factor or DEFAULT_EASE_FACTOR),
            phase=phase,
        ),
        min_interval_days=1,
    )
    return dt.timedelta(days=decision.interval_days)


__all__ = [
    "LAPSE_INTERVAL_DAYS",
    "MIN_INTERVAL_MINUTES",
    "Phase",
    "ScheduleDecision",
    "ScheduleState",
    "interval_for_score",
    "quality_from_score",
    "schedule_next",
]
