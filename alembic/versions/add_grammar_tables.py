"""add grammar tables

Revision ID: add_grammar_tables
Revises: 
Create Date: 2024-12-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_grammar_tables'
down_revision: Union[str, None] = 'd2e3f4g5h6i7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create grammar_concepts table
    op.create_table(
        'grammar_concepts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('examples', sa.Text(), nullable=True),
        sa.Column('difficulty_order', sa.Integer(), nullable=True, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_grammar_concepts_level', 'grammar_concepts', ['level'], unique=False)

    # Create user_grammar_progress table
    op.create_table(
        'user_grammar_progress',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('concept_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=True, default=0.0),
        sa.Column('reps', sa.Integer(), nullable=True, default=0),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True, default='neu'),
        sa.Column('last_review', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_review', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['concept_id'], ['grammar_concepts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_grammar_progress_user_concept', 'user_grammar_progress', ['user_id', 'concept_id'], unique=True)
    op.create_index('ix_user_grammar_progress_next_review', 'user_grammar_progress', ['user_id', 'next_review'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_grammar_progress_next_review', table_name='user_grammar_progress')
    op.drop_index('ix_user_grammar_progress_user_concept', table_name='user_grammar_progress')
    op.drop_table('user_grammar_progress')
    op.drop_index('ix_grammar_concepts_level', table_name='grammar_concepts')
    op.drop_table('grammar_concepts')
