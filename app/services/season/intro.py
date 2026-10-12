"""STORY-ORIENTATION (2026-10-12): what a learner reads before their first season page.

The owner's first run on a phone: «a new learner does not know where they are or
what they are in». The season's premise was written (``season.json`` ``logline``)
but never shown; the cast intro was only sent on the authored café first day, which
a learner who begins on the season never plays. So on the learner's first season
day the journey carries the season's own intro: the premise, how to play, and the
faces of the first night — from ``app/data/season/<id>/intro.json``.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.services.season.format import SEASON_ROOT


@lru_cache(maxsize=4)
def _intro(season_id: str) -> dict[str, Any]:
    path = SEASON_ROOT / season_id / "intro.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _localized(value: Any, language: str) -> str:
    if isinstance(value, dict):
        return str(value.get(language) or value.get("en") or "")
    return str(value or "")


#: The premise is repeated on the learner's first few season days: a new learner
#: who skipped a day, or forgot, still reads who they are before the «Précédemment».
PREMISE_DAYS = 3


def season_day(story_context: dict[str, Any] | None) -> int:
    """The learner's day of the season (1-based), or 0 off a season or on a reprise."""

    season = (story_context or {}).get("season")
    if not isinstance(season, dict) or season.get("reprise"):
        return 0
    position = season.get("position") if isinstance(season.get("position"), dict) else {}
    try:
        return int(position.get("season_day") or 0)
    except (TypeError, ValueError):
        return 0


def is_first_season_day(story_context: dict[str, Any] | None) -> bool:
    """Is today the learner's first day of an authored season (its first page, not a
    reprise of it)?"""

    season = (story_context or {}).get("season") or {}
    return season_day(story_context) == 1 and season.get("kind") == "tentpole"


def season_intro(season_id: str | None, language: str) -> dict[str, Any] | None:
    """``{premise_native, how_native, cast_intro}`` in the learner's language, or
    ``None`` when the season has no intro."""

    data = _intro(str(season_id or ""))
    if not data:
        return None
    cast = [
        {
            "character_id": str(row.get("character_id") or ""),
            "name": str(row.get("name") or ""),
            "role_native": _localized(row.get("role_native"), language),
            "line_fr": str(row.get("line_fr") or ""),
            "line_native": _localized(row.get("line_native"), language),
        }
        for row in data.get("cast") or []
        if isinstance(row, dict) and row.get("character_id")
    ]
    return {
        "premise_native": _localized(data.get("premise_native"), language) or None,
        "how_native": _localized(data.get("how_native"), language) or None,
        "cast_intro": cast,
    }
