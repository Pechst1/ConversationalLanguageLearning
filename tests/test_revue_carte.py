"""WP-120 phase C: La Carte (``revue/carte.py``, ``GET /revue/carte``, the build script).

* ``pins_for`` turns the learner's **closed** Papiers into pins (place, geo, headline,
  kept words, the learner's part, plate, vignette when minted); open and abandoned
  sessions never pin; a place without coordinates counts as ``unplaced``.
* «Mon quartier» lists only the season places of days the learner has lived.
* The route hides behind the Revue flag like every Revue route.
* The drawings: the build script's Lambert-93 lands known places inside the right
  department / arrondissement path of the shipped SVGs, and the projection file's check
  points agree with the script (± 2 svg units).
"""

from __future__ import annotations

import importlib.util
import json
import re
import uuid
from collections.abc import Generator, Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.revue_session import RevueSession
from app.db.models.revue_vignette import RevuePictogram, RevueVignette
from app.db.models.user import User
from app.main import create_app
from app.services.revue import carte
from app.services.revue.carte import level_of, pins_for, visited_season_places

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "web-frontend" / "public" / "assets" / "carte"
PASSWORD = "securepass123"
TABLES = (RevueSession.__table__, RevuePictogram.__table__, RevueVignette.__table__)

ALIGRE = {"lat": 48.849, "lon": 2.378, "precision": "exact", "label_fr": "Place d'Aligre et marché Beauvau, Paris 12e"}
LONGCHAMP = {"lat": 48.8573, "lon": 2.2338, "precision": "exact", "label_fr": "Hippodrome de ParisLongchamp"}
BOURGOGNE = {"lat": 47.05, "lon": 4.83, "precision": "region", "label_fr": "Vignoble de Bourgogne"}
VERSAILLES = {"lat": 48.8049, "lon": 2.1204, "precision": "city", "label_fr": "Versailles"}


@pytest.fixture(scope="module")
def carte_tables(db_engine) -> Generator[None, None, None]:
    created = [table for table in TABLES if not inspect(db_engine).has_table(table.name)]
    for table in created:
        table.create(bind=db_engine, checkfirst=True)
    try:
        yield
    finally:
        for table in reversed(created):
            table.drop(bind=db_engine, checkfirst=True)


@pytest.fixture()
def db(db_session: Session, carte_tables) -> Session:
    return db_session


def make_user(db: Session) -> User:
    user = User(id=uuid.uuid4(), email=f"carte-{uuid.uuid4().hex[:10]}@example.com", hashed_password="x")
    db.add(user)
    db.commit()
    return user


def event(seq: int, event_kind: str, **payload) -> dict:
    return {"seq": seq, "at": datetime(2026, 10, 1, 9, tzinfo=UTC).isoformat(), "kind": event_kind, "payload": payload}


def papier(
    db: Session,
    user: User,
    *,
    geo: dict | None,
    status: str = "closed",
    place_id: str = "lieu",
    name_fr: str = "Le lieu",
    title: str = "Le titre du dossier",
    headline: str | None = "Un titre filé",
    artifact: dict | None = None,
    words: list[dict] | None = None,
    week: str = "2026-W40",
    plate: str | None = "/assets/serial/locations/marche_canal.webp",
) -> RevueSession:
    place = {"id": place_id, "name_fr": name_fr, "brief": "", "known": False}
    if geo is not None:
        place["geo"] = geo
    snapshot = {"id": f"d-{uuid.uuid4().hex[:8]}", "topic": "food", "title_fr": title,
                "places": [{"id": "autre", "name_fr": "Ailleurs", "brief": "", "known": False}, place]}
    events = [event(1, "choice", kind="dossier", dossier_id=snapshot["id"], snapshot=snapshot)]
    if artifact is not None:
        events.append(event(2, "artifact", **artifact))
    if status == "closed" and headline is not None:
        events.append(event(3, "closed", closing={
            "romy_line_fr": "C'est noté.",
            "dispatch": {"headline_fr": headline, "contribution": [], "body_fr": [], "kicker_fr": "", "byline_fr": "", "sources": []},
            "kept": {"words": words or [], "claims": []},
            "question_kept_fr": "Est-ce que les prix baissent ?",
        }))
    row = RevueSession(
        user_id=user.id, week=week, dossier_id=snapshot["id"],
        plan={"stage": {"place_id": place_id, "plate_url": plate}},
        state={"state_version": "revue-state-v1", "events": events},
        status=status,
        closed_at=datetime(2026, 10, 1, 10, tzinfo=UTC) if status == "closed" else None,
    )
    db.add(row)
    db.commit()
    return row


def lived_day(db: Session, user: User, location_ids: list[str], *, status: str = "completed", day: int = 1) -> None:
    journey = DailyJourney(user_id=user.id, local_date=date(2026, 9, day), status=status)
    db.add(journey)
    db.flush()
    brief = {"location_id": location_ids[0], "panels": [{"location_id": lid} for lid in location_ids[1:]]}
    db.add(DailyJourneyStep(journey_id=journey.id, ordinal=1, kind="scene", private_task={"scenario_brief": brief}))
    db.commit()


# ---------------------------------------------------------------------------
# pins_for
# ---------------------------------------------------------------------------


def test_pins_come_from_closed_papiers_only(db: Session) -> None:
    user = make_user(db)
    closed = papier(db, user, geo=ALIGRE, place_id="marche_aligre", headline="Les prix montent au marché",
                    artifact={"kind": "reader_question", "text_fr": "Est-ce que les prix baissent ?", "contribution": [[11, 30]]},
                    words=[{"fr": "un étal", "gloss": "", "claim_id": "c1", "used": False},
                           {"fr": "le prix", "gloss": "", "claim_id": "c1", "used": True}])
    papier(db, user, geo=LONGCHAMP, status="active")
    papier(db, user, geo=BOURGOGNE, status="abandoned")
    other = make_user(db)
    papier(db, other, geo=ALIGRE)

    view = pins_for(db, user)
    assert [pin.session_id for pin in view.pins] == [str(closed.id)]
    [pin] = view.pins
    assert (pin.lat, pin.lon, pin.precision, pin.level) == (48.849, 2.378, "exact", "paris")
    assert pin.place_label_fr == "Place d'Aligre et marché Beauvau, Paris 12e"
    assert pin.headline_fr == "Les prix montent au marché"
    # The words the learner used come first.
    assert pin.kept_words == ["le prix", "un étal"]
    assert pin.contribution_kind == "reader_question"
    assert pin.contribution_fr == "Est-ce que les prix baissent ?"
    assert pin.contribution_spans == [(11, 30)]
    assert pin.question_fr == "Est-ce que les prix baissent ?"
    assert pin.plate_url == "/assets/serial/locations/marche_canal.webp"
    assert pin.vignette is None
    assert view.counts.model_dump() == {"france": 1, "idf": 1, "paris": 1, "unplaced": 0}


def test_six_papiers_give_six_pins_and_the_counts_per_level(db: Session) -> None:
    user = make_user(db)
    for geo in (ALIGRE, ALIGRE, LONGCHAMP, BOURGOGNE, VERSAILLES):
        papier(db, user, geo=geo)
    papier(db, user, geo=None, place_id="cuisine", name_fr="Une cuisine quelque part")
    view = carte.build_carte(db, user.id)
    assert len(view.pins) == 5
    assert view.counts.model_dump() == {"france": 5, "idf": 4, "paris": 3, "unplaced": 1}
    assert {pin.level for pin in view.pins} == {"paris", "idf", "france"}
    bourgogne = next(pin for pin in view.pins if pin.precision == "region")
    assert bourgogne.level == "france"


def test_a_snapshot_without_geo_asks_the_gazetteer(db: Session) -> None:
    user = make_user(db)
    papier(db, user, geo=None, place_id="hippodrome_longchamp", name_fr="L'hippodrome de Longchamp")
    [pin] = carte.build_carte(db, user.id).pins
    assert pin.level == "paris" and pin.precision == "exact"
    assert abs(pin.lat - 48.8573) < 1e-6 and abs(pin.lon - 2.2338) < 1e-6


def test_the_headline_falls_back_to_the_dossier_title(db: Session) -> None:
    user = make_user(db)
    papier(db, user, geo=BOURGOGNE, headline=None, title="Le beaujolais nouveau arrive")
    [pin] = carte.build_carte(db, user.id).pins
    assert pin.headline_fr == "Le beaujolais nouveau arrive"
    assert pin.kept_words == [] and pin.contribution_fr is None


def test_a_minted_vignette_rides_on_its_pin(db: Session) -> None:
    user = make_user(db)
    row = papier(db, user, geo=ALIGRE)
    svg = '<svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="20" fill="#d8321a"/></svg>'
    db.add(RevuePictogram(dossier_id=row.dossier_id, object_fr="une pomme", svg=svg, prompt_version="test"))
    db.add(RevueVignette(user_id=user.id, session_id=row.id, dossier_id=row.dossier_id, ring="question",
                         kept_contribution=True, week=row.week, place_label_fr="Place d'Aligre"))
    db.commit()
    [pin] = carte.build_carte(db, user.id).pins
    assert pin.vignette is not None
    assert pin.vignette.model_dump() == {"ring": "question", "kept_contribution": True, "pictogram_svg": svg}


def test_pins_for_is_cached_for_a_minute(db: Session, monkeypatch) -> None:
    user = make_user(db)
    papier(db, user, geo=ALIGRE)
    assert len(pins_for(db, user).pins) == 1
    papier(db, user, geo=LONGCHAMP)
    assert len(pins_for(db, user).pins) == 1  # served from the cache
    carte.invalidate(user.id)
    assert len(pins_for(db, user).pins) == 2


def test_level_of_nests_paris_in_the_idf_in_france() -> None:
    assert level_of(48.8566, 2.3522) == "paris"
    assert level_of(48.8049, 2.1204) == "idf"
    assert level_of(45.764, 4.8357) == "france"
    assert level_of(-20.88, 55.45) == "france"


# ---------------------------------------------------------------------------
# «Mon quartier»
# ---------------------------------------------------------------------------


def test_quartier_lists_only_places_already_lived(db: Session) -> None:
    user = make_user(db)
    lived_day(db, user, ["le_mistral", "quai_de_valmy"], day=1)
    lived_day(db, user, ["buttes_chaumont"], day=2, status="ended_early")
    lived_day(db, user, ["gare_de_lest"], day=3, status="active")  # today, not lived yet
    lived_day(db, user, ["not_a_season_place"], day=4)
    other = make_user(db)
    lived_day(db, other, ["brocante"], day=1)

    assert visited_season_places(db, user.id) == ["le_mistral", "quai_de_valmy", "buttes_chaumont", "not_a_season_place"]
    quartier = carte.build_carte(db, user.id).quartier
    assert [place.id for place in quartier] == ["le_mistral", "quai_de_valmy", "buttes_chaumont"]
    mistral = quartier[0]
    assert mistral.name_fr == "Le Mistral"
    assert mistral.plate_url == "/assets/serial/locations/le_mistral-counter.webp"
    assert level_of(mistral.lat, mistral.lon) == "paris"


def test_quartier_is_empty_for_a_learner_who_has_not_started(db: Session) -> None:
    user = make_user(db)
    assert carte.build_carte(db, user.id).quartier == []


# ---------------------------------------------------------------------------
# The route
# ---------------------------------------------------------------------------


@pytest.fixture()
def api(db_session: Session, carte_tables) -> Generator[TestClient, None, None]:
    app = create_app()

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client


def login(client: TestClient) -> tuple[dict[str, str], str]:
    email = f"carte-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": PASSWORD, "target_language": "fr", "native_language": "de"})
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def test_route_is_404_while_the_flag_is_off(api: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", False)
    assert api.get("/api/v1/revue/carte").status_code == 404
    headers, _ = login(api)
    assert api.get("/api/v1/revue/carte", headers=headers).status_code == 404


def test_route_answers_the_learners_map_when_on(api: TestClient, db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "REVUE_ENABLED", True)
    assert api.get("/api/v1/revue/carte").status_code == 401
    headers, email = login(api)
    empty = api.get("/api/v1/revue/carte", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {"pins": [], "quartier": [], "counts": {"france": 0, "idf": 0, "paris": 0, "unplaced": 0}}

    user = db_session.scalar(select(User).where(User.email == email))
    papier(db_session, user, geo=BOURGOGNE)
    carte.invalidate(user.id)
    body = api.get("/api/v1/revue/carte", headers=headers).json()
    [pin] = body["pins"]
    assert set(pin) == {"session_id", "dossier_id", "week", "closed_at", "place_label_fr", "lat", "lon", "precision",
                        "level", "headline_fr", "kept_words", "contribution_kind", "contribution_fr",
                        "contribution_spans", "question_fr", "plate_url", "vignette"}
    assert pin["precision"] == "region" and pin["level"] == "france"
    assert body["counts"] == {"france": 1, "idf": 0, "paris": 0, "unplaced": 0}


# ---------------------------------------------------------------------------
# The drawings and the projection file
# ---------------------------------------------------------------------------


def _build_module():
    spec = importlib.util.spec_from_file_location("build_carte", ROOT / "scripts" / "geo" / "build_carte.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _rings(d: str) -> list[list[tuple[float, float]]]:
    """Parse the build script's own path grammar: ``M x y l dx dy … z`` per ring."""

    rings = []
    for chunk in re.findall(r"M([^z]+)z", d):
        head, _, rel = chunk.partition("l")
        x, y = (float(v) for v in head.split())
        ring = [(x, y)]
        values = [float(v) for v in rel.split()]
        for dx, dy in zip(values[::2], values[1::2], strict=True):
            x, y = x + dx, y + dy
            ring.append((x, y))
        rings.append(ring)
    return rings


def _inside(rings: list[list[tuple[float, float]]], x: float, y: float) -> bool:
    inside = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _path(svg: str, code: str) -> list[list[tuple[float, float]]]:
    match = re.search(rf'data-code="{code}"[^>]* d="([^"]+)"', svg)
    assert match, f"no path for {code}"
    return _rings(match.group(1))


@pytest.fixture(scope="module")
def projection() -> dict:
    return json.loads((ASSETS / "carte-projection.json").read_text(encoding="utf-8"))


def test_lambert93_is_conformal_and_true_to_scale_on_its_standard_parallels() -> None:
    import math

    build = _build_module()
    x, y = build.lambert93(46.5, 3.0)
    assert abs(x - 700000) < 0.01 and abs(y - 6600000) < 0.01
    e2 = build.GRS80_E**2
    for lat in (44.0, 49.0):
        phi = math.radians(lat)
        metres = build.GRS80_A * math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2) * math.radians(0.01)
        (x1, y1), (x2, y2) = build.lambert93(lat, 2.995), build.lambert93(lat, 3.005)
        assert abs(math.hypot(x2 - x1, y2 - y1) / metres - 1) < 1e-6, lat
    # Off the standard parallels the scale is below 1 between them (46.5°N), above outside (51°N).
    for lat, below in ((46.5, True), (51.0, False)):
        phi = math.radians(lat)
        metres = build.GRS80_A * math.cos(phi) / math.sqrt(1 - e2 * math.sin(phi) ** 2) * math.radians(0.01)
        (x1, y1), (x2, y2) = build.lambert93(lat, 2.995), build.lambert93(lat, 3.005)
        assert (math.hypot(x2 - x1, y2 - y1) / metres < 1) is below, lat


def test_known_places_land_inside_their_shapes(projection: dict) -> None:
    build = _build_module()
    cases = [
        ("france", "69", 45.764, 4.8357),   # Lyon, Rhône
        ("france", "29", 48.3904, -4.4861),  # Brest, Finistère
        ("france", "2B", 42.3061, 9.1497),  # Corte, Haute-Corse
        ("france", "974", -20.8821, 55.4504),  # Saint-Denis, inset
        ("idf", "78", 48.8049, 2.1204),  # Versailles, Yvelines
        ("idf", "75", 48.8564, 2.3524),  # Hôtel de Ville
        ("paris", "75112", 48.849, 2.378),  # place d'Aligre, 12e
        ("paris", "75116", 48.8573, 2.2338),  # Longchamp, 16e
        ("paris", "75107", 48.862, 2.3185),  # Assemblée nationale, 7e
    ]
    for drawing, code, lat, lon in cases:
        svg = (ASSETS / f"{drawing}.svg").read_text(encoding="utf-8")
        point = build.project_point(projection["drawings"][drawing], lat, lon)
        assert point is not None, (drawing, code)
        assert _inside(_path(svg, code), *point), (drawing, code, point)


def test_projection_checks_round_trip_within_two_units(projection: dict) -> None:
    build = _build_module()
    assert projection["fallback"] is False
    assert {c["drawing"] for c in projection["checks"]} == {"france", "idf", "paris"}
    for check in projection["checks"]:
        x, y = build.project_point(projection["drawings"][check["drawing"]], check["lat"], check["lon"])
        assert abs(x - check["x"]) <= 2 and abs(y - check["y"]) <= 2, check
    # The backend's level bounds are the drawings' own.
    idf, paris = projection["drawings"]["idf"]["bounds"], projection["drawings"]["paris"]["bounds"]
    assert carte.IDF_BOUNDS == (idf["lat_min"], idf["lat_max"], idf["lon_min"], idf["lon_max"])
    assert carte.PARIS_BOUNDS == (paris["lat_min"], paris["lat_max"], paris["lon_min"], paris["lon_max"])


def test_the_drawings_are_av2_and_small() -> None:
    limits = {"france": 150, "idf": 60, "paris": 60}
    for name, kb in limits.items():
        svg = (ASSETS / f"{name}.svg").read_text(encoding="utf-8")
        assert len(svg.encode("utf-8")) <= kb * 1024, name
        # No colour in the files: classes only, painted by styles/carte.css from the av2 tokens.
        assert not re.search(r'(fill|stroke)="(?!none)', svg), name
        assert "#" not in svg and "<style" not in svg and "<script" not in svg, name
    france = (ASSETS / "france.svg").read_text(encoding="utf-8")
    assert len(re.findall(r'data-code="', france)) == 96 + 5
    assert all(f'data-code="{code}"' in france for code in ("971", "972", "973", "974", "976"))
    paris = (ASSETS / "paris.svg").read_text(encoding="utf-8")
    assert len(re.findall(r'data-code="751', paris)) == 20 and 'class="carte-seine"' in paris
