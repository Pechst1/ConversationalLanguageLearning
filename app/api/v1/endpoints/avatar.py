"""The learner's avatar: read it, save it (items unlocked by achievements).

Free for everyone, onboarding included: no paid-route guard.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.user import User
from app.schemas.avatar import AvatarState, AvatarUpdate
from app.services.avatar import (
    AvatarInvalidError,
    AvatarItemLockedError,
    AvatarService,
    AvatarStateData,
)
from app.utils.cache import build_cache_key, cache_backend

router = APIRouter(prefix="/avatar", tags=["avatar"])


def _read(state: AvatarStateData) -> AvatarState:
    return AvatarState.model_validate(asdict(state))


@router.get("", response_model=AvatarState)
def read_avatar(
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> AvatarState:
    """The learner's avatar (``null`` until they make one) and every reward item."""

    return _read(AvatarService(db).state(current_user))


@router.put(
    "",
    response_model=AvatarState,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": 'An item not unlocked yet: `{"detail": {"code": "avatar_item_locked", "item": …}}`'
        },
    },
)
def save_avatar(
    payload: AvatarUpdate,
    *,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> AvatarState:
    """Replace the learner's avatar. Locked items are refused with 403."""

    try:
        state = AvatarService(db).save(current_user, payload.avatar)
    except AvatarInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except AvatarItemLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "avatar_item_locked", "item": exc.item},
        ) from exc
    # The cached /users/me profile is the user row; drop it with the row changed.
    cache_backend.invalidate("user:profile", key=build_cache_key(user_id=str(current_user.id)))
    return _read(state)
