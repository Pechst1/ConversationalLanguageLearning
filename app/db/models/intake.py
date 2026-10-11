"""WP-34 — a real document the learner brought in, read once and kept private.

The learner pastes a letter or photographs a menu. It is read by one model call,
summarised at their band, glossed through the existing resolver, and turned into
one Courrier task. This table is where that lives, and the shape of the table is
mostly an argument about privacy.

Four properties the columns exist to hold
-----------------------------------------

* **Private.** An artefact belongs to exactly one learner, is never joined to a
  story table, and is never read by anything that generates the continuing
  story. ``test_intake.py::test_intake_never_writes_story_canon`` scans the
  service source to keep it that way.
* **Deletable.** ``DELETE /intake/{id}`` removes the row *and* the Courrier task
  derived from it. A derived mission carries the learner's own document inside
  its brief, so a deletion that left it standing would leave the document
  standing. The relationship is deliberately not a database cascade: the
  deletion path is one function with a test on it.
* **The image is never stored.** A photograph is bytes in one request and then
  gone: it is bounded, sent to the model call, and dropped. What survives is the
  *reading* — the text the model transcribed, the summary, the facts, the words.
  So a photograph that came back unreadable cannot be re-read from the row, and
  the learner is asked for another photo rather than shown an invented one.
* **Honest when nothing was read.** ``unread`` is a real state with no artefact
  in it. A provider that did not answer, answered unusably, or was handed an
  illegible photo leaves «non lu» plus a retry — never a plausible summary of a
  document nobody read.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

#: ``read``   — the model returned a usable reading; there is a summary and a task.
#: ``unread`` — nothing was read. No summary, no facts, no task, and a retry.
ARTEFACT_STATUSES: tuple[str, ...] = ("read", "unread")

#: How the document reached the app. ``image`` bytes are never persisted.
ARTEFACT_SOURCE_KINDS: tuple[str, ...] = ("text", "image")

#: What kind of document it turned out to be. Deliberately short: the type only
#: has to be right enough to pick the task and to label the card in French.
ARTEFACT_TYPES: tuple[str, ...] = (
    "menu",
    "lettre",
    "courriel",
    "affiche",
    "facture",
    "formulaire",
    "message",
    "autre",
)

#: The three things a Courrier task derived from a document can ask for.
ARTEFACT_TASK_KINDS: tuple[str, ...] = ("reply", "decide", "ask")

#: The provenance stamped on a vocabulary row this artefact created. WP-29 reads
#: it to treat a learner-sourced word as a *target* rather than an accident.
LEARNER_SOURCED_PROVENANCE = "learner_artefact"


class LearnerArtefact(Base):
    """One real document a learner brought in, and what was made of it."""

    __tablename__ = "learner_artefacts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="read", index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="intake-v1")

    #: ``text`` or ``image``. For ``image`` the bytes are gone by the time this
    #: row exists — only what the model read of them is kept.
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="text")

    #: The document's own words: what the learner pasted, or what the vision call
    #: transcribed from the photograph. Bounded on the way in.
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    #: type, title, summary at the learner's band, key facts, glossed unknowns.
    #: Empty on ``unread`` — an empty dict is the honest reading of nothing.
    artefact: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: The derived Courrier task before it became a mission: kind, the French
    #: instruction, the counterpart and the register.
    task: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: The Courrier mission the task became, graded by the existing corrector.
    #: ``SET NULL`` so deleting a mission never silently deletes the artefact —
    #: the deletion that matters runs the other way, and runs in one function.
    mission_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("real_world_missions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    #: Word ids queued as learner-sourced vocabulary from this artefact.
    queued_word_ids: Mapped[list[Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )

    #: Why there is no reading, when there is none. Logged, never shown.
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User")

    __table_args__ = (
        Index("ix_learner_artefacts_user_created", "user_id", "created_at"),
        Index("ix_learner_artefacts_user_status", "user_id", "status"),
    )


__all__ = [
    "ARTEFACT_SOURCE_KINDS",
    "ARTEFACT_STATUSES",
    "ARTEFACT_TASK_KINDS",
    "ARTEFACT_TYPES",
    "LEARNER_SOURCED_PROVENANCE",
    "LearnerArtefact",
]
