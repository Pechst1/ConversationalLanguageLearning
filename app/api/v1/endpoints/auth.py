"""Authentication API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas import Token, UserCreate, UserLogin, UserRead
from app.services.auth import (
    AuthService,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    handle_email_exists,
    handle_invalid_credentials,
)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """Register a new user and return the created entity."""

    service = AuthService(db)
    try:
        user = service.register_user(payload)
    except EmailAlreadyExistsError as exc:
        handle_email_exists(exc)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate a user and return JWT tokens."""

    service = AuthService(db)
    try:
        user = service.authenticate_user(payload.email, payload.password)
    except InvalidCredentialsError as exc:
        handle_invalid_credentials(exc)
    return service.create_tokens(user)
