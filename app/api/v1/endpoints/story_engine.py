"""Read-only narrative projection plus reading-position persistence.

All story/learning mutations go through the existing daily-journey state machine.
Reading does not complete an episode. No private rubric or future ending is exposed.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.schemas.story_archive import StoryArchive
from app.services.living_story import ENGINE_VERSION_PREFIX

router = APIRouter(prefix="/story-engine", tags=["story-engine"])


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    panel_index: int = Field(ge=0, strict=True)


#: WP-93: a «Coulisses» side page (``app/services/coulisses.py``) is stored with a
#: prompt version outside the engine prefix, so it never lists as a day's episode;
#: the READ step still opens it by id.
SIDE_PAGE_VERSION_PREFIX = "coulisses-"


def owned_scene(db, user, scene_id, *, lock=False, side_pages=False):
    versions = GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%")
    if side_pages:
        versions = or_(
            versions, GraphicNovelScene.prompt_version.like(f"{SIDE_PAGE_VERSION_PREFIX}%")
        )
    query = select(GraphicNovelScene).where(
        GraphicNovelScene.id == scene_id,
        GraphicNovelScene.user_id == user.id,
        versions,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    scene = db.scalar(query)
    if scene is None:
        raise HTTPException(404, "Story scene not found")
    return scene


def cast_names(db, scenes) -> dict[str, str]:
    """Display names for the cast ids that dialogue lines carry.

    Read from the owning thread's world bible so the reader never has to keep
    its own copy of the cast; an unknown id simply gets no display name.
    """
    thread_ids = {scene.serial_thread_id for scene in scenes if scene.serial_thread_id}
    if not thread_ids:
        return {}
    names: dict[str, str] = {}
    for bible in db.scalars(
        select(SerialThread.world_bible).where(SerialThread.id.in_(thread_ids))
    ):
        for member in (bible or {}).get("cast", []) or []:
            if member.get("id") and member.get("name"):
                names.setdefault(str(member["id"]), str(member["name"]))
    return names


def panel_image_status(panel) -> str:
    """``panel_art`` (the panel's own drawing), ``rendering`` (the plate, while the
    drawing is on its way), ``setting_reference`` (the plate) or ``unavailable``."""

    if not panel.image_url:
        return "unavailable"
    meta = panel.generation_metadata or {}
    if meta.get("image_source") == "panel_art":
        return "panel_art"
    if meta.get("image_status") == "rendering":
        return "rendering"
    return "setting_reference"


def panel_plate_url(panel) -> str | None:
    """WP-116: the location plate under a panel. New panels keep it in their metadata
    when a drawing replaces ``image_url``; an undrawn panel's image is the plate."""

    meta = panel.generation_metadata or {}
    if meta.get("plate_url"):
        return str(meta["plate_url"])
    if panel.image_url and meta.get("image_source") != "panel_art":
        return panel.image_url
    return None


def public_grammar_focus(scene) -> dict | None:
    """WP-92: the unit the scene was written to show, as the story lane stored it
    (``script_payload.grammar_focus`` = ``{unit_id, title_fr, title_native, woven}``).

    Read defensively: a scene written before WP-92 has none, and a malformed
    value is dropped rather than shipped.
    """

    focus = (scene.script_payload or {}).get("grammar_focus")
    if not isinstance(focus, dict) or focus.get("unit_id") in (None, ""):
        return None
    return {
        "unit_id": str(focus.get("unit_id")),
        "title_fr": str(focus.get("title_fr") or ""),
        "title_native": str(focus.get("title_native") or ""),
        "woven": bool(focus.get("woven")),
    }


def public_scene(scene, names: dict[str, str] | None = None):
    source = scene.source_snapshot or {}
    panels = sorted(scene.panels, key=lambda p: p.panel_index)
    names = names or {}
    season_id = ((scene.script_payload or {}).get("season") or {}).get("id")
    if season_id:
        # WP-111: an authored page's minor voices (the clerk, Odile in a flashback)
        # are named by the season, not the director's world.
        from app.services.season.world import season_cast_names

        names = {**season_cast_names(str(season_id)), **names}
    public_panels = [
        {
            "id": str(p.id),
            "index": p.panel_index,
            "narration_fr": (p.overlay_payload or {}).get("narration_fr", ""),
            # WP-90: one sentence describing the picture, for VoiceOver.
            "alt_native": (p.overlay_payload or {}).get("alt_native"),
            "dialogue": [
                {**line, "character_name": names.get(str(line.get("character_id")))}
                for line in (p.overlay_payload or {}).get("dialogue", [])
            ],
            "image_url": p.image_url,
            "image_status": panel_image_status(p),
            "plate_url": panel_plate_url(p),
        }
        for p in panels
    ]
    from app.services.story_page import episode_page

    return {
        "id": str(scene.id),
        "scene_id": str(scene.id),
        "serial_thread_id": str(scene.serial_thread_id),
        "serial_episode_id": source.get("serial_episode_id"),
        "journey_id": source.get("journey_id"),
        "title_fr": scene.title,
        "status": scene.status,
        "chapter": source.get("chapter"),
        "panel_index": source.get("panel_index", 0),
        # WP-92: the form this page shows («Rayons X» marks it in the lines).
        "grammar_focus": public_grammar_focus(scene),
        "panels": public_panels,
        # WP-110: the finished day as one page, the learner's lines in it.
        "page": episode_page(scene, public_panels, names),
        "resolution": {
            "text_fr": (scene.recap_payload or {}).get("resolution_fr"),
            "summary_native": (scene.recap_payload or {}).get("summary_native"),
        }
        if scene.status == "completed"
        else None,
    }


@router.get("/episodes")
def episodes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    before: UUID | None = None,
    journey_id: UUID | None = None,
):
    query = select(GraphicNovelScene).where(
        GraphicNovelScene.user_id == user.id, GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%")
    )
    if journey_id:
        query = query.where(
            GraphicNovelScene.source_snapshot["journey_id"].as_string() == str(journey_id)
        )
    if before:
        previous = owned_scene(db, user, before)
        # UUID tie-breaker gives deterministic pagination within a transaction.
        from sqlalchemy import and_

        query = query.where(
            or_(
                GraphicNovelScene.created_at < previous.created_at,
                and_(
                    GraphicNovelScene.created_at == previous.created_at,
                    GraphicNovelScene.id < previous.id,
                ),
            )
        )
    rows = list(
        db.scalars(
            query.order_by(GraphicNovelScene.created_at.desc(), GraphicNovelScene.id.desc()).limit(
                21
            )
        )
    )
    from app.services.panel_art import heal_stale_rendering

    heal_stale_rendering(db, rows[:20])
    names = cast_names(db, rows[:20])
    return {
        "episodes": [public_scene(scene, names) for scene in rows[:20]],
        "next_cursor": str(rows[19].id) if len(rows) > 20 else None,
    }


@router.get("/episodes/{scene_id}")
def episode(scene_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """One of the owner's pages with its panels — a day's episode, or (WP-93) the
    «Lecture» page a READ step names (yesterday's episode, or today's «Coulisses»).
    Anyone else's page, or an unknown id, is a 404."""
    scene = owned_scene(db, user, scene_id, side_pages=True)
    from app.services.panel_art import heal_stale_rendering

    heal_stale_rendering(db, [scene])  # WP-108: a drawing that never came is served as its plate
    return public_scene(scene, cast_names(db, [scene]))


@router.put("/episodes/{scene_id}/position")
def position(
    scene_id: UUID,
    payload: Position,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scene = owned_scene(db, user, scene_id, lock=True)
    if payload.panel_index >= len(scene.panels):
        raise HTTPException(422, "Panel index out of range")
    scene.source_snapshot = {**(scene.source_snapshot or {}), "panel_index": payload.panel_index}
    db.commit()
    return {"scene_id": str(scene.id), "panel_index": payload.panel_index}


@router.get("/archive", response_model=StoryArchive)
def archive(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    season: int | None = Query(default=None, ge=1),
):
    """WP-96 «Archives du journal»: every day the learner lived, as seasons of
    chapters of planches — the authored first day and fallback days included.
    Newest chapter first, days oldest first; one season's days per call
    (``?season=N``, default the newest)."""

    from app.services.story_archive import build_archive

    return build_archive(db, user, season=season)
