"""Custom database column types for cross-database compatibility."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.types import Text, TypeDecorator


class StringList(TypeDecorator):
    """Persist a list of strings across PostgreSQL and SQLite."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_ARRAY(Text))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect):  # type: ignore[override]
        if value is None:
            return []
        if dialect.name == "postgresql":
            return value
        return json.loads(value)
