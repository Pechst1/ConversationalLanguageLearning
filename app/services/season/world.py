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
from collections.abc import Iterable
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


def season_location_ids(season_id: str = "s1") -> set[str]:
    """The places a page of the season may name: the bible's, and the places its learners'
    stories named that the forge has built since (``story_places``)."""

    authored = set(SEASON_ONE_LOCATIONS) if season_id == "s1" else set()
    return authored | set(story_places(season_id))


# ---------------------------------------------------------------------------
# Where the 3D world can play a page (the forge's register)
# ---------------------------------------------------------------------------


#: Written by ``scripts/forge/forge.py stages`` into each season's folder.
STAGES_FILE = "stages.json"


@lru_cache(maxsize=4)
def built_stages(season_id: str = "s1") -> dict[str, str]:
    """Each place of the season Le Quartier has built, to the built place a page set
    there plays in. The forge writes ``stages.json`` from the 3D world's register
    (``scripts/forge/forge.py stages``); a season without one has no 3D world to keep
    in step with, and every place stays open."""

    try:
        data = json.loads((SEASON_ROOT / season_id / STAGES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    stages = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(stages, dict):
        return {}
    return {str(key): str(value) for key, value in stages.items() if key and value}


def unbuilt_places(season_id: str = "s1") -> dict[str, str]:
    """The places the season names that Le Quartier has not built yet, id to French name
    (``to_be_built`` in ``stages.json``, written by the forge with ``stages``). A
    generated page is never set there; a page may name one, as a promise (S5)."""

    try:
        data = json.loads((SEASON_ROOT / season_id / STAGES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = data.get("to_be_built") if isinstance(data, dict) else None
    if not isinstance(rows, dict):
        return {}
    return {str(key): str(value) for key, value in rows.items() if key and value}


#: The plate a place the stories named opens on in the Feuilleton until its own is drawn.
STORY_PLACE_PLATE = "assets/serial/locations/marche_canal.webp"


@lru_cache(maxsize=4)
def story_places(season_id: str = "s1") -> dict[str, dict[str, Any]]:
    """The places the season's learners' stories named and the forge has built since
    («Erst erwähnen, dann betreten»): a page mentioned «la librairie de la rue Bichat», the
    forge built it over a night, and from then on the night may set pages there. The forge
    writes them into ``stages.json`` (``places``) with their French name and what they look
    like; each one is also in ``stages``, where it plays."""

    try:
        data = json.loads((SEASON_ROOT / season_id / STAGES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    places = data.get("places") if isinstance(data, dict) else None
    stages = data.get("stages") if isinstance(data, dict) else None
    if not isinstance(places, dict) or not isinstance(stages, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for place_id, row in places.items():
        if not isinstance(row, dict) or not row.get("name_fr") or place_id not in stages:
            continue
        out[str(place_id)] = {
            "id": str(place_id),
            "name": str(row.get("name") or row["name_fr"]),
            "name_fr": str(row["name_fr"]),
            "type": str(row.get("type") or "story"),
            "description": str(row.get("description") or row["name_fr"]),
        }
    return out


def playable_locations(
    locations: list[dict[str, Any]], season_id: str, *, keep: Iterable[str | None] = ()
) -> list[dict[str, Any]]:
    """The places a generated page of ``season_id`` may be set in: the ones the 3D
    world has built, and ``keep`` (a room the open chapter may not leave). A page set
    anywhere else would play in the Feuilleton only, and the quarter would stand still
    on the quai while the story moves on. Fewer than two left (a register not written
    yet, a world bible that names other places) leaves the list as it was."""

    built = set(built_stages(season_id))
    if not built:
        return list(locations)
    wanted = built | {str(item) for item in keep if item}
    kept = [place for place in locations if str(place.get("id") or "") in wanted]
    return kept if len(kept) >= 2 else list(locations)


def plate_for(location_id: str | None) -> str | None:
    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    if row:
        return f"/{row['plate']}"
    return f"/{STORY_PLACE_PLATE}" if str(location_id or "") in story_places("s1") else None


def location_name_fr(location_id: str | None) -> str:
    row = SEASON_ONE_LOCATIONS.get(str(location_id or "")) or story_places("s1").get(str(location_id or ""))
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
