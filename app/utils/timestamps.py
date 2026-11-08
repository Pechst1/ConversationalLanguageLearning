"""One way to put a stored datetime on the wire.

``datetime.isoformat()`` on a naive value prints no zone («2026-10-24T02:06:00»),
and a browser reads that as its own local clock. Several of our columns come
back naive (SQLite always, and any ``DateTime`` declared without a zone), so a
payload built with bare ``.isoformat()`` shows a Berlin learner the UTC hour.
Everything the app stores is UTC; say so on the wire.
"""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


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


def local_clock(value: datetime | None, zone_name: str | None) -> str | None:
    """«03 h 58»: the stored instant on the wall clock of ``zone_name`` (an IANA name).

    The server decides which clock a learner's messages are read on (the account's
    zone, the same one the streak day uses), so the page never has to guess it from
    the device. ``None`` when there is no time or no usable zone.
    """
    aware = as_utc(value)
    if aware is None or not zone_name:
        return None
    try:
        local = aware.astimezone(ZoneInfo(zone_name))
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return None
    return f"{local.hour:02d} h {local.minute:02d}"
