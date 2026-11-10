"""Package V stage 3: the settlement job's log. One row per thing that happened to one answer.

An answer saved unread (its live :class:`VerdictRecord` does not count and says a later
check could help) is queued here, and :mod:`app.services.verdict_settle` checks it again
later. The newest row of a subject is the job's state:

* ``queued``: waiting for its first attempt (``next_at``);
* ``refused``: the broker would not take the task; the sweep sends it again at ``next_at``;
* ``unread``: an attempt ran and the provider still did not read it; tried again at ``next_at``;
* ``over_budget``: the learner's background checks for the day are spent; tried tomorrow;
* ``settled``: a check landed and the answer counts (``settled_record_id``);
* ``gave_up``: the attempts are spent; only the learner's «Ask again» can still try;
* ``error``: the attempt itself raised (logged); tried again at ``next_at``.

``source`` is ``auto`` (the sweep) or ``ask`` (the learner's «Ask again»). Only ``auto``
attempts spend the daily budget; ``ask`` has its own limit (``enforce_recheck_limit``).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models._clock import app_now


class VerdictSettlement(Base):
    __tablename__ = "verdict_settlements"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    record_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_record_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=app_now
    )

    __table_args__ = (
        Index("ix_verdict_settlements_subject", "subject_type", "subject_id", "created_at"),
        Index("ix_verdict_settlements_user_day", "user_id", "created_at"),
        Index("ix_verdict_settlements_due", "state", "next_at"),
    )
