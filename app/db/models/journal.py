"""WP-30 — «Le journal de bord»: the recap the learner writes themselves.

One row per (learner, recalled scene). The row is the whole package's state,
because every one of its properties needs to survive a night:

* **The offer is dated, not computed on the fly.** ``offered_on`` is the
  learner-local day the entry became askable (scene day + 1) and
  ``followup_due_on`` is the +7-day one-liner's day. Storing both means a
  learner who opens the app at 23:58 and answers at 00:02 is asked about the
  scene they were offered, not a different one.
* **The learner's text outlives the correction.** ``entry_text`` is written
  before any provider is called and is never rolled back by a grading failure:
  ``assessment_status`` says ``unavailable`` and the writing stands.
* **Content recall and grammar are two columns, not one score.** Remembering
  what Romy asked for and writing it in correct French are different claims,
  and the package exists to keep them apart.

The row holds a *snapshot* of the scene facts it scored against
(``scene_facts``), copied at offer time from public read paths. The story is
never written from here, and a later story revision must not silently rescore
an entry the learner already answered.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

#: ``offered``     — the prompt exists; the learner has written nothing yet.
#: ``written``     — the learner wrote, and the correction came back.
#: ``unavailable`` — the learner wrote, and the checker did not answer. The text
#:                   is kept; no verdict is invented.
#: ``skipped``     — the learner declined this entry. Terminal, and it is why the
#:                   same scene is never offered twice.
JOURNAL_STATUSES: tuple[str, ...] = ("offered", "written", "unavailable", "skipped")

#: The +7-day follow-up's answer, as the digest reads it.
#: ``used_again_later`` — the learner still recalled a stored scene fact a week on.
#: ``not_recalled``     — they answered, and nothing they wrote matched a fact.
#: ``unanswered``       — no follow-up answer exists yet. Never a zero.
JOURNAL_FOLLOWUP_SIGNALS: tuple[str, ...] = (
    "used_again_later",
    "not_recalled",
    "unanswered",
)


class JournalEntry(Base):
    """One free-recall entry about one scene, plus its +7-day follow-up."""

    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: The scene being recalled. ``SET NULL`` rather than cascade: a learner's
    #: own writing is not a detail of the journey row that prompted it.
    journey_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("daily_journeys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="offered", index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="journal-v1")

    #: The learner-local day of the scene, and the day this entry became askable
    #: (scene day + ``RECALL_OFFSET_DAYS``).
    scene_date: Mapped[date] = mapped_column(Date, nullable=False)
    offered_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    followup_due_on: Mapped[date] = mapped_column(Date, nullable=False)

    #: The cue the learner sees before writing. Carries **no scene text**: a
    #: free-recall prompt that shows the scene is a copying exercise.
    cue: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: The facts content recall is scored against, snapshotted at offer time.
    scene_facts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )
    #: The scene text, revealed only *after* the learner has written.
    scene_reveal: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    entry_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: ``checked`` or ``unavailable``. The one word the learner-facing state
    #: machine turns on.
    assessment_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    #: The Séance correction payload as the correction service returned it.
    correction: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: ``{"score": 0..1|None, "matched": [...], "missed": [...]}`` — the content
    #: half, deliberately never folded into the grammar verdict.
    content_recall: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: One line from the character, about what the learner remembered.
    reaction_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: What the vocabulary credit service was told, summarised.
    vocabulary_credit: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: WP-24 erratum ids created from this entry's grammar errors.
    errata_ids: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )

    # -- the +7-day follow-up ---------------------------------------------
    followup_prompt_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_signal: Mapped[str | None] = mapped_column(String(24), nullable=True)
    followup_recall: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    followup_answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Denormalised from ``content_recall`` so a digest reads one indexed column.
    recall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    __table_args__ = (
        # One entry per scene. The offer is made once, and a replayed create
        # cannot fork a learner's memory of the same evening into two rows.
        UniqueConstraint("user_id", "journey_id", name="uq_journal_entries_user_journey"),
        Index("ix_journal_entries_user_status", "user_id", "status"),
        Index("ix_journal_entries_user_offered", "user_id", "offered_on"),
        Index("ix_journal_entries_user_followup", "user_id", "followup_due_on"),
    )


__all__ = ["JOURNAL_FOLLOWUP_SIGNALS", "JOURNAL_STATUSES", "JournalEntry"]
