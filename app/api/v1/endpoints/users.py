"""User management endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models.user import User
from app.schemas import UserRead, UserUpdate
from app.services.users import UserNotFoundError, UserService
from app.utils.cache import cache_backend, build_cache_key

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(deps.get_current_user)) -> UserRead:
    """Return the authenticated user profile."""

    cache_key = build_cache_key(user_id=str(current_user.id))
    cached = cache_backend.get("user:profile", cache_key)
    if cached is not None:
        return cached

    payload = UserRead.model_validate(current_user).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, payload, ttl_seconds=300)
    return payload


@router.patch("/me", response_model=UserRead)
def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db),
) -> UserRead:
    """Allow the authenticated user to update their profile details."""

    service = UserService(db)
    updated = service.update(current_user, payload)
    cache_key = build_cache_key(user_id=str(updated.id))
    cache_backend.invalidate("user:profile", key=cache_key)
    response = UserRead.model_validate(updated).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, response, ttl_seconds=300)
    return response


@router.get("/", response_model=list[UserRead])
def list_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.get_current_user),
) -> list[User]:
    """Return a paginated list of users ordered by recency."""

    service = UserService(db)
    return service.list_users(limit=limit, offset=offset)


@router.get("/{user_id}", response_model=UserRead)
def read_user_by_id(
    user_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.get_current_user),
) -> UserRead:
    """Fetch another user profile. Access control to be refined later."""

    cache_key = build_cache_key(user_id=str(user_id))
    cached = cache_backend.get("user:profile", cache_key)
    if cached is not None:
        return cached

    service = UserService(db)
    try:
        user = service.get(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = UserRead.model_validate(user).model_dump(mode="json")
    cache_backend.set("user:profile", cache_key, payload, ttl_seconds=300)
    return payload
