"""Test-copy tooling (WP-111): put a learner's story on a given season day.

Used by ``scripts/season_jump.py`` so the owner can play T2 or T5 on the test copy
without living the days before it. Never called by the app.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.season.clock import SEASON_KEY, nominal_calendar
from app.services.season.flags import apply_sets
from app.services.season.format import load_season
from app.services.season.runtime import initial_relationships, initial_state
from app.services.season.world import season_world_bible


def jump_to_day(db: Session, user: User, *, day: int, season_id: str = "s1", flags: dict[str, Any] | None = None) -> dict[str, Any]:
    """The learner's next story day becomes season day ``day``. Returns a summary.

    The days before it are recorded as played on the bible's calendar (no flex),
    every tentpole already passed leaves its fixed facts, ``flags`` override the
    defaults, an open chapter is closed, and the thread moves to the season's world.
    The caller commits.
    """

    from app.services import living_story as engine

    season = load_season(season_id)
    if not 1 <= int(day) <= season.total_days:
        raise ValueError(f"day must be 1..{season.total_days}")
    world = season_world_bible(season_id)
    thread = db.scalar(
        select(SerialThread)
        .where(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
    )
    if thread is None:
        thread = SerialThread(
            user_id=user.id,
            world_bible=world,
            state=dict(world.get("initial_state") or {}),
            news_seed={},
            current_episode_index=0,
            status="active",
        )
        db.add(thread)
        db.flush()
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    season_state = initial_state(season_id)
    calendar = nominal_calendar(season)
    played = []
    for row in calendar[: int(day) - 1]:
        played.append({**row, "flex": 0, "date": None, "event_id": f"season_jump:{row['key']}"})
        if row["kind"] == "tentpole" and row["day_in_segment"] == 2:
            season_state = apply_sets(season, season_state, season.tentpoles[row["segment"]].state_out, source="season_jump")
    season_state["played"] = played
    season_state = apply_sets(season, season_state, dict(flags or {}), source="season_jump")
    live[SEASON_KEY] = season_state
    chapter = dict(live.get("chapter") or {})
    if chapter and not chapter.get("resolved"):
        live["chapter"] = {**chapter, "resolved": True, "closed_by": "season_jump"}
    live["day_index"] = max(int(live.get("day_index") or 0), int(day) - 1)
    state[engine.STATE_KEY] = live
    state["relationships"] = {**dict(state.get("relationships") or {}), **initial_relationships(season_id)}
    thread.world_bible = world
    thread.state = state
    db.flush()
    return {"next": calendar[int(day) - 1], "played": len(played), "flags": season_state.get("flags")}
