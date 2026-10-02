"""One learner's Revue on one dossier (WP-119 phase 1).

The session plan (``plan``, :class:`app.services.revue.session.SessionPlan`) is
pinned at start; the conversation state (``state``,
:class:`app.services.revue.state.ConversationState`) is an append-only event log
replayed on resume. ``app/services/revue/encounter.py`` is the only writer.

One ``active`` session per learner per ISO week: the partial unique index below
(PostgreSQL in production, the identical SQLite index in tests) plus a service-level
check before insert, which is what answers ``409 revue_session_active``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

REVUE_STATUSES: tuple[str, ...] = ("active", "closed", "abandoned")
_ACTIVE_SQL = "status = 'active'"


class RevueSession(Base):
    __tablename__ = "revue_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: ISO week, ``"2026-W40"``.
    week: Mapped[str] = mapped_column(String(8), nullable=False)
    dossier_id: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_revue_sessions_user_week", "user_id", "week"),
        Index(
            "uq_revue_sessions_one_active_per_week",
            "user_id",
            "week",
            unique=True,
            postgresql_where=text(_ACTIVE_SQL),
            sqlite_where=text(_ACTIVE_SQL),
        ),
    )
