"""Add Atelier practice tables and grammar catalog metadata.

Revision ID: f3a4b5c6d7e8
Revises: e1f2a3b4c5d6
Create Date: 2026-05-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f3a4b5c6d7e8"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    if getattr(op.get_context(), "as_sql", False):
        return True
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if getattr(op.get_context(), "as_sql", False):
        return False
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_once(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_once("grammar_concepts", sa.Column("external_id", sa.String(length=80), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("language", sa.String(length=10), nullable=False, server_default="fr"))
    _add_column_once("grammar_concepts", sa.Column("subskill", sa.String(length=100), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("core_rule", sa.Text(), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("main_traps", sa.Text(), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("anchor_examples", sa.Text(), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("exercise_tags", sa.JSON(), nullable=True))
    _add_column_once(
        "grammar_concepts",
        sa.Column("is_foundation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    _add_column_once(
        "grammar_concepts",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    _add_column_once("grammar_concepts", sa.Column("parent_external_id", sa.String(length=80), nullable=True))

    op.create_index(
        "ix_grammar_concepts_external_id",
        "grammar_concepts",
        ["external_id"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_grammar_concepts_active_foundation",
        "grammar_concepts",
        ["active", "is_foundation"],
        unique=False,
        if_not_exists=True,
    )

    if not _has_table("atelier_sessions"):
        op.create_table(
            "atelier_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("selected_concept_ids", sa.JSON(), nullable=False),
            sa.Column("quote_payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("recap_payload", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_atelier_sessions_user_id", "atelier_sessions", ["user_id"], if_not_exists=True)
    op.create_index(
        "ix_atelier_sessions_user_status",
        "atelier_sessions",
        ["user_id", "status"],
        if_not_exists=True,
    )

    if not _has_table("atelier_exercise_sets"):
        op.create_table(
            "atelier_exercise_sets",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("concept_id", sa.Integer(), nullable=False),
            sa.Column("generator_version", sa.String(length=80), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("source", sa.String(length=30), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("validation_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["concept_id"], ["grammar_concepts.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("concept_id", "generator_version", "content_hash", name="uq_atelier_exercise_set_payload"),
        )
    op.create_index("ix_atelier_exercise_sets_concept_id", "atelier_exercise_sets", ["concept_id"], if_not_exists=True)
    op.create_index(
        "ix_atelier_exercise_sets_lookup",
        "atelier_exercise_sets",
        ["concept_id", "generator_version", "created_at"],
        if_not_exists=True,
    )

    if not _has_table("atelier_attempts"):
        op.create_table(
            "atelier_attempts",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("atelier_session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("concept_id", sa.Integer(), nullable=True),
            sa.Column("round", sa.String(length=30), nullable=False),
            sa.Column("mode", sa.String(length=40), nullable=False),
            sa.Column("exercise_id", sa.String(length=120), nullable=False),
            sa.Column("prompt_payload", sa.JSON(), nullable=False),
            sa.Column("answer_payload", sa.JSON(), nullable=False),
            sa.Column("correction_payload", sa.JSON(), nullable=False),
            sa.Column("verdict", sa.String(length=30), nullable=False),
            sa.Column("score_0_4", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["atelier_session_id"], ["atelier_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["concept_id"], ["grammar_concepts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.create_index("ix_atelier_attempts_atelier_session_id", "atelier_attempts", ["atelier_session_id"], if_not_exists=True)
    op.create_index("ix_atelier_attempts_concept_id", "atelier_attempts", ["concept_id"], if_not_exists=True)
    op.create_index("ix_atelier_attempts_user_id", "atelier_attempts", ["user_id"], if_not_exists=True)
    op.create_index(
        "ix_atelier_attempts_session_round",
        "atelier_attempts",
        ["atelier_session_id", "round", "mode"],
        if_not_exists=True,
    )

    _add_column_once("user_errors", sa.Column("concept_id", sa.Integer(), nullable=True))
    _add_column_once("user_errors", sa.Column("source_attempt_id", postgresql.UUID(as_uuid=True), nullable=True))
    _add_column_once("user_errors", sa.Column("why_wrong", sa.Text(), nullable=True))
    _add_column_once("user_errors", sa.Column("repair_hint", sa.Text(), nullable=True))
    _add_column_once("user_errors", sa.Column("display_label", sa.String(length=120), nullable=True))
    _add_column_once("user_errors", sa.Column("task_error_type", sa.String(length=80), nullable=True))
    op.create_foreign_key(
        "fk_user_errors_concept_id_grammar_concepts",
        "user_errors",
        "grammar_concepts",
        ["concept_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_user_errors_source_attempt_id_atelier_attempts",
        "user_errors",
        "atelier_attempts",
        ["source_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_user_errors_concept_id", "user_errors", ["concept_id"], if_not_exists=True)
    op.create_index("ix_user_errors_source_attempt_id", "user_errors", ["source_attempt_id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_user_errors_source_attempt_id", table_name="user_errors", if_exists=True)
    op.drop_index("ix_user_errors_concept_id", table_name="user_errors", if_exists=True)
    op.drop_constraint("fk_user_errors_source_attempt_id_atelier_attempts", "user_errors", type_="foreignkey")
    op.drop_constraint("fk_user_errors_concept_id_grammar_concepts", "user_errors", type_="foreignkey")
    for column_name in (
        "task_error_type",
        "display_label",
        "repair_hint",
        "why_wrong",
        "source_attempt_id",
        "concept_id",
    ):
        if _has_column("user_errors", column_name):
            op.drop_column("user_errors", column_name)

    op.drop_table("atelier_attempts", if_exists=True)
    op.drop_table("atelier_exercise_sets", if_exists=True)
    op.drop_table("atelier_sessions", if_exists=True)

    op.drop_index("ix_grammar_concepts_active_foundation", table_name="grammar_concepts", if_exists=True)
    op.drop_index("ix_grammar_concepts_external_id", table_name="grammar_concepts", if_exists=True)
    for column_name in (
        "parent_external_id",
        "active",
        "is_foundation",
        "exercise_tags",
        "anchor_examples",
        "main_traps",
        "core_rule",
        "subskill",
        "language",
        "external_id",
    ):
        if _has_column("grammar_concepts", column_name):
            op.drop_column("grammar_concepts", column_name)
