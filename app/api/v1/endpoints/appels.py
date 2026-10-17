"""Les appels — the cast phones the learner (``app.services.appels``).

Every route answers a plain 404 while ``ATELIER_CALLS_ENABLED`` is off, before
authentication. ``GET /appels/today`` never calls a provider; picking up, declining
(the voicemail) and each line may, and are paid routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.user import User
from app.services import appels


def require_calls_enabled() -> None:
    if not appels.calls_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


router = APIRouter(prefix="/appels", tags=["appels"], dependencies=[Depends(require_calls_enabled)])


def get_call_provider() -> appels.CallProvider:
    """Injection seam: tests override it with ``FakeCallProvider``."""

    return appels.default_provider()


class SayRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=600)
    mode: str = Field("text", pattern="^(text|voice)$")


def _refused(refused: appels.CallRefused) -> HTTPException:
    return HTTPException(status_code=refused.status_code, detail=refused.detail())


@router.get("/today")
def call_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Today's call (ringing, live, ended or missed), or ``{"call": null}``."""

    call = appels.today(db, current_user)
    db.commit()
    return {"call": call}


@router.post("/{call_id}/answer")
def answer_call(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: appels.CallProvider = Depends(get_call_provider),
) -> dict[str, Any]:
    try:
        call = appels.answer(db, current_user, call_id, provider=provider)
    except appels.CallRefused as refused:
        db.rollback()
        raise _refused(refused) from refused
    db.commit()
    return {"call": call}


@router.post("/{call_id}/decline")
def decline_call(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: appels.CallProvider = Depends(get_call_provider),
) -> dict[str, Any]:
    try:
        call = appels.decline(db, current_user, call_id, provider=provider)
    except appels.CallRefused as refused:
        db.rollback()
        raise _refused(refused) from refused
    db.commit()
    return {"call": call}


@router.post("/{call_id}/say")
def say_on_call(
    call_id: str,
    payload: SayRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: appels.CallProvider = Depends(get_call_provider),
) -> dict[str, Any]:
    try:
        call = appels.say(db, current_user, call_id, payload.text, mode=payload.mode, provider=provider)
    except appels.CallRefused as refused:
        db.rollback()
        raise _refused(refused) from refused
    db.commit()
    return {"call": call}


@router.post("/{call_id}/hang-up")
def hang_up_call(
    call_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        call = appels.hang_up(db, current_user, call_id)
    except appels.CallRefused as refused:
        db.rollback()
        raise _refused(refused) from refused
    db.commit()
    return {"call": call}
