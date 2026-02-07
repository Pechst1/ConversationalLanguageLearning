"""Grammar models for structured grammar review with SRS."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class GrammarConcept(Base):
    """A grammar concept to be learned (e.g., 'B2 - Partizip Perfekt')."""

    __tablename__ = "grammar_concepts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)  # A1, A2, B1, B2, C1, C2
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Verben, Nomen, etc.
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of examples
    difficulty_order: Mapped[int] = mapped_column(Integer, default=0)  # Ordering within level

    # Prerequisites for concept dependency graph
    prerequisites = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=list)
    # Structure: [concept_id1, concept_id2] - IDs of concepts that should be learned first

    # Visualization type for interactive diagrams
    visualization_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Values: "conjugation_table", "timeline", "agreement_flow", "sentence_structure"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user_progress: Mapped[list["UserGrammarProgress"]] = relationship(
        "UserGrammarProgress", back_populates="concept", lazy="dynamic"
    )

    __table_args__ = (
        Index("ix_grammar_concepts_level", "level"),
    )


class UserGrammarProgress(Base):
    """User's SRS progress for a grammar concept."""

    __tablename__ = "user_grammar_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    concept_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grammar_concepts.id", ondelete="CASCADE"), nullable=False
    )

    # SRS fields (matching Excel tracker logic)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-10 rating
    reps: Mapped[int] = mapped_column(Integer, default=0)  # Number of reviews
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # State: "neu", "ausbaufähig", "in_arbeit", "gefestigt", "gemeistert"
    state: Mapped[str] = mapped_column(String(50), default="neu")
    
    # Review scheduling
    last_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_review: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="grammar_progress")
    concept: Mapped["GrammarConcept"] = relationship("GrammarConcept", back_populates="user_progress")

    __table_args__ = (
        Index("ix_user_grammar_progress_user_concept", "user_id", "concept_id", unique=True),
        Index("ix_user_grammar_progress_next_review", "user_id", "next_review"),
    )

    @property
    def state_label(self) -> str:
        """Return German label for state."""
        labels = {
            "neu": "Neu",
            "ausbaufähig": "Ausbaufähig",
            "in_arbeit": "In Arbeit",
            "gefestigt": "Gefestigt",
            "gemeistert": "Gemeistert",
        }
        return labels.get(self.state, self.state)


__all__ = ["GrammarConcept", "UserGrammarProgress"]
