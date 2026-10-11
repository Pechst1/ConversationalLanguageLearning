"""WP-130 B — the life walk's check that every held unit earned «Tenue».

``check_held_evidence_chain(record)`` reads a life record from
``tests/experience_walk.py`` (its last day's ``grammar_life``: the fields
``concept_life.held_conditions`` reads, as dates). For every unit marked held:

* two correct *independent* uses (``free_use_first`` / ``free_use_last`` are
  written only for an unassisted, correct production — a hint, a copied
  suggestion, a transform or a displayed example never writes them) on days at
  least seven days apart;
* a correct spaced item (``spaced_success``) at least fourteen days after the
  introduction — and so no unit held before day 14 of its introduction.

A ``spaced_success`` before day 14 is a fault for any unit, held or not (it
is written only from day 14). A unit the learner tested out of in La Forge
(``tested_out``, an open owner decision) is not judged here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

FREE_USE_GAP_DAYS = 7
SPACED_AFTER_DAYS = 14


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def check_held_evidence_chain(record: dict[str, Any]) -> list[str]:
    days = record.get("days") or []
    if not days:
        return []
    who = f"{record.get('persona')} {record.get('quality')}"
    problems: list[str] = []
    for unit in days[-1].get("grammar_life") or []:
        if unit.get("tested_out"):
            continue
        name = unit.get("unit")
        introduced = _day(unit.get("introduced"))
        spaced = _day(unit.get("spaced_success"))
        if introduced and spaced and (spaced - introduced).days < SPACED_AFTER_DAYS:
            problems.append(
                f"{who}: {name} has a spaced success {(spaced - introduced).days} days after its introduction"
            )
        held = _day(unit.get("held"))
        if held is None:
            continue
        first, last = _day(unit.get("free_use_first")), _day(unit.get("free_use_last"))
        if first is None or last is None or (last - first).days < FREE_USE_GAP_DAYS:
            problems.append(f"{who}: {name} is held without two independent uses ≥ 7 days apart ({first} … {last})")
        if spaced is None:
            problems.append(f"{who}: {name} is held without a spaced success")
        if introduced is None or (held - introduced).days < SPACED_AFTER_DAYS:
            problems.append(f"{who}: {name} is held on {held}, before day 14 of its introduction ({introduced})")
    return problems


__all__ = ["check_held_evidence_chain"]
