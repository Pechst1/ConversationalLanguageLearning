"""WP-128 — life-walk invariants for the time budget.

Each function takes one life record of :mod:`tests.experience_walk` (the shape
``tests/test_experience_walk.py::live`` builds, with ``day["time_budget"]`` from
:func:`tests.experience_walk.day_time_estimate`) and returns problems as strings,
like :func:`tests.walk_checks.check_life`.

* :func:`check_core_day_fits` — ordinary core days (the journey, timed by the
  walk's own Timer, never by the planner) fit the selected rhythm within 20 %:
  at most :data:`OUTLIER_SHARE` of a life's ordinary days may run over, and
  none past :data:`HARD_CEILING` × the rhythm. A day the plan flagged a *longer
  day* before Start is exempt. (The outliers are a distribution's tail — a
  tentpole whose character answers at length, a reply that uses the repair
  slot as one more exchange — reported, never averaged away.)
* :func:`check_one_core_number` — once the day is planned, Home's estimate is
  the plan's core, and the ending carries the same number; before it, Home's
  core is the forecast the offer card prints.
"""
from __future__ import annotations

from typing import Any

#: WP-128: the tolerance over the selected rhythm.
TOLERANCE = 0.20
#: The walk's «struggling» learner is 1.4× slower than its Timer's base
#: (``experience_walk.SLOWER``). In the product, WP-L6's measured pace scales
#: that learner's plan after three days (``STEP_MULTIPLIER_BOUNDS`` up to 1.35);
#: the walk cannot feed it — its events carry real, not Timer, timestamps — so a
#: struggling life is held to the budget the trusted multiplier would allow.
UNMEASURED_SLOWNESS = {"struggling": 1.35}
#: At most this share of a life's ordinary days may run past the tolerance …
OUTLIER_SHARE = 0.10
#: … and none past this multiple of the rhythm.
HARD_CEILING = 2.0


def _who(record: dict[str, Any]) -> str:
    return f"{record.get('persona')} {record.get('quality')}"


def check_core_day_fits(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    slowness = UNMEASURED_SLOWNESS.get(str(record.get("quality")), 1.0)
    ordinary = 0
    over: list[str] = []
    for day in record.get("days") or []:
        journey = day.get("journey") or {}
        budget = int(journey.get("budget_seconds") or 0)
        seconds = float((((day.get("time") or {}).get("journey")) or {}).get("total") or 0.0)
        if not budget or not seconds:
            continue
        if (day.get("time_budget") or {}).get("longer_day"):
            continue
        ordinary += 1
        line = (
            f"day {day.get('day')}: {seconds / 60:.1f} min against a {budget / 60:.0f}-minute rhythm "
            f"(+{seconds / budget - 1:.0%}; estimate {journey.get('estimated_active_seconds')} s)"
        )
        if seconds > HARD_CEILING * budget * slowness:
            problems.append(f"{_who(record)} {line}: past {HARD_CEILING:.0f}× the rhythm, not flagged longer")
        elif seconds > (1 + TOLERANCE) * budget * slowness:
            over.append(line)
    if ordinary and len(over) > OUTLIER_SHARE * ordinary:
        problems.append(
            f"{_who(record)}: {len(over)} of {ordinary} ordinary days ran more than "
            f"{TOLERANCE:.0%} over the rhythm (at most {OUTLIER_SHARE:.0%}): " + "; ".join(over)
        )
    return problems


def check_one_core_number(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for day in record.get("days") or []:
        planned = day.get("time_budget") or {}
        core = planned.get("core_seconds")
        if core is None:
            continue
        home = (planned.get("home") or {}).get("core_seconds")
        if home != core:
            problems.append(
                f"{_who(record)} day {day.get('day')}: Home says {home} s, the plan's core is {core} s"
            )
        ending = planned.get("recap_core_seconds")
        if ending is not None and ending != core:
            problems.append(
                f"{_who(record)} day {day.get('day')}: the ending says {ending} s, the plan's core is {core} s"
            )
        une = day.get("la_une") or {}
        forecast = (une.get("time_estimate") or {}).get("core_seconds")
        offered = (une.get("available") or {}).get("estimated_seconds")
        if forecast is not None and offered is not None and forecast != offered:
            problems.append(
                f"{_who(record)} day {day.get('day')}: La Une's card says {offered} s, its estimate {forecast} s"
            )
    return problems


def check_life_wp128(record: dict[str, Any]) -> list[str]:
    return [*check_core_day_fits(record), *check_one_core_number(record)]


__all__ = ["HARD_CEILING", "OUTLIER_SHARE", "TOLERANCE", "check_core_day_fits", "check_life_wp128", "check_one_core_number"]
