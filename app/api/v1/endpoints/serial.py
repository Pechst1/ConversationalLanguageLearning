"""Serial World API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import get_atelier_user
from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.mission import RealWorldMission
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.schemas.serial import SerialAdvanceRequest, SerialThreadCreateRequest, SerialThreadRead
from app.services.serial import SerialThreadService

router = APIRouter(prefix="/serial", tags=["serial"])


def _ensure_enabled() -> None:
    if not settings.SERIAL_WORLD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "serial_world_disabled", "message": "Serial World is not enabled."},
        )


def _thread_or_404(db: Session, thread_id: UUID, user: User) -> SerialThread:
    thread = db.get(SerialThread, thread_id)
    if not thread or thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serial thread not found")
    return thread


@router.get("/today")
async def get_serial_today(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> dict:
    _ensure_enabled()
    return await SerialThreadService(db).today(current_user)


@router.post("/threads", response_model=SerialThreadRead)
@router.post("/threads/", response_model=SerialThreadRead)
async def create_serial_thread(
    request: SerialThreadCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> SerialThreadRead:
    _ensure_enabled()
    thread = await SerialThreadService(db).get_or_create_thread(
        current_user,
        world_bible=request.world_bible,
        state=request.state,
        news_seed=request.news_seed,
    )
    return SerialThreadRead.model_validate(thread)


@router.get("/threads/current/episodes")
async def list_current_serial_episodes(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> dict:
    _ensure_enabled()
    service = SerialThreadService(db)
    thread = await service.get_or_create_thread(current_user)
    return {"thread_id": str(thread.id), "episodes": service.episode_archive(thread)}


@router.get("/threads/current/cast")
async def get_current_serial_cast(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> dict:
    _ensure_enabled()
    service = SerialThreadService(db)
    thread = await service.get_or_create_thread(current_user)
    return {"thread_id": str(thread.id), "cast": service.cast_payload(thread)}


@router.post("/threads/{thread_id}/advance")
async def advance_serial_thread(
    thread_id: UUID,
    request: SerialAdvanceRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> dict:
    _ensure_enabled()
    thread = _thread_or_404(db, thread_id, current_user)
    mission = db.get(RealWorldMission, request.mission_id) if request.mission_id else None
    scene = db.get(GraphicNovelScene, request.scene_id) if request.scene_id else None
    if mission and mission.user_id != current_user.id:
        mission = None
    if scene and scene.user_id != current_user.id:
        scene = None
    if not mission and not scene:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mission_id or scene_id is required")
    try:
        return await SerialThreadService(db).apply_completion(
            thread,
            mission=mission,
            scene=scene,
            state_delta=request.state_delta.model_dump() if hasattr(request.state_delta, "model_dump") else request.state_delta,
            hook=request.hook.model_dump() if hasattr(request.hook, "model_dump") else request.hook,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
