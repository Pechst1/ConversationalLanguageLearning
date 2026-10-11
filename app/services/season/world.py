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
SEASON_ONE_LOCATIONS: dict[str, dict[str, Any]] = {
    "le_mistral": {"name_fr": "Le Mistral", "plate": "assets/serial/locations/le_mistral-counter.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "mistral_back_room": {"name_fr": "L'arrière-salle du Mistral", "plate": "assets/serial/locations/le_mistral-booth.webp", "own": False, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    # The quai has no plate of its own yet. The market plate (a sunny day, stalls) told
    # the wrong story for T1's opening (night, rain, the red neon); the café's counter
    # looks out on the rainy quai at night through its windows (2026-10-02).
    "quai_de_valmy": {"name_fr": "Le quai de Valmy", "plate": "assets/serial/locations/le_mistral-counter.webp", "own": False, "geo": {"lat": 48.8712, "lon": 2.3646, "precision": "exact", "label_fr": "Quai de Valmy, Paris 10e"}},
    "stairwell": {"name_fr": "L'escalier", "plate": "assets/serial/locations/user_apartment.webp", "own": False, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "odile_flat": {"name_fr": "L'appartement d'Odile", "plate": "assets/serial/locations/user_apartment.webp", "own": False, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "user_apartment": {"name_fr": "Ton studio", "plate": "assets/serial/locations/user_apartment.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "marin_lila_flat": {"name_fr": "L'appartement de Marin et Lila", "plate": "assets/serial/locations/marin_lila_flat.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "ngo_office": {"name_fr": "Le bureau de l'ONG de Marin", "plate": "assets/serial/locations/ngo_office.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "mairie": {"name_fr": "La mairie du 10e", "plate": "assets/serial/locations/office_admin.webp", "own": False, "geo": {"lat": 48.8718, "lon": 2.3574, "precision": "exact", "label_fr": "Mairie du 10e, rue du Faubourg-Saint-Martin"}},
    "marchand_office": {"name_fr": "La gérance Marchand", "plate": "assets/serial/locations/office_admin.webp", "own": False, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "notaire": {"name_fr": "Chez Maître Vasseur", "plate": "assets/serial/locations/office_admin.webp", "own": False, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "gare_de_lest": {"name_fr": "La gare de l'Est", "plate": "assets/serial/locations/metro_platform.webp", "own": False, "geo": {"lat": 48.8768, "lon": 2.3592, "precision": "exact", "label_fr": "Gare de l'Est"}},
    "rue_de_lancry": {"name_fr": "La rue de Lancry", "plate": "assets/serial/locations/marche_canal.webp", "own": False, "geo": {"lat": 48.87, "lon": 2.3615, "precision": "exact", "label_fr": "Rue de Lancry, Paris 10e"}},
    "gus_loft": {"name_fr": "Le « château » de Gus", "plate": "assets/serial/locations/gus_loft.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "boulangerie": {"name_fr": "La boulangerie de Mme Diallo", "plate": "assets/serial/locations/marche_canal.webp", "own": False, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "ecole": {"name_fr": "La classe de Lila", "plate": "assets/serial/locations/ngo_office.webp", "own": False, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "toit": {"name_fr": "Le toit de l'immeuble", "plate": "assets/serial/locations/buttes_chaumont.webp", "own": False, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "newsroom": {"name_fr": "La rédaction de Romy", "plate": "assets/serial/locations/newsroom.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "marche_canal": {"name_fr": "Le marché du canal", "plate": "assets/serial/locations/marche_canal.webp", "own": True, "geo": {"lat": 48.8725, "lon": 2.365, "precision": "exact", "label_fr": "Le marché du canal, quai de Valmy, Paris 10e"}},
    "buttes_chaumont": {"name_fr": "Le parc des Buttes-Chaumont", "plate": "assets/serial/locations/buttes_chaumont.webp", "own": True, "geo": {"lat": 48.8809, "lon": 2.3828, "precision": "exact", "label_fr": "Parc des Buttes-Chaumont, Paris 19e"}},
    "metro_platform": {"name_fr": "Le quai du métro", "plate": "assets/serial/locations/metro_platform.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.361, "precision": "exact", "label_fr": "Métro Jacques Bonsergent, Paris 10e"}},
    "brocante": {"name_fr": "La brocante", "plate": "assets/serial/locations/brocante.webp", "own": True, "geo": {"lat": 48.8718, "lon": 2.364, "precision": "exact", "label_fr": "La brocante du canal Saint-Martin, Paris 10e"}},
}


def season_location_ids(season_id: str = "s1", *, world: dict[str, Any] | None = None) -> set[str]:
    """The season's own places, plus (WP-168) the places a written season brought."""

    from app.services.season.written_world import written_places

    own = set(SEASON_ONE_LOCATIONS) if season_id == "s1" else set()
    return own | {str(place["id"]) for place in written_places(world)}


def plate_for(location_id: str | None, *, world: dict[str, Any] | None = None) -> str | None:
    """The static plate of a place. WP-168: a place a written season brought (not in
    the table above) opens on its stand-in, the plate of a season-1 place of its kind;
    ``season.plates.plate_url_for`` / ``written_world.plate_url`` give the painted one."""

    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    if row:
        return f"/{row['plate']}"
    from app.services.season.written_world import is_written, place_row, stand_in_plate

    place = place_row(world, location_id)
    return stand_in_plate(place) if is_written(place) else None


def location_name_fr(location_id: str | None, *, world: dict[str, Any] | None = None) -> str:
    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    if row:
        return str(row["name_fr"])
    from app.services.season.written_world import place_row

    place = place_row(world, location_id) or {}
    return str(place.get("name_fr") or place.get("name") or location_id or "")


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
