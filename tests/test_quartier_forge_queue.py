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
from types import SimpleNamespace

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
    assert forge.stage_of("toit")["room"] == "toit_mistral"
    assert forge.stage_of("mistral_back_room")["room"] == "arriere_salle"
    assert forge.stage_of("marin_lila_flat")["room"] == "chez_marin_lila"
    assert forge.stage_of("marchand_office")["room"] == "gerance_marchand"
    # the mairie has a world entry but nothing built yet; the rue de Lancry has neither
    assert forge.stage_of("mairie") is None
    assert forge.stage_of("rue_de_lancry") is None


def test_the_queue_puts_the_next_unbuilt_place_after_the_frontier_first():
    forge = _forge()
    from_start = [r for r in forge.season_queue() if r["status"] != "built"]
    assert from_start[0]["location"] == "mairie"  # T3 is the first page set somewhere unbuilt
    # gap 3's roof, T5's back room, Marin and Lila's flat and T6's gérance are built: from g3 the
    # next place is the gare de l'Est
    for built in ("toit", "mistral_back_room", "marin_lila_flat", "marchand_office"):
        assert next(r for r in forge.season_queue("g3") if r["location"] == built)["status"] == "built"
    from_g3 = [r for r in forge.season_queue("g3") if r["status"] != "built"]
    assert from_g3[0]["location"] == "gare_de_lest"
    ahead = [r["location"] for r in from_g3 if r["ahead"]]
    assert ahead[:3] == ["gare_de_lest", "rue_de_lancry", "gus_loft"]
    # places only needed before the frontier still come, after the ones ahead
    behind = [r["location"] for r in from_g3 if not r["ahead"]]
    assert "ngo_office" in behind and "mairie" in behind
    assert all(r["ahead"] for r in from_g3[: len(ahead)])


def test_a_place_built_for_the_season_leaves_the_queue():
    forge = _forge()
    places = forge.world()["places"] + [
        {"id": "lancry", "kind": "season", "stages": ["rue_de_lancry"], "site": "lancry"}
    ]
    assert forge.stage_of("rue_de_lancry") is None
    assert forge.stage_of("rue_de_lancry", places)["site"] == "lancry"


def test_a_place_no_kit_can_build_yet_waits_and_the_queue_names_the_next(tmp_path, monkeypatch):
    forge = _forge()
    monkeypatch.setattr(forge, "BRIEFS", str(tmp_path))
    (tmp_path / "gare_de_lest.md").write_text(
        "Waits for a kit: a station's platform needs a glass roof and a train the kit lacks.\n", encoding="utf-8"
    )
    rows = forge.season_queue("g3")
    assert next(r for r in rows if r["location"] == "gare_de_lest")["status"] == "no kit"
    todo = [r for r in rows if r["status"] in ("new", "locked")]
    assert todo[0]["location"] == "rue_de_lancry"


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
    # one learner on gap 3, one still on T1: the mairie (T3) is nearer the second than T8's gare
    # is to the first
    both = [r for r in forge.season_queue(["t1", "g3"]) if r["status"] != "built"]
    assert both[0]["location"] == "mairie"
    assert [r["location"] for r in both].index("gare_de_lest") < [r["location"] for r in both].index("brocante")
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


# ---------------------------------------------------------------------------------------------
# «Die Geschichte bestellt, die Schmiede baut»: the story's orders
# ---------------------------------------------------------------------------------------------


def _orders(tmp_path, *orders) -> str:
    path = tmp_path / "world-orders.json"
    path.write_text(json.dumps({"season": "s1", "orders": list(orders)}), encoding="utf-8")
    return str(path)


PETITION = {"kind": "thing", "name_fr": "la pétition de Gus", "location_id": "le_mistral", "look": "Taped inside the window.", "times": 3, "lives": 2}


def test_the_forge_reads_what_the_stories_left_and_builds_the_next_thing(tmp_path, monkeypatch, capsys):
    forge = _forge()
    source = _orders(
        tmp_path,
        {"kind": "thing", "name_fr": "une échelle", "location_id": "gare_de_lest", "look": "", "times": 4, "lives": 3},
        {"kind": "thing", "name_fr": "un carnet", "location_id": "le_mistral", "look": "", "times": 1, "lives": 1},
        PETITION,
        {"kind": "place", "name_fr": "la librairie de la rue Bichat", "location_id": None, "look": "", "times": 2, "lives": 2},
        {"kind": "place", "name_fr": "la boulangerie de Mme Diallo", "location_id": None, "look": "", "times": 2, "lives": 2},
        {"kind": "place", "name_fr": "la mairie", "location_id": "mairie", "look": "", "times": 1, "lives": 1},
        {"kind": "place", "name_fr": "Le Mistral", "location_id": None, "look": "", "times": 9, "lives": 4},
        {"kind": "person", "name_fr": "Gus"},
        "garbage",
    )
    rows = forge.orders_queue(forge.story_orders(source))
    status = {r["name_fr"]: r["status"] for r in rows}
    # a thing where the world is built is a detail of that place, the most asked for first
    things = [r for r in rows if r["kind"] == "thing"]
    assert [r["name_fr"] for r in things[:2]] == ["la pétition de Gus", "un carnet"]
    assert things[0]["stage"] == "quai_de_valmy"
    # a thing in the gare waits for the gare; a place the story named is new to the world
    assert status["une échelle"] == "waits"
    assert status["la librairie de la rue Bichat"] == "new"
    # a place of the season the season queue builds (by its id, or by its name), and one the world has
    assert status["la mairie"] == "season"
    assert status["la boulangerie de Mme Diallo"] == "season"
    assert status["Le Mistral"] == "built"
    assert "Gus" not in status

    forge.cmd_orders_queue(SimpleNamespace(frontier=source))
    out = capsys.readouterr().out
    assert "next detail: «la pétition de Gus» in quai_de_valmy (mark: le_mistral)" in out
    assert "next place: «la librairie de la rue Bichat» (id librairie_rue_bichat), named by 2 lives" in out

    # a detail written for the mark: the order is built, and the next thing comes up
    details = tmp_path / "details"
    details.mkdir()
    (details / "petition_gus.json").write_text(
        json.dumps({"id": "petition_gus", "kind": "detail", "in": "quai_de_valmy", "mark": {"name_fr": "La pétition de Gus", "location_id": "le_mistral"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(forge, "DETAILS", str(details))
    rows = forge.orders_queue(forge.story_orders(source))
    assert next(r for r in rows if r["name_fr"] == "la pétition de Gus")["status"] == "built"
    assert next(r for r in rows if r["kind"] == "thing")["name_fr"] == "un carnet"


def test_an_unreadable_server_leaves_the_forge_without_orders(monkeypatch, capsys):
    forge = _forge()
    monkeypatch.setattr(forge, "API", "http://127.0.0.1:9")
    assert forge.story_orders() == []
    assert "orders are unreadable" in capsys.readouterr().err


def test_a_place_of_the_season_the_stories_named_is_built_first(tmp_path):
    """«Erst erwähnen, dann betreten»: a page names the mairie, the forge builds it next, and
    pages go there once it is."""
    forge = _forge()
    source = _orders(tmp_path, {"kind": "place", "name_fr": "La mairie du 10e", "location_id": None, "look": "", "times": 1, "lives": 3})
    asked = forge.asked_places(forge.orders_queue(forge.story_orders(source)))
    assert asked == {"mairie": 3}
    todo = [r for r in forge.season_queue("g3", asked=asked) if r["status"] in ("new", "locked")]
    assert todo[0]["location"] == "mairie" and todo[0]["asked"] == 3
    # without the stories' word, the roof the learner reaches first comes first
    assert [r for r in forge.season_queue("g3") if r["status"] in ("new", "locked")][0]["location"] != "mairie"


def test_a_place_of_the_season_no_authored_page_is_set_in_is_built_once_named(tmp_path):
    """The bakery is a place of the season no authored page goes to: once a story names it, the
    season queue has it, first, so the night can set a page there after the forge built it."""
    forge = _forge()
    assert "boulangerie" not in {n["location"] for n in forge.season_needs()}
    assert "boulangerie" not in {r["location"] for r in forge.season_queue("g3")}
    source = _orders(tmp_path, {"kind": "place", "name_fr": "la boulangerie de Mme Diallo", "location_id": None, "look": "", "times": 2, "lives": 2})
    asked = forge.asked_places(forge.orders_queue(forge.story_orders(source)))
    assert asked == {"boulangerie": 2}
    todo = [r for r in forge.season_queue("g3", asked=asked) if r["status"] in ("new", "locked")]
    assert todo[0]["location"] == "boulangerie" and todo[0]["asked"] == 2 and todo[0]["named_only"]
    assert todo[0]["need"]["page"] == "named"


def test_a_place_the_stories_named_and_the_forge_built_reaches_the_server(tmp_path, monkeypatch):
    forge = _forge()
    assert forge.place_id_for("la librairie de la rue Bichat") == "librairie_rue_bichat"
    assert forge.place_id_for("Chez Mme Hébert") == "mme_hebert"
    places = json.loads(Path(forge.WORLD).read_text(encoding="utf-8"))["places"]
    shop = {
        "id": "librairie_rue_bichat",
        "name": {"fr": "La librairie de la rue Bichat", "en": "The bookshop on rue Bichat", "de": "Die Buchhandlung in der Rue Bichat"},
        "lat": 48.8716, "lon": 2.3644, "status": "locked", "kind": "story", "in": "quai_de_valmy",
        "why": {"fr": "Les histoires l'ont nommée.", "en": "The stories named it.", "de": "Die Geschichten haben sie genannt."},
        "room": "librairie_rue_bichat", "stages": ["librairie_rue_bichat"],
        "story": {"description": "A narrow bookshop with a green front and a cat in the window.", "named_by": 2},
    }
    data = forge.stages_file([*places, shop])
    assert data["stages"]["librairie_rue_bichat"] == "librairie_rue_bichat"
    assert data["places"] == {
        "librairie_rue_bichat": {
            "name_fr": "La librairie de la rue Bichat",
            "name": "The bookshop on rue Bichat",
            "type": "story",
            "description": "A narrow bookshop with a green front and a cat in the window.",
        }
    }
    # not built yet: neither a stage nor a place the night may go to
    unbuilt = {**shop, "room": None}
    assert "places" not in forge.stages_file([*places, unbuilt])
    # the forge's check knows it as a place a page may be set in
    monkeypatch.setattr(forge, "world", lambda: {"places": [*places, shop]})
    assert forge.register_problems(shop) == []

    # the server reads the same file as the forge writes it
    from app.services.season import world as season_world

    (tmp_path / "s1").mkdir()
    (tmp_path / "s1" / "stages.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(season_world, "SEASON_ROOT", tmp_path)
    season_world.story_places.cache_clear()
    try:
        assert season_world.story_places("s1")["librairie_rue_bichat"]["name_fr"] == "La librairie de la rue Bichat"
    finally:
        season_world.story_places.cache_clear()


def test_what_a_learner_named_in_their_own_words_is_built_first(tmp_path, capsys):
    """«Deine eigenen Worte bestellen beim Bau»: a thing a learner named themselves goes
    before one more pages left, and a place they named counts twice in the season queue."""
    forge = _forge()
    flowers = {"kind": "thing", "name_fr": "des fleurs", "location_id": "le_mistral", "look": "", "times": 1, "lives": 1, "said": 1}
    rows = forge.orders_queue(forge.story_orders(_orders(tmp_path, PETITION, flowers)))
    things = [r["name_fr"] for r in rows if r["kind"] == "thing" and r["status"] == "new"]
    assert things[:2] == ["des fleurs", "la pétition de Gus"]
    bakery = {"kind": "place", "name_fr": "la boulangerie de Mme Diallo", "location_id": None, "look": "", "times": 1, "lives": 1, "said": 1}
    assert forge.asked_places(forge.orders_queue(forge.story_orders(_orders(tmp_path, bakery)))) == {"boulangerie": 2}

    class Args:
        frontier = _orders(tmp_path, PETITION, flowers)

    forge.cmd_orders_queue(Args)
    out = capsys.readouterr().out
    assert "1 lives, said by 1" in out and "next detail: «des fleurs»" in out
