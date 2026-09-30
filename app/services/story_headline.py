"""WP-109 «Une seule maison»: today's episode, as Home and the Feuilleton headline it.

One answer to «where is the story?»: the day's episode is headlined with its number,
its title (when it is known), yesterday's «À suivre…» and the faces of who is in it.

* **Title.** The day's scene once the journey exists. Before that, the season's
  tentpole title on a tentpole day (authored, known in advance). A generated day's
  title is not known until the director writes it, and nothing is invented: the
  teaser leads instead.
* **Teaser.** The «À suivre…» written when the previous day settled — only when it
  was written on an earlier day (after today's ending it already speaks of tomorrow).
* **Cast.** Who speaks in the day's scene; before it exists, who speaks on the
  tentpole's page, or the teaser's speaker.

Read-only and cheap: one thread read, the journey's scene when there is one, no model.
Returns ``None`` when the story engine is not the day's story, or once the day's
episode is over (the finished card has its own recap and teaser).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: Faces on the headline, at most.
MAX_CAST = 4
_NOT_CAST = {"toi", "learner", "you", "narrator", "caption", "all", "sms", "letter", "card", ""}


def _cast_names(world: dict[str, Any]) -> dict[str, str]:
    return {
        str(member.get("id")): str(member.get("name"))
        for member in (world or {}).get("cast") or []
        if member.get("id") and member.get("name")
    }


def _ordered(ids: list[str]) -> list[str]:
    seen: list[str] = []
    for value in ids:
        if value not in _NOT_CAST and value not in seen:
            seen.append(value)
    return seen[:MAX_CAST]


def _scene_cast(db: Session, journey: Any) -> tuple[str | None, list[str], bool, str | None]:
    """The day's scene: (title, speakers, finished, the first panel's picture)."""

    from sqlalchemy import select

    from app.db.models.graphic_novel import GraphicNovelScene
    from app.services.living_story import ENGINE_VERSION_PREFIX

    scene = db.scalars(
        select(GraphicNovelScene)
        .where(
            GraphicNovelScene.user_id == journey.user_id,
            GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%"),
            GraphicNovelScene.source_snapshot["journey_id"].as_string() == str(journey.id),
        )
        .order_by(GraphicNovelScene.created_at.desc())
    ).first()
    if scene is None:
        return None, [], False, None
    panels = sorted(scene.panels, key=lambda p: p.panel_index)
    speakers = [
        str(line.get("character_id") or "")
        for panel in panels
        for line in (panel.overlay_payload or {}).get("dialogue") or []
    ]
    image = next((panel.image_url for panel in panels if panel.image_url), None)
    return scene.title or None, _ordered(speakers), scene.status in ("completed", "abandoned"), image


def _tentpole(live: dict, user: Any) -> tuple[str | None, list[str], str | None, str | None]:
    """A season tentpole day: (title, speakers, season title, the opening place's
    picture). Gap days: (None, [], season, None)."""

    from app.services.season import runtime as season_runtime
    from app.services.season.world import plate_for

    today = season_runtime.today_for(live, user=user, seed=str(user.id))
    if today is None:
        return None, [], None, None
    if not today.pos.is_tentpole:
        return None, [], today.season.title_fr, None
    page = season_runtime.page_for(today) or {}
    speakers: list[str] = []
    image: str | None = None
    for movement in page.get("movements") or []:
        panels = [movement] if movement.get("kind") == "panel" else [movement.get("panel") or {}]
        for panel in panels:
            speakers += [str(line.get("who") or "") for line in panel.get("lines") or []]
            image = image or plate_for(panel.get("location_id"))
    return page.get("title_fr"), _ordered(speakers), today.season.title_fr, image


def episode_headline(db: Session, user: Any, journey: Any = None, *, local_date: Any = None) -> dict[str, Any] | None:
    """``{edition_no, title_fr, teaser_fr, season_title_fr, cast: [{id, name}]}`` or None."""

    from app.config import settings
    from app.services import living_story as engine

    if not getattr(settings, "ATELIER_STORY_ENGINE_ENABLED", False):
        return None
    try:
        # No thread yet (the very first day): a life not yet begun plays the enabled
        # season, whose first page is known.
        thread = engine._active_thread(db, user)
        live = dict(((thread.state if thread else None) or {}).get(engine.STATE_KEY) or {})
        world = thread.world_bible if thread is not None and isinstance(thread.world_bible, dict) else {}
        names = _cast_names(world)

        title: str | None = None
        cast: list[str] = []
        image: str | None = None
        edition_no: int | None = None
        if journey is not None:
            if str(getattr(journey, "status", "")) in ("completed", "ended_early"):
                return None
            title, cast, finished, image = _scene_cast(db, journey)
            if finished:
                return None
            from app.services.seals import edition_no_for

            edition_no = edition_no_for(db, journey)
        season_title: str | None = None
        if title is None:
            planned_title, planned_cast, season_title, planned_image = _tentpole(live, user)
            title = planned_title
            cast = cast or planned_cast
            image = image or planned_image
        else:
            _unused, _cast, season_title, planned_image = _tentpole(live, user)
            image = image or planned_image
        if edition_no is None:
            edition_no = int((thread.current_episode_index if thread else 0) or 0) + 1

        teaser = live.get(engine.TEASER_KEY) or {}
        teaser_fr = str(teaser.get("text_fr") or "").strip() or None
        written = str(teaser.get("date") or "")
        if teaser_fr and local_date is not None and written == str(local_date):
            teaser_fr = None  # written by today's ending: it speaks of tomorrow
        if not cast and teaser_fr and teaser.get("character_id"):
            cast = _ordered([str(teaser["character_id"])])
        if not (title or teaser_fr or thread is not None or season_title):
            return None  # a life with no story yet and no season to open: nothing to say
        from app.services.season.runtime import season_id_for
        from app.services.season.world import season_cast_names

        season_id = season_id_for(live)
        more = season_cast_names(str(season_id)) if season_id else {}
        return {
            "edition_no": edition_no,
            "title_fr": title,
            "teaser_fr": teaser_fr,
            "season_title_fr": season_title,
            # The episode's picture for Home's card: the scene's first panel, else
            # the tentpole's opening place.
            "image_url": image,
            "cast": [{"id": who, "name": names.get(who) or more.get(who) or who.split("_")[0].title()} for who in cast],
        }
    except Exception:  # noqa: BLE001 - a headline never costs Home
        logger.exception("story_headline: headline unavailable")
        return None
