"""«Demain» (steering read 2026-10-24): the finished day's choice of tomorrow's thread.

The season's day plans are not a chain (``season.director.tomorrow_options``): a
finished day may offer the plan's own thread and up to two the learner pulls
forward. :func:`recap_tomorrow` reads that choice for the recap; :func:`pick`
records the learner's pick in the season state, where the next day's brief reads it
(``season.director.learner_pick``).

The pick becomes the day's one tomorrow-hook (#237), filed where the settlement filed
the engine's: the living story's ``next_teaser`` (Home and the morning push), the
scene's ``next_teaser_fr`` (the last panel's «À suivre…» and the Feuilleton's filed
day) and the recap (the finished card). One line, the learner's own choice, in A1
French: «On va cuisiner avec Lila.»

Reads, and one locked write. Never a model call.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User

#: The ledger row each pick writes: which thread, and whether it was the plan's own.
PICKED_EVENT = "story_tomorrow_picked"


def _event_id(journey: DailyJourney) -> str:
    return f"journey:{journey.id}:story"


def _view(choice: dict[str, Any], picked: str | None) -> dict[str, Any]:
    return {"options": [dict(row) for row in choice["options"]], "picked": picked}


def recap_tomorrow(user: User, journey: DailyJourney, live: dict[str, Any]) -> dict[str, Any] | None:
    """The recap's ``tomorrow`` (``{options, picked}``), or None when there is no choice."""

    from app.services.season import runtime as season_runtime

    choice = season_runtime.tomorrow_choice(live, user=user, seed=str(user.id), event_id=_event_id(journey))
    return _view(choice, choice["picked"]) if choice else None


def hook_for(label_fr: str) -> str:
    """The pick as tomorrow's line: «Cuisiner avec Lila» → «On va cuisiner avec Lila.»

    A pick label is an infinitive phrase (``season.format`` checks it), so A1's near
    future reads right the evening it is picked and the morning it is pushed.
    """

    label = " ".join(str(label_fr or "").split()).rstrip(" .")
    return f"On va {label[:1].lower()}{label[1:]}." if label else ""


def _scene(db: Session, user: User, scene_id: Any) -> Any:
    from app.db.models.graphic_novel import GraphicNovelScene

    try:
        key = uuid.UUID(str(scene_id))
    except (TypeError, ValueError):
        return None
    scene = db.get(GraphicNovelScene, key, with_for_update=True, populate_existing=True)
    return scene if scene is not None and scene.user_id == user.id else None


def pick(
    db: Session, *, user: User, journey: DailyJourney, premise_id: str, scene_id: Any = None
) -> dict[str, Any] | None:
    """Record ``premise_id`` for the season's next day and file it as the day's hook.

    Returns the journey's recap as it now reads, or None, writing nothing, when the
    thread is not on offer: the plan leaves no choice, this journey's exchange is no
    longer the last one played, or ``premise_id`` is not among the options. Picking
    again replaces the pick, and its line.
    """

    from app.services import living_story as engine
    from app.services.pilot_events import PilotEventService
    from app.services.season import runtime as season_runtime
    from app.services.story_page import HOOK_PAYLOAD_KEY

    # The order every story writer takes (``living_story._lock_context``): the
    # learner's row, then the thread.
    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    thread = engine._active_thread(db, user, lock=True)
    if thread is None:
        return None
    state = dict(thread.state or {})
    seed, event_id = str(user.id), _event_id(journey)
    picked = season_runtime.pick_tomorrow(
        dict(state.get(engine.STATE_KEY) or {}), premise_id, user=user, seed=seed, event_id=event_id
    )
    choice = (
        season_runtime.tomorrow_choice(picked, user=user, seed=seed, event_id=event_id) if picked else None
    )
    if choice is None:
        return None
    option = next(row for row in choice["options"] if row["premise_id"] == premise_id)
    hook = hook_for(option["label_fr"])
    picked[engine.TEASER_KEY] = {
        "text_fr": hook,
        "character_id": None,
        "date": journey.local_date.isoformat(),
        "ref": f"tomorrow:{choice['gap']}.{choice['day']}:{premise_id}",
        # Unvoiced, like a tentpole's «À suivre…»: nobody in the story says it.
        "kind": "season",
        "source_event_id": event_id,
    }
    state[engine.STATE_KEY] = picked
    thread.state = state
    scene = _scene(db, user, scene_id) if scene_id else None
    if scene is not None:
        scene.script_payload = {**(scene.script_payload or {}), HOOK_PAYLOAD_KEY: hook}
    PilotEventService(db).record(
        PICKED_EVENT,
        user_id=user.id,
        entity_type="daily_journey",
        entity_id=journey.id,
        payload={
            "gap": choice["gap"],
            "day": choice["day"],
            "premise": premise_id,
            "planned": bool(option.get("planned")),
            "options": [row["premise_id"] for row in choice["options"]],
        },
    )
    return {
        **dict(journey.recap_snapshot or {}),
        "tomorrow": _view(choice, premise_id),
        "teaser": {"text_fr": hook, "character_id": None, "character_name": None, "source": "engine"},
        "teaser_fr": hook,
    }


__all__ = ["PICKED_EVENT", "hook_for", "pick", "recap_tomorrow"]
