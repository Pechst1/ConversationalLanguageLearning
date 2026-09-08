"""Atelier V2 daily journey API (WP-02).

Every route is authenticated with the existing ``get_current_user`` dependency —
there is no new token path and no production bypass. The static
``/capabilities/progress`` route is declared **before** ``/{journey_id}`` so it
is never swallowed by the dynamic segment.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.daily_journey import (
    AttemptResult,
    CapabilityProgress,
    HelpResult,
    JourneyAdvanceRequest,
    JourneyAttemptRequest,
    JourneyCreateRequest,
    JourneyFinishRequest,
    JourneyHelpRequest,
    JourneyRetryRequest,
    JourneyRevisionRequest,
    JourneySnapshot,
    TodayEnvelope,
)
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import JourneyAdapters, build_default_adapters

router = APIRouter(prefix="/daily-journeys", tags=["daily-journeys"])

_ADAPTERS: JourneyAdapters | None = None


def get_journey_adapters() -> JourneyAdapters:
    """Injection seam for WP-03/04/05/06/09/11.

    Overridable with ``app.dependency_overrides[get_journey_adapters]``; the
    resolved default always prefers a real domain module over a stub.
    """

    global _ADAPTERS
    if _ADAPTERS is None:
        _ADAPTERS = build_default_adapters()
    return _ADAPTERS


def get_journey_service(
    db: Session = Depends(get_db),
    adapters: JourneyAdapters = Depends(get_journey_adapters),
) -> DailyJourneyService:
    return DailyJourneyService(db, adapters)


@router.get("/today", response_model=TodayEnvelope)
def read_today(
    timezone: str | None = Query(
        None,
        max_length=64,
        description="Client IANA timezone, used only when no journey exists yet.",
    ),
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> TodayEnvelope:
    """Capability, the open journey, or today's available scenario.

    Never creates a journey and never pays for generation.
    """

    return service.get_today(current_user, timezone_hint=timezone)


@router.get("/capabilities/progress", response_model=CapabilityProgress)
def read_capability_progress(
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> CapabilityProgress:
    """Evidence-backed practical capability summary (WP-09 fills this in)."""

    return service.get_capability_progress(current_user)


@router.post("", response_model=JourneySnapshot, status_code=status.HTTP_201_CREATED)
def create_journey(
    payload: JourneyCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """201 for a new ready journey, 200 for an existing one, 202 while preparing."""

    snapshot, status_code = service.create_journey(current_user, payload)
    response.status_code = status_code
    return snapshot


@router.get("/{journey_id}", response_model=JourneySnapshot)
def read_journey(
    journey_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Owned persisted state, terminal states included. Safe to poll."""

    return service.get_journey(current_user, journey_id)


@router.post(
    "/{journey_id}/steps/{step_id}/help",
    response_model=HelpResult,
)
def use_help(
    journey_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: JourneyHelpRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> HelpResult:
    """Record the reveal, then return it. Assistance is never client-asserted."""

    return service.use_help(current_user, journey_id, step_id, payload)


@router.post(
    "/{journey_id}/steps/{step_id}/attempts",
    response_model=AttemptResult,
)
def submit_attempt(
    journey_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: JourneyAttemptRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> AttemptResult:
    """Canonical server evaluation. The client never supplies a score."""

    return service.submit_attempt(current_user, journey_id, step_id, payload)


@router.post("/{journey_id}/advance", response_model=JourneySnapshot)
def advance(
    journey_id: uuid.UUID,
    payload: JourneyAdvanceRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Acknowledge the current step and activate the next eligible one."""

    return service.advance(current_user, journey_id, payload)


@router.post("/{journey_id}/pause", response_model=JourneySnapshot)
def pause(
    journey_id: uuid.UUID,
    payload: JourneyRevisionRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Preserve every completed step."""

    return service.pause(current_user, journey_id, payload)


@router.post("/{journey_id}/resume", response_model=JourneySnapshot)
def resume(
    journey_id: uuid.UUID,
    payload: JourneyRevisionRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Return the same step and the same pinned content, never a new plan."""

    return service.resume(current_user, journey_id, payload)


@router.post("/{journey_id}/finish", response_model=JourneySnapshot)
def finish(
    journey_id: uuid.UUID,
    payload: JourneyFinishRequest,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Complete requires resolved mandatory steps; early records partial work."""

    return service.finish(current_user, journey_id, payload)


@router.post("/{journey_id}/retry", response_model=JourneySnapshot)
def retry(
    journey_id: uuid.UUID,
    payload: JourneyRetryRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    service: DailyJourneyService = Depends(get_journey_service),
) -> JourneySnapshot:
    """Bounded recovery for a preparing/unavailable journey, reusing its id."""

    snapshot, status_code = service.retry_journey(current_user, journey_id, payload)
    response.status_code = status_code
    return snapshot
