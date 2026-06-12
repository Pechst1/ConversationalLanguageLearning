"""Authentication API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.core.security import InvalidTokenError
from app.schemas import LogoutRequest, RefreshTokenRequest, Token, UserCreate, UserLogin, UserRead
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
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)) -> Token:
    """Authenticate a user and return JWT tokens."""

    service = AuthService(db)
    try:
        user = service.authenticate_user(payload.email, payload.password)
        return service.create_tokens(
            user,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as exc:
        # Developer convenience: optionally create the user on first login attempt in dev
        if settings.AUTO_CREATE_USERS_ON_LOGIN:
            try:
                created = service.register_user(
                    UserCreate(
                        email=payload.email,
                        password=payload.password,
                        full_name=payload.email.split("@")[0],
                    )
                )
                return service.create_tokens(
                    created,
                    user_agent=request.headers.get("user-agent"),
                    ip_address=request.client.host if request.client else None,
                )
            except EmailAlreadyExistsError:
                # If a user exists with a different password, still return 401
                pass
        handle_invalid_credentials(exc)


@router.post("/refresh", response_model=Token)
def refresh_tokens(payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    """Rotate a refresh token and return a fresh token pair."""

    service = AuthService(db)
    try:
        return service.rotate_refresh_token(
            payload.refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except (InvalidCredentialsError, InvalidTokenError, ValueError, KeyError) as exc:
        handle_invalid_credentials(InvalidCredentialsError("Invalid refresh token"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest | None = None, db: Session = Depends(get_db)) -> None:
    """Revoke the supplied refresh token if the client has one."""

    service = AuthService(db)
    service.revoke_refresh_token(payload.refresh_token if payload else None)
