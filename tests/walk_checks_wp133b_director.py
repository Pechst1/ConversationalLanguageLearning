"""WP-133b walk checks: the director fixes of the live read of 2026-10-06.

* :func:`check_season_tu_register` (life record): on a generated day, a season
  cast member whose register with the learner is always «tu» (``season.json`` cast
  ``address``, no ``register.<id>`` flag) never speaks to them only in «vous» — run 1,
  day 3: Margaux «Je suis Margaux et vous êtes… ?». Authored pages are not judged:
  T1 A is the first meeting, where Marin still says «vous».
* :func:`check_gendered_learner_nouns` (day transcript): no cast line names the
  learner with a gendered person noun («Vous êtes l'héritier ?»).
* :func:`check_departed_after_finale` (life record of ``tests/experience_walk``):
  once a life has played the finale (T8 B), no generated page stages Lila — she
  left for Berlin on every ending (run 8, day 62). Margaux's departure depends on
  the ending, which a life record does not carry; the engine guard covers it.

Wire into ``tests/walk_checks.CHECKS`` / ``check_life`` (see the WP-133b report).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: A re-read day (WP-124a reprise) is authored text, never judged here.
REPRISE_PREFIX = "season_reprise:"


@lru_cache(maxsize=1)
def _always_tu() -> frozenset[str]:
    season = json.loads((ROOT / "app" / "data" / "season" / "s1" / "season.json").read_text(encoding="utf-8"))
    flagged = {str(row.get("id") or "").removeprefix("register.") for row in season.get("flags") or []}
    return frozenset(
        member["id"] for member in season.get("cast") or [] if member.get("address") == "tu" and member["id"] not in flagged
    )


def _page_lines(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        line
        for event in transcript.get("events") or []
        for panel in event.get("page") or []
        for line in panel.get("dialogue") or []
        if isinstance(line, dict)
    ]


def _finale_played(last: str) -> bool:
    return last == "t8.b" or last.startswith("e")


def generated_days(record: dict[str, Any]) -> list[tuple[int, dict[str, Any], bool]]:
    """``(day, journey, after_finale)`` for each generated page of a life: a gap day
    (the season log gained a ``g…`` key) or, after the finale, a day that played no
    season page (the continuation). Re-read days are left out."""

    rows: list[tuple[int, dict[str, Any], bool]] = []
    played_before, finale = 0, False
    for day in record.get("days") or []:
        season = day.get("season") or {}
        journey = day.get("journey") or {}
        played, last = int(season.get("played") or 0), str(season.get("last") or "")
        key = str((journey.get("scenario") or {}).get("scenario_key") or "")
        moved = played > played_before
        if not key.startswith(REPRISE_PREFIX) and ((moved and last.startswith("g")) or (finale and not moved)):
            rows.append((int(day.get("day") or 0), journey, finale))
        played_before = max(played_before, played)
        finale = finale or _finale_played(last)
    return rows


def check_season_tu_register(record: dict[str, Any]) -> list[str]:
    from app.services.living_story import _PLURAL_VOUS, _address_register

    problems = []
    for day, journey, _after in generated_days(record):
        by_speaker: dict[str, list[str]] = {}
        for line in _page_lines(journey):
            text = str(line.get("text_fr") or "")
            if text and not _PLURAL_VOUS.search(text):
                by_speaker.setdefault(str(line.get("character_id") or ""), []).append(text)
        problems += [
            f"day {day}: {speaker} says «tu» to the learner in this season, "
            f"but only «vous» on this page («{lines[0][:60]}»)"
            for speaker, lines in sorted(by_speaker.items())
            if speaker in _always_tu() and _address_register(lines) == "vous"
        ]
    return problems


def check_gendered_learner_nouns(transcript: dict[str, Any]) -> list[str]:
    from app.services.living_story import (
        _FEMININE_PERSON_NOUNS,
        _MASCULINE_PERSON_NOUNS,
        _folded,
        _person_noun_hits,
    )

    said = [str(line.get("text_fr") or "") for line in _page_lines(transcript)]
    said += [
        str((event.get("result") or {}).get("character_reply_fr") or "") for event in transcript.get("events") or []
    ]
    problems = []
    for text in said:
        hits = _person_noun_hits(f" {_folded(text)} ", _MASCULINE_PERSON_NOUNS + _FEMININE_PERSON_NOUNS)
        if hits:
            problems.append(f"day {transcript.get('day')}: «{hits[0]}» genders the learner («{text[:80]}»)")
    return problems


def check_departed_after_finale(record: dict[str, Any]) -> list[str]:
    problems = []
    for day, journey, after in generated_days(record):
        if not after:
            continue
        speakers = {str(line.get("character_id") or "") for line in _page_lines(journey)}
        if "lila_bonnet" in speakers or (journey.get("scenario") or {}).get("character_name") == "Lila Bonnet":
            problems.append(f"day {day}: Lila is on a generated page after the finale (she is in Berlin)")
    return problems
