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
la confiture ?») or its authored ``ask`` — and
the learner's reply, which needs the rule. It is graded like any production
(WP-S1: the local check, then the asynchronous relecture).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.forge_item_validator import register_problems

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


#: Who stands in for a coach the learner has not met yet, in order: the people the
#: season puts on its first page (#147: Romy coached «L'interview» before T4).
STAND_INS = ("margaux_barman", "lila_bonnet", "marin_leveque", "augustin_de_roncourt")


def coach(
    character_id: str | None,
    *,
    family: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """The coach payload for one cast member: ``{id, name, register, family, family_title}``.

    #147: the name is the cast registry's (what the learner reads on every other
    screen), and with the learner's thread ``state`` the register is the one the scene
    and the Courrier use (``address.character_register``: Gus says vous until T3). The
    coaches file only says who coaches which rules, and a register for no learner.
    """

    cast = _data()["cast"].get(str(character_id or ""))
    if cast is None:
        return None
    from app.services.cast_registry import display_name

    register = cast.get("register", "tu")
    if state is not None:
        from app.services.address import character_register

        register = character_register(state, str(character_id))
    return {
        "id": str(character_id),
        "name": display_name(character_id, cast["name"]),
        "register": register,
        "family": family["id"] if family else None,
        "family_title": dict(family["title"]) if family else None,
    }


def coach_for_unit(unit: str | None, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    family = family_for_unit(unit)
    return _met_coach(family["coach"], family=family, state=state) if family else None


def _met_coach(
    character_id: str, *, family: dict[str, Any] | None, state: dict[str, Any] | None
) -> dict[str, Any] | None:
    """The coach, or, when this learner has not met them yet, the first stand-in they have
    met (without the family's title: «Romy's interview» is not Margaux's)."""

    if state is None:
        return coach(character_id, family=family)
    from app.services.cast_registry import has_met

    if has_met(state, character_id):
        return coach(character_id, family=family, state=state)
    stand_in = next((cid for cid in STAND_INS if cid != character_id and has_met(state, cid)), None)
    return coach(stand_in, state=state) if stand_in else None


def coach_for_concept(external_id: str | None, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The coach of a concept (a v2 unit, or a v1 concept through its card or its units).

    With the learner's thread ``state`` (#147): only someone the learner has met, and
    their register as the story has it."""

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
        return _met_coach(speaker, family=family if family and family["coach"] == speaker else None, state=state)
    if family:
        return _met_coach(family["coach"], family=family, state=state)
    return None


def recast_scene(item: dict[str, Any], coach_payload: dict[str, Any] | None) -> dict[str, Any]:
    """A shared item's two-line scene, said by this learner's coach (#147).

    Exercise sets are built once for every learner, with the file's coach (Romy for the
    question words). A learner who has not met Romy gets the stand-in from
    :func:`coach_for_concept`; the scene's line, badge and prompt follow, so the person
    who asks is the person who reacts. When the stand-in's register cannot say the line
    («vous» on a «tu» line), the scene is posed without a speaker.
    """

    character = item.get("character") if isinstance(item.get("character"), dict) else None
    if not character or not coach_payload or str(character.get("id")) == str(coach_payload.get("id")):
        return item
    old_name, new_name = str(character.get("name") or ""), str(coach_payload["name"])
    lines = [dict(line) for line in ((item.get("scene") or {}).get("lines") or []) if isinstance(line, dict)]
    said = next((line for line in lines if line.get("speaker") != "learner"), None)
    fits = said is not None and not register_problems(str(said.get("fr") or ""), coach_payload.get("register"))

    def retitle(text: Any) -> Any:
        if not isinstance(text, str) or not old_name or not text.startswith(old_name):
            return text
        rest = text[len(old_name):]
        return f"{new_name}{rest}" if fits else rest.lstrip(" :").lstrip()

    out = dict(item)
    out["prompt"] = retitle(item.get("prompt"))
    if isinstance(item.get("prompt_l10n"), dict):
        out["prompt_l10n"] = {key: retitle(value) for key, value in item["prompt_l10n"].items()}
    if not fits:
        out.pop("character", None)
        out.pop("coach", None)
        out.pop("scene", None)
        return out
    out["character"] = {"id": coach_payload["id"], "name": new_name, "register": coach_payload.get("register", "tu")}
    out["coach"] = dict(coach_payload)
    for line in lines:
        if line is said:
            line["speaker"], line["name"] = coach_payload["id"], new_name
    out["scene"] = {**(item.get("scene") or {}), "lines": lines}
    return out


def story_state_of(db: Any, user: Any) -> dict[str, Any] | None:
    """The learner's story thread state when it says who they have met, else ``None``
    (the coaches then stay as the file has them: no story to read, nothing to filter)."""

    if db is None or user is None or getattr(user, "id", None) is None:
        return None
    try:
        from app.services.cast_registry import met_ids
        from app.services.story_correspondence import active_thread

        thread = active_thread(db, user)
    except Exception:  # noqa: BLE001 - a coach is decoration, never a reason to fail an item
        return None
    state = thread.state if thread is not None and isinstance(thread.state, dict) else None
    return state if state is not None and met_ids(state) is not None else None


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


def mini_scene(item: Any, coach_payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """The coach's line and the learner's reply for one bank item, or ``None``.

    The coach's line is the question **the item itself carries**: the question in
    its sentence («Tu prends la confiture ? — Oui, je la prends.») or its authored
    ``ask``. ``None`` when the item has neither, when the reply would name the coach
    in the third person («Marin est à la brocante», said to Marin), or when the
    rule's span would not be in the reply.

    #176 / #146: a line used to be drawn from the coach's list of generic openers
    («Qu'est-ce que tu me racontes ?») and put above any sentence to translate, so the
    line and the task came from two sources and did not belong together. A line and
    its task now come from one item record, or there is no line (the caller poses the
    plain task).
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
        return None
    if re.search(rf"\b{re.escape(first_name)}\b", f"{line} {reply}"):
        return None
    if register_problems(line, coach_payload.get("register")):
        # #267: «tu» on the badge, «vous» in the line (or the reverse): two people.
        return None
    if str(item.target) not in reply:
        return None
    # FORGE-DE: the reply's German meaning, cut the same way as the English one.
    reply_de = None
    german = getattr(item, "de", None)
    if german:
        german = _strip_vocative(str(german), french=False)
        split_de = _split_question(german)
        if split and split_en:
            reply_de = split_de[1] if split_de else None
        elif not split_de:
            reply_de = german
    return {
        "coach": coach_payload,
        "lines": [
            {"speaker": coach_id, "name": name, "fr": line, "en": line_en},
            {"speaker": "learner", "fr": reply, "en": reply_en},
        ],
        "reply": reply,
        "reply_en": reply_en,
        "reply_de": reply_de,
    }


__all__ = [
    "MOODS",
    "STAND_INS",
    "cast_ids",
    "coach",
    "coach_for_concept",
    "coach_for_unit",
    "coach_mood",
    "family_for_unit",
    "mini_scene",
    "recast_scene",
    "story_state_of",
]
