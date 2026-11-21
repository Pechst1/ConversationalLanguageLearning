"""Package V stage 5: an appeal. «I think this is right», and what the stronger model said.

One row per appeal. ``state``:

* ``upheld``: the stronger model holds the answer right. A ledger record supersedes the
  old one (``record_id``), the memo gains the answer (``memo_id``), and
  ``scripts/verdict_appeal_export.py`` writes the case to ``tests/verdict_corpus/candidates/``;
* ``refused``: it does not; ``reason`` is one sentence in the learner's language;
* ``unread``: the model could not be asked. It does not count against the day's limit.

``verdict_before`` is the verdict the learner appealed, ``ruling`` what the model answered.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models._clock import app_now

_JSON = JSONB().with_variant(JSON(), "sqlite")


class VerdictAppeal(Base):
    __tablename__ = "verdict_appeals"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    item: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    verdict_before: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    ruling: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    record_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    memo_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=app_now
    )

    __table_args__ = (
        Index("ix_verdict_appeals_subject", "subject_type", "subject_id"),
        Index("ix_verdict_appeals_user_day", "user_id", "created_at"),
    )
