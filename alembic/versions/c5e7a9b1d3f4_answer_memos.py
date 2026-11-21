"""Package V stage 4: the memo of judged answers (see app/db/models/answer_memo.py).

Revision ID: c5e7a9b1d3f4
Revises: b4d6f8a0c2e3
Create Date: 2026-11-11
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c5e7a9b1d3f4"
down_revision = "b4d6f8a0c2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_memos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("surface", sa.String(32), nullable=False),
        sa.Column("item_fingerprint", sa.String(64), nullable=False),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("answer_norm", sa.Text(), nullable=False),
        sa.Column("item_label", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("edits", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", sa.String(16), nullable=False, server_default="candidate"),
        sa.Column("confirmation", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("backing", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("settled", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_answer_memos_lookup", "answer_memos", ["surface", "item_fingerprint", "answer_hash", "state"]
    )
    op.create_index("ix_answer_memos_state", "answer_memos", ["state", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_answer_memos_state", table_name="answer_memos")
    op.drop_index("ix_answer_memos_lookup", table_name="answer_memos")
    op.drop_table("answer_memos")
