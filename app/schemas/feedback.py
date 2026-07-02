"""Schemas for lightweight in-app feedback reports."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FeedbackCategory = Literal[
    "bug",
    "broken_link",
    "content",
    "layout",
    "slow_loading",
    "suggestion",
    "other",
]


class FeedbackReportCreate(BaseModel):
    """Payload submitted by the global feedback widget."""

    category: FeedbackCategory
    message: str | None = Field(default=None, max_length=1000)
    route: str = Field(..., min_length=1, max_length=240)
    url: str | None = Field(default=None, max_length=2000)
    screen: str | None = Field(default=None, max_length=120)
    viewport: dict[str, Any] = Field(default_factory=dict)
    user_agent: str | None = Field(default=None, max_length=500)
    context_payload: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @field_validator("route", mode="before")
    @classmethod
    def strip_route(cls, value: str) -> str:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("message", "url", "screen", "user_agent", mode="before")
    @classmethod
    def blank_strings_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class FeedbackReportRead(BaseModel):
    """Stored feedback report returned to the submitter or admins."""

    id: uuid.UUID
    user_id: uuid.UUID
    category: str
    message: str | None = None
    route: str
    url: str | None = None
    screen: str | None = None
    viewport: dict[str, Any]
    user_agent: str | None = None
    context_payload: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


__all__ = ["FeedbackCategory", "FeedbackReportCreate", "FeedbackReportRead"]
