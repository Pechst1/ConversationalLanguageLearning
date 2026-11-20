"""La Revue de Romy, phase 1 (WP-119): the week's offer and the encounter.

The wire is ``docs/implementation/atelier-v2/WP-119-WIRE.md``. Every route answers a
plain 404 while ``settings.REVUE_ENABLED`` is off — the flag check is the router's first
dependency, before authentication, so the feature stays invisible. Then the existing
``get_current_user`` and the paid-route guard (active once the POSTs are listed in
``app.core.rate_limit.PAID_ROUTES``).

«Au comptoir» (WP-119, 2026-10-19) sits on the same router. ``REVUE_COMPTOIR_ENABLED`` decides
which sessions start at the counter, not whether its route answers: a session started while the
switch was on plays to its end after it is turned off (a chat session answers 409).

«Le fil» (2026-11-20) likewise: ``REVUE_ASSIGNMENTS_ENABLED`` decides which sessions are dealt
it; its route answers a session that was (any other answers 409 ``revue_not_fil``).

«Le titre» and «L'intox express» (2026-11-20) share ONE act route,
``POST /sessions/{id}/rubrique``, which plays the assignment the session was dealt
(``rubriques.LOOPS``; any other session answers 409 ``revue_not_rubrique``). «Le fil» keeps
its own route.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.core.rate_limit import paid_route_guard
from app.db.models.user import User
from app.schemas.revue import (
    WEEK_PATTERN,
    RvCloseResult,
    RvComptoirRequest,
    RvComptoirResult,
    RvFilRequest,
    RvFilResult,
    RvMakeOffer,
    RvMakeRequest,
    RvMakeResult,
    RvMatchRequest,
    RvMatchResult,
    RvOffer,
    RvRubriqueRequest,
    RvRubriqueResult,
    RvSessionView,
    RvStartRequest,
    RvTurnRequest,
    RvTurnResult,
)
from app.services.revue.encounter import (
    RevueEncounter,
    RevueError,
    RevueProvider,
    default_provider,
    owned_session,
)


def require_revue_enabled() -> None:
    if not getattr(settings, "REVUE_ENABLED", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(
    prefix="/revue",
    tags=["revue"],
    dependencies=[Depends(require_revue_enabled), Depends(paid_route_guard(get_current_user))],
)


def get_revue_provider() -> RevueProvider:
    """Injection seam: tests override it with ``FakeRevueProvider``."""

    return default_provider()


def get_encounter(
    db: Session = Depends(get_db),
    provider: RevueProvider = Depends(get_revue_provider),
) -> RevueEncounter:
    return RevueEncounter(db, provider)


def _http(error: RevueError) -> HTTPException:
    return HTTPException(status_code=error.status, detail=error.detail)


@router.get("/week", response_model=RvOffer)
def read_week(
    week: str | None = Query(None, pattern=WEEK_PATTERN),
    current_user: User = Depends(get_current_user),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvOffer:
    """The week's recommended story, two alternatives, and any session to resume or already filed."""

    try:
        return encounter.week_offer(current_user, week)
    except RevueError as error:
        raise _http(error) from error


@router.post("/match", response_model=RvMatchResult)
def match_request(
    body: RvMatchRequest,
    current_user: User = Depends(get_current_user),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvMatchResult:
    """«Autre chose ?»: match a free request against the week's dossiers. Nothing is stored."""

    return encounter.match(current_user, body.text, body.week)


@router.post("/sessions", response_model=RvSessionView, status_code=status.HTTP_201_CREATED)
def start_session(
    body: RvStartRequest,
    current_user: User = Depends(get_current_user),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvSessionView:
    try:
        row = encounter.start(
            current_user,
            week=body.week,
            dossier_id=body.dossier_id,
            free_request=body.free_request,
            angle_id=body.angle_id,
        )
        return encounter.view(row)
    except RevueError as error:
        raise _http(error) from error


@router.get("/sessions/{session_id}", response_model=RvSessionView)
def read_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvSessionView:
    """Resume: a pure replay of the session's state. No model call, nothing written."""

    try:
        return encounter.view(owned_session(db, current_user, session_id))
    except RevueError as error:
        raise _http(error) from error


@router.post("/sessions/{session_id}/turns", response_model=RvTurnResult)
def post_turn(
    session_id: str,
    body: RvTurnRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvTurnResult:
    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.turn(row, body.text, mode=body.mode, client_turn_id=body.client_turn_id)
    except RevueError as error:
        raise _http(error) from error


@router.get("/sessions/{session_id}/make", response_model=RvMakeOffer)
def read_make_options(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvMakeOffer:
    """The make options; the headline exercise is built once and reused, its answer never sent."""

    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.make_options(row)
    except RevueError as error:
        raise _http(error) from error


@router.post(
    "/sessions/{session_id}/make",
    response_model=RvMakeResult,  # WP-119 phase 2: + headline_write, short_report
)
def post_make(
    session_id: str,
    body: RvMakeRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> Any:
    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.make(row, body.kind, body.model_dump())
    except RevueError as error:
        raise _http(error) from error


@router.post("/sessions/{session_id}/close", response_model=RvCloseResult)
def close_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvCloseResult:
    """Romy does something with it: the dispatch, the words and claims kept, her memory. Idempotent."""

    try:
        row = owned_session(db, current_user, session_id, lock=True)
        view, closing = encounter.close(row)
        return RvCloseResult(session=view, closing=closing)
    except RevueError as error:
        raise _http(error) from error


@router.post("/sessions/{session_id}/comptoir", response_model=RvComptoirResult)
def post_comptoir(
    session_id: str,
    body: RvComptoirRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvComptoirResult:
    """«Au comptoir»: one act of the learner's loop (vote, react, intox_who, intox_fix,
    opinion, comeback). 409 ``revue_not_comptoir`` on a chat session, 409
    ``revue_comptoir_out_of_order`` (with the current ``step``) for an act out of order; an
    act that repeats one already recorded returns the session as it is."""

    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.comptoir(row, body)
    except RevueError as error:
        raise _http(error) from error


@router.post("/sessions/{session_id}/fil", response_model=RvFilResult)
def post_fil(
    session_id: str,
    body: RvFilRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvFilResult:
    """«Le fil»: one act of the learner's loop (open, order, words, tell, tell_fix). 409
    ``revue_not_fil`` on another session, 409 ``revue_fil_out_of_order`` (with the current
    ``step``) for an act out of order; an act that repeats one already recorded returns the
    session as it is; ``error`` says why an act the learner can fix was not recorded."""

    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.fil(row, body)
    except RevueError as error:
        raise _http(error) from error


@router.post("/sessions/{session_id}/rubrique", response_model=RvRubriqueResult)
def post_rubrique(
    session_id: str,
    body: RvRubriqueRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    encounter: RevueEncounter = Depends(get_encounter),
) -> RvRubriqueResult:
    """«Le titre» (open, pick, trap, build, build_fix) and «L'intox express» (open, answer,
    fix): one act of the assignment the session was dealt. 409 ``revue_not_rubrique`` on
    another session, 409 ``revue_<mode>_out_of_order`` (with the current ``step``) for an act
    out of order; an act that repeats one already recorded returns the session as it is;
    ``error`` says why an act the learner can fix was not recorded."""

    try:
        row = owned_session(db, current_user, session_id, lock=True)
        return encounter.rubrique(row, body)
    except RevueError as error:
        raise _http(error) from error
