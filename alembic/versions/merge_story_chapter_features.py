"""Merge story chapter features from worktree

Adds narrative goals, completion criteria, branching choices, and XP tracking
to support chapter-based story navigation alongside scene-based progression.

Revision ID: merge_story_chapter_features
Revises: add_story_rpg_models
Create Date: 2025-01-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'merge_story_chapter_features'
down_revision = 'add_story_rpg_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to chapters table
    op.add_column('chapters', sa.Column('narrative_goals', sa.JSON(), nullable=True))
    op.add_column('chapters', sa.Column('completion_criteria', sa.JSON(), nullable=True))
    op.add_column('chapters', sa.Column('branching_choices', sa.JSON(), nullable=True))
    op.add_column('chapters', sa.Column('default_next_chapter_id', sa.String(50), nullable=True))
    op.add_column('chapters', sa.Column('completion_xp', sa.Integer(), nullable=True, server_default='75'))
    op.add_column('chapters', sa.Column('perfect_completion_xp', sa.Integer(), nullable=True, server_default='150'))
    op.add_column('chapters', sa.Column('vocabulary_theme', sa.String(100), nullable=True))

    # Add foreign key for default_next_chapter_id (self-referencing)
    op.create_foreign_key(
        'fk_chapters_default_next_chapter',
        'chapters',
        'chapters',
        ['default_next_chapter_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # Add new columns to story_progress table
    op.add_column('story_progress', sa.Column('chapters_completed_details', sa.JSON(), nullable=True))
    op.add_column('story_progress', sa.Column('narrative_choices', sa.JSON(), nullable=True))
    op.add_column('story_progress', sa.Column('total_xp_earned', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('story_progress', sa.Column('perfect_chapters_count', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    # Remove columns from story_progress table
    op.drop_column('story_progress', 'perfect_chapters_count')
    op.drop_column('story_progress', 'total_xp_earned')
    op.drop_column('story_progress', 'narrative_choices')
    op.drop_column('story_progress', 'chapters_completed_details')

    # Remove foreign key and columns from chapters table
    op.drop_constraint('fk_chapters_default_next_chapter', 'chapters', type_='foreignkey')
    op.drop_column('chapters', 'vocabulary_theme')
    op.drop_column('chapters', 'perfect_completion_xp')
    op.drop_column('chapters', 'completion_xp')
    op.drop_column('chapters', 'default_next_chapter_id')
    op.drop_column('chapters', 'branching_choices')
    op.drop_column('chapters', 'completion_criteria')
    op.drop_column('chapters', 'narrative_goals')
