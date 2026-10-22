"""ROOT CAUSE #265 (child of #147) — a person's role is one string, kept here.

Lila was «institutrice et peintre» in the Courrier header, an English paragraph about
a CE1 class in the generated Courrier, «Architecte» in a scene gag, and a director
prompt carried yet another free-text copy; Margaux was «serveuse» in a letter and
«Tient Le Mistral» in the cast intro. Each surface typed its own role, so nothing
failed when one changed.

Now the role is written once per person and language (what the learner reads, a
short noun phrase with no capital and no full stop) and every surface reads it by id:
the authored and generated Courrier, both cast intros (:func:`role_line` puts the
role in front of the intro's own trait sentence), the director's cast rows and the
voice persona. ``tests/test_cast_role_265.py`` is the guard.

This module is a leaf (no imports from the cast modules) so ``cast_voices`` can use
it without a cycle; the registry re-exports :func:`role`.
"""
from __future__ import annotations

ROLES: dict[str, dict[str, str]] = {
    "margaux_barman": {
        "fr": "patronne du Mistral",
        "en": "the owner of Le Mistral",
        "de": "Wirtin des Mistral",
    },
    "augustin_de_roncourt": {
        "fr": "habitué du Mistral",
        "en": "a regular at Le Mistral",
        "de": "Stammgast im Mistral",
    },
    "marin_leveque": {
        "fr": "ton premier ami à Paris",
        "en": "your first friend in Paris",
        "de": "dein erster Freund in Paris",
    },
    "lila_bonnet": {
        "fr": "institutrice et peintre",
        "en": "a teacher and painter",
        "de": "Lehrerin und Malerin",
    },
    "romy_tremblay": {
        "fr": "journaliste québécoise, elle aussi nouvelle à Paris",
        "en": "a journalist from Québec, new in Paris too",
        "de": "Journalistin aus Québec, auch neu in Paris",
    },
    "landlord_marchand": {
        "fr": "ton propriétaire",
        "en": "your landlord",
        "de": "dein Vermieter",
    },
}


def role_of(cast_id: str | None, language: str = "fr") -> str:
    """The role of a registry id (not an alias: use ``cast_registry.role``), or ``""``."""

    row = ROLES.get(str(cast_id or ""))
    if not row:
        return ""
    return row.get(language) or row.get("en") or ""


def role_line(cast_id: str | None, language: str = "fr", trait: str = "") -> str:
    """«Role. Trait.» as a cast intro prints it; ``""`` for a person without a role here."""

    text = role_of(cast_id, language)
    if not text:
        return ""
    line = f"{text[:1].upper()}{text[1:]}."
    trait = str(trait or "").strip()
    return f"{line} {trait}" if trait else line
