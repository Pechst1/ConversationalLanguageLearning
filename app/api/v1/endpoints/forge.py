"""La Forge (WP-S3): the test-out and the forge's per-rule state.

* ``POST /atelier/forge/test-out`` — start «Épreuve de la règle» for any rule
  (owner, 2026-09-24: available from day one). Returns the session; its items
  are answered through the ordinary ``POST /atelier/sessions/{id}/attempts``
  and the attempt response carries ``forge`` (next item, and the result once
  the fifth item is in).
* ``GET /atelier/forge/state`` — per rule: current rung, stage, next due,
  held / tested-out stamps (``?concept_id=`` narrows it).
* ``GET /atelier/forge/sessions/{id}`` — the forge's view of one session.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import _session_response, get_atelier_user
from app.db.models.user import User
from app.schemas.atelier import (
    AtelierForgeStateResponse,
    AtelierForgeTestOutRequest,
    AtelierSessionStartResponse,
)
from app.services.forge import ForgeService, session_for_user

router = APIRouter(prefix="/atelier/forge", tags=["atelier"])


@router.post("/test-out", response_model=AtelierSessionStartResponse, status_code=status.HTTP_201_CREATED)
def start_test_out(
    payload: AtelierForgeTestOutRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierSessionStartResponse:
    try:
        session = ForgeService(db).start_test_out(user=current_user, concept_id=payload.concept_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar concept not found") from exc
    return _session_response(db, current_user, session, fast_path=True, background_tasks=background_tasks)


@router.get("/state", response_model=AtelierForgeStateResponse)
def get_forge_state(
    concept_id: list[int] | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> AtelierForgeStateResponse:
    return AtelierForgeStateResponse(rules=ForgeService(db).state_for_user(user=current_user, concept_ids=concept_id))


@router.get("/sessions/{session_id}")
def get_forge_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> dict:
    session = session_for_user(db, user=current_user, session_id=session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atelier session not found")
    return ForgeService(db).view(user=current_user, session=session)
