"""Durable state for the Atelier V2 daily journey (WP-02).

Three tables, described in ``docs/implementation/atelier-v2/CONTRACTS.md`` §2:

* :class:`DailyJourney` — one short scenario per learner-local date.
* :class:`DailyJourneyStep` — the persisted plan. ``private_task`` is evaluator
  material and is **never** serialized to a client.
* :class:`DailyJourneyMutation` — an idempotency receipt, not a second copy of
  the learner transcript.

``app/services/daily_journey.py`` is the only writer of these rows.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.base import Base

#: Statuses that make a journey "the one the learner is currently in".
#: At most one of these may exist per user (partial unique index below plus a
#: service-level guard, because SQLite tests alone are not sufficient proof).
OCCUPYING_STATUS_VALUES: tuple[str, ...] = ("preparing", "active", "paused")

_OCCUPYING_SQL = "status IN ('preparing', 'active', 'paused')"


class DailyJourney(Base):
    """One five-minute scenario for one learner on one learner-local date."""

    __tablename__ = "daily_journeys"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The learner's own calendar day, plus the IANA zone it was computed in.
    # ``users`` has no timezone column, so the journey stores its own snapshot.
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    contract_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Pinned content identity. Both are passed back to WP-03 on every reopen so
    #: neither a content bump nor a learner level change can swap the variant.
    content_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    level_band: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="preparing")

    #: Bumped on every accepted mutation; clients send it back as expected_revision.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_step_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    budget_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    estimated_active_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    serial_thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serial_episode_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    learning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("learning_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    #: Public ScenarioDescriptor exactly as it is served; no private content.
    scenario_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    recap_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    #: WP-04's selection record. ``selected_target_ids`` and
    #: ``omitted_candidate_ids`` hold composite ``"{kind}:{id}"`` identities and
    #: are stored verbatim — a vocabulary row and a grammar concept can share a
    #: primary key, so splitting them would merge two different targets.
    plan_selection: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )

    #: Durable claim so provider work happens outside a long-held row lock and a
    #: crashed worker is recoverable through ``POST /retry``.
    generation_claim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    generation_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    unavailable_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: WP-03's deterministic data problems are not retryable; a transient claim
    #: failure is. The public ``retry`` hint must never promise a retry that
    #: cannot possibly help.
    unavailable_retry_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    unavailable_retry_after_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    steps: Mapped[list[DailyJourneyStep]] = relationship(
        "DailyJourneyStep",
        back_populates="journey",
        cascade="all, delete-orphan",
        order_by="DailyJourneyStep.ordinal",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="uq_daily_journeys_user_date"),
        Index("ix_daily_journeys_user_status", "user_id", "status"),
        # One preparing/active/paused journey per learner. PostgreSQL is the
        # production enforcement; the identical SQLite partial index keeps the
        # invariant honest in tests. The service additionally guards it under a
        # locked read (see app/services/daily_journey.py).
        Index(
            "uq_daily_journeys_one_open_per_user",
            "user_id",
            unique=True,
            postgresql_where=text(_OCCUPYING_SQL),
            sqlite_where=text(_OCCUPYING_SQL),
        ),
    )


class DailyJourneyStep(Base):
    """One planned step. ``public_prompt`` is renderer-safe, ``private_task`` is not."""

    __tablename__ = "daily_journey_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    journey_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("daily_journeys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    estimated_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    target_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(180), nullable=True)

    public_prompt: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: Rubric, accepted answers, correct option id, solution text. Never public.
    private_task: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict, nullable=False
    )
    #: Server-recorded assistance levels, in the order they were revealed.
    assistance_used: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )
    #: Canonical learning-record reference produced by WP-05, e.g.
    #: ``session_learning_moment:<uuid>``.
    evidence_ref: Mapped[str | None] = mapped_column(String(180), nullable=True)

    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    turns_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    journey: Mapped[DailyJourney] = relationship("DailyJourney", back_populates="steps")

    __table_args__ = (
        UniqueConstraint(
            "journey_id", "ordinal", name="uq_daily_journey_steps_journey_ordinal"
        ),
    )


class DailyJourneyMutation(Base):
    """Idempotency receipt for one client mutation key.

    Keeps only what is needed to replay the operation: the digest of the request
    that produced it and the public response snapshot. Canonical learner content
    lives in the existing session/attempt records under their privacy rules.
    """

    __tablename__ = "daily_journey_mutations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Client-supplied idempotency key.
    mutation_id: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Null for creation: there is no journey yet when the key is first claimed.
    journey_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("daily_journeys.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Route/action scope, e.g. ``create``, ``attempt``, ``advance``.
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    #: sha256 of the canonical request body (without the mutation key itself).
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="processing"
    )
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), nullable=True
    )
    evidence_refs: Mapped[list[str]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "scope",
            "mutation_id",
            name="uq_daily_journey_mutations_user_scope_key",
        ),
    )
