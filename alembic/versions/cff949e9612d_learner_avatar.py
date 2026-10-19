"""The learner's drawn character (avatar).

``users.avatar``: the part ids and colour ids the learner chose in the avatar
editor, as a small JSON object (``app.services.avatar`` validates its shape;
some items are unlocked by achievements). Null until the learner makes one.
Only adds a nullable column.

Revision ID: cff949e9612d
Revises: 504cc77963e8
Create Date: 2026-10-18
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "cff949e9612d"
down_revision = "504cc77963e8"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_avatar() -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    return "avatar" in {column["name"] for column in inspector.get_columns("users")}


def upgrade() -> None:
    if not _has_avatar():
        json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
        op.add_column("users", sa.Column("avatar", json_type, nullable=True))


def downgrade() -> None:
    if _offline_mode() or _has_avatar():
        op.drop_column("users", "avatar")
