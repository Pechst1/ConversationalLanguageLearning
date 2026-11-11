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

from app.services.chrome_language import mother_tongue

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

    return LEARNER_ADDRESS.get(mother_tongue(language))


def address_instruction(language: str | None) -> str:
    """The sentence a prompt gives a model so its text to the learner uses the setting.

    Empty for a language without a choice. It is about the *app's* voice (instructions,
    corrections, explanations); a character's own lines keep that character's register
    (:func:`character_register`).
    """

    form = _ADDRESS_FORMS.get(mother_tongue(language))
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


def _same_person(left: str, right: str) -> bool:
    """Do two ids name one person? The cast registry decides (#147), not the spelling."""

    if left == right:
        return True
    from app.services import cast_registry

    resolved = cast_registry.resolve_id(left)
    return resolved is not None and resolved == cast_registry.resolve_id(right)


def _relationship_register(state: Mapping[str, Any] | None, character_id: str) -> Register | None:
    relationships = (state or {}).get("relationships") if isinstance(state, Mapping) else None
    if not isinstance(relationships, Mapping):
        return None
    # The id asked for first, then any row that names the same person («gus» asked, the
    # engine recorded «augustin_de_roncourt»).
    rows = sorted(relationships.items(), key=lambda item: str(item[0]) != character_id)
    for key, entry in rows:
        if isinstance(entry, Mapping) and _same_person(str(key), character_id):
            found = register_of(entry.get("register"))
            if found:
                return found
    return None


def relationship_register(state: Mapping[str, Any] | None, character_id: Any) -> Register | None:
    """What the relationship map alone records. Off a season this is the person's register
    (an accepted «On se tutoie ?» is kept there); a season's value never comes from here."""

    key = str(character_id or "").strip()
    return _relationship_register(state, key) if key else None


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
        # The scene reads the season row by the season's own id; a surface may spell the
        # same person otherwise (the season's «odile» is the registry's «odile_ferrand»).
        member = next((row for row in season.cast if row.id == character_id), None) or next(
            (row for row in season.cast if _same_person(row.id, character_id)), None
        )
        if member is None:
            return None
        stored = live.get(SEASON_KEY)
        flags = effective_flags(season, stored if isinstance(stored, dict) else None)
        return season_registers(season, flags).get(member.id)
    except Exception:  # noqa: BLE001 - a missing season file must not break a letter
        return None


def season_registers(season: Any, flags: Mapping[str, Any]) -> dict[str, Register]:
    """How each person of the season's cast addresses the learner, ``{id: "tu"|"vous"}``:
    the cast's ``address`` overridden by its ``register.<id>`` flag (Gus's «vous» until T3).

    The one place that reads a cast row's register (#594): the Courrier, the scene's
    voice and the check on a learner's reply all take it from here.
    """

    return {
        member.id: register_of(flags.get(f"register.{member.id}") or member.address) or DEFAULT_CHARACTER_REGISTER
        for member in season.cast
    }


def _snapshot_register(registers: Mapping[str, Any] | None, character_id: str) -> Register | None:
    """The register a scene kept for ``character_id`` when it was planned (``season_registers``)."""

    if not isinstance(registers, Mapping):
        return None
    rows = sorted(registers.items(), key=lambda item: str(item[0]) != character_id)
    for key, value in rows:
        if _same_person(str(key), character_id):
            found = register_of(value)
            if found:
                return found
    return None


def known_register(
    state: Mapping[str, Any] | None,
    character_id: Any,
    *,
    registers: Mapping[str, Any] | None = None,
) -> Register | None:
    """What the cast itself says about how ``character_id`` addresses the learner, or ``None``.

    ``character_register`` without its last-resort default: «tu» or «vous» only when a
    source above it knows, so a caller whose own text can decide (a letter that carries
    its register) does not mistake the default for knowledge (#506). ``state`` may be
    ``None``: a first letter is made before any scene has started a thread, and the
    season still names its cast. ``registers`` is a scene's own snapshot of the season's
    registers (``season_registers``, kept with the day), read before the season file.
    """

    key = str(character_id or "").strip()
    if not key:
        return None
    from app.services import cast_registry

    canonical = cast_registry.resolve_id(key) or key
    if any(
        name in ALWAYS_VOUS or name.startswith(ALWAYS_VOUS_PREFIXES) for name in (key, canonical)
    ):
        return DEFAULT_CHARACTER_REGISTER
    return (
        _relationship_register(state, key)
        or _snapshot_register(registers, key)
        or _season_register(state, key)
    )


def character_register(state: Mapping[str, Any] | None, character_id: Any) -> Register:
    """How ``character_id`` addresses the learner: «tu» or «vous». The one resolver.

    ``character_id`` may be any spelling the cast registry knows (a scene id, an alias, a
    portrait directory): every lookup goes through :func:`_same_person`.

    1. the landlord and office clerks: «vous», always;
    2. the register the relationship map records (the story writes «tu» there when the
       learner accepts «On se tutoie ?»);
    3. what the season the thread plays opens that character with: the cast's
       ``address``, overridden by its ``register.<id>`` flag (the scene reads the same);
    4. «vous».

    :func:`known_register` is steps 1 to 3 alone.
    """

    return known_register(state, character_id) or DEFAULT_CHARACTER_REGISTER


__all__ = [
    "ALWAYS_VOUS",
    "DEFAULT_CHARACTER_REGISTER",
    "LEARNER_ADDRESS",
    "Register",
    "address_instruction",
    "character_register",
    "known_register",
    "learner_address",
    "register_of",
    "relationship_register",
    "season_registers",
]
