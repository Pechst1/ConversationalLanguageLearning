"""The places of a season (WP-111), and the plate each one opens on.

The world bible's ``setting.recurring_locations`` is where the director reads places
from; this module is where the season format checks them. Season 1 («La clé
d'Odile», ``docs/story/season-1/10-lieux-et-images.md``) adds Odile's flat, the
stairwell, M. Marchand's office, the mairie, the notary's, the Gare de l'Est, the
rue de Lancry, the bakery, Lila's classroom and the roof. Until WP-165 twelve of
them borrowed the nearest existing plate; since WP-165 every place has its own,
painted from its brief in :data:`SEASON_ONE_PLATE_BRIEFS` (name, three landmarks,
the light) and committed next to the originals.

A place's ``light`` is the light its committed plate is painted in. A scene the
director sets in another light or weather gets a painted variant of the plate
(``app/services/season/plates.py``), painted lazily the first time it is asked for.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.services.season.format import SEASON_ROOT

#: Where a ``plate`` path is served from (the backend image ships the plates too: a
#: painted variant is an edit of its place's committed plate).
PUBLIC_ROOT = Path(__file__).resolve().parents[3] / "web-frontend" / "public"

#: Every place a season-1 page may be set in: its French name, the plate it opens
#: on (a path under ``web-frontend/public``), and whether that plate is its own.
SEASON_ONE_LOCATIONS: dict[str, dict[str, Any]] = {
    "le_mistral": {"name_fr": "Le Mistral", "plate": "assets/serial/locations/le_mistral-counter.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "mistral_back_room": {"name_fr": "L'arrière-salle du Mistral", "plate": "assets/serial/locations/mistral_back_room.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    # WP-165: the quai's own plate is painted at night in the rain, T1's opening (the
    # market plate, a sunny day with stalls, told the wrong story; 2026-10-02).
    "quai_de_valmy": {"name_fr": "Le quai de Valmy", "plate": "assets/serial/locations/quai_de_valmy.webp", "own": True, "geo": {"lat": 48.8712, "lon": 2.3646, "precision": "exact", "label_fr": "Quai de Valmy, Paris 10e"}},
    "stairwell": {"name_fr": "L'escalier", "plate": "assets/serial/locations/stairwell.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "odile_flat": {"name_fr": "L'appartement d'Odile", "plate": "assets/serial/locations/odile_flat.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "user_apartment": {"name_fr": "Ton studio", "plate": "assets/serial/locations/user_apartment.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "marin_lila_flat": {"name_fr": "L'appartement de Marin et Lila", "plate": "assets/serial/locations/marin_lila_flat.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "ngo_office": {"name_fr": "Le bureau de l'ONG de Marin", "plate": "assets/serial/locations/ngo_office.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "mairie": {"name_fr": "La mairie du 10e", "plate": "assets/serial/locations/mairie.webp", "own": True, "geo": {"lat": 48.8718, "lon": 2.3574, "precision": "exact", "label_fr": "Mairie du 10e, rue du Faubourg-Saint-Martin"}},
    "marchand_office": {"name_fr": "La gérance Marchand", "plate": "assets/serial/locations/marchand_office.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "notaire": {"name_fr": "Chez Maître Vasseur", "plate": "assets/serial/locations/notaire.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "gare_de_lest": {"name_fr": "La gare de l'Est", "plate": "assets/serial/locations/gare_de_lest.webp", "own": True, "geo": {"lat": 48.8768, "lon": 2.3592, "precision": "exact", "label_fr": "Gare de l'Est"}},
    "rue_de_lancry": {"name_fr": "La rue de Lancry", "plate": "assets/serial/locations/rue_de_lancry.webp", "own": True, "geo": {"lat": 48.87, "lon": 2.3615, "precision": "exact", "label_fr": "Rue de Lancry, Paris 10e"}},
    "gus_loft": {"name_fr": "Le « château » de Gus", "plate": "assets/serial/locations/gus_loft.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "boulangerie": {"name_fr": "La boulangerie de Mme Diallo", "plate": "assets/serial/locations/boulangerie.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "ecole": {"name_fr": "La classe de Lila", "plate": "assets/serial/locations/ecole.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "toit": {"name_fr": "Le toit de l'immeuble", "plate": "assets/serial/locations/toit.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.3632, "precision": "exact", "label_fr": "Le Mistral, quai de Valmy, Paris 10e"}},
    "newsroom": {"name_fr": "La rédaction de Romy", "plate": "assets/serial/locations/newsroom.webp", "own": True, "geo": {"lat": 48.8761, "lon": 2.3607, "precision": "city", "label_fr": "Paris 10e"}},
    "marche_canal": {"name_fr": "Le marché du canal", "plate": "assets/serial/locations/marche_canal.webp", "own": True, "geo": {"lat": 48.8725, "lon": 2.365, "precision": "exact", "label_fr": "Le marché du canal, quai de Valmy, Paris 10e"}},
    "buttes_chaumont": {"name_fr": "Le parc des Buttes-Chaumont", "plate": "assets/serial/locations/buttes_chaumont.webp", "own": True, "geo": {"lat": 48.8809, "lon": 2.3828, "precision": "exact", "label_fr": "Parc des Buttes-Chaumont, Paris 19e"}},
    "metro_platform": {"name_fr": "Le quai du métro", "plate": "assets/serial/locations/metro_platform.webp", "own": True, "geo": {"lat": 48.8706, "lon": 2.361, "precision": "exact", "label_fr": "Métro Jacques Bonsergent, Paris 10e"}},
    "brocante": {"name_fr": "La brocante", "plate": "assets/serial/locations/brocante.webp", "own": True, "geo": {"lat": 48.8718, "lon": 2.364, "precision": "exact", "label_fr": "La brocante du canal Saint-Martin, Paris 10e"}},
}


#: WP-165: what the image model paints for each place, people-free (the drawn cast stands
#: on it). ``brief`` is the place's name and three landmarks, never the light; ``light``
#: is the light and weather of the committed plate (``note`` says it in words);
#: ``outdoor`` decides how rain looks; ``variants`` False means light and weather
#: never change there (a metro platform underground). Grounded in
#: ``docs/story/season-1/10-lieux-et-images.md`` and the season's ``world.json``.
SEASON_ONE_PLATE_BRIEFS: dict[str, dict[str, Any]] = {
    "le_mistral": {
        "brief": "Le Mistral, a narrow corner café-bar on the quai de Valmy in Paris: a worn zinc counter with a hinged flap and a small round-topped stool at its far end, a long mirror and shelves of bottles behind the bar, an ox-blood leather booth at the back, tall windows onto the canal",
        "light": {"time_of_day": "night", "weather": "rain", "note": "night outside with rain on the windows, warm amber lamps inside"},
        "outdoor": False,
    },
    "mistral_back_room": {
        "brief": "The back room of Le Mistral, a small Paris café rebuilt after a fire: fresh plaster a slightly whiter white than the old walls, an open grey electrical board on the wall, stacked wooden crates of bottles, an easel covered with a white sheet, a door ajar onto the bar",
        "light": {"time_of_day": "evening", "weather": "dry", "note": "evening, one bare bulb overhead and warm amber light spilling in from the bar"},
        "outdoor": False,
    },
    "quai_de_valmy": {
        "brief": "The quai de Valmy on the Canal Saint-Martin in Paris: a green iron arched footbridge over black water, a lock gate, bare plane trees and old street lamps along the cobbled quay, a corner café with a tall vertical red neon sign glowing above its door, a moored barge",
        "light": {"time_of_day": "night", "weather": "rain", "note": "late-autumn night in steady rain, the red neon and the lamps broken into flat stripes on the wet cobbles and the water"},
        "outdoor": True,
    },
    "stairwell": {
        "brief": "The stairwell of an old Paris building: worn wooden steps curving up with a black iron banister, a tall stair window onto a courtyard, a round push-button light switch glowing on the wall, a first-floor door with a small brass plate",
        "light": {"time_of_day": "evening", "weather": "dry", "note": "evening, one bare bulb on a timer and the courtyard window deep blue"},
        "outdoor": False,
    },
    "odile_flat": {
        "brief": "Odile's flat, a small two-room Paris flat on the first floor above a corner café, kept exactly as she left it: a woman's moss-green coat on a hook by the door and felt slippers side by side under a chair, a kitchen table with an old instant camera beside a cup, a wall calendar with a plain grid, a tall window with half-open shutters onto a narrow balcony over the canal",
        "light": {"time_of_day": "morning", "weather": "dry", "note": "morning, thin bars of sunflower light through the shutters with dust hanging in them; a room that waited, tidy, never decayed"},
        "outdoor": False,
    },
    "user_apartment": {
        "brief": "Your studio, a sixth-floor walk-up in Paris: a tall French window with a small iron balcony onto zinc roofs and chimney pots, a cast-iron radiator painted red, a tiny kitchenette corner, moving boxes and a duffel bag on the floor",
        "light": {"time_of_day": "evening", "weather": "dry", "note": "dusk, the sky deep blue over the roofs, a small lamp lit"},
        "outdoor": False,
    },
    "marin_lila_flat": {
        "brief": "Marin and Lila's flat in Paris: a cluttered kitchen-living room, Lila's canvases stacked against the wall and an easel, a round café table with mismatched chairs, plants everywhere, a fridge with a folder held by a fish-shaped magnet",
        "light": {"time_of_day": "day", "weather": "dry", "note": "warm daylight through the window"},
        "outdoor": False,
    },
    "ngo_office": {
        "brief": "Marin's NGO office in Paris: desks piled with folders, a big fern, a world map on the wall, a projected chart of coloured bars, tall windows onto a Paris street",
        "light": {"time_of_day": "day", "weather": "dry", "note": "plain daylight"},
        "outdoor": False,
    },
    "mairie": {
        "brief": "The mairie of the 10th arrondissement in Paris: a grand hall with tall arched windows and a stone staircase up to a second floor, a long wooden counter behind a glass screen, a row of waiting chairs, a ticket machine, no lift",
        "light": {"time_of_day": "morning", "weather": "dry", "note": "bright institutional morning light through the tall windows"},
        "outdoor": False,
    },
    "marchand_office": {
        "brief": "La gérance Marchand, a small property-management office on the second floor of an old Paris building: a whole wall of key boards with hundreds of old keys on hooks, grey metal filing cabinets, a wooden desk with one green desk lamp and a small framed photograph, a narrow camp bed made with hospital corners in the middle of the room",
        "light": {"time_of_day": "day", "weather": "dry", "note": "cold grey daylight from one window, the desk lamp the only warm light"},
        "outdoor": False,
    },
    "notaire": {
        "brief": "Chez Maître Vasseur, a notary's office in Paris: a long polished dark-wood table with leather chairs, a fountain pen beside a closed folder, tall windows onto a boulevard with plane trees, shelves of bound volumes",
        "light": {"time_of_day": "day", "weather": "dry", "note": "calm grey-gold afternoon light"},
        "outdoor": False,
    },
    "gare_de_lest": {
        "brief": "The Gare de l'Est in Paris: a long platform under a vast arched iron-and-glass roof, a long white high-speed train waiting, a departures board of blank yellow tiles, luggage trolleys and a bench",
        "light": {"time_of_day": "morning", "weather": "dry", "note": "pale winter morning light falling through the glass roof"},
        "outdoor": True,
    },
    "rue_de_lancry": {
        "brief": "The rue de Lancry, a narrow Paris street running off the canal: tall pale stone façades with wrought-iron balconies, one third-floor window with an easel visible inside, a small café terrace and parked bicycles, the canal's footbridge glimpsed at the end",
        "light": {"time_of_day": "day", "weather": "dry", "note": "late-afternoon autumn light, yellow plane leaves on the pavement"},
        "outdoor": True,
    },
    "gus_loft": {
        "brief": "Gus's «château», a grand Paris loft: a red velvet armchair, a marble fireplace, a red heraldic banner with a golden lion, a mezzanine with a black iron railing, tall windows on the rooftops",
        "light": {"time_of_day": "day", "weather": "dry", "note": "bright daylight"},
        "outdoor": False,
    },
    "boulangerie": {
        "brief": "Mme Diallo's boulangerie, a small Paris bakery: baguettes standing in a wicker rack behind the counter, a floured wooden counter with paper bags and a tray of croissants, a glass case of pastries, a tiled floor and a shop window onto the street",
        "light": {"time_of_day": "morning", "weather": "dry", "note": "early morning, warm light inside, the street outside still blue"},
        "outdoor": False,
    },
    "ecole": {
        "brief": "Lila's classroom, a French primary-school class: rows of small wooden desks and chairs, children's paintings pinned on every wall, a green chalkboard with chalk drawings and no writing, tall windows onto a school courtyard with a plane tree",
        "light": {"time_of_day": "day", "weather": "dry", "note": "bright late-morning daylight"},
        "outdoor": False,
    },
    "toit": {
        "brief": "The roof of an old Paris building: sloping grey zinc roofs, rows of terracotta chimney pots, an open skylight glowing from below, the Canal Saint-Martin and its footbridge far below",
        "light": {"time_of_day": "night", "weather": "dry", "note": "a clear night with a thin moon, lamp reflections on the canal"},
        "outdoor": True,
    },
    "newsroom": {
        "brief": "Romy's newsroom in Paris: rows of desks with screens, a wall of monitors, hanging lamps, glass partitions, windows onto Paris façades",
        "light": {"time_of_day": "day", "weather": "dry", "note": "daylight"},
        "outdoor": False,
    },
    "marche_canal": {
        "brief": "The canal market on the quai de Valmy: striped awnings over a fish stall and a cheese stall, crates of vegetables, a green iron footbridge over the canal behind, plane trees and a street lamp",
        "light": {"time_of_day": "day", "weather": "dry", "note": "a bright sunny day"},
        "outdoor": True,
    },
    "buttes_chaumont": {
        "brief": "The parc des Buttes-Chaumont in Paris: a little temple on top of a rocky cliff, a red suspension footbridge over a lake, winding paths with lamp posts, big trees",
        "light": {"time_of_day": "day", "weather": "dry", "note": "a sunny afternoon"},
        "outdoor": True,
    },
    "metro_platform": {
        "brief": "The Jacques Bonsergent metro platform in Paris: white bevelled tiles in a vaulted tunnel, a red bench, the dark mouth of the tunnel, the rails, hanging signal lamps",
        "light": {"time_of_day": "day", "weather": "dry", "note": "flat electric light underground"},
        "outdoor": False,
        "variants": False,
    },
    "brocante": {
        "brief": "The brocante by the canal in Paris: trestle tables of old frames, globes, vases and teapots, a big red parasol, old trunks, the quay and a bridge behind",
        "light": {"time_of_day": "day", "weather": "dry", "note": "a bright day with a few clouds"},
        "outdoor": True,
    },
}


def place_brief(location_id: str | None, *, with_light: bool = True) -> str | None:
    """WP-165: the plate brief of a season place (name + three landmarks [+ the light])."""

    row = SEASON_ONE_PLATE_BRIEFS.get(str(location_id or ""))
    if not row:
        return None
    if not with_light:
        return str(row["brief"])
    return f"{row['brief']}; {row['light']['note']}"


def place_light(location_id: str | None) -> tuple[str, str] | None:
    """WP-165: the (time_of_day, weather) the place's committed plate is painted in."""

    row = SEASON_ONE_PLATE_BRIEFS.get(str(location_id or ""))
    if not row:
        return None
    return str(row["light"]["time_of_day"]), str(row["light"]["weather"])


def place_is_outdoor(location_id: str | None) -> bool:
    return bool((SEASON_ONE_PLATE_BRIEFS.get(str(location_id or "")) or {}).get("outdoor"))


def place_takes_variants(location_id: str | None) -> bool:
    """False for a place whose light never changes (underground); True for any other,
    a place painted for a later season included."""

    return bool((SEASON_ONE_PLATE_BRIEFS.get(str(location_id or "")) or {}).get("variants", True))


def static_plate_path(location_id: str | None) -> Path | None:
    """The committed plate file under ``web-frontend/public`` (a painted variant's
    reference image), or ``None`` when the place has none or the file is not shipped."""

    row = SEASON_ONE_LOCATIONS.get(str(location_id or ""))
    if not row:
        return None
    path = PUBLIC_ROOT / str(row["plate"])
    return path if path.is_file() else None


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
