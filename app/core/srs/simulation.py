"""A seeded learner simulation over the one memory model (WP-L3).

The numbers it produces are the input for WP-L6's intake throttle: how many
reviews a day each new item per day costs once the schedule has settled.

The learner is deliberately simple — a fixed accuracy, no forgetting curve — so
the result isolates the *scheduler's* load:

* one new item per day (``new_per_day``) is introduced the way §2.4 introduces a
  concept: a guided Essai item, then its use in the reply (Emploi);
* every due item is reviewed on its due day, with a Rappel format that scales
  with its stability (WP-L4: recognise under 3 days, guided under 7, transform
  under 15, free production above);
* each observation is correct with probability ``accuracy``; an error in
  production is a lapse, an error in an easier format a Hard.

The ``rated`` profile replays the same learner on self-graded cards (right →
Good, wrong → Again), the vocabulary-style baseline.
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass, field

from app.core.srs.memory import (
    MAX_INTERVAL_DAYS,
    Evidence,
    EvidenceFormat,
    MemoryState,
    Rating,
    review,
)

SIMULATION_START = dt.datetime(2026, 1, 5, 8, 0, tzinfo=dt.UTC)


def rappel_format(stability: float) -> EvidenceFormat:
    """The Rappel format a concept of this stability gets (WP-L4's ladder)."""

    if stability < 3:
        return EvidenceFormat.RECOGNISE
    if stability < 7:
        return EvidenceFormat.GUIDED
    if stability < 15:
        return EvidenceFormat.TRANSFORM
    return EvidenceFormat.PRODUCE


@dataclass
class SimulatedItem:
    introduced_day: int
    state: MemoryState = field(default_factory=MemoryState)
    due_day: int = 0
    review_days: list[int] = field(default_factory=list)
    intervals: list[int] = field(default_factory=list)
    #: One per observation, aligned with ``intervals``: was it correct, a lapse.
    outcomes: list[bool] = field(default_factory=list)
    lapses_at: list[bool] = field(default_factory=list)
    lapse_days: list[int] = field(default_factory=list)


@dataclass
class SimulationResult:
    accuracy: float
    profile: str
    days: int
    new_per_day: int
    reviews_per_day: list[int]
    items: list[SimulatedItem]
    steady_window: tuple[int, int]

    @property
    def steady_state_reviews_per_day(self) -> float:
        start, end = self.steady_window
        window = self.reviews_per_day[start:end]
        return sum(window) / max(1, len(window))

    @property
    def load_per_new_item(self) -> float:
        """Reviews a day per new item a day, in the steady window."""

        return self.steady_state_reviews_per_day / max(1, self.new_per_day)

    @property
    def max_gap_days(self) -> int:
        gaps = [
            later - earlier
            for item in self.items
            for earlier, later in zip(item.review_days, item.review_days[1:], strict=False)
        ]
        return max(gaps, default=0)

    @property
    def total_lapses(self) -> int:
        return sum(len(item.lapse_days) for item in self.items)


def simulate_learner(
    accuracy: float,
    *,
    days: int = 120,
    new_per_day: int = 1,
    seed: int = 20260923,
    profile: str = "grammar",
    steady_window: tuple[int, int] | None = None,
) -> SimulationResult:
    rng = random.Random(f"{seed}:{accuracy}:{profile}")  # noqa: S311 - a seeded simulation
    items: list[SimulatedItem] = []
    reviews_per_day = [0] * days

    def observe(item: SimulatedItem, day: int, fmt: EvidenceFormat) -> None:
        correct = rng.random() < accuracy
        if profile == "rated":
            evidence = Evidence.rated(Rating.GOOD if correct else Rating.AGAIN)
        else:
            evidence = Evidence(fmt, correct=correct)
        decision = review(item.state, evidence, now=SIMULATION_START + dt.timedelta(days=day))
        if decision is None:  # pragma: no cover - only a mention returns None
            raise RuntimeError("a graded observation must schedule")
        item.state = MemoryState(
            stability=decision.stability,
            difficulty=decision.difficulty,
            reps=decision.reps,
            lapses=decision.lapses,
        )
        item.due_day = day + decision.interval_days
        item.intervals.append(decision.interval_days)
        item.outcomes.append(correct)
        item.lapses_at.append(decision.is_lapse)
        if decision.is_lapse:
            item.lapse_days.append(day)

    for day in range(days):
        for item in items:
            if item.due_day <= day:
                reviews_per_day[day] += 1
                item.review_days.append(day)
                observe(item, day, rappel_format(item.state.stability))
        for _ in range(new_per_day):
            item = SimulatedItem(introduced_day=day)
            item.review_days.append(day)
            observe(item, day, EvidenceFormat.GUIDED)  # Essai
            observe(item, day, EvidenceFormat.PRODUCE)  # Emploi, same day
            items.append(item)

    window = steady_window or (max(0, days - 30), days)
    return SimulationResult(
        accuracy=accuracy,
        profile=profile,
        days=days,
        new_per_day=new_per_day,
        reviews_per_day=reviews_per_day,
        items=items,
        steady_window=window,
    )


__all__ = [
    "MAX_INTERVAL_DAYS",
    "SimulatedItem",
    "SimulationResult",
    "rappel_format",
    "simulate_learner",
]
