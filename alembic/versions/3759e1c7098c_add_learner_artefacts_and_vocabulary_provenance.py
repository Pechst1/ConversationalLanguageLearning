"""Add learner_artefacts and vocabulary provenance (WP-34).

Additive only: one new table plus two nullable columns on an existing one. Both
halves belong to one package and one deploy — a `learner_artefacts` row is only
useful if the vocabulary it queues can be stamped as learner-sourced — so they
travel in a single revision rather than two that can land apart.

A deploy that runs this and then rolls the code back leaves an unread table and
two always-null columns behind, both inert.

The provenance columns are deliberately *nullable with no default*. Null means
"the app scheduled this card", which is what every existing row is, and
backfilling them to a sentinel would assert a provenance for millions of rows
nobody recorded one for.

Revision ID: 3759e1c7098c
Revises: 79e0beb6c84b
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "3759e1c7098c"
down_revision = "79e0beb6c84b"
branch_labels = None
depends_on = None

TABLE = "learner_artefacts"
PROGRESS_TABLE = "user_vocabulary_progress"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return table_name in set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _json_type() -> sa.types.TypeEngine:
    return postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")


def _uuid_type() -> sa.types.TypeEngine:
    return postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def upgrade() -> None:
    if not _has_table(TABLE):
        op.create_table(
            TABLE,
            sa.Column("id", _uuid_type(), primary_key=True, nullable=False),
            sa.Column("user_id", _uuid_type(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="read"),
            sa.Column("version", sa.String(length=32), nullable=False, server_default="intake-v1"),
            sa.Column(
                "source_kind", sa.String(length=16), nullable=False, server_default="text"
            ),
            sa.Column("source_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("artefact", _json_type(), nullable=False, server_default="{}"),
            sa.Column("task", _json_type(), nullable=False, server_default="{}"),
            sa.Column("mission_id", _uuid_type(), nullable=True),
            sa.Column("queued_word_ids", _json_type(), nullable=False, server_default="[]"),
            sa.Column("failure_reason", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            # SET NULL, not CASCADE: deleting a mission must never take the
            # learner's document with it. The deletion that matters runs the
            # other way, in `IntakeService.delete`, where it has a test on it.
            sa.ForeignKeyConstraint(
                ["mission_id"], ["real_world_missions.id"], ondelete="SET NULL"
            ),
        )
        op.create_index(f"ix_{TABLE}_user_id", TABLE, ["user_id"])
        op.create_index(f"ix_{TABLE}_status", TABLE, ["status"])
        op.create_index(f"ix_{TABLE}_mission_id", TABLE, ["mission_id"])
        op.create_index(f"ix_{TABLE}_user_created", TABLE, ["user_id", "created_at"])
        op.create_index(f"ix_{TABLE}_user_status", TABLE, ["user_id", "status"])

    if not _has_column(PROGRESS_TABLE, "provenance"):
        op.add_column(
            PROGRESS_TABLE, sa.Column("provenance", sa.String(length=32), nullable=True)
        )
        op.create_index(
            f"ix_{PROGRESS_TABLE}_provenance", PROGRESS_TABLE, ["provenance"]
        )
    if not _has_column(PROGRESS_TABLE, "provenance_ref"):
        op.add_column(
            PROGRESS_TABLE, sa.Column("provenance_ref", sa.String(length=64), nullable=True)
        )
        op.create_index(
            f"ix_{PROGRESS_TABLE}_provenance_ref", PROGRESS_TABLE, ["provenance_ref"]
        )


def downgrade() -> None:
    if _has_column(PROGRESS_TABLE, "provenance_ref"):
        op.drop_index(f"ix_{PROGRESS_TABLE}_provenance_ref", table_name=PROGRESS_TABLE)
        op.drop_column(PROGRESS_TABLE, "provenance_ref")
    if _has_column(PROGRESS_TABLE, "provenance"):
        op.drop_index(f"ix_{PROGRESS_TABLE}_provenance", table_name=PROGRESS_TABLE)
        op.drop_column(PROGRESS_TABLE, "provenance")
    if _has_table(TABLE):
        op.drop_index(f"ix_{TABLE}_user_status", table_name=TABLE)
        op.drop_index(f"ix_{TABLE}_user_created", table_name=TABLE)
        op.drop_index(f"ix_{TABLE}_mission_id", table_name=TABLE)
        op.drop_index(f"ix_{TABLE}_status", table_name=TABLE)
        op.drop_index(f"ix_{TABLE}_user_id", table_name=TABLE)
        op.drop_table(TABLE)
