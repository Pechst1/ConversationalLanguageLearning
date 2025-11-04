"""add anki_import_records and unique index on vocabulary note/card

Revision ID: a1b2c3d4e5f6
Revises: 9b7f2c4d6e01
Create Date: 2025-11-04 18:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9b7f2c4d6e01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anki_import_records",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("deck_name", sa.String(length=255), nullable=True),
        sa.Column("preserve_scheduling", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("csv_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
    )
    op.create_index("ix_anki_import_records_user_id", "anki_import_records", ["user_id"], unique=False)

    # Optional uniqueness to avoid accidental duplicates when note/card ids are present
    try:
        op.create_index(
            "uq_vocab_note_card",
            "vocabulary_words",
            ["note_id", "card_id"],
            unique=True,
            postgresql_where=sa.text("note_id IS NOT NULL AND card_id IS NOT NULL"),
        )
    except Exception:
        # If the index already exists (manual runs), ignore
        pass


def downgrade() -> None:
    try:
        op.drop_index("uq_vocab_note_card", table_name="vocabulary_words")
    except Exception:
        pass
    op.drop_index("ix_anki_import_records_user_id", table_name="anki_import_records")
    op.drop_table("anki_import_records")

