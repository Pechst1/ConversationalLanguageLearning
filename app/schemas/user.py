"""Pydantic models for user API interactions."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Shared properties of user representations."""

    email: EmailStr
    full_name: Optional[str] = None
    native_language: str = Field(default="en", max_length=10)
    target_language: str = Field(default="fr", max_length=10)
    proficiency_level: str = Field(default="beginner", max_length=20)
    daily_goal_minutes: int = Field(default=15, ge=0)
    notifications_enabled: bool = True
    preferred_session_time: Optional[time] = None


class UserCreate(UserBase):
    """Schema for user registration input."""

    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr
    password: str


class UserRead(UserBase):
    """Schema returned after user registration or retrieval."""

    id: uuid.UUID
    is_active: bool
    is_verified: bool
    subscription_tier: str
    subscription_expires_at: Optional[datetime]
    total_xp: int
    level: int
    current_streak: int
    longest_streak: int
    last_activity_date: Optional[date]

    model_config = ConfigDict(from_attributes=True)
