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


def season_frontier(db: Session, season_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    """``{"season": id, "segments": ["t1", "g3"], "frontier": "t1" | None}``: the
    segments of the season recently active learners are on, in the season's order,
    and the earliest of them (None when nobody is on it)."""

    hit = _cache.get(season_id)
    if now is None and hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    from app.services.living_story import STATE_KEY
    from app.services.season.runtime import learner_date

    moment = now or datetime.now(UTC)
    try:
        season = load_season(season_id)
    except Exception:  # noqa: BLE001 - an unknown season has no frontier
        return {"season": season_id, "segments": [], "frontier": None}
    order = [segment.id for segment in season.segments]
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
    at: set[int] = set()
    for state, user in rows:
        live = (state or {}).get(STATE_KEY) or {}
        season_state = live.get(SEASON_KEY)
        if not isinstance(season_state, dict) or str(season_state.get("id") or "") != season_id:
            continue
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
