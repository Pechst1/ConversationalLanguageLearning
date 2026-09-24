"""La Forge (WP-S3): the test-out and the forge's per-rule state.

* ``POST /atelier/forge/test-out`` — start «Épreuve de la règle» for any rule
  (owner, 2026-09-24: available from day one). Returns the session; its items
  are answered through the ordinary ``POST /atelier/sessions/{id}/attempts``
  and the attempt response carries ``forge`` (next item, and the result once
  the fifth item is in).
* ``GET /atelier/forge/state`` — per rule: current rung, stage, next due,
  held / tested-out stamps (``?concept_id=`` narrows it).
* ``GET /atelier/forge/sessions/{id}`` — the forge's view of one session.

WP-S7 (momentum, each behind its own flag):

* ``GET /atelier/forge/map`` — the grammar map: every rule of the active
  syllabus with its stage (ghost · introduced · proficient · held), rung and
  next review, grouped by sub-band; the Éclair pairs; the feature switches.
* ``POST /atelier/forge/map/opened`` — the pilot event for a map open.
* ``POST /atelier/forge/eclair`` — start an Éclair round (``pair`` or
  ``concept_id``); ``POST /atelier/forge/eclair/{id}/finish`` files it.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.atelier import _session_response, get_atelier_user
from app.db.models.user import User
from app.schemas.atelier import (
    AtelierForgeStateResponse,
    AtelierForgeTestOutRequest,
    AtelierSessionStartResponse,
)
from app.services.forge import ForgeService, forge_features, session_for_user

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


# ---------------------------------------------------------------------------
# WP-S7 — the grammar map and Éclair
# ---------------------------------------------------------------------------


@router.get("/map")
def get_grammar_map(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> dict:
    from app.services.grammar_map import grammar_map

    if not forge_features()["grammar_map"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grammar map is off")
    return grammar_map(db, current_user)


@router.post("/map/opened", status_code=status.HTTP_204_NO_CONTENT)
def record_grammar_map_opened(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> Response:
    from app.services.pilot_events import PilotEventService

    PilotEventService(db).record("grammar_map_opened", user_id=current_user.id, entity_type="grammar_map")
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class EclairStartRequest(BaseModel):
    pair: str | None = Field(None, max_length=40)
    concept_id: int | None = None


class EclairAnswer(BaseModel):
    id: str = Field(..., max_length=160)
    answer: str | None = Field(None, max_length=400)


class EclairFinishRequest(BaseModel):
    answers: list[EclairAnswer] = Field(default_factory=list, max_length=200)
    elapsed_ms: int | None = Field(None, ge=0, le=600_000)


@router.post("/eclair", status_code=status.HTTP_201_CREATED)
def start_eclair(
    payload: EclairStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> dict[str, Any]:
    from app.services.eclair import EclairUnavailable, start_round

    try:
        return start_round(db, user=current_user, pair=payload.pair, concept_id=payload.concept_id)
    except EclairUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Éclair is not unlocked for this pair") from exc


@router.post("/eclair/{eclair_id}/finish")
def finish_eclair(
    eclair_id: UUID,
    payload: EclairFinishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_atelier_user),
) -> dict[str, Any]:
    from app.services.eclair import finish_round, round_for_user

    session = round_for_user(db, user=current_user, eclair_id=eclair_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Éclair round not found")
    return finish_round(
        db,
        user=current_user,
        session=session,
        answers=[answer.model_dump() for answer in payload.answers],
        elapsed_ms=payload.elapsed_ms,
    )
