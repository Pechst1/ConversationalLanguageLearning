"""Security utilities for password hashing and JWT handling."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or is invalid."""


# bcrypt only ever reads the first 72 bytes of a password. bcrypt 4 truncated
# silently; bcrypt 5 raises ValueError, which surfaced as a 500 on sign-up and
# sign-in (WP-71). New passwords are refused above this at the schema; checking
# an existing one compares the same 72-byte prefix bcrypt 4 stored.
BCRYPT_MAX_PASSWORD_BYTES = 72


def password_byte_length(password: str) -> int:
    """Length of a password as bcrypt counts it: UTF-8 bytes, not characters."""

    return len(password.encode("utf-8"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Validate a plaintext password against a hashed value. Never raises."""

    if not plain_password or not hashed_password:
        return False
    candidate = plain_password.encode("utf-8")[:BCRYPT_MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(candidate, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        # A malformed or foreign hash is a failed check, not a server error.
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using the configured hashing algorithm.

    Raises ``ValueError`` above 72 UTF-8 bytes; the request schemas reject such a
    password first with a readable 422.
    """

    encoded = password.encode("utf-8")
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes.")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def get_unusable_password_hash() -> str:
    """Return a valid hash whose random source value is never disclosed."""

    return get_password_hash(secrets.token_urlsafe(48))


def _create_token(
    subject: str | Any,
    expires_delta: timedelta,
    token_type: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> str:
    expire = expires_at if expires_at is not None else datetime.now(UTC) + expires_delta
    payload: dict[str, Any] = {"exp": expire, "sub": str(subject), "type": token_type}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(
    subject: str | Any,
    expires_minutes: int | None = None,
    *,
    auth_version: int | None = None,
) -> str:
    """Create a signed JWT access token for the supplied subject."""

    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    extra_claims = {"av": auth_version} if auth_version is not None else None
    return _create_token(  # noqa: S106 - JWT type claim, not a credential
        subject,
        timedelta(minutes=minutes),
        token_type="access",  # noqa: S106 - JWT type claim, not a credential
        extra_claims=extra_claims,
    )


def create_refresh_token(
    subject: str | Any,
    expires_days: int | None = None,
    *,
    auth_version: int | None = None,
    token_id: str | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Create a signed JWT refresh token for the supplied subject.

    With an explicit whole-second ``expires_at`` the token is a pure function of
    its claims (HS256 is deterministic), which is what lets the refresh grace
    window hand a late racer the very successor the winner already holds.
    """

    days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    extra_claims: dict[str, Any] = {}
    if auth_version is not None:
        extra_claims["av"] = auth_version
    if token_id:
        extra_claims["jti"] = token_id
    return _create_token(  # noqa: S106 - JWT type claim, not a credential
        subject,
        timedelta(days=days),
        token_type="refresh",  # noqa: S106 - JWT type claim, not a credential
        extra_claims=extra_claims or None,
        expires_at=expires_at,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode a JWT and return its payload, raising ``InvalidTokenError`` if invalid."""

    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:  # pragma: no cover - defensive branch
        raise InvalidTokenError(str(exc)) from exc
