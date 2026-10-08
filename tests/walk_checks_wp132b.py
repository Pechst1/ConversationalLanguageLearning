"""WP-132B walk check: a season life never meets the old serial's later seasons.

Content program D8: «The old Berlin S2 bible is never loaded after s1.» After the
finale a season life reads its epilogue (or the archive day), then a continuation in
s1's own world. This check reads a day transcript of :mod:`tests.learner_walk` and
fires when anything the learner was shown comes from the old serial's authored
seasons 2 and 3 (``app/prompts/serial/world_bible_paris_s2.json`` / ``_s3.json``):
their season titles and loglines, or the character only they add.

Wire into ``tests/walk_checks.CHECKS`` (see the WP-132B report).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OLD_SEASONS = ("world_bible_paris_s2.json", "world_bible_paris_s3.json")


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
def old_season_markers() -> tuple[str, ...]:
    """The old seasons' titles and loglines, and the names of the cast only they add."""

    found: set[str] = set()
    for name in OLD_SEASONS:
        path = ROOT / "app" / "prompts" / "serial" / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("season_title_fr", "season_logline_fr"):
            if data.get(key):
                found.add(_fold(data[key]))
        for member in data.get("cast_additions") or []:
            for part in str((member or {}).get("name") or "").split():
                if len(part) >= 4 and part[:1].isupper():
                    found.add(_fold(part))
    return tuple(sorted(found))


def check_no_old_serial_season(transcript: dict[str, Any]) -> list[str]:
    """A day of a season life shows nothing of the old serial's seasons 2 and 3."""

    shown = [
        *_strings(transcript.get("scenario") or {}),
        *[text for event in transcript.get("events") or [] for text in _strings((event.get("step") or {}).get("prompt") or {})],
        *[text for event in transcript.get("events") or [] for text in _strings(event.get("result") or {})],
    ]
    folded = [_fold(text) for text in shown if isinstance(text, str) and text.strip()]
    problems = []
    for marker in old_season_markers():
        hit = next((text for text in folded if marker in text), None)
        if hit is not None:
            problems.append(
                f"day {transcript.get('day')}: the old serial's later season is on the page («{marker}» in «{hit[:80]}»)"
            )
    return problems
