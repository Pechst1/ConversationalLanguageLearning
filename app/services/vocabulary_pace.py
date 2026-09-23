"""WP-L6 — the vocabulary pace: «Nouveaux mots par jour», one intake pool.

Owner decision 2026-09-23 (§5.1 of WORK-PACKAGES-2026-09-23-learning): the
learner sets how many new words a day they take in (``users.new_words_per_day``,
1–50), independently of the rhythm, and the day and the word drill share that
one quota:

* **one intake pool** — a word is introduced once, by the word drill or by a
  scene, and the day's quota counts both. A word is *introduced* the moment
  the learner owns a progress row for it (``UserVocabularyProgress.created_at``
  falls on their local today), plus the words today's journey planned as new
  and has not credited yet (``plan_selection["new_word_ids"]``, a reservation);
* **the journey takes its share first** — until today's journey is planned the
  drill leaves the rhythm's share of new words free for it
  (:attr:`~app.services.journey_contracts.RhythmCaps.journey_new_words`);
  once it is planned, its actual new words are the reservation;
* **no double introduction** — the drill never offers a word the journey has
  reserved, and the journey never meets a word the drill introduced as new
  (it has a progress row, so it is a review).

The auto-throttle (§2.2: intake halves when the backlog outgrows capacity or
accuracy drops) needs WP-L3's queue numbers. :func:`intake_throttle_factor` is
its hook and returns 1.0 until then.
"""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.progress import UserVocabularyProgress
from app.services.journey_contracts import rhythm_caps
from app.services.journey_rhythm import budget_seconds_for
from app.services.streak import local_today, user_timezone

DEFAULT_NEW_WORDS_PER_DAY = 10
#: The plan_selection key holding the vocabulary ids today's journey introduces.
JOURNEY_NEW_WORDS_KEY = "new_word_ids"
#: §5.1's honest cost, as a planning prior: each new word a day costs about
#: eight to ten reviews a day once the schedule reaches its steady state
#: (≈ 150–200 reviews at 20 new words). An estimate, labelled as one.
REVIEWS_PER_NEW_WORD_LOW = 8
REVIEWS_PER_NEW_WORD_HIGH = 10
#: §5.1's own arithmetic (150–200 reviews ≈ 15–20 min): about six seconds a review.
SECONDS_PER_REVIEW = 6


def intake_throttle_factor(db: Session, user: Any, *, now: datetime | None = None) -> float:
    """WP-L6 auto-throttle hook — **not implemented yet** (needs WP-L3).

    §2.2: when the due backlog exceeds 1.5 days of review capacity, or 7-day
    review accuracy falls below 80 %, new intake halves until it recovers and
    the learner reads «Cette semaine, on consolide.» Returns the multiplier
    applied to the daily quota; 1.0 means no throttle.
    """

    return 1.0


def daily_quota(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """How many new words this learner takes in today, all surfaces together."""

    raw = getattr(user, "new_words_per_day", None)
    quota = int(raw) if raw else DEFAULT_NEW_WORDS_PER_DAY
    return max(0, int(quota * intake_throttle_factor(db, user, now=now)))


def _local_window(user: Any, now: datetime) -> tuple[datetime, datetime]:
    zone = ZoneInfo(user_timezone(user))
    day = local_today(user, now)
    start = datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)
    return start, start + timedelta(days=1)


def introduced_today(db: Session, user: Any, *, now: datetime | None = None) -> set[int]:
    """Word ids whose progress row was created on the learner's local today."""

    now = now or datetime.now(UTC)
    start, end = _local_window(user, now)
    rows = db.execute(
        select(UserVocabularyProgress.word_id).where(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.created_at >= start,
            UserVocabularyProgress.created_at < end,
        )
    ).all()
    return {int(row[0]) for row in rows if row[0] is not None}


def todays_journey(db: Session, user: Any, *, now: datetime | None = None) -> DailyJourney | None:
    now = now or datetime.now(UTC)
    return db.execute(
        select(DailyJourney).where(
            DailyJourney.user_id == user.id,
            DailyJourney.local_date == local_today(user, now),
        )
    ).scalars().first()


def journey_reservation(
    db: Session, user: Any, *, now: datetime | None = None
) -> tuple[bool, set[int]]:
    """``(planned, word_ids)``: has today's journey been planned, and which
    new words it introduces."""

    journey = todays_journey(db, user, now=now)
    selection = dict(getattr(journey, "plan_selection", None) or {}) if journey else {}
    if JOURNEY_NEW_WORDS_KEY not in selection:
        return False, set()
    ids: set[int] = set()
    for value in selection.get(JOURNEY_NEW_WORDS_KEY) or []:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return True, ids


def journey_new_word_room(db: Session, user: Any, *, now: datetime | None = None) -> int:
    """How many new words today's journey may introduce: what the quota has
    left after everything already introduced today."""

    return max(0, daily_quota(db, user, now=now) - len(introduced_today(db, user, now=now)))


def drill_new_word_room(
    db: Session, user: Any, *, now: datetime | None = None
) -> tuple[int, set[int]]:
    """``(room, excluded_word_ids)`` for the word drill.

    The drill gets what the quota leaves after today's introductions and the
    journey's share — its reservation once planned, its rhythm's share before.
    ``excluded_word_ids`` are the journey's reserved words: never offered as
    new by the drill.
    """

    quota = daily_quota(db, user, now=now)
    introduced = introduced_today(db, user, now=now)
    planned, reserved = journey_reservation(db, user, now=now)
    taken = len(introduced | reserved)
    pending = 0 if planned else min(quota, rhythm_caps(budget_seconds_for(user)).journey_new_words)
    return max(0, quota - taken - pending), reserved - introduced


def review_load_estimate(new_words_per_day: int) -> dict[str, int]:
    """The steady-state review load a vocabulary pace costs — an estimate."""

    words = max(0, int(new_words_per_day))
    low = words * REVIEWS_PER_NEW_WORD_LOW
    high = words * REVIEWS_PER_NEW_WORD_HIGH
    return {
        "reviews_low": low,
        "reviews_high": high,
        "minutes_low": round(low * SECONDS_PER_REVIEW / 60),
        "minutes_high": round(high * SECONDS_PER_REVIEW / 60),
    }




def vocabulary_pace_limit(db: Session, user: Any, requested: int) -> tuple[int, set[int]]:
    """The word drill's ``new_limit``, clamped to the learner's pace.

    ``(min(requested, room), reserved_ids)``. A pace that cannot be read (a
    demo account, a broken read) leaves the request as it was: the pace is a
    ceiling, never a reason to lose the deck.
    """

    if not getattr(user, "id", None) or requested <= 0:
        return max(0, requested), set()
    try:
        with db.begin_nested():
            room, reserved = drill_new_word_room(db, user)
    except Exception:  # noqa: BLE001 - the deck is worth more than the ceiling
        return requested, set()
    return min(requested, room), reserved


__all__ = [
    "DEFAULT_NEW_WORDS_PER_DAY",
    "JOURNEY_NEW_WORDS_KEY",
    "daily_quota",
    "drill_new_word_room",
    "intake_throttle_factor",
    "introduced_today",
    "journey_new_word_room",
    "journey_reservation",
    "review_load_estimate",
    "todays_journey",
    "vocabulary_pace_limit",
]
