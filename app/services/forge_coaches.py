"""WP-S5 — La Forge's coaches and the free-use rung's two-line scene.

Every rule has a coach: one cast member per family of v2 units
(``app/data/forge_coaches.json``). Margaux keeps the counter (articles,
amounts, ordering), Gus tells the past and compares, Romy interviews
(questions, time, reasons), Lila teaches the class (être/avoir, describing,
instructions), Marin walks (everyday verbs, going and coming, pronouns, what
comes next) and M. Marchand owns the flat (il y a, polite requests). A v1
concept with an authored rule card keeps the card's speaker, so the face on the
card is the face on the feedback.

The coach shows on the rule card and on each answer's feedback, with a mood:
``happy`` on a checked right answer, ``cross`` on a checked wrong one,
``moved`` when the answer made the rule held, ``neutral`` otherwise
(:func:`coach_mood`).

The free-use rung becomes a two-line scene with the coach
(:func:`mini_scene`): the coach's line — the item's own question («Tu prends
la confiture ?»), its authored ``ask``, or one of the coach's openers — and
the learner's reply, which needs the rule. It is graded like any production
(WP-S1: the local check, then the asynchronous relecture).
"""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

COACHES_PATH = Path(__file__).resolve().parents[1] / "data" / "forge_coaches.json"

MOODS = ("neutral", "happy", "cross", "moved")


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    return json.loads(COACHES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _unit_family() -> dict[str, dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}
    for family in _data()["families"]:
        for unit in family["units"]:
            families[unit] = family
    return families


def cast_ids() -> list[str]:
    return list(_data()["cast"])


def family_for_unit(unit: str | None) -> dict[str, Any] | None:
    return _unit_family().get(str(unit or ""))


def coach(character_id: str | None, *, family: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The coach payload for one cast member: ``{id, name, register, family, family_title}``."""

    cast = _data()["cast"].get(str(character_id or ""))
    if cast is None:
        return None
    return {
        "id": str(character_id),
        "name": cast["name"],
        "register": cast.get("register", "tu"),
        "family": family["id"] if family else None,
        "family_title": dict(family["title"]) if family else None,
    }


def coach_for_unit(unit: str | None) -> dict[str, Any] | None:
    family = family_for_unit(unit)
    return coach(family["coach"], family=family) if family else None


def coach_for_concept(external_id: str | None) -> dict[str, Any] | None:
    """The coach of a concept (a v2 unit, or a v1 concept through its card or its units)."""

    from app.services.item_bank import units_for_external_id
    from app.services.rule_cards import rule_card_for

    external_id = str(external_id or "")
    if not external_id:
        return None
    units = units_for_external_id(external_id) or [external_id]
    family = next((family_for_unit(unit) for unit in units if family_for_unit(unit)), None)
    card = rule_card_for(external_id) or {}
    speaker = card.get("speaker")
    if speaker and speaker in _data()["cast"]:
        # The authored card's speaker is the face the learner already knows.
        return coach(speaker, family=family if family and family["coach"] == speaker else None)
    if family:
        return coach(family["coach"], family=family)
    return None


def coach_mood(*, correct: bool | None, checked: bool, held: bool = False) -> str:
    """The coach's face after an answer."""

    if held:
        return "moved"
    if not checked or correct is None:
        return "neutral"
    return "happy" if correct else "cross"


# --------------------------------------------------------------------------- #
# The free-use rung: a two-line scene
# --------------------------------------------------------------------------- #

_NAMES = r"(?:Margaux|Marin|Romy|Lila|Gus|Monsieur Marchand|Mr Marchand|M\. Marchand)"
_VOCATIVE = re.compile(rf",\s*{_NAMES}\s*(?=[.?!])")


def _strip_vocative(text: str, *, french: bool) -> str:
    """«Tu prends le sac, Lila ?» → «Tu prends le sac ?»: in the scene, «tu» is the learner."""

    stripped = _VOCATIVE.sub("", text)
    if french:
        return re.sub(r"\s*([?!])", r" \1", stripped).strip()
    return re.sub(r"\s+([?!.])", r"\1", stripped).strip()


def _split_question(text: str) -> tuple[str, str] | None:
    index = text.find("?")
    if 0 < index < len(text) - 1:
        return text[: index + 1].strip(), text[index + 1:].strip()
    return None


def _opener(coach_id: str, key: str) -> dict[str, str]:
    openers = _data()["cast"][coach_id]["openers"]
    index = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:6], 16) % len(openers)
    return dict(openers[index])


def mini_scene(item: Any, coach_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """The coach's line and the learner's reply for one bank item, or ``None``.

    ``None`` when the item cannot be a scene with this coach: the reply would
    name the coach in the third person («Marin est à la brocante», said to
    Marin), or the rule's span would not be in the reply.
    """

    if not coach_payload:
        return None
    coach_id = str(coach_payload["id"])
    name = str(coach_payload["name"])
    first_name = name.split()[-1]
    sentence = _strip_vocative(str(item.sentence), french=True)
    english = _strip_vocative(str(item.en), french=False)
    split, split_en = _split_question(sentence), _split_question(english)
    if not split and re.search(r"[.!]\s", sentence):
        # «Romy demande l'heure. Il est dix heures.»: a narrated line is no reply.
        return None
    if split and split_en:
        line, reply = split
        line_en, reply_en = split_en
    elif getattr(item, "ask", None):
        line, line_en = item.ask["fr"], item.ask["en"]
        reply, reply_en = sentence, english
    else:
        opener = _opener(coach_id, str(item.fingerprint))
        line, line_en = opener["fr"], opener["en"]
        reply, reply_en = sentence, english
    if re.search(rf"\b{re.escape(first_name)}\b", f"{line} {reply}"):
        return None
    if str(item.target) not in reply:
        return None
    return {
        "coach": coach_payload,
        "lines": [
            {"speaker": coach_id, "name": name, "fr": line, "en": line_en},
            {"speaker": "learner", "fr": reply, "en": reply_en},
        ],
        "reply": reply,
        "reply_en": reply_en,
    }


__all__ = [
    "MOODS",
    "cast_ids",
    "coach",
    "coach_for_concept",
    "coach_for_unit",
    "coach_mood",
    "family_for_unit",
    "mini_scene",
]
