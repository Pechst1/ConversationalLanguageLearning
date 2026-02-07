"""Audio transcription and TTS endpoints."""
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_llm_service, get_current_user
from app.db.models.user import User
from app.services.llm_service import LLMService

router = APIRouter()


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
        content = await file.read()
        print(f"Received audio file: {len(content)} bytes") # Simple logging
        text = llm_service.transcribe_audio(content)
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

