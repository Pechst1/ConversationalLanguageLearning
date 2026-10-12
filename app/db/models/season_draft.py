"""A season the writer drafted in the background (WP-168 follow-up, 12 October 2026).

The season writer takes 60–95 s. It used to run on the learner's request when a
season ended. Now it runs on a worker thread (``season_writer.request_draft``),
started when the finale closes, and keeps its result here. The rollover adopts a
``ready`` row on the request path without a model call. One row per (thread,
season); the learner's story state is never written from the worker.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base


class StorySeasonDraft(Base):
    __tablename__ = "story_season_drafts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("serial_threads.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: ``drafting`` → ``ready`` | ``refused`` | ``failed``; ``ready`` → ``adopted``.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="drafting")
    #: The season file ``season_writer.draft_next_season`` returned (``ready`` only).
    season_file = mapped_column(JSONB().with_variant(JSON(), "sqlite"), nullable=True)
    #: Why it was refused, the retries, the seconds it took.
    detail = mapped_column(JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
