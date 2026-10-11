"""Refresh-token families, a grace window for rotation, and reset codes (WP-71).

Additive only. `refresh_tokens` gains `family_id`, `replaced_by_id` and
`rotated_at`, so a refresh that raced a rotation a few seconds late gets the same
successor instead of a 401, and a replay after the window can revoke the family.
Rows written before this have a null family; the service treats such a token as
the head of its own family, so nothing is backfilled.

`users` gains the hashed six-digit reset code and its attempt counter, plus a
non-unique index on lower(email) for the case-insensitive lookups. It is not
unique on purpose: legacy accounts that differ only by case must stay readable.

Revision ID: 2face6b8f71e
Revises: a1c4e7b90d33
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "2face6b8f71e"
down_revision = "a1c4e7b90d33"
branch_labels = None
depends_on = None

COLUMNS: tuple[tuple[str, str, sa.types.TypeEngine], ...] = (
    ("refresh_tokens", "family_id", postgresql.UUID(as_uuid=True)),
    ("refresh_tokens", "replaced_by_id", postgresql.UUID(as_uuid=True)),
    ("refresh_tokens", "rotated_at", sa.DateTime(timezone=True)),
    ("users", "password_reset_code_hash", sa.String(length=128)),
    ("users", "password_reset_code_attempts", sa.Integer()),
)

FAMILY_INDEX = "ix_refresh_tokens_family_id"
EMAIL_LOWER_INDEX = "ix_users_email_lower"


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    inspector = sa.inspect(op.get_bind())
    if table_name not in set(inspector.get_table_names()):
        return False
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    for table, name, column_type in COLUMNS:
        if not _has_column(table, name):
            op.add_column(table, sa.Column(name, column_type, nullable=True))
    if not _has_index("refresh_tokens", FAMILY_INDEX):
        op.create_index(FAMILY_INDEX, "refresh_tokens", ["family_id"])
    if not _has_index("users", EMAIL_LOWER_INDEX):
        op.create_index(EMAIL_LOWER_INDEX, "users", [sa.text("lower(email)")])


def downgrade() -> None:
    if _has_index("users", EMAIL_LOWER_INDEX):
        op.drop_index(EMAIL_LOWER_INDEX, table_name="users")
    if _has_index("refresh_tokens", FAMILY_INDEX):
        op.drop_index(FAMILY_INDEX, table_name="refresh_tokens")
    for table, name, _ in reversed(COLUMNS):
        if _has_column(table, name):
            op.drop_column(table, name)
