"""WP-31 — the learner's own upcoming situation, rehearsed once.

A rehearsal is the one thing in this app that is **not** fiction. The learner
declares something that is going to happen to them ("call the landlord about the
heating, Tuesday"), rehearses it, does it, and says how it went.

``docs/implementation/atelier-v2/CONTINUOUS-STORY.md`` draws the line this table
exists to keep: *distinguish fictional roleplay facts from real learner
biography*. So the declaration, the structured brief, the rehearsal scene and
the debrief all live **here**, in a table of their own, and nothing in this row
is ever written into ``SerialThread.state``, an episode, or any other store the
continuing story reads. A landlord the learner invented for practice must never
turn up in Romy's Paris.

Three shapes drive the columns:

* **Resumable.** The rehearsal is a row, not a request: a learner who closes the
  app comes back to the same scene with the same graded turns.
* **Idempotent.** Generation and grading cost money. Turns carry their index, so
  a replayed submit returns the stored grading and pays nothing.
* **Honest under failure.** ``not_prepared`` is a real state with no scene in it.
  A rehearsal the provider could not prepare says «non préparée» and offers a
  retry; it never shows an invented scene wearing the learner's real situation.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

#: ``declared``     — the situation is stored; no scene yet.
#: ``ready``        — a validated scene is waiting to be rehearsed.
#: ``not_prepared`` — the provider did not answer, or answered unusably. No scene.
#: ``rehearsing``   — at least one turn is graded, the bound is not spent.
#: ``rehearsed``    — the turns are spent or the objective was reached.
#: ``debriefed``    — the learner said how the real thing went. Terminal.
#: ``abandoned``    — the learner dropped it. Terminal, and frees nothing: a
#:                    started rehearsal still counts against the weekly cap,
#:                    because the generation was already paid for.
REHEARSAL_STATUSES = (
    "declared",
    "ready",
    "not_prepared",
    "rehearsing",
    "rehearsed",
    "debriefed",
    "abandoned",
)

#: What the learner reports after the real event. The success metric of WP-31.
REHEARSAL_OUTCOMES = ("done", "partly", "not_yet")


class Rehearsal(Base):
    """One declared real situation, its rehearsal, and its debrief."""

    __tablename__ = "rehearsals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="declared", index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="rehearsal-v1")

    #: The learner's own words, in whatever language they used. Kept verbatim so
    #: the structured brief can always be checked against what was actually said.
    declaration: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    #: goal / counterpart / register / date / facts, plus how it was structured.
    brief: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: The generated scene: setup, opening line, private rubric points, the
    #: phrases held back until asked for, and the attainable endings.
    scene: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: One entry per graded turn: index, learner text, modality, assistance,
    #: outcome, evidence kind, the counterpart's reply and any correction.
    turns: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )

    #: ``done`` / ``partly`` / ``not_yet`` plus the corrected free line.
    debrief: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: Denormalized from ``debrief`` so the digest reads one indexed column.
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    #: When the real thing happens, when the learner named a date the structurer
    #: could resolve. ``None`` is normal and never guessed at: it only means the
    #: debrief is offered as soon as the rehearsal is done.
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    #: Why there is no scene, when there is none. Shown to nobody; read in logs.
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    rehearsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    debriefed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    __table_args__ = (
        Index("ix_rehearsals_user_status", "user_id", "status"),
        Index("ix_rehearsals_user_created", "user_id", "created_at"),
    )


__all__ = ["REHEARSAL_OUTCOMES", "REHEARSAL_STATUSES", "Rehearsal"]
