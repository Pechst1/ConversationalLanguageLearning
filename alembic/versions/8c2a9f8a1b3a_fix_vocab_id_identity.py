"""ensure vocabulary_words.id uses a proper sequence

Revision ID: 8c2a9f8a1b3a
Revises: 4f0d5a5f2dc0
Create Date: 2025-11-04 16:20:00.000000

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "8c2a9f8a1b3a"
down_revision = "4f0d5a5f2dc0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create a sequence for vocabulary_words.id if absent and attach as default
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind = 'S' AND c.relname = 'vocabulary_words_id_seq'
            ) THEN
                CREATE SEQUENCE vocabulary_words_id_seq START 1; 
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        ALTER SEQUENCE vocabulary_words_id_seq OWNED BY vocabulary_words.id;
        ALTER TABLE vocabulary_words ALTER COLUMN id SET DEFAULT nextval('vocabulary_words_id_seq');
        """
    )
    # Align sequence to max(id)+1 to avoid duplicate key violations
    op.execute(
        """
        SELECT setval('vocabulary_words_id_seq', COALESCE((SELECT MAX(id) + 1 FROM vocabulary_words), 1), false);
        """
    )


def downgrade() -> None:
    # Leave the sequence in place but detach default to avoid breaking inserts on downgrade
    op.execute("ALTER TABLE vocabulary_words ALTER COLUMN id DROP DEFAULT;")
    # Do not drop the sequence to avoid surprises if data relies on it

