"""Vocabulary progress models."""
import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.types import JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserVocabularyProgress(Base):
    """Track per-user vocabulary progress with both FSRS and Anki SM-2 support."""

    __tablename__ = "user_vocabulary_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id = Column(
        Integer, ForeignKey("vocabulary_words.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # FSRS fields (existing)
    stability = Column(Float, default=0.0)
    difficulty = Column(Float, default=5.0)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=1)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    state = Column(String(20), default="new")

    # Anki SM-2 fields (new)
    scheduler = Column(String(20), default="fsrs")  # "fsrs" or "anki"
    ease_factor = Column(Float, default=2.5)  # Anki ease factor
    interval_days = Column(Integer, default=0)  # Current interval in days
    phase = Column(String(20), default="new")  # "new", "learn", "review", "relearn"
    step_index = Column(Integer, default=0)  # For learning steps
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Precise due time
    
    # Anki metadata
    deck_name = Column(String(255), nullable=True)
    note_id = Column(String(50), nullable=True)
    card_id = Column(String(50), nullable=True)
    raw_history = Column(Text, nullable=True)  # Original allrevs data

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

    error_types = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)

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

    def mark_anki_review(self, review_date: datetime, due_at: datetime, rating: int, 
                        interval_days: int, ease_factor: float, phase: str) -> None:
        """Update Anki SM-2 scheduling metadata after a review."""
        
        self.last_review_date = review_date
        self.due_at = due_at
        self.due_date = due_at.date() if due_at else None
        self.interval_days = interval_days
        self.ease_factor = ease_factor
        self.phase = phase
        self.reps += 1
        if rating < 3:
            self.lapses += 1

    def record_usage(self, correct: bool, *, used_hint: bool = False, is_new: bool = False) -> None:
        """Update usage counters based on conversation events."""

        self.times_seen += 1
        if correct:
            self.times_used_correctly += 1
            self.correct_count += 1
            delta = 15 if is_new else 10
            self.adjust_proficiency(delta)
        else:
            self.times_used_incorrectly += 1
            self.incorrect_count += 1
            self.adjust_proficiency(-10)
        if used_hint:
            self.hint_count += 1
            self.adjust_proficiency(-5)

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

    # Anki-specific fields
    scheduler_type = Column(String(20), default="fsrs")  # "fsrs" or "anki"
    ease_factor_before = Column(Float, nullable=True)
    ease_factor_after = Column(Float, nullable=True)
    interval_before = Column(Integer, nullable=True)
    interval_after = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    progress = relationship("UserVocabularyProgress", back_populates="reviews")

    def set_schedule_transition(self, before: int | None, after: int | None) -> None:
        """Store review scheduling transition values."""

        self.schedule_before = before
        self.schedule_after = after

    def set_anki_transition(self, ease_before: float | None, ease_after: float | None,
                           interval_before: int | None, interval_after: int | None) -> None:
        """Store Anki SM-2 scheduling transition values."""
        
        self.ease_factor_before = ease_before
        self.ease_factor_after = ease_after
        self.interval_before = interval_before
        self.interval_after = interval_after
