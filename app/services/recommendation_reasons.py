"""Shared, inspectable explanations for personalized learning choices.

A because-line is the app's own words, so it follows the one-language rule
(``app/services/chrome_language.py``): the learner's language up to A2, French
from B1. Every reason carries the three versions in ``text_by_language`` so the
client can re-apply the rule; ``text`` is the one resolved for ``language``.
"""
from __future__ import annotations

from typing import Any

from app.services.chrome_language import pick

_Table = dict[str, str]

_REVIEW: dict[str, _Table] = {
    "due": {
        "fr": "Choisi parce que son rappel arrive aujourd’hui.",
        "en": "Chosen because it is due for review today.",
        "de": "Ausgewählt, weil die Wiederholung heute fällig ist.",
    },
    "fragile": {
        "fr": "Choisi parce que ce mot reste fragile dans vos derniers rappels.",
        "en": "Chosen because this word is still fragile in your recent reviews.",
        "de": "Ausgewählt, weil dieses Wort in Ihren letzten Wiederholungen noch wackelt.",
    },
    "linked": {
        "fr": "Choisi parce qu’il appartient à la mission ou à l’épisode en cours.",
        "en": "Chosen because it belongs to the current letter or episode.",
        "de": "Ausgewählt, weil es zum aktuellen Brief oder zur aktuellen Folge gehört.",
    },
    "topic": {
        "fr": "Choisi parce qu’il rejoint le sujet de votre édition.",
        "en": "Chosen because it fits the topic of your edition.",
        "de": "Ausgewählt, weil es zum Thema Ihrer Ausgabe passt.",
    },
    "new": {
        "fr": "Choisi comme unique nouveau fil du jour.",
        "en": "Chosen as today’s one new word.",
        "de": "Ausgewählt als das eine neue Wort von heute.",
    },
}
_REVIEW["topic_compatible"] = _REVIEW["topic"]
_REVIEW_DEFAULT: _Table = {
    "fr": "Choisi d’après votre calendrier de rappel.",
    "en": "Chosen from your review schedule.",
    "de": "Ausgewählt nach Ihrem Wiederholungsplan.",
}

_MISSION_SERIAL: _Table = {
    "fr": "Choisi pour faire avancer votre Feuilleton avec les mots et corrections du jour.",
    "en": "Chosen to move your Feuilleton on with today’s words and corrections.",
    "de": "Ausgewählt, um Ihr Feuilleton mit den Wörtern und Korrekturen von heute voranzubringen.",
}
_MISSION_ERRATA: _Table = {
    "fr": "Choisi pour remettre une correction récente en situation réelle.",
    "en": "Chosen to put a recent correction to use in a real situation.",
    "de": "Ausgewählt, um eine neue Korrektur in einer echten Situation anzuwenden.",
}
_MISSION_DEFAULT: _Table = {
    "fr": "Choisi pour produire les mots et structures de votre édition.",
    "en": "Chosen so you use the words and structures of your edition.",
    "de": "Ausgewählt, damit Sie die Wörter und Strukturen Ihrer Ausgabe anwenden.",
}

_PANEL_ERRATA: _Table = {
    "fr": "Choisie pour réparer une forme fragile dans le contexte de cette scène.",
    "en": "Chosen to repair a fragile form in the context of this scene.",
    "de": "Ausgewählt, um eine wackelige Form im Kontext dieser Szene zu festigen.",
}
_PANEL_VOCAB: _Table = {
    "fr": "Choisie pour réemployer un mot du jour dans l’histoire.",
    "en": "Chosen to reuse one of today’s words in the story.",
    "de": "Ausgewählt, um ein Wort von heute in der Geschichte wiederzuverwenden.",
}
_PANEL_DEFAULT: _Table = {
    "fr": "Choisie pour vérifier le point de langue de cette planche.",
    "en": "Chosen to check this page’s language point.",
    "de": "Ausgewählt, um den Sprachpunkt dieser Seite zu prüfen.",
}
_DEFAULT: _Table = {
    "fr": "Choisi d’après les signaux de votre édition.",
    "en": "Chosen from your edition’s signals.",
    "de": "Ausgewählt nach den Signalen Ihrer Ausgabe.",
}


def recommendation_reason(surface: str, *, language: str = "fr", **signals: Any) -> dict[str, Any]:
    """Return a because-line (in ``language``, all three in ``text_by_language``)
    plus the exact named signals behind it."""
    clean = {key: value for key, value in signals.items() if value not in (None, "", [], {})}
    if surface == "review":
        table = _REVIEW.get(str(clean.get("bucket") or "due"), _REVIEW_DEFAULT)
    elif surface == "mission":
        if clean.get("serial_thread_id"):
            table = _MISSION_SERIAL
        elif clean.get("target_errata_count"):
            table = _MISSION_ERRATA
        else:
            table = _MISSION_DEFAULT
    elif surface == "panel_task":
        if clean.get("target_errata_count"):
            table = _PANEL_ERRATA
        elif clean.get("target_vocabulary_count"):
            table = _PANEL_VOCAB
        else:
            table = _PANEL_DEFAULT
    else:
        table = _DEFAULT
    return {"text": pick(table, language), "text_by_language": dict(table), "signals": clean}


__all__ = ["recommendation_reason"]
