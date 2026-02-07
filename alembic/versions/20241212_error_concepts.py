"""Add user_error_concepts table

Revision ID: 20241212_error_concepts
Revises: 
Create Date: 2024-12-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20241212_error_concepts'
down_revision = None  # Will need to be set to actual latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_error_concepts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('concept_id', sa.String(50), nullable=False),
        sa.Column('stability', sa.Float(), default=0.0),
        sa.Column('difficulty', sa.Float(), default=5.0),
        sa.Column('elapsed_days', sa.Integer(), default=0),
        sa.Column('scheduled_days', sa.Integer(), default=1),
        sa.Column('reps', sa.Integer(), default=0),
        sa.Column('lapses', sa.Integer(), default=0),
        sa.Column('state', sa.String(20), default='new'),
        sa.Column('last_review_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_review_date', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('total_occurrences', sa.Integer(), default=0),
        sa.Column('last_occurrence_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'concept_id', name='uq_user_error_concept'),
    )


def downgrade() -> None:
    op.drop_table('user_error_concepts')
