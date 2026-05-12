"""Graphic Novel / Feuilleton practice API."""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import get_atelier_user
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.user import User
from app.schemas.graphic_novel import (
    GraphicNovelAttemptRequest,
    GraphicNovelAttemptResponse,
    GraphicNovelCompleteResponse,
    GraphicNovelCreateRequest,
    GraphicNovelSceneResponse,
    GraphicNovelTodayResponse,
)
from app.services.graphic_novel import (
    GraphicNovelCorrectionService,
    GraphicNovelGenerationError,
    GraphicNovelScheduler,
    serialize_attempt,
    serialize_scene,
)

router = APIRouter(prefix="/graphic-novel", tags=["graphic-novel"])


def _scene_or_404(db: Session, scene_id: UUID, user: User) -> GraphicNovelScene:
    scene = GraphicNovelScheduler(db).get(user=user, scene_id=scene_id)
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feuilleton scene not found")
    return scene


def _ensure_open(scene: GraphicNovelScene) -> None:
    if scene.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feuilleton scene already completed")


@router.get("/today", response_model=GraphicNovelTodayResponse)
async def get_graphic_novel_today(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelTodayResponse:
    return GraphicNovelTodayResponse(**(await GraphicNovelScheduler(db).today(current_user)))


@router.post("/scenes", response_model=GraphicNovelSceneResponse)
@router.post("/scenes/", response_model=GraphicNovelSceneResponse)
async def create_graphic_novel_scene(
    request: GraphicNovelCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelSceneResponse:
    if request.experience_mode == "reward":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reward Feuilleton mode is currently disabled.",
        )
    try:
        scene = await GraphicNovelScheduler(db).create(
            user=current_user,
            cadence=request.cadence,
            atelier_session_id=request.atelier_session_id,
            mission_id=request.mission_id,
            personal_input_item_id=request.personal_input_item_id,
            preferred_concept_ids=request.preferred_concept_ids,
            preferred_errata_ids=request.preferred_errata_ids,
            use_news=request.use_news,
            panel_count=request.panel_count,
            story_quality=request.story_quality,
            humor_style=request.humor_style,
            experience_mode=request.experience_mode,
            render_mode=request.render_mode,
            image_quality=request.image_quality,
            public_figure_mode=request.public_figure_mode,
            force_new=request.force_new,
            refresh_news=request.refresh_news,
        )
    except GraphicNovelGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "feuilleton_generation_failed",
                "message": "Today’s edition is being prepared.",
                "errors": exc.errors,
                "metadata": exc.metadata,
            },
        ) from exc
    return GraphicNovelSceneResponse(scene=serialize_scene(scene) or {})


@router.get("/scenes/{scene_id}", response_model=GraphicNovelSceneResponse)
def get_graphic_novel_scene(
    scene_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelSceneResponse:
    scene = _scene_or_404(db, scene_id, current_user)
    return GraphicNovelSceneResponse(scene=serialize_scene(scene) or {})


@router.post("/scenes/{scene_id}/attempts", response_model=GraphicNovelAttemptResponse)
def submit_graphic_novel_attempt(
    scene_id: UUID,
    request: GraphicNovelAttemptRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelAttemptResponse:
    scene = _scene_or_404(db, scene_id, current_user)
    _ensure_open(scene)
    try:
        attempt, errata = GraphicNovelCorrectionService(db).submit_attempt(
            user=current_user,
            scene=scene,
            task_id=request.task_id,
            answer_payload=request.answer_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    db.refresh(scene)
    return GraphicNovelAttemptResponse(
        attempt=serialize_attempt(attempt),
        correction=attempt.correction_payload or {},
        errata=errata,
        scene=serialize_scene(scene) or {},
    )


@router.post("/scenes/{scene_id}/complete", response_model=GraphicNovelCompleteResponse)
def complete_graphic_novel_scene(
    scene_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelCompleteResponse:
    scene = _scene_or_404(db, scene_id, current_user)
    completed = GraphicNovelScheduler(db).complete(user=current_user, scene=scene)
    return GraphicNovelCompleteResponse(
        scene=serialize_scene(completed) or {},
        recap=completed.recap_payload or {},
    )
