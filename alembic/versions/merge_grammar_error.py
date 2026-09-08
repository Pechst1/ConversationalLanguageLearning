"""merge grammar and error concepts

Revision ID: merge_grammar_error
Revises: add_grammar_tables, 20241212_error_concepts
Create Date: 2024-12-14

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'merge_grammar_error'
down_revision: str | Sequence[str] | None = ('add_grammar_tables', '20241212_error_concepts')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Merge revision - no operations needed
    pass


def downgrade() -> None:
    # Merge revision - no operations needed
    pass
