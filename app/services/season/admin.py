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

    The days before it are recorded as played on the bible's calendar (no flex), an
    open chapter is closed, and the thread moves to the season's world. The state is
    the one a real learner would have on that day (LOSS-RATE 2026-10-06), not the
    defaults alone:

    * every tentpole day already passed is settled by the runtime's own settle with
      no reply routed: what each turn sets whatever is said, each solve's default,
      Day B's fixed ``state_out`` (``s1.plan``, ``s1.went_with_lila_to_marin``… — the
      bare ``state_out`` left them unset from T6 on, a state no learner reaches). No
      choice is invented for the learner: ``flags`` set one;
    * every gap passed in full has staged its required moments (a real gap is not
      left before they are — WP-124b's bridge or the director stages them). A jump
      into the middle of a gap leaves that gap's moments owed, as a learner who
      missed them would have them;
    * the cast's registers follow the flags (Gus says «tu» after T3).

    ``flags`` then override all of it. The caller commits.
    """

    from app.services import living_story as engine
    from app.services.chrome_language import user_chrome_language
    from app.services.season.flags import effective_flags
    from app.services.season.page import resolve_day
    from app.services.season.runtime import _apply_registers, _settle_tentpole

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
    seed = str(user.id)
    band = engine.learner_level_band(user)
    language = user_chrome_language(user)
    passed = calendar[: int(day) - 1]
    for index, row in enumerate(passed):
        event_id = f"season_jump:{row['key']}"
        played.append({**row, "flex": 0, "date": None, "event_id": event_id})
        if row["kind"] != "tentpole":
            continue
        page = resolve_day(
            season,
            row["segment"],
            "a" if row["day_in_segment"] == 1 else "b",
            flags=effective_flags(season, season_state, seed=seed),
            band=band,
            language=language,
        ) or {}
        # No reply is routed: what a turn sets «whatever is said», each solve's
        # default and Day B's state_out — the runtime's own settle, nothing invented
        # about what this learner chose.
        season_state = _settle_tentpole(
            season,
            season_state,
            {"page": page, "position": {"segment": row["segment"], "day_in_segment": row["day_in_segment"]}},
            {},
            event_id=event_id,
            day=index + 1,
            seed=seed,
        )
    # A gap the jump passes in full staged its required moments; the gap the next day
    # belongs to (if any) keeps its own owed.
    current = calendar[int(day) - 1]["segment"]
    staged = [row for row in season_state.get("premises") or [] if isinstance(row, dict)]
    for gap_id in dict.fromkeys(row["segment"] for row in passed if row["kind"] == "gap"):
        gap = season.gaps.get(gap_id)
        if gap is None or gap_id == current:
            continue
        last = max(index + 1 for index, row in enumerate(passed) if row["segment"] == gap_id)
        for need in gap.required:
            if not any(row.get("gap") == gap_id and row.get("premise") == need.premise for row in staged):
                staged.append({"gap": gap_id, "premise": need.premise, "day": last, "event_id": f"season_jump:{gap_id}"})
    season_state["premises"] = staged
    season_state["played"] = played
    season_state = apply_sets(season, season_state, dict(flags or {}), source="season_jump")
    live[SEASON_KEY] = season_state
    chapter = dict(live.get("chapter") or {})
    if chapter and not chapter.get("resolved"):
        live["chapter"] = {**chapter, "resolved": True, "closed_by": "season_jump"}
    live["day_index"] = max(int(live.get("day_index") or 0), int(day) - 1)
    state[engine.STATE_KEY] = live
    relationships = {**dict(state.get("relationships") or {}), **initial_relationships(season_id)}
    _apply_registers(season, season_state, relationships)
    state["relationships"] = relationships
    thread.world_bible = world
    thread.state = state
    db.flush()
    return {"next": calendar[int(day) - 1], "played": len(played), "flags": season_state.get("flags")}
