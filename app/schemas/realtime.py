"""Schemas for real-time session messaging."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class SessionUserMessage(BaseModel):
    """Inbound message when a learner submits content."""

    type: Literal["user_message"]
    content: str
    suggested_words: list[int] = Field(default_factory=list)


class SessionTypingMessage(BaseModel):
    """Inbound typing indicator payload."""

    type: Literal["typing"]
    is_typing: bool = True


class SessionHeartbeatMessage(BaseModel):
    """Inbound heartbeat event to keep the connection alive."""

    type: Literal["heartbeat"]
    sent_at: datetime | None = None


SessionClientMessage = Annotated[
    SessionUserMessage | SessionTypingMessage | SessionHeartbeatMessage,
    Field(discriminator="type"),
]
