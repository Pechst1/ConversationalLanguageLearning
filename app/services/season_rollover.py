"""S5 · the season rollover as stored state, moved by the date, never by a request.

A finished season used to be followed inside the learner's last answer: the
settle called the season writer with the user and the resolution rows locked
(walk #649: 40–66 s from the last answer to the ending). Now the request only
closes the season (``living_story.roll_over_season``, no model call) and stores
one rollover state on the life, ``live["rollover"]``:

* ``pending`` — the interlude is named, and the writer job is writing;
* ``interlude`` — the interlude is named, and nothing is writing (the writer is
  off, or its attempts are spent): the promised date brings the reprise;
* ``written`` — a next season is ready (``season_file``), or has begun
  (``installed_on``);
* ``reprise`` — the promised date came with nothing written; the reprise began.

:func:`advance` is the sweep's step for one life: a written season waiting is
installed between two days, and on the promised date the next season begins
whether or not a chapter closes. Home, the premiere card and the named interlude
read this state (``journey_absence``); no screen infers it.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)

STATE_KEY = "rollover"
PENDING = "pending"
WRITTEN = "written"
INTERLUDE = "interlude"
REPRISE = "reprise"
STATES = (PENDING, WRITTEN, INTERLUDE, REPRISE)


def store(live: dict, state: str, **fields: Any) -> dict:
    """Write the life's rollover state (a fresh record: nothing from the last one)."""

    if state not in STATES:
        raise ValueError(f"unknown rollover state {state!r}")
    live[STATE_KEY] = {"state": state, **{key: value for key, value in fields.items() if value is not None}}
    return live[STATE_KEY]


def state_of(live: dict | None) -> dict:
    row = (live or {}).get(STATE_KEY)
    return dict(row) if isinstance(row, dict) and row.get("state") in STATES else {}


def is_open(row: dict) -> bool:
    """A rollover that has not begun its next season yet."""

    return bool(row) and not row.get("installed_on")


def _live_key() -> str:
    from app.services.living_story import STATE_KEY as LIVE_KEY

    return LIVE_KEY


def open_rollovers(db: Session) -> list[UUID]:
    """The active lives whose rollover is open (the sweep's work list)."""

    from app.db.models.serial import SerialThread

    rows = db.execute(
        select(SerialThread.id, SerialThread.state).where(SerialThread.status == "active")
    ).all()
    key = _live_key()
    return [
        thread_id
        for thread_id, state in rows
        if is_open(state_of(((state or {}).get(key) or {}) if isinstance(state, dict) else {}))
    ]


def _between_days(db: Session, user_id: Any, today: date) -> bool:
    """No day of this learner is open: a new season may begin without changing one."""

    from app.db.models.daily_journey import OCCUPYING_STATUS_VALUES, DailyJourney

    return (
        db.scalars(
            select(DailyJourney.id).where(
                DailyJourney.user_id == user_id,
                DailyJourney.status.in_(sorted(OCCUPYING_STATUS_VALUES)),
            )
        ).first()
        is None
    )


def advance(db: Session, thread_id: UUID, *, today: date) -> str:
    """One life's rollover, moved by the date. Short, locked, and model-free.

    Returns ``idle`` (nothing open), ``waiting`` (before the date, nothing ready),
    ``busy`` (a written season is ready but a day is open), or the state the
    next season began in (``written`` / ``reprise``). Commits what it changed."""

    from app.db.models.serial import SerialThread
    from app.services import living_story as engine

    thread = db.scalars(
        select(SerialThread).where(SerialThread.id == thread_id).with_for_update()
        .execution_options(populate_existing=True)
    ).first()
    if thread is None:
        db.rollback()
        return "idle"
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    row = state_of(live)
    if not is_open(row):
        db.rollback()
        return "idle"
    today_iso = today.isoformat()
    ready = row.get("state") == WRITTEN and bool(row.get("season_file"))
    due = bool(row.get("returns_on")) and today_iso >= str(row["returns_on"])
    if not ready and not due:
        db.rollback()
        return "waiting"
    if ready and not due and not _between_days(db, thread.user_id, today):
        db.rollback()
        return "busy"
    chapter = dict(live.get("chapter") or {})
    if chapter.get("interlude") and not engine.chapter_closing(chapter):
        # The interlude chapter does not outlive its season: the next scene opens the
        # new season's first chapter.
        live["chapter"] = {**chapter, "resolved": True, "closed_by_rollover": today_iso}
    if not engine.roll_over_season(
        db, thread, live, day=int(live.get("day_index") or 0), today=today_iso
    ):
        db.rollback()
        return "waiting"
    state[engine.STATE_KEY] = live
    thread.state = state
    flag_modified(thread, "state")
    flag_modified(thread, "world_bible")
    db.commit()
    began = state_of(live).get("state") or WRITTEN
    logger.info("season_rollover: thread %s began season %s (%s)", thread_id, live.get("season_index"), began)
    return began


__all__ = [
    "INTERLUDE",
    "PENDING",
    "REPRISE",
    "STATES",
    "STATE_KEY",
    "WRITTEN",
    "advance",
    "is_open",
    "open_rollovers",
    "state_of",
    "store",
]
