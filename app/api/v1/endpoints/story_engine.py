"""Read-only narrative projection plus reading-position persistence.

All story/learning mutations go through the existing daily-journey state machine.
Reading does not complete an episode. No private rubric or future ending is exposed.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.services.living_story import VERSION

router = APIRouter(prefix="/story-engine", tags=["story-engine"])


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    panel_index: int = Field(ge=0, strict=True)


def owned_scene(db, user, scene_id, *, lock=False):
    query = select(GraphicNovelScene).where(
        GraphicNovelScene.id == scene_id,
        GraphicNovelScene.user_id == user.id,
        GraphicNovelScene.prompt_version == VERSION,
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


def public_scene(scene, names: dict[str, str] | None = None):
    source = scene.source_snapshot or {}
    panels = sorted(scene.panels, key=lambda p: p.panel_index)
    names = names or {}
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
        "panels": [
            {
                "id": str(p.id),
                "index": p.panel_index,
                "narration_fr": (p.overlay_payload or {}).get("narration_fr", ""),
                "dialogue": [
                    {**line, "character_name": names.get(str(line.get("character_id")))}
                    for line in (p.overlay_payload or {}).get("dialogue", [])
                ],
                "image_url": p.image_url,
                "image_status": "setting_reference" if p.image_url else "unavailable",
            }
            for p in panels
        ],
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
        GraphicNovelScene.user_id == user.id, GraphicNovelScene.prompt_version == VERSION
    )
    if journey_id:
        query = query.where(
            GraphicNovelScene.source_snapshot["journey_id"].as_string() == str(journey_id)
        )
    if before:
        previous = owned_scene(db, user, before)
        # UUID tie-breaker gives deterministic pagination within a transaction.
        from sqlalchemy import and_, or_

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
    names = cast_names(db, rows[:20])
    return {
        "episodes": [public_scene(scene, names) for scene in rows[:20]],
        "next_cursor": str(rows[19].id) if len(rows) > 20 else None,
    }


@router.get("/episodes/{scene_id}")
def episode(scene_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scene = owned_scene(db, user, scene_id)
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
