"""User error tracking models."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserError(Base):
    """Track specific user errors for spaced repetition review."""

    __tablename__ = "user_errors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=True
    )
    message_id = Column(
        UUID(as_uuid=True), ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )

    # Error Details
    error_category = Column(String(50), nullable=False)  # e.g., "grammar", "spelling", "vocabulary"
    error_pattern = Column(String(100))  # Legacy field, kept for backwards compatibility
    subcategory = Column(String(50))  # Fine-grained: "gender_agreement", "verb_tenses", "subjonctif", etc.
    original_text = Column(Text)  # The exact erroneous text the user wrote (e.g., "une homme")
    correction = Column(Text)  # The corrected version (e.g., "un homme")
    context_snippet = Column(Text)  # Broader context / explanation

    # SRS Fields (FSRS-compatible)
    stability = Column(Float, default=0.0)
    difficulty = Column(Float, default=5.0)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=1)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    occurrences = Column(Integer, default=1)  # How many times this error pattern occurred
    state = Column(String(20), default="new")  # "new", "learning", "review", "relearning"
    
    last_review_date = Column(DateTime(timezone=True))
    next_review_date = Column(DateTime(timezone=True), index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="errors")
    session = relationship("LearningSession")
    message = relationship("ConversationMessage")

    def mark_review(self, review_date: datetime, next_review: datetime, rating: int) -> None:
        """Update scheduling metadata after a review."""
        self.last_review_date = review_date
        self.next_review_date = next_review
        self.reps += 1
        if rating <= 2:
            self.lapses += 1


class UserErrorConcept(Base):
    """User's progress on an error CONCEPT (not individual patterns).
    
    This model provides SRS tracking at the concept level to prevent
    over-representation of common mistake types like gender agreement.
    Individual error instances (UserError) link to their parent concept.
    """

    __tablename__ = "user_error_concepts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id = Column(String(50), nullable=False)  # e.g. "gender_agreement"
    
    # SRS Fields (this is what gets scheduled for review)
    stability = Column(Float, default=0.0)
    difficulty = Column(Float, default=5.0)
    elapsed_days = Column(Integer, default=0)
    scheduled_days = Column(Integer, default=1)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    state = Column(String(20), default="new")  # "new", "learning", "review", "relearning"
    
    last_review_date = Column(DateTime(timezone=True))
    next_review_date = Column(DateTime(timezone=True), index=True)
    
    # Aggregated stats from all patterns in this concept
    total_occurrences = Column(Integer, default=0)
    last_occurrence_date = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="error_concepts")
    
    # Unique constraint: one concept per user
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
    
    def increment_occurrence(self) -> None:
        """Called when a new error instance matches this concept."""
        self.total_occurrences = (self.total_occurrences or 0) + 1
        self.last_occurrence_date = datetime.now()
        self.lapses = (self.lapses or 0) + 1
        # Increase difficulty slightly for repeated errors (max 10)
        self.difficulty = min(10.0, (self.difficulty or 5.0) + 0.3)
        # Reset to relearning if was mastered
        if self.state in ("review", "mastered"):
            self.state = "relearning"
    
    def mark_review(self, review_date: datetime, next_review: datetime, rating: int) -> None:
        """Update scheduling metadata after reviewing this concept."""
        self.last_review_date = review_date
        self.next_review_date = next_review
        self.reps += 1
        if rating <= 2:
            self.lapses += 1
