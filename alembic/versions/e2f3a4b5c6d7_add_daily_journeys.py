"""Add the Atelier V2 daily journey tables.

Additive only: three new tables, no data migration, no change to any existing
row, SRS due date, CEFR level, completed session, collectible or serial index.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None

_OCCUPYING = sa.text("status IN ('preparing', 'active', 'paused')")


def upgrade() -> None:
    op.create_table(
        "daily_journeys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("contract_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_version", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("level_band", sa.String(length=8), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="preparing"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("budget_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column(
            "estimated_active_seconds", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("serial_thread_id", sa.String(length=64), nullable=True),
        sa.Column("serial_episode_id", sa.String(length=64), nullable=True),
        sa.Column("learning_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "scenario_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("recap_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "plan_selection",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("generation_claim_id", sa.String(length=64), nullable=True),
        sa.Column("generation_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unavailable_reason", sa.String(length=120), nullable=True),
        sa.Column(
            "unavailable_retry_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "unavailable_retry_after_seconds",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["learning_session_id"], ["learning_sessions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="uq_daily_journeys_user_date"),
    )
    op.create_index("ix_daily_journeys_user_id", "daily_journeys", ["user_id"])
    op.create_index(
        "ix_daily_journeys_user_status", "daily_journeys", ["user_id", "status"]
    )
    # At most one preparing/active/paused journey per learner.
    op.create_index(
        "uq_daily_journeys_one_open_per_user",
        "daily_journeys",
        ["user_id"],
        unique=True,
        postgresql_where=_OCCUPYING,
        sqlite_where=_OCCUPYING,
    )

    op.create_table(
        "daily_journey_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("estimated_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("target_kind", sa.String(length=20), nullable=True),
        sa.Column("target_id", sa.String(length=180), nullable=True),
        sa.Column(
            "public_prompt",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "private_task",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "assistance_used",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("evidence_ref", sa.String(length=180), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("turns_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["journey_id"], ["daily_journeys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journey_id", "ordinal", name="uq_daily_journey_steps_journey_ordinal"
        ),
    )
    op.create_index(
        "ix_daily_journey_steps_journey_id", "daily_journey_steps", ["journey_id"]
    )

    op.create_table(
        "daily_journey_mutations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mutation_id", sa.String(length=80), nullable=False),
        sa.Column("journey_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="processing"
        ),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column(
            "response_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "evidence_refs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["journey_id"], ["daily_journeys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "scope",
            "mutation_id",
            name="uq_daily_journey_mutations_user_scope_key",
        ),
    )
    op.create_index(
        "ix_daily_journey_mutations_user_id", "daily_journey_mutations", ["user_id"]
    )
    op.create_index(
        "ix_daily_journey_mutations_journey_id",
        "daily_journey_mutations",
        ["journey_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_journey_mutations_journey_id", table_name="daily_journey_mutations"
    )
    op.drop_index(
        "ix_daily_journey_mutations_user_id", table_name="daily_journey_mutations"
    )
    op.drop_table("daily_journey_mutations")
    op.drop_index("ix_daily_journey_steps_journey_id", table_name="daily_journey_steps")
    op.drop_table("daily_journey_steps")
    op.drop_index("uq_daily_journeys_one_open_per_user", table_name="daily_journeys")
    op.drop_index("ix_daily_journeys_user_status", table_name="daily_journeys")
    op.drop_index("ix_daily_journeys_user_id", table_name="daily_journeys")
    op.drop_table("daily_journeys")
