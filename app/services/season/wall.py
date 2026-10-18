"""Le mur du Mistral: the season's objects the learner has been handed, and the
marks their choices left on them.

Every tentpole of a scripted season turns on one object (the client draws them,
``web-frontend/lib/season-items.ts``), handed over once the tentpole's first page
is read. The wall is a projection of what the learner has read: a part of the
season counts once a page of it is completed, and parts come in order, so every
tentpole up to the furthest part read has been handed over. It works from any
device, because it reads the pages, not the device that was handed the object.

``marks`` carries the few choices an object shows (where the burnt Polaroid
went, what the learner promised Gus), and only once the learner has made them:
the season's defaults are never sent. Read-only: opening the wall opens no
thread and touches no state.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User

#: The choices an object shows, and the values it can draw.
MARK_FLAGS: dict[str, tuple[str, ...]] = {
    "s1.fire_photo": ("wall", "margaux"),
    "s1.promise_gus": ("yes", "half", "no"),
}

_PART = re.compile(r"^([tge])(\d+)$")


def _part(payload: Any) -> tuple[str, str, int] | None:
    """``(season_id, kind letter, number)`` of a page, or ``None`` off a season."""

    season = (payload or {}).get("season") if isinstance(payload, dict) else None
    if not isinstance(season, dict):
        return None
    season_id = str(season.get("season_id") or season.get("id") or "").strip()
    match = _PART.match(str(season.get("segment") or "").strip())
    if not season_id or not match:
        return None
    return season_id, match.group(1), int(match.group(2))


def marks_of(state: dict | None) -> dict[str, str]:
    """The choices the learner made that an object shows, from the season state."""

    from app.services.season.flags import stored_flags

    flags = stored_flags(state)
    return {key: str(flags[key]) for key, values in MARK_FLAGS.items() if str(flags.get(key) or "") in values}


def season_wall(db: Session, user: User) -> dict[str, Any]:
    """``{season_id, through, pages, marks}``.

    ``through`` is the furthest part number read: every tentpole up to it has been
    handed over. An epilogue page means the whole season (``None``: every tentpole
    the client knows of). ``pages`` maps a tentpole (``t3``) to the first page of it
    the learner read, to reread from the wall.
    """

    from app.services.living_story import ENGINE_VERSION_PREFIX, STATE_KEY
    from app.services.season.clock import SEASON_KEY

    empty: dict[str, Any] = {"season_id": None, "through": 0, "pages": {}, "marks": {}}
    thread = db.scalars(
        select(SerialThread)
        .where(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.created_at.desc())
    ).first()
    if thread is None:
        return empty
    scenes = db.scalars(
        select(GraphicNovelScene)
        .where(
            GraphicNovelScene.user_id == user.id,
            GraphicNovelScene.serial_thread_id == thread.id,
            GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%"),
            GraphicNovelScene.status == "completed",
        )
        .order_by(GraphicNovelScene.created_at.asc(), GraphicNovelScene.id.asc())
    ).all()

    season_id: str | None = None
    through = 0
    whole = False
    pages: dict[str, str] = {}
    for scene in scenes:
        part = _part(scene.script_payload)
        if part is None:
            continue
        sid, letter, number = part
        if season_id is None:
            season_id = sid
        if sid != season_id:
            continue
        if letter == "e":
            whole = True
            continue
        through = max(through, number)
        if letter == "t":
            pages.setdefault(f"t{number}", str(scene.id))
    if season_id is None:
        return empty

    state = thread.state if isinstance(thread.state, dict) else {}
    live = state.get(STATE_KEY) if isinstance(state.get(STATE_KEY), dict) else {}
    season_state = live.get(SEASON_KEY) if isinstance(live.get(SEASON_KEY), dict) else None
    return {
        "season_id": season_id,
        "through": None if whole else through,
        "pages": pages,
        "marks": marks_of(season_state),
    }
