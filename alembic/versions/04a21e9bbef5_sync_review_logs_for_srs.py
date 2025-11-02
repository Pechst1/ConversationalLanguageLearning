"""sync review_logs for SRS

Revision ID: 04a21e9bbef5
Revises: 0001_initial_schema
Create Date: 2025-11-01 14:43:44.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "04a21e9bbef5"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extend vocabulary words with Anki specific metadata.
    with op.batch_alter_table("vocabulary_words") as batch:
        batch.add_column(sa.Column("german_translation", sa.Text(), nullable=True))
        batch.add_column(sa.Column("french_translation", sa.Text(), nullable=True))
        batch.add_column(sa.Column("direction", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("linked_word_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("deck_name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("note_id", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("card_id", sa.String(length=50), nullable=True))
        batch.add_column(
            sa.Column(
                "is_anki_card",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )

    # Extend user vocabulary progress with scheduler metadata.
    with op.batch_alter_table("user_vocabulary_progress") as batch:
        batch.add_column(
            sa.Column(
                "scheduler",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'fsrs'"),
            )
        )
        batch.add_column(
            sa.Column(
                "ease_factor",
                sa.Float(),
                nullable=False,
                server_default=sa.text("2.5"),
            )
        )
        batch.add_column(
            sa.Column(
                "interval_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column(
                "phase",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'new'"),
            )
        )
        batch.add_column(
            sa.Column(
                "step_index",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("deck_name", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("note_id", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("card_id", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("raw_history", sa.Text(), nullable=True))

    op.create_index(
        "ix_user_vocabulary_progress_due_at",
        "user_vocabulary_progress",
        ["due_at"],
        unique=False,
    )

    # Extend review logs with Anki scheduler metadata.
    with op.batch_alter_table("review_logs") as batch:
        batch.add_column(
            sa.Column(
                "scheduler_type",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'fsrs'"),
            )
        )
        batch.add_column(sa.Column("ease_factor_before", sa.Float(), nullable=True))
        batch.add_column(sa.Column("ease_factor_after", sa.Float(), nullable=True))
        batch.add_column(sa.Column("interval_before", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("interval_after", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("review_logs") as batch:
        batch.drop_column("interval_after")
        batch.drop_column("interval_before")
        batch.drop_column("ease_factor_after")
        batch.drop_column("ease_factor_before")
        batch.drop_column("scheduler_type")

    op.drop_index(
        "ix_user_vocabulary_progress_due_at",
        table_name="user_vocabulary_progress",
    )

    with op.batch_alter_table("user_vocabulary_progress") as batch:
        batch.drop_column("raw_history")
        batch.drop_column("card_id")
        batch.drop_column("note_id")
        batch.drop_column("deck_name")
        batch.drop_column("due_at")
        batch.drop_column("step_index")
        batch.drop_column("phase")
        batch.drop_column("interval_days")
        batch.drop_column("ease_factor")
        batch.drop_column("scheduler")

    with op.batch_alter_table("vocabulary_words") as batch:
        batch.drop_column("is_anki_card")
        batch.drop_column("card_id")
        batch.drop_column("note_id")
        batch.drop_column("deck_name")
        batch.drop_column("linked_word_id")
        batch.drop_column("direction")
        batch.drop_column("french_translation")
        batch.drop_column("german_translation")
