"""WP-168 · the world a written season moved to: its places, its plates, its new faces.

A season the writer drafts (``app/services/season_writer.py``) may move the story (owner,
11 October): another city, another genre, another situation for the learner, anywhere
French is spoken. What it brings with it lives in the world bible, and this module is
what reads it:

* **Places.** A written place is a row of ``setting.recurring_locations`` with a
  ``plate_id`` and a ``brief`` (the place, three landmarks, the light; never people).
  Until its plate is painted it opens on a *stand-in*: the season-1 place of the same
  kind (a café on Le Mistral's counter, a quay on the quai de Valmy), so a panel never
  shows a broken image. The painting itself goes through the shared plate interface
  (``season.plates.paint_plate``), in the background, once per brief, lazily: when the
  season begins, and again whenever a story context finds a place still unpainted.
* **Who moved with the learner.** ``apply_setting_move`` lays a season's
  ``setting_move`` directive over the world: the new city and places, and an ``away``
  note on every cast member who did not travel (they write, they call; they are not on
  the page there).
* **New faces.** A written character carries ``rig``: parameters from a closed
  vocabulary (:data:`RIG_VOCABULARY`, mirrored in ``web-frontend/components/cast/
  rig-params.ts``) from which the drawn set builds an SVG figure that stands on the
  plate like the fixed cast. Anything outside the vocabulary falls back to a default,
  so a new face always draws.

No model is called here; painting is the plate interface's one image call.
"""

from __future__ import annotations

import hashlib
import logging
import re
import threading
import unicodedata
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_]{1,62}$")

# ---------------------------------------------------------------------------
# Places
# ---------------------------------------------------------------------------

#: The kinds of place a written season may name, and the season-1 place whose plate
#: stands in for each until the new one is painted. A lender that itself borrows a plate
#: today (the quai, the gare) improves with it when WP-165 paints its own.
PLACE_KINDS: dict[str, str] = {
    "cafe": "le_mistral",
    "bar": "le_mistral",
    "restaurant": "mistral_back_room",
    "kitchen": "mistral_back_room",
    "home": "user_apartment",
    "loft": "gus_loft",
    "stairwell": "stairwell",
    "office": "ngo_office",
    "administration": "mairie",
    "newsroom": "newsroom",
    "studio": "newsroom",
    "school": "ecole",
    "market": "marche_canal",
    "street": "rue_de_lancry",
    "shop": "brocante",
    "workshop": "brocante",
    "station": "gare_de_lest",
    "metro": "metro_platform",
    "quay": "quai_de_valmy",
    "harbour": "quai_de_valmy",
    "boat": "quai_de_valmy",
    "beach": "buttes_chaumont",
    "park": "buttes_chaumont",
    "garden": "buttes_chaumont",
    "countryside": "buttes_chaumont",
    "vineyard": "buttes_chaumont",
    "rooftop": "toit",
}
DEFAULT_PLACE_KIND = "home"
#: Words of a place's id or name → its kind, when the writer named none we know.
_KIND_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("station", ("gare", "station", "train", "tram", "aeroport", "airport")),
    ("metro", ("metro", "subway", "rer")),
    ("boat", ("ferry", "bateau", "peniche", "navire", "pont", "deck", "boat")),
    ("harbour", ("port", "harbour", "harbor", "marina", "phare", "digue")),
    ("quay", ("quai", "canal", "fleuve", "riviere", "berge", "lac")),
    ("beach", ("plage", "beach", "mer", "dune", "falaise")),
    ("cafe", ("cafe", "bar", "bistrot", "bistro", "maquis", "buvette", "comptoir")),
    ("restaurant", ("restaurant", "brasserie", "cantine", "cuisine", "kitchen")),
    ("market", ("marche", "souk", "halle", "halles", "foire", "market")),
    ("shop", ("boutique", "epicerie", "boulangerie", "magasin", "librairie", "kiosque", "atelier", "shop")),
    ("street", ("rue", "place", "avenue", "boulevard", "ruelle", "street", "square", "cour")),
    ("school", ("ecole", "classe", "lycee", "college", "universite", "school")),
    ("administration", ("mairie", "prefecture", "tribunal", "notaire", "consulat", "ambassade", "banque")),
    ("newsroom", ("redaction", "radio", "journal", "newsroom")),
    ("office", ("bureau", "office", "agence", "hopital", "clinique", "bibliotheque", "mediatheque", "salle")),
    ("vineyard", ("vigne", "vignes", "vignoble", "chai", "domaine")),
    ("rooftop", ("toit", "terrasse", "balcon", "rooftop")),
    ("park", ("parc", "jardin", "square", "park", "garden")),
    ("countryside", ("champ", "ferme", "foret", "colline", "montagne", "verger", "campagne", "route", "sentier")),
    ("stairwell", ("escalier", "palier", "couloir", "stairwell")),
    ("home", ("appartement", "studio", "chambre", "maison", "loft", "salon", "chez", "home", "flat")),
)


def _fold(text: Any) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: Any) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", _fold(text)) if token]


def place_kind(kind: Any = None, *texts: Any) -> str:
    """The writer's kind when it is one we know, else one guessed from the words."""

    named = _fold(kind).strip().replace(" ", "_")
    if named in PLACE_KINDS:
        return named
    tokens = [token for text in texts for token in _tokens(text)]
    for found, words in _KIND_WORDS:
        if any(word in tokens for word in words):
            return found
    return DEFAULT_PLACE_KIND


def plate_id_for(place_id: str, brief: str) -> str:
    """``w-<place>-<hash of the brief>``: one plate per brief, shared by any life whose
    written season describes the same place the same way, and never a stranger's plate
    under a place of the same id described otherwise."""

    slug = re.sub(r"[^a-z0-9_]+", "_", _fold(place_id)).strip("_")[:48] or "place"
    digest = hashlib.sha256(" ".join(str(brief or "").split()).encode("utf-8")).hexdigest()[:8]
    return f"w-{slug}-{digest}"


def place_row(world: dict | None, location_id: str | None) -> dict | None:
    """The world's own row for ``location_id`` (any place, written or authored)."""

    if not location_id or not isinstance(world, dict):
        return None
    setting = world.get("setting") or {}
    places = setting.get("recurring_locations") if isinstance(setting, dict) else None
    for place in places or []:
        if isinstance(place, dict) and str(place.get("id") or "") == str(location_id):
            return place
    return None


def is_written(place: dict | None) -> bool:
    return isinstance(place, dict) and bool(place.get("plate_id")) and bool(place.get("brief"))


def written_places(world: dict | None) -> list[dict]:
    """Every place of the world a written season brought (it has a plate to paint)."""

    setting = (world or {}).get("setting") or {}
    places = setting.get("recurring_locations") if isinstance(setting, dict) else None
    return [place for place in places or [] if is_written(place)]


def stand_in_location(place: dict | None) -> str:
    """The season-1 place whose plate a written place opens on until its own is painted."""

    place = place or {}
    lender = str(place.get("stand_in") or "")
    if lender:
        return lender
    return PLACE_KINDS[place_kind(place.get("type"), place.get("id"), place.get("name_fr"), place.get("name"))]


def stand_in_plate(place: dict | None) -> str | None:
    from app.services.season.world import plate_for

    return plate_for(stand_in_location(place))


def painted_plate(db: Session | None, plate_id: str | None) -> str | None:
    """The painted plate of ``plate_id``, or ``None`` while it is not painted (or the
    lookup fails: a stand-in is never an error)."""

    if not plate_id:
        return None
    from app.services.season import plates

    try:
        return plates.painted_url(db, plates.plate_key(plate_id))
    except Exception:  # noqa: BLE001 - a lookup never costs a panel its plate
        logger.debug("written_world: painted lookup failed for %s", plate_id, exc_info=True)
        return None


def plate_url(db: Session | None, place: dict | None) -> tuple[str | None, bool]:
    """``(url, stand_in)`` for a written place: its painted plate, else its stand-in."""

    if not is_written(place):
        return None, False
    painted = painted_plate(db, place.get("plate_id"))
    if painted:
        return painted, False
    return stand_in_plate(place), True


# --- painting, lazily, in the background --------------------------------------

#: Tests replace this with an inline or recording dispatcher: ``dispatcher(bind, places)``.
dispatcher: Callable[[Any, list[dict]], Any] | None = None
_EXECUTOR: ThreadPoolExecutor | None = None
_LOCK = threading.Lock()
#: Plate ids a painter of this process is working on (or gave up on until restart).
_IN_FLIGHT: set[str] = set()


def _executor() -> ThreadPoolExecutor:
    global _EXECUTOR
    with _LOCK:
        if _EXECUTOR is None:
            # One at a time: a new season's four or five places are not urgent, and the
            # image API is the same one the Revue and the day's plates use.
            _EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="season-plates")
        return _EXECUTOR


def unpainted(db: Session | None, world: dict | None) -> list[dict]:
    return [place for place in written_places(world) if not painted_plate(db, place.get("plate_id"))]


def schedule_painting(db: Session | None, places: Iterable[dict]) -> list[str]:
    """Paint these written places in the background; returns the plate ids queued.

    Never waits and never raises. A place already painted, or already queued in this
    process, is skipped; when painting is off (flag, key, storage) nothing is queued
    and the stand-ins stay.
    """

    wanted = [place for place in places if is_written(place)]
    if not wanted or db is None:
        return []
    try:
        from app.services.season import plates

        reason = plates.generation_unavailable_reason()
    except Exception as exc:  # noqa: BLE001
        reason = str(exc)
    if reason and dispatcher is None:
        logger.info("written_world: %s new place(s) keep their stand-ins (%s)", len(wanted), reason)
        return []
    with _LOCK:
        fresh = [place for place in wanted if place["plate_id"] not in _IN_FLIGHT]
        _IN_FLIGHT.update(place["plate_id"] for place in fresh)
    if not fresh:
        return []
    rows = [
        {key: place.get(key) for key in ("id", "plate_id", "brief", "name_fr", "name")}
        for place in fresh
    ]
    try:
        bind = db.get_bind()
        if dispatcher is not None:
            dispatcher(bind, rows)
        else:
            _executor().submit(paint_places, bind, rows)
    except Exception:  # noqa: BLE001 - the stand-ins stay
        logger.exception("written_world: could not queue %s plate(s)", len(rows))
        with _LOCK:
            _IN_FLIGHT.difference_update(row["plate_id"] for row in rows)
        return []
    return [row["plate_id"] for row in rows]


def ensure_painting(db: Session | None, world: dict | None) -> list[str]:
    """The lazy half: any written place of this world still on its stand-in is queued."""

    try:
        return schedule_painting(db, unpainted(db, world))
    except Exception:  # noqa: BLE001 - a story context never fails on a plate
        logger.debug("written_world: ensure_painting failed", exc_info=True)
        return []


def paint_places(bind: Any, places: list[dict]) -> dict[str, str]:
    """Paint each place once through ``season.plates.paint_plate``; ``{plate_id: url}``.

    Runs on its own session. Painting off stops the run (the stand-ins stay); one
    place's failure does not stop the others. A place that failed is released, so a
    later story context may queue it again.
    """

    from sqlalchemy.orm import Session as OrmSession

    from app.services.season import plates

    done: dict[str, str] = {}
    try:
        with OrmSession(bind=bind) as db:
            for place in places:
                plate_id = str(place.get("plate_id") or "")
                try:
                    done[plate_id] = plates.paint_plate(
                        db,
                        plates.plate_key(plate_id),
                        str(place.get("brief") or ""),
                        name_fr=str(place.get("name_fr") or place.get("name") or place.get("id") or plate_id),
                    )
                except plates.SeasonPlateOff as exc:
                    logger.info("written_world: painting is off (%s); stand-ins stay", exc)
                    break
                except Exception:  # noqa: BLE001 - the next place still gets its plate
                    db.rollback()
                    logger.exception("written_world: plate %s not painted", plate_id)
    finally:
        with _LOCK:
            _IN_FLIGHT.difference_update(
                str(place.get("plate_id") or "") for place in places if place.get("plate_id") not in done
            )
    if done:
        logger.info("written_world: painted %s new place(s)", len(done))
    return done


# ---------------------------------------------------------------------------
# The move itself, laid over the world (``serial.merge_season_world_bible``)
# ---------------------------------------------------------------------------

#: What a cast member who stayed behind is, for the director (``living_story``).
AWAY_NOTE = (
    "Stayed in {old} when the story moved to {new}: only from afar (a message, a call, a "
    "letter, a visit someone plans), never physically on the page there."
)


def same_city(a: Any, b: Any) -> bool:
    return " ".join(_tokens(a)) == " ".join(_tokens(b))


def apply_setting_move(
    world: dict[str, Any], move: dict[str, Any], *, next_season: int, added: Iterable[str] = ()
) -> dict[str, Any]:
    """The world after a written season's ``setting_move`` (pure; returns a new dict).

    * the setting's city, region, neighbourhood, genre, tone and the learner's
      situation are the season's;
    * a season that changes city keeps only the places it names in ``keep_locations``;
      one that stays adds its new places to the old ones;
    * each new place is described for the director and the painted art set
      (``visual_design.locations``) and opens on its stand-in until painted;
    * after a change of city, every cast member who is not in ``travelling_cast`` (and
      was not added this season, ``added``) is ``away``; one who travels is not.
    """

    world = dict(world or {})
    setting = dict(world.get("setting") or {})
    old_city = setting.get("city")
    city = str(move.get("city") or "").strip() or old_city
    moved = bool(city) and bool(old_city) and not same_city(city, old_city)
    old_places = [
        dict(place) for place in setting.get("recurring_locations") or [] if isinstance(place, dict) and place.get("id")
    ]
    keep = {str(value) for value in move.get("keep_locations") or []}
    kept = [place for place in old_places if place["id"] in keep] if moved else old_places
    known = {place["id"] for place in kept}
    fresh: list[dict] = []
    for raw in move.get("places") or []:
        if not isinstance(raw, dict) or not raw.get("id") or raw["id"] in known:
            continue
        place = dict(raw)
        place.setdefault("plate_id", plate_id_for(place["id"], place.get("brief") or ""))
        place.setdefault("stand_in", stand_in_location(place))
        place.setdefault("written_season", int(next_season))
        fresh.append(place)
        known.add(place["id"])
    for key in ("region", "neighborhood", "genre", "tone", "situation"):
        if move.get(key):
            setting[key] = move[key]
    setting["city"] = city
    if moved:
        setting["previous_city"] = old_city
        setting["moved_in_season"] = int(next_season)
    setting["recurring_locations"] = kept + fresh
    world["setting"] = setting

    if fresh:
        visual = dict(world.get("visual_design") or {})
        locations = dict(visual.get("locations") or {})
        for place in fresh:
            locations[place["id"]] = {
                "canonical_descriptor": str(place.get("brief") or place.get("description") or ""),
                "reference_images": [],
            }
        visual["locations"] = locations
        world["visual_design"] = visual

    if moved:
        travelling = {str(value) for value in move.get("travelling_cast") or []}
        joined = {str(value) for value in added}
        cast = []
        for member in world.get("cast") or []:
            if not isinstance(member, dict):
                continue
            member = dict(member)
            member_id = str(member.get("id") or "")
            if member_id in travelling or member_id in joined or member_id == "user":
                member.pop("away", None)
            else:
                member["away"] = AWAY_NOTE.format(old=old_city, new=city)
            cast.append(member)
        world["cast"] = cast
    return world


# ---------------------------------------------------------------------------
# New faces: the drawn rig's parameters
# ---------------------------------------------------------------------------

#: The drawn cast's own colours (``web-frontend/components/cast/rigs/*``), by name.
RIG_COLOURS: tuple[str, ...] = (
    "ink", "navy", "cobalt", "sky", "red", "brick", "green", "pine", "olive", "ochre",
    "yellow", "charcoal", "slate", "grey", "stone", "cream", "brown",
)
#: Every parameter of a generated rig and its closed vocabulary. Mirrored, value for
#: value, in ``web-frontend/components/cast/rig-params.ts`` (a test checks the two).
RIG_VOCABULARY: dict[str, tuple[str, ...]] = {
    "build": ("slim", "medium", "broad"),
    "height": ("short", "medium", "tall"),
    "head": ("round", "oval", "long", "square"),
    "skin": ("porcelain", "light", "rose", "warm", "olive", "tan", "brown", "deep", "deeper", "deepest"),
    "hair": ("bald", "cropped", "short", "bob", "long", "wavy", "curly", "afro", "bun", "braids", "ponytail", "locs"),
    "hair_colour": ("black", "dark_brown", "brown", "chestnut", "auburn", "copper", "blond", "grey", "white"),
    "facial_hair": ("none", "stubble", "moustache", "beard"),
    "glasses": ("none", "round", "square"),
    "top": ("coat", "jacket", "jumper", "shirt", "dress", "apron", "overalls", "hoodie", "boubou", "suit", "uniform"),
    "top_colour": RIG_COLOURS,
    "bottom_colour": RIG_COLOURS,
    "accessory": ("none", "scarf", "beret", "cap", "headwrap", "earrings", "necklace"),
    "accessory_colour": RIG_COLOURS,
    "idle": ("bob", "bounce", "sway", "nod"),
}
RIG_DEFAULTS: dict[str, str] = {
    "build": "medium",
    "height": "medium",
    "head": "oval",
    "skin": "warm",
    "hair": "short",
    "hair_colour": "brown",
    "facial_hair": "none",
    "glasses": "none",
    "top": "jumper",
    "top_colour": "cobalt",
    "bottom_colour": "ink",
    "accessory": "none",
    "accessory_colour": "red",
    "idle": "bob",
}


def normalise_rig(raw: Any) -> dict[str, str]:
    """Every rig parameter, from the vocabulary; an unknown or missing value is the
    default (a new face always draws, never an error)."""

    raw = raw if isinstance(raw, dict) else {}
    out: dict[str, str] = {}
    for key, allowed in RIG_VOCABULARY.items():
        value = _fold(raw.get(key)).strip().replace(" ", "_").replace("-", "_")
        if key.endswith("colour") and value.endswith("_colour"):
            value = value[: -len("_colour")]
        out[key] = value if value in allowed else RIG_DEFAULTS[key]
    return out


def valid_slug(value: Any) -> bool:
    return bool(_SLUG.match(str(value or "")))
