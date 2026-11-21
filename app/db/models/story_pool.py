"""Red-thread design, slice 5: a generated day's page, shared between learners.

One row per page a writer wrote for a contract day in the shared mode
(``app/services/season/page_pool.py``): the accepted draft as written, with the
learner's marks still as slots and nothing of the life it was written in. A learner
whose day gives the writer the same input (``frame_hash``) reads the same page; their
own words are put in when it is served, and every guard runs on what they will read.
A retired page is never served again and never deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base
from app.db.models._clock import app_now


class StoryPoolPage(Base):
    __tablename__ = "story_pool_pages"
    __table_args__ = (Index("ix_story_pool_pages_frame", "season_id", "day_key", "frame_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    season_id: Mapped[str] = mapped_column(String(40), nullable=False)
    #: The planned day: ``<gap>:<premise>``.
    day_key: Mapped[str] = mapped_column(String(160), nullable=False)
    #: For the owner's reading: the level band and the learner's language of the page.
    band: Mapped[str] = mapped_column(String(8), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    #: SHA-256 of what the writer was given (``page_pool.frame``).
    frame_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The accepted ``SceneDraft``, slots unfilled, life-bound claims cleared.
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=False)
    #: ``living_story.VERSION`` of the engine that wrote it.
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    served: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=app_now, server_default=func.now(), nullable=False
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
