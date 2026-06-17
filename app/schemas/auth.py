"""Authentication related schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class Token(BaseModel):
    """Token response returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Payload data extracted from access tokens."""

    sub: uuid.UUID
    exp: datetime
    type: str
    av: int | None = None
    jti: str | None = None


class RefreshTokenRequest(BaseModel):
    """Request body for rotating an access/refresh token pair."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Optional refresh token payload for explicit session logout."""

    refresh_token: str | None = None
