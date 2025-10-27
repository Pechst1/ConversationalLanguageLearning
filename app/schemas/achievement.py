"""Pydantic schemas for achievement endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AchievementRead(BaseModel):
    """Achievement definition schema."""

    id: int
    achievement_key: str
    name: str
    description: str | None = None
    tier: str
    xp_reward: int
    icon_url: str | None = None


class AchievementProgressResponse(BaseModel):
    """User achievement progress schema."""

    achievement_id: int
    achievement_key: str
    name: str
    description: str | None = None
    tier: str
    xp_reward: int
    icon_url: str | None = None
    current_progress: int
    target_progress: int
    completed: bool
    unlocked_at: datetime | None = None


class AchievementUnlockResponse(BaseModel):
    """Response after checking for achievement unlocks."""

    newly_unlocked: list[AchievementRead] = Field(default_factory=list)
    total_unlocked: int


__all__ = [
    "AchievementRead",
    "AchievementProgressResponse",
    "AchievementUnlockResponse",
]
