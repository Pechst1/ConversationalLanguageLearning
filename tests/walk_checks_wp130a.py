"""WP-130 A — the life walk's check that the notebook and the level agree.

``check_progress_labels_agree(record)`` reads a life record from
``tests/experience_walk.py``: on every day whose Cahier holds the notebook
(days 1, 7, 14 and 30), the notebook's units of the level's band, counted per
state (``stage``: introduced · practising · held), must equal the level's own
counts (``coverage.units``), and no notebook label may call a unit held
(«tenue», «acquis», «gefestigt», «Solide» …) that the level does not hold.

It needs the notebook records to carry ``id``, ``stage``, ``stage_label`` and
``level_band`` and the whole catalogue (``limit=500``): see the patch to
``experience_walk.cahier`` in the WP-130 A report.
"""
from __future__ import annotations

import re
from typing import Any

STAGES = ("introduced", "practising", "held")
#: Words that claim *held*. «solide à l’entraînement» qualifies practice and is allowed.
HELD_CLAIM = re.compile(
    r"\b(tenue?s?|acquise?s?|acquis|maîtrisée?s?|held|mastered|gefestigt|gemeistert|solide|solid)\b", re.I
)
PRACTICE_QUALIFIERS = ("solide à l’entraînement", "solid in practice", "in der Übung sicher")


def _claims_held(label: str) -> bool:
    text = str(label or "")
    for allowed in PRACTICE_QUALIFIERS:
        text = text.replace(allowed, "")
    return bool(HELD_CLAIM.search(text))


def check_progress_labels_agree(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for day in record.get("days") or []:
        cahier = day.get("cahier") or {}
        notebook = cahier.get("notebook")
        if notebook is None:
            continue
        number = day.get("day")
        if notebook and not all("stage" in item and "level_band" in item for item in notebook):
            problems.append(f"day {number}: the notebook record carries no stage/level_band (walk recorder not patched)")
            continue
        for item in notebook:
            if item.get("stage") == "held":
                continue
            for key in ("state_label", "stage_label"):
                if _claims_held(item.get(key) or ""):
                    problems.append(
                        f"day {number}: «{item.get('display_title')}» is {item.get('stage')} "
                        f"but its {key} says «{item.get(key)}»"
                    )
        coverage = (cahier.get("cefr") or {}).get("coverage") or {}
        units = coverage.get("units") or {}
        band = coverage.get("band")
        if not band or "practising" not in units:
            continue
        in_band = [item for item in notebook if item.get("level_band") == band]
        if len(in_band) != int(units.get("total") or 0):
            problems.append(
                f"day {number}: the notebook shows {len(in_band)} units of {band}, the level counts {units.get('total')}"
            )
            continue
        notebook_counts = {stage: sum(1 for item in in_band if item.get("stage") == stage) for stage in STAGES}
        level_counts = {stage: int(units.get(stage) or 0) for stage in STAGES}
        if notebook_counts != level_counts:
            problems.append(f"day {number}: {band} notebook {notebook_counts} ≠ level {level_counts}")
    return problems


__all__ = ["check_progress_labels_agree"]
