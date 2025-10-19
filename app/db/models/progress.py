"""Vocabulary progress models."""
import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserVocabularyProgress(Base):
    """Track per-user vocabulary progress and FSRS state."""

    __tablename__ = "user_vocabulary_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id = Column(
        Integer, ForeignKey("vocabulary_words.id", ondelete="CASCADE"), nullable=False, index=True
    )

    stability = Column(Float, default=0.0)
    difficulty = Column(Float, default=5.0)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=1)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    state = Column(String(20), default="new")

    proficiency_score = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)
    hint_count = Column(Integer, default=0)

    last_review_date = Column(DateTime(timezone=True))
    next_review_date = Column(DateTime(timezone=True))
    due_date = Column(Date, index=True)

    times_seen = Column(Integer, default=0)
    times_used_correctly = Column(Integer, default=0)
    times_used_incorrectly = Column(Integer, default=0)

    error_types = Column(JSONB, default=list)

    first_seen_date = Column(DateTime(timezone=True), server_default=func.now())
    mastered_date = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="vocabulary_progress")
    word = relationship("VocabularyWord")
    reviews = relationship(
        "ReviewLog", back_populates="progress", cascade="all, delete-orphan", lazy="selectin"
    )

    def mark_review(self, review_date: datetime, next_review: datetime, rating: int) -> None:
        """Update scheduling metadata after a review."""

        self.last_review_date = review_date
        self.next_review_date = next_review
        self.due_date = next_review.date() if next_review else None
        self.reps += 1
        if rating <= 2:
            self.lapses += 1

    def record_usage(self, correct: bool, used_hint: bool = False) -> None:
        """Update usage counters based on conversation events."""

        self.times_seen += 1
        if correct:
            self.times_used_correctly += 1
            self.correct_count += 1
        else:
            self.times_used_incorrectly += 1
            self.incorrect_count += 1
        if used_hint:
            self.hint_count += 1

    def adjust_proficiency(self, delta: int) -> None:
        """Adjust proficiency score within 0-100 bounds."""

        new_score = max(0, min(100, (self.proficiency_score or 0) + delta))
        self.proficiency_score = new_score
        if new_score >= 90 and not self.mastered_date:
            self.mastered_date = datetime.utcnow()


class ReviewLog(Base):
    """Individual review history entries for vocabulary words."""

    __tablename__ = "review_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    progress_id = Column(
        UUID(as_uuid=True), ForeignKey("user_vocabulary_progress.id", ondelete="CASCADE"), nullable=False
    )
    review_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    rating = Column(Integer, nullable=False)
    response_time_ms = Column(Integer)
    state_transition = Column(String(50))
    schedule_before = Column(Integer)
    schedule_after = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    progress = relationship("UserVocabularyProgress", back_populates="reviews")

    def set_schedule_transition(self, before: int | None, after: int | None) -> None:
        """Store review scheduling transition values."""

        self.schedule_before = before
        self.schedule_after = after
