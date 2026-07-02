"""User-owned guided reading library models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserBook(Base):
    """A private uploaded book owned by one learner."""

    __tablename__ = "user_books"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    target_level: Mapped[str] = mapped_column(String(10), default="A2", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False, index=True)
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_episodes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_episode_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_episode_indices = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    estimated_total_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    extra_metadata = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User")
    episodes: Mapped[list[BookEpisode]] = relationship(
        "BookEpisode", back_populates="book", cascade="all, delete-orphan", order_by="BookEpisode.order_index"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source_hash", name="uq_user_books_owner_source_hash"),
        Index("ix_user_books_user_status", "user_id", "status"),
    )


class BookEpisode(Base):
    """One level-sized guided reading episode generated from a user's book."""

    __tablename__ = "book_episodes"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_book_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    passage_text: Mapped[str] = mapped_column(Text, nullable=False)
    est_reading_minutes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cefr_level: Mapped[str] = mapped_column(String(10), default="A2", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vocab_seed = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    grammar_seed = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    exercise_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ready", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    book: Mapped[UserBook] = relationship("UserBook", back_populates="episodes")

    __table_args__ = (
        UniqueConstraint("user_book_id", "order_index", name="uq_book_episodes_book_order"),
        Index("ix_book_episodes_book_status", "user_book_id", "status"),
    )


__all__ = ["BookEpisode", "UserBook"]
