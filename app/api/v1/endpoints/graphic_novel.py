"""Graphic Novel / Feuilleton practice API."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import get_atelier_user
from app.config import settings
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.serial import SerialEpisode, SerialThread
from app.db.models.user import User
from app.db.session import SessionLocal
from app.schemas.graphic_novel import (
    GraphicNovelAttemptRequest,
    GraphicNovelAttemptResponse,
    GraphicNovelCompleteResponse,
    GraphicNovelCreateRequest,
    GraphicNovelSceneResponse,
    GraphicNovelTodayResponse,
)
from app.services.cefr_progress import CEFRProgressService
from app.services.graphic_novel import (
    GraphicNovelCorrectionService,
    GraphicNovelGenerationError,
    GraphicNovelScheduler,
    GraphicNovelTargetVocabularyError,
    scene_matches_current_contract,
    serialize_attempt,
    serialize_scene,
)
from app.services.serial import SerialThreadService

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
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelSceneResponse:
    if request.experience_mode == "reward":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reward Feuilleton mode is currently disabled.",
        )
    create_kwargs = {
        "cadence": request.cadence,
        "atelier_session_id": request.atelier_session_id,
        "mission_id": request.mission_id,
        "serial_thread_id": request.serial_thread_id,
        "episode_index": request.episode_index,
        "personal_input_item_id": request.personal_input_item_id,
        "preferred_concept_ids": request.preferred_concept_ids,
        "preferred_errata_ids": request.preferred_errata_ids,
        "target_vocabulary_ids": request.target_vocabulary_ids,
        "use_news": request.use_news,
        "panel_count": request.panel_count,
        "story_quality": request.story_quality,
        "humor_style": request.humor_style,
        "experience_mode": request.experience_mode,
        "render_mode": request.render_mode,
        "image_quality": request.image_quality,
        "public_figure_mode": request.public_figure_mode,
        "force_new": request.force_new,
        "refresh_news": request.refresh_news,
    }
    if request.async_generation:
        scheduler = GraphicNovelScheduler(db)
        scene = scheduler.prepare_generation(
            user=current_user,
            cadence=request.cadence,
            atelier_session_id=request.atelier_session_id,
            mission_id=request.mission_id,
            serial_thread_id=request.serial_thread_id,
            episode_index=request.episode_index,
            personal_input_item_id=request.personal_input_item_id,
            image_quality=request.image_quality,
            force_new=request.force_new,
        )
        if request.serial_thread_id is not None and request.episode_index is not None:
            episode = (
                db.query(SerialEpisode)
                .filter(
                    SerialEpisode.thread_id == request.serial_thread_id,
                    SerialEpisode.episode_index == request.episode_index,
                )
                .first()
            )
            if episode:
                episode.kind = "feuilleton"
                episode.scene_id = scene.id
                episode.status = "writing"
                db.add(episode)
                db.commit()
        if scheduler.claim_prepared_generation(scene.id):
            background_tasks.add_task(
                _generate_prepared_scene,
                scene.id,
                current_user.id,
                {**create_kwargs, "force_new": True},
            )
        return GraphicNovelSceneResponse(scene=serialize_scene(scene) or {})
    try:
        scene = await GraphicNovelScheduler(db).create(
            user=current_user,
            **create_kwargs,
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
    except GraphicNovelTargetVocabularyError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unknown_target_vocabulary",
                "message": "One or more target vocabulary IDs could not be found.",
                "missing_ids": exc.missing_ids,
            },
        ) from exc
    return GraphicNovelSceneResponse(scene=serialize_scene(scene) or {})


def _generate_prepared_scene(scene_id: UUID, user_id: UUID, create_kwargs: dict[str, Any]) -> None:
    """Run the blocking story call after the response, on its own DB session/thread."""
    import asyncio

    db = SessionLocal()
    scheduler = GraphicNovelScheduler(db)
    try:
        user = db.get(User, user_id)
        if not user:
            raise ValueError("Feuilleton user not found")
        asyncio.run(
            scheduler.create(
                user=user,
                pending_scene_id=scene_id,
                # This function already runs after the HTTP response. Finish the
                # artwork here so an unavailable Celery worker cannot strand the
                # edition in `generating` with permanently queued panels.
                sync=True,
                **create_kwargs,
            )
        )
    except Exception as exc:  # noqa: BLE001 - persisted for a retryable UI state
        db.rollback()
        logger.exception("Prepared Feuilleton generation failed", scene_id=str(scene_id))
        scheduler.mark_generation_failed(scene_id, exc)
    finally:
        db.close()


@router.get("/scenes/{scene_id}", response_model=GraphicNovelSceneResponse)
def get_graphic_novel_scene(
    scene_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelSceneResponse:
    scene = _scene_or_404(db, scene_id, current_user)
    # A direct resume link must not revive an incompatible pre-redesign edition. Completed
    # scenes stay viewable as history; still-open stale scenes are reported as superseded so
    # the client requests a fresh edition under the current contract.
    if scene.status != "completed" and not scene_matches_current_contract(scene):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "feuilleton_scene_superseded",
                "message": "This edition predates the current Feuilleton and can no longer be resumed.",
            },
        )
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
async def complete_graphic_novel_scene(
    scene_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> GraphicNovelCompleteResponse:
    scene = _scene_or_404(db, scene_id, current_user)
    scheduler = GraphicNovelScheduler(db)
    missing_task_ids = scheduler.missing_required_task_ids(scene)
    if scene.status != "completed" and missing_task_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "feuilleton_tasks_incomplete",
                "message": "Complete the remaining Feuilleton tasks before filing the edition.",
                "missing_task_ids": missing_task_ids,
            },
        )
    already_completed = scene.status == "completed"
    completed = scheduler.complete(user=current_user, scene=scene)
    next_serial = None if already_completed else await _advance_serial_thread(db, completed)
    if not already_completed:
        CEFRProgressService(db).recompute(current_user, source="feuilleton_complete")
    return GraphicNovelCompleteResponse(
        scene=serialize_scene(completed) or {},
        recap=completed.recap_payload or {},
        next_serial=next_serial,
    )


async def _advance_serial_thread(db: Session, scene: GraphicNovelScene) -> dict[str, Any] | None:
    """Advance the serial story when a thread-linked Feuilleton episode completes."""
    if not settings.SERIAL_WORLD_ENABLED or not getattr(scene, "serial_thread_id", None):
        return None
    thread = db.get(SerialThread, scene.serial_thread_id)
    if not thread:
        return None
    try:
        return await SerialThreadService(db).apply_completion(thread, scene=scene)
    except Exception as exc:  # noqa: BLE001 — completion must never fail on serial advance
        db.rollback()
        logger.warning("Serial advance after Feuilleton failed: {}", str(exc))
        return None
