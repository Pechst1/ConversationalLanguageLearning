"""The streak, one row per learner-local day (WP-D5).

``User.grammar_streak_days`` is the number Home prints; this table is the
grid behind it. Both are written by :mod:`app.services.streak` in the same
flush — a practised day in :func:`record_practice_day`, a «jour de relâche» in
:func:`settle_streak` when a banked freeze covers a missed day — so the number
and the calendar cannot disagree. A day with no row is a missed day.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base

#: A day the learner practised (finished the daily journey or a Séance).
STREAK_DAY_PRACTISED = "practised"
#: A missed day a banked freeze covered: it keeps the chain, it does not add.
STREAK_DAY_RELACHE = "relache"


class StreakDay(Base):
    __tablename__ = "streak_days"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: The learner's own calendar day, in ``User.timezone`` when it was written.
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_streak_days_user_date"),
    )


__all__ = ["STREAK_DAY_PRACTISED", "STREAK_DAY_RELACHE", "StreakDay"]
