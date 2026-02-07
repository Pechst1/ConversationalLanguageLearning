"""Pydantic models for user API interactions."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserBase(BaseModel):
    """Shared properties of user representations."""

    email: EmailStr
    full_name: Optional[str] = None
    native_language: str = Field(default="en", max_length=10)
    target_language: str = Field(default="fr", max_length=10)
    proficiency_level: str = Field(default="beginner", max_length=20)
    daily_goal_minutes: int = Field(default=15, ge=0)
    daily_goal_xp: int = Field(default=50, ge=0)
    new_words_per_day: int = Field(default=10, ge=1)
    default_vocab_direction: str = Field(default="fr_to_de", max_length=20)
    
    # Notifications
    notifications_enabled: bool = True
    practice_reminders: bool = True
    reminder_time: str = Field(default="09:00", max_length=10)
    streak_notifications: bool = True
    weekly_email_summary: bool = True
    achievement_notifications: bool = True
    preferred_session_time: Optional[time] = None

    # Appearance
    theme: str = Field(default="system", max_length=20)
    font_size: str = Field(default="medium", max_length=20)

    # Audio
    voice_input_enabled: bool = True
    text_to_speech_enabled: bool = True
    tts_speed: str = Field(default="1.0", max_length=10)
    auto_play_pronunciation: bool = True

    # Grammar
    grammar_correction_level: str = Field(default="moderate", max_length=20)
    show_grammar_explanations: bool = True


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


class UserUpdate(BaseModel):
    """Schema for partial updates to the current user profile."""

    full_name: Optional[str] = Field(default=None, max_length=255)
    native_language: Optional[str] = Field(default=None, max_length=10)
    target_language: Optional[str] = Field(default=None, max_length=10)
    proficiency_level: Optional[str] = Field(default=None, max_length=20)
    daily_goal_minutes: Optional[int] = Field(default=None, ge=0)
    daily_goal_xp: Optional[int] = Field(default=None, ge=0)
    new_words_per_day: Optional[int] = Field(default=None, ge=1)
    default_vocab_direction: Optional[str] = Field(default=None, max_length=20)
    
    notifications_enabled: Optional[bool] = None
    practice_reminders: Optional[bool] = None
    reminder_time: Optional[str] = Field(default=None, max_length=10)
    streak_notifications: Optional[bool] = None
    weekly_email_summary: Optional[bool] = None
    achievement_notifications: Optional[bool] = None
    preferred_session_time: Optional[time] = None

    theme: Optional[str] = Field(default=None, max_length=20)
    font_size: Optional[str] = Field(default=None, max_length=20)

    voice_input_enabled: Optional[bool] = None
    text_to_speech_enabled: Optional[bool] = None
    tts_speed: Optional[str] = Field(default=None, max_length=10)
    auto_play_pronunciation: Optional[bool] = None

    grammar_correction_level: Optional[str] = Field(default=None, max_length=20)
    show_grammar_explanations: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def ensure_payload_not_empty(self) -> "UserUpdate":
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one field must be provided")
        return self
