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




class UserCanDoStamp(Base):
    """WP-95 «Le Carnet» — the first time story evidence showed one can-do.

    One row per (learner, can-do), written once and never removed: the Seal
    the Carnet presses. ``quote_fr`` keeps the learner's own words that did it
    (≤160 chars); ``source`` is ``scene`` (an engine scene whose objective was
    met), ``epreuve`` (a passed «Numéro spécial») or ``authored`` (an authored
    scenario mapped to a can-do). Writer: :mod:`app.services.can_do`.
    """

    __tablename__ = "user_can_do_stamps"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    can_do_id: Mapped[str] = mapped_column(String(60), nullable=False)
    band: Mapped[str] = mapped_column(String(10), nullable=False)
    stamped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    journey_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("daily_journeys.id", ondelete="SET NULL"), nullable=True
    )
    scene_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scene_title_fr: Mapped[str | None] = mapped_column(String(200), nullable=True)
    character_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quote_fr: Mapped[str | None] = mapped_column(String(160), nullable=True)
    #: scene | epreuve | authored
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="scene")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "can_do_id", name="uq_user_can_do_stamps_user_can_do"),
    )


__all__ = ["UserCEFRProgressHistory", "UserCanDoStamp", "UserLevelCheckpoint"]
