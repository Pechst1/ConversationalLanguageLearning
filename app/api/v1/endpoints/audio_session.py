"""Audio Session API endpoints for zero-config audio-only conversations."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_service
from app.db.models.user import User
from app.services.audio_session_service import AudioSessionService
from app.services.llm_service import LLMService


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
    user_text: str = Field(..., min_length=1)
    system_prompt: str  # Passed from client (stored from start)
    conversation_history: list[dict] = Field(default_factory=list)


class AudioSessionMessageResponse(BaseModel):
    """AI response to user's message."""
    ai_response: str
    ai_audio_text: str  # Same as ai_response, for TTS
    detected_errors: list[dict] = Field(default_factory=list)
    xp_awarded: int = 0
    should_show_text: bool = False  # True if errors detected


class AudioSessionEndRequest(BaseModel):
    """Request to end an audio session."""
    session_id: str


class AudioSessionEndResponse(BaseModel):
    """Summary when ending an audio session."""
    session_id: str
    duration_seconds: int
    total_xp: int
    errors_practiced: int
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
    service = AudioSessionService(db)
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start audio session: {str(e)}"
        )


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
        result = await service.process_user_response(
            session_id=UUID(request.session_id),
            user_text=request.user_text,
            system_prompt=request.system_prompt,
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
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process response: {str(e)}"
        )


@router.post("/end", response_model=AudioSessionEndResponse)
async def end_audio_session(
    request: AudioSessionEndRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AudioSessionEndResponse:
    """End an audio session and get summary."""
    from app.db.models.session import LearningSession
    
    session = db.query(LearningSession).filter(
        LearningSession.id == UUID(request.session_id),
        LearningSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Calculate duration
    duration_seconds = 0
    if session.created_at:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        duration_seconds = int((now - session.created_at).total_seconds())
    
    # Update session status
    session.status = "completed"
    db.commit()
    
    return AudioSessionEndResponse(
        session_id=request.session_id,
        duration_seconds=duration_seconds,
        total_xp=50,  # TODO: Calculate from session
        errors_practiced=0,  # TODO: Track from session
        message="Super session ! À bientôt ! 🎉"
    )


__all__ = ["router"]
