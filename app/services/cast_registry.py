"""ROOT CAUSE #147 — the cast is one registry.

Before this module a character's name, gender, face, voice and first day were
written out again in the teaser (``serial_notifications``), the cast intro
(``intro.json``), the story content (``t*.json``), the voices (``cast_voices``)
and the prompts, and they drifted: Romy greeted in a teaser before she was in the
story, Camille was missing from the cast intro, M. Marchand was called «Elle».
Nothing made a second copy fail when the first changed.

Now there is one row per person, :class:`CastMember` (id, name, gender, face,
voice, first day), and every surface reads it **by id**:

* ``name`` and ``gender`` come from the season's world bible
  (``app/data/season/s1/world.json`` ``cast``), so a pronoun follows the canon;
* ``voice`` comes from :mod:`app.services.cast_voices`;
* ``face`` is the drawn portrait directory, found on disk, never typed twice;
* ``first_day`` is ``(tentpole, day letter)`` of the person's first authored page;
* the pronoun the story uses for a person (:func:`pronoun_for`) comes from the same
  row, and for the one person whose gender the learner picks (Camille) from that
  life's own choice — every story prompt reads it here (#147, Phase 3).

``tests/test_cast_registry_147.py`` is the guard: every id the authored season,
the cast intro and the teasers name must be here, speakers need a face, the
first day must match the authored season, and the intro may not name someone
before their day.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.cast_voices import CAST_VOICES

_REPO = Path(__file__).resolve().parents[2]
WORLD_PATH = _REPO / "app" / "data" / "season" / "s1" / "world.json"
DRAWN_FACES_DIR = _REPO / "web-frontend" / "public" / "assets" / "serial" / "drawn"

#: What the learner reads for each person.
_SHORT_NAMES: dict[str, str] = {
    "margaux_barman": "Margaux",
    "augustin_de_roncourt": "Gus",
    "marin_leveque": "Marin",
    "lila_bonnet": "Lila",
    "camille_marchand": "Camille",
    "romy_tremblay": "Romy",
    "landlord_marchand": "M. Marchand",
    "mme_diallo": "Mme Diallo",
    "maitre_vasseur": "Maître Vasseur",
    "bastien_roux": "Bastien Roux",
    "odile_ferrand": "Odile",
}
#: When the story first puts each person on a page: ``(tentpole, day letter)``.
#: The guard test re-derives it from ``t*.json`` and fails if this drifts.
_FIRST_APPEARANCE: dict[str, tuple[int, str]] = {
    "margaux_barman": (1, "a"),
    "augustin_de_roncourt": (1, "a"),
    "marin_leveque": (1, "a"),
    "lila_bonnet": (1, "a"),
    "camille_marchand": (1, "b"),
    "bastien_roux": (2, "b"),
    "romy_tremblay": (4, "a"),
    "mme_diallo": (4, "a"),
    "landlord_marchand": (4, "a"),
    "odile_ferrand": (4, "b"),
    "maitre_vasseur": (6, "b"),
}
#: Ids a scene uses for the same person.
_ALIASES: dict[str, str] = {
    "odile": "odile_ferrand",
    "marchand": "landlord_marchand",
    "landlord": "landlord_marchand",
    "gus": "augustin_de_roncourt",
    "augustin": "augustin_de_roncourt",
    "marin": "marin_leveque",
    "lila": "lila_bonnet",
    "margaux": "margaux_barman",
    "romy": "romy_tremblay",
    "camille": "camille_marchand",
}
#: A person whose gender the learner picks: the season flag that holds the choice.
GENDER_FLAGS: dict[str, str] = {"camille_marchand": "s1.camille_gender"}
#: Ids in a scene that are not a person with a face: the learner, the narration
#: and things that «speak» (a letter, an SMS, everyone at once).
NON_PEOPLE: frozenset[str] = frozenset({"toi", "caption", "letter", "all", "sms"})
#: Unnamed one-scene extras (a clerk, a child): a role, not a recurring person.
EXTRAS: frozenset[str] = frozenset({"clerk", "clerk_2", "child", "builder", "dealer"})


@dataclass(frozen=True)
class CastMember:
    id: str
    name: str  # the world bible's full name
    short_name: str  # what the learner reads
    gender: str  # "f", "m", or "x" (the learner picks: Camille)
    voice: str | None
    face: str | None  # drawn portrait directory name; None when no art exists yet
    first_day: tuple[int, str]  # (tentpole number, day letter)

    @property
    def pronoun_fr(self) -> str:
        """«Il» or «Elle»; the neutral «Iel» for a person whose gender the learner picks."""

        return {"f": "Elle", "m": "Il"}.get(self.gender, "Iel")


def _face_for(cast_id: str) -> str | None:
    return cast_id if (DRAWN_FACES_DIR / cast_id / "portrait-neutre.png").is_file() else None


@lru_cache(maxsize=1)
def _registry() -> dict[str, CastMember]:
    world = json.loads(WORLD_PATH.read_text(encoding="utf-8"))
    rows = {str(row["id"]): row for row in world.get("cast", []) if row.get("id")}
    rows.setdefault("odile_ferrand", {"id": "odile_ferrand", "gender": "f", "name": "Odile Ferrand"})
    members: dict[str, CastMember] = {}
    for cast_id, row in rows.items():
        gender = str(row.get("gender") or "x")
        members[cast_id] = CastMember(
            id=cast_id,
            name=str(row.get("name") or cast_id),
            short_name=_SHORT_NAMES.get(cast_id, str(row.get("name") or cast_id)),
            gender=gender if gender in ("f", "m", "x") else "x",
            voice=CAST_VOICES.get(cast_id),
            face=_face_for(cast_id),
            first_day=_FIRST_APPEARANCE.get(cast_id, (1, "a")),
        )
    return members


def all_members() -> dict[str, CastMember]:
    return dict(_registry())


def resolve_id(character_id: str | None) -> str | None:
    """The registry id for any id, alias or first-name token, or ``None``."""

    raw = str(character_id or "").strip().lower()
    if not raw:
        return None
    registry = _registry()
    if raw in registry:
        return raw
    if raw in _ALIASES:
        return _ALIASES[raw]
    return _ALIASES.get(raw.split("_", 1)[0])


def member(character_id: str | None) -> CastMember | None:
    cast_id = resolve_id(character_id)
    return _registry().get(cast_id) if cast_id else None


def display_name(character_id: str | None, default: str = "") -> str:
    found = member(character_id)
    return found.short_name if found else default


def pronoun_for(
    character_id: str | None,
    *,
    gender: str | None = None,
    flags: Mapping[str, Any] | None = None,
) -> str | None:
    """«il» or «elle» for a person, as this life's story says it — or ``None`` when
    nobody has decided (a prompt then uses the name, never a guess).

    The registry's gender; for Camille, the learner's own choice (``flags``, seeded
    until T1 B poses it); ``gender`` is the world bible's value for a person the
    registry does not hold (a later season's cast)."""

    found = member(character_id)
    cast_id = found.id if found else str(character_id or "")
    value = (flags or {}).get(GENDER_FLAGS[cast_id]) if cast_id in GENDER_FLAGS else None
    if not value:
        value = found.gender if found else gender
    return {"f": "elle", "m": "il"}.get(str(value or "").strip().lower()[:1])


def introduced_by(character_id: str | None, tentpole: int, day: str = "z") -> bool:
    """Has the story put this person on a page by ``(tentpole, day)``?

    Unknown ids are not introduced: a surface must not name someone the registry
    does not hold.
    """

    found = member(character_id)
    return found is not None and found.first_day <= (int(tentpole), str(day))
