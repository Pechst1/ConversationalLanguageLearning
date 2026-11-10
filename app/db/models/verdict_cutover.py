"""Package V stage 1: the moment the verdict stack went live.

One row, written by the migration that ships the stack, so its time is the deploy's.
Rows a learner stored before it keep what they counted for (``VERDICT_LEGACY_ROWS``,
default ``as_counted``): a change to how a verdict is read must never move a level, l'or
or a token the learner already earned. :mod:`app.services.verdict_cutover` reads it.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class VerdictCutover(Base):
    __tablename__ = "verdict_cutover"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    note: Mapped[str] = mapped_column(String(200), nullable=False, default="")
