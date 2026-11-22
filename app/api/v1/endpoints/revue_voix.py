"""«Papier · la voix» (``REVUE_VOIX_ENABLED``, ``app/services/revue/voix.py``): the paper is heard.

* ``GET  /revue/sessions/{id}/voix`` — what the session may speak (the lead, the regulars'
  lines as they stand) and the dictée, if one fits.
* ``POST /revue/sessions/{id}/voix/line`` — one of those lines, spoken (lazily, cached per line,
  voice and band pace in ``line_audio_clips``; another learner's clip is copied, no call). The
  bytes come from the journey's ``GET /daily-journeys/line-audio/{clip_id}``. Any other text is
  a 404: this is not a free text-to-speech route.
* ``POST /revue/sessions/{id}/voix/dictee`` — one try at the dictée, graded; no model call.

Each route answers a plain 404 unless ``REVUE_ENABLED`` and ``REVUE_VOIX_ENABLED`` are on,
checked before authentication.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import paid_route_guard
from app.db.models.user import User
from app.schemas.daily_journey import LineAudioRequest, LineAudioResult
from app.schemas.revue_voix import RvVoixDicteeRequest, RvVoixDicteeResult, RvVoixManifest
from app.services import line_audio
from app.services.chrome_language import user_mother_tongue
from app.services.revue import voix
from app.services.revue.encounter import Loaded, RevueError, load, owned_session


def require_voix_enabled() -> None:
    if not voix.enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/revue",
    tags=["revue"],
    # The switch first (404 while off), then the paid-route guard: the line route pays for speech.
    dependencies=[Depends(require_voix_enabled), Depends(paid_route_guard(get_current_user))],
)


def _loaded(db: Session, user: User, session_id: str) -> Loaded:
    try:
        return load(owned_session(db, user, session_id))
    except RevueError as error:
        raise HTTPException(status_code=error.status, detail=error.detail) from error


@router.get("/sessions/{session_id}/voix", response_model=RvVoixManifest)
def read_voix(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvVoixManifest:
    return RvVoixManifest.model_validate(voix.manifest(_loaded(db, current_user, session_id)))


@router.post("/sessions/{session_id}/voix/line", response_model=LineAudioResult, response_model_exclude_none=True)
def speak_voix_line(
    session_id: str,
    payload: LineAudioRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LineAudioResult:
    """Speak one line of the session, or say ``disabled`` so the device reads it."""

    loaded = _loaded(db, current_user, session_id)
    lines = [line.step_line() for line in voix.session_lines(loaded)]
    line = line_audio.match_line(lines, payload.text_fr, payload.character_id)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a line of this session")
    outcome = line_audio.speak_line(
        db, user=current_user, line=line, surface=voix.AUDIO_SURFACE, band=voix.band_of(loaded)
    )
    if outcome.status == "ready":
        db.commit()
    return LineAudioResult.model_validate(outcome.as_payload())


@router.post("/sessions/{session_id}/voix/dictee", response_model=RvVoixDicteeResult)
def grade_voix_dictee(
    session_id: str,
    payload: RvVoixDicteeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RvVoixDicteeResult:
    loaded = _loaded(db, current_user, session_id)
    # The grader's note is an explanation: always in the mother tongue.
    result = voix.grade(loaded, payload.text, payload.attempt, user_mother_tongue(current_user))
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="revue_voix_no_dictee")
    return RvVoixDicteeResult.model_validate(result)
