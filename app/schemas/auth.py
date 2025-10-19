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
