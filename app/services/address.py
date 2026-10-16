"""How the app addresses the learner, and how a character does: one place.

Two different questions used to be answered, over and over, in different files:

1. **How does the app itself speak to the learner?** Instructions, hints, mission
   goals, success signals, the prompts that ask a model to write for the learner.
   The owner's decision is *du* in German and *tu* in French (14 Oct 2026). That is
   :data:`LEARNER_ADDRESS`, a single setting; server templates and model prompts read
   it through :func:`learner_address` and :func:`address_instruction` instead of
   choosing a pronoun in a string literal.
2. **How does a *character* address the learner?** That is story, not chrome: Gus
   says «vous» until the third tentpole, Margaux says «tu» from the first night,
   M. Marchand says «vous» always. :func:`character_register` is the one resolver:
   the register the relationship records, else what the story starts that character
   with (the season's cast, then the world bible), else «vous».

Before this module five places each answered question 2 by reading
``state.relationships[id].register`` and falling back to «vous» when the entry was
missing (``story_correspondence.learner_register``,
``serial_notifications.character_register``, ``missions`` and ``serial`` each had a
private copy). The season scene, meanwhile, read the cast's ``address``. A character
the relationship map had not recorded yet therefore spoke «tu» in the scene and
«vous» in the Courrier on the same day.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

Register = Literal["tu", "vous"]

#: The one setting: the form the *app* uses to address a learner, per interface
#: language. English has no second person to choose between.
LEARNER_ADDRESS: Mapping[str, str] = {"fr": "tu", "de": "du"}

#: Characters who address the learner as «vous» whatever a row says.
ALWAYS_VOUS = frozenset({"landlord_marchand"})
ALWAYS_VOUS_PREFIXES = ("office_",)

DEFAULT_CHARACTER_REGISTER: Register = "vous"

_ADDRESS_FORMS: Mapping[str, Mapping[str, str]] = {
    "fr": {"pronoun": "tu", "possessive": "ton/ta/tes", "example": "Tu as", "avoid": "vous, votre, vos"},
    "de": {"pronoun": "du", "possessive": "dein/deine", "example": "Du hast", "avoid": "Sie, Ihr, Ihnen"},
}


def learner_address(language: str | None) -> str | None:
    """«tu» for French, «du» for German, ``None`` where the language has no choice."""

    return LEARNER_ADDRESS.get(str(language or "").strip().lower()[:2])


def address_instruction(language: str | None) -> str:
    """The sentence a prompt gives a model so its text to the learner uses the setting.

    Empty for a language without a choice. It is about the *app's* voice (instructions,
    corrections, explanations); a character's own lines keep that character's register
    (:func:`character_register`).
    """

    form = _ADDRESS_FORMS.get(str(language or "").strip().lower()[:2])
    if form is None:
        return ""
    return (
        f"Address the learner as «{form['pronoun']}» ({form['possessive']}; e.g. «{form['example']} …») "
        f"in every sentence that is not a character's own line. Never «{form['avoid']}» for the learner."
    )


def register_of(value: Any) -> Register | None:
    """«tu» / «vous» from a stored value such as ``"tu"``, ``"vous / polite formal"``."""

    text = str(value or "").strip().lower()
    if not text:
        return None
    return "tu" if text.startswith("tu") else "vous"


def _relationship_register(state: Mapping[str, Any] | None, character_id: str) -> Register | None:
    relationships = (state or {}).get("relationships") if isinstance(state, Mapping) else None
    entry = relationships.get(character_id) if isinstance(relationships, Mapping) else None
    return register_of(entry.get("register")) if isinstance(entry, Mapping) else None


def _season_register(state: Mapping[str, Any] | None, character_id: str) -> Register | None:
    """What the season's cast opens with: ``address``, overridden by ``register.<id>`` flags."""

    live = (state or {}).get("living_story") if isinstance(state, Mapping) else None
    if not isinstance(live, Mapping):
        # Day one: no living story yet, but the enabled season still names its cast.
        live = {}
    try:
        from app.services.season.clock import SEASON_KEY
        from app.services.season.flags import effective_flags
        from app.services.season.format import load_season
        from app.services.season.runtime import season_id_for

        season_id = season_id_for(dict(live))
        if not season_id:
            return None
        season = load_season(season_id)
        member = next((row for row in season.cast if row.id == character_id), None)
        if member is None:
            return None
        stored = live.get(SEASON_KEY)
        flags = effective_flags(season, stored if isinstance(stored, dict) else None)
        return register_of(flags.get(f"register.{character_id}") or member.address)
    except Exception:  # noqa: BLE001 - a missing season file must not break a letter
        return None


def character_register(state: Mapping[str, Any] | None, character_id: Any) -> Register:
    """How ``character_id`` addresses the learner: «tu» or «vous». The one resolver.

    1. the landlord and office clerks: «vous», always;
    2. the register the relationship map records (the story writes «tu» there when the
       learner accepts «On se tutoie ?»);
    3. what the season the thread plays opens that character with: the cast's
       ``address``, overridden by its ``register.<id>`` flag (the scene reads the same);
    4. «vous».
    """

    key = str(character_id or "")
    if not key or key in ALWAYS_VOUS or key.startswith(ALWAYS_VOUS_PREFIXES):
        return DEFAULT_CHARACTER_REGISTER
    return (
        _relationship_register(state, key)
        or _season_register(state, key)
        or DEFAULT_CHARACTER_REGISTER
    )


__all__ = [
    "ALWAYS_VOUS",
    "DEFAULT_CHARACTER_REGISTER",
    "LEARNER_ADDRESS",
    "Register",
    "address_instruction",
    "character_register",
    "learner_address",
    "register_of",
]
