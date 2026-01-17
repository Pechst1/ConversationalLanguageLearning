"""Story-related database models for interactive narrative learning."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class Story(Base):
    """Represents an interactive narrative story with multiple chapters."""

    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    story_key = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    difficulty_level = Column(String(20))  # A1, A2, B1, B2, C1, C2
    estimated_duration_minutes = Column(Integer, default=60)
    theme_tags = Column(JSONB, default=list)  # ["mystery", "adventure", "romance"]
    vocabulary_theme = Column(
        String(100)
    )  # "daily_life,food,places" - matches VocabularyWord.topic_tags
    cover_image_url = Column(String(500))
    author = Column(String(100))
    total_chapters = Column(Integer, default=0)

    # Publishing
    is_published = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    chapters = relationship(
        "StoryChapter",
        back_populates="story",
        order_by="StoryChapter.sequence_order",
        cascade="all, delete-orphan",
    )
    user_progress = relationship(
        "UserStoryProgress", back_populates="story", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_stories_published", "is_published", "difficulty_level"),
    )

    def __repr__(self) -> str:
        return f"<Story(id={self.id}, key={self.story_key}, title={self.title})>"


class StoryChapter(Base):
    """Individual chapter within a story."""

    __tablename__ = "story_chapters"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(
        Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False
    )
    chapter_key = Column(String(100), nullable=False, index=True)
    sequence_order = Column(Integer, nullable=False)

    # Content
    title = Column(String(255), nullable=False)
    synopsis = Column(Text)  # Brief description
    opening_narrative = Column(Text)  # Initial scene setting

    # Session parameters
    min_turns = Column(Integer, default=3)
    max_turns = Column(Integer, default=10)

    # Goals and completion
    narrative_goals = Column(
        JSONB, default=list
    )  # [{"goal_id": "find_key", "description": "...", "required_words": [...]}]
    completion_criteria = Column(
        JSONB
    )  # {"min_goals_completed": 2, "min_vocabulary_used": 5}

    # Branching narrative
    branching_choices = Column(
        JSONB
    )  # [{"choice_id": "help_baker", "text": "...", "next_chapter_id": 5}]
    default_next_chapter_id = Column(
        Integer, ForeignKey("story_chapters.id"), nullable=True
    )

    # Rewards
    completion_xp = Column(Integer, default=75)
    perfect_completion_xp = Column(Integer, default=150)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    story = relationship("Story", back_populates="chapters")
    next_chapter = relationship(
        "StoryChapter", remote_side=[id], foreign_keys=[default_next_chapter_id]
    )

    __table_args__ = (
        Index("idx_story_chapters_story_seq", "story_id", "sequence_order"),
    )

    def __repr__(self) -> str:
        return f"<StoryChapter(id={self.id}, story_id={self.story_id}, key={self.chapter_key}, order={self.sequence_order})>"


class UserStoryProgress(Base):
    """Tracks user progress through stories."""

    __tablename__ = "user_story_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    story_id = Column(
        Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Progress tracking
    current_chapter_id = Column(
        Integer, ForeignKey("story_chapters.id"), nullable=True
    )
    chapters_completed = Column(
        JSONB, default=list
    )  # [{"chapter_id": 1, "completed_at": "...", "xp_earned": 75, "was_perfect": true}]
    total_chapters_completed = Column(Integer, default=0)

    # Completion status
    status = Column(
        String(20), default="in_progress"
    )  # in_progress, completed, abandoned
    completion_percentage = Column(Float, default=0.0)

    # Statistics
    total_xp_earned = Column(Integer, default=0)
    total_time_spent_minutes = Column(Integer, default=0)
    vocabulary_mastered_count = Column(Integer, default=0)
    perfect_chapters_count = Column(Integer, default=0)

    # Story-specific data
    narrative_choices = Column(
        JSONB, default=dict
    )  # {"ch1_discovery": "help_baker", ...}

    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    last_accessed_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="story_progress")
    story = relationship("Story", back_populates="user_progress")
    current_chapter = relationship("StoryChapter", foreign_keys=[current_chapter_id])

    __table_args__ = (
        Index("idx_user_story_status", "user_id", "status"),
        Index("idx_user_current_chapter", "user_id", "current_chapter_id"),
        Index("idx_user_story_unique", "user_id", "story_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<UserStoryProgress(id={self.id}, user_id={self.user_id}, story_id={self.story_id}, status={self.status})>"
