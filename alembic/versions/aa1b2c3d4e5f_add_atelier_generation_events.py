"""Add Atelier generation quality events.

Revision ID: aa1b2c3d4e5f
Revises: b0c1d2e3f4a5
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "aa1b2c3d4e5f"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if _offline_mode():
        return False
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")

    if not _has_table("atelier_generation_events"):
        op.create_table(
            "atelier_generation_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("concept_id", sa.Integer(), nullable=True),
            sa.Column("atelier_session_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("exercise_set_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("generator_version", sa.String(length=80), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=True),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("payload", json_type, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("timezone('utc', now())"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["concept_id"], ["grammar_concepts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["atelier_session_id"], ["atelier_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["exercise_set_id"], ["atelier_exercise_sets.id"], ondelete="SET NULL"),
        )
    _create_index_once(
        "ix_atelier_generation_events_concept_type",
        "atelier_generation_events",
        ["concept_id", "event_type", "created_at"],
    )
    _create_index_once(
        "ix_atelier_generation_events_user_created",
        "atelier_generation_events",
        ["user_id", "created_at"],
    )
    _create_index_once("ix_atelier_generation_events_user_id", "atelier_generation_events", ["user_id"])
    _create_index_once("ix_atelier_generation_events_concept_id", "atelier_generation_events", ["concept_id"])
    _create_index_once(
        "ix_atelier_generation_events_atelier_session_id",
        "atelier_generation_events",
        ["atelier_session_id"],
    )
    _create_index_once(
        "ix_atelier_generation_events_exercise_set_id",
        "atelier_generation_events",
        ["exercise_set_id"],
    )


def downgrade() -> None:
    for index_name in (
        "ix_atelier_generation_events_exercise_set_id",
        "ix_atelier_generation_events_atelier_session_id",
        "ix_atelier_generation_events_concept_id",
        "ix_atelier_generation_events_user_id",
        "ix_atelier_generation_events_user_created",
        "ix_atelier_generation_events_concept_type",
    ):
        if _has_index("atelier_generation_events", index_name):
            op.drop_index(index_name, table_name="atelier_generation_events")
    if _has_table("atelier_generation_events"):
        op.drop_table("atelier_generation_events")
