"""Authentication service layer."""
from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.db.models.user import User
from app.schemas import Token, UserCreate


class EmailAlreadyExistsError(ValueError):
    """Raised when attempting to register with an email that already exists."""


class InvalidCredentialsError(ValueError):
    """Raised when authentication credentials are invalid."""


class AuthService:
    """Encapsulates user registration and authentication logic."""

    def __init__(self, db: Session):
        self.db = db

    def register_user(self, payload: UserCreate) -> User:
        """Create a new user in the database."""

        existing_user = self.db.scalar(select(User).where(User.email == payload.email))
        if existing_user:
            raise EmailAlreadyExistsError("A user with this email already exists.")

        user = User(
            email=payload.email,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
            native_language=payload.native_language,
            target_language=payload.target_language,
            proficiency_level=payload.proficiency_level,
            daily_goal_minutes=payload.daily_goal_minutes,
            notifications_enabled=payload.notifications_enabled,
            preferred_session_time=payload.preferred_session_time,
        )

        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise EmailAlreadyExistsError("A user with this email already exists.") from exc
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> User:
        """Validate credentials and return the associated user."""

        user = self.db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Incorrect email or password")
        return user

    def create_tokens(self, user: User) -> Token:
        """Generate access and refresh tokens for a user."""

        user_id = uuid.UUID(str(user.id))
        access = create_access_token(str(user_id))
        refresh = create_refresh_token(str(user_id))
        return Token(access_token=access, refresh_token=refresh)


def handle_email_exists(error: EmailAlreadyExistsError) -> None:
    """Raise an HTTP 400 error for duplicate email attempts."""

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    ) from error


def handle_invalid_credentials(error: InvalidCredentialsError) -> None:
    """Raise an HTTP 401 error for invalid login attempts."""

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(error),
        headers={"WWW-Authenticate": "Bearer"},
    ) from error
