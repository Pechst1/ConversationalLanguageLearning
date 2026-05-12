"""Real-world scenario mission models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.atelier import AtelierSession
    from app.db.models.user import User


class RealWorldMission(Base):
    """A weekly or post-session task that asks the learner to use French in context."""

    __tablename__ = "real_world_missions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atelier_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("atelier_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="available", nullable=False, index=True)
    cadence: Mapped[str] = mapped_column(String(30), default="weekly", nullable=False, index=True)
    mission_type: Mapped[str] = mapped_column(String(40), default="message", nullable=False, index=True)
    iso_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    iso_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    selected_concept_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    target_errata_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    target_vocabulary_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    source_snapshot = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    objectives = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    prompt_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    recap_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    atelier_session: Mapped["AtelierSession | None"] = relationship("AtelierSession")
    attempts: Mapped[list["RealWorldMissionAttempt"]] = relationship(
        "RealWorldMissionAttempt", back_populates="mission", cascade="all, delete-orphan"
    )
    turns: Mapped[list["RealWorldMissionTurn"]] = relationship(
        "RealWorldMissionTurn", back_populates="mission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "cadence", "iso_year", "iso_week", name="uq_real_world_mission_weekly"),
        Index("ix_real_world_missions_user_status", "user_id", "status"),
    )


class RealWorldMissionAttempt(Base):
    """One writing/submission attempt for a mission."""

    __tablename__ = "real_world_mission_attempts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("real_world_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(30), default="writing", nullable=False)
    answer_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    correction_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), default="needs_review", nullable=False)
    score_0_4: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    mission: Mapped[RealWorldMission] = relationship("RealWorldMission", back_populates="attempts")
    user: Mapped["User"] = relationship("User")


class RealWorldMissionTurn(Base):
    """One chat or voice transcript turn inside a mission conversation."""

    __tablename__ = "real_world_mission_turns"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("real_world_missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), default="chat", nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    audio_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    correction_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    mission: Mapped[RealWorldMission] = relationship("RealWorldMission", back_populates="turns")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        UniqueConstraint("mission_id", "turn_index", name="uq_real_world_mission_turn_index"),
        Index("ix_real_world_mission_turns_order", "mission_id", "turn_index"),
    )


__all__ = ["RealWorldMission", "RealWorldMissionAttempt", "RealWorldMissionTurn"]
