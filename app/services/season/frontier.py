"""Where a season's learners stand: the forge builds the places their next pages need.

The forge (``scripts/forge/forge.py queue --season --from api``) builds the season's
places in the order the learners' pages reach them. It used to be told the segment by
hand (``--from g3``), and the world fell behind the story the day the learner moved
on. This reads it from the lives themselves: the segments the learners who played in
the last fortnight are on, so the place someone's page reaches soonest is built first.

Public (the nightly forge has no account) and so says as little as it can: segment
ids, never a learner, a count or a date of theirs.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.season.clock import SEASON_KEY
from app.services.season.epilogue import position_for
from app.services.season.format import load_season

#: A learner who has not played for this long does not hold the forge back.
ACTIVE_DAYS = 14
#: The lives read per call, newest first.
MAX_THREADS = 200
#: One read of the lives per this many seconds and season: the route is public.
CACHE_SECONDS = 600

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_orders_cache: dict[str, tuple[float, dict[str, Any]]] = {}
#: The orders the forge reads, most asked for first.
MAX_ORDERS = 30


def season_frontier(db: Session, season_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """``{"season": id, "segments": ["t1", "g3"], "frontier": "t1" | None}``: the
    segments of the season recently active learners are on, in the season's order,
    and the earliest of them (None when nobody is on it)."""

    hit = _cache.get(season_id)
    if now is None and hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    from app.services.season.runtime import learner_date

    moment = now or datetime.now(UTC)
    try:
        season = load_season(season_id)
    except Exception:  # noqa: BLE001 - an unknown season has no frontier
        return {"season": season_id, "segments": [], "frontier": None}
    order = [segment.id for segment in season.segments]
    at: set[int] = set()
    for live, user in _season_lives(db, season_id, moment):
        season_state = live.get(SEASON_KEY)
        try:
            pos = position_for(season, dict(season_state), today=learner_date(user, moment))
        except Exception:  # noqa: BLE001 - one unreadable life never hides the others
            logger.exception("season frontier: a life of %s could not be placed", season_id)
            continue
        if pos.segment is not None and not pos.finished and pos.segment.id in order:
            at.add(order.index(pos.segment.id))
    on = [order[index] for index in sorted(at)]
    result = {"season": season_id, "segments": on, "frontier": on[0] if on else None}
    if now is None:
        _cache[season_id] = (time.monotonic(), result)
    return result


def _season_lives(db: Session, season_id: str, moment: datetime):
    """``(live, user)`` for each recently active life playing ``season_id``, newest first."""

    from app.services.living_story import STATE_KEY

    rows = db.execute(
        select(SerialThread.state, User)
        .join(User, User.id == SerialThread.user_id)
        .where(
            SerialThread.status == "active",
            SerialThread.updated_at >= moment - timedelta(days=ACTIVE_DAYS),
        )
        .order_by(SerialThread.updated_at.desc())
        .limit(MAX_THREADS)
    ).all()
    for state, user in rows:
        live = (state or {}).get(STATE_KEY) or {}
        season_state = live.get(SEASON_KEY)
        if isinstance(season_state, dict) and str(season_state.get("id") or "") == season_id:
            yield live, user


def _learner_names(live: dict, user: User) -> set[str]:
    """The words that name this learner: their account's name and address, and the
    name they gave the cast in the story."""

    from app.services import story_memory

    told = story_memory.name_in(story_memory.full_view(live.get(story_memory.MEMORY_KEY))) or ""
    words = [*str(getattr(user, "full_name", "") or "").split(), str(getattr(user, "email", "") or "").split("@")[0], *told.split()]
    return {word.casefold() for word in words if len(word) >= 3}


def _personal(text: str, names: set[str]) -> bool:
    """Whether a mark names its learner: never published."""

    folded = text.casefold()
    return any(name in folded for name in names)


def world_orders(db: Session, season_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """What the season's recent lives have left in Le Quartier (``living_story.WorldMark``),
    merged across lives, most asked for first: the forge builds from it, a little every
    night. Fiction only: a mark that names its learner is left out."""

    hit = _orders_cache.get(season_id)
    if now is None and hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    moment = now or datetime.now(UTC)
    merged: dict[tuple, dict[str, Any]] = {}
    for live, user in _season_lives(db, season_id, moment):
        names = _learner_names(live, user)
        for mark in live.get("world_marks") or []:
            if not isinstance(mark, dict) or mark.get("kind") not in ("thing", "place") or not mark.get("name_fr"):
                continue
            name = " ".join(str(mark["name_fr"]).split())[:80]
            look = " ".join(str(mark.get("look") or "").split())[:200]
            if _personal(f"{name} {look}", names):
                continue
            key = (mark["kind"], name.casefold(), mark.get("location_id"))
            row = merged.setdefault(
                key,
                {"kind": mark["kind"], "name_fr": name, "location_id": mark.get("location_id"), "look": look, "times": 0, "lives": 0},
            )
            row["times"] += max(1, int(mark.get("times") or 1))
            row["lives"] += 1
            row["look"] = row["look"] or look
    orders = sorted(merged.values(), key=lambda row: (-row["lives"], -row["times"], row["name_fr"]))[:MAX_ORDERS]
    result = {"season": season_id, "orders": orders}
    if now is None:
        _orders_cache[season_id] = (time.monotonic(), result)
    return result


def world_state(live: dict) -> dict[str, Any]:
    """One learner's own world, for Le Quartier to lay: the season flags their story set
    and the marks it left."""

    from app.services.season.flags import stored_flags

    season_state = live.get(SEASON_KEY) if isinstance(live.get(SEASON_KEY), dict) else None
    marks = [
        {key: mark.get(key) for key in ("id", "kind", "name_fr", "location_id", "look", "times", "day")}
        for mark in live.get("world_marks") or []
        if isinstance(mark, dict)
    ]
    return {
        "season": str(season_state.get("id")) if season_state and season_state.get("id") else None,
        "flags": dict(stored_flags(season_state)) if season_state else {},
        "marks": marks,
    }
