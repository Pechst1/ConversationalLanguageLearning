"""Create core application tables"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("native_language", sa.String(length=10), server_default=sa.text("'en'"), nullable=False),
        sa.Column("target_language", sa.String(length=10), server_default=sa.text("'fr'"), nullable=False),
        sa.Column("proficiency_level", sa.String(length=20), server_default=sa.text("'beginner'"), nullable=False),
        sa.Column("total_xp", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("level", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("current_streak", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("longest_streak", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_activity_date", sa.Date(), nullable=True),
        sa.Column("daily_goal_minutes", sa.Integer(), server_default=sa.text("15"), nullable=False),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("preferred_session_time", sa.Time(timezone=False), nullable=True),
        sa.Column("subscription_tier", sa.String(length=20), server_default=sa.text("'free'"), nullable=False),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_last_activity_date", "users", ["last_activity_date"], unique=False)

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("achievement_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url", sa.String(length=255), nullable=True),
        sa.Column("xp_reward", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("tier", sa.String(length=20), server_default=sa.text("'bronze'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
    )
    op.create_unique_constraint("uq_achievements_achievement_key", "achievements", ["achievement_key"])

    op.create_table(
        "vocabulary_words",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("normalized_word", sa.String(length=255), nullable=False),
        sa.Column("part_of_speech", sa.String(length=50), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("frequency_rank", sa.Integer(), nullable=False),
        sa.Column("english_translation", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("example_sentence", sa.Text(), nullable=True),
        sa.Column("example_translation", sa.Text(), nullable=True),
        sa.Column("usage_notes", sa.Text(), nullable=True),
        sa.Column("difficulty_level", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("topic_tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
    )
    op.create_index("ix_vocabulary_words_language", "vocabulary_words", ["language"], unique=False)
    op.create_index("ix_vocabulary_words_normalized_word", "vocabulary_words", ["normalized_word"], unique=False)
    op.create_index("ix_vocabulary_words_frequency_rank", "vocabulary_words", ["frequency_rank"], unique=False)

    op.create_table(
        "learning_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("conversation_style", sa.String(length=50), nullable=True),
        sa.Column("difficulty_preference", sa.String(length=20), nullable=True),
        sa.Column("words_practiced", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("new_words_introduced", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("words_reviewed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("correct_responses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("incorrect_responses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("accuracy_rate", sa.Float(), nullable=True),
        sa.Column("xp_earned", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("level_before", sa.Integer(), nullable=True),
        sa.Column("level_after", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'in_progress'"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_learning_sessions_user_id", "learning_sessions", ["user_id"], unique=False)

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_words_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("words_learning", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("words_mastered", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("new_words_today", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("reviews_completed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("average_accuracy", sa.Float(), nullable=True),
        sa.Column("average_response_time_ms", sa.Integer(), nullable=True),
        sa.Column("streak_length", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Date(), server_default=sa.text("current_date"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_analytics_snapshots_user_id", "analytics_snapshots", ["user_id"], unique=False)
    op.create_index("ix_analytics_snapshots_snapshot_date", "analytics_snapshots", ["snapshot_date"], unique=False)

    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("progress", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"], unique=False)
    op.create_index("ix_user_achievements_achievement_id", "user_achievements", ["achievement_id"], unique=False)

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("target_words", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("errors_detected", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("words_used", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("suggested_words_used", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("xp_earned", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("generation_prompt", sa.String(length=255), nullable=True),
        sa.Column("llm_model", sa.String(length=50), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversation_messages_session_id", "conversation_messages", ["session_id"], unique=False)

    op.create_table(
        "user_vocabulary_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("stability", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("difficulty", sa.Float(), server_default=sa.text("5"), nullable=False),
        sa.Column("elapsed_days", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("scheduled_days", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("reps", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("lapses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("state", sa.String(length=20), server_default=sa.text("'new'"), nullable=False),
        sa.Column("proficiency_score", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("correct_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("hint_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("times_seen", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("times_used_correctly", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("times_used_incorrectly", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_types", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("first_seen_date", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("mastered_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["vocabulary_words.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_vocabulary_progress_user_id", "user_vocabulary_progress", ["user_id"], unique=False)
    op.create_index("ix_user_vocabulary_progress_word_id", "user_vocabulary_progress", ["word_id"], unique=False)
    op.create_index("ix_user_vocabulary_progress_due_date", "user_vocabulary_progress", ["due_date"], unique=False)

    op.create_table(
        "word_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("context_sentence", sa.Text(), nullable=True),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(length=50), nullable=True),
        sa.Column("error_description", sa.String(length=255), nullable=True),
        sa.Column("correction", sa.String(length=255), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("was_suggested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"], ),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["vocabulary_words.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_word_interactions_user_id", "word_interactions", ["user_id"], unique=False)
    op.create_index("ix_word_interactions_word_id", "word_interactions", ["word_id"], unique=False)

    op.create_table(
        "review_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("progress_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_date", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("state_transition", sa.String(length=50), nullable=True),
        sa.Column("schedule_before", sa.Integer(), nullable=True),
        sa.Column("schedule_after", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())"), nullable=False),
        sa.ForeignKeyConstraint(["progress_id"], ["user_vocabulary_progress.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_review_logs_progress_id", "review_logs", ["progress_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_review_logs_progress_id", table_name="review_logs")
    op.drop_table("review_logs")

    op.drop_index("ix_word_interactions_word_id", table_name="word_interactions")
    op.drop_index("ix_word_interactions_user_id", table_name="word_interactions")
    op.drop_table("word_interactions")

    op.drop_index("ix_user_vocabulary_progress_due_date", table_name="user_vocabulary_progress")
    op.drop_index("ix_user_vocabulary_progress_word_id", table_name="user_vocabulary_progress")
    op.drop_index("ix_user_vocabulary_progress_user_id", table_name="user_vocabulary_progress")
    op.drop_table("user_vocabulary_progress")

    op.drop_index("ix_conversation_messages_session_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")

    op.drop_index("ix_user_achievements_achievement_id", table_name="user_achievements")
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_table("user_achievements")

    op.drop_index("ix_analytics_snapshots_snapshot_date", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_user_id", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")

    op.drop_index("ix_learning_sessions_user_id", table_name="learning_sessions")
    op.drop_table("learning_sessions")

    op.drop_index("ix_vocabulary_words_frequency_rank", table_name="vocabulary_words")
    op.drop_index("ix_vocabulary_words_normalized_word", table_name="vocabulary_words")
    op.drop_index("ix_vocabulary_words_language", table_name="vocabulary_words")
    op.drop_table("vocabulary_words")

    op.drop_constraint("uq_achievements_achievement_key", "achievements", type_="unique")
    op.drop_table("achievements")

    op.drop_index("ix_users_last_activity_date", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
