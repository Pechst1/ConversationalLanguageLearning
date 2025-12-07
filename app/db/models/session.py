"""Session and conversation database models."""
import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class LearningSession(Base):
    """Represents a user learning session."""

    __tablename__ = "learning_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    planned_duration_minutes = Column(Integer, nullable=False)
    actual_duration_minutes = Column(Integer)
    topic = Column(String(255))
    conversation_style = Column(String(50))
    difficulty_preference = Column(String(20))
    anki_direction = Column(String(20))
    scenario = Column(String(50))

    words_practiced = Column(Integer, default=0)
    new_words_introduced = Column(Integer, default=0)
    words_reviewed = Column(Integer, default=0)
    correct_responses = Column(Integer, default=0)
    incorrect_responses = Column(Integer, default=0)
    accuracy_rate = Column(Float)

    xp_earned = Column(Integer, default=0)
    level_before = Column(Integer)
    level_after = Column(Integer)

    status = Column(String(20), default="in_progress")

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="sessions")
    messages = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )
    interactions = relationship(
        "WordInteraction", back_populates="session", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    """Individual messages exchanged during a session."""

    __tablename__ = "conversation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )

    sender = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    sequence_number = Column(Integer, nullable=False)

    target_words = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)

    errors_detected = Column(JSONB().with_variant(JSON(), "sqlite"))
    words_used = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    suggested_words_used = Column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    xp_earned = Column(Integer, default=0)

    generation_prompt = Column(String)
    llm_model = Column(String(50))
    tokens_used = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("LearningSession", back_populates="messages")


class WordInteraction(Base):
    """Detailed tracking of word interactions within sessions."""

    __tablename__ = "word_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    word_id = Column(
        Integer, ForeignKey("vocabulary_words.id", ondelete="CASCADE"), nullable=False, index=True
    )

    interaction_type = Column(String(50), nullable=False)

    message_id = Column(UUID(as_uuid=True), ForeignKey("conversation_messages.id"))
    context_sentence = Column(Text)
    user_response = Column(Text)

    error_type = Column(String(50))
    error_description = Column(String)
    correction = Column(String)

    response_time_ms = Column(Integer)
    was_suggested = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("LearningSession", back_populates="interactions")
    message = relationship("ConversationMessage")
