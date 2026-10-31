"""One way to put a stored datetime on the wire.

``datetime.isoformat()`` on a naive value prints no zone («2026-10-24T02:06:00»),
and a browser reads that as its own local clock. Several of our columns come
back naive (SQLite always, and any ``DateTime`` declared without a zone), so a
payload built with bare ``.isoformat()`` shows a Berlin learner the UTC hour.
Everything the app stores is UTC; say so on the wire.
"""
from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime | None) -> datetime | None:
    """The same instant, always timezone-aware (naive values are UTC)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_iso(value: datetime | None) -> str | None:
    """ISO-8601 with an explicit ``+00:00`` offset, or ``None``."""
    aware = as_utc(value)
    return aware.isoformat() if aware is not None else None
