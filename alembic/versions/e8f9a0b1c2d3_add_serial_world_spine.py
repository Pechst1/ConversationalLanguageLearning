"""Add serial world spine.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-05-31
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _offline_mode() -> bool:
    return bool(getattr(op.get_context(), "as_sql", False))


def _dialect_name() -> str:
    return str(getattr(op.get_context().dialect, "name", ""))


def _optional_fk_column(name: str, column_type: sa.types.TypeEngine, target: str) -> sa.Column:
    if _dialect_name() == "sqlite":
        return sa.Column(name, column_type, nullable=True)
    return sa.Column(name, column_type, sa.ForeignKey(target, ondelete="SET NULL"), nullable=True)


def _has_table(table_name: str) -> bool:
    if _offline_mode():
        return False
    return _inspector().has_table(table_name)


def _table_columns(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {column["name"] for column in _inspector().get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return index_name in {index["name"] for index in _inspector().get_indexes(table_name)}


def _add_column_if_missing(table_name: str, existing_columns: set[str], column: sa.Column) -> None:
    if column.name in existing_columns:
        return
    op.add_column(table_name, column)
    existing_columns.add(column.name)


def _create_index_once(index_name: str, table_name: str, columns: list[str]) -> None:
    if _offline_mode() or (_has_table(table_name) and not _has_index(table_name, index_name)):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _offline_mode() or _has_index(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _offline_mode() or column_name in _table_columns(table_name):
        op.drop_column(table_name, column_name)


def upgrade() -> None:
    json_type = postgresql.JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite")
    uuid_type = postgresql.UUID(as_uuid=True)

    if not _has_table("serial_threads"):
        op.create_table(
            "serial_threads",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("user_id", uuid_type, nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("world_bible", json_type, nullable=False),
            sa.Column("state", json_type, nullable=False),
            sa.Column("news_seed", json_type, nullable=False),
            sa.Column("current_episode_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_once("ix_serial_threads_user_id", "serial_threads", ["user_id"])
    _create_index_once("ix_serial_threads_status", "serial_threads", ["status"])
    _create_index_once("ix_serial_threads_user_status", "serial_threads", ["user_id", "status"])

    mission_columns = _table_columns("real_world_missions")
    _add_column_if_missing(
        "real_world_missions",
        mission_columns,
        _optional_fk_column("serial_thread_id", uuid_type, "serial_threads.id"),
    )
    _add_column_if_missing("real_world_missions", mission_columns, sa.Column("episode_index", sa.Integer(), nullable=True))
    _add_column_if_missing(
        "real_world_missions",
        mission_columns,
        sa.Column("stakes_level", sa.Integer(), nullable=False, server_default="1"),
    )
    _create_index_once("ix_real_world_missions_serial_thread_id", "real_world_missions", ["serial_thread_id"])

    scene_columns = _table_columns("graphic_novel_scenes")
    _add_column_if_missing(
        "graphic_novel_scenes",
        scene_columns,
        _optional_fk_column("serial_thread_id", uuid_type, "serial_threads.id"),
    )
    _add_column_if_missing("graphic_novel_scenes", scene_columns, sa.Column("episode_index", sa.Integer(), nullable=True))
    _create_index_once("ix_graphic_novel_scenes_serial_thread_id", "graphic_novel_scenes", ["serial_thread_id"])

    if not _has_table("serial_episodes"):
        op.create_table(
            "serial_episodes",
            sa.Column("id", uuid_type, nullable=False),
            sa.Column("thread_id", uuid_type, nullable=False),
            sa.Column("episode_index", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=30), nullable=False),
            sa.Column("mission_id", uuid_type, nullable=True),
            sa.Column("scene_id", uuid_type, nullable=True),
            sa.Column("location_id", sa.String(length=80), nullable=True),
            sa.Column("hook", json_type, nullable=False),
            sa.Column("hook_from_previous", json_type, nullable=False),
            sa.Column("state_delta", json_type, nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="available"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["mission_id"], ["real_world_missions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["scene_id"], ["graphic_novel_scenes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["thread_id"], ["serial_threads.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("thread_id", "episode_index", name="uq_serial_episode_thread_index"),
        )
    _create_index_once("ix_serial_episodes_thread_id", "serial_episodes", ["thread_id"])
    _create_index_once("ix_serial_episodes_kind", "serial_episodes", ["kind"])
    _create_index_once("ix_serial_episodes_mission_id", "serial_episodes", ["mission_id"])
    _create_index_once("ix_serial_episodes_scene_id", "serial_episodes", ["scene_id"])
    _create_index_once("ix_serial_episodes_location_id", "serial_episodes", ["location_id"])
    _create_index_once("ix_serial_episodes_status", "serial_episodes", ["status"])
    _create_index_once("ix_serial_episodes_thread_status", "serial_episodes", ["thread_id", "status"])


def downgrade() -> None:
    op.drop_table("serial_episodes", if_exists=True)
    _drop_index_if_exists("ix_graphic_novel_scenes_serial_thread_id", "graphic_novel_scenes")
    _drop_column_if_exists("graphic_novel_scenes", "episode_index")
    _drop_column_if_exists("graphic_novel_scenes", "serial_thread_id")
    _drop_index_if_exists("ix_real_world_missions_serial_thread_id", "real_world_missions")
    _drop_column_if_exists("real_world_missions", "stakes_level")
    _drop_column_if_exists("real_world_missions", "episode_index")
    _drop_column_if_exists("real_world_missions", "serial_thread_id")
    op.drop_table("serial_threads", if_exists=True)
