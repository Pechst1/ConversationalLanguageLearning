"""Serial world spine models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.graphic_novel import GraphicNovelScene
    from app.db.models.mission import RealWorldMission
    from app.db.models.user import User


class SerialThread(Base):
    """A persistent serial story spine for one learner."""

    __tablename__ = "serial_threads"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    world_bible = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    state = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    news_seed = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    current_episode_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    episodes: Mapped[list["SerialEpisode"]] = relationship(
        "SerialEpisode", back_populates="thread", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_serial_threads_user_status", "user_id", "status"),
    )


class SerialEpisode(Base):
    """One act-or-see beat inside a serial thread."""

    __tablename__ = "serial_episodes"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("serial_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    episode_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("real_world_missions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("graphic_novel_scenes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    location_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    hook = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    hook_from_previous = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    state_delta = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    brief_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="available", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    thread: Mapped["SerialThread"] = relationship("SerialThread", back_populates="episodes")
    mission: Mapped["RealWorldMission | None"] = relationship("RealWorldMission")
    scene: Mapped["GraphicNovelScene | None"] = relationship("GraphicNovelScene")

    __table_args__ = (
        UniqueConstraint("thread_id", "episode_index", name="uq_serial_episode_thread_index"),
        Index("ix_serial_episodes_thread_status", "thread_id", "status"),
    )


__all__ = ["SerialEpisode", "SerialThread"]
