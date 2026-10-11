"""WP-124b walk checks: lost days cannot stall the season.

Read a life record of :mod:`tests.experience_walk` (``record["days"][i]["journey"]``
is the day's transcript; ``record["days"][i]["season"]`` the season cursor after
the day, from :func:`tests.experience_walk.season_cursor`).

* :func:`check_reprise_runs` — never more than ``MAX_CONSECUTIVE_REPRISES`` WP-124a
  reprises (``season_reprise:<page>``) on consecutive days of a life: the next lost
  day of a run is the authored continuation. A reprise of the finale (``t8.*``) is
  exempt: after the season there is nothing left to stall (WP-132B's epilogue).
* :func:`check_season_cursor` — the season only moves forward: the played log never
  shrinks, the last played day never moves back in the season's calendar, and a gap
  once recorded as shortened stays recorded.

Wire into ``tests/test_experience_walk.py`` beside the other life checks:
``problems += walk_checks_wp124b.check_life_wp124b(record)``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.services.season.recovery import MAX_CONSECUTIVE_REPRISES

REPRISE_PREFIX = "season_reprise:"
#: Reprises of the finale's pages: the season is over, the epilogue owns the day.
AFTER_FINALE_PAGES = ("t8.",)


def _key(day: dict[str, Any]) -> str:
    return str((((day.get("journey") or {}).get("scenario")) or {}).get("scenario_key") or "")


def check_reprise_runs(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    run: list[int] = []
    for day in record.get("days") or []:
        key = _key(day)
        page = key[len(REPRISE_PREFIX):] if key.startswith(REPRISE_PREFIX) else None
        if page is None or page.startswith(AFTER_FINALE_PAGES):
            run = []
            continue
        run.append(int(day.get("day") or 0))
        if len(run) == MAX_CONSECUTIVE_REPRISES + 1:
            problems.append(
                f"{record.get('persona')} {record.get('quality')} days {run[0]}–{run[-1]}: "
                f"{len(run)} reprises in a row of «{page}» — the season stalls (WP-124b allows {MAX_CONSECUTIVE_REPRISES})"
            )
    return problems


@lru_cache(maxsize=4)
def _calendar_index(season_id: str) -> dict[str, int]:
    from app.services.season.clock import nominal_calendar
    from app.services.season.format import load_season

    return {row["key"]: index for index, row in enumerate(nominal_calendar(load_season(season_id)))}


def _order(season_id: str, key: str | None) -> int:
    """A played key's place in the season: its segment's first nominal day (a gap
    day beyond the nominal length — the weekend flex — keeps its segment's place)."""

    if not key:
        return -1
    index = _calendar_index(season_id)
    if key in index:
        return index[key]
    segment = key.split(".", 1)[0]
    return max((value for name, value in index.items() if name.split(".", 1)[0] == segment), default=-1)


def check_season_cursor(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    previous: dict[str, Any] | None = None
    for day in record.get("days") or []:
        cursor = day.get("season")
        if not isinstance(cursor, dict) or not cursor.get("id"):
            continue
        if previous is not None:
            season_id = str(cursor["id"])
            if int(cursor.get("played") or 0) < int(previous.get("played") or 0):
                problems.append(f"{who} day {day.get('day')}: the season's played log shrank ({previous.get('played')} → {cursor.get('played')})")
            if _order(season_id, cursor.get("last")) < _order(season_id, previous.get("last")):
                problems.append(f"{who} day {day.get('day')}: the season moved back ({previous.get('last')} → {cursor.get('last')})")
            lost = set(previous.get("shortened") or []) - set(cursor.get("shortened") or [])
            if lost:
                problems.append(f"{who} day {day.get('day')}: a shortened gap is no longer recorded ({sorted(lost)})")
        previous = cursor
    return problems


def check_life_wp124b(record: dict[str, Any]) -> list[str]:
    return check_reprise_runs(record) + check_season_cursor(record)


__all__ = ["check_life_wp124b", "check_reprise_runs", "check_season_cursor"]
