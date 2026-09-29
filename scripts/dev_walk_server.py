#!/usr/bin/env python
"""E-3 · the walk harness's API: the fake story engine plus the test-only clock.

``scripts/dev_story_engine_server.py`` (every provider key faked, the throwaway-database
guard, the fake director) with ``ATELIER_TEST_CLOCK_ENABLED`` on, so
``POST /api/v1/dev/test-clock {"offset_days": n}`` moves the server's "today" and the
walk can play days 2..7 in minutes. ``APP_ENV`` is forced to ``development``: the clock
refuses to exist in production. ``--live`` is deliberately NOT offered here.

    DATABASE_URL=postgresql://localhost/atelier_walk_XXXX \
        venv/bin/python scripts/dev_walk_server.py --port 8021
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["ATELIER_TEST_CLOCK_ENABLED"] = "true"
os.environ["APP_ENV"] = "development"
os.environ.setdefault("ATELIER_DAILY_JOURNEY_COHORT", "*")
os.environ.setdefault("SCHEMA_GUARD_ENABLED", "true")

import dev_story_engine_server  # noqa: E402

if __name__ == "__main__":
    dev_story_engine_server.main()
