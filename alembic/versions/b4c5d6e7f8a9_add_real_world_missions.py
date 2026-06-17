"""Add real-world scenario missions.

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b4c5d6e7f8a9"
down_revision = "a2b3c4d5e6f7"
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
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("real_world_missions"):
        op.create_table(
            "real_world_missions",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("atelier_session_id", uuid_type, nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="available"),
            sa.Column("cadence", sa.String(length=30), nullable=False, server_default="weekly"),
            sa.Column("mission_type", sa.String(length=40), nullable=False, server_default="message"),
            sa.Column("iso_year", sa.Integer(), nullable=True),
            sa.Column("iso_week", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("brief", sa.Text(), nullable=False),
            sa.Column("selected_concept_ids", json_type, nullable=False),
            sa.Column("target_errata_ids", json_type, nullable=False),
            sa.Column("target_vocabulary_ids", json_type, nullable=False),
            sa.Column("source_snapshot", json_type, nullable=False),
            sa.Column("objectives", json_type, nullable=False),
            sa.Column("prompt_payload", json_type, nullable=False),
            sa.Column("recap_payload", json_type, nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["atelier_session_id"], ["atelier_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "cadence", "iso_year", "iso_week", name="uq_real_world_mission_weekly"),
        )
    _create_index_once("ix_real_world_missions_user_id", "real_world_missions", ["user_id"])
    _create_index_once("ix_real_world_missions_atelier_session_id", "real_world_missions", ["atelier_session_id"])
    _create_index_once("ix_real_world_missions_status", "real_world_missions", ["status"])
    _create_index_once("ix_real_world_missions_cadence", "real_world_missions", ["cadence"])
    _create_index_once("ix_real_world_missions_mission_type", "real_world_missions", ["mission_type"])
    _create_index_once("ix_real_world_missions_user_status", "real_world_missions", ["user_id", "status"])

    if not _has_table("real_world_mission_attempts"):
        op.create_table(
            "real_world_mission_attempts",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("mission_id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("mode", sa.String(length=30), nullable=False, server_default="writing"),
            sa.Column("answer_payload", json_type, nullable=False),
            sa.Column("correction_payload", json_type, nullable=False),
            sa.Column("verdict", sa.String(length=30), nullable=False, server_default="needs_review"),
            sa.Column("score_0_4", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["mission_id"], ["real_world_missions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_once("ix_real_world_mission_attempts_mission_id", "real_world_mission_attempts", ["mission_id"])
    _create_index_once("ix_real_world_mission_attempts_user_id", "real_world_mission_attempts", ["user_id"])

    if not _has_table("real_world_mission_turns"):
        op.create_table(
            "real_world_mission_turns",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("mission_id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("mode", sa.String(length=30), nullable=False, server_default="chat"),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("audio_payload", json_type, nullable=False),
            sa.Column("correction_payload", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["mission_id"], ["real_world_missions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("mission_id", "turn_index", name="uq_real_world_mission_turn_index"),
        )
    _create_index_once("ix_real_world_mission_turns_mission_id", "real_world_mission_turns", ["mission_id"])
    _create_index_once("ix_real_world_mission_turns_user_id", "real_world_mission_turns", ["user_id"])
    _create_index_once("ix_real_world_mission_turns_order", "real_world_mission_turns", ["mission_id", "turn_index"])


def downgrade() -> None:
    op.drop_table("real_world_mission_turns", if_exists=True)
    op.drop_table("real_world_mission_attempts", if_exists=True)
    op.drop_table("real_world_missions", if_exists=True)
