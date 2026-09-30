"""WP-115a — FSRS-4.5 for vocabulary: one honest memory.

The scheduler that ``app/services/srs.py`` calls "FSRS-inspired" multiplies stability
by a constant on every pass and never reads how long it has been since the last
review, so a word reviewed early (the «fragile» and «kept» pools review early every
day) grew exactly as much as one reviewed when it was due. This is the published
FSRS-4.5 model (Ye et al., KDD 2022; open-spaced-repetition/fsrs4anki), with its
default parameters:

* **retrievability** ``R(t, S) = (1 + 19/81 · t/S) ** -0.5`` — the same curve the
  coverage code already reads (``vocabulary_coverage._retrievability``);
* **after a pass** stability grows with how much was forgotten: a review a few
  minutes after another (R ≈ 1) barely moves it, so reviewing a word twice in one
  day can no longer advance it twice;
* **after a lapse** stability falls to the post-lapse formula and the card relearns
  in 10 minutes;
* **the interval** is the time until R falls to the target retention
  (``settings.VOCAB_TARGET_RETENTION``, 0.87 by the owner's decision of 2026-09-30).

Ratings stay the app's 0..3 (Again, Hard, Good, Easy); FSRS's grades are 1..4.
Grammar, conjugation and errata keep their own schedulers for now (WP-115 §4.1).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.services.srs import ReviewOutcome, SchedulerState

#: FSRS-4.5 default parameters (w0..w16).
W: tuple[float, ...] = (
    0.4872, 1.4003, 3.7145, 13.8206,  # initial stability for Again, Hard, Good, Easy
    5.1618, 1.2298,                   # initial difficulty
    0.8975, 0.031,                    # difficulty step, mean reversion
    1.6474, 0.1367, 1.0461,           # stability after a pass
    2.1072, 0.0793, 0.3246, 1.587,    # stability after a lapse
    0.2272, 2.8755,                   # Hard penalty, Easy bonus
)
DECAY = -0.5
FACTOR = 0.9 ** (1 / DECAY) - 1  # = 19/81
DEFAULT_RETENTION = 0.87
RELEARN = timedelta(minutes=10)


def retrievability(stability: float, elapsed_days: float) -> float:
    if stability <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, elapsed_days) / stability) ** DECAY


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _initial_difficulty(grade: int) -> float:
    return _clamp(W[4] - math.exp(W[5] * (grade - 1)) + 1, 1.0, 10.0)


def _next_difficulty(difficulty: float, grade: int) -> float:
    stepped = difficulty - W[6] * (grade - 3)
    # Mean reversion towards the difficulty of an «Easy» first answer.
    return _clamp(W[7] * _initial_difficulty(4) + (1 - W[7]) * stepped, 1.0, 10.0)


def _stability_after_pass(difficulty: float, stability: float, r: float, grade: int) -> float:
    hard = W[15] if grade == 2 else 1.0
    easy = W[16] if grade == 4 else 1.0
    growth = (
        math.exp(W[8]) * (11 - difficulty) * stability ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) * hard * easy
    )
    return stability * (growth + 1)


def _stability_after_lapse(difficulty: float, stability: float, r: float) -> float:
    after = W[11] * difficulty ** -W[12] * ((stability + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
    return min(after, stability)


class VocabularyFSRS:
    """FSRS-4.5 with the app's review interface (``review(state=…, rating=…)``)."""

    def __init__(self, *, retention: float | None = None, maximum_interval_days: int = 3650) -> None:
        from app.config import settings

        target = retention if retention is not None else getattr(settings, "VOCAB_TARGET_RETENTION", DEFAULT_RETENTION)
        self.retention = _clamp(float(target), 0.7, 0.97)
        self.maximum_interval_days = maximum_interval_days

    def interval_days(self, stability: float) -> int:
        days = stability / FACTOR * (self.retention ** (1 / DECAY) - 1)
        return int(_clamp(round(days), 1, self.maximum_interval_days))

    def review(
        self,
        *,
        state: SchedulerState,
        rating: int,
        last_review_at: datetime | None,
        now: datetime | None = None,
    ) -> ReviewOutcome:
        if rating < 0 or rating > 3:
            raise ValueError("Rating must be between 0 and 3 inclusive")
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        if last_review_at is not None and last_review_at.tzinfo is None:
            last_review_at = last_review_at.replace(tzinfo=UTC)
        grade = rating + 1
        elapsed = max(0.0, (now - last_review_at).total_seconds() / 86400) if last_review_at else 0.0

        fresh = (state.reps or 0) <= 0 or (state.stability or 0) <= 0
        if fresh:
            stability = W[grade - 1]
            difficulty = _initial_difficulty(grade)
        else:
            previous = max(0.01, float(state.stability))
            difficulty_before = _clamp(float(state.difficulty or 5.0), 1.0, 10.0)
            r = retrievability(previous, elapsed)
            difficulty = _next_difficulty(difficulty_before, grade)
            stability = (
                _stability_after_lapse(difficulty_before, previous, r)
                if grade == 1
                else _stability_after_pass(difficulty_before, previous, r, grade)
            )
        stability = _clamp(stability, 0.01, float(self.maximum_interval_days))

        if grade == 1:
            new_state = "learning" if fresh else "relearning"
            scheduled_days = 0
            next_review = now + RELEARN
        else:
            new_state = "reviewing"
            scheduled_days = self.interval_days(stability)
            next_review = now + timedelta(days=scheduled_days)
        return ReviewOutcome(
            stability=round(stability, 4),
            difficulty=round(difficulty, 4),
            scheduled_days=scheduled_days,
            elapsed_days=int(elapsed),
            state=new_state,
            next_review=next_review,
        )


#: WP-115a: the grade an answer earns, by how it was given. Recalling the word
#: (typed, cloze, spoken) is «Good»; picking it among options is «Hard»; a wrong
#: answer is «Again». A self-rated flashcard keeps the learner's own rating.
_EARNED = {"typed": 2, "cloze": 2, "audio": 2, "choice": 1}


def earned_rating(review_format: str | None, correct: bool | None, rating: int) -> int:
    if review_format in _EARNED and correct is not None:
        return _EARNED[review_format] if correct else 0
    return rating


def prediction(
    stability: float | None, reps: int | None, last_review_at: datetime | None, now: datetime
) -> tuple[float | None, float | None]:
    """WP-115e: ``(predicted recall, days since the last review)`` at a review, for the
    calibration and the forgetting curve. ``None`` for a card never reviewed."""

    if last_review_at is None or not reps or not stability or stability <= 0:
        return None, None
    if last_review_at.tzinfo is None:
        last_review_at = last_review_at.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    elapsed = max(0.0, (now - last_review_at).total_seconds() / 86400)
    return round(retrievability(float(stability), elapsed), 4), round(elapsed, 4)
