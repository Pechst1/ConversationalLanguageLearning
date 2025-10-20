"""User database model."""
from datetime import date, datetime, time
import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


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

    # Settings
    daily_goal_minutes = Column(Integer, default=15)
    notifications_enabled = Column(Boolean, default=True)
    preferred_session_time = Column(Time)

    # Subscription
    subscription_tier = Column(String(20), default="free")
    subscription_expires_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

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
