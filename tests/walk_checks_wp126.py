"""WP-126 / WP-127 — life-walk invariants for the starting point, the offer and the check.

Each function takes one life record of :mod:`tests.experience_walk` (the shape
``tests/test_experience_walk.py::live`` builds) and returns problems as strings,
like :func:`tests.walk_checks.check_life`.

* :func:`check_band_check_visits` — no visit of the vocabulary check shows more
  than 48 items (two 24-item checks), the WP-127 bound;
* :func:`check_new_life_offer` — a learner who declared «Nouveau» (an A1 life) is
  never offered the placement on own-band evidence: an unsolicited offer needs
  three earlier days served *above* A1;
* :func:`check_declared_day_one` — a B2 or C1 life's day one is played at the
  declared band, not at B1.1.
"""
from __future__ import annotations

from typing import Any

#: WP-127: two checks of 24 items.
MAX_VISIT_ITEMS = 48
#: placement.JOURNEY_EVIDENCE_MET_UNAIDED — distinct above-band days.
ABOVE_BAND_DAYS = 3
_ORDER = ("A1", "A2", "B1", "B2", "C1", "C2")


def _rank(band: Any) -> int:
    coarse = str(band or "").upper()[:2]
    return _ORDER.index(coarse) if coarse in _ORDER else -1


def check_band_check_visits(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    for day in record.get("days") or []:
        checks = day.get("band_check") or []
        items = sum(int(check.get("item_count") or 0) for check in checks)
        if items > MAX_VISIT_ITEMS:
            problems.append(
                f"{who} day {day.get('day')}: one vocabulary-check visit showed {items} items "
                f"(at most {MAX_VISIT_ITEMS}): {[c.get('sub_band') for c in checks]}"
            )
    return problems


def check_new_life_offer(record: dict[str, Any]) -> list[str]:
    if _rank(record.get("true_level")) != 0:
        return []
    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    above_days = 0
    for day in record.get("days") or []:
        journey = day.get("journey") or {}
        band = (journey.get("scenario") or {}).get("level_band") or journey.get("learner_level")
        if _rank(band) > 0:
            above_days += 1
        offer = day.get("placement_offer") or {}
        if not offer.get("offer") or offer.get("reason") == "resume":
            continue
        if offer.get("reason") != "journey_evidence" or above_days < ABOVE_BAND_DAYS:
            problems.append(
                f"{who} day {day.get('day')}: a «Nouveau» learner was offered the placement "
                f"(reason {offer.get('reason')!r}) after {above_days} day(s) above A1"
            )
    return problems


def check_declared_day_one(record: dict[str, Any]) -> list[str]:
    declared = str(record.get("true_level") or "")[:2].upper()
    if _rank(declared) < _rank("B2"):
        return []
    days = record.get("days") or []
    if not days:
        return []
    journey = days[0].get("journey") or {}
    problems: list[str] = []
    who = f"{record.get('persona')} {record.get('quality')}"
    level = str(journey.get("learner_level") or "")
    band = str((journey.get("scenario") or {}).get("level_band") or "")
    if level[:2].upper() != declared or band[:2].upper() != declared:
        problems.append(
            f"{who} day 1: a learner who declared {declared} played day one at "
            f"level {level or '?'} / scene band {band or '?'}"
        )
    return problems


def check_life_wp126(record: dict[str, Any]) -> list[str]:
    return check_band_check_visits(record) + check_new_life_offer(record) + check_declared_day_one(record)


__all__ = [
    "MAX_VISIT_ITEMS",
    "check_band_check_visits",
    "check_declared_day_one",
    "check_life_wp126",
    "check_new_life_offer",
]
