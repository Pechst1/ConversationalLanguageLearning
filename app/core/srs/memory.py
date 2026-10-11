"""One memory model for grammar concepts and errata (WP-L3).

Vocabulary has always been scheduled by the FSRS-style scheduler in
:mod:`app.services.srs` — per-item *stability* (days until recall drops to the
requested retention of 0.9) and *difficulty* (1–10), moved by a 0–3 rating.
Grammar and errata ran on SM-2 with a first-review seed table and an ease that
grammar never stored. This module puts both on the vocabulary model:

* the same rating scale (0 Again, 1 Hard, 2 Good, 3 Easy);
* the same stability / difficulty moves as ``FSRSScheduler._adjust_existing``
  (Good: ``S·1.3 + 1``, Easy: ``S·1.6 + 1.5``, Hard: ``S·0.7``, Again:
  ``S·0.2``) — *delegated* to it, not copied;
* the same retention target, so the interval is the stability in days.

What grammar needs on top is **evidence weight**. A concept is not a flash card
the learner grades: it is observed through formats that prove different amounts.
Tapping the right option proves less than building the sentence, which proves
less than transforming one, which proves less than using the form unprompted in
a reply. :func:`grade_evidence` is the one mapping from an observation to a
rating plus a weight; the weight scales how much of the rating's stability gain
this observation can buy. A failure is not weighted: an error in production is a
lapse (Again), an error in any easier format is a Hard (the memory is shaken, not
lost).

``MAX_INTERVAL_DAYS`` is the other difference: a held concept keeps coming back,
at least every 60 days, however strong it is (WP-L3 §5 / §2.4 «Tenue»).

The module is pure: callers own the storage and the transaction.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from enum import IntEnum, StrEnum

from app.services.srs import FSRSScheduler, SchedulerState

#: A concept or erratum never waits longer than this between reviews.
MAX_INTERVAL_DAYS = 60

#: Stability is memory strength and may outgrow the interval cap, but not this.
MAX_STABILITY_DAYS = 365.0

#: A lapse comes back tomorrow: grammar and errata live in a daily loop, the
#: vocabulary scheduler's ten-minute relearning step has no surface here.
LAPSE_INTERVAL_DAYS = 1

DEFAULT_DIFFICULTY = 5.0


class Rating(IntEnum):
    """The vocabulary scheduler's scale (``app.services.srs``)."""

    AGAIN = 0
    HARD = 1
    GOOD = 2
    EASY = 3


class EvidenceFormat(StrEnum):
    """How a concept was observed, weakest first.

    ``MENTION`` is exposure — the form appeared in a scene or was used in
    passing without being asked for. It is recorded, never scheduled.
    ``RATED`` is a self-graded Rappel card (the daily-practice «Encore / Difficile
    / Bien / Facile» buttons): the learner gave the rating directly.
    """

    MENTION = "mention"
    RECOGNISE = "recognise"  # choice, classify, fill-with-options
    GUIDED = "guided"  # tiles, word bank, build
    TRANSFORM = "transform"  # rewrite a given sentence into the target form
    PRODUCE = "produce"  # free production (a reply, a written/spoken line)
    RATED = "rated"


#: The evidence ladder. ``assisted`` moves one step down it.
FORMAT_STEP: dict[EvidenceFormat, int] = {
    EvidenceFormat.RECOGNISE: 1,
    EvidenceFormat.GUIDED: 2,
    EvidenceFormat.TRANSFORM: 3,
    EvidenceFormat.PRODUCE: 4,
}

#: A correct observation at each ladder step: (rating, weight on its gain).
#: Step 0 is "recognise, with help".
SUCCESS_BY_STEP: dict[int, tuple[Rating, float]] = {
    0: (Rating.GOOD, 0.25),
    1: (Rating.GOOD, 0.5),
    2: (Rating.GOOD, 1.0),
    3: (Rating.EASY, 0.75),
    4: (Rating.EASY, 1.0),
}

#: The stability (days) a *first* correct observation grants, by ladder step.
#: Monotone, and ≥ 1 day: nothing new comes back the same afternoon.
FIRST_STABILITY_BY_STEP: dict[int, float] = {0: 1.0, 1: 1.5, 2: 2.0, 3: 3.0, 4: 4.0}

#: A first failed observation: a lapse starts at a day, a shaky Hard at one too.
FIRST_FAILURE_STABILITY = 0.5


#: Exercise / round names across surfaces → the evidence ladder. One table, so
#: the Atelier, the journey and the Rappel agree on what a format proves.
FORMAT_BY_NAME: dict[str, EvidenceFormat] = {
    # recognise: pick or sort among given options
    "choice": EvidenceFormat.RECOGNISE,
    "multiple_choice": EvidenceFormat.RECOGNISE,
    "classify": EvidenceFormat.RECOGNISE,
    "fill": EvidenceFormat.RECOGNISE,  # Atelier «fill» offers choices
    "recognize": EvidenceFormat.RECOGNISE,
    "recognise": EvidenceFormat.RECOGNISE,
    # guided: assemble the form from given pieces
    "tiles": EvidenceFormat.GUIDED,
    "word_bank": EvidenceFormat.GUIDED,
    "build": EvidenceFormat.GUIDED,
    "guided": EvidenceFormat.GUIDED,
    # transform: rewrite a given sentence into the target form
    "transform": EvidenceFormat.TRANSFORM,
    "short_answer": EvidenceFormat.TRANSFORM,
    "repair": EvidenceFormat.TRANSFORM,
    # production: the learner's own line
    "produce": EvidenceFormat.PRODUCE,
    "sentence": EvidenceFormat.PRODUCE,
    "speak": EvidenceFormat.PRODUCE,
    "conversation": EvidenceFormat.PRODUCE,
    "reply": EvidenceFormat.PRODUCE,
}


def format_for_name(*names: str | None) -> EvidenceFormat | None:
    """The evidence format of the first name the table knows (mode before round)."""

    for name in names:
        key = str(name or "").strip().lower()
        if key in FORMAT_BY_NAME:
            return FORMAT_BY_NAME[key]
    return None


@dataclass(frozen=True, slots=True)
class Evidence:
    """One observation of a concept (or an erratum repair)."""

    format: EvidenceFormat
    correct: bool = True
    assisted: bool = False
    #: Only for ``RATED``: the learner's own 0–3 rating.
    rating: int | None = None

    @classmethod
    def mention(cls) -> Evidence:
        return cls(EvidenceFormat.MENTION)

    @classmethod
    def rated(cls, rating: int) -> Evidence:
        rating = max(0, min(3, int(rating)))
        return cls(EvidenceFormat.RATED, correct=rating >= Rating.GOOD, rating=rating)

    @classmethod
    def from_score(cls, score_0_10: float, *, fmt: EvidenceFormat = EvidenceFormat.RATED) -> Evidence:
        """A legacy 0–10 score (five is the pass mark everywhere in the product)."""

        score = max(0.0, min(10.0, float(score_0_10 or 0.0)))
        if fmt is EvidenceFormat.RATED:
            if score >= 9:
                return cls.rated(Rating.EASY)
            if score >= 5:
                return cls.rated(Rating.GOOD)
            if score >= 3:
                return cls.rated(Rating.HARD)
            return cls.rated(Rating.AGAIN)
        return cls(fmt, correct=score >= 5.0)


@dataclass(frozen=True, slots=True)
class EvidenceGrade:
    rating: Rating
    weight: float
    step: int

    @property
    def is_lapse(self) -> bool:
        return self.rating is Rating.AGAIN

    @property
    def is_success(self) -> bool:
        return self.rating >= Rating.GOOD


def grade_evidence(evidence: Evidence) -> EvidenceGrade | None:
    """The one mapping from an observation to a rating. ``None``: do not schedule."""

    if evidence.format is EvidenceFormat.MENTION:
        return None
    if evidence.format is EvidenceFormat.RATED:
        rating = Rating(max(0, min(3, int(evidence.rating if evidence.rating is not None else 2))))
        # A self-graded card sits at the guided step; «Facile» at the top.
        return EvidenceGrade(rating=rating, weight=1.0, step=4 if rating is Rating.EASY else 2)
    step = FORMAT_STEP[evidence.format] - (1 if evidence.assisted else 0)
    step = max(0, step)
    if evidence.correct:
        rating, weight = SUCCESS_BY_STEP[step]
        return EvidenceGrade(rating=rating, weight=weight, step=step)
    # A lapse is an error in production, with or without help. An error in an
    # easier format shakes the memory (Hard) but is not a lapse.
    if evidence.format is EvidenceFormat.PRODUCE:
        return EvidenceGrade(rating=Rating.AGAIN, weight=1.0, step=step)
    return EvidenceGrade(rating=Rating.HARD, weight=1.0, step=step)


@dataclass(frozen=True, slots=True)
class MemoryState:
    """What is stored about one item's memory."""

    stability: float = 0.0
    difficulty: float = DEFAULT_DIFFICULTY
    reps: int = 0
    lapses: int = 0


@dataclass(frozen=True, slots=True)
class MemoryDecision:
    stability: float
    difficulty: float
    reps: int
    lapses: int
    interval_days: int
    due_at: dt.datetime
    grade: EvidenceGrade

    @property
    def is_lapse(self) -> bool:
        return self.grade.is_lapse


_SCHEDULER = FSRSScheduler(maximum_interval_days=int(MAX_STABILITY_DAYS))


def interval_for_stability(stability: float, *, max_interval_days: int = MAX_INTERVAL_DAYS) -> int:
    """At retention 0.9 the FSRS interval is the stability itself, in days."""

    return int(max(1, min(max_interval_days, round(max(0.0, stability)))))


def review(
    state: MemoryState | None,
    evidence: Evidence | EvidenceGrade,
    *,
    now: dt.datetime,
    interval_multiplier: float = 1.0,
    max_interval_days: int = MAX_INTERVAL_DAYS,
) -> MemoryDecision | None:
    """Apply one observation. ``None`` when the evidence does not schedule."""

    grade = evidence if isinstance(evidence, EvidenceGrade) else grade_evidence(evidence)
    if grade is None:
        return None
    current = state or MemoryState()
    stability = max(0.0, float(current.stability or 0.0))
    difficulty = float(current.difficulty or DEFAULT_DIFFICULTY)
    reps = max(0, int(current.reps or 0))
    lapses = max(0, int(current.lapses or 0))

    if reps <= 0 or stability <= 0.0:
        # First scheduled observation.
        if grade.is_success:
            new_stability = max(1.0, FIRST_STABILITY_BY_STEP.get(grade.step, 2.0))
        else:
            new_stability = FIRST_FAILURE_STABILITY
        new_difficulty = min(10.0, max(1.0, DEFAULT_DIFFICULTY - (int(grade.rating) - 1) * 0.5))
    else:
        raw_stability, new_difficulty, _days, _phase = _SCHEDULER._adjust_existing(
            SchedulerState(
                stability=stability,
                difficulty=difficulty,
                reps=reps,
                lapses=lapses,
                scheduled_days=interval_for_stability(stability),
                state="reviewing",
            ),
            int(grade.rating),
        )
        if grade.is_success:
            # The weight is how much of the rating's gain this format can buy.
            new_stability = stability + grade.weight * (raw_stability - stability)
        else:
            new_stability = raw_stability
    new_stability = min(MAX_STABILITY_DAYS, max(0.1, new_stability))

    due_in = None
    if grade.is_lapse:
        interval_days = LAPSE_INTERVAL_DAYS
        lapses += 1
    else:
        interval_days = interval_for_stability(new_stability, max_interval_days=max_interval_days)
        multiplier = max(0.25, min(2.0, float(interval_multiplier or 1.0)))
        if not math.isclose(multiplier, 1.0):
            # A calibration nudge (the Atelier's confidence signal) scales the
            # due date, not the memory; never under a day nor over the cap.
            scaled = max(1.0, min(float(max_interval_days), interval_days * multiplier))
            due_in = dt.timedelta(days=scaled)
            interval_days = int(max(1, round(scaled)))

    return MemoryDecision(
        stability=round(new_stability, 4),
        difficulty=round(new_difficulty, 4),
        reps=reps + 1,
        lapses=lapses,
        interval_days=interval_days,
        due_at=now + (due_in or dt.timedelta(days=interval_days)),
        grade=grade,
    )


def collapse(state: MemoryState) -> MemoryState:
    """The memory after the item was *made wrong again* outside a review.

    An erratum that recurs in the learner's own production is a lapse: the
    stability and difficulty move as an Again would move them (the vocabulary
    scheduler's formula), and the lapse is counted. ``reps`` is untouched — a
    recurrence is not a review.
    """

    stability = max(0.0, float(state.stability or 0.0))
    if stability <= 0.0:
        return MemoryState(
            stability=0.0,
            difficulty=min(10.0, float(state.difficulty or DEFAULT_DIFFICULTY) + 1.0),
            reps=state.reps,
            lapses=int(state.lapses or 0) + 1,
        )
    new_stability, new_difficulty, _days, _phase = _SCHEDULER._adjust_existing(
        SchedulerState(
            stability=stability,
            difficulty=float(state.difficulty or DEFAULT_DIFFICULTY),
            reps=max(1, int(state.reps or 0)),
            lapses=int(state.lapses or 0),
            scheduled_days=interval_for_stability(stability),
            state="reviewing",
        ),
        int(Rating.AGAIN),
    )
    return MemoryState(
        stability=round(new_stability, 4),
        difficulty=round(new_difficulty, 4),
        reps=state.reps,
        lapses=int(state.lapses or 0) + 1,
    )


# ---------------------------------------------------------------------------
# Seeding from the SM-2 era (the migration uses the same formula)
# ---------------------------------------------------------------------------

#: The historic first-review interval by score band (score ≥ threshold → days).
LEGACY_SEED_DAYS = ((9.0, 30), (7.0, 14), (5.0, 7), (3.0, 3))


def seed_from_legacy(
    *,
    score: float | None,
    reps: int | None,
    last_review: dt.datetime | None,
    next_review: dt.datetime | None,
) -> MemoryState:
    """Stability/difficulty/lapses for a row that only has SM-2-era fields.

    * ``reps == 0`` → no memory yet: ``S = 0, D = 5, lapses = 0``.
    * ``S`` = the interval the last review granted (``next_review − last_review``
      in days, at least 1) — at retention 0.9 an FSRS interval *is* the
      stability; when that pair is missing, the historic seed interval for the
      score (≥9 → 30, ≥7 → 14, ≥5 → 7, ≥3 → 3, else 1). Capped at 365.
    * ``D = clamp(5 + (5 − score) · 0.6, 1, 10)``: score 10 → 2, 5 → 5, 0 → 8.
    * ``lapses = 1`` when the last score failed (< 5), else 0 — SM-2 never
      stored a lapse count, so only the current failure is known.
    """

    reps = int(reps or 0)
    score_value = max(0.0, min(10.0, float(score or 0.0)))
    if reps <= 0:
        return MemoryState(stability=0.0, difficulty=DEFAULT_DIFFICULTY, reps=0, lapses=0)
    if last_review is not None and next_review is not None:
        stability = max(1.0, (next_review - last_review).total_seconds() / 86400.0)
    else:
        stability = 1.0
        for threshold, days in LEGACY_SEED_DAYS:
            if score_value >= threshold:
                stability = float(days)
                break
    stability = min(MAX_STABILITY_DAYS, stability)
    difficulty = min(10.0, max(1.0, 5.0 + (5.0 - score_value) * 0.6))
    return MemoryState(
        stability=round(stability, 4),
        difficulty=round(difficulty, 4),
        reps=reps,
        lapses=1 if score_value < 5.0 else 0,
    )


__all__ = [
    "FIRST_STABILITY_BY_STEP",
    "FORMAT_BY_NAME",
    "FORMAT_STEP",
    "LAPSE_INTERVAL_DAYS",
    "MAX_INTERVAL_DAYS",
    "SUCCESS_BY_STEP",
    "Evidence",
    "EvidenceFormat",
    "EvidenceGrade",
    "MemoryDecision",
    "MemoryState",
    "Rating",
    "format_for_name",
    "collapse",
    "grade_evidence",
    "interval_for_stability",
    "review",
    "seed_from_legacy",
]
