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


def cast_variants(live: dict, *, seed: str | None = None) -> dict[str, str]:
    """WP-116: how the drawn cast looks for this learner.

    Camille's look follows ``s1.camille_gender``: the learner's own choice in T1 Day B
    once it is stored. Without ``seed`` only that choice is sent, and the client keeps
    Camille's face hidden.

    Walk 2026-10-13 (#107): no screen poses that choice yet, so the story already
    plays the seeded value (``flags.effective_flags``: the pronouns other characters
    use for Camille from T1 B on). With the learner's ``seed`` (``str(user.id)``,
    as the season runtime uses) that same value is sent from the day Camille walks
    in, so Camille has a face like the rest of the cast, and it is the face the
    story's «il» or «elle» already describes.
    """

    from app.services.season.clock import SEASON_KEY
    from app.services.season.flags import effective_flags, stored_flags

    state = (live or {}).get(SEASON_KEY)
    gender = stored_flags(state).get("s1.camille_gender")
    if gender not in ("f", "m") and seed:
        from app.services.season.format import load_season
        from app.services.season.runtime import season_id_for

        try:
            if season_id_for(live) == "s1":
                gender = effective_flags(load_season("s1"), state, seed=seed).get("s1.camille_gender")
        except Exception:  # noqa: BLE001 - a face is never worth the headline
            logger.exception("story_headline: Camille's seeded look unavailable")
    return {"camille_marchand": gender} if gender in ("f", "m") else {}


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
        reread = False
        if journey is not None:
            if str(getattr(journey, "status", "")) in ("completed", "ended_early"):
                return None
            title, cast, finished, image = _scene_cast(db, journey)
            if finished:
                return None
            from app.services.seals import edition_no_for
            from app.services.season.reprise import is_reprise_journey

            edition_no = edition_no_for(db, journey)
            if is_reprise_journey(journey):
                # #314: a re-read has no scene of its own, so the planned tentpole
                # (the page the story would have played) must not headline it.
                reread = True
                snapshot = journey.scenario_snapshot if isinstance(journey.scenario_snapshot, dict) else {}
                title = str(snapshot.get("title_fr") or "").strip() or None
                who = str(snapshot.get("character_id") or "")
                cast = _ordered([who]) if who else []
                image = str(snapshot.get("image_url") or "") or None
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
            # Before the day is planned: the number it will be given (seals.next_edition_no
            # is the rule the plan applies), not the thread's index on its own.
            edition_no = int((thread.current_episode_index if thread else 0) or 0) + 1
            if local_date is not None:
                from app.services.seals import next_edition_no

                edition_no = next_edition_no(db, user.id, local_date, base=edition_no)

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
            "reread": reread,
            "title_fr": title,
            "teaser_fr": teaser_fr,
            "season_title_fr": season_title,
            # The episode's picture for Home's card: the scene's first panel, else
            # the tentpole's opening place.
            "image_url": image,
            "cast": [{"id": who, "name": names.get(who) or more.get(who) or who.split("_")[0].title()} for who in cast],
            "cast_variants": cast_variants(live, seed=str(user.id)),
        }
    except Exception:  # noqa: BLE001 - a headline never costs Home
        logger.exception("story_headline: headline unavailable")
        return None
