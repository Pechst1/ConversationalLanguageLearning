"""Le Quartier's forge builds what the season reaches next (scripts/forge/forge.py queue --season).

The story and the 3D world share one register of places: ``stages`` in
``web-frontend/lib/quartier/world/world.json`` says which season locations each built place is
the stage for. The forge's season queue reads the season's own pages in order and lists the
places none of them is built for yet, so the nightly forge builds the next place the story goes
instead of a fixed list.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORGE_DIR = ROOT / "scripts" / "forge"


def _forge():
    spec = importlib.util.spec_from_file_location("quartier_forge", FORGE_DIR / "forge.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(FORGE_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(FORGE_DIR))
    return module


def test_the_season_locations_are_read_from_the_season_world():
    from app.services.season.world import SEASON_ONE_LOCATIONS

    names = _forge().season_locations()
    assert set(names) == set(SEASON_ONE_LOCATIONS)
    assert names["toit"] == SEASON_ONE_LOCATIONS["toit"]["name_fr"]


def test_every_page_location_is_a_season_place():
    forge = _forge()
    known = set(forge.season_locations())
    needs = forge.season_needs()
    assert {n["location"] for n in needs} <= known
    # the roof is where gap 3's bridge page plays
    assert any(n["location"] == "toit" and n["page"] == "g3.bridge" for n in needs)


def test_the_register_names_only_season_places_and_every_built_room_stages_one():
    forge = _forge()
    known = set(forge.season_locations())
    world = json.loads(
        (ROOT / "web-frontend/lib/quartier/world/world.json").read_text(encoding="utf-8")
    )
    for place in world["places"]:
        for loc in (place.get("stages") or []) + (place.get("sees") or []):
            assert loc in known, f"{place['id']}: {loc} is not a season place"
        if place.get("room"):
            assert forge.register_problems(place) == [], place["id"]
    # two built places never claim the same season place
    claimed = [
        loc
        for p in world["places"]
        if forge.is_built(p) and p.get("kind") != "home"
        for loc in p.get("stages") or []
    ]
    assert len(claimed) == len(set(claimed))


def test_a_built_room_is_the_stage_of_its_place_and_the_quarter_of_the_rest():
    forge = _forge()
    assert forge.stage_of("stairwell")["room"] == "escalier_mistral"
    assert forge.stage_of("odile_flat")["room"] == "odile_flat"
    assert forge.stage_of("le_mistral")["id"] == "quai_de_valmy"
    # the mairie has a world entry but nothing built yet
    assert forge.stage_of("mairie") is None
    assert forge.stage_of("toit") is None


def test_the_queue_puts_the_next_unbuilt_place_after_the_frontier_first():
    forge = _forge()
    from_start = [r for r in forge.season_queue() if r["status"] != "built"]
    assert from_start[0]["location"] == "mairie"  # T3 is the first page set somewhere unbuilt
    from_g3 = [r for r in forge.season_queue("g3") if r["status"] != "built"]
    assert from_g3[0]["location"] == "toit"
    ahead = [r["location"] for r in from_g3 if r["ahead"]]
    assert ahead[:3] == ["toit", "mistral_back_room", "marin_lila_flat"]
    # places only needed before the frontier still come, after the ones ahead
    behind = [r["location"] for r in from_g3 if not r["ahead"]]
    assert "ngo_office" in behind and "mairie" in behind
    assert all(r["ahead"] for r in from_g3[: len(ahead)])


def test_a_place_built_for_the_season_leaves_the_queue():
    forge = _forge()
    places = forge.world()["places"] + [
        {"id": "toit", "kind": "season", "stages": ["toit"], "room": "toit", "in": "quai_de_valmy"}
    ]
    assert forge.stage_of("toit", places)["room"] == "toit"


def test_a_place_no_kit_can_build_yet_waits_and_the_queue_names_the_next(tmp_path, monkeypatch):
    forge = _forge()
    monkeypatch.setattr(forge, "BRIEFS", str(tmp_path))
    (tmp_path / "toit.md").write_text(
        "Waits for a kit: zinc roofs need a roof finish the room kit lacks.\n", encoding="utf-8"
    )
    rows = forge.season_queue("g3")
    assert next(r for r in rows if r["location"] == "toit")["status"] == "no kit"
    todo = [r for r in rows if r["status"] in ("new", "locked")]
    assert todo[0]["location"] == "mistral_back_room"


def test_the_server_has_the_worlds_register_as_the_forge_writes_it():
    """``app/data/season/s1/stages.json`` is the forge's register as the server reads it (the
    Docker image has no web-frontend). After any change to world.json: ``forge.py stages``."""
    forge = _forge()
    written = json.loads(Path(forge.STAGES).read_text(encoding="utf-8"))
    assert written == forge.stages_file(), "run `python scripts/forge/forge.py stages`"
    assert forge.stages_problems() == []
    from app.services.season.world import built_stages

    assert built_stages("s1") == forge.built_stages()


def test_the_queue_builds_first_what_the_nearest_learner_reaches_first():
    forge = _forge()
    # one learner on gap 3, one still on T1: the roof is days away for the first, the mairie
    # two weeks away for the second
    both = [r for r in forge.season_queue(["t1", "g3"]) if r["status"] != "built"]
    assert both[0]["location"] == "toit"
    # the mairie is ahead of the learner on T1, so it is not left behind
    assert next(r for r in both if r["location"] == "mairie")["ahead"]
    # a single segment orders the queue as before
    assert [r["location"] for r in forge.season_queue(["g3"])] == [r["location"] for r in forge.season_queue("g3")]


def test_an_unreadable_server_leaves_the_queue_at_the_seasons_start(monkeypatch, capsys):
    forge = _forge()
    monkeypatch.setattr(forge, "API", "http://127.0.0.1:9")
    assert forge.live_frontier() == []
    assert "unreadable" in capsys.readouterr().err


def test_a_learner_on_the_epilogue_is_a_learner_of_the_season():
    """The server counts the epilogue's segments (``e1``…) as the season's; so does the forge,
    with the places its pages are set in."""
    forge = _forge()
    assert [s["id"] for s in forge.season_segments()][-3:] == ["e1", "e2", "e3"]
    assert any(n["segment"] == "e1" and n["location"] == "gus_loft" for n in forge.season_needs())
    rows = [r for r in forge.season_queue(["t2", "e1"]) if r["status"] != "built"]
    # Gus's «château» is that learner's next page; the mairie is a week ahead of the one on T2
    assert rows[0]["location"] == "gus_loft"
    assert next(r for r in rows if r["location"] == "mairie")["ahead"]
