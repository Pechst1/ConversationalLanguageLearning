"""Add the journal_entries table (WP-30, «Le journal de bord»).

Additive only: one new table, no column on any existing one. A deploy that runs
this and then rolls the code back leaves an unread table behind, which is inert.

Revision ID: c7d8e9f0a1b2
Revises: e48fd9624811

Chained off the newest **committed** revision so that committed history has one
head. Several innovation packages landed tables against this checkout the same
day; anything still untracked when this was written is that package's to chain
or merge, and WP-30-JOURNAL.md §6 carries the merge revision if one is needed.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c7d8e9f0a1b2"
down_revision = "e48fd9624811"
branch_labels = None
depends_on = None

TABLE = "journal_entries"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    if _has_table(TABLE):
        return
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SET NULL, not CASCADE: the learner's own writing is not a detail of
        # the journey row that prompted it.
        sa.Column(
            "journey_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("daily_journeys.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="offered"),
        sa.Column("version", sa.String(length=32), nullable=False, server_default="journal-v1"),
        sa.Column("scene_date", sa.Date(), nullable=False),
        sa.Column("offered_on", sa.Date(), nullable=False),
        sa.Column("followup_due_on", sa.Date(), nullable=False),
        sa.Column("cue", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("scene_facts", _json_type(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("scene_reveal", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("entry_text", sa.Text(), nullable=True),
        sa.Column("assessment_status", sa.String(length=16), nullable=True),
        sa.Column("correction", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("content_recall", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reaction_fr", sa.Text(), nullable=True),
        sa.Column("vocabulary_credit", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("errata_ids", _json_type(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("followup_prompt_fr", sa.Text(), nullable=True),
        sa.Column("followup_text", sa.Text(), nullable=True),
        sa.Column("followup_signal", sa.String(length=24), nullable=True),
        sa.Column("followup_recall", _json_type(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("followup_answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recall_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "journey_id", name="uq_journal_entries_user_journey"),
    )
    op.create_index("ix_journal_entries_user_id", TABLE, ["user_id"])
    op.create_index("ix_journal_entries_journey_id", TABLE, ["journey_id"])
    op.create_index("ix_journal_entries_status", TABLE, ["status"])
    op.create_index("ix_journal_entries_offered_on", TABLE, ["offered_on"])
    op.create_index("ix_journal_entries_user_status", TABLE, ["user_id", "status"])
    op.create_index("ix_journal_entries_user_offered", TABLE, ["user_id", "offered_on"])
    op.create_index("ix_journal_entries_user_followup", TABLE, ["user_id", "followup_due_on"])


def downgrade() -> None:
    if not _has_table(TABLE):
        return
    op.drop_index("ix_journal_entries_user_followup", table_name=TABLE)
    op.drop_index("ix_journal_entries_user_offered", table_name=TABLE)
    op.drop_index("ix_journal_entries_user_status", table_name=TABLE)
    op.drop_index("ix_journal_entries_offered_on", table_name=TABLE)
    op.drop_index("ix_journal_entries_status", table_name=TABLE)
    op.drop_index("ix_journal_entries_journey_id", table_name=TABLE)
    op.drop_index("ix_journal_entries_user_id", table_name=TABLE)
    op.drop_table(TABLE)
