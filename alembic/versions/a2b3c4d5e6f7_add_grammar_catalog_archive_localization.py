"""Add grammar catalog archive and localization metadata.

Revision ID: a2b3c4d5e6f7
Revises: 9c0d1e2f3a4b
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a2b3c4d5e6f7"
down_revision = "9c0d1e2f3a4b"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if _offline_mode():
        return False
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_column_once(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_index_once(index_name: str, table_name: str, columns: list[str], unique: bool = False) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    _add_column_once("grammar_concepts", sa.Column("catalog_version", sa.String(length=80), nullable=True))
    _add_column_once("grammar_concepts", sa.Column("source_refs", json_type, nullable=True))
    _create_index_once("ix_grammar_concepts_catalog_version", "grammar_concepts", ["catalog_version"])

    if not _has_table("grammar_concept_localizations"):
        op.create_table(
            "grammar_concept_localizations",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("concept_id", sa.Integer(), sa.ForeignKey("grammar_concepts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("locale", sa.String(length=10), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("category_label", sa.String(length=100), nullable=True),
            sa.Column("subskill_label", sa.String(length=100), nullable=True),
            sa.Column("short_description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("concept_id", "locale", name="uq_grammar_concept_localization"),
        )
    _create_index_once(
        "ix_grammar_concept_localizations_locale",
        "grammar_concept_localizations",
        ["locale"],
    )

    if not _has_table("grammar_concept_archives"):
        op.create_table(
            "grammar_concept_archives",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("concept_id", sa.Integer(), sa.ForeignKey("grammar_concepts.id", ondelete="SET NULL"), nullable=True),
            sa.Column("external_id", sa.String(length=80), nullable=True),
            sa.Column("language", sa.String(length=10), nullable=False, server_default="fr"),
            sa.Column("archived_from_version", sa.String(length=80), nullable=True),
            sa.Column("archive_reason", sa.String(length=160), nullable=False),
            sa.Column("replacement_external_id", sa.String(length=80), nullable=True),
            sa.Column("source_refs", json_type, nullable=True),
            sa.Column("row_snapshot", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
    _create_index_once("ix_grammar_concept_archives_concept", "grammar_concept_archives", ["concept_id"])
    _create_index_once("ix_grammar_concept_archives_external", "grammar_concept_archives", ["external_id"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_grammar_concept_archives_external", "grammar_concept_archives"),
        ("ix_grammar_concept_archives_concept", "grammar_concept_archives"),
        ("ix_grammar_concept_localizations_locale", "grammar_concept_localizations"),
        ("ix_grammar_concepts_catalog_version", "grammar_concepts"),
    ):
        if _has_index(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
    if _has_table("grammar_concept_archives"):
        op.drop_table("grammar_concept_archives")
    if _has_table("grammar_concept_localizations"):
        op.drop_table("grammar_concept_localizations")
    for column_name in ("source_refs", "catalog_version"):
        if _has_column("grammar_concepts", column_name):
            op.drop_column("grammar_concepts", column_name)
