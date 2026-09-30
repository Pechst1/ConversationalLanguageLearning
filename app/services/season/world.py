"""The places of a season (WP-111), and the plate each one opens on.

The world bible's ``setting.recurring_locations`` is where the director reads places
from; this module is where the season format checks them. Season 1 («La clé
d'Odile», ``docs/story/season-1/10-lieux-et-images.md``) adds Odile's flat, the
stairwell, M. Marchand's office, the mairie, the notary's, the Gare de l'Est, the
rue de Lancry, the bakery, Lila's classroom and the roof. A new place has no
painted plate yet, so it borrows the nearest existing one until its art is drawn
(``plate``) — the reader never shows a broken image.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from typing import Any

from app.services.season.format import SEASON_ROOT

#: Every place a season-1 page may be set in: its French name, the plate it opens
#: on (a path under ``web-frontend/public``), and whether that plate is its own.
SEASON_ONE_LOCATIONS: dict[str, dict[str, str | bool]] = {
    "le_mistral": {"name_fr": "Le Mistral", "plate": "assets/serial/locations/le_mistral-counter.webp", "own": True},
    "mistral_back_room": {"name_fr": "L'arrière-salle du Mistral", "plate": "assets/serial/locations/le_mistral-booth.webp", "own": False},
    "quai_de_valmy": {"name_fr": "Le quai de Valmy", "plate": "assets/serial/locations/marche_canal.webp", "own": False},
    "stairwell": {"name_fr": "L'escalier", "plate": "assets/serial/locations/user_apartment.webp", "own": False},
    "odile_flat": {"name_fr": "L'appartement d'Odile", "plate": "assets/serial/locations/user_apartment.webp", "own": False},
    "user_apartment": {"name_fr": "Ton studio", "plate": "assets/serial/locations/user_apartment.webp", "own": True},
    "marin_lila_flat": {"name_fr": "L'appartement de Marin et Lila", "plate": "assets/serial/locations/marin_lila_flat.webp", "own": True},
    "ngo_office": {"name_fr": "Le bureau de l'ONG de Marin", "plate": "assets/serial/locations/ngo_office.webp", "own": True},
    "mairie": {"name_fr": "La mairie du 10e", "plate": "assets/serial/locations/office_admin.webp", "own": False},
    "marchand_office": {"name_fr": "La gérance Marchand", "plate": "assets/serial/locations/office_admin.webp", "own": False},
    "notaire": {"name_fr": "Chez Maître Vasseur", "plate": "assets/serial/locations/office_admin.webp", "own": False},
    "gare_de_lest": {"name_fr": "La gare de l'Est", "plate": "assets/serial/locations/metro_platform.webp", "own": False},
    "rue_de_lancry": {"name_fr": "La rue de Lancry", "plate": "assets/serial/locations/marche_canal.webp", "own": False},
    "gus_loft": {"name_fr": "Le « château » de Gus", "plate": "assets/serial/locations/gus_loft.webp", "own": True},
    "boulangerie": {"name_fr": "La boulangerie de Mme Diallo", "plate": "assets/serial/locations/marche_canal.webp", "own": False},
    "ecole": {"name_fr": "La classe de Lila", "plate": "assets/serial/locations/ngo_office.webp", "own": False},
    "toit": {"name_fr": "Le toit de l'immeuble", "plate": "assets/serial/locations/buttes_chaumont.webp", "own": False},
    "newsroom": {"name_fr": "La rédaction de Romy", "plate": "assets/serial/locations/newsroom.webp", "own": True},
    "marche_canal": {"name_fr": "Le marché du canal", "plate": "assets/serial/locations/marche_canal.webp", "own": True},
    "buttes_chaumont": {"name_fr": "Le parc des Buttes-Chaumont", "plate": "assets/serial/locations/buttes_chaumont.webp", "own": True},
    "metro_platform": {"name_fr": "Le quai du métro", "plate": "assets/serial/locations/metro_platform.webp", "own": True},
    "brocante": {"name_fr": "La brocante", "plate": "assets/serial/locations/brocante.webp", "own": True},
}


def season_location_ids(season_id: str = "s1") -> set[str]:
    return set(SEASON_ONE_LOCATIONS) if season_id == "s1" else set()


def plate_for(location_id: str | None) -> str | None:
    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    return f"/{row['plate']}" if row else None


def location_name_fr(location_id: str | None) -> str:
    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    return str(row["name_fr"]) if row else str(location_id or "")


# ---------------------------------------------------------------------------
# The season's world bible
# ---------------------------------------------------------------------------

_OVERLAY_ONLY = {
    "_about",
    "setting_locations",
    "drop_locations",
    "visual_characters",
    "visual_locations",
    "generation_guardrails_add",
}


@lru_cache(maxsize=4)
def _season_world(season_id: str) -> dict[str, Any]:
    from app.services.serial import SerialThreadService

    path = SEASON_ROOT / season_id / "world.json"
    overlay = json.loads(path.read_text(encoding="utf-8"))
    world = copy.deepcopy(SerialThreadService._load_world_bible())
    for key, value in overlay.items():
        if key not in _OVERLAY_ONLY:
            world[key] = copy.deepcopy(value)
    setting = dict(world.get("setting") or {})
    dropped = set(overlay.get("drop_locations") or [])
    places = [
        place
        for place in setting.get("recurring_locations") or []
        if isinstance(place, dict) and place.get("id") not in dropped
    ]
    known = {place.get("id") for place in places}
    places += [place for place in overlay.get("setting_locations") or [] if place.get("id") not in known]
    setting["recurring_locations"] = places
    world["setting"] = setting
    visual = dict(world.get("visual_design") or {})
    characters = dict(visual.get("characters") or {})
    characters.update(overlay.get("visual_characters") or {})
    visual["characters"] = characters
    locations = dict(visual.get("locations") or {})
    for location_id, row in (overlay.get("visual_locations") or {}).items():
        plate = SEASON_ONE_LOCATIONS.get(location_id, {}).get("plate") if season_id == "s1" else None
        locations[location_id] = {**row, "reference_images": [plate] if plate else []}
    visual["locations"] = locations
    world["visual_design"] = visual
    guardrails = dict(world.get("generation_guardrails") or {})
    guardrails.update(overlay.get("generation_guardrails_add") or {})
    world["generation_guardrails"] = guardrails
    # The old season's text must not leak into this one.
    for stale in ("season_two_situation", "season_three_situation", "cold_open"):
        world.pop(stale, None)
    return world


def season_world_bible(season_id: str) -> dict[str, Any]:
    """The world bible a life on this season is created with (a fresh copy)."""

    return copy.deepcopy(_season_world(season_id))


def season_cast_names(season_id: str) -> dict[str, str]:
    """Every speaker a season's pages name, minor voices included."""

    from app.services.season.format import load_season

    try:
        return {member.id: member.name for member in load_season(season_id).cast}
    except Exception:  # noqa: BLE001 - a name is never worth a failed read
        return {}
