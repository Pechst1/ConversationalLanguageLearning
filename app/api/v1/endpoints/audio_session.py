"""Audio Session API endpoints for zero-config audio-only conversations."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_service
from app.db.models.user import User
from app.services.audio_session_service import (
    AudioSessionNotFoundError,
    AudioSessionService,
    AudioSessionUnavailableError,
)
from app.services.llm_service import LLMService
from app.services.pilot_events import PilotEventService

router = APIRouter(prefix="/audio-session", tags=["audio-session"])


# ─────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────

class AudioSessionStartRequest(BaseModel):
    """Request to start an audio session."""
    scenario_id: str | None = None


class AudioSessionStartResponse(BaseModel):
    """Response when starting an audio session."""
    session_id: str
    opening_message: str
    opening_audio_text: str  # Same as opening_message, for TTS
    context: dict[str, Any]


class AudioSessionMessageRequest(BaseModel):
    """User's transcribed speech."""
    session_id: str
    user_text: str = Field(..., min_length=1, max_length=4000)
    conversation_history: list[dict] = Field(
        default_factory=list,
        max_length=20,
    )


class AudioSessionMessageResponse(BaseModel):
    """AI response to user's message."""
    ai_response: str
    ai_audio_text: str  # Same as ai_response, for TTS
    detected_errors: list[dict] = Field(default_factory=list)
    xp_awarded: int = 0
    should_show_text: bool = False  # True if errors detected
    vocabulary_credit: dict[str, Any] = Field(default_factory=dict)
    minted_collectibles: list[dict[str, Any]] = Field(default_factory=list)


class AudioSessionEndRequest(BaseModel):
    """Request to end an audio session."""
    session_id: str


class AudioSessionEndResponse(BaseModel):
    """Summary when ending an audio session."""
    session_id: str
    duration_seconds: int
    total_xp: int
    errors_practiced: int
    turns: int
    produced_words: int
    due_words_reused: list[str] = Field(default_factory=list)
    longest_answer_words: int
    longest_answer: str
    tomorrow_focus: str
    cast_memory: dict[str, Any] | None = None
    message: str


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[dict])
async def list_audio_scenarios(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List available roleplay scenarios."""
    service = AudioSessionService(db, initialize_llm=False)
    return service.get_available_scenarios()


@router.post("/start", response_model=AudioSessionStartResponse)
async def start_audio_session(
    request: AudioSessionStartRequest | None = None,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
) -> AudioSessionStartResponse:
    """Start a new audio-only session.
    
    This is a ZERO-CONFIG endpoint. The AI automatically:
    - Picks a conversation topic based on time of day (default)
    - Or uses the requested roleplay scenario
    - Weaves in user's past errors for natural practice
    - Adjusts to user's proficiency level
    """
    service = AudioSessionService(db, llm_service)
    
    scenario_id = request.scenario_id if request else None
    
    try:
        result = await service.create_audio_session(
            user=current_user,
            duration_minutes=5,  # Default 5 minutes
            scenario_id=scenario_id,
        )
        
        return AudioSessionStartResponse(
            session_id=result["session_id"],
            opening_message=result["opening_message"],
            opening_audio_text=result["opening_message"],
            context=result["context"],
        )
    except Exception as exc:
        logger.exception("Failed to start audio session for user {}", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start audio session",
        ) from exc


@router.post("/respond", response_model=AudioSessionMessageResponse)
async def respond_to_audio(
    request: AudioSessionMessageRequest,
    db: Session = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
) -> AudioSessionMessageResponse:
    """Process user's spoken response and get AI reply.
    
    Flow:
    1. Transcribed text comes from client (via Whisper)
    2. AI generates natural response
    3. Error detection runs in background
    4. If errors detected, they're tracked for SRS and linked to grammar concepts
    """
    service = AudioSessionService(db, llm_service)

    try:
        session_id = UUID(request.session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        ) from exc

    try:
        result = await service.process_user_response(
            session_id=session_id,
            user_id=current_user.id,
            user_text=request.user_text,
            conversation_history=request.conversation_history,
        )
        
        # Show text if errors were detected
        should_show = len(result.get("detected_errors", [])) > 0
        
        return AudioSessionMessageResponse(
            ai_response=result["ai_response"],
            ai_audio_text=result["ai_response"],
            detected_errors=result.get("detected_errors", []),
            xp_awarded=result.get("xp_awarded", 10),
            should_show_text=should_show,
            vocabulary_credit=result.get("vocabulary_credit", {}),
            minted_collectibles=result.get("minted_collectibles", []),
        )
    except AudioSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio session not found",
        ) from exc
    except AudioSessionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Audio session is no longer active; start a new session",
        ) from exc
    except Exception as exc:
        logger.exception(
            "Failed to process audio response for user {} and session {}",
            current_user.id,
            session_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process response",
        ) from exc


@router.post("/end", response_model=AudioSessionEndResponse)
async def end_audio_session(
    request: AudioSessionEndRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioSessionEndResponse:
    """End an audio session and get summary."""
    from app.db.models.session import ConversationMessage, LearningSession
    
    try:
        session_id = UUID(request.session_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session_id format",
        ) from exc

    session = db.scalar(
        select(LearningSession)
        .where(
            LearningSession.id == session_id,
            LearningSession.user_id == current_user.id,
        )
        .with_for_update()
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Ending twice is an ordinary accident: the learner says "au revoir" (which
    # closes the call) and also taps Classer, or a dropped request is retried.
    # A replay must serve the filed summary, never re-file the séance -- else the
    # duration keeps growing, La Une counts the studio twice, and the serial
    # character gains a closeness point per tap.
    already_completed = session.status == "completed"

    # Calculate and persist the real session summary.
    duration_seconds = 0
    started_at = session.started_at or session.created_at
    now = datetime.now(UTC)
    closed_at = session.completed_at if already_completed else None
    if closed_at is not None and closed_at.tzinfo is None:
        closed_at = closed_at.replace(tzinfo=UTC)
    if started_at:
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        duration_seconds = max(0, int(((closed_at or now) - started_at).total_seconds()))

    user_messages = list(
        db.scalars(
            select(ConversationMessage)
            .where(
                ConversationMessage.session_id == session.id,
                ConversationMessage.sender == "user",
            )
            .order_by(ConversationMessage.sequence_number)
        ).all()
    )
    produced_words = sum(len((message.content or "").split()) for message in user_messages)
    longest_message = max(user_messages, key=lambda message: len((message.content or "").split()), default=None)
    longest_answer = (longest_message.content or "").strip() if longest_message else ""
    longest_answer_words = len(longest_answer.split())
    due_words_reused: list[str] = []
    for message in user_messages:
        for word in message.words_used or []:
            value = str(word or "").strip()
            if value and value not in due_words_reused:
                due_words_reused.append(value)

    tomorrow_focus = (
        "Reprendre une correction d’aujourd’hui, puis parler une minute sans s’interrompre."
        if int(session.incorrect_responses or 0)
        else "Allonger une réponse avec un détail et une question de retour."
    )
    cast_memory: dict[str, Any] | None = None
    if not already_completed:
        # Update session status
        session.status = "completed"
        session.completed_at = now
        session.actual_duration_minutes = duration_seconds // 60
        cast_memory = AudioSessionService(db, initialize_llm=False).complete_serial_call(
            user=current_user,
            session=session,
            user_messages=user_messages,
        )
        PilotEventService(db).record(
            "plan_completed",
            user_id=current_user.id,
            entity_type="audio_session",
            entity_id=session.id,
            payload={
                "turns": len(user_messages),
                "produced_words": produced_words,
                "errors": int(session.incorrect_responses or 0),
                "due_words_reused": due_words_reused,
                "longest_answer_words": longest_answer_words,
            },
        )
        db.commit()


    return AudioSessionEndResponse(
        session_id=str(session.id),
        duration_seconds=duration_seconds,
        total_xp=int(session.xp_earned or 0),
        errors_practiced=int(session.incorrect_responses or 0),
        turns=len(user_messages),
        produced_words=produced_words,
        due_words_reused=due_words_reused,
        longest_answer_words=longest_answer_words,
        longest_answer=longest_answer,
        tomorrow_focus=tomorrow_focus,
        cast_memory=cast_memory,
        message="Super séance ! À bientôt !",
    )


__all__ = ["router"]
