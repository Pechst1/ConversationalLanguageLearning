"""add story rpg models

Revision ID: add_story_rpg_models
Revises: merge_grammar_error
Create Date: 2024-12-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_story_rpg_models'
down_revision: Union[str, None] = 'merge_grammar_error'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create stories table
    op.create_table(
        'stories',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('subtitle', sa.String(255), nullable=True),
        sa.Column('source_book', sa.String(255), nullable=True),
        sa.Column('source_author', sa.String(255), nullable=True),
        sa.Column('gutenberg_id', sa.String(20), nullable=True),
        sa.Column('target_levels', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('themes', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('learning_objectives', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Integer(), default=60),
        sa.Column('cover_image_url', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create chapters table
    op.create_table(
        'chapters',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('story_id', sa.String(50), sa.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('target_level', sa.String(10), nullable=True),
        sa.Column('learning_focus', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('cliffhanger', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('unlock_conditions', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create scenes table
    op.create_table(
        'scenes',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('chapter_id', sa.String(50), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('atmosphere', sa.String(100), nullable=True),
        sa.Column('narration_variants', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('objectives', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('npcs_present', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('consequences', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('transition_rules', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('estimated_duration_minutes', sa.Integer(), default=10),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create NPCs table
    op.create_table(
        'npcs',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('story_id', sa.String(50), sa.ForeignKey('stories.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('role', sa.String(255), nullable=True),
        sa.Column('backstory', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('appearance_description', sa.Text(), nullable=True),
        sa.Column('personality', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('speech_pattern', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('voice_config', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('information_tiers', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('relationship_config', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create NPC relationships table
    op.create_table(
        'npc_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('npc_id', sa.String(50), sa.ForeignKey('npcs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('level', sa.Integer(), default=1),
        sa.Column('trust', sa.Integer(), default=0),
        sa.Column('mood', sa.String(50), default='neutral'),
        sa.Column('total_interactions', sa.Integer(), default=0),
        sa.Column('positive_interactions', sa.Integer(), default=0),
        sa.Column('negative_interactions', sa.Integer(), default=0),
        sa.Column('has_shared_secret', sa.Integer(), default=0),
        sa.Column('is_ally', sa.Integer(), default=0),
        sa.Column('is_rival', sa.Integer(), default=0),
        sa.Column('first_interaction_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'npc_id', name='uq_user_npc_relationship'),
    )

    # Create NPC memories table
    op.create_table(
        'npc_memories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('npc_id', sa.String(50), sa.ForeignKey('npcs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('memory_type', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('scene_id', sa.String(50), nullable=True),
        sa.Column('sentiment', sa.String(20), default='neutral'),
        sa.Column('importance', sa.Integer(), default=5),
        sa.Column('player_quote', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create story progress table
    op.create_table(
        'story_progress',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('story_id', sa.String(50), sa.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('current_chapter_id', sa.String(50), nullable=True),
        sa.Column('current_scene_id', sa.String(50), nullable=True),
        sa.Column('story_flags', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('player_choices', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('philosophical_learnings', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('book_quotes_unlocked', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('chapters_completed', postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), 'sqlite'), nullable=True),
        sa.Column('completion_percentage', sa.Integer(), default=0),
        sa.Column('status', sa.String(20), default='in_progress'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_played_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('user_id', 'story_id', name='uq_user_story_progress'),
    )


def downgrade() -> None:
    op.drop_table('story_progress')
    op.drop_table('npc_memories')
    op.drop_table('npc_relationships')
    op.drop_table('npcs')
    op.drop_table('scenes')
    op.drop_table('chapters')
    op.drop_table('stories')
