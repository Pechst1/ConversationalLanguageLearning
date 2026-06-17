"""Add user settings columns and refresh token sessions."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "d7e8f9a0b1c2"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _table_columns(table_name: str) -> set[str]:
    if _offline_mode():
        return set()
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _add_column_if_missing(table_name: str, existing_columns: set[str], column: sa.Column) -> None:
    if column.name in existing_columns:
        return
    op.add_column(table_name, column)
    existing_columns.add(column.name)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if _offline_mode():
        op.create_index(index_name, table_name, columns, unique=unique)
        return
    inspector = sa.inspect(op.get_bind())
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    user_columns = _table_columns("users")
    for column in [
        sa.Column("grammar_streak_days", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("grammar_last_review_date", sa.Date(), nullable=True),
        sa.Column("grammar_longest_streak", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("daily_goal_xp", sa.Integer(), server_default=sa.text("50"), nullable=False),
        sa.Column("new_words_per_day", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("default_vocab_direction", sa.String(length=20), server_default=sa.text("'fr_to_de'"), nullable=False),
        sa.Column("practice_reminders", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("reminder_time", sa.String(length=10), server_default=sa.text("'09:00'"), nullable=False),
        sa.Column("streak_notifications", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("weekly_email_summary", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("achievement_notifications", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("theme", sa.String(length=20), server_default=sa.text("'system'"), nullable=False),
        sa.Column("font_size", sa.String(length=20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("voice_input_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("text_to_speech_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("tts_speed", sa.String(length=10), server_default=sa.text("'1.0'"), nullable=False),
        sa.Column("auto_play_pronunciation", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("interests", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column("grammar_correction_level", sa.String(length=20), server_default=sa.text("'moderate'"), nullable=False),
        sa.Column("show_grammar_explanations", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'user'"), nullable=False),
        sa.Column("auth_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_email", sa.String(length=255), nullable=True),
        sa.Column("pending_email_token_hash", sa.String(length=255), nullable=True),
        sa.Column("pending_email_requested_at", sa.DateTime(timezone=True), nullable=True),
    ]:
        _add_column_if_missing("users", user_columns, column)

    inspector = None if _offline_mode() else sa.inspect(op.get_bind())
    if _offline_mode() or not inspector.has_table("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )
    _create_index_if_missing("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    _create_index_if_missing("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    _create_index_if_missing("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_column("users", "pending_email_requested_at")
    op.drop_column("users", "pending_email_token_hash")
    op.drop_column("users", "pending_email")
    op.drop_column("users", "email_updated_at")
    op.drop_column("users", "password_updated_at")
    op.drop_column("users", "auth_version")
    op.drop_column("users", "role")
    op.drop_column("users", "show_grammar_explanations")
    op.drop_column("users", "grammar_correction_level")
    op.drop_column("users", "interests")
    op.drop_column("users", "auto_play_pronunciation")
    op.drop_column("users", "tts_speed")
    op.drop_column("users", "text_to_speech_enabled")
    op.drop_column("users", "voice_input_enabled")
    op.drop_column("users", "font_size")
    op.drop_column("users", "theme")
    op.drop_column("users", "achievement_notifications")
    op.drop_column("users", "weekly_email_summary")
    op.drop_column("users", "streak_notifications")
    op.drop_column("users", "reminder_time")
    op.drop_column("users", "practice_reminders")
    op.drop_column("users", "default_vocab_direction")
    op.drop_column("users", "new_words_per_day")
    op.drop_column("users", "daily_goal_xp")
    op.drop_column("users", "grammar_longest_streak")
    op.drop_column("users", "grammar_last_review_date")
    op.drop_column("users", "grammar_streak_days")
