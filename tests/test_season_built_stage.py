"""Step 3 of the 3D overhaul: the story and Le Quartier stay in step.

The 3D world hands each page to the room or street that stages its place; a place it
has not built plays in the Feuilleton only. The night used to write pages anywhere in
the world bible (the gérance, the mairie, the bakery) while the quarter stood still
on the quai. Now:

* the forge writes the server a copy of its register (``app/data/season/s1/stages.json``);
* the night writes a season's generated page only at a built place, or in the room an
  open bottle chapter may not leave; the authored days keep every place;
* the forge reads where the season's learners stand from the server
  (``GET /api/v1/story-engine/season-frontier``) instead of a segment set by hand.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

from app.services.living_story import SEASON_TODAY_KEY, _variety, on_built_stage
from app.services.season import world as season_world
from app.services.season.world import built_stages, playable_locations, season_world_bible

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def _places(*ids: str) -> list[dict]:
    return [{"id": place, "name": place} for place in ids]


def test_the_server_reads_the_places_the_forge_built():
    stages = built_stages("s1")
    # the café and its quai, the stairwell, Odile's flat, the studio, the notary's, the roof, the back room,
    # Marin and Lila's flat, the gérance Marchand
    assert stages["stairwell"] == "escalier_mistral"
    assert stages["le_mistral"] == "quai_de_valmy"
    assert stages["toit"] == "toit_mistral"
    assert stages["mistral_back_room"] == "arriere_salle"
    assert stages["marin_lila_flat"] == "chez_marin_lila"
    assert stages["marchand_office"] == "gerance_marchand"
    assert "gare_de_lest" not in stages and "gus_loft" not in stages
    # every one of them is a place of the season the director reads
    ids = {place["id"] for place in season_world_bible("s1")["setting"]["recurring_locations"]}
    assert set(stages) <= ids
    # a season with no register has no 3D world to keep in step with
    assert built_stages("no_such_season") == {}


def test_a_generated_page_is_offered_the_built_places_and_the_room_it_may_not_leave(monkeypatch):
    monkeypatch.setattr(season_world, "built_stages", lambda season_id="s1": {"le_mistral": "q", "stairwell": "e"})
    places = _places("le_mistral", "stairwell", "toit", "mairie")
    assert [p["id"] for p in playable_locations(places, "s1")] == ["le_mistral", "stairwell"]
    assert [p["id"] for p in playable_locations(places, "s1", keep=["toit", None])] == ["le_mistral", "stairwell", "toit"]
    # fewer than two left: the list stays as it was (a register not written yet)
    monkeypatch.setattr(season_world, "built_stages", lambda season_id="s1": {"le_mistral": "q"})
    assert playable_locations(places, "s1") == places
    monkeypatch.setattr(season_world, "built_stages", lambda season_id="s1": {})
    assert playable_locations(places, "s1") == places


def _context(season_id: str | None = "s1") -> dict:
    world = season_world_bible("s1")
    places = list(world["setting"]["recurring_locations"])
    recent = [{"character_id": "lila_bonnet", "location_id": "mairie"}]
    return {
        **({SEASON_TODAY_KEY: SimpleNamespace(season=SimpleNamespace(id=season_id))} if season_id else {}),
        "world": {"cast": [{"id": "lila_bonnet"}], "locations": places},
        "recent_situations": recent,
        "variety": _variety(recent, [{"id": "lila_bonnet"}], places),
    }


def test_the_night_writes_a_season_page_only_where_the_quarter_can_play_it():
    context = _context()
    on_built_stage(context)
    offered = [place["id"] for place in context["world"]["locations"]]
    assert set(offered) == set(built_stages("s1"))
    # the rotation the director is told to follow names only those places too
    assert context["variety"]["all_locations"] == offered
    assert set(context["variety"]["unused_locations"]) <= set(offered)

    kept = _context()
    on_built_stage(kept, keep=["toit"])
    assert "toit" in [place["id"] for place in kept["world"]["locations"]]


def test_a_life_outside_a_season_keeps_every_place():
    context = _context(season_id=None)
    before = list(context["world"]["locations"])
    on_built_stage(context)
    assert context["world"]["locations"] == before


# ---------------------------------------------------------------------------
# Where the season's learners stand
# ---------------------------------------------------------------------------


def _learner(db, day: int | None):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    user = User(email=f"frontier-{uuid.uuid4()}@example.com", hashed_password="t", timezone="UTC")
    db.add(user)
    db.flush()
    if day is not None:
        jump_to_day(db, user, day=day)
    db.commit()
    return user


def test_the_forge_reads_the_segments_the_learners_are_on(client, db_session, monkeypatch):
    from app.services.season import frontier

    monkeypatch.setattr(frontier, "_cache", {})
    first = client.get("/api/v1/story-engine/season-frontier")
    assert first.status_code == 200
    assert first.json() == {"season": "s1", "segments": [], "frontier": None}

    _learner(db_session, day=18)  # g3.1, the roof's gap
    _learner(db_session, day=8)  # t2.a
    _learner(db_session, day=None)  # an account with no season life
    monkeypatch.setattr(frontier, "_cache", {})
    body = client.get("/api/v1/story-engine/season-frontier?season=s1").json()
    assert body == {"season": "s1", "segments": ["t2", "g3"], "frontier": "t2"}
    # only segment ids: never a learner, a count or a date
    assert set(body) == {"season", "segments", "frontier"}

    assert client.get("/api/v1/story-engine/season-frontier?season=s9").status_code == 404
    assert client.get("/api/v1/story-engine/season-frontier?season=../x").status_code == 422


def test_a_place_the_forge_builds_leaves_the_season_lexicon_current(tmp_path, monkeypatch):
    """The register changes with every build; the lexicon's source digest reads the files
    that hold words only, so a forge PR never makes ``lexicon.json`` stale."""
    import shutil

    from app.services import season_lexicon
    from app.services.season import format as season_format

    before = season_lexicon.source_digest("s1")
    shutil.copytree(season_format.SEASON_ROOT / "s1", tmp_path / "s1")
    (tmp_path / "s1" / "stages.json").write_text('{"stages": {"toit": "toit"}}\n', encoding="utf-8")
    monkeypatch.setattr(season_format, "SEASON_ROOT", tmp_path)
    assert season_lexicon.source_digest("s1") == before


# ---------------------------------------------------------------------------
# «Erst erwähnen, dann betreten» (Vincent, 8 Nov)
# ---------------------------------------------------------------------------


def _register(tmp_path, monkeypatch, **data):
    import shutil

    shutil.copytree(season_world.SEASON_ROOT / "s1", tmp_path / "s1")
    (tmp_path / "s1" / "stages.json").write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(season_world, "SEASON_ROOT", tmp_path)
    season_world.built_stages.cache_clear()
    season_world.story_places.cache_clear()


def test_a_place_not_built_is_one_a_page_may_name_never_one_it_is_set_in():
    context = _context()
    on_built_stage(context)
    built = set(built_stages("s1"))
    elsewhere = {place["id"] for place in context["world"]["elsewhere"]}
    # the mairie, the gare de l'Est, Gus's loft: named, not entered
    assert {"mairie", "gare_de_lest", "gus_loft"} <= elsewhere
    assert not elsewhere & built
    assert all(place["name_fr"] for place in context["world"]["elsewhere"])


def test_a_place_the_stories_named_and_the_forge_built_is_one_the_night_may_go_to(tmp_path, monkeypatch):
    from app.services import story_split

    librairie = {"name_fr": "La librairie de la rue Bichat", "description": "A narrow bookshop with a green front."}
    _register(
        tmp_path,
        monkeypatch,
        stages={"le_mistral": "quai_de_valmy", "stairwell": "escalier_mistral", "librairie_bichat": "librairie_bichat"},
        places={"librairie_bichat": librairie, "not_built": {"name_fr": "Nulle part"}},
    )
    try:
        assert set(season_world.story_places("s1")) == {"librairie_bichat"}, "a place is a story place once it is built"
        assert "librairie_bichat" in season_world.season_location_ids("s1")
        assert season_world.location_name_fr("librairie_bichat") == "La librairie de la rue Bichat"
        assert season_world.plate_for("librairie_bichat")

        context = _context()
        on_built_stage(context)
        offered = {place["id"]: place for place in context["world"]["locations"]}
        assert set(offered) == {"le_mistral", "stairwell", "librairie_bichat"}
        assert offered["librairie_bichat"]["name_fr"] == "La librairie de la rue Bichat"
        assert "librairie_bichat" in context["variety"]["all_locations"]
        # the planner reads both: where today may be set, and what it may only name
        payload = story_split.planner_payload({**context, "level": "A2", "control_language": "en"} | _planner_bits(), [])
        assert {place["id"] for place in payload["places"]} == set(offered)
        assert "mairie" in {place["id"] for place in payload["elsewhere"]}
    finally:
        season_world.built_stages.cache_clear()
        season_world.story_places.cache_clear()


def _planner_bits() -> dict:
    return {
        "season_script": {"brief": {"today": {}, "page_rules": {"voices": {"speakers": ["lila_bonnet"]}, "chapter": {"open_new": False}}}},
    }


def test_the_walk_s_fake_director_sets_a_season_page_where_it_was_offered():
    """The browser walks' fake (scripts/dev_story_engine_server.py) is a compliant
    director: since the night offers only the built places, a page it set at the bakery
    or the NGO office was refused as a place not in the world, and «Walk · season × 10
    days» failed on every push to main from #614 on."""

    import dev_story_engine_server as dev

    context = _context()
    on_built_stage(context)
    offered = {place["id"] for place in context["world"]["locations"]}
    context["season_script"] = {"brief": {}}
    assert {dev.FakeStoryProvider._season_draft(context, n)["location_id"] for n in range(14)} <= offered


def test_the_walk_s_fake_director_never_repeats_one_of_the_last_five_situations():
    """#717: the fake set a season page from a counter shared by the whole walk. On the
    11 Nov season walk all three attempts of day 7 landed on situations of the last five
    pages, the engine refused each one as ``repeated_situation``, and the day was lost
    (it re-read T1 Day B). A compliant director picks a situation not recently played."""

    import dev_story_engine_server as dev

    for n in range(14):
        recent = [
            {"premise_fr": dev.SEASON_PREMISES[(n + k) % len(dev.SEASON_PREMISES)], "objective_native": dev.PREMISES[(n + k) % len(dev.PREMISES)][1]}
            for k in range(5)
        ]
        context = {"season_script": {"brief": {}}, "recent_situations": recent}
        draft = dev.FakeStoryProvider._season_draft(context, n)
        assert draft["premise_fr"] not in {row["premise_fr"] for row in recent}, n
        assert draft["objective_native"] not in {row["objective_native"] for row in recent}, n
