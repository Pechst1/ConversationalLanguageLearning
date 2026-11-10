"""Package V stage 2: the verdict ledger, and the moment levels start reading it.

``verdict_records`` is append-only (see app/db/models/verdict_record.py). The second row
of ``verdict_cutover`` (id 2, «ledger») is stamped at upgrade time: rows stored after it
count by their ledger record, not by re-reading the row.

Revision ID: a3c5e7f9b1d2
Revises: f2b4d6e8a0c1
Create Date: 2026-11-10
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a3c5e7f9b1d2"
down_revision = "f2b4d6e8a0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verdict_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("verdict", postgresql.JSONB(), nullable=False),
        sa.Column("counts", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("judge_version", sa.String(32), nullable=False),
        sa.Column(
            "supersedes_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("verdict_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("superseded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_verdict_records_user_id", "verdict_records", ["user_id"])
    op.create_index("ix_verdict_records_subject", "verdict_records", ["subject_type", "subject_id"])
    op.create_index(
        "ix_verdict_records_live", "verdict_records", ["subject_type", "subject_id", "superseded_by_id"]
    )
    op.execute(
        sa.text(
            "INSERT INTO verdict_cutover (id, at, note) "
            "VALUES (2, CURRENT_TIMESTAMP, 'verdict ledger (package V stage 2)')"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM verdict_cutover WHERE id = 2"))
    op.drop_index("ix_verdict_records_live", table_name="verdict_records")
    op.drop_index("ix_verdict_records_subject", table_name="verdict_records")
    op.drop_index("ix_verdict_records_user_id", table_name="verdict_records")
    op.drop_table("verdict_records")
