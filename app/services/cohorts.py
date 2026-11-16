"""Who came back: return numbers per sign-up week, read from the ledger (S6 stage 2).

Every pilot report before this one answered «what happened on day D». This one asks
«of the learners who started in week W, who came back on day 1, 3, 7 and 14», so a fix
can be judged by what learners did, not only by a walk.

Sources, both already written by the product:

* ``streak_days``: one row per learner-local day practised (journey or Séance).
* ``pilot_events``: the journey events (started, step completed, completed, ended
  early), each with the learner's IANA zone at the time.

Rules:

* **Days are the learner's own.** Sign-up is ``users.created_at`` in ``users.timezone``;
  a journey event is placed in the zone it carries (as the daily rollup does). Day N is
  sign-up date + N.
* **Active** on a day = a journey started or a step done that day, or a practised
  streak row for it.
* **Due**: day N counts only once it is over, or once the learner was already active
  on it. A day still running with no visit yet is «not due», never «did not return».
* **Small counts**: under :data:`MIN_LEARNERS_FOR_RATE` due learners a cell shows the
  raw counts and no percentage.
* **Synthetic accounts** (``users.is_synthetic``) are left out unless asked for.
* **Minutes** are measured by :func:`~app.services.journey_events.measure_journey_duration`
  (pauses and idle stretches excluded), summed per learner-day. Never an estimate.
* **Where an unfinished day stopped**: the kind of the last step completed in a journey
  that was started and not completed («before the first step» when none was). Read from
  the journey's step events until the stored day plan (S2) lands.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import median
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.db.models.pilot_event import PilotEvent
from app.db.models.streak_day import STREAK_DAY_PRACTISED, StreakDay
from app.db.models.user import User
from app.services.journey_contracts import JourneyEventName
from app.services.journey_events import (
    FALLBACK_TIMEZONE,
    JOURNEY_ENTITY_TYPE,
    measure_journey_duration,
)

#: The return days the table reports.
RETURN_DAYS: tuple[int, ...] = (1, 3, 7, 14)
#: Below this many due learners a cell shows counts only.
MIN_LEARNERS_FOR_RATE = 5
#: Label for an unfinished day that stopped before any step was done.
BEFORE_FIRST_STEP = "before the first step"

_STARTED = str(JourneyEventName.STARTED)
_STEP = str(JourneyEventName.STEP_COMPLETED)
_COMPLETED = str(JourneyEventName.COMPLETED)
_ENDED_EARLY = str(JourneyEventName.ENDED_EARLY)
_EVENTS = (_STARTED, _STEP, _COMPLETED, _ENDED_EARLY)


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or FALLBACK_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo(FALLBACK_TIMEZONE)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass
class _Journey:
    local_date: date
    started: bool = False
    completed: bool = False
    last_step_at: datetime | None = None
    last_step_kind: str | None = None


@dataclass
class _Learner:
    user: User
    zone: ZoneInfo
    signup_date: date
    today: date
    active_days: set[date] = field(default_factory=set)
    journeys: dict[str, _Journey] = field(default_factory=dict)
    minutes_by_day: dict[date, float] = field(default_factory=dict)

    def returned(self, offset: int) -> bool | None:
        day = self.signup_date + timedelta(days=offset)
        if day in self.active_days:
            return True
        if day < self.today:
            return False
        return None

    def started_days(self) -> set[date]:
        return {j.local_date for j in self.journeys.values() if j.started}

    def completed_days(self) -> set[date]:
        return {j.local_date for j in self.journeys.values() if j.started and j.completed}

    def stops(self) -> list[dict[str, str]]:
        rows = []
        for journey in self.journeys.values():
            if journey.started and not journey.completed:
                rows.append(
                    {
                        "date": journey.local_date.isoformat(),
                        "after_step": journey.last_step_kind or BEFORE_FIRST_STEP,
                    }
                )
        return sorted(rows, key=lambda row: row["date"])


def _cell(returned: int, due: int) -> dict[str, Any]:
    if due == 0:
        return {"returned": 0, "due": 0, "rate": None, "display": "not due"}
    if due < MIN_LEARNERS_FOR_RATE:
        return {"returned": returned, "due": due, "rate": None, "display": f"{returned} of {due}"}
    rate = round(returned / due, 4)
    return {
        "returned": returned,
        "due": due,
        "rate": rate,
        "display": f"{round(rate * 100)}% ({returned} of {due})",
    }


def _median(values: list[float]) -> float | None:
    return round(median(values), 1) if values else None


def build_cohorts(
    db: Session,
    *,
    weeks: int = 8,
    include_synthetic: bool = False,
) -> dict[str, Any]:
    """Return numbers for the last ``weeks`` sign-up weeks (Monday to Sunday), newest first."""

    weeks = max(1, min(int(weeks), 52))
    now = datetime.now(UTC)
    # A wide UTC window; each learner is then placed in their own zone.
    first_week = _week_start(now.date()) - timedelta(weeks=weeks - 1)
    window_start = datetime.combine(first_week - timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    query = db.query(User).filter(User.created_at >= window_start, User.created_at <= now)
    users = query.all()
    synthetic_excluded = sum(1 for user in users if user.is_synthetic)
    if not include_synthetic:
        users = [user for user in users if not user.is_synthetic]

    learners: dict[UUID, _Learner] = {}
    for user in users:
        if user.created_at is None:
            continue
        zone = _zone(user.timezone)
        signup = _aware(user.created_at).astimezone(zone).date()
        if signup < first_week:
            continue
        learners[user.id] = _Learner(
            user=user, zone=zone, signup_date=signup, today=now.astimezone(zone).date()
        )

    if learners:
        _read_streak(db, learners)
        _read_journeys(db, learners)

    by_week: dict[date, list[_Learner]] = defaultdict(list)
    for learner in learners.values():
        by_week[_week_start(learner.signup_date)].append(learner)

    cohorts = [_cohort_row(week, by_week[week]) for week in sorted(by_week, reverse=True)]
    return {
        "today": now.astimezone(_zone(FALLBACK_TIMEZONE)).date().isoformat(),
        "weeks": weeks,
        "first_week": first_week.isoformat(),
        "return_days": list(RETURN_DAYS),
        "min_learners_for_rate": MIN_LEARNERS_FOR_RATE,
        "include_synthetic": include_synthetic,
        "synthetic_excluded": 0 if include_synthetic else synthetic_excluded,
        "cohorts": cohorts,
    }


def _read_streak(db: Session, learners: dict[UUID, _Learner]) -> None:
    rows = (
        db.query(StreakDay.user_id, StreakDay.local_date)
        .filter(StreakDay.user_id.in_(list(learners)), StreakDay.kind == STREAK_DAY_PRACTISED)
        .all()
    )
    for user_id, local_date in rows:
        learners[user_id].active_days.add(local_date)


def _read_journeys(db: Session, learners: dict[UUID, _Learner]) -> None:
    events = (
        db.query(PilotEvent)
        .filter(
            PilotEvent.user_id.in_(list(learners)),
            PilotEvent.event_type.in_(_EVENTS),
            PilotEvent.entity_type == JOURNEY_ENTITY_TYPE,
        )
        .order_by(PilotEvent.occurred_at)
        .all()
    )
    for event in events:
        learner = learners[event.user_id]
        payload = event.payload or {}
        journey_id = str(payload.get("journey_id") or event.entity_id or "")
        if not journey_id:
            continue
        moment = _aware(event.occurred_at)
        zone = _zone(payload.get("timezone")) if payload.get("timezone") else learner.zone
        local = moment.astimezone(zone).date()
        journey = learner.journeys.get(journey_id)
        if journey is None:
            journey = learner.journeys[journey_id] = _Journey(local_date=local)
        if event.event_type == _STARTED:
            # The day a journey belongs to is the day it was started.
            journey.started = True
            journey.local_date = local
            learner.active_days.add(local)
        elif event.event_type == _STEP:
            learner.active_days.add(local)
            if journey.last_step_at is None or moment >= journey.last_step_at:
                journey.last_step_at = moment
                kind = payload.get("step_kind")
                journey.last_step_kind = str(kind) if kind else "unknown"
        elif event.event_type == _COMPLETED:
            journey.completed = True

    for learner in learners.values():
        minutes: dict[date, float] = defaultdict(float)
        for journey_id, journey in learner.journeys.items():
            if not journey.started:
                continue
            measured = measure_journey_duration(db, journey_id=journey_id)
            if measured.active_seconds is not None:
                minutes[journey.local_date] += measured.active_seconds / 60.0
        learner.minutes_by_day = dict(minutes)


def _learner_row(learner: _Learner) -> dict[str, Any]:
    user = learner.user
    return {
        "user_id": str(user.id),
        "email": user.email,
        "synthetic": bool(user.is_synthetic),
        "signup_date": learner.signup_date.isoformat(),
        "timezone": str(learner.zone),
        "returns": {f"d{offset}": learner.returned(offset) for offset in RETURN_DAYS},
        "days_started": len(learner.started_days()),
        "days_completed": len(learner.completed_days()),
        "median_active_minutes": _median(list(learner.minutes_by_day.values())),
        "stops": learner.stops(),
    }


def _cohort_row(week: date, members: list[_Learner]) -> dict[str, Any]:
    returns: dict[str, dict[str, Any]] = {}
    for offset in RETURN_DAYS:
        answers = [learner.returned(offset) for learner in members]
        due = [answer for answer in answers if answer is not None]
        returns[f"d{offset}"] = _cell(sum(1 for answer in due if answer), len(due))
    stops: Counter[str] = Counter(
        stop["after_step"] for learner in members for stop in learner.stops()
    )
    all_minutes = [value for learner in members for value in learner.minutes_by_day.values()]
    return {
        "week_start": week.isoformat(),
        "learners": len(members),
        "returns": returns,
        "days_started": sum(len(learner.started_days()) for learner in members),
        "days_completed": sum(len(learner.completed_days()) for learner in members),
        "median_active_minutes": _median(all_minutes),
        "stops": [
            {"after_step": step, "days": days}
            for step, days in sorted(stops.items(), key=lambda item: (-item[1], item[0]))
        ],
        "learner_rows": sorted(
            (_learner_row(learner) for learner in members),
            key=lambda row: (row["signup_date"], row["user_id"]),
        ),
    }


def cohort_table_lines(report: dict[str, Any]) -> list[str]:
    """The cohort table as Markdown, for the nightly digest.

    Cohort rows only: the digest is posted in a public repository, so no learner rows,
    no ids and no emails.
    """

    headers = ["Sign-up week", "Learners"] + [f"Day {offset}" for offset in RETURN_DAYS]
    headers += ["Days done / started", "Median min/day", "Unfinished days stopped after"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
    ]
    for row in report.get("cohorts", []):
        stops = ", ".join(f"{stop['after_step']} ({stop['days']})" for stop in row["stops"]) or "none"
        minutes = row["median_active_minutes"]
        cells = [row["week_start"], str(row["learners"])]
        cells += [row["returns"][f"d{offset}"]["display"] for offset in RETURN_DAYS]
        cells += [
            f"{row['days_completed']} of {row['days_started']}",
            "unknown" if minutes is None else f"{minutes:g}",
            stops,
        ]
        lines.append("| " + " | ".join(cells) + " |")
    if not report.get("cohorts"):
        lines.append("| no sign-ups in these weeks |" + " |" * (len(headers) - 1))
    lines.append("")
    excluded = report.get("synthetic_excluded", 0)
    lines.append(
        f"Under {report.get('min_learners_for_rate', MIN_LEARNERS_FOR_RATE)} due learners a cell "
        f"shows counts, not a percentage. Synthetic accounts left out: {excluded}."
    )
    return lines


__all__ = [
    "BEFORE_FIRST_STEP",
    "MIN_LEARNERS_FOR_RATE",
    "RETURN_DAYS",
    "build_cohorts",
    "cohort_table_lines",
]
