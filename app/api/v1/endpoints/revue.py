"""La Revue de Romy, phase 1 (WP-119): the week's offer and the encounter.

The wire is ``docs/implementation/atelier-v2/WP-119-WIRE.md``. Every route answers a
plain 404 while ``settings.REVUE_ENABLED`` is off — the flag check is the router's first
dependency, before authentication, so the feature stays invisible. Then the existing
``get_current_user`` and the paid-route guard (active once the POSTs are listed in
``app.core.rate_limit.PAID_ROUTES``).
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
    RvMakeOffer,
    RvMakeRequest,
    RvMakeResult,
    RvMatchRequest,
    RvMatchResult,
    RvOffer,
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
