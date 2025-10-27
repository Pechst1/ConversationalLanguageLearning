"""Initial database schema.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS uuid-ossp")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255)),
        sa.Column("native_language", sa.String(length=10), server_default="en"),
        sa.Column("target_language", sa.String(length=10), nullable=False, server_default="fr"),
        sa.Column("proficiency_level", sa.String(length=20), server_default="beginner"),
        sa.Column("total_xp", sa.Integer(), server_default="0"),
        sa.Column("level", sa.Integer(), server_default="1"),
        sa.Column("current_streak", sa.Integer(), server_default="0"),
        sa.Column("longest_streak", sa.Integer(), server_default="0"),
        sa.Column("last_activity_date", sa.Date()),
        sa.Column("daily_goal_minutes", sa.Integer(), server_default="15"),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("preferred_session_time", sa.Time()),
        sa.Column("subscription_tier", sa.String(length=20), server_default="free"),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.text("false")),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_last_activity_date", "users", ["last_activity_date"])

    op.create_table(
        "vocabulary_words",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("normalized_word", sa.String(length=255), nullable=False),
        sa.Column("part_of_speech", sa.String(length=50)),
        sa.Column("gender", sa.String(length=10)),
        sa.Column("frequency_rank", sa.Integer(), nullable=False),
        sa.Column("english_translation", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text()),
        sa.Column("example_sentence", sa.Text()),
        sa.Column("example_translation", sa.Text()),
        sa.Column("usage_notes", sa.Text()),
        sa.Column("difficulty_level", sa.Integer(), server_default="1"),
        sa.Column("topic_tags", postgresql.ARRAY(sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_vocabulary_words_language", "vocabulary_words", ["language"])
    op.create_index("ix_vocabulary_words_normalized_word", "vocabulary_words", ["normalized_word"])
    op.create_index("ix_vocabulary_words_frequency_rank", "vocabulary_words", ["frequency_rank"])

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("achievement_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("icon_url", sa.String(length=255)),
        sa.Column("xp_reward", sa.Integer(), server_default="0"),
        sa.Column("tier", sa.String(length=20), server_default="bronze"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("achievement_key"),
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("total_words_seen", sa.Integer(), server_default="0"),
        sa.Column("words_learning", sa.Integer(), server_default="0"),
        sa.Column("words_mastered", sa.Integer(), server_default="0"),
        sa.Column("new_words_today", sa.Integer(), server_default="0"),
        sa.Column("reviews_completed", sa.Integer(), server_default="0"),
        sa.Column("average_accuracy", sa.Float()),
        sa.Column("average_response_time_ms", sa.Integer()),
        sa.Column("streak_length", sa.Integer()),
        sa.Column("created_at", sa.Date(), server_default=sa.func.current_date()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_analytics_snapshots_user_id", "analytics_snapshots", ["user_id"])
    op.create_index("ix_analytics_snapshots_snapshot_date", "analytics_snapshots", ["snapshot_date"])

    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("achievement_id", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("progress", sa.Integer(), server_default="0"),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["achievement_id"], ["achievements.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievement"),
    )
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])

    op.create_table(
        "learning_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_duration_minutes", sa.Integer()),
        sa.Column("topic", sa.String(length=255)),
        sa.Column("conversation_style", sa.String(length=50)),
        sa.Column("difficulty_preference", sa.String(length=20)),
        sa.Column("words_practiced", sa.Integer(), server_default="0"),
        sa.Column("new_words_introduced", sa.Integer(), server_default="0"),
        sa.Column("words_reviewed", sa.Integer(), server_default="0"),
        sa.Column("correct_responses", sa.Integer(), server_default="0"),
        sa.Column("incorrect_responses", sa.Integer(), server_default="0"),
        sa.Column("accuracy_rate", sa.Float()),
        sa.Column("xp_earned", sa.Integer(), server_default="0"),
        sa.Column("level_before", sa.Integer()),
        sa.Column("level_after", sa.Integer()),
        sa.Column("status", sa.String(length=20), server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_learning_sessions_user_id", "learning_sessions", ["user_id"])
    op.create_index("ix_learning_sessions_started_at", "learning_sessions", ["started_at"])
    op.create_index(
        "ix_learning_sessions_user_status", "learning_sessions", ["user_id", "status"]
    )

    op.create_table(
        "user_vocabulary_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("stability", sa.Float(), server_default="0"),
        sa.Column("difficulty", sa.Float(), server_default="5"),
        sa.Column("elapsed_days", sa.Integer(), server_default="0"),
        sa.Column("scheduled_days", sa.Integer(), server_default="1"),
        sa.Column("reps", sa.Integer(), server_default="0"),
        sa.Column("lapses", sa.Integer(), server_default="0"),
        sa.Column("state", sa.String(length=20), server_default="new"),
        sa.Column("proficiency_score", sa.Integer(), server_default="0"),
        sa.Column("correct_count", sa.Integer(), server_default="0"),
        sa.Column("incorrect_count", sa.Integer(), server_default="0"),
        sa.Column("hint_count", sa.Integer(), server_default="0"),
        sa.Column("last_review_date", sa.DateTime(timezone=True)),
        sa.Column("next_review_date", sa.DateTime(timezone=True)),
        sa.Column("due_date", sa.Date()),
        sa.Column("times_seen", sa.Integer(), server_default="0"),
        sa.Column("times_used_correctly", sa.Integer(), server_default="0"),
        sa.Column("times_used_incorrectly", sa.Integer(), server_default="0"),
        sa.Column("error_types", postgresql.JSONB(astext_type=sa.Text()), server_default="[]"),
        sa.Column("first_seen_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("mastered_date", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["vocabulary_words.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "word_id", name="uq_user_word"),
    )
    op.create_index(
        "ix_user_vocabulary_progress_user_id", "user_vocabulary_progress", ["user_id"]
    )
    op.create_index("ix_user_vocabulary_progress_word_id", "user_vocabulary_progress", ["word_id"])
    op.create_index("ix_user_vocabulary_progress_due_date", "user_vocabulary_progress", ["due_date"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("target_words", postgresql.ARRAY(sa.Integer())),
        sa.Column("errors_detected", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("words_used", postgresql.ARRAY(sa.Integer())),
        sa.Column("suggested_words_used", postgresql.ARRAY(sa.Integer())),
        sa.Column("xp_earned", sa.Integer(), server_default="0"),
        sa.Column("generation_prompt", sa.Text()),
        sa.Column("llm_model", sa.String(length=50)),
        sa.Column("tokens_used", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_conversation_messages_session", "conversation_messages", ["session_id", "sequence_number"]
    )

    op.create_table(
        "review_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("progress_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_date", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("state_transition", sa.String(length=50)),
        sa.Column("schedule_before", sa.Integer()),
        sa.Column("schedule_after", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["progress_id"], ["user_vocabulary_progress.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "word_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("interaction_type", sa.String(length=50), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("context_sentence", sa.Text()),
        sa.Column("user_response", sa.Text()),
        sa.Column("error_type", sa.String(length=50)),
        sa.Column("error_description", sa.Text()),
        sa.Column("correction", sa.Text()),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("was_suggested", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["session_id"], ["learning_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["vocabulary_words.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"]),
    )
    op.create_index("ix_word_interactions_user_id", "word_interactions", ["user_id"])
    op.create_index("ix_word_interactions_session_id", "word_interactions", ["session_id"])
    op.create_index("ix_word_interactions_word_id", "word_interactions", ["word_id"])


def downgrade() -> None:
    op.drop_table("word_interactions")
    op.drop_table("review_logs")
    op.drop_index("ix_conversation_messages_session", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_user_vocabulary_progress_due_date", table_name="user_vocabulary_progress")
    op.drop_index("ix_user_vocabulary_progress_word_id", table_name="user_vocabulary_progress")
    op.drop_index("ix_user_vocabulary_progress_user_id", table_name="user_vocabulary_progress")
    op.drop_table("user_vocabulary_progress")
    op.drop_index("ix_learning_sessions_user_status", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_started_at", table_name="learning_sessions")
    op.drop_index("ix_learning_sessions_user_id", table_name="learning_sessions")
    op.drop_table("learning_sessions")
    op.drop_index("ix_user_achievements_user_id", table_name="user_achievements")
    op.drop_table("user_achievements")
    op.drop_index("ix_analytics_snapshots_snapshot_date", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_user_id", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")
    op.drop_table("achievements")
    op.drop_index("ix_vocabulary_words_frequency_rank", table_name="vocabulary_words")
    op.drop_index("ix_vocabulary_words_normalized_word", table_name="vocabulary_words")
    op.drop_index("ix_vocabulary_words_language", table_name="vocabulary_words")
    op.drop_table("vocabulary_words")
    op.drop_index("ix_users_last_activity_date", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
