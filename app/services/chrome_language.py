"""The one-language rule, server side (mirror of web-frontend/lib/language-rule.ts).

S3 stage 1: this module is the only place that turns a stored language code
into a language. Two questions, two functions, never merged:

* **The interface language** — ``user_chrome_language(user)``: en / de / fr,
  level-aware (French from B1). Every instruction, status line and button.
* **The mother tongue** — ``user_mother_tongue(user)``: the learner's own
  language as a bare code (it may be ``es`` or ``it``), level-blind. Glosses,
  correction explanations and prompt lines that name the learner's language.

``fold_language`` (any code → en / de / fr, unknown → en) and
``mother_tongue`` (any code → bare lowercase code, empty → en) are the two
primitives under them; the old per-module normalisers are aliases of these.
``tests/test_one_language_resolver.py`` forbids reading ``native_language``
anywhere else.

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
from typing import Any, Literal

ControlLanguage = Literal["en", "de", "fr"]
SUPPORTED_CONTROL_LANGUAGES: tuple[ControlLanguage, ...] = ("en", "de", "fr")
FALLBACK_CONTROL_LANGUAGE: ControlLanguage = "en"

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


def mother_tongue(value: Any) -> str:
    """«en-GB», «DE», «pt_BR», None → a bare lowercase code; empty → ``en``.

    Any language survives (``es`` stays ``es``): this is the gloss and
    explanation language, not the interface one.
    """
    text = str(value or "").strip().lower()
    if not text:
        return FALLBACK_CONTROL_LANGUAGE
    return text.replace("_", "-").split("-", 1)[0] or FALLBACK_CONTROL_LANGUAGE


def fold_language(value: Any) -> ControlLanguage:
    """Any code onto the three languages the app is written in; unknown → ``en``."""
    code = mother_tongue(value)
    return code if code in SUPPORTED_CONTROL_LANGUAGES else FALLBACK_CONTROL_LANGUAGE  # type: ignore[return-value]


def localized(value: Any, language: Any) -> str:
    """A ``{en, de, fr}`` block in ``language``, falling back to English.

    A plain string is returned as it is (content that was authored once).
    """
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""
    for candidate in (fold_language(language), FALLBACK_CONTROL_LANGUAGE):
        text = value.get(candidate)
        if isinstance(text, str) and text.strip():
            return text
    return ""


def chrome_language(native_language: Any, level: Any = None) -> ControlLanguage:
    """The language the app's own words are written in for this learner."""
    if french_chrome(level):
        return "fr"
    return fold_language(native_language if isinstance(native_language, str) else None)


def user_chrome_language(user: Any) -> ControlLanguage:
    """``chrome_language`` for a ``User`` row (or anything shaped like one)."""
    if user is None:
        return "fr"
    level = getattr(user, "cefr_estimate", None) or getattr(user, "proficiency_level", None)
    return chrome_language(getattr(user, "native_language", None), level)


def user_mother_tongue(user: Any) -> str:
    """The learner's own language, level-blind: glosses, explanations, prompts.

    A bare code that may lie outside en / de / fr; ``en`` when unknown.
    """
    return mother_tongue(getattr(user, "native_language", None) if user is not None else None)


def user_mother_tongue_raw(user: Any) -> str | None:
    """The stored value as typed, for prompt lines that quote it («unknown» when unset)."""
    value = getattr(user, "native_language", None) if user is not None else None
    return value if isinstance(value, str) and value.strip() else None


def pick(table: dict[str, str] | None, language: str, *, default: str = "fr") -> str:
    """The entry for ``language``; else the default language's; else any."""
    table = {k: v for k, v in (table or {}).items() if isinstance(v, str) and v.strip()}
    if not table:
        return ""
    return table.get(language) or table.get(default) or next(iter(table.values()))


__all__ = [
    "FALLBACK_CONTROL_LANGUAGE",
    "SUPPORTED_CONTROL_LANGUAGES",
    "ControlLanguage",
    "chrome_language",
    "fold_language",
    "french_chrome",
    "level_band",
    "localized",
    "mother_tongue",
    "pick",
    "user_chrome_language",
    "user_mother_tongue",
    "user_mother_tongue_raw",
]
