"""WP-S3 (La Forge): the forge's rung and the test-out stamp on grammar progress.

Two nullable columns on `user_grammar_progress`, read and written by
`app.services.forge`:

* `forge_rung` — where the rule stands on the forge's staircase
  (0 recognise, 1 discriminate, 2 build, 3 transform, 4 produce, 5 free use);
  NULL until the rule was first forged or tested out;
* `tested_out_at` — when the learner passed the rule's «Épreuve de la règle»
  (the rule is held from then on; `held_at` is written at the same time).

Additive, no backfill.

Revision ID: c3e5a7b9d1f4
Revises: b7d9f1a3c5e8
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "c3e5a7b9d1f4"
down_revision = "b7d9f1a3c5e8"
branch_labels = None
depends_on = None

TABLE = "user_grammar_progress"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _existing() -> set[str]:
    if _offline_mode():
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(TABLE)}


def upgrade() -> None:
    existing = _existing()
    if "forge_rung" not in existing:
        op.add_column(TABLE, sa.Column("forge_rung", sa.Integer(), nullable=True))
    if "tested_out_at" not in existing:
        op.add_column(TABLE, sa.Column("tested_out_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = _existing()
    for name in ("tested_out_at", "forge_rung"):
        if name in existing or _offline_mode():
            op.drop_column(TABLE, name)
