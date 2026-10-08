"""«Vos sceaux» — the streak calendar (WP-D5).

One source of truth: the number is :func:`app.services.streak.settle_streak`
(the same read Home and the journey wire print) and the grid is the
``streak_days`` rows that :mod:`app.services.streak` writes in the same flush.
The learner's timezone decides which day is «today».

Each day is one of:

* ``completed`` — practised; ``sealed`` when that day's journey was
  *completed* (an early stop moves the streak but presses no seal), with the
  edition's ``edition_no`` and ``seal_variant``;
* ``relache`` — a missed day a banked «jour de relâche» covered;
* ``missed`` — a past day with neither;
* ``today`` — today, not yet practised (a practised today is ``completed``);
* ``future`` — the rest of this week.

The grid starts on the Monday of the learner's first recorded week inside the
window and ends on this week's Sunday; days before the first recorded day are
left out, not counted as missed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.streak_day import STREAK_DAY_PRACTISED, STREAK_DAY_RELACHE, StreakDay
from app.db.models.user import User
from app.services.seals import edition_numbers, seal_variant_for
from app.services.streak import local_today, settle_streak, user_timezone


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def streak_calendar(
    db: Session,
    user: User,
    *,
    window_days: int = 28,
    now: datetime | None = None,
) -> dict[str, Any]:
    """The number and the grid, from the same rows. Flushes; the caller commits."""

    today = local_today(user, now)
    state = settle_streak(db, user, today=today)
    window_start = _monday(today - timedelta(days=max(1, window_days) - 1))
    end = _monday(today) + timedelta(days=6)

    rows = (
        db.execute(
            select(StreakDay.local_date, StreakDay.kind).where(
                StreakDay.user_id == user.id,
                StreakDay.local_date >= window_start,
                StreakDay.local_date <= today,
            )
        )
        .all()
    )
    kinds = {row[0]: row[1] for row in rows}
    first_ever = db.execute(
        select(StreakDay.local_date)
        .where(StreakDay.user_id == user.id)
        .order_by(StreakDay.local_date.asc())
        .limit(1)
    ).scalar_one_or_none()
    first = first_ever if first_ever is not None and first_ever <= today else today
    start = max(window_start, first)

    journeys = (
        db.execute(
            select(DailyJourney).where(
                DailyJourney.user_id == user.id,
                DailyJourney.local_date >= start,
                DailyJourney.local_date <= today,
            )
        )
        .scalars()
        .all()
    )
    editions = edition_numbers(db, journeys)
    by_day = {journey.local_date: journey for journey in journeys}

    calendar: list[dict[str, Any]] = []
    day = start
    while day <= end:
        kind = kinds.get(day)
        journey = by_day.get(day)
        sealed = bool(
            kind == STREAK_DAY_PRACTISED
            and journey is not None
            and journey.status == "completed"
        )
        edition_no = editions.get(journey.id) if journey is not None else None
        if day > today:
            day_state = "future"
        elif kind == STREAK_DAY_PRACTISED:
            day_state = "completed"
        elif kind == STREAK_DAY_RELACHE:
            day_state = "relache"
        elif day == today:
            day_state = "today"
        else:
            day_state = "missed"
        calendar.append(
            {
                "date": day,
                "state": day_state,
                "completed": 1 if day_state == "completed" else 0,
                "is_today": day == today,
                "sealed": sealed,
                "edition_no": edition_no if sealed else None,
                "seal_variant": seal_variant_for(edition_no) if sealed else None,
            }
        )
        day += timedelta(days=1)

    return {
        "current_streak": state.days,
        "longest_streak": max(state.longest, state.days),
        "today_done": state.today_done,
        "freeze_available": state.freeze_available,
        "today": today,
        "timezone": user_timezone(user),
        "calendar": calendar,
    }


__all__ = ["streak_calendar"]
