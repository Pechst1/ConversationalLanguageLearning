"""Add Atelier language packs and concept blueprints.

Revision ID: 9c0d1e2f3a4b
Revises: 0f4e5a6b7c8d
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "9c0d1e2f3a4b"
down_revision = "0f4e5a6b7c8d"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    if not _has_table("atelier_language_packs"):
        op.create_table(
            "atelier_language_packs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("language_code", sa.String(length=10), nullable=False),
            sa.Column("version", sa.String(length=80), nullable=False),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="approved"),
            sa.Column("payload", json_type, nullable=False),
            sa.Column("generation_metadata", json_type, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("timezone('utc', now())"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("timezone('utc', now())"),
                nullable=False,
            ),
            sa.UniqueConstraint("language_code", "version", name="uq_atelier_language_pack_version"),
        )
    _create_index_once(
        "ix_atelier_language_packs_status",
        "atelier_language_packs",
        ["language_code", "review_status"],
    )

    if not _has_table("atelier_concept_blueprints"):
        op.create_table(
            "atelier_concept_blueprints",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "concept_id",
                sa.Integer(),
                sa.ForeignKey("grammar_concepts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("language", sa.String(length=10), nullable=False),
            sa.Column("asset_version", sa.String(length=80), nullable=False),
            sa.Column("review_status", sa.String(length=30), nullable=False, server_default="approved"),
            sa.Column("payload", json_type, nullable=False),
            sa.Column("generation_metadata", json_type, nullable=False),
            sa.Column("source_hash", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("timezone('utc', now())"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("timezone('utc', now())"),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "concept_id",
                "language",
                "asset_version",
                name="uq_atelier_concept_blueprint_version",
            ),
        )
    _create_index_once("ix_atelier_concept_blueprints_concept_id", "atelier_concept_blueprints", ["concept_id"])
    _create_index_once(
        "ix_atelier_concept_blueprints_lookup",
        "atelier_concept_blueprints",
        ["concept_id", "language", "review_status"],
    )


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_atelier_concept_blueprints_lookup", "atelier_concept_blueprints"),
        ("ix_atelier_concept_blueprints_concept_id", "atelier_concept_blueprints"),
        ("ix_atelier_language_packs_status", "atelier_language_packs"),
    ):
        if _has_index(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
    if _has_table("atelier_concept_blueprints"):
        op.drop_table("atelier_concept_blueprints")
    if _has_table("atelier_language_packs"):
        op.drop_table("atelier_language_packs")
