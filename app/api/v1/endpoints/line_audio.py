"""WP-91 «Les voix» — a character's line, spoken in their voice.

Two routes beside the daily journey's own (same ``/daily-journeys`` prefix, a
separate module so the journey's router stays the state machine's):

* ``POST /daily-journeys/{journey_id}/steps/{step_id}/line-audio`` — speak one
  line the learner can see in that step. 404 for a journey or step that is not
  theirs, and 404 for text that is not a line of that step: the route never
  synthesizes arbitrary text. ``{"status": "disabled"}`` (200) when the
  deployment does not speak, the provider failed, or the daily cap is near —
  the client then reads the line with the device's voice.
* ``GET /daily-journeys/line-audio/{clip_id}`` — the audio bytes, for the
  learner's own clips only. A listening item's clip is spoken on this first
  request (see :func:`app.services.line_audio.speak_planned_clip`).

Both are paid routes (``app.core.rate_limit.PAID_ROUTES``) and open-day routes:
a line is part of finishing a day already begun.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.user import User
from app.schemas.daily_journey import LineAudioRequest, LineAudioResult
from app.services import line_audio
from app.services.cast_voices import voice_of_clip_id

router = APIRouter(prefix="/daily-journeys", tags=["daily-journeys", "line-audio"])


@router.get("/line-audio/{clip_id}")
def line_audio_clip(
    clip_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """One spoken line: the learner's own clip, or a listening item's, spoken now."""

    if voice_of_clip_id(clip_id) is None:
        raise HTTPException(404, "Line audio clip not found")
    clip = line_audio.owned_clip(db, user_id=current_user.id, clip_id=clip_id)
    if clip is None and settings.ATELIER_EPISODE_AUDIO_ENABLED:
        clip = line_audio.speak_planned_clip(db, user=current_user, clip_id=clip_id)
        if clip is not None:
            db.commit()
    if clip is None:
        raise HTTPException(404, "Line audio clip not found")
    return Response(
        content=clip.audio,
        media_type=clip.content_type or "audio/mpeg",
        headers={
            "Content-Disposition": "inline; filename=line.mp3",
            # One id is one line in one voice, forever: safe to hold.
            "Cache-Control": "private, max-age=86400, immutable",
        },
    )


@router.post(
    "/{journey_id}/steps/{step_id}/line-audio",
    response_model=LineAudioResult,
    response_model_exclude_none=True,
)
def speak_step_line(
    journey_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: LineAudioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LineAudioResult:
    """Speak one line of one step, or say ``disabled`` so the device reads it."""

    journey = db.scalar(
        select(DailyJourney).where(
            DailyJourney.id == journey_id, DailyJourney.user_id == current_user.id
        )
    )
    if journey is None:
        raise HTTPException(404, "Journey not found")
    step = db.scalar(
        select(DailyJourneyStep).where(
            DailyJourneyStep.id == step_id, DailyJourneyStep.journey_id == journey.id
        )
    )
    if step is None:
        raise HTTPException(404, "Step not found")
    line = line_audio.match_line(
        line_audio.step_lines(db, journey, step), payload.text_fr, payload.character_id
    )
    if line is None:
        raise HTTPException(404, "Not a line of this step")
    outcome = line_audio.speak_line(
        db, user=current_user, line=line, surface=f"journey_{step.kind}_line", step_id=step.id
    )
    if outcome.status == "ready":
        db.commit()
    return LineAudioResult.model_validate(outcome.as_payload())
