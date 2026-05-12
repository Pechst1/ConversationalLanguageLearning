"""Add graphic novel Feuilleton mode.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
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
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("personal_input_items"):
        op.create_table(
            "personal_input_items",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("item_type", sa.String(length=40), nullable=False, server_default="interest"),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("text", sa.Text(), nullable=False, server_default=""),
            sa.Column("source_url", sa.Text(), nullable=True),
            sa.Column("source_name", sa.String(length=120), nullable=True),
            sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
            sa.Column("tags", json_type, nullable=False),
            sa.Column("item_metadata", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_once("ix_personal_input_items_user_id", "personal_input_items", ["user_id"])
    _create_index_once("ix_personal_input_items_item_type", "personal_input_items", ["item_type"])
    _create_index_once("ix_personal_input_items_language", "personal_input_items", ["language"])
    _create_index_once("ix_personal_input_items_user_type", "personal_input_items", ["user_id", "item_type"])

    if not _has_table("graphic_novel_scenes"):
        op.create_table(
            "graphic_novel_scenes",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("atelier_session_id", uuid_type, nullable=True),
            sa.Column("mission_id", uuid_type, nullable=True),
            sa.Column("personal_input_item_id", uuid_type, nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="available"),
            sa.Column("cadence", sa.String(length=30), nullable=False, server_default="ad_hoc"),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("brief", sa.Text(), nullable=False),
            sa.Column("selected_concept_ids", json_type, nullable=False),
            sa.Column("target_errata_ids", json_type, nullable=False),
            sa.Column("target_vocabulary_ids", json_type, nullable=False),
            sa.Column("source_snapshot", json_type, nullable=False),
            sa.Column("script_payload", json_type, nullable=False),
            sa.Column("recap_payload", json_type, nullable=False),
            sa.Column("cache_key", sa.String(length=96), nullable=False),
            sa.Column("prompt_version", sa.String(length=80), nullable=False),
            sa.Column("image_model", sa.String(length=100), nullable=False),
            sa.Column("image_quality", sa.String(length=40), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["atelier_session_id"], ["atelier_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["mission_id"], ["real_world_missions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["personal_input_item_id"], ["personal_input_items.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "cache_key", name="uq_graphic_novel_scene_cache"),
        )
    _create_index_once("ix_graphic_novel_scenes_user_id", "graphic_novel_scenes", ["user_id"])
    _create_index_once("ix_graphic_novel_scenes_atelier_session_id", "graphic_novel_scenes", ["atelier_session_id"])
    _create_index_once("ix_graphic_novel_scenes_mission_id", "graphic_novel_scenes", ["mission_id"])
    _create_index_once("ix_graphic_novel_scenes_personal_input_item_id", "graphic_novel_scenes", ["personal_input_item_id"])
    _create_index_once("ix_graphic_novel_scenes_status", "graphic_novel_scenes", ["status"])
    _create_index_once("ix_graphic_novel_scenes_cadence", "graphic_novel_scenes", ["cadence"])
    _create_index_once("ix_graphic_novel_scenes_cache_key", "graphic_novel_scenes", ["cache_key"])
    _create_index_once("ix_graphic_novel_scenes_user_status", "graphic_novel_scenes", ["user_id", "status"])

    if not _has_table("graphic_novel_panels"):
        op.create_table(
            "graphic_novel_panels",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("scene_id", uuid_type, nullable=False),
            sa.Column("panel_index", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("beat", sa.Text(), nullable=False),
            sa.Column("image_prompt", sa.Text(), nullable=False),
            sa.Column("image_url", sa.Text(), nullable=True),
            sa.Column("image_payload", json_type, nullable=False),
            sa.Column("overlay_payload", json_type, nullable=False),
            sa.Column("generation_metadata", json_type, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["scene_id"], ["graphic_novel_scenes.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("scene_id", "panel_index", name="uq_graphic_novel_panel_index"),
        )
    _create_index_once("ix_graphic_novel_panels_scene_id", "graphic_novel_panels", ["scene_id"])
    _create_index_once("ix_graphic_novel_panels_scene_order", "graphic_novel_panels", ["scene_id", "panel_index"])

    if not _has_table("graphic_novel_attempts"):
        op.create_table(
            "graphic_novel_attempts",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("scene_id", uuid_type, nullable=False),
            sa.Column("panel_id", uuid_type, nullable=True),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("task_id", sa.String(length=120), nullable=False),
            sa.Column("task_type", sa.String(length=40), nullable=False),
            sa.Column("answer_payload", json_type, nullable=False),
            sa.Column("correction_payload", json_type, nullable=False),
            sa.Column("verdict", sa.String(length=30), nullable=False, server_default="needs_review"),
            sa.Column("score_0_4", sa.Float(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["panel_id"], ["graphic_novel_panels.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["scene_id"], ["graphic_novel_scenes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_once("ix_graphic_novel_attempts_scene_id", "graphic_novel_attempts", ["scene_id"])
    _create_index_once("ix_graphic_novel_attempts_panel_id", "graphic_novel_attempts", ["panel_id"])
    _create_index_once("ix_graphic_novel_attempts_user_id", "graphic_novel_attempts", ["user_id"])
    _create_index_once("ix_graphic_novel_attempts_scene_task", "graphic_novel_attempts", ["scene_id", "task_id"])


def downgrade() -> None:
    op.drop_table("graphic_novel_attempts", if_exists=True)
    op.drop_table("graphic_novel_panels", if_exists=True)
    op.drop_table("graphic_novel_scenes", if_exists=True)
    op.drop_table("personal_input_items", if_exists=True)
