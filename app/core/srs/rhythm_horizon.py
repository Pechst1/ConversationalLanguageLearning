"""WP-L9 — the 126-day harness, per rhythm: what a day costs and what it buys.

One seeded learner per (rhythm, accuracy) walks the sub-bands A1.1 → A1.2 → …
for :data:`HORIZON_DAYS` days on the app's own rules:

* **intake** — the rhythm's §2.2 plan (new words a day, new units a week, the
  same numbers as ``level_forecast.PRIOR_INTAKE`` and
  ``concept_life.NEW_CONCEPTS_PER_WEEK``), multiplied every morning by the
  **auto-throttle** (:func:`app.services.intake_throttle.decide`, the rule the
  app runs: backlog of the morning's due items vs one day of review capacity,
  and 7-day word-review accuracy, with its hysteresis);
* **memory** — every due item is reviewed on its day through the one memory
  model (:func:`app.core.srs.memory.review`): units in a Rappel format that
  grows with stability, words as self-rated cards; each answer is right with
  probability ``accuracy``;
* **held / known** — units reach «Tenue» through the app's own bookkeeping
  (``concept_life.note_concept_evidence``); a word is known when seen twice,
  last answer right and retrievability ≥ 0.85 (WP-L7);
* **the level** — a band closes when 85 % of its units are held and 80 % of its
  words known, plus one day for its épreuve (passed first time); the next band
  opens. Intake runs ahead into the next band's material once the current
  band's is all introduced. The shown level is WP-L7's «A1.1 · 60 %».

Costs (per day):

* **reviews** — every item due that day (the review load);
* **review seconds** — words 6 s (the word drill), units 40 s (a Rappel item);
* **minutes** — the séance's planned minutes (the real planner at the prior
  pace, passed in: ``seance_seconds``) plus whatever the reviews need beyond
  the Rappel's 35 % share, which spills into the word drill;
* **graded interactions** — the séance's (passed in) plus the spilled reviews.

Pure: no database. The planner numbers come from the caller.
"""
from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass, field
from types import SimpleNamespace

from app.core.srs.memory import Evidence, EvidenceFormat, MemoryState, Rating, review
from app.core.srs.simulation import (
    _WORD_KNOWN_R,
    SIMULATION_START,
    _retrievability,
    new_unit_life,
    note_unit_life,
    rappel_format,
)

HORIZON_DAYS = 126
CHECKPOINTS = (30, 60, 90, 126)
ACCURACIES = (0.70, 0.85, 0.95)

#: §2.2: (new words a day, new units a week).
RHYTHM_INTAKE: dict[str, tuple[float, float]] = {
    "leger": (2.0, 1.0),
    "regulier": (4.0, 2.0),
    "soutenu": (8.0, 3.0),
    "intensif": (12.0, 4.0),
}
RHYTHM_BUDGET: dict[str, int] = {"leger": 300, "regulier": 600, "soutenu": 1200, "intensif": 1800}

WORD_REVIEW_SECONDS = 6
UNIT_REVIEW_SECONDS = 40
UNITS_SHARE = 0.85
WORDS_SHARE = 0.80
CHECKPOINT_DAYS = 1


@dataclass
class _Item:
    band: int
    introduced: int
    state: MemoryState = field(default_factory=MemoryState)
    due: int = 0
    last: int = 0
    last_correct: bool = False
    life: SimpleNamespace | None = None

    @property
    def held(self) -> bool:
        return getattr(self.life, "held_at", None) is not None

    def known(self, day: int) -> bool:
        return (
            self.state.reps >= 2
            and self.last_correct
            and _retrievability(self.state.stability, day - self.last) >= _WORD_KNOWN_R
        )


@dataclass
class HorizonDay:
    day: int
    band: str
    percent: int
    reviews: int
    review_seconds: int
    new_words: int
    new_units: int
    throttled: bool


@dataclass
class RhythmHorizon:
    rhythm: str
    accuracy: float
    days: list[HorizonDay]
    bands_closed: list[tuple[str, int]]
    seance_seconds: int
    seance_graded: int

    @property
    def rappel_seconds(self) -> float:
        return 0.35 * RHYTHM_BUDGET[self.rhythm]

    def _mean(self, values: list[float]) -> float:
        return sum(values) / max(1, len(values))

    def spill_seconds(self, day: HorizonDay) -> float:
        return max(0.0, day.review_seconds - self.rappel_seconds)

    @property
    def minutes_per_day(self) -> float:
        return (self.seance_seconds + self._mean([self.spill_seconds(d) for d in self.days])) / 60

    @property
    def graded_per_day(self) -> float:
        spilled = [
            self.spill_seconds(d) / (d.review_seconds / d.reviews) if d.reviews else 0.0 for d in self.days
        ]
        return self.seance_graded + self._mean(spilled)

    @property
    def new_items_per_day(self) -> float:
        return self._mean([d.new_words + d.new_units for d in self.days])

    @property
    def new_words_per_day(self) -> float:
        return self._mean([d.new_words for d in self.days])

    @property
    def units_per_week(self) -> float:
        return 7 * self._mean([d.new_units for d in self.days])

    def reviews_per_day(self, start: int = 0, end: int | None = None) -> float:
        window = self.days[start:end]
        return self._mean([d.reviews for d in window])

    @property
    def throttled_share(self) -> float:
        return self._mean([1.0 if d.throttled else 0.0 for d in self.days])

    def level_at(self, day: int) -> str:
        entry = self.days[min(day, len(self.days)) - 1]
        return f"{entry.band} · {entry.percent} %"


def _percent(units_held: int, units_required: int, words_known: int, words_required: int, has_words: bool) -> int:
    parts = [(0.45, min(1.0, units_held / max(1, units_required)))]
    if has_words:
        parts.append((0.45, min(1.0, words_known / max(1, words_required))))
    weight = sum(w for w, _ in parts)
    share = sum(w * v for w, v in parts) / weight * 0.9
    return max(0, min(100, int(math.floor(share * 100 + 1e-9))))


def simulate_rhythm_horizon(
    rhythm: str,
    accuracy: float,
    *,
    bands: list[tuple[str, int, int]],
    seance_seconds: int,
    seance_graded: int,
    days: int = HORIZON_DAYS,
    seed: int = 20260924,
) -> RhythmHorizon:
    """``bands``: ``[(label, units_total, words_total), …]`` in teaching order."""

    from app.services.intake_throttle import ThrottleSignals, decide

    rng = random.Random(f"horizon:{seed}:{rhythm}:{accuracy}")  # noqa: S311 - seeded
    words_per_day, units_per_week = RHYTHM_INTAKE[rhythm]
    capacity = 0.35 * RHYTHM_BUDGET[rhythm] + words_per_day * 10 * WORD_REVIEW_SECONDS
    units: list[_Item] = []
    words: list[_Item] = []
    word_log: list[tuple[int, bool]] = []
    history: list[HorizonDay] = []
    closed: list[tuple[str, int]] = []
    current = 0
    epreuve_day: int | None = None
    throttle_on, since = False, None
    unit_credit = word_credit = 0.0

    def observe(item: _Item, day: int, evidence: Evidence) -> None:
        decision = review(item.state, evidence, now=SIMULATION_START + dt.timedelta(days=day))
        if decision is None:  # pragma: no cover - a graded observation always schedules
            raise RuntimeError("a graded observation must schedule")
        item.state = MemoryState(
            stability=decision.stability,
            difficulty=decision.difficulty,
            reps=decision.reps,
            lapses=decision.lapses,
        )
        item.due = day + decision.interval_days
        item.last = day
        if item.life is not None:
            note_unit_life(item.life, evidence, day=day)

    def introduced_in(pool: list[_Item], band: int) -> int:
        return sum(1 for item in pool if item.band == band)

    def next_band_for(pool: list[_Item], index: int) -> int | None:
        for band in range(current, len(bands)):
            if introduced_in(pool, band) < bands[band][index]:
                return band
        return None

    for day in range(days):
        now = SIMULATION_START + dt.timedelta(days=day)
        due_units = [item for item in units if item.due <= day]
        due_words = [item for item in words if item.due <= day]
        backlog = len(due_units) * UNIT_REVIEW_SECONDS + len(due_words) * WORD_REVIEW_SECONDS
        recent = [ok for (at, ok) in word_log if day - 7 < at <= day]
        accuracy_7d = (sum(recent) / len(recent)) if len(recent) >= 20 else None
        signals = ThrottleSignals(
            backlog_seconds=backlog,
            capacity_seconds=int(capacity),
            backlog_days=backlog / capacity,
            due_counts={},
            accuracy=accuracy_7d,
            reviews=len(recent),
        )
        active, _ = decide(signals, was_active=throttle_on, since=since, now=now)
        if active != throttle_on:
            since = now if active else None
        throttle_on = active
        factor = 0.5 if throttle_on else 1.0

        for item in due_units:
            correct = rng.random() < accuracy
            observe(item, day, Evidence(rappel_format(item.state.stability), correct=correct))
            item.last_correct = correct
        for item in due_words:
            correct = rng.random() < accuracy
            observe(item, day, Evidence.rated(Rating.GOOD if correct else Rating.AGAIN))
            item.last_correct = correct
            word_log.append((day, correct))

        unit_credit += units_per_week / 7.0 * factor
        word_credit += words_per_day * factor
        new_units = new_words = 0
        while unit_credit >= 1.0 - 1e-9:
            band = next_band_for(units, 1)
            if band is None:
                break
            unit_credit -= 1.0
            item = _Item(band=band, introduced=day, life=new_unit_life())
            for fmt in (EvidenceFormat.GUIDED, EvidenceFormat.PRODUCE):
                correct = rng.random() < accuracy
                observe(item, day, Evidence(fmt, correct=correct))
                item.last_correct = correct
            units.append(item)
            new_units += 1
        while word_credit >= 1.0 - 1e-9:
            band = next_band_for(words, 2)
            if band is None:
                break
            word_credit -= 1.0
            item = _Item(band=band, introduced=day)
            correct = rng.random() < accuracy
            observe(item, day, Evidence.rated(Rating.GOOD if correct else Rating.AGAIN))
            item.last_correct = correct
            word_log.append((day, correct))
            words.append(item)
            new_words += 1

        # The level: the band in force, its coverage, its épreuve.
        label, units_total, words_total = bands[current]
        units_required = math.ceil(units_total * UNITS_SHARE)
        words_required = math.ceil(words_total * WORDS_SHARE)
        held = sum(1 for item in units if item.band == current and item.held)
        known = sum(1 for item in words if item.band == current and item.known(day))
        met = held >= units_required and (words_total == 0 or known >= words_required)
        if met and epreuve_day is None:
            epreuve_day = day + CHECKPOINT_DAYS
        percent = _percent(held, units_required, known, words_required, words_total > 0)
        if epreuve_day is not None and day >= epreuve_day and current + 1 < len(bands):
            closed.append((label, day))
            current += 1
            epreuve_day = None
            label = bands[current][0]
            percent = 0
        history.append(
            HorizonDay(
                day=day,
                band=label,
                percent=percent,
                reviews=len(due_units) + len(due_words),
                review_seconds=backlog,
                new_words=new_words,
                new_units=new_units,
                throttled=throttle_on,
            )
        )
    return RhythmHorizon(
        rhythm=rhythm,
        accuracy=accuracy,
        days=history,
        bands_closed=closed,
        seance_seconds=seance_seconds,
        seance_graded=seance_graded,
    )


def render_table(results: list[RhythmHorizon]) -> str:
    """The Markdown table the learning WP doc carries (WP-L9 Status)."""

    head = (
        "| Rhythm | Acc. | Min/day | Graded/day | New words/day | New units/wk | Reviews/day (d 90–126) "
        "| Throttled | Day 30 | Day 60 | Day 90 | Day 126 |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    )
    rows = []
    for result in results:
        rows.append(
            f"| {result.rhythm} | {int(round(result.accuracy * 100))} % | {result.minutes_per_day:.1f} | {result.graded_per_day:.0f} | {result.new_words_per_day:.1f} | {result.units_per_week:.1f} | {result.reviews_per_day(90, 126):.0f} "
            f"| {100 * result.throttled_share:.0f} % | {result.level_at(30)} | {result.level_at(60)} | {result.level_at(90)} | {result.level_at(126)} |"
        )
    return "\n".join([head, *rows])


__all__ = [
    "ACCURACIES",
    "CHECKPOINTS",
    "HORIZON_DAYS",
    "RHYTHM_INTAKE",
    "HorizonDay",
    "RhythmHorizon",
    "render_table",
    "simulate_rhythm_horizon",
]
