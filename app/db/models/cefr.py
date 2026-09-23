"""Persisted CEFR estimate history."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class UserCEFRProgressHistory(Base):
    """Point-in-time CEFR estimate snapshots for smoothing and forecasting."""

    __tablename__ = "user_cefr_progress_history"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    estimate_level: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), default="recompute", nullable=False)
    signal_snapshot = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship("User")

    __table_args__ = (
        Index("ix_user_cefr_history_user_created", "user_id", "created_at"),
    )


class UserLevelCheckpoint(Base):
    """WP-L7 — one learner's checkpoint («épreuve») for one sub-band.

    A row exists once the band's coverage has been met at least once (``ready``),
    or once the band is credited without an épreuve (``credited``: bands below a
    level shown before the coverage rule shipped, or below a placement /
    declaration that in-app work confirmed). ``passed`` and ``credited`` both
    close the band; ``failed`` reopens it after ``retry_after`` (a week of
    consolidation). State machine: :mod:`app.services.level_checkpoint`.
    """

    __tablename__ = "user_level_checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    band: Mapped[str] = mapped_column(String(10), nullable=False)
    #: ready | passed | failed | credited
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ready")
    #: Where the state came from: coverage, episode, release_grandfather, prior_confirmed, api …
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "band", name="uq_user_level_checkpoints_user_band"),
    )


__all__ = ["UserCEFRProgressHistory", "UserLevelCheckpoint"]
