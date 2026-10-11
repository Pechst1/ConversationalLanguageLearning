"""The practice streak — one source of truth, honest on every read (WP-80, WP-79).

What counts: a day on which the learner finished the daily journey (the V2
Séance, decision D-0) or completed a legacy Atelier session. Both surfaces call
:func:`record_practice_day`; it is a no-op once the day is marked, so a learner
who finishes the journey and then drills gets one increment, not two.

Which day: the learner's **local** day, in ``User.timezone``. A streak counted
in server time loses a day for everybody far from Europe.

Honest on read: the stored number is the streak *as of the last practice day*.
Reading it without checking the date is how a learner who stopped a week ago
kept seeing «12 jours» (``atelier.py`` summary before WP-80). :func:`read_streak`
checks the date and says 0 the moment the chain is broken.

«Jour de relâche»: one freeze is earned per full seven-day week of the streak,
at most one banked. It is spent automatically on the first missed day, and the
day it covered is recorded (``User.streak_freeze_used_on``) so the number stays
explainable. A frozen day is not a practised day: it keeps the chain, it does
not add to it. Two missed days in a row always break the streak.

Storage: ``grammar_streak_days`` / ``grammar_last_review_date`` /
``grammar_longest_streak`` are the columns both surfaces have always written;
``current_streak`` / ``longest_streak`` are mirrored so the streak-at-risk push
and the achievements that read them see the same number.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from loguru import logger
from sqlalchemy.orm import Session

from app.db.models.streak_day import STREAK_DAY_PRACTISED, STREAK_DAY_RELACHE, StreakDay
from app.db.models.user import User

#: The zone every learner had before WP-80 stored one.
DEFAULT_TIMEZONE = "Europe/Paris"
#: A full week of the streak earns one «jour de relâche».
FREEZE_EARNED_EVERY = 7
#: At most this many freezes are banked.
MAX_BANKED_FREEZES = 1


# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------


def valid_timezone(value: Any) -> str | None:
    """The IANA name when it is one, else ``None``. Never guesses a city."""

    candidate = str(value or "").strip()
    if not candidate or len(candidate) > 64:
        return None
    try:
        ZoneInfo(candidate)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    return candidate


def user_timezone(user: User) -> str:
    return valid_timezone(getattr(user, "timezone", None)) or DEFAULT_TIMEZONE


def local_now(user: User, now: datetime | None = None) -> datetime:
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(ZoneInfo(user_timezone(user)))


def local_today(user: User, now: datetime | None = None) -> date:
    return local_now(user, now).date()


def remember_timezone(user: User, value: Any) -> bool:
    """Store the client's zone when it is valid and new. Returns whether it changed.

    The caller commits. An invalid value is ignored, never stored: a typo must
    not move somebody's streak day.
    """

    zone = valid_timezone(value)
    if zone is None or zone == getattr(user, "timezone", None):
        return False
    user.timezone = zone
    return True


# ---------------------------------------------------------------------------
# The streak
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StreakState:
    #: Practised days in the unbroken chain, today included when done.
    days: int
    #: Whether today (local) is already practised.
    today_done: bool
    #: Whether a «jour de relâche» is banked.
    freeze_available: bool
    #: The local day the last freeze covered, if any.
    freeze_used_on: date | None
    longest: int

    @property
    def at_risk(self) -> bool:
        """A live chain that today's practice has not yet extended."""

        return self.days > 0 and not self.today_done

    def as_payload(self) -> dict[str, Any]:
        return {
            "days": self.days,
            "today_done": self.today_done,
            "freeze_available": self.freeze_available,
            "freeze_used_on": self.freeze_used_on.isoformat() if self.freeze_used_on else None,
        }


@dataclass(frozen=True, slots=True)
class _Resolution:
    state: StreakState
    #: The freeze this read spends (the missed day), when it spends one.
    spend_freeze_on: date | None = None
    #: The chain broke; the stored count must go to zero.
    broken: bool = False


def _stored(user: User) -> tuple[int, date | None, int, date | None, int]:
    return (
        int(getattr(user, "grammar_streak_days", 0) or 0),
        getattr(user, "grammar_last_review_date", None),
        int(getattr(user, "streak_freezes", 0) or 0),
        getattr(user, "streak_freeze_used_on", None),
        int(getattr(user, "grammar_longest_streak", 0) or 0),
    )


def _resolve(user: User, today: date) -> _Resolution:
    days, last, freezes, used_on, longest = _stored(user)
    banked = freezes > 0
    if last is None or days <= 0:
        return _Resolution(StreakState(0, False, banked, used_on, longest))
    if last >= today:
        # Done today (or a clock that moved backwards across zones: never
        # punish the learner for travelling west).
        return _Resolution(StreakState(days, True, banked, used_on, longest))
    anchor = max(last, used_on) if used_on else last
    if anchor >= today - timedelta(days=1):
        return _Resolution(StreakState(days, False, banked, used_on, longest))
    missed = today - timedelta(days=1)
    if banked and anchor == today - timedelta(days=2):
        return _Resolution(
            StreakState(days, False, False, missed, longest), spend_freeze_on=missed
        )
    return _Resolution(StreakState(0, False, banked, used_on, longest), broken=True)


def read_streak(user: User, *, today: date | None = None, now: datetime | None = None) -> StreakState:
    """The streak as it stands on the learner's local ``today``. Pure: no writes.

    A freeze that is due is *reported* as spent (so every surface prints the
    same number); :func:`settle_streak` is what writes it down.
    """

    return _resolve(user, today or local_today(user, now)).state


def _mark_day(db: Session, user: User, day: date, kind: str) -> StreakDay:
    """WP-D5: write the day into the calendar in the same flush as the number.

    Idempotent per (learner, day); a practised day wins over a relâche.
    """

    with db.no_autoflush:
        row = (
            db.query(StreakDay)
            .filter(StreakDay.user_id == user.id, StreakDay.local_date == day)
            .one_or_none()
        )
    if row is None:
        row = StreakDay(user_id=user.id, local_date=day, kind=kind)
        db.add(row)
    elif row.kind != kind and kind == STREAK_DAY_PRACTISED:
        row.kind = kind
    return row


def _mirror(user: User, days: int) -> None:
    user.current_streak = days
    user.longest_streak = max(int(getattr(user, "longest_streak", 0) or 0), days)


def settle_streak(
    db: Session, user: User, *, today: date | None = None, now: datetime | None = None
) -> StreakState:
    """Read the streak and persist what the read decided (a spent freeze, a
    broken chain). Flushes; the caller commits."""

    day = today or local_today(user, now)
    resolution = _resolve(user, day)
    changed = False
    marked: list[Any] = []
    if resolution.spend_freeze_on is not None:
        user.streak_freezes = max(0, int(getattr(user, "streak_freezes", 0) or 0) - 1)
        user.streak_freeze_used_on = resolution.spend_freeze_on
        marked.append(_mark_day(db, user, resolution.spend_freeze_on, STREAK_DAY_RELACHE))
        changed = True
        logger.info(
            "streak: jour de relâche spent",
            user_id=str(user.id),
            covered=resolution.spend_freeze_on.isoformat(),
        )
    if resolution.broken and int(getattr(user, "grammar_streak_days", 0) or 0) != 0:
        user.grammar_streak_days = 0
        changed = True
    if int(getattr(user, "current_streak", 0) or 0) != resolution.state.days:
        _mirror(user, resolution.state.days)
        changed = True
    if changed:
        db.add(user)
        db.flush([user, *marked])
    return resolution.state


def record_practice_day(
    db: Session, user: User, *, on_date: date | None = None, now: datetime | None = None
) -> StreakState:
    """Mark ``on_date`` (default: the learner's local today) as practised.

    At most once per local day. Earns a «jour de relâche» on every full week.
    Flushes; the caller commits.
    """

    day = on_date or local_today(user, now)
    before = settle_streak(db, user, today=day)
    if before.today_done:
        return before
    days = before.days + 1
    user.grammar_streak_days = days
    user.grammar_last_review_date = day
    user.grammar_longest_streak = max(int(getattr(user, "grammar_longest_streak", 0) or 0), days)
    freezes = int(getattr(user, "streak_freezes", 0) or 0)
    if days % FREEZE_EARNED_EVERY == 0 and freezes < MAX_BANKED_FREEZES:
        user.streak_freezes = freezes + 1
    _mirror(user, days)
    user.mark_activity(day)
    marked = _mark_day(db, user, day, STREAK_DAY_PRACTISED)
    db.add(user)
    db.flush([user, marked])
    return read_streak(user, today=day)


def missed_days_before(last_practice: date | None, today: date) -> int:
    """Whole local days with no practice between the last practised day and today."""

    if last_practice is None or last_practice >= today:
        return 0
    return max(0, (today - last_practice).days - 1)


__all__ = [
    "DEFAULT_TIMEZONE",
    "FREEZE_EARNED_EVERY",
    "MAX_BANKED_FREEZES",
    "StreakState",
    "local_now",
    "local_today",
    "missed_days_before",
    "read_streak",
    "record_practice_day",
    "remember_timezone",
    "settle_streak",
    "snapshot_fields",
    "today_fields",
    "user_timezone",
    "valid_timezone",
]


# ---------------------------------------------------------------------------
# Journey wire fields (additive on TodayEnvelope / JourneySnapshot)
# ---------------------------------------------------------------------------


def today_fields(db: Session, user: User, *, timezone_hint: Any = None) -> dict[str, Any]:
    """``GET /daily-journeys/today``: persist the client's zone, settle, report.

    Best effort by design: a streak write that fails must never cost the
    learner their day, so a failure rolls back and reports the pure read.
    """

    try:
        remember_timezone(user, timezone_hint)
        state = settle_streak(db, user)
        db.commit()
    except Exception:  # pragma: no cover - defensive; logged, never raised
        db.rollback()
        logger.exception("streak: settling on /today failed", user_id=str(user.id))
        state = read_streak(user)
    today = local_today(user)
    return {
        "streak": state.as_payload(),
        "missed_days": missed_days_before(getattr(user, "grammar_last_review_date", None), today),
    }


def snapshot_fields(db: Session, user_id: Any, local_date: date) -> dict[str, Any]:
    """The same two fields for a journey snapshot. A pure read, no writes."""

    user = db.get(User, user_id)
    if user is None:
        return {"streak": None, "missed_days": 0}
    return {
        "streak": read_streak(user, today=local_date).as_payload(),
        "missed_days": missed_days_before(
            getattr(user, "grammar_last_review_date", None), local_date
        ),
    }
