"""E1 — money held for a paid call before the provider is asked.

The cap check in :mod:`app.services.spend_guard` reads what has already been
*recorded*. Two requests that start together both see the same total and both
pass, so a learner (or the service) can end the day above its cap. A
reservation is written, under a lock, before the work starts: the check counts
every open reservation as already spent, and the row is closed when the work
ends (its real cost lands on the usual ledgers).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

#: Holding money: counted against both caps until closed.
OPEN_STATUSES = ("reserved", "uncertain")


class SpendReservation(Base):
    __tablename__ = "spend_reservations"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Idempotency: a retried request with the same key reuses its reservation.
    request_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    upper_bound_usd: Mapped[float] = mapped_column(Float, nullable=False)
    actual_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: reserved → released (work ended, its cost is on the ledgers) or settled
    #: (actual cost recorded here). A reservation nobody closed in time becomes
    #: ``uncertain`` and keeps holding its bound: a timeout is never billed at zero.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved")
    service_day: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_spend_reservations_day_status", "service_day", "status"),)
