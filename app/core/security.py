"""Security utilities for password hashing and JWT handling."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
from jose import JWTError, jwt

from app.config import settings


ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Validate a plaintext password against a hashed value."""

    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using the configured hashing algorithm."""

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _create_token(subject: str | Any, expires_delta: timedelta, token_type: str) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload: Dict[str, Any] = {"exp": expire, "sub": str(subject), "type": token_type}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: str | Any, expires_minutes: int | None = None) -> str:
    """Create a signed JWT access token for the supplied subject."""

    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    return _create_token(subject, timedelta(minutes=minutes), token_type="access")


def create_refresh_token(subject: str | Any, expires_days: int | None = None) -> str:
    """Create a signed JWT refresh token for the supplied subject."""

    days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    return _create_token(subject, timedelta(days=days), token_type="refresh")


def decode_token(token: str) -> Dict[str, Any]:
    """Decode a JWT and return its payload, raising ``InvalidTokenError`` if invalid."""

    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:  # pragma: no cover - defensive branch
        raise InvalidTokenError(str(exc)) from exc
