"""WP-25 — the placement conversation's one durable row.

A placement is a short adaptive conversation whose *result* the CEFR service
reads as a prior. Two properties drive the shape of this table:

* **Resumable.** A learner who closes the app mid-placement comes back to the
  same session with the same graded turns, so the turns live in a row rather
  than in a request.
* **Idempotent.** Grading costs money. A replayed response for a turn that is
  already graded must return the stored grading instead of paying again, so
  each turn carries its index and the grading that was written for it.

The estimate is stored as it was computed, with the evidence that produced it.
A session whose provider never answered stays ``unassessed`` and carries no
level: an honest absence, never a level nobody measured.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

#: ``in_progress`` — turns are still being asked.
#: ``complete``    — enough graded turns; ``estimate_level`` is set.
#: ``unassessed``  — the grader never answered; no level, and the learner is told so.
#: ``skipped``     — the learner declined the offer. Also a terminal state.
#: ``abandoned``   — superseded by a re-run started from Réglages.
PLACEMENT_STATUSES = ("in_progress", "complete", "unassessed", "skipped", "abandoned")


class PlacementSession(Base):
    """One placement conversation and the estimate it produced."""

    __tablename__ = "placement_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="in_progress", index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="placement-v1")
    #: The band the next prompt is drawn from — the adaptive ladder's cursor.
    current_band: Mapped[str] = mapped_column(String(8), nullable=False, default="A1.2")
    #: One entry per asked turn: band, prompt, the learner's answer, its grading.
    turns: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=list,
        nullable=False,
    )
    #: The whole result payload — level, confidence, per-dimension means, evidence.
    estimate: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"),
        default=dict,
        nullable=False,
    )
    #: Denormalized from ``estimate`` so the CEFR service reads one indexed row.
    #: ``None`` whenever no level was measured, which is the honest case.
    estimate_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("ix_placement_sessions_user_status", "user_id", "status"),
        Index("ix_placement_sessions_user_created", "user_id", "created_at"),
    )


__all__ = ["PLACEMENT_STATUSES", "PlacementSession"]
