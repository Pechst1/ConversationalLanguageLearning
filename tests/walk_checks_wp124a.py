"""WP-124a walk check: a lost day of a season life never leaves the season.

Reads a day transcript of :mod:`tests.learner_walk` (the walk plays season lives).

* No day of a season life is one of the three generic authored scenes
  (``order_at_cafe``, ``arrange_meeting``, ``explain_delay``), by key or by their
  openers («Tiens, bonjour ! Vous vous installez…», «Lila voudrait vous montrer le
  marché…», «Le métro reste bloqué…», «Margaux s'apprête à fermer…»).
* On a lost day (the WP-124a reprise, ``season_reprise:<page>``):
  - a cast member who says «tu» to the learner never says «vous» — unless the line
    is the season bible's own words (T1's Marin before the tutoiement, T5's
    Margaux to a group), which the reprise re-reads verbatim;
  - at A1, for an English or German learner, every line of the page has its
    translation (``text_native``).

Wire into ``tests/walk_checks.CHECKS`` (see the WP-124a report).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GENERIC_SCENARIO_KEYS = frozenset({"order_at_cafe", "arrange_meeting", "explain_delay"})
#: The stand-ins' openers the review quotes, kept literally as well as read from the files.
GENERIC_OPENERS = (
    "s'apprête à fermer",
    "voudrait vous montrer le marché",
    "le métro reste bloqué",
    "vous vous installez ou c'est à emporter",
)
REPRISE_PREFIX = "season_reprise:"
TRANSLATED_NATIVES = frozenset({"en", "de"})
_VOUS = re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE)


def _fold(text: Any) -> str:
    return " ".join(str(text or "").replace("’", "'").split()).casefold()


def _strings(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)


@lru_cache(maxsize=1)
def generic_lines() -> tuple[str, ...]:
    """The generic scenes' titles, setups and opening lines (four words or more)."""

    folder = ROOT / "app" / "data" / "journey_scenarios"
    found: set[str] = {_fold(opener) for opener in GENERIC_OPENERS}
    for path in folder.glob("*/*.json"):
        if path.stem not in GENERIC_SCENARIO_KEYS:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        stack: list[Any] = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    if key in ("setup_fr", "opening_line_fr", "title_fr") and isinstance(value, str):
                        if len(value.split()) >= 4:
                            found.add(_fold(value))
                    else:
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)
    return tuple(sorted(found))


@lru_cache(maxsize=1)
def bible_lines() -> frozenset[str]:
    """Every French string the season files hold (the owner-approved words)."""

    lines: set[str] = set()
    for path in (ROOT / "app" / "data" / "season" / "s1").glob("*.json"):
        for text in _strings(json.loads(path.read_text(encoding="utf-8"))):
            lines.add(_fold(text))
    return frozenset(lines)


@lru_cache(maxsize=1)
def tu_speakers() -> frozenset[str]:
    """Cast ids and display names of everyone who says «tu» to the learner."""

    data = json.loads((ROOT / "app" / "data" / "season" / "s1" / "season.json").read_text(encoding="utf-8"))
    out: set[str] = set()
    for member in data.get("cast") or []:
        if member.get("address") == "tu":
            out.add(str(member.get("id")))
            if member.get("name"):
                out.add(str(member["name"]))
    return frozenset(out)


def _said_lines(event: dict[str, Any]) -> list[tuple[str, str, str | None, str]]:
    """``(speaker, text_fr, text_native, where)`` of every line a character says."""

    out: list[tuple[str, str, str | None, str]] = []
    prompt = (event.get("step") or {}).get("prompt") or {}
    for source, panels in (("prompt", prompt.get("panels")), ("page", event.get("page"))):
        for index, panel in enumerate(panels or []):
            for line in (panel or {}).get("dialogue") or []:
                if isinstance(line, dict) and line.get("text_fr"):
                    out.append(
                        (str(line.get("character_id") or ""), str(line["text_fr"]), line.get("text_native"), f"{source}.panels[{index}]")
                    )
    result = event.get("result") or {}
    for line in result.get("character_lines") or []:
        if isinstance(line, dict) and line.get("text_fr"):
            out.append((str(line.get("speaker_id") or ""), str(line["text_fr"]), None, "reply"))
    return out


def check_lost_day_stays_in_season(transcript: dict[str, Any]) -> list[str]:
    if transcript.get("season_life") is False:
        return []
    problems: list[str] = []
    label = f"{transcript.get('persona')} {transcript.get('quality')} day {transcript.get('day')}"
    key = str((transcript.get("scenario") or {}).get("scenario_key") or "")
    if key in GENERIC_SCENARIO_KEYS:
        problems.append(f"{label}: a season life was served the generic scene {key!r}")
    openers = generic_lines()
    for index, event in enumerate(transcript.get("events") or []):
        for text in _strings([(event.get("step") or {}).get("prompt"), event.get("result"), event.get("page")]):
            folded = _fold(text)
            hit = next((line for line in openers if line in folded), None)
            if hit:
                problems.append(f"{label} #{index}: a generic stand-in line reached a season life: {text[:90]!r}")
    if not key.startswith(REPRISE_PREFIX):
        return problems
    tu = tu_speakers()
    bible = bible_lines()
    a1 = str(transcript.get("cefr") or "")[:2].upper() == "A1"
    translated = a1 and str(transcript.get("native") or "") in TRANSLATED_NATIVES
    for index, event in enumerate(transcript.get("events") or []):
        for speaker, text, native, where in _said_lines(event):
            if speaker in tu and _VOUS.search(text) and _fold(text) not in bible:
                problems.append(f"{label} #{index} {where}: {speaker} says «tu» to the learner but «vous» here: {text!r}")
            if translated and where != "reply" and not str(native or "").strip():
                problems.append(f"{label} #{index} {where}: an A1 line without its translation: {text!r}")
    return problems


__all__ = ["check_lost_day_stays_in_season", "generic_lines", "bible_lines", "tu_speakers"]
