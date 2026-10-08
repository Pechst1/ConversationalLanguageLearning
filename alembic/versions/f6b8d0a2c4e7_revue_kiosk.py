"""WP-119 phase 3 «Le kiosque»: the week's editorial dossiers, and a period wide enough for a day.

* ``revue_dossiers``: what the intake built (one row per dossier): the dossier JSON as
  ``weekly.load_week`` reads it, the hash of each source's full text (the text itself is
  never stored, §4.1/§12.3), the checks it passed and the builder's version.
* ``revue_sessions.week`` and ``revue_vignettes.week`` widen from 8 to 10 characters. The
  column keeps its name but holds the Papier's *period*: an ISO week («2026-W40») under
  ``REVUE_CADENCE=weekly``, an ISO date («2026-10-03») under ``daily`` (§12.2). The partial
  unique index (one active Papier per learner per period) is unchanged: it already keys
  on that column.

Revision ID: f6b8d0a2c4e7
Revises: d4f6a8c0e2b4
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f6b8d0a2c4e7"
down_revision = "d4f6a8c0e2b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revue_dossiers",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("week", sa.String(8), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("topic", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_hashes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("builder_version", sa.String(40), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_revue_dossiers_week", "revue_dossiers", ["week"])
    op.create_index("ix_revue_dossiers_period", "revue_dossiers", ["period"])
    with op.batch_alter_table("revue_sessions") as batch:
        batch.alter_column("week", existing_type=sa.String(8), type_=sa.String(10), existing_nullable=False)
    with op.batch_alter_table("revue_vignettes") as batch:
        batch.alter_column("week", existing_type=sa.String(8), type_=sa.String(10), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("revue_vignettes") as batch:
        batch.alter_column("week", existing_type=sa.String(10), type_=sa.String(8), existing_nullable=False)
    with op.batch_alter_table("revue_sessions") as batch:
        batch.alter_column("week", existing_type=sa.String(10), type_=sa.String(8), existing_nullable=False)
    op.drop_index("ix_revue_dossiers_period", table_name="revue_dossiers")
    op.drop_index("ix_revue_dossiers_week", table_name="revue_dossiers")
    op.drop_table("revue_dossiers")
