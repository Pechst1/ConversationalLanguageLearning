"""Geo: a place gets coordinates (WP-120 §3).

:func:`resolve_place` gives a dossier :class:`~app.services.revue.dossier.Place` a
:class:`~app.services.revue.dossier.Geo` in the four steps of §3.2:

1. **The gazetteer** (``app/data/geo/gazetteer.json``): a hand-kept table matched by
   folded name and alias on the place's ``id``, its ``name_fr`` and the capitalised
   words of its ``brief``. A precise entry (a landmark, a market, an institution, a
   venue: precision ``exact``) wins outright.
2. **The builder's proposal**, accepted only inside a France box (:data:`FRANCE_BBOXES`)
   and, when a city is named (``city_hint`` or a city the gazetteer found in the
   place's text), within :data:`MAX_CITY_DISTANCE_KM` of it.
3. **The city centroid** from ``city_hint`` or the city (or arrondissement) the
   gazetteer found, precision ``city``; a wine region found alone gives its centroid,
   precision ``region``.
4. **No geo**: ``None``, logged once as ``revue_place_without_geo`` so the gazetteer grows.

:func:`geo_problems` is the meaning check of §3.4 (``check_geo`` in ``checks.py`` wraps
it); :func:`geocode_dossier` resolves every place, downgrading a Paris-centre «exact» to
``city`` and dropping (then re-resolving without the proposal) anything else that fails.

Matching folds names (:func:`fold_name`): accents stripped, lower case, ``œ``→``oe``,
punctuation split, French particles (``de``, ``la``, ``l'``, ``à``…) dropped, so
«marché d'Aligre», ``marche_aligre`` and «Marché Aligre» are the same three tokens.
In ``name_fr`` and ``brief`` a match needs one capitalised (or numbered) word, so
«les tours» is not Tours.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from loguru import logger

from app.services.revue.dossier import EditorialDossier, Geo, Place

GAZETTEER_PATH = Path(__file__).resolve().parents[2] / "data" / "geo" / "gazetteer.json"

#: A proposal or a geo further than this from the place's named city is rejected (§3.2, §3.4).
MAX_CITY_DISTANCE_KM = 25.0
#: The coordinates every geocoder gives for «Paris», and the radius the check calls "the centre".
PARIS_CENTROID: tuple[float, float] = (48.8566, 2.3522)
PARIS_CENTROID_RADIUS_KM = 0.3

#: ``name`` → ``(lat_min, lat_max, lon_min, lon_max)``. Coarse on purpose: a box, not a border.
FRANCE_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "metropolitan": (42.3, 51.15, -5.2, 8.3),
    "corse": (41.3, 43.1, 8.5, 9.6),
    "guadeloupe": (15.8, 16.55, -61.85, -60.95),
    "martinique": (14.35, 14.9, -61.25, -60.8),
    "guyane": (2.1, 5.8, -54.65, -51.6),
    "reunion": (-21.4, -20.85, 55.2, 55.85),
    "mayotte": (-13.05, -12.6, 44.95, 45.35),
}

_PARTICLES = frozenset({"a", "au", "aux", "d", "de", "des", "du", "en", "et", "l", "la", "le", "les"})
_TOKEN = re.compile(r"\w+", re.UNICODE)
_LIGATURES = str.maketrans({"œ": "oe", "Œ": "oe", "æ": "ae", "Æ": "ae", "ß": "ss", "_": " "})
#: Single-word aliases too common to trust inside a snake_case ``place.id``.
_ID_AMBIGUOUS = frozenset({"tours", "nice", "nation", "orange", "vienne", "seine"})
#: Kinds whose entry is a point (precision ``exact``), ranked before cities and regions.
_CITY_KINDS = frozenset({"city", "arrondissement"})


def _fold_token(token: str) -> str:
    decomposed = unicodedata.normalize("NFKD", token.translate(_LIGATURES))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _tokens(text: str | None) -> list[tuple[str, str]]:
    """``(folded, original)`` pairs, particles dropped."""

    pairs: list[tuple[str, str]] = []
    for raw in _TOKEN.findall(str(text or "").translate(_LIGATURES)):
        folded = _fold_token(raw)
        if folded and folded not in _PARTICLES:
            pairs.append((folded, raw))
    return pairs


def fold_name(text: str | None) -> str:
    """The gazetteer's alias form: «Marché d'Aligre» → ``"marche aligre"``."""

    return " ".join(folded for folded, _ in _tokens(text))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(min(1.0, a)))


def in_france(lat: float, lon: float) -> str | None:
    """The name of the France box holding the point, or ``None``."""

    for name, (lat_min, lat_max, lon_min, lon_max) in FRANCE_BBOXES.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None


# ---------------------------------------------------------------------------
# The gazetteer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GazetteerEntry:
    id: str
    names: tuple[str, ...]
    lat: float
    lon: float
    precision: str
    label_fr: str
    kind: str
    parent: str | None = None
    verify: bool = False

    def geo(self, precision: str | None = None) -> Geo:
        return Geo(lat=self.lat, lon=self.lon, precision=precision or self.precision, label_fr=self.label_fr)  # type: ignore[arg-type]

    @property
    def rank(self) -> int:
        """Most specific first: a point, an arrondissement, a city, a region."""

        if self.precision == "exact":
            return 0
        return {"arrondissement": 1, "city": 2}.get(self.kind, 3)


@lru_cache(maxsize=1)
def load_gazetteer() -> tuple[GazetteerEntry, ...]:
    rows = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
    return tuple(
        GazetteerEntry(
            id=row["id"],
            names=tuple(row["names"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            precision=row["precision"],
            label_fr=row["label_fr"],
            kind=row["kind"],
            parent=row.get("parent"),
            verify=bool(row.get("verify", False)),
        )
        for row in rows
    )


@lru_cache(maxsize=1)
def _by_id() -> dict[str, GazetteerEntry]:
    return {entry.id: entry for entry in load_gazetteer()}


@lru_cache(maxsize=1)
def _aliases() -> tuple[tuple[tuple[str, ...], GazetteerEntry], ...]:
    """Every alias as a token tuple, longest first."""

    pairs = [(tuple(name.split()), entry) for entry in load_gazetteer() for name in entry.names if name]
    return tuple(sorted(pairs, key=lambda pair: -len(pair[0])))


def gazetteer_entry(entry_id: str) -> GazetteerEntry | None:
    return _by_id().get(entry_id)


def _find(text: str | None, *, from_id: bool = False) -> list[tuple[int, GazetteerEntry]]:
    """``(alias length, entry)`` for every alias found in ``text``."""

    pairs = _tokens(text.replace("_", " ") if from_id and text else text)
    folded = [token for token, _ in pairs]
    found: list[tuple[int, GazetteerEntry]] = []
    for alias, entry in _aliases():
        size = len(alias)
        if from_id and size == 1 and (len(alias[0]) < 4 or alias[0] in _ID_AMBIGUOUS):
            continue
        for start in range(len(folded) - size + 1):
            if tuple(folded[start : start + size]) != alias:
                continue
            originals = [raw for _, raw in pairs[start : start + size]]
            if from_id or any(raw[:1].isupper() or raw[:1].isdigit() for raw in originals):
                found.append((size, entry))
                break
    return found


def place_matches(place: Place, *, extra: str | None = None) -> list[GazetteerEntry]:
    """Gazetteer entries named by the place, most specific first (id/name before brief)."""

    scored: dict[str, tuple[tuple[int, int, int], GazetteerEntry]] = {}
    sources = (
        (0, place.id, True),
        (0, place.name_fr, False),
        (1, place.brief, False),
        (1, extra, False),
    )
    for where, text, from_id in sources:
        if not text:
            continue
        for size, entry in _find(text, from_id=from_id):
            key = (entry.rank, -size, where)
            if entry.id not in scored or key < scored[entry.id][0]:
                scored[entry.id] = (key, entry)
    return [entry for _, entry in sorted(scored.values(), key=lambda row: (row[0], row[1].id))]


def city_entry(name: str | None) -> GazetteerEntry | None:
    """A city or arrondissement by folded name or alias (``"Strasbourg"``, ``"Paris 12e"``)."""

    alias = fold_name(name)
    if not alias:
        return None
    for names, entry in _aliases():
        if entry.kind in _CITY_KINDS and " ".join(names) == alias:
            return entry
    return None


def _named_cities(texts: list[str | None]) -> list[GazetteerEntry]:
    cities: dict[str, GazetteerEntry] = {}
    for text in texts:
        for _, entry in _find(text):
            if entry.kind in _CITY_KINDS:
                cities[entry.id] = entry
    return list(cities.values())


# ---------------------------------------------------------------------------
# Resolution (§3.2) and the meaning check (§3.4)
# ---------------------------------------------------------------------------


def _accept_proposal(proposed: Geo, city: GazetteerEntry | None) -> bool:
    if in_france(proposed.lat, proposed.lon) is None:
        return False
    if city is None:
        return True
    return haversine_km(proposed.lat, proposed.lon, city.lat, city.lon) <= MAX_CITY_DISTANCE_KM


def _resolve(place: Place, proposed: Geo | None, city_hint: str | None) -> Geo | None:
    matches = place_matches(place)
    # 1. The gazetteer: a precise entry wins outright.
    if matches and matches[0].precision == "exact":
        return matches[0].geo()
    city = city_entry(city_hint) or next((entry for entry in matches if entry.kind in _CITY_KINDS), None)
    # 2. The builder's proposal, inside France and near the named city.
    if proposed is not None and _accept_proposal(proposed, city):
        return proposed.model_copy()
    # 3. The city centroid (or a region found alone).
    if city is not None:
        return city.geo("city")
    region = next((entry for entry in matches if entry.precision == "region"), None)
    if region is not None:
        return region.geo("region")
    # 4. Nothing.
    return None


def resolve_place(
    place: Place, *, proposed: Geo | None = None, city_hint: str | None = None
) -> Geo | None:
    """The place's coordinates by the four steps of §3.2 (``place.geo`` itself is ignored)."""

    geo = _resolve(place, proposed, city_hint)
    if geo is None:
        logger.bind(place_id=place.id, name_fr=place.name_fr).info(
            "revue_place_without_geo {} {!r}", place.id, place.name_fr
        )
    return geo


def _is_gazetteer_centre(place: Place) -> bool:
    """The place really is the landmark at Paris's centre (the Hôtel de Ville)."""

    lat0, lon0 = PARIS_CENTROID
    return any(
        entry.precision == "exact"
        and haversine_km(entry.lat, entry.lon, lat0, lon0) <= PARIS_CENTROID_RADIUS_KM
        for entry in place_matches(place)
    )


def geo_problems(place: Place, geo: Geo | None = None) -> list[str]:
    """§3.4 reason codes for ``geo`` (default ``place.geo``); ``[]`` when it holds."""

    geo = geo if geo is not None else place.geo
    if geo is None:
        return []
    problems: list[str] = []
    if in_france(geo.lat, geo.lon) is None:
        problems.append("outside_france")
    lat0, lon0 = PARIS_CENTROID
    if (
        geo.precision == "exact"
        and haversine_km(geo.lat, geo.lon, lat0, lon0) <= PARIS_CENTROID_RADIUS_KM
        and not _is_gazetteer_centre(place)
    ):
        problems.append("paris_centroid_claimed_exact")
    cities = _named_cities([place.name_fr, place.brief, geo.label_fr])
    if cities and min(haversine_km(geo.lat, geo.lon, c.lat, c.lon) for c in cities) > MAX_CITY_DISTANCE_KM:
        problems.append("city_mismatch")
    return problems


def geocode_dossier(dossier: EditorialDossier, *, city_hint: str | None = None) -> EditorialDossier:
    """A copy with every place's geo resolved and checked.

    An existing ``place.geo`` is the builder's proposal (step 2). A geo the check
    refuses is downgraded to ``city`` when its only fault is a Paris-centre «exact»,
    otherwise dropped and resolved again without the proposal.
    """

    copy = dossier.model_copy(deep=True)
    for place in copy.places:
        geo = _resolve(place, place.geo, city_hint)
        problems = geo_problems(place, geo) if geo is not None else []
        if problems == ["paris_centroid_claimed_exact"] and geo is not None:
            geo = geo.model_copy(update={"precision": "city"})
        elif problems:
            geo = _resolve(place, None, city_hint)
            if geo is not None and geo_problems(place, geo):
                geo = None
        if geo is None:
            logger.bind(place_id=place.id, dossier_id=dossier.id).info(
                "revue_place_without_geo {} {}", dossier.id, place.id
            )
        place.geo = geo
    return copy
