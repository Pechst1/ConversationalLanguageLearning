"""Shared, inspectable explanations for personalized learning choices."""
from __future__ import annotations

from typing import Any


def recommendation_reason(surface: str, **signals: Any) -> dict[str, Any]:
    """Return a French because-line plus the exact named signals behind it."""
    clean = {key: value for key, value in signals.items() if value not in (None, "", [], {})}
    if surface == "review":
        bucket = str(clean.get("bucket") or "due")
        text = {
            "due": "Choisi parce que son rappel arrive aujourd’hui.",
            "fragile": "Choisi parce que ce mot reste fragile dans vos derniers rappels.",
            "linked": "Choisi parce qu’il appartient à la mission ou à l’épisode en cours.",
            "topic": "Choisi parce qu’il rejoint le sujet de votre édition.",
            "topic_compatible": "Choisi parce qu’il rejoint le sujet de votre édition.",
            "new": "Choisi comme unique nouveau fil du jour.",
        }.get(bucket, "Choisi d’après votre calendrier de rappel.")
    elif surface == "mission":
        if clean.get("serial_thread_id"):
            text = "Choisi pour faire avancer votre Feuilleton avec les mots et corrections du jour."
        elif clean.get("target_errata_count"):
            text = "Choisi pour remettre une correction récente en situation réelle."
        else:
            text = "Choisi pour produire les mots et structures de votre édition."
    elif surface == "panel_task":
        if clean.get("target_errata_count"):
            text = "Choisie pour réparer une forme fragile dans le contexte de cette scène."
        elif clean.get("target_vocabulary_count"):
            text = "Choisie pour réemployer un mot du jour dans l’histoire."
        else:
            text = "Choisie pour vérifier le point de langue de cette planche."
    else:
        text = "Choisi d’après les signaux de votre édition."
    return {"text": text, "signals": clean}


__all__ = ["recommendation_reason"]

