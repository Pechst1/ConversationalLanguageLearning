"""WP-31 — «Répétition»: the API for rehearsing a real upcoming situation.

Authenticated with the existing ``get_current_user`` dependency; no new token
path, no bypass. Every route answers the same envelope, so the page renders one
state machine rather than seven screens.

Two rules the transport keeps rather than the client:

* **The private rubric and the recognition cues never leave the server** while a
  rehearsal is live. ``rehearsal.public_view`` is the only serializer, and the
  routes have no other way to emit a scene.
* **Every refusal is a sentence, not a stack trace.** A learner at the weekly
  cap, a replayed turn, a debrief asked for before the real event — each one is
  a 409 with French the page can print as it stands.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.rehearsal import REHEARSAL_OUTCOMES, Rehearsal
from app.db.models.user import User
from app.services.rehearsal import (
    DECLARATION_MAX_CHARS,
    FREE_LINE_MAX_CHARS,
    MAX_TURNS,
    MIN_TURNS,
    REHEARSAL_VERSION,
    RehearsalRefused,
    RehearsalService,
    cap_state,
    public_view,
)

router = APIRouter(prefix="/rehearsals", tags=["rehearsals"])

#: One French sentence per refusal code. The page prints them verbatim, so a new
#: code without a sentence here is a bug that shows up as the fallback line.
_REFUSAL_FR: dict[str, str] = {
    "declaration_empty": "Dites d’abord ce qui vous attend, en une phrase.",
    "rehearsal_disabled": "Les répétitions sont désactivées pour l’instant.",
    "weekly_cap_reached": (
        "Vous avez déjà utilisé vos répétitions de la semaine. La prochaine se libère bientôt."
    ),
    "rehearsal_already_open": "Une répétition est déjà en cours. Terminez-la ou abandonnez-la.",
    "rehearsal_not_preparable": "Cette répétition est déjà préparée.",
    "rehearsal_not_live": "Cette répétition n’est plus en cours.",
    "turn_out_of_order": "Ce tour a déjà été joué. Rechargez la page.",
    "turn_budget_spent": "La répétition est terminée.",
    "no_phrases_available": "Aucune phrase utile n’a été préparée pour cette scène.",
    "unknown_outcome": "Choisissez : c’est fait, en partie, ou pas encore.",
    "debrief_not_due": "Le bilan s’ouvrira le jour de votre rendez-vous.",
}
_REFUSAL_FALLBACK = "Cette action n’est pas possible pour l’instant."


class RehearsalCapView(BaseModel):
    """The weekly bound, as the learner sees it."""

    limit: int
    used: int
    remaining: int
    next_slot_at: str | None = None


class RehearsalEnvelope(BaseModel):
    """One shape for every rehearsal route."""

    version: str = REHEARSAL_VERSION
    #: The rehearsal in play — being declared, rehearsed, or awaiting a debrief.
    rehearsal: dict | None = None
    #: A finished rehearsal whose real event is due, when it is not the one above.
    debrief_due: dict | None = None
    cap: RehearsalCapView
    min_turns: int = MIN_TURNS
    max_turns: int = MAX_TURNS


class DeclareRequest(BaseModel):
    declaration: str = Field(default="", max_length=DECLARATION_MAX_CHARS)


class TurnRequest(BaseModel):
    text: str = Field(default="", max_length=4000)
    mode: str = Field(default="text")
    #: Which turn this answers. Replaying an already-graded index is a no-op, so
    #: a retried request never buys a second grading.
    turn_index: int = Field(ge=0)


class DebriefRequest(BaseModel):
    outcome: str = Field(description="done | partly | not_yet")
    free_line: str = Field(default="", max_length=FREE_LINE_MAX_CHARS)


def _refused(exc: RehearsalRefused) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": exc.code, "message_fr": _REFUSAL_FR.get(exc.code, _REFUSAL_FALLBACK)},
    )


def _envelope(db: Session, user: User, current: Rehearsal | None = None) -> RehearsalEnvelope:
    now = datetime.now(UTC)
    today = now.date()
    service = RehearsalService(db)
    live = current if current is not None else service.open_rehearsal(user)
    due = service.awaiting_debrief(user, today=today)
    if live is None and due is not None:
        live, due = due, None
    if live is None and current is None:
        # Nothing open and nothing due: show the last one so the page can say
        # what happened rather than pretending the learner has never rehearsed.
        live = service.latest(user)
    if due is not None and live is not None and due.id == live.id:
        due = None
    return RehearsalEnvelope(
        rehearsal=public_view(live, today=today) if live is not None else None,
        debrief_due=public_view(due, today=today) if due is not None else None,
        cap=RehearsalCapView(**cap_state(db, user, now=now)),
    )


def _load(db: Session, user: User, rehearsal_id: uuid.UUID) -> Rehearsal:
    rehearsal = RehearsalService(db).load(user, rehearsal_id)
    if rehearsal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Répétition introuvable"
        )
    return rehearsal


@router.get("/state", response_model=RehearsalEnvelope)
def read_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """What the learner has open, what is owed a debrief, and what is left."""

    return _envelope(db, current_user)


@router.post("", response_model=RehearsalEnvelope, status_code=status.HTTP_201_CREATED)
def declare(
    body: DeclareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """Declare a real situation and prepare it in one round trip.

    The response may well carry ``status: "not_prepared"``. That is a success of
    the transport and a failure of the provider, and it is reported as such —
    never as a 500, and never as an invented scene.
    """

    service = RehearsalService(db)
    try:
        rehearsal = service.declare(current_user, declaration=body.declaration)
    except RehearsalRefused as exc:
        raise _refused(exc) from exc
    db.commit()
    db.refresh(rehearsal)
    return _envelope(db, current_user, rehearsal)


@router.post("/{rehearsal_id}/prepare", response_model=RehearsalEnvelope)
def prepare(
    rehearsal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """Try again to prepare a rehearsal the provider could not prepare."""

    rehearsal = _load(db, current_user, rehearsal_id)
    try:
        RehearsalService(db).prepare(current_user, rehearsal)
    except RehearsalRefused as exc:
        raise _refused(exc) from exc
    db.commit()
    db.refresh(rehearsal)
    return _envelope(db, current_user, rehearsal)


@router.post("/{rehearsal_id}/phrases", response_model=RehearsalEnvelope)
def reveal_phrases(
    rehearsal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """Hand over the useful phrases — and book the assistance that costs."""

    rehearsal = _load(db, current_user, rehearsal_id)
    try:
        RehearsalService(db).reveal_phrases(rehearsal)
    except RehearsalRefused as exc:
        raise _refused(exc) from exc
    db.commit()
    db.refresh(rehearsal)
    return _envelope(db, current_user, rehearsal)


@router.post("/{rehearsal_id}/turns", response_model=RehearsalEnvelope)
def respond(
    rehearsal_id: uuid.UUID,
    body: TurnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """Grade one rehearsal turn."""

    rehearsal = _load(db, current_user, rehearsal_id)
    try:
        RehearsalService(db).respond(
            current_user,
            rehearsal,
            text=body.text,
            mode=body.mode,
            turn_index=body.turn_index,
        )
    except RehearsalRefused as exc:
        raise _refused(exc) from exc
    db.commit()
    db.refresh(rehearsal)
    return _envelope(db, current_user, rehearsal)


@router.post("/{rehearsal_id}/debrief", response_model=RehearsalEnvelope)
def debrief(
    rehearsal_id: uuid.UUID,
    body: DebriefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """How the real thing went. This is the package's success metric."""

    if body.outcome not in REHEARSAL_OUTCOMES:
        raise _refused(RehearsalRefused("unknown_outcome"))
    rehearsal = _load(db, current_user, rehearsal_id)
    try:
        RehearsalService(db).debrief(
            current_user, rehearsal, outcome=body.outcome, free_line=body.free_line
        )
    except RehearsalRefused as exc:
        raise _refused(exc) from exc
    db.commit()
    db.refresh(rehearsal)
    return _envelope(db, current_user, rehearsal)


@router.post("/{rehearsal_id}/abandon", response_model=RehearsalEnvelope)
def abandon(
    rehearsal_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RehearsalEnvelope:
    """Drop a rehearsal. It still counts against the week: the scene was paid for."""

    rehearsal = _load(db, current_user, rehearsal_id)
    RehearsalService(db).abandon(rehearsal)
    db.commit()
    return _envelope(db, current_user)
