"""Package V stage 2: the verdict ledger. What was decided, by which judge, and what it paid.

Append-only. A later check of the same subject (a «Check again», a relecture, a corrector
that answered late) writes a new record whose ``supersedes_id`` names the one it replaces;
nothing is ever updated in place except ``superseded_by_id`` on the record it replaces.
The live record of a subject is the one nobody superseded.

``subject_type`` / ``subject_id`` name the stored row: ``forge_attempt``,
``courrier_attempt``, ``courrier_turn``, ``feuilleton_attempt``, ``journal_entry``.
``verdict`` holds the verdict as shown (outcome, checked_by, call, edits, counts) and the
reading it was judged from, so a replay can judge it again. ``paid`` is what this record
moved: whether it counted for the level, and the gold entry it minted or voided.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models._clock import app_now


class VerdictRecord(Base):
    __tablename__ = "verdict_records"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verdict: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    counts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    judge_version: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("verdict_records.id", ondelete="SET NULL"), nullable=True
    )
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=app_now
    )

    __table_args__ = (
        Index("ix_verdict_records_subject", "subject_type", "subject_id"),
        Index("ix_verdict_records_live", "subject_type", "subject_id", "superseded_by_id"),
    )
