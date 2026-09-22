"""Audio transcription and TTS endpoints."""
from contextlib import suppress
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_service
from app.config import settings
from app.core.offload import off_event_loop
from app.db.models.user import User
from app.services.llm_service import LLMService, estimate_tts_cost_usd
from app.services.pilot_events import PilotEventService
from app.services.transcription_cost import record_transcription_cost

router = APIRouter()
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024

#: WP-70: the pilot-ledger event for ``POST /audio/speak``. It had no cost row at
#: all, so the daily spend cap could not see it.
SPEECH_EVENT_TYPE = "audio_speech"
_DEFAULT_TTS_MODEL = {"openai": "tts-1-hd", "elevenlabs": "eleven_turbo_v2_5"}


def _record_speech_cost(db: Session, *, user_id, text: str, provider: str | None) -> None:  # type: ignore[no-untyped-def]
    """One estimated cost row per synthesized line; telemetry never costs the audio."""

    resolved = (provider or settings.TTS_PROVIDER or "openai").lower()
    model = _DEFAULT_TTS_MODEL.get(resolved, resolved)
    try:
        PilotEventService(db).record(
            SPEECH_EVENT_TYPE,
            user_id=user_id,
            entity_type="speech",
            payload={
                "provider": resolved,
                "model": model,
                "chars": len(text),
                "estimated": True,
                "cost_basis": f"chars·{model}",
            },
            cost_usd=estimate_tts_cost_usd(model, len(text)),
        )
        db.commit()
    except Exception:  # pragma: no cover - defensive
        logger.warning("Speech cost row could not be written")
        with suppress(Exception):
            db.rollback()


class TTSRequest(BaseModel):
    """Request body for text-to-speech."""
    text: str = Field(..., min_length=1, max_length=4096)
    voice: str = Field("nova", description="Voice ID or name (e.g. nova, Rachel)")
    provider: str | None = Field(None, pattern="^(openai|elevenlabs)$")


@router.post("/transcribe")
@off_event_loop
async def transcribe_audio(
    file: Annotated[UploadFile, File()],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    surface: Annotated[str, Form()] = "unknown",
) -> dict[str, str]:
    """Transcribe an audio file to text.

    WP-27 made speaking the daily journey's default output, so this is a paid
    endpoint on the learner's main path: every successful call writes one
    priced pilot-cost row (`app.services.transcription_cost`). Nothing here
    scores pronunciation — the transcript is graded as text, exactly like a
    typed answer.
    """
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be audio.")
    
    try:
        content = await file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    except Exception as exc:
        logger.exception("Failed to read uploaded audio")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read the uploaded audio",
        ) from exc

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty",
        )
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Audio file exceeds the 25 MB limit",
        )

    logger.info("Received audio file: {} bytes", len(content))
    try:
        text = llm_service.transcribe_audio(
            content,
            filename=file.filename,
            content_type=file.content_type,
        )
        # After the call, so a failed request is not billed on the ledger.
        record_transcription_cost(
            db,
            user_id=current_user.id,
            byte_count=len(content),
            content_type=file.content_type,
            surface=surface,
        )
        db.commit()
        return {"text": text}
    except Exception as exc:
        logger.exception("Audio transcription failed")
        raise HTTPException(
            status_code=500,
            detail="Audio transcription failed",
        ) from exc


@router.post("/speak")
@off_event_loop
async def text_to_speech(
    request: TTSRequest,
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> Response:
    """Convert text to speech audio."""
    try:
        audio_bytes = llm_service.text_to_speech(
            text=request.text,
            voice=request.voice,
            provider=request.provider,
        )
        # After the call, so a failed synthesis is not billed.
        _record_speech_cost(
            db, user_id=current_user.id, text=request.text, provider=request.provider
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except Exception as exc:
        logger.exception("Text-to-speech generation failed")
        raise HTTPException(
            status_code=500,
            detail="Text-to-speech generation failed",
        ) from exc
