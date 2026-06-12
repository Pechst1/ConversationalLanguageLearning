"""Atelier grammar practice models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.grammar import GrammarConcept
    from app.db.models.user import User


class AtelierSession(Base):
    """A focused Atelier practice session built from three selected concepts."""

    __tablename__ = "atelier_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    selected_concept_ids = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False)
    quote_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False)
    recap_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User")
    attempts: Mapped[list["AtelierAttempt"]] = relationship(
        "AtelierAttempt", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_atelier_sessions_user_status", "user_id", "status"),
    )


class AtelierExerciseSet(Base):
    """Cached generated exercise payload for one grammar concept/version."""

    __tablename__ = "atelier_exercise_sets"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("grammar_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="llm", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    concept: Mapped["GrammarConcept"] = relationship("GrammarConcept")

    __table_args__ = (
        UniqueConstraint("concept_id", "generator_version", "content_hash", name="uq_atelier_exercise_set_payload"),
        Index("ix_atelier_exercise_sets_lookup", "concept_id", "generator_version", "created_at"),
    )


class AtelierLanguagePack(Base):
    """Versioned language-level conventions used by Atelier asset generation."""

    __tablename__ = "atelier_language_packs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="approved", nullable=False)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    generation_metadata = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("language_code", "version", name="uq_atelier_language_pack_version"),
        Index("ix_atelier_language_packs_status", "language_code", "review_status"),
    )


class AtelierConceptBlueprint(Base):
    """Reviewable concept-level assets: pedagogy, motifs, recipes, rubrics, and hints."""

    __tablename__ = "atelier_concept_blueprints"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("grammar_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    asset_version: Mapped[str] = mapped_column(String(80), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="approved", nullable=False)
    payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    generation_metadata = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    concept: Mapped["GrammarConcept"] = relationship("GrammarConcept")

    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "language",
            "asset_version",
            name="uq_atelier_concept_blueprint_version",
        ),
        Index("ix_atelier_concept_blueprints_lookup", "concept_id", "language", "review_status"),
    )


class AtelierAttempt(Base):
    """One submitted Atelier drill or writing attempt."""

    __tablename__ = "atelier_attempts"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    atelier_session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("atelier_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("grammar_concepts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    round: Mapped[str] = mapped_column(String(30), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    exercise_id: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    answer_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    correction_payload = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    verdict: Mapped[str] = mapped_column(String(30), default="needs_review", nullable=False)
    score_0_4: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session: Mapped[AtelierSession] = relationship("AtelierSession", back_populates="attempts")
    user: Mapped["User"] = relationship("User")
    concept: Mapped["GrammarConcept"] = relationship("GrammarConcept")

    __table_args__ = (
        Index("ix_atelier_attempts_session_round", "atelier_session_id", "round", "mode"),
    )


__all__ = [
    "AtelierAttempt",
    "AtelierConceptBlueprint",
    "AtelierExerciseSet",
    "AtelierLanguagePack",
    "AtelierSession",
]
