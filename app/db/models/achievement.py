"""Achievement tracking models."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Achievement(Base):
    """Static achievement definitions."""

    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    achievement_key = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon_url = Column(String(255))
    xp_reward = Column(Integer, default=0)
    tier = Column(String(20), default="bronze")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    """Join table storing unlocked achievements per user."""

    __tablename__ = "user_achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    achievement_id = Column(
        Integer, ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False, index=True
    )

    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())
    progress = Column(Integer, default=0)
    completed = Column(Boolean, default=False)

    achievement = relationship("Achievement", back_populates="user_achievements")
    user = relationship("User", backref="achievements")

