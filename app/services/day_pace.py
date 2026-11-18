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

Round 3 (walk 2, 17 Nov): the measured paces collapsed the quote. The walk's
players answered a card in 1.6–2.4 s and a La Forge item in about 10 s, so Home
said «Grammatik 2 Min.» and «Wörter 1 Min.» against 9 and 6 real minutes, and
«30 mots · 1 min». A person tapping «Je sais» through known cards would do the
same. So a measured pace is now only used with evidence, and only within reach:

* at least :data:`MIN_PACE_SAMPLES` items of that kind over at least
  :data:`MIN_PACE_DAYS` days, and the **median**, never the mean;
* clamped to half the default (a floor no real learner beats) and three times
  the default (:data:`PACE_FLOOR_SHARE`, :data:`PACE_CEILING_FACTOR`);
* a step is never quoted below one minute per :data:`CARDS_PER_MINUTE_FLOOR`
  cards or per :data:`FORGE_ITEMS_PER_MINUTE_FLOOR` La Forge items.
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
MIN_CARD_SAMPLES = 20
#: Round 3: a measured pace (La Forge, cards) needs this many items of its kind…
MIN_PACE_SAMPLES = 20
#: …over at least this many days.
MIN_PACE_DAYS = 2
#: Round 3: a measured pace is clamped to this share of its default at least…
PACE_FLOOR_SHARE = 0.5
#: …and this many times its default at most.
PACE_CEILING_FACTOR = 3.0
#: Round 3: a deck is never quoted below one minute for this many cards…
CARDS_PER_MINUTE_FLOOR = 6
#: …and La Forge never below one minute for this many items.
FORGE_ITEMS_PER_MINUTE_FLOOR = 2
#: La Forge's attempts the pace reads, newest first.
FORGE_LOOKBACK = 120
#: Two La Forge attempts further apart than this are a pause, not an item.
FORGE_MAX_GAP_SECONDS = 180.0


def clamp_pace(measured: float, default: float) -> float:
    """A measured seconds-per-item within reach of its default (round 3)."""

    return min(default * PACE_CEILING_FACTOR, max(default * PACE_FLOOR_SHARE, float(measured)))


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
        items = max(0, int(items))
        floor = items * 60.0 / FORGE_ITEMS_PER_MINUTE_FLOOR
        return int(round(max(items * self.forge_seconds_per_item, floor)))

    def words_seconds(self, new_words: int, reviews: int) -> int:
        new_words, reviews = max(0, int(new_words)), max(0, int(reviews))
        floor = (new_words + reviews) * 60.0 / CARDS_PER_MINUTE_FLOOR
        return int(
            round(max(new_words * self.new_card_seconds + reviews * self.review_card_seconds, floor))
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
    gaps: list[float] = []
    days: set[Any] = set()
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        gap = _seconds(earlier, later)
        if gap is not None and 0 < gap <= CARD_MAX_GAP_SECONDS:
            gaps.append(gap)
            days.add(later.date())
    # Round 3: evidence over days, or the default stands.
    if len(gaps) < MIN_CARD_SAMPLES or len(days) < MIN_PACE_DAYS:
        return None
    return float(median(gaps))


def measured_seconds_per_forge_item(db: Session, user: Any) -> float | None:
    """The median gap between consecutive attempts of one séance; ``None`` unmeasured.

    ``atelier.measured_seconds_per_drill`` read with the round-3 evidence rule:
    at least :data:`MIN_PACE_SAMPLES` gaps over at least :data:`MIN_PACE_DAYS` days.
    """

    from app.db.models.atelier import AtelierAttempt

    user_id = getattr(user, "id", None)
    if user_id is None:
        return None
    rows = db.execute(
        select(AtelierAttempt.atelier_session_id, AtelierAttempt.created_at)
        .where(AtelierAttempt.user_id == user_id)
        .order_by(AtelierAttempt.created_at.desc())
        .limit(FORGE_LOOKBACK)
    ).all()
    gaps: list[float] = []
    days: set[Any] = set()
    previous: tuple[Any, datetime] | None = None
    for session_id, created_at in reversed(rows):
        if not isinstance(created_at, datetime):
            continue
        if previous is not None and previous[0] == session_id:
            gap = _seconds(previous[1], created_at)
            if gap is not None and 0 < gap <= FORGE_MAX_GAP_SECONDS:
                gaps.append(gap)
                days.add(created_at.date())
        previous = (session_id, created_at)
    if len(gaps) < MIN_PACE_SAMPLES or len(days) < MIN_PACE_DAYS:
        return None
    return float(median(gaps))


def day_pace(db: Session, user: Any, *, now: datetime | None = None) -> DayPace:
    """The learner's measured pace per step, the calibrated defaults elsewhere.

    Best effort: a read that fails costs the quote its measurement, never Home its day.
    """

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
    drill = read("forge", lambda: measured_seconds_per_forge_item(db, user))
    if drill:
        # Round 3: within reach of the default, never the walk's 10 s an item.
        pace = replace(pace, forge_seconds_per_item=clamp_pace(drill, DEFAULT_FORGE_SECONDS_PER_ITEM))
        measured.add("forge")
    card = read("words", lambda: measured_seconds_per_card(db, user))
    if card:
        pace = replace(
            pace,
            new_card_seconds=clamp_pace(card, DEFAULT_SECONDS_PER_NEW_CARD),
            review_card_seconds=clamp_pace(card, DEFAULT_SECONDS_PER_REVIEW_CARD),
        )
        measured.add("words")
    return replace(pace, measured=frozenset(measured))


__all__ = [
    "DEFAULT_FORGE_SECONDS_PER_ITEM",
    "DEFAULT_PACE",
    "DEFAULT_SECONDS_PER_NEW_CARD",
    "DEFAULT_SECONDS_PER_REVIEW_CARD",
    "DayPace",
    "clamp_pace",
    "day_pace",
    "measured_scene_ratio",
    "measured_seconds_per_card",
    "measured_seconds_per_forge_item",
]
