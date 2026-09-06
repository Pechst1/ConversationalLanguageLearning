"""The daily journey migration must match the models it is supposed to create.

A live upgrade/downgrade cycle needs PostgreSQL (the revision uses `JSONB` and
`postgresql.UUID`) and is therefore **not** exercised here — see the WP-02
handoff. What is exercised is the part that silently rots: column parity with
the ORM models, the uniqueness rules, and a downgrade that really drops
everything the upgrade created.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa

from app.db.models.daily_journey import (
    DailyJourney,
    DailyJourneyMutation,
    DailyJourneyStep,
)

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "e2f3a4b5c6d7_add_daily_journeys.py"
)


class RecordingOp:
    """Stands in for ``alembic.op`` so the revision can be replayed offline."""

    def __init__(self) -> None:
        self.tables: dict[str, list[Any]] = {}
        self.indexes: list[dict[str, Any]] = []
        self.dropped_tables: list[str] = []
        self.dropped_indexes: list[str] = []

    def create_table(self, name: str, *items: Any, **_kwargs: Any) -> None:
        self.tables[name] = list(items)

    def create_index(
        self, name: str, table: str, columns: list[str], **kwargs: Any
    ) -> None:
        self.indexes.append(
            {"name": name, "table": table, "columns": columns, **kwargs}
        )

    def drop_table(self, name: str) -> None:
        self.dropped_tables.append(name)

    def drop_index(self, name: str, table_name: str | None = None) -> None:
        self.dropped_indexes.append(name)


@pytest.fixture(scope="module")
def replayed() -> RecordingOp:
    spec = importlib.util.spec_from_file_location("wp02_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder = RecordingOp()
    module.op = recorder  # type: ignore[attr-defined]
    module.upgrade()
    module.downgrade()
    return recorder


def _columns(recorder: RecordingOp, table: str) -> set[str]:
    return {
        item.name for item in recorder.tables[table] if isinstance(item, sa.Column)
    }


def test_revision_identifiers_are_the_assigned_ones() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "e2f3a4b5c6d7"' in source
    assert 'down_revision = "d1e2f3a4b5c6"' in source


@pytest.mark.parametrize(
    ("table", "model"),
    [
        ("daily_journeys", DailyJourney),
        ("daily_journey_steps", DailyJourneyStep),
        ("daily_journey_mutations", DailyJourneyMutation),
    ],
)
def test_migration_columns_match_the_model(
    replayed: RecordingOp, table: str, model: Any
) -> None:
    assert _columns(replayed, table) == set(model.__table__.columns.keys())


def test_the_migration_is_additive(replayed: RecordingOp) -> None:
    """Three new tables and nothing else: no altered or backfilled existing row."""

    assert set(replayed.tables) == {
        "daily_journeys",
        "daily_journey_steps",
        "daily_journey_mutations",
    }


def test_uniqueness_rules_are_created(replayed: RecordingOp) -> None:
    journey_constraints = {
        item.name
        for item in replayed.tables["daily_journeys"]
        if isinstance(item, sa.UniqueConstraint)
    }
    assert "uq_daily_journeys_user_date" in journey_constraints

    step_constraints = {
        item.name
        for item in replayed.tables["daily_journey_steps"]
        if isinstance(item, sa.UniqueConstraint)
    }
    assert "uq_daily_journey_steps_journey_ordinal" in step_constraints

    receipt_constraints = {
        item.name
        for item in replayed.tables["daily_journey_mutations"]
        if isinstance(item, sa.UniqueConstraint)
    }
    assert "uq_daily_journey_mutations_user_scope_key" in receipt_constraints

    open_journey = next(
        index
        for index in replayed.indexes
        if index["name"] == "uq_daily_journeys_one_open_per_user"
    )
    assert open_journey["unique"] is True
    assert open_journey["columns"] == ["user_id"]
    # Partial: the constraint must only bind preparing/active/paused journeys,
    # never a completed one.
    where = str(open_journey["postgresql_where"])
    assert "preparing" in where and "active" in where and "paused" in where
    assert "completed" not in where


def test_ownership_cascades_are_declared(replayed: RecordingOp) -> None:
    def foreign_keys(table: str) -> dict[str, str]:
        return {
            constraint.column_keys[0]: (constraint.ondelete or "")
            for constraint in replayed.tables[table]
            if isinstance(constraint, sa.ForeignKeyConstraint)
        }

    journeys = foreign_keys("daily_journeys")
    assert journeys["user_id"] == "CASCADE"
    # A deleted learning session must not delete the learner's journey.
    assert journeys["learning_session_id"] == "SET NULL"
    assert foreign_keys("daily_journey_steps")["journey_id"] == "CASCADE"
    receipts = foreign_keys("daily_journey_mutations")
    assert receipts["user_id"] == "CASCADE"
    assert receipts["journey_id"] == "CASCADE"


def test_downgrade_drops_everything_the_upgrade_created(
    replayed: RecordingOp,
) -> None:
    assert set(replayed.dropped_tables) == set(replayed.tables)
    assert set(replayed.dropped_indexes) == {
        index["name"] for index in replayed.indexes
    }
