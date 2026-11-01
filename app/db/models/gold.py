"""Package O-1 — l'or: the gold ledger and its balance cache (shadow first).

``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §15. The ledger is append-only in
spirit: an entry's amount is decided when it is minted, a pending entry is
settled or voided once (R6), and nothing is ever deleted. The balance is a
cache, recomputable from the ledger at any time.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base
from app.db.models._clock import app_now


class GoldLedgerEntry(Base):
    """One movement of l'or: an answer's feuilles, a milestone, a bonus (later: a purchase)."""

    __tablename__ = "atelier_gold_ledger"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    #: Positive for earning, negative for spending (O-3). After the plafond.
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: ``earn`` · ``milestone`` · ``bonus`` · ``award`` · ``spend`` · ``adjust``.
    entry_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: ``pending`` · ``settled`` · ``void``.
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    #: ``journey_target`` · ``journey_reply`` · ``forge_item`` · ``letter`` · ``milestone`` · …
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Unique per learner: the same evidence can never mint twice.
    source_key: Mapped[str] = mapped_column(String(255), nullable=False)
    #: ``{kind, id}`` of the learning target, or null for a unit (a reply turn, a letter).
    target: Mapped[dict[str, Any] | None] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    #: What the server recorded: category, format, outcome, assistance, the R4 gap …
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: How the amount came about: base, factors, R1, the plafond, the reason line.
    breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The learner's local day (the zone pinned against plafond resets, §6).
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: ISO week in Europe/Paris, ``2026-W45``.
    week_id: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=app_now, server_default=func.now(), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: ``not_yet`` · ``unread`` · ``withdrawn`` · ``injection``.
    void_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "source_key", name="uq_atelier_gold_ledger_source"),
        Index("ix_atelier_gold_ledger_user_day", "user_id", "local_date"),
        Index("ix_atelier_gold_ledger_user_week_state", "user_id", "week_id", "state"),
    )


class GoldBalance(Base):
    """The learner's livret: a cache of the settled ledger."""

    __tablename__ = "atelier_gold_balance"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    earned_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spent_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=app_now, server_default=func.now(), nullable=False
    )


__all__ = ["GoldBalance", "GoldLedgerEntry"]
