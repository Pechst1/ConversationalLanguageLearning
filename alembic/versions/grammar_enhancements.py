"""Grammar enhancements: achievements, streaks, prerequisites, visualizations

Adds:
- Achievement trigger fields for grammar-specific achievements
- Grammar streak tracking fields to users
- Prerequisites and visualization_type to grammar_concepts
- grammar_focus field to chapters for story-grammar integration

Revision ID: grammar_enhancements
Revises: merge_story_chapter_features
Create Date: 2025-01-19

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'grammar_enhancements'
down_revision = 'merge_story_chapter_features'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column already exists in the table."""
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :column"
    ), {"table": table_name, "column": column_name})
    return result.fetchone() is not None


def upgrade() -> None:
    # Add trigger fields to achievements table
    if not column_exists('achievements', 'category'):
        op.add_column('achievements', sa.Column('category', sa.String(50), nullable=True, server_default='general'))
    if not column_exists('achievements', 'trigger_type'):
        op.add_column('achievements', sa.Column('trigger_type', sa.String(50), nullable=True))
    if not column_exists('achievements', 'trigger_value'):
        op.add_column('achievements', sa.Column('trigger_value', sa.Integer(), nullable=True))

    # Add grammar streak fields to users table (may already exist)
    if not column_exists('users', 'grammar_streak_days'):
        op.add_column('users', sa.Column('grammar_streak_days', sa.Integer(), nullable=True, server_default='0'))
    if not column_exists('users', 'grammar_last_review_date'):
        op.add_column('users', sa.Column('grammar_last_review_date', sa.Date(), nullable=True))
    if not column_exists('users', 'grammar_longest_streak'):
        op.add_column('users', sa.Column('grammar_longest_streak', sa.Integer(), nullable=True, server_default='0'))

    # Add prerequisites and visualization_type to grammar_concepts
    if not column_exists('grammar_concepts', 'prerequisites'):
        op.add_column('grammar_concepts', sa.Column('prerequisites', sa.JSON(), nullable=True))
    if not column_exists('grammar_concepts', 'visualization_type'):
        op.add_column('grammar_concepts', sa.Column('visualization_type', sa.String(50), nullable=True))

    # Add grammar_focus to chapters table
    if not column_exists('chapters', 'grammar_focus'):
        op.add_column('chapters', sa.Column('grammar_focus', sa.JSON(), nullable=True))

    # Seed grammar-specific achievements
    op.execute("""
        INSERT INTO achievements (achievement_key, name, description, xp_reward, tier, category, trigger_type, trigger_value)
        VALUES
            ('grammar_first_steps', 'Erste Schritte', 'Schließe deine erste Grammatik-Übung ab', 10, 'bronze', 'grammar', 'grammar_review', 1),
            ('grammar_streak_7', 'Wochenstreak', '7 Tage in Folge Grammatik geübt', 50, 'silver', 'grammar', 'streak', 7),
            ('grammar_streak_30', 'Monatsstreak', '30 Tage in Folge Grammatik geübt', 200, 'gold', 'grammar', 'streak', 30),
            ('grammar_perfect_score', 'Perfektion', 'Erhalte 10/10 bei einer Grammatik-Übung', 25, 'silver', 'grammar', 'perfect_score', 10),
            ('grammar_level_master_a1', 'A1 Meister', 'Meistere alle A1 Grammatik-Konzepte', 100, 'gold', 'grammar', 'level_master', 1),
            ('grammar_level_master_a2', 'A2 Meister', 'Meistere alle A2 Grammatik-Konzepte', 150, 'gold', 'grammar', 'level_master', 2),
            ('grammar_level_master_b1', 'B1 Meister', 'Meistere alle B1 Grammatik-Konzepte', 200, 'platinum', 'grammar', 'level_master', 3),
            ('grammar_error_crusher', 'Fehler-Bezwinger', 'Meistere 5 Konzepte, die aus deinen Fehlern stammen', 75, 'silver', 'grammar', 'error_crusher', 5)
        ON CONFLICT (achievement_key) DO UPDATE SET
            category = EXCLUDED.category,
            trigger_type = EXCLUDED.trigger_type,
            trigger_value = EXCLUDED.trigger_value
    """)


def downgrade() -> None:
    # Remove grammar_focus from chapters
    op.drop_column('chapters', 'grammar_focus')

    # Remove prerequisites and visualization_type from grammar_concepts
    op.drop_column('grammar_concepts', 'visualization_type')
    op.drop_column('grammar_concepts', 'prerequisites')

    # Remove grammar streak fields from users
    op.drop_column('users', 'grammar_longest_streak')
    op.drop_column('users', 'grammar_last_review_date')
    op.drop_column('users', 'grammar_streak_days')

    # Remove trigger fields from achievements
    op.drop_column('achievements', 'trigger_value')
    op.drop_column('achievements', 'trigger_type')
    op.drop_column('achievements', 'category')

    # Remove seeded achievements
    op.execute("""
        DELETE FROM achievements WHERE achievement_key IN (
            'grammar_first_steps', 'grammar_streak_7', 'grammar_streak_30',
            'grammar_perfect_score', 'grammar_level_master_a1', 'grammar_level_master_a2',
            'grammar_level_master_b1', 'grammar_error_crusher'
        )
    """)
