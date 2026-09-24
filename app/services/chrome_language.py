"""The one-language rule, server side (mirror of web-frontend/lib/language-rule.ts).

* Up to A2, the app's own words (instructions, status, "why this" lines, a
  letter's objective) are in the learner's language: ``native_language``
  folded onto en / de / fr.
* From B1, the chrome is French too.
* Story and letter *content* is French at every level and never passes
  through here.

Server-sent chrome is served as a ``{fr, en, de}`` table alongside the resolved
string, so the client can re-apply the same rule with the level it knows best.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.journey_contracts import ControlLanguage, normalize_control_language

_BANDS = ("A1", "A2", "B1", "B2", "C1", "C2")


def level_band(level: Any) -> str | None:
    """«A1.1», «b2», « B1 » → the CEFR band; anything else → ``None``."""
    if not isinstance(level, str):
        return None
    match = re.match(r"^([ABC][12])", level.strip().upper())
    return match.group(1) if match and match.group(1) in _BANDS else None


def french_chrome(level: Any) -> bool:
    """B1 and above read French chrome. An unknown level is treated as a beginner."""
    band = level_band(level)
    return band is not None and _BANDS.index(band) >= _BANDS.index("B1")


def chrome_language(native_language: Any, level: Any = None) -> ControlLanguage:
    """The language the app's own words are written in for this learner."""
    if french_chrome(level):
        return "fr"
    return normalize_control_language(native_language if isinstance(native_language, str) else None)


def user_chrome_language(user: Any) -> ControlLanguage:
    """``chrome_language`` for a ``User`` row (or anything shaped like one)."""
    if user is None:
        return "fr"
    level = getattr(user, "cefr_estimate", None) or getattr(user, "proficiency_level", None)
    return chrome_language(getattr(user, "native_language", None), level)


def pick(table: dict[str, str] | None, language: str, *, default: str = "fr") -> str:
    """The entry for ``language``; else the default language's; else any."""
    table = {k: v for k, v in (table or {}).items() if isinstance(v, str) and v.strip()}
    if not table:
        return ""
    return table.get(language) or table.get(default) or next(iter(table.values()))


__all__ = ["chrome_language", "french_chrome", "level_band", "pick", "user_chrome_language"]
