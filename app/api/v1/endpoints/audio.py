"""Audio transcription and TTS endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from loguru import logger
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_llm_service
from app.db.models.user import User
from app.services.llm_service import LLMService

router = APIRouter()
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024


class TTSRequest(BaseModel):
    """Request body for text-to-speech."""
    text: str = Field(..., min_length=1, max_length=4096)
    voice: str = Field("nova", description="Voice ID or name (e.g. nova, Rachel)")
    provider: str | None = Field(None, pattern="^(openai|elevenlabs)$")


@router.post("/transcribe")
async def transcribe_audio(
    file: Annotated[UploadFile, File()],
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Transcribe an audio file to text."""
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
        return {"text": text}
    except Exception as exc:
        logger.exception("Audio transcription failed")
        raise HTTPException(
            status_code=500,
            detail="Audio transcription failed",
        ) from exc


@router.post("/speak")
async def text_to_speech(
    request: TTSRequest,
    llm_service: Annotated[LLMService, Depends(get_llm_service)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Convert text to speech audio."""
    try:
        audio_bytes = llm_service.text_to_speech(
            text=request.text,
            voice=request.voice,
            provider=request.provider,
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
