"""One learner's Revue on one dossier (WP-119 phase 1).

The session plan (``plan``, :class:`app.services.revue.session.SessionPlan`) is
pinned at start; the conversation state (``state``,
:class:`app.services.revue.state.ConversationState`) is an append-only event log
replayed on resume. ``app/services/revue/encounter.py`` is the only writer.

One ``active`` session per learner per *period*: the partial unique index below
(PostgreSQL in production, the identical SQLite index in tests) plus a service-level
check before insert, which is what answers ``409 revue_session_active``.

**Period (WP-119 phase 3, §12.2).** The column is still called ``week`` (renaming it would
touch every reader for a label), but it holds the Papier's period: the ISO week
(``"2026-W40"``) under ``REVUE_CADENCE=weekly`` and the ISO date (``"2026-10-03"``) under
``daily``. ``app.services.revue.weekly.period_for`` writes it and ``week_of_period`` reads the
ISO week back; migration ``f6b8d0a2c4e7`` widened it to ten characters.

:class:`RevueDossier` (same migration) is the intake's output: one row per editorial dossier
the weekly task built (``app/tasks/revue.py``), which ``weekly.load_week`` reads before the
hand-authored files.
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
    #: The period: ISO week ``"2026-W40"`` (weekly) or ISO date ``"2026-10-03"`` (daily).
    week: Mapped[str] = mapped_column(String(10), nullable=False)
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


class RevueDossier(Base):
    """One editorial dossier the intake built (WP-119 phase 3, §4.1).

    ``payload`` is the :class:`app.services.revue.dossier.EditorialDossier` JSON, quotes
    included; ``source_hashes`` maps each source id to the SHA-256 of the article text the
    quotes were checked against. The text itself is never stored (§12.3).
    """

    __tablename__ = "revue_dossiers"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    #: The ISO week the dossier belongs to (``EditorialDossier.week``).
    week: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    #: The kiosk period it was built for: the ISO week (weekly) or the ISO date (daily).
    period: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    source_hashes: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict
    )
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False, default=dict)
    builder_version: Mapped[str] = mapped_column(String(40), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
