"""R2 (7): what each step of the day takes *this* learner, for Home's minutes.

Home quoted about half of real play (walk 2026-11-17: La Forge «4 Min.» for 8
items played in 6–7 min; a B1 day quoted «8 min · + mots ≈ 5 min» took ~25).
The quote now reads the learner's own pace per step wherever it was measured,
and otherwise defaults calibrated to the walk's logs:

* **Scene** — the journey's step timestamps (``started_at``/``completed_at``) of
  the learner's last ended days, against what those days had estimated: the
  ratio scales today's core estimate. Each step's wall time is capped at three
  times its own estimate (idle, as ``measure_journey_duration`` reads it).
  Default: the plan's own estimate (ratio 1.0; the A1 walk's scenes ran 4–6 min
  against «8–9 Min.», so the plan does not under-quote the scene).
* **La Forge** — ``atelier.measured_seconds_per_drill`` (the median gap between
  a séance's attempts). Default :data:`DEFAULT_FORGE_SECONDS_PER_ITEM`, 48 s:
  the A1 walk's séances were 8 items in 6–7 min (day 1, 2) and ~7 min (day 3),
  B1's 7 items in about 5 min; the old 25 s quoted them at «4 Min.».
* **Words** — the median gap between the learner's consecutive day-deck answers
  (``ReviewLog``, ``source = "drill"``). Default 20 s a new card (A1 day 1:
  15 new cards with three «Nochmal» returns in ~5 min, quoted 5) and
  :data:`DEFAULT_SECONDS_PER_REVIEW_CARD`, 10 s a review card: a flip, the
  example line and a rating — two taps and a read. The 6 s of
  ``vocabulary_pace.SECONDS_PER_REVIEW`` is a bare recall and stays the
  vocabulary plan's own number.

The day is not shortened anywhere: only the minutes printed beside it change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: One La Forge item, read, answered, its verdict read (and a retry now and then).
DEFAULT_FORGE_SECONDS_PER_ITEM = 48.0
#: One new card of the day deck: the word, its example, a rating, a «Nochmal» return.
DEFAULT_SECONDS_PER_NEW_CARD = 20.0
#: One review card of the day deck: flip, read, rate.
DEFAULT_SECONDS_PER_REVIEW_CARD = 10.0

#: The ended days the scene's measurement reads, newest first.
SCENE_LOOKBACK_DAYS = 5
#: Measured days needed before the scene's own ratio replaces the plan's estimate.
MIN_SCENE_DAYS = 2
#: A step's wall time past this many times its own estimate is idle, not play.
STEP_IDLE_FACTOR = 3.0
#: A scene ratio outside this band is a measurement artefact.
SCENE_RATIO_BOUNDS = (0.5, 3.0)

#: The deck answers the card pace reads, newest first.
CARD_LOOKBACK = 200
#: A gap longer than this between two answers is a pause, not a card.
CARD_MAX_GAP_SECONDS = 120.0
#: Gaps needed before the measured card pace replaces the defaults.
MIN_CARD_SAMPLES = 10


@dataclass(frozen=True, slots=True)
class DayPace:
    """Seconds per unit of each step; ``measured`` names the ones read from play."""

    scene_ratio: float = 1.0
    forge_seconds_per_item: float = DEFAULT_FORGE_SECONDS_PER_ITEM
    new_card_seconds: float = DEFAULT_SECONDS_PER_NEW_CARD
    review_card_seconds: float = DEFAULT_SECONDS_PER_REVIEW_CARD
    measured: frozenset[str] = field(default_factory=frozenset)

    def scene_seconds(self, estimate: int) -> int:
        return int(round(max(0, int(estimate)) * self.scene_ratio))

    def forge_seconds(self, items: int) -> int:
        return int(round(max(0, int(items)) * self.forge_seconds_per_item))

    def words_seconds(self, new_words: int, reviews: int) -> int:
        return int(
            round(
                max(0, int(new_words)) * self.new_card_seconds
                + max(0, int(reviews)) * self.review_card_seconds
            )
        )


#: A learner with nothing measured yet: the calibrated defaults.
DEFAULT_PACE = DayPace()


def _seconds(start: Any, end: Any) -> float | None:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return (end - start).total_seconds()


def measured_scene_ratio(db: Session, user: Any, *, now: datetime | None = None) -> float | None:
    """Played over estimated, on the learner's last ended days; ``None`` unmeasured."""

    from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
    from app.services.journey_contracts import EXTENSION_STEP_KINDS, TERMINAL_JOURNEY_STATUSES

    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    extensions = {getattr(kind, "value", kind) for kind in EXTENSION_STEP_KINDS}
    terminal = [getattr(status, "value", status) for status in TERMINAL_JOURNEY_STATUSES]
    journeys = db.scalars(
        select(DailyJourney)
        .where(DailyJourney.user_id == user_id, DailyJourney.status.in_(terminal))
        .order_by(DailyJourney.local_date.desc())
        .limit(SCENE_LOOKBACK_DAYS)
    ).all()
    ratios: list[float] = []
    for journey in journeys:
        steps = db.scalars(
            select(DailyJourneyStep).where(DailyJourneyStep.journey_id == journey.id)
        ).all()
        played = estimated = 0.0
        for step in steps:
            if step.kind in extensions or not step.estimated_seconds:
                continue
            wall = _seconds(step.started_at, step.completed_at)
            if wall is None or wall <= 0:
                continue
            played += min(wall, STEP_IDLE_FACTOR * step.estimated_seconds)
            estimated += step.estimated_seconds
        if played > 0 and estimated > 0:
            ratios.append(played / estimated)
    if len(ratios) < MIN_SCENE_DAYS:
        return None
    low, high = SCENE_RATIO_BOUNDS
    return min(high, max(low, float(median(ratios))))


def measured_seconds_per_card(db: Session, user: Any) -> float | None:
    """The median gap between consecutive day-deck answers; ``None`` unmeasured."""

    from app.db.models.progress import ReviewLog, UserVocabularyProgress

    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    stamps = db.scalars(
        select(ReviewLog.review_date)
        .join(UserVocabularyProgress, UserVocabularyProgress.id == ReviewLog.progress_id)
        .where(UserVocabularyProgress.user_id == user_id, ReviewLog.source == "drill")
        .order_by(ReviewLog.review_date.desc())
        .limit(CARD_LOOKBACK)
    ).all()
    ordered = sorted(stamp for stamp in stamps if isinstance(stamp, datetime))
    gaps = [
        gap
        for earlier, later in zip(ordered, ordered[1:], strict=False)
        if (gap := _seconds(earlier, later)) is not None and 0 < gap <= CARD_MAX_GAP_SECONDS
    ]
    if len(gaps) < MIN_CARD_SAMPLES:
        return None
    return float(median(gaps))


def day_pace(db: Session, user: Any, *, now: datetime | None = None) -> DayPace:
    """The learner's measured pace per step, the calibrated defaults elsewhere.

    Best effort: a read that fails costs the quote its measurement, never Home its day.
    """

    from app.services.atelier import measured_seconds_per_drill

    def read(label: str, reader: Any) -> Any:
        try:
            with db.begin_nested():
                return reader()
        except Exception:  # noqa: BLE001 - a pace that cannot be read is the default
            logger.warning("day_pace: the %s pace could not be read", label, exc_info=True)
            return None

    measured: set[str] = set()
    pace = DEFAULT_PACE
    ratio = read("scene", lambda: measured_scene_ratio(db, user, now=now))
    if ratio:
        pace = replace(pace, scene_ratio=ratio)
        measured.add("scene")
    drill = read("forge", lambda: measured_seconds_per_drill(db, user)) if getattr(user, "id", None) else None
    if drill:
        pace = replace(pace, forge_seconds_per_item=float(drill))
        measured.add("forge")
    card = read("words", lambda: measured_seconds_per_card(db, user))
    if card:
        pace = replace(pace, new_card_seconds=card, review_card_seconds=card)
        measured.add("words")
    return replace(pace, measured=frozenset(measured))


__all__ = [
    "DEFAULT_FORGE_SECONDS_PER_ITEM",
    "DEFAULT_PACE",
    "DEFAULT_SECONDS_PER_NEW_CARD",
    "DEFAULT_SECONDS_PER_REVIEW_CARD",
    "DayPace",
    "day_pace",
    "measured_scene_ratio",
    "measured_seconds_per_card",
]
