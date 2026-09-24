"""WP-25 — the placement conversation's API.

Authenticated with the existing ``get_current_user`` dependency; no new token
path, no bypass. Every route answers the same envelope, so the client renders
one state machine rather than four.

The offer is made once: :func:`read_state` reports ``offered`` only while the
learner has neither taken nor declined a placement, and Réglages re-runs it by
asking for ``restart``.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.services.cefr_progress import CEFRProgressService
from app.services.placement import (
    MAX_TURNS,
    PLACEMENT_VERSION,
    PlacementService,
    hint_by_language,
    latest_placement_prior,
    placement_offer,
)

router = APIRouter(prefix="/placement", tags=["placement"])


class PlacementPromptView(BaseModel):
    """The turn on screen, or ``None`` when the conversation is over."""

    index: int
    band: str
    prompt_fr: str
    hint_fr: str
    #: The hint is chrome: {fr, en, de}; the client shows the learner's
    #: declared native language (the prompt itself stays French).
    hint_by_language: dict[str, str] = Field(default_factory=dict)
    turns_so_far: int
    max_turns: int = MAX_TURNS


class PlacementEnvelope(BaseModel):
    """One shape for every placement route."""

    version: str = PLACEMENT_VERSION
    session_id: str | None = None
    status: str
    #: ``offered`` only before the learner has either taken or declined one.
    offer: bool = False
    prompt: PlacementPromptView | None = None
    estimate: dict | None = None
    level: str | None = None
    confidence: float = 0.0
    #: The prior the CEFR service would use right now, or ``None``.
    prior: dict | None = None


class RespondRequest(BaseModel):
    answer: str = Field(default="", max_length=4000)
    #: Which turn this answers. Replaying an already-graded index is a no-op,
    #: so a retried request never buys a second paid grading.
    turn_index: int = Field(ge=0)


class StartRequest(BaseModel):
    #: Réglages re-run. Only this opens a second session over an open one.
    restart: bool = False


def _envelope(
    db: Session,
    user: User,
    session: PlacementSession | None,
    *,
    offer: bool = False,
) -> PlacementEnvelope:
    if session is None:
        return PlacementEnvelope(
            status="none",
            offer=offer,
            prior=latest_placement_prior(db, user),
        )
    prompt = None
    if session.status == "in_progress":
        rung = PlacementService.current_prompt(session)
        turns = len(session.turns or [])
        prompt = PlacementPromptView(
            index=turns,
            band=rung.band,
            prompt_fr=rung.prompt_fr,
            hint_fr=rung.hint_fr,
            hint_by_language=hint_by_language(rung.hint_fr),
            turns_so_far=turns,
        )
    return PlacementEnvelope(
        version=str(session.version or PLACEMENT_VERSION),
        session_id=str(session.id),
        status=str(session.status),
        offer=offer,
        prompt=prompt,
        estimate=dict(session.estimate or {}) or None,
        level=session.estimate_level,
        confidence=float(session.confidence or 0.0),
        prior=latest_placement_prior(db, user),
    )


def _load(db: Session, user: User, session_id: uuid.UUID) -> PlacementSession:
    session = (
        db.query(PlacementSession)
        .filter(PlacementSession.id == session_id, PlacementSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Placement introuvable")
    return session


@router.get("/state", response_model=PlacementEnvelope)
def read_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementEnvelope:
    """What the learner should see: an open placement, a result, or the offer."""
    service = PlacementService(db)
    active = service.active_session(current_user)
    if active is not None:
        return _envelope(db, current_user, active)
    latest = service.latest_session(current_user)
    # The offer is made once. A learner who took it or declined it is never
    # asked again; Réglages is where they go to re-run it.
    return _envelope(db, current_user, latest, offer=latest is None)


class PlacementOffer(BaseModel):
    """WP-75: whether to offer the placement now. Never true at sign-up."""

    offer: bool


@router.get("/offer", response_model=PlacementOffer)
def read_offer(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementOffer:
    """True after three completed days, before any placement was taken or
    declined, and only when it can tell the learner something (they declared
    more than «Nouveau», or their days say they are above their band)."""
    return PlacementOffer(offer=placement_offer(db, current_user))


@router.post("/start", response_model=PlacementEnvelope)
def start(
    payload: StartRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementEnvelope:
    """Open a placement, or resume the one already open (idempotent)."""
    service = PlacementService(db)
    session = service.start(current_user, restart=bool(payload and payload.restart))
    return _envelope(db, current_user, session)


@router.post("/{session_id}/respond", response_model=PlacementEnvelope)
def respond(
    session_id: uuid.UUID,
    payload: RespondRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementEnvelope:
    """Grade one answer and hand back the next rung, or the result."""
    session = _load(db, current_user, session_id)
    service = PlacementService(db)
    session = service.respond(session, answer=payload.answer, turn_index=payload.turn_index)
    if session.status != "in_progress":
        # The estimate is the CEFR service's prior from here on; recompute so
        # Home and Le Cahier answer with the new level on their next read.
        CEFRProgressService(db).recompute(current_user, source="placement")
    return _envelope(db, current_user, session)


@router.post("/{session_id}/finish", response_model=PlacementEnvelope)
def finish(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementEnvelope:
    """End it with the evidence there is. No graded turn means no level."""
    session = _load(db, current_user, session_id)
    session = PlacementService(db).finish_now(session)
    CEFRProgressService(db).recompute(current_user, source="placement")
    return _envelope(db, current_user, session)


@router.post("/skip", response_model=PlacementEnvelope)
def skip(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PlacementEnvelope:
    """The learner declined. Their declared level stands, exactly as before."""
    session = PlacementService(db).skip(current_user)
    return _envelope(db, current_user, session)
