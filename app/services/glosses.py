"""One place that decides which translation a learner is shown.

The vocabulary table stores three columns (`german_translation`,
`english_translation`, `french_translation`) and the payload builders used to
read them in a hardcoded `german or english or french` order. That silently
served German to every learner, including the English default that signup ships
with, so a learner could be shown a gloss in a language they do not speak.

Resolution order here is: the learner's own language, then any other gloss that
exists, so a missing German entry never blanks a card for a German speaker.
`gloss_language` reports what was actually used, which lets a surface label a
fallback instead of pretending it is the learner's language.
"""
from __future__ import annotations

from typing import Any

# Columns that exist on VocabularyWord, keyed by the language they hold.
_GLOSS_COLUMNS: dict[str, str] = {
    "de": "german_translation",
    "en": "english_translation",
    "fr": "french_translation",
}
# Tried in order once the learner's own language has no entry.
_FALLBACK_ORDER: tuple[str, ...] = ("en", "de", "fr")
DEFAULT_GLOSS_LANGUAGE = "en"

# Names the correction model understands, for "write the explanation in X".
EXPLANATION_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
}


def normalize_language(value: Any) -> str:
    """Reduce 'en-GB', 'EN', None to a bare lowercase code with a safe default."""
    text = str(value or "").strip().lower()
    if not text:
        return DEFAULT_GLOSS_LANGUAGE
    return text.split("-", 1)[0].split("_", 1)[0]


def gloss_map(word: Any) -> dict[str, str | None]:
    """Every stored gloss for a word, keyed by language."""
    return {code: getattr(word, column, None) for code, column in _GLOSS_COLUMNS.items()}


def gloss_from_map(translations: Any, native_language: Any) -> str:
    """Same resolution order, for payloads that carry the raw map instead of a row."""
    glosses = translations if isinstance(translations, dict) else {}
    preferred = normalize_language(native_language)
    for code in [preferred, *(code for code in _FALLBACK_ORDER if code != preferred)]:
        value = str(glosses.get(code) or "").strip()
        if value:
            return value
    return ""


def resolve_gloss(word: Any, native_language: Any) -> tuple[str, str | None]:
    """Return (gloss, language_used). Empty string when the word has none."""
    glosses = gloss_map(word)
    preferred = normalize_language(native_language)
    order = [preferred, *(code for code in _FALLBACK_ORDER if code != preferred)]
    for code in order:
        value = str(glosses.get(code) or "").strip()
        if value:
            return value, code
    definition = str(getattr(word, "definition", "") or "").strip()
    return definition, None


def word_gloss(word: Any, native_language: Any) -> str:
    """The learner-facing translation of a word, or an empty string."""
    return resolve_gloss(word, native_language)[0]


def gloss_payload(word: Any, native_language: Any) -> dict[str, Any]:
    """The standard learner-facing translation fields for a vocabulary payload.

    `translation` is what the surface should render; `translations` stays in the
    payload because several clients still read the raw map, and
    `translation_language` lets a surface mark a fallback gloss honestly.
    """
    gloss, language = resolve_gloss(word, native_language)
    return {
        "translation": gloss,
        "translation_language": language,
        "translations": gloss_map(word),
    }
