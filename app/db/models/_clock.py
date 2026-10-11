"""WP-123b — the application's clock for timestamps that are learning evidence.

``server_default=func.now()`` is the database's clock. The level forecast, the
CEFR signals (active days, recent errors and scores) and the reading-known words
read *when* a card, a unit, an attempt or an erratum was created, so those
columns also take a Python-side default from :func:`app_now`. In production the
two clocks agree; under ``app.core.test_clock`` (the life walk, the E-3 browser
walk) this module's ``datetime`` is swapped like every other ``app.*`` module's,
so a walk's day 20 writes day-20 timestamps instead of the real "now".

The ``server_default`` stays, for raw SQL inserts and the schema: no migration.
"""
from __future__ import annotations

from datetime import UTC, datetime


def app_now() -> datetime:
    """``datetime.now(UTC)``, looked up at call time (so the test clock can move it)."""

    return datetime.now(UTC)


__all__ = ["app_now"]
