"""add story system

Revision ID: c1d2e3f4g5h6
Revises: b1b2c3d4e5f7
Create Date: 2026-01-17 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c1d2e3f4g5h6"
down_revision = "b1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create stories table
    op.create_table(
        "stories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("story_key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("difficulty_level", sa.String(length=20), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True, server_default="60"),
        sa.Column("theme_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("vocabulary_theme", sa.String(length=100), nullable=True),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("author", sa.String(length=100), nullable=True),
        sa.Column("total_chapters", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=True, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("story_key"),
    )
    op.create_index("idx_stories_published", "stories", ["is_published", "difficulty_level"], unique=False)
    op.create_index(op.f("ix_stories_id"), "stories", ["id"], unique=False)
    op.create_index(op.f("ix_stories_story_key"), "stories", ["story_key"], unique=True)

    # Create story_chapters table
    op.create_table(
        "story_chapters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("chapter_key", sa.String(length=100), nullable=False),
        sa.Column("sequence_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("opening_narrative", sa.Text(), nullable=True),
        sa.Column("min_turns", sa.Integer(), nullable=True, server_default="3"),
        sa.Column("max_turns", sa.Integer(), nullable=True, server_default="10"),
        sa.Column("narrative_goals", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("completion_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("branching_choices", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("default_next_chapter_id", sa.Integer(), nullable=True),
        sa.Column("completion_xp", sa.Integer(), nullable=True, server_default="75"),
        sa.Column("perfect_completion_xp", sa.Integer(), nullable=True, server_default="150"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_next_chapter_id"], ["story_chapters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_story_chapters_story_seq", "story_chapters", ["story_id", "sequence_order"], unique=False)
    op.create_index(op.f("ix_story_chapters_chapter_key"), "story_chapters", ["chapter_key"], unique=False)
    op.create_index(op.f("ix_story_chapters_id"), "story_chapters", ["id"], unique=False)

    # Create user_story_progress table
    op.create_table(
        "user_story_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("current_chapter_id", sa.Integer(), nullable=True),
        sa.Column("chapters_completed", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"),
        sa.Column("total_chapters_completed", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=True, server_default="'in_progress'"),
        sa.Column("completion_percentage", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("total_xp_earned", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("total_time_spent_minutes", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("vocabulary_mastered_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("perfect_chapters_count", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("narrative_choices", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["current_chapter_id"], ["story_chapters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_current_chapter", "user_story_progress", ["user_id", "current_chapter_id"], unique=False)
    op.create_index("idx_user_story_status", "user_story_progress", ["user_id", "status"], unique=False)
    op.create_index("idx_user_story_unique", "user_story_progress", ["user_id", "story_id"], unique=True)
    op.create_index(op.f("ix_user_story_progress_story_id"), "user_story_progress", ["story_id"], unique=False)
    op.create_index(op.f("ix_user_story_progress_user_id"), "user_story_progress", ["user_id"], unique=False)

    # Add story columns to learning_sessions table
    op.add_column("learning_sessions", sa.Column("story_id", sa.Integer(), nullable=True))
    op.add_column("learning_sessions", sa.Column("story_chapter_id", sa.Integer(), nullable=True))
    op.add_column("learning_sessions", sa.Column("chapter_completion_status", sa.String(length=20), nullable=True))
    op.add_column("learning_sessions", sa.Column("narrative_goals_completed", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="[]"))

    op.create_foreign_key("fk_learning_sessions_story_id", "learning_sessions", "stories", ["story_id"], ["id"])
    op.create_foreign_key("fk_learning_sessions_story_chapter_id", "learning_sessions", "story_chapters", ["story_chapter_id"], ["id"])


def downgrade() -> None:
    # Drop foreign keys from learning_sessions
    op.drop_constraint("fk_learning_sessions_story_chapter_id", "learning_sessions", type_="foreignkey")
    op.drop_constraint("fk_learning_sessions_story_id", "learning_sessions", type_="foreignkey")

    # Drop columns from learning_sessions
    op.drop_column("learning_sessions", "narrative_goals_completed")
    op.drop_column("learning_sessions", "chapter_completion_status")
    op.drop_column("learning_sessions", "story_chapter_id")
    op.drop_column("learning_sessions", "story_id")

    # Drop user_story_progress table
    op.drop_index(op.f("ix_user_story_progress_user_id"), table_name="user_story_progress")
    op.drop_index(op.f("ix_user_story_progress_story_id"), table_name="user_story_progress")
    op.drop_index("idx_user_story_unique", table_name="user_story_progress")
    op.drop_index("idx_user_story_status", table_name="user_story_progress")
    op.drop_index("idx_user_current_chapter", table_name="user_story_progress")
    op.drop_table("user_story_progress")

    # Drop story_chapters table
    op.drop_index(op.f("ix_story_chapters_id"), table_name="story_chapters")
    op.drop_index(op.f("ix_story_chapters_chapter_key"), table_name="story_chapters")
    op.drop_index("idx_story_chapters_story_seq", table_name="story_chapters")
    op.drop_table("story_chapters")

    # Drop stories table
    op.drop_index(op.f("ix_stories_story_key"), table_name="stories")
    op.drop_index(op.f("ix_stories_id"), table_name="stories")
    op.drop_index("idx_stories_published", table_name="stories")
    op.drop_table("stories")
