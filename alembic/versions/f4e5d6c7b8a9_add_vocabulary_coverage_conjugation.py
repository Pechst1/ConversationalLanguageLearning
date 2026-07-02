"""Add vocabulary coverage and conjugation progress tables.

Revision ID: f4e5d6c7b8a9
Revises: e5f6a7b8c9d0
Create Date: 2026-06-19
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f4e5d6c7b8a9"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode() or not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("verb_conjugations"):
        op.create_table(
            "verb_conjugations",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("lemma", sa.String(length=120), nullable=False),
            sa.Column("normalized_lemma", sa.String(length=120), nullable=False),
            sa.Column("tense", sa.String(length=80), nullable=False),
            sa.Column("person", sa.String(length=20), nullable=False),
            sa.Column("form", sa.String(length=160), nullable=False),
            sa.Column("auxiliary", sa.String(length=20), nullable=True),
            sa.Column("verb_group", sa.String(length=20), nullable=True),
            sa.Column("regularity", sa.String(length=20), server_default="regular", nullable=False),
            sa.Column("is_irregular", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("cefr_band", sa.String(length=10), server_default="A1", nullable=False),
            sa.Column("source", sa.String(length=40), server_default="deterministic", nullable=False),
            sa.Column("forms_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("normalized_lemma", "tense", "person", name="uq_verb_conjugation_form"),
        )
    _create_index_once("ix_verb_conjugations_lemma", "verb_conjugations", ["lemma"])
    _create_index_once("ix_verb_conjugations_normalized_lemma", "verb_conjugations", ["normalized_lemma"])
    _create_index_once("ix_verb_conjugations_tense", "verb_conjugations", ["tense"])
    _create_index_once("ix_verb_conjugations_is_irregular", "verb_conjugations", ["is_irregular"])
    _create_index_once("ix_verb_conjugations_cefr_band", "verb_conjugations", ["cefr_band"])
    _create_index_once("ix_verb_conjugations_lemma_tense", "verb_conjugations", ["normalized_lemma", "tense"])

    if not _has_table("user_conjugation_progress"):
        op.create_table(
            "user_conjugation_progress",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("verb_lemma", sa.String(length=120), nullable=False),
            sa.Column("normalized_lemma", sa.String(length=120), nullable=False),
            sa.Column("tense", sa.String(length=80), nullable=False),
            sa.Column("cefr_band", sa.String(length=10), server_default="A1", nullable=False),
            sa.Column("stability", sa.Float(), server_default="0", nullable=True),
            sa.Column("difficulty", sa.Float(), server_default="5", nullable=True),
            sa.Column("elapsed_days", sa.Integer(), server_default="0", nullable=True),
            sa.Column("scheduled_days", sa.Integer(), server_default="1", nullable=True),
            sa.Column("reps", sa.Integer(), server_default="0", nullable=True),
            sa.Column("lapses", sa.Integer(), server_default="0", nullable=True),
            sa.Column("state", sa.String(length=20), server_default="new", nullable=True),
            sa.Column("proficiency_score", sa.Integer(), server_default="0", nullable=True),
            sa.Column("last_review_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_review_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("mastered_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "normalized_lemma", "tense", name="uq_user_conjugation_progress_item"),
        )
    _create_index_once("ix_user_conjugation_progress_user_id", "user_conjugation_progress", ["user_id"])
    _create_index_once("ix_user_conjugation_progress_normalized_lemma", "user_conjugation_progress", ["normalized_lemma"])
    _create_index_once("ix_user_conjugation_progress_tense", "user_conjugation_progress", ["tense"])
    _create_index_once("ix_user_conjugation_progress_cefr_band", "user_conjugation_progress", ["cefr_band"])
    _create_index_once("ix_user_conjugation_progress_next_review_date", "user_conjugation_progress", ["next_review_date"])
    _create_index_once("ix_user_conjugation_progress_due_date", "user_conjugation_progress", ["due_date"])
    _create_index_once(
        "ix_user_conjugation_progress_due",
        "user_conjugation_progress",
        ["user_id", "next_review_date", "due_date"],
    )


def downgrade() -> None:
    op.drop_table("user_conjugation_progress", if_exists=True)
    op.drop_table("verb_conjugations", if_exists=True)
