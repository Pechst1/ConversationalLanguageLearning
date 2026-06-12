"""Graphic novel / Feuilleton practice models."""
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
    from app.db.models.mission import RealWorldMission
    from app.db.models.serial import SerialThread
    from app.db.models.user import User


class PersonalInputItem(Base):
    """Saved user context that can seed personalized reading scenes."""

    __tablename__ = "personal_input_items"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_type: Mapped[str] = mapped_column(String(40), default="interest", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False, index=True)
    tags = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    item_metadata = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_personal_input_items_user_type", "user_id", "item_type"),
    )


class GraphicNovelScene(Base):
    """A cached Feuilleton scene driven by errata, weak concepts, and generated story structure."""

    __tablename__ = "graphic_novel_scenes"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atelier_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("atelier_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("real_world_missions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    serial_thread_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("serial_threads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    episode_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    personal_input_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("personal_input_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="available", nullable=False, index=True)
    cadence: Mapped[str] = mapped_column(String(30), default="ad_hoc", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    selected_concept_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    target_errata_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    target_vocabulary_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    source_snapshot = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    script_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    recap_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    cache_key: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    image_model: Mapped[str] = mapped_column(String(100), nullable=False)
    image_quality: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
    atelier_session: Mapped["AtelierSession | None"] = relationship("AtelierSession")
    mission: Mapped["RealWorldMission | None"] = relationship("RealWorldMission")
    serial_thread: Mapped["SerialThread | None"] = relationship("SerialThread")
    personal_input_item: Mapped["PersonalInputItem | None"] = relationship("PersonalInputItem")
    panels: Mapped[list["GraphicNovelPanel"]] = relationship(
        "GraphicNovelPanel", back_populates="scene", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["GraphicNovelAttempt"]] = relationship(
        "GraphicNovelAttempt", back_populates="scene", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "cache_key", name="uq_graphic_novel_scene_cache"),
        Index("ix_graphic_novel_scenes_user_status", "user_id", "status"),
    )


class GraphicNovelPanel(Base):
    """One illustrated panel with HTML/SVG overlay instructions."""

    __tablename__ = "graphic_novel_panels"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("graphic_novel_scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    panel_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    beat: Mapped[str] = mapped_column(Text, nullable=False)
    image_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    overlay_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    generation_metadata = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scene: Mapped["GraphicNovelScene"] = relationship("GraphicNovelScene", back_populates="panels")

    __table_args__ = (
        UniqueConstraint("scene_id", "panel_index", name="uq_graphic_novel_panel_index"),
        Index("ix_graphic_novel_panels_scene_order", "scene_id", "panel_index"),
    )


class GraphicNovelAttempt(Base):
    """One submitted overlay or short-production task in a scene."""

    __tablename__ = "graphic_novel_attempts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("graphic_novel_scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    panel_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("graphic_novel_panels.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    answer_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    correction_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), default="needs_review", nullable=False)
    score_0_4: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    scene: Mapped["GraphicNovelScene"] = relationship("GraphicNovelScene", back_populates="attempts")
    panel: Mapped["GraphicNovelPanel | None"] = relationship("GraphicNovelPanel")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index("ix_graphic_novel_attempts_scene_task", "scene_id", "task_id"),
    )


__all__ = [
    "GraphicNovelAttempt",
    "GraphicNovelPanel",
    "GraphicNovelScene",
    "PersonalInputItem",
]
