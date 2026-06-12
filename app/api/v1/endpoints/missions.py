"""Real-world scenario mission API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from loguru import logger

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import get_atelier_user
from app.config import settings
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.schemas.missions import (
    MissionAttemptResponse,
    MissionCompleteResponse,
    MissionCreateRequest,
    MissionResponse,
    MissionSubmitRequest,
    MissionTodayResponse,
    MissionTurnRequest,
    MissionTurnResponse,
)
from app.services.llm_service import LLMService
from app.services.serial import SerialThreadService
from app.services.missions import (
    MissionConversationService,
    MissionCorrectionService,
    MissionScheduler,
    serialize_mission,
)

router = APIRouter(prefix="/missions", tags=["missions"])


def _mission_or_404(db: Session, mission_id: UUID, user: User) -> RealWorldMission:
    mission = MissionScheduler(db).get(user=user, mission_id=mission_id)
    if not mission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return mission


def _ensure_open(mission: RealWorldMission) -> None:
    if mission.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mission already completed")


def _mark_started(mission: RealWorldMission) -> None:
    if mission.status == "available":
        mission.status = "in_progress"
    if not mission.started_at:
        mission.started_at = datetime.now(timezone.utc)


def _attempt_read(attempt: RealWorldMissionAttempt) -> dict:
    return {
        "id": str(attempt.id),
        "mode": attempt.mode,
        "answer_payload": attempt.answer_payload or {},
        "correction": attempt.correction_payload or {},
        "verdict": attempt.verdict,
        "score_0_4": attempt.score_0_4,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


def _turn_read(turn: RealWorldMissionTurn) -> dict:
    return {
        "id": str(turn.id),
        "turn_index": turn.turn_index,
        "role": turn.role,
        "mode": turn.mode,
        "text": turn.text,
        "audio_payload": turn.audio_payload or {},
        "correction": turn.correction_payload or {},
        "created_at": turn.created_at.isoformat() if turn.created_at else None,
    }


def _next_turn_index(db: Session, mission: RealWorldMission) -> int:
    current = (
        db.query(func.max(RealWorldMissionTurn.turn_index))
        .filter(RealWorldMissionTurn.mission_id == mission.id)
        .scalar()
    )
    return int(current or 0) + 1


def _normalized_submission_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _duplicate_attempt(db: Session, mission: RealWorldMission, *, mode: str, text: str) -> RealWorldMissionAttempt | None:
    normalized = _normalized_submission_text(text)
    if not normalized:
        return None
    rows = (
        db.query(RealWorldMissionAttempt)
        .filter(
            RealWorldMissionAttempt.mission_id == mission.id,
            RealWorldMissionAttempt.user_id == mission.user_id,
            RealWorldMissionAttempt.mode == mode,
        )
        .order_by(RealWorldMissionAttempt.created_at.desc())
        .limit(8)
        .all()
    )
    for row in rows:
        if _normalized_submission_text((row.answer_payload or {}).get("text", "")) == normalized:
            return row
    return None


def _duplicate_turn(
    db: Session,
    mission: RealWorldMission,
    *,
    mode: str,
    text: str,
) -> tuple[RealWorldMissionTurn, RealWorldMissionTurn | None] | None:
    normalized = _normalized_submission_text(text)
    if not normalized:
        return None
    user_turn = (
        db.query(RealWorldMissionTurn)
        .filter(
            RealWorldMissionTurn.mission_id == mission.id,
            RealWorldMissionTurn.user_id == mission.user_id,
            RealWorldMissionTurn.role == "user",
            RealWorldMissionTurn.mode == mode,
        )
        .order_by(RealWorldMissionTurn.turn_index.desc())
        .first()
    )
    if not user_turn or _normalized_submission_text(user_turn.text) != normalized:
        return None
    assistant_turn = (
        db.query(RealWorldMissionTurn)
        .filter(
            RealWorldMissionTurn.mission_id == mission.id,
            RealWorldMissionTurn.turn_index == user_turn.turn_index + 1,
            RealWorldMissionTurn.role == "assistant",
        )
        .first()
    )
    return user_turn, assistant_turn


@router.get("/today", response_model=MissionTodayResponse)
async def get_missions_today(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionTodayResponse:
    """Return the weekly mission, active mission, and post-session recommendation."""
    return MissionTodayResponse(**(await MissionScheduler(db).today(current_user)))


@router.post("", response_model=MissionResponse)
@router.post("/", response_model=MissionResponse)
async def create_mission(
    request: MissionCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionResponse:
    mission = await MissionScheduler(db).create(
        user=current_user,
        mission_type=request.mission_type,
        cadence=request.cadence,
        atelier_session_id=request.atelier_session_id,
        serial_thread_id=request.serial_thread_id,
        episode_index=request.episode_index,
        preferred_concept_ids=request.preferred_concept_ids,
        preferred_errata_ids=request.preferred_errata_ids,
        preferred_vocabulary_ids=request.preferred_vocabulary_ids,
        use_news=request.use_news,
        custom_scenario=request.custom_scenario,
        desired_outcome=request.desired_outcome,
        relationship=request.relationship,
        register=request.target_register,
        stakes_level=request.stakes_level,
    )
    return MissionResponse(mission=serialize_mission(mission) or {})


@router.post("/audio/transcribe")
async def transcribe_mission_audio(
    file: Annotated[UploadFile, File()],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> dict[str, str]:
    """Transcribe mission voice input while keeping Atelier's demo-auth behavior."""
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Must be audio.")
    try:
        content = await file.read()
        return {"text": LLMService().transcribe_audio(content)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/{mission_id}", response_model=MissionResponse)
def get_mission(
    mission_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionResponse:
    mission = _mission_or_404(db, mission_id, current_user)
    return MissionResponse(mission=serialize_mission(mission) or {})


@router.post("/{mission_id}/submit", response_model=MissionAttemptResponse)
def submit_mission(
    mission_id: UUID,
    request: MissionSubmitRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionAttemptResponse:
    mission = _mission_or_404(db, mission_id, current_user)
    _ensure_open(mission)
    _mark_started(mission)

    duplicate = _duplicate_attempt(db, mission, mode=request.mode, text=request.text)
    if duplicate:
        return MissionAttemptResponse(
            attempt=_attempt_read(duplicate),
            correction=duplicate.correction_payload or {},
            errata=[],
            mission=serialize_mission(mission) or {},
        )

    correction_service = MissionCorrectionService(db)
    correction = correction_service.correct_submission(
        user=current_user,
        mission=mission,
        text=request.text,
        mode=request.mode,
    )
    attempt = RealWorldMissionAttempt(
        mission_id=mission.id,
        user_id=current_user.id,
        mode=request.mode,
        answer_payload={"text": request.text},
        correction_payload=correction,
        verdict=correction.get("verdict", "needs_revision"),
        score_0_4=float(correction.get("score_0_4") or 0),
    )
    db.add(attempt)
    db.add(mission)
    db.commit()
    db.refresh(attempt)
    db.refresh(mission)
    persisted = correction_service.persist_errata(
        user=current_user,
        mission=mission,
        correction=correction,
        mode=request.mode,
        source_id=str(attempt.id),
    )
    db.commit()
    db.refresh(mission)
    return MissionAttemptResponse(
        attempt=_attempt_read(attempt),
        correction=correction,
        errata=persisted,
        mission=serialize_mission(mission) or {},
    )


@router.post("/{mission_id}/turns", response_model=MissionTurnResponse)
def submit_mission_turn(
    mission_id: UUID,
    request: MissionTurnRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionTurnResponse:
    mission = _mission_or_404(db, mission_id, current_user)
    _ensure_open(mission)
    _mark_started(mission)

    duplicate = _duplicate_turn(db, mission, mode=request.mode, text=request.text)
    if duplicate:
        user_turn, assistant_turn = duplicate
        if not assistant_turn:
            conversation_service = MissionConversationService(db)
            assistant_text = conversation_service.respond(
                user=current_user,
                mission=mission,
                user_text=request.text,
            )
            assistant_turn = RealWorldMissionTurn(
                mission_id=mission.id,
                user_id=current_user.id,
                turn_index=user_turn.turn_index + 1,
                role="assistant",
                mode="chat",
                text=assistant_text,
                audio_payload={
                    "branch": conversation_service.branch_state(
                        mission=mission,
                        user_text=request.text,
                        assistant_text=assistant_text,
                    )
                },
                correction_payload={},
            )
            db.add(assistant_turn)
            db.commit()
            db.refresh(assistant_turn)
            db.refresh(mission)
        outcome = MissionConversationService(db).turn_outcome(
            mission=mission,
            user_text=user_turn.text,
            assistant_text=assistant_turn.text,
        )
        return MissionTurnResponse(
            user_turn=_turn_read(user_turn),
            assistant_turn=_turn_read(assistant_turn),
            correction=user_turn.correction_payload or {},
            errata=[],
            mission=serialize_mission(mission) or {},
            outcome=outcome,
        )

    correction_service = MissionCorrectionService(db)
    correction = correction_service.correct_submission(
        user=current_user,
        mission=mission,
        text=request.text,
        mode=request.mode,
        near_realtime=True,
    )
    first_index = _next_turn_index(db, mission)
    user_turn = RealWorldMissionTurn(
        mission_id=mission.id,
        user_id=current_user.id,
        turn_index=first_index,
        role="user",
        mode=request.mode,
        text=request.text,
        audio_payload=request.transcript_metadata,
        correction_payload=correction,
    )
    db.add(user_turn)
    db.add(mission)
    db.commit()
    db.refresh(user_turn)
    db.refresh(mission)
    persisted = correction_service.persist_errata(
        user=current_user,
        mission=mission,
        correction=correction,
        mode=request.mode,
        source_id=str(user_turn.id),
    )
    conversation_service = MissionConversationService(db)
    assistant_text = conversation_service.respond(
        user=current_user,
        mission=mission,
        user_text=request.text,
    )
    assistant_turn = RealWorldMissionTurn(
        mission_id=mission.id,
        user_id=current_user.id,
        turn_index=first_index + 1,
        role="assistant",
        mode="chat",
        text=assistant_text,
        audio_payload={
            "branch": conversation_service.branch_state(
                mission=mission,
                user_text=request.text,
                assistant_text=assistant_text,
            )
        },
        correction_payload={},
    )
    db.add(assistant_turn)
    db.commit()
    db.refresh(assistant_turn)
    db.refresh(mission)
    outcome = conversation_service.turn_outcome(
        mission=mission,
        user_text=request.text,
        assistant_text=assistant_text,
    )
    return MissionTurnResponse(
        user_turn=_turn_read(user_turn),
        assistant_turn=_turn_read(assistant_turn),
        correction=correction,
        errata=persisted,
        mission=serialize_mission(mission) or {},
        outcome=outcome,
    )


@router.post("/{mission_id}/complete", response_model=MissionCompleteResponse)
async def complete_mission(
    mission_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_atelier_user)],
) -> MissionCompleteResponse:
    mission = _mission_or_404(db, mission_id, current_user)
    completed = MissionScheduler(db).complete(user=current_user, mission=mission)
    await _advance_serial_thread(db, completed)
    return MissionCompleteResponse(
        mission=serialize_mission(completed) or {},
        recap=completed.recap_payload or {},
    )


async def _advance_serial_thread(db: Session, mission: RealWorldMission) -> None:
    """Advance the serial story when a thread-linked mission completes.

    Resilient: if the next Feuilleton beat fails to generate, the thread index
    has already advanced, so /serial/today regenerates it lazily next load.
    """
    if not settings.SERIAL_WORLD_ENABLED or not getattr(mission, "serial_thread_id", None):
        return
    thread = db.get(SerialThread, mission.serial_thread_id)
    if not thread:
        return
    try:
        await SerialThreadService(db).apply_completion(thread, mission=mission)
    except Exception as exc:  # noqa: BLE001 — completion must never fail on serial advance
        db.rollback()
        logger.warning("Serial advance after mission failed: {}", str(exc))
