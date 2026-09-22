"""WP-74 — the GDPR export covers every table that holds a learner's content.

The hand-written export in ``users.py`` knew six tables; the journal, missions,
intake artefacts, rehearsals, the living story, the Courrier, placement and the
daily journeys were all missing. Rather than add another hand-picked list that
drifts the next time a table is born, this walks the mapped metadata:

* every table with a ``user_id`` foreign key to ``users`` is exported, filtered
  to *this* learner, unless it is in :data:`EXCLUDED_USER_TABLES` with a reason;
* a few child tables that hold the learner's own words but carry no ``user_id``
  (chat messages, review logs, journey steps, serial episodes) are exported
  through their owning row (:data:`CHILD_TABLES`);
* columns that are secrets (hashes, tokens, keys) are never written out;
* each table is bounded to :data:`MAX_ROWS_PER_TABLE`, newest first, and says
  when it was truncated.

``tests/test_wp74_gdpr_export.py`` fails when a new user-linked table appears
without being exported or explicitly excluded.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Table, inspect, select
from sqlalchemy.orm import Session

from app.db.base import Base

MAX_ROWS_PER_TABLE = 1000

#: User-linked tables deliberately left out, with the reason.
EXCLUDED_USER_TABLES: dict[str, str] = {
    "refresh_tokens": "authentication secrets (token hashes); not learner content",
    "push_subscriptions": "device push endpoint and encryption keys; credentials, not learner content",
}

#: Child tables with learner content but no user_id: table -> (fk column, parent table).
CHILD_TABLES: dict[str, tuple[str, str]] = {
    "conversation_messages": ("session_id", "learning_sessions"),
    "review_logs": ("progress_id", "user_vocabulary_progress"),
    "daily_journey_steps": ("journey_id", "daily_journeys"),
    "serial_episodes": ("thread_id", "serial_threads"),
}

#: Child tables left out, with the reason.
EXCLUDED_CHILD_TABLES: dict[str, str] = {
    "graphic_novel_panels": "generated artwork and prompts; the learner's scene rows are exported",
    "book_episodes": "generated book text; the learner's user_books rows are exported",
}

_SECRET_COLUMN = re.compile(r"(password|hash|token|secret|api_key|p256dh|auth_key)", re.IGNORECASE)


def _load_models() -> None:
    import app.db.models as models_pkg

    for module in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"{models_pkg.__name__}.{module.name}")


def user_linked_tables() -> dict[str, Table]:
    """Every mapped table with a ``user_id`` foreign key to ``users``."""

    _load_models()
    linked: dict[str, Table] = {}
    for table in Base.metadata.tables.values():
        column = table.columns.get("user_id")
        if column is None:
            continue
        if any(fk.column.table.name == "users" for fk in column.foreign_keys):
            linked[table.name] = table
    return linked


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _exportable_columns(table: Table) -> list:
    return [column for column in table.columns if not _SECRET_COLUMN.search(column.name)]


def _order(table: Table):
    for name in ("created_at", "occurred_at", "updated_at", "id"):
        column = table.columns.get(name)
        if column is not None:
            return column.desc()
    return None


def _rows(db: Session, table: Table, where) -> dict[str, Any]:
    columns = _exportable_columns(table)
    query = select(*columns).where(where)
    order = _order(table)
    if order is not None:
        query = query.order_by(order)
    result = db.execute(query.limit(MAX_ROWS_PER_TABLE + 1)).mappings().all()
    truncated = len(result) > MAX_ROWS_PER_TABLE
    return {
        "rows": [{key: _jsonable(value) for key, value in row.items()} for row in result[:MAX_ROWS_PER_TABLE]],
        "truncated": truncated,
    }


def export_learner_records(db: Session, *, user_id: Any) -> dict[str, Any]:
    """Every learner-content table for ``user_id``, keyed by table name."""

    tables = user_linked_tables()
    # A database a migration has not reached yet may lack a table; say so
    # rather than fail the whole export.
    present = set(inspect(db.get_bind()).get_table_names())
    records: dict[str, Any] = {}
    missing: list[str] = []
    for name in sorted(tables):
        if name in EXCLUDED_USER_TABLES:
            continue
        if name not in present:
            missing.append(name)
            continue
        table = tables[name]
        records[name] = _rows(db, table, table.columns["user_id"] == user_id)
    metadata = Base.metadata.tables
    for name, (fk_column, parent_name) in sorted(CHILD_TABLES.items()):
        child = metadata.get(name)
        parent = metadata.get(parent_name)
        if child is None or parent is None:
            continue
        if name not in present or parent_name not in present:
            missing.append(name)
            continue
        parent_ids = select(parent.columns["id"]).where(parent.columns["user_id"] == user_id)
        records[name] = _rows(db, child, child.columns[fk_column].in_(parent_ids))
    return {
        "tables": records,
        "excluded": {**EXCLUDED_USER_TABLES, **EXCLUDED_CHILD_TABLES},
        "not_in_database": missing,
        "max_rows_per_table": MAX_ROWS_PER_TABLE,
    }


__all__ = [
    "CHILD_TABLES",
    "EXCLUDED_CHILD_TABLES",
    "EXCLUDED_USER_TABLES",
    "MAX_ROWS_PER_TABLE",
    "export_learner_records",
    "user_linked_tables",
]
