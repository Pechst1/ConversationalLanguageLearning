"""User database model."""
from datetime import date, datetime, time
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.grammar import UserGrammarProgress


class User(Base):
    """Represents an application user."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))

    # Profile
    native_language = Column(String(10), default="en")
    target_language = Column(String(10), nullable=False, default="fr")
    proficiency_level = Column(String(20), default="beginner")

    # Gamification
    total_xp = Column(Integer, default=0)
    level = Column(Integer, default=1)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_activity_date = Column(Date, index=True)

    # Grammar-specific streak tracking
    grammar_streak_days = Column(Integer, default=0)
    grammar_last_review_date = Column(Date)
    grammar_longest_streak = Column(Integer, default=0)

    # Settings - Practice
    daily_goal_minutes = Column(Integer, default=15)
    daily_goal_xp = Column(Integer, default=50)
    new_words_per_day = Column(Integer, default=10)
    default_vocab_direction = Column(String(20), default="fr_to_de")
    preferred_session_time = Column(Time)  # Deprecated in favor of reminder_time string for simplicity, but kept for schema compact? No, let's just add new ones.

    # Settings - Notifications
    notifications_enabled = Column(Boolean, default=True)  # Global toggle
    practice_reminders = Column(Boolean, default=True)
    reminder_time = Column(String(10), default="09:00")
    streak_notifications = Column(Boolean, default=True)
    weekly_email_summary = Column(Boolean, default=True)
    achievement_notifications = Column(Boolean, default=True)

    # Settings - Appearance
    theme = Column(String(20), default="system")
    font_size = Column(String(20), default="medium")

    # Settings - Audio
    voice_input_enabled = Column(Boolean, default=True)
    text_to_speech_enabled = Column(Boolean, default=True)
    tts_speed = Column(String(10), default="1.0")  # Stored as string to avoid float precision issues if needed, or float
    auto_play_pronunciation = Column(Boolean, default=True)

    # User interests for personalized conversations
    interests = Column(String(500), default="")  # Comma-separated: "tech,sports,cooking"

    # Settings - Grammar
    grammar_correction_level = Column(String(20), default="moderate")
    show_grammar_explanations = Column(Boolean, default=True)

    # Subscription
    subscription_tier = Column(String(20), default="free")
    subscription_expires_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Relationships
    grammar_progress = relationship("UserGrammarProgress", back_populates="user", lazy="dynamic")

    def mark_activity(self, activity_date: date | None = None) -> None:
        """Update last activity and streak metadata."""

        activity_date = activity_date or date.today()
        self.last_activity_date = activity_date

    def activate_subscription(self, tier: str, expires_at: datetime | None) -> None:
        """Activate or update the user subscription."""

        self.subscription_tier = tier
        self.subscription_expires_at = expires_at

    def set_preferred_session_time(self, session_time: time | None) -> None:
        """Update the user's preferred session time."""

        self.preferred_session_time = session_time
