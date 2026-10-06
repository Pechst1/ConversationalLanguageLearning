"""WP-120 phase A — Geo: the gazetteer, the four-step resolution and the Geo check.

No DB, no network. See docs/implementation/atelier-v2/WP-120-LA-CARTE.md §3.
"""

from __future__ import annotations

import json

import pytest
from loguru import logger

from app.services.revue.checks import CHECK_NAMES, check_geo, failures
from app.services.revue.dossier import EditorialDossier, Geo, Place
from app.services.revue.evergreen import load_evergreens
from app.services.revue.geo import (
    FRANCE_BBOXES,
    GAZETTEER_PATH,
    PARIS_CENTROID,
    fold_name,
    gazetteer_entry,
    geocode_dossier,
    haversine_km,
    in_france,
    load_gazetteer,
    resolve_place,
)
from app.services.season.world import SEASON_ONE_LOCATIONS

PARIS_BOX = (48.815, 48.903, 2.224, 2.470)


def _dossier(*places: Place) -> EditorialDossier:
    dossier = load_evergreens()[0]
    dossier.places = list(places)
    return EditorialDossier.model_validate(dossier.model_dump())


@pytest.fixture
def without_geo_logs() -> list[str]:
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="INFO")
    yield messages
    logger.remove(sink)


# -- the gazetteer ----------------------------------------------------------------


def test_gazetteer_loads_with_unique_ids_inside_france() -> None:
    entries = load_gazetteer()
    assert len(entries) >= 150
    ids = [entry.id for entry in entries]
    assert len(ids) == len(set(ids))
    for entry in entries:
        assert in_france(entry.lat, entry.lon), entry.id
        assert entry.precision in {"exact", "city", "region"}, entry.id
        assert entry.kind in {
            "landmark", "arrondissement", "city", "region", "institution", "venue", "market"
        }, entry.id
        assert entry.names and all(name == fold_name(name) for name in entry.names), entry.id
        assert entry.parent is None or gazetteer_entry(entry.parent) is not None, entry.id
    kinds = [entry.kind for entry in entries]
    assert kinds.count("arrondissement") == 20
    assert kinds.count("city") >= 101
    # 13 metropolitan regions + 5 overseas departments + the 10 wine regions.
    assert kinds.count("region") >= 28


def test_gazetteer_aliases_are_unambiguous() -> None:
    rows = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
    names = [name for row in rows for name in row["names"]]
    assert len(names) == len(set(names))


def test_france_boxes_cover_overseas_and_refuse_neighbours() -> None:
    assert set(FRANCE_BBOXES) >= {"metropolitan", "corse", "guadeloupe", "martinique", "guyane", "reunion", "mayotte"}
    assert in_france(48.8566, 2.3522) == "metropolitan"
    assert in_france(42.6977, 9.4508) == "corse"
    assert in_france(-20.8823, 55.4504) == "reunion"
    assert in_france(4.9224, -52.3135) == "guyane"
    assert in_france(41.3874, 2.1686) is None  # Barcelone
    assert in_france(51.5072, -0.1276) is None  # Londres
    assert haversine_km(48.8566, 2.3522, 45.7640, 4.8357) == pytest.approx(392, abs=5)


# -- resolution (§3.2) ----------------------------------------------------------


def test_step_one_resolves_by_alias() -> None:
    geo = resolve_place(Place(id="p1", name_fr="Le marché d'Aligre, un matin"))
    assert geo is not None and geo.precision == "exact"
    assert "Aligre" in geo.label_fr and "Beauvau" in geo.label_fr
    by_id = resolve_place(Place(id="marche_aligre", name_fr="Un marché"))
    by_beauvau = resolve_place(Place(id="p2", name_fr="Sous la halle du marché Beauvau"))
    assert by_id == geo == by_beauvau


def test_step_one_prefers_the_landmark_over_its_city() -> None:
    place = Place(id="p", name_fr="Le marché de Noël, place Broglie à Strasbourg")
    geo = resolve_place(place)
    assert geo is not None and geo.precision == "exact" and "Broglie" in geo.label_fr


def test_lowercase_common_words_are_not_cities() -> None:
    place = Place(id="p", name_fr="Une rue avec les tours", brief="a nice street with tours")
    assert resolve_place(place) is None


def test_proposal_far_from_the_named_city_is_rejected() -> None:
    place = Place(id="p", name_fr="Une rue de Lyon")
    far = Geo(lat=45.7640 + 0.36, lon=4.8357, precision="exact", label_fr="Ailleurs")  # ~40 km north
    geo = resolve_place(place, proposed=far)
    assert geo is not None and geo.precision == "city" and geo.label_fr == "Lyon"
    near = Geo(lat=45.7578, lon=4.8320, precision="exact", label_fr="Place Bellecour, Lyon")
    assert resolve_place(place, proposed=near) == near


def test_proposal_outside_france_is_rejected() -> None:
    place = Place(id="p", name_fr="Une plage")
    barcelone = Geo(lat=41.3874, lon=2.1686, precision="exact", label_fr="Barcelone")
    assert resolve_place(place, proposed=barcelone) is None
    calanques = Geo(lat=43.2100, lon=5.4500, precision="exact", label_fr="Calanques")
    assert resolve_place(place, proposed=calanques) == calanques


def test_step_three_city_centroid_from_hint_or_brief() -> None:
    bakery = Place(id="p", name_fr="Une boulangerie", brief="a bakery window in January")
    geo = resolve_place(bakery, city_hint="Toulouse")
    assert geo is not None and geo.precision == "city" and geo.label_fr == "Toulouse"
    briefed = Place(id="p", name_fr="Une petite place", brief="a small square in Nantes at dusk")
    geo = resolve_place(briefed)
    assert geo is not None and geo.precision == "city" and geo.label_fr == "Nantes"
    arrondissement = Place(id="p", name_fr="Une rue du 12e arrondissement")
    geo = resolve_place(arrondissement)
    assert geo is not None and geo.precision == "city" and geo.label_fr == "Paris 12e"


def test_a_wine_region_alone_gives_region_precision() -> None:
    geo = resolve_place(Place(id="p", name_fr="Les vignes du Beaujolais en novembre"))
    assert geo is not None and geo.precision == "region"


def test_nothing_matches_gives_none_and_logs(without_geo_logs: list[str]) -> None:
    place = Place(id="salle_examen", name_fr="Une salle d'examen dans un lycée en juin")
    assert resolve_place(place) is None
    assert any("revue_place_without_geo" in message for message in without_geo_logs)


# -- the Geo check (§3.4) -------------------------------------------------------


def test_geo_is_a_check_name() -> None:
    assert "geo" in CHECK_NAMES


def test_paris_centroid_claimed_exact_is_downgraded() -> None:
    lat, lon = PARIS_CENTROID
    lie = Geo(lat=lat, lon=lon, precision="exact", label_fr="Une librairie, Paris")
    place = Place(id="librairie", name_fr="Une librairie à Paris", geo=lie)
    dossier = _dossier(place)
    failed = failures(check_geo(dossier))
    assert [row.reason for row in failed] == ["paris_centroid_claimed_exact"]
    assert failed[0].detail["advice"] == "city"
    geocoded = geocode_dossier(dossier).places[0].geo
    assert geocoded is not None and geocoded.precision == "city"
    assert dossier.places[0].geo == lie  # a copy, not the stored dossier


def test_the_hotel_de_ville_itself_may_be_exact() -> None:
    lat, lon = PARIS_CENTROID
    geo = Geo(lat=lat, lon=lon, precision="exact", label_fr="Hôtel de Ville de Paris")
    place = Place(id="hdv", name_fr="Le parvis de l'Hôtel de Ville", geo=geo)
    assert failures(check_geo(_dossier(place))) == []


def test_outside_france_and_city_mismatch_fail() -> None:
    abroad = Place(
        id="abroad", name_fr="Une rue", geo=Geo(lat=41.3874, lon=2.1686, precision="exact", label_fr="Barcelone")
    )
    mismatch = Place(
        id="lyon",
        name_fr="Un café à Lyon",
        geo=Geo(lat=43.2965, lon=5.3698, precision="exact", label_fr="Un café"),
    )
    reasons = {row.detail["place_id"]: row.reason for row in failures(check_geo(_dossier(abroad, mismatch)))}
    assert reasons == {"abroad": "outside_france", "lyon": "city_mismatch"}
    geocoded = {place.id: place.geo for place in geocode_dossier(_dossier(abroad, mismatch)).places}
    assert geocoded["abroad"] is None
    assert geocoded["lyon"] is not None and geocoded["lyon"].label_fr == "Lyon"


def test_missing_geo_is_informational() -> None:
    results = check_geo(_dossier(Place(id="p", name_fr="Une rue")))
    assert [(row.ok, row.reason) for row in results] == [(True, "missing_geo")]


# -- the season's places (§3.3) ---------------------------------------------------


def test_season_one_locations_all_have_geo_inside_paris() -> None:
    lat_min, lat_max, lon_min, lon_max = PARIS_BOX
    for location_id, row in SEASON_ONE_LOCATIONS.items():
        assert {"name_fr", "plate", "own"} <= set(row), location_id
        geo = Geo.model_validate(row["geo"])
        assert in_france(geo.lat, geo.lon) == "metropolitan", location_id
        assert lat_min <= geo.lat <= lat_max and lon_min <= geo.lon <= lon_max, location_id
        assert geo.precision in {"exact", "city"}, location_id
        assert not failures(check_geo(_dossier(Place(id=location_id, name_fr=str(row["name_fr"]), geo=geo))))
