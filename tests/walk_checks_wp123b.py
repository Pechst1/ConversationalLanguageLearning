"""WP-123b walk checks: La Forge, played from the after-day chip.

Read a life record of :mod:`tests.experience_walk`: ``record["days"][i]["forge"]``
is one séance played by :func:`tests.experience_walk.play_forge`, and
``record["days"][i]["time"]["forge"]`` its clock.

* :func:`check_forge_runs` — the séance opens, every answer is graded and it is
  filed (no 4xx/5xx on start, attempts or completion); it never serves more items
  than its own length; it ends (``finished``) once answered.
* :func:`check_forge_seats_the_chip` — the séance works on the rule the chip
  names (Home, the forge and the day's Règle agree: WP-S4's one picker).
* :func:`check_forge_fits_its_budget` — the séance takes no longer than
  :data:`BUDGET_TOLERANCE` × the chip's budget on the walk's clock.
* :func:`check_forge_language` — a German learner reads no English cue.
* :func:`check_forge_give_up` — «je ne sais pas» is never graded correct.

Wire into ``tests/test_experience_walk.py`` beside the other life checks:
``problems += walk_checks_wp123b.check_life_wp123b(record)``.
"""
from __future__ import annotations

import re
from typing import Any

#: The chip's séance may run over its budget by this factor at most (a struggling
#: learner reads 1.4× slower, and one item more than planned is not a defect).
BUDGET_TOLERANCE = 1.5

#: Words only an English sentence has (QA-FORGE's list, ``test_forge_qa_walk_de``).
ENGLISH = re.compile(
    r"\b(?:the|you|is|are|were|sentence|correct it|which|says|build|say in french|reply|"
    r"please|would|like|with|this|that|have|has|at the|in the)\b",
    re.IGNORECASE,
)
GIVE_UP = re.compile(r"\bje\s+ne\s+sais\s+pas\b", re.IGNORECASE)


def _seances(record: dict[str, Any]):
    who = f"{record.get('persona')} {record.get('quality')}"
    for day in record.get("days") or []:
        seance = day.get("forge")
        if seance:
            yield f"{who} day {day.get('day')}", day, seance


def check_forge_runs(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, _day, seance in _seances(record):
        if seance.get("start_status") not in (200, 201):
            problems.append(f"{label}: La Forge did not open ({seance.get('start_status')}): {seance.get('error')}")
            continue
        if seance.get("error"):
            problems.append(f"{label}: La Forge: {seance['error']}")
        bad = [item for item in seance.get("items") or [] if item.get("status_code") != 200]
        if bad:
            problems.append(f"{label}: La Forge refused {len(bad)} answer(s) ({bad[0].get('status_code')})")
        if seance.get("complete_status") != 200:
            problems.append(f"{label}: La Forge could not be filed ({seance.get('complete_status')})")
        length = int(seance.get("length") or 0)
        served = len(seance.get("items") or [])
        if length and served > length:
            problems.append(f"{label}: La Forge served {served} items for a séance of {length}")
        if served and not seance.get("finished"):
            problems.append(f"{label}: La Forge did not end after {served} answers (length {length})")
    return problems


def check_forge_seats_the_chip(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, _day, seance in _seances(record):
        offered = seance.get("offered_concept_id")
        rules = [rule for rule in seance.get("rules") or [] if rule is not None]
        if offered and rules and int(offered) not in {int(rule) for rule in rules}:
            problems.append(f"{label}: the chip named rule {offered}, the séance worked on {rules}")
    return problems


def check_forge_fits_its_budget(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, day, seance in _seances(record):
        budget = int(seance.get("budget_seconds") or 0)
        spent = float((((day.get("time") or {}).get("forge")) or {}).get("total") or 0.0)
        if budget and spent > BUDGET_TOLERANCE * budget:
            problems.append(f"{label}: La Forge took {spent / 60:.1f} min against a {budget / 60:.0f}-min chip")
    return problems


def check_forge_language(record: dict[str, Any]) -> list[str]:
    if record.get("native") != "de":
        return []
    problems: list[str] = []
    for label, _day, seance in _seances(record):
        for item in seance.get("items") or []:
            for cue in item.get("cues") or []:
                if " " in cue and ENGLISH.search(cue):
                    problems.append(f"{label}: English on a German learner's forge item ({item.get('round')}): {cue!r}")
    return problems


def check_forge_give_up(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, _day, seance in _seances(record):
        for item in seance.get("items") or []:
            if GIVE_UP.search(str(item.get("answer") or "")) and item.get("verdict") == "correct":
                problems.append(f"{label}: «je ne sais pas» graded correct on a forge {item.get('round')} item")
    return problems


def check_life_wp123b(record: dict[str, Any]) -> list[str]:
    return [
        *check_forge_runs(record),
        *check_forge_seats_the_chip(record),
        *check_forge_fits_its_budget(record),
        *check_forge_language(record),
        *check_forge_give_up(record),
    ]


__all__ = [
    "BUDGET_TOLERANCE",
    "check_forge_fits_its_budget",
    "check_forge_give_up",
    "check_forge_language",
    "check_forge_runs",
    "check_forge_seats_the_chip",
    "check_life_wp123b",
]
