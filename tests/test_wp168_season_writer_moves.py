"""WP-168 «the season writer may move the story».

A finished season-1 life rolls over into a season the writer drafts, and that season
may change city, genre and the learner's situation (owner, 11 October). Checked here,
with a scripted director and no image call:

* a moved season merges into the world: the city, the new places with their plate
  briefs, the new faces with their rig parameters, who travelled and who stayed;
* a new place opens on a stand-in plate and, once painted, on its own (the painter is
  the shared plate interface, its image call faked);
* the structural gate and the critic refuse a move with no material behind it, and
  the canon guards hold (the departed cast never travels, a new face never takes a
  cast member's name);
* a new character reaches the reader as rig parameters that always draw.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.v1.endpoints import story_engine
from app.config import settings
from app.db.models.revue_place import RevuePlace
from app.schemas.story_projection import StoryEpisodeRead
from app.services import living_story as engine
from app.services import season_writer
from app.services.revue import plates as revue_plates
from app.services.season import plates as season_plates
from app.services.season import written_world
from app.services.season.clock import SEASON_KEY, nominal_calendar
from app.services.season.epilogue import CARRIED_KEY, carry_into_live
from app.services.season.format import load_season
from app.services.season.world import (
    location_name_fr,
    plate_for,
    season_location_ids,
    season_world_bible,
)
from app.services.serial import SerialThreadService

ROOT = Path(__file__).resolve().parents[1]
ENDING_FLAGS = {
    "garder": {"s1.flat_decision": "keep", "s1.evidence_shared": "marchand_only", "s1.margaux_persuaded": True},
    "partager": {"s1.flat_decision": "coop", "s1.evidence_shared": "public", "s1.gus_persuaded": True},
    "laisser_partir": {"s1.flat_decision": "sell"},
}


def finished_life(ending: str) -> dict:
    """A life that played season 1 to its finale with this ending, carried into ``live``."""

    season = load_season("s1")
    played = []
    for row in nominal_calendar(season):
        played.append({**row, "flex": 0, "date": None, "event_id": f"x:{row['key']}"})
        if row["segment"] == "t8" and row["day_in_segment"] == 2:
            break
    live = {
        SEASON_KEY: {"id": "s1", "played": played, "flags": dict(ENDING_FLAGS[ending]), "signals": []},
        "season_index": 1,
        "planted": [
            {"id": "p:polaroid", "text_fr": "Le Polaroid d'Odile, avec une photo d'un port inconnu.", "status": "planted", "character_id": "romy_tremblay"},
        ],
        "commitments": [
            {"id": "c:carte", "text_fr": "Écrire à Margaux quand elle enverra sa carte.", "status": "open", "witnesses": ["margaux_barman"]},
        ],
        "consequences": [
            {"id": "b:radio", "kind": "branch", "text_fr": "Vous avez promis à Romy un reportage ensemble.", "weight": 3, "day": 50, "last_referenced": None, "character_id": "romy_tremblay"},
        ],
    }
    return carry_into_live(live, season=season)


def _rig(**over) -> dict:
    return {"skin": "deeper", "hair": "braids", "top": "boubou", "top_colour": "ochre", **over}


def moving_draft(material: list[dict], *, setting_row: str | None = None, traveller: str = "romy_tremblay",
                 new_name: str = "Awa Ndiaye", new_id: str = "awa_ndiaye") -> dict:
    refs = [row["id"] for row in material]
    return {
        "title_fr": "Le port de la photo",
        "logline": "The learner follows Odile's Polaroid to Marseille, where Romy has a radio job and a harbour keeps a secret.",
        "logline_fr": "Une photo vous emmène à Marseille.",
        "your_arc": "Find the harbour of the photo, and say who you are there in French.",
        "first_episode_seed": "Saint-Charles station at dawn, the Polaroid in your pocket, Romy late as always.",
        "arcs": [
            {
                "id": f"s2_arc_{index}",
                "title_fr": f"Arc {index}",
                "characters": [traveller, new_id, "user"],
                "grounded_in": refs[index % len(refs)],
                "stages": [
                    {"id": "spark", "summary": "Something from before turns up in the harbour.", "sets": {"awa.x": "a"}},
                    {"id": "pressure", "summary": "It costs the learner a day of work to follow it.", "sets": {"awa.x": "b"}},
                    {"id": "tentpole", "summary": "It is answered on the quay, out loud.", "sets": {"awa.x": True}},
                ],
            }
            for index in range(3)
        ],
        "open_threads": [
            {"text": "Whose harbour is in the photo?", "text_fr": "Quel port est sur la photo ?", "grounded_in": refs[0]}
            for _ in range(3)
        ],
        "setting": {
            "city": "Marseille",
            "region": "Bouches-du-Rhône, France",
            "neighborhood": "Le Panier and the Vieux-Port",
            "genre": "a harbour mystery with a summer job",
            "situation": "The learner works the summer on a ferry ticket desk.",
            "situation_fr": "Cet été, vous travaillez au guichet du ferry.",
            "why": "Odile's Polaroid shows this harbour; Romy's radio job is here.",
            "grounded_in": setting_row or refs[0],
            "travelling_cast": [traveller],
            "keep_locations": [],
        },
        "places": [
            {"id": "quai_du_vieux_port", "name_fr": "Le quai du Vieux-Port", "kind": "harbour",
             "description": "The old harbour where the ferries leave.",
             "brief": "the Vieux-Port quay in Marseille: fishing boats, the ferry ticket kiosk, Notre-Dame-de-la-Garde on the hill, hard white noon light"},
            {"id": "bar_le_cargo", "name_fr": "Le Cargo", "kind": "bar",
             "description": "A dockers' bar where the radio crew meets.",
             "brief": "a narrow dockers' bar: a zinc counter, ship photographs, a ceiling fan, late amber light through blinds"},
            {"id": "studio_radio_galere", "name_fr": "Radio Galère", "kind": "studio",
             "description": "Romy's tiny radio studio above a laundrette.",
             "brief": "a tiny radio studio: egg-box foam walls, two microphones, a window over the rooftops, blue evening light"},
        ],
        "new_characters": [
            {"id": new_id, "name": new_name, "gender": "f", "role": "Ferry ticket desk manager, the learner's boss.",
             "personality": "Brisk, funny, misses nothing.", "wants": "To find who left a key at her desk.",
             "speech_pattern": "Short sentences, Marseille slang explained with a smile.", "register_with_user": "tu",
             "grounded_in": refs[0], "rig": _rig(glasses="round")},
        ],
    }


class MovingDirector:
    """The season writer's director and critic, scripted."""

    def __init__(self, draft_for, *, grows: bool = True, fresh: bool = True) -> None:
        self.draft_for = draft_for
        self.grows = grows
        self.fresh = fresh
        self.calls: list[str] = []
        self.payloads: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        data = json.loads(messages[0]["content"])
        schema = data["output_schema"]["title"]
        self.calls.append(schema)
        self.payloads.append(data["data"])
        if schema == "SeasonDraft":
            value = self.draft_for(data["data"]["material"])
        else:
            value = {
                "accepted": self.grows and self.fresh,
                "grows_from_material": self.grows,
                "fresh": self.fresh,
                "issues": [] if self.grows else ["the move is not motivated by any row"],
            }
        return SimpleNamespace(content=json.dumps(value, ensure_ascii=False), model="fake-season", provider="test",
                               total_tokens=10, cost=0.0)


@pytest.fixture(autouse=True)
def writer_on(monkeypatch) -> Generator[list, None, None]:
    monkeypatch.setattr(settings, "ATELIER_LLM_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_ENABLED", True)
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_MAY_MOVE", True)
    queued: list = []
    monkeypatch.setattr(written_world, "dispatcher", lambda bind, rows: queued.append(rows))
    written_world._IN_FLIGHT.clear()
    revue_plates._PAINTED.clear()
    yield queued
    written_world._IN_FLIGHT.clear()
    revue_plates._PAINTED.clear()


def roll(director, ending: str = "partager", db=None) -> tuple[SimpleNamespace, dict, bool]:
    thread = SimpleNamespace(id="thread-168", world_bible=season_world_bible("s1"))
    live = finished_life(ending)
    rolled = engine.roll_over_season(db, thread, live, day=66, today="2026-12-20")
    return thread, live, rolled


# ---------------------------------------------------------------------------
# 1. A moved season merges into the world
# ---------------------------------------------------------------------------


def test_a_moved_season_merges_into_the_world(monkeypatch):
    director = MovingDirector(moving_draft)
    monkeypatch.setattr(engine, "_client", lambda: director)
    thread, live, rolled = roll(director)

    assert rolled is True and director.calls == ["SeasonDraft", "SeasonReview"]
    world = thread.world_bible
    assert world["season_number"] == 2 and world["season_source"] == "written"
    assert world["world_bible_version"] == "marseille-s2-written"
    setting = world["setting"]
    assert (setting["city"], setting["previous_city"], setting["moved_in_season"]) == ("Marseille", "Paris", 2)
    assert setting["genre"] == "a harbour mystery with a summer job"
    # A change of city keeps no Paris place it did not name.
    places = {place["id"]: place for place in setting["recurring_locations"]}
    assert set(places) == {"quai_du_vieux_port", "bar_le_cargo", "studio_radio_galere"}
    quay = places["quai_du_vieux_port"]
    assert quay["plate_id"] == written_world.plate_id_for("quai_du_vieux_port", quay["brief"])
    assert quay["stand_in"] == "quai_de_valmy" and places["bar_le_cargo"]["stand_in"] == "le_mistral"
    assert world["visual_design"]["locations"]["bar_le_cargo"]["canonical_descriptor"].startswith("a narrow dockers'")
    # The director reads the new world: its logline, its places, who is here.
    assert world["logline"].startswith("The learner follows Odile's Polaroid to Marseille")
    cast = {member["id"]: member for member in world["cast"]}
    assert "away" not in cast["romy_tremblay"], "Romy travelled"
    assert "Stayed in Paris" in cast["marin_leveque"]["away"]
    assert cast["awa_ndiaye"]["rig"]["hair"] == "braids" and cast["awa_ndiaye"]["rig"]["glasses"] == "round"
    assert "away" not in cast["awa_ndiaye"]
    projection = {row["id"]: row for row in engine._cast_projection(world)}
    assert projection["marin_leveque"]["away"].startswith("Stayed in Paris")
    locations = {row["id"]: row for row in engine._locations(world)}
    assert locations["bar_le_cargo"]["image_url"] == plate_for("le_mistral")
    assert "brief" not in locations["bar_le_cargo"] and "plate_id" not in locations["bar_le_cargo"]
    assert live["season_premiere"]["title_fr"] == "Le port de la photo"
    # The writer was told it may move, and what may not be undone.
    payload = director.payloads[0]
    assert payload["may_move"] is True and payload["world"]["setting"]["city"] == "Paris"
    assert {row["id"] for row in payload["canon"]["departed"]} == {"lila_bonnet"}
    assert any("L." in rule for rule in payload["canon"]["rules"])
    assert not any("Montréal" in rule for rule in payload["canon"]["rules"]), "a move is not forbidden"


def test_a_season_that_stays_adds_its_places_to_the_old_ones():
    world = season_world_bible("s1")
    move = {"city": "Paris", "genre": "a heist comedy", "places": [
        {"id": "cave_du_mistral", "name_fr": "La cave", "type": "cellar", "brief": "a vaulted cellar, bottles, a bulb, cold light"},
    ]}
    after = written_world.apply_setting_move(world, move, next_season=2)
    ids = [place["id"] for place in after["setting"]["recurring_locations"]]
    assert "le_mistral" in ids and ids[-1] == "cave_du_mistral"
    assert "previous_city" not in after["setting"] and after["setting"]["genre"] == "a heist comedy"
    assert all("away" not in member for member in after["cast"])


def test_the_director_hears_the_written_seasons_rules_not_the_finished_ones():
    block = {CARRIED_KEY: {"rules": [
        "The whole cast knows the learner: never a stranger's welcome.",
        "This is the s1 world after its finale, not a new story: carry the ending.",
        "Never the old serial's second season («Choisir Paris», a Berlin opening, Montréal, Créteil).",
    ], "closed_locations": ["le_mistral"], "departed": [{"id": "lila_bonnet"}]}}
    world = {"season_source": "written", "season_number": 2, "season_title_fr": "Le port",
             "setting": {"city": "Marseille", "moved_in_season": 2}}
    after = engine._after_a_written_season(block, world)[CARRIED_KEY]
    assert after["rules"][0].startswith("The whole cast knows the learner")
    assert not any("Montréal" in rule or "not a new story" in rule for rule in after["rules"])
    assert "set in Marseille" in after["rules"][-1]
    assert after["closed_locations"] == [] and after["departed"] == [{"id": "lila_bonnet"}]
    assert engine._after_a_written_season(block, {"season_source": "reprise"}) is block


# ---------------------------------------------------------------------------
# 2. New places: a stand-in, then the painted plate
# ---------------------------------------------------------------------------


@pytest.fixture()
def plate_db(db_session: Session, db_engine) -> Generator[Session, None, None]:
    created = not inspect(db_engine).has_table(RevuePlace.__table__.name)
    RevuePlace.__table__.create(bind=db_engine, checkfirst=True)
    yield db_session
    db_session.rollback()
    db_session.query(RevuePlace).delete()
    db_session.commit()
    if created:
        RevuePlace.__table__.drop(bind=db_engine, checkfirst=True)


def test_new_places_open_on_a_stand_in_then_on_their_painted_plate(monkeypatch, tmp_path, plate_db, writer_on):
    director = MovingDirector(moving_draft)
    monkeypatch.setattr(engine, "_client", lambda: director)
    thread, live, rolled = roll(director, db=plate_db)
    assert rolled
    world = thread.world_bible
    # The rollover queued every new place for the painter, once.
    queued = [row["plate_id"] for batch in writer_on for row in batch]
    assert sorted(queued) == sorted(place["plate_id"] for place in written_world.written_places(world))
    assert written_world.ensure_painting(plate_db, world) == [], "already queued in this process"

    quay = written_world.place_row(world, "quai_du_vieux_port")
    stand_in = plate_for("quai_de_valmy")
    assert written_world.plate_url(plate_db, quay) == (stand_in, True)
    assert plate_for("quai_du_vieux_port", world=world) == stand_in
    assert plate_for("quai_du_vieux_port") is None, "without its world an unknown place has no plate"
    assert location_name_fr("quai_du_vieux_port", world=world) == "Le quai du Vieux-Port"
    assert "quai_du_vieux_port" in season_location_ids("s1", world=world)
    stand_in_panel = SimpleNamespace(image_url=stand_in, generation_metadata={"plate_url": stand_in, "plate_id": quay["plate_id"]})
    assert story_engine.panel_plate_url(stand_in_panel) == stand_in

    # The painter runs (its image call faked): one plate per place, through the shared interface.
    prompts: list[str] = []
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key-not-used")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", "local")
    monkeypatch.setattr(settings, "GRAPHIC_NOVEL_LOCAL_IMAGE_DIR", tmp_path)
    monkeypatch.setattr(revue_plates, "_call", lambda prompt: prompts.append(prompt) or Image.new("RGB", (1536, 1024), (241, 236, 225)))
    done = written_world.paint_places(plate_db.get_bind(), writer_on[0])
    assert len(done) == 3 and len(prompts) == 3
    assert any("Notre-Dame-de-la-Garde" in prompt for prompt in prompts)
    assert all("No people" in prompt for prompt in prompts)
    painted = done[quay["plate_id"]]
    assert plate_db.get(RevuePlace, season_plates.plate_key(quay["plate_id"])).plate_url == painted

    revue_plates._PAINTED.clear()  # a fresh process reads the row, not the memo
    assert written_world.plate_url(plate_db, quay) == (painted, False)
    assert {row["id"]: row["image_url"] for row in engine._locations(world, db=plate_db)}["quai_du_vieux_port"] == painted
    assert story_engine.panel_plate_url(stand_in_panel) == painted, "a panel bound on the stand-in now shows the plate"
    assert story_engine.panel_image_url(stand_in_panel) == painted
    assert written_world.unpainted(plate_db, world) == []
    # Painting again never repaints.
    assert written_world.paint_places(plate_db.get_bind(), writer_on[0]) == done and len(prompts) == 3


def test_painting_off_keeps_the_stand_ins_and_never_raises(monkeypatch):
    monkeypatch.setattr(written_world, "dispatcher", None)
    monkeypatch.setattr(season_plates, "generation_unavailable_reason", lambda: "ATELIER_SEASON_PLATES_ENABLED is false")
    place = {"id": "gare_saint_charles", "plate_id": "w-gare-1", "brief": "the station stairs, palms, morning light"}
    assert written_world.schedule_painting(SimpleNamespace(get_bind=lambda: None), [place]) == []
    assert written_world.plate_url(None, place) == (plate_for("gare_de_lest"), True)


@pytest.mark.parametrize(
    ("kind", "words", "lender"),
    [
        ("harbour", "quai_du_port", "quai_de_valmy"),
        ("nonsense", "gare_saint_charles", "gare_de_lest"),
        (None, "maquis_chez_tantie", "le_mistral"),
        (None, "vignes_du_domaine", "buttes_chaumont"),
        (None, "atlantis", "user_apartment"),
    ],
)
def test_every_new_place_has_a_stand_in_of_its_kind(kind, words, lender):
    place = {"id": words, "type": kind, "plate_id": "w-x", "brief": "somewhere, three landmarks, a light"}
    assert written_world.stand_in_location(place) == lender
    assert plate_for(lender), f"{lender} has a static plate"


# ---------------------------------------------------------------------------
# 3. The gate and the critic refuse a move with no material behind it
# ---------------------------------------------------------------------------


def test_a_move_with_no_material_behind_it_is_refused_before_the_critic(monkeypatch):
    director = MovingDirector(lambda material: moving_draft(material, setting_row="invented:sunny_south"))
    monkeypatch.setattr(engine, "_client", lambda: director)
    thread, live, rolled = roll(director)
    assert rolled is False and director.calls == ["SeasonDraft"]
    assert thread.world_bible["setting"]["city"] == "Paris"
    assert live["interlude"]["returns_on"] == "2027-01-03"


@pytest.mark.parametrize(("grows", "fresh"), [(False, True), (True, False)])
def test_the_critic_judges_both_the_material_and_the_freshness(monkeypatch, grows, fresh):
    director = MovingDirector(moving_draft, grows=grows, fresh=fresh)
    monkeypatch.setattr(engine, "_client", lambda: director)
    record: dict = {}
    world = season_world_bible("s1")
    live = finished_life("garder")
    assert season_writer.draft_next_season(live=live, world=world, next_season=2, record=record) is None
    assert director.calls == ["SeasonDraft", "SeasonReview"] and record["refused"] == "critic"
    assert record["review"]["grows_from_material"] is grows and record["review"]["fresh"] is fresh
    assert director.payloads[1]["proposal"]["setting"]["city"] == "Marseille", "the critic reads the move"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"traveller": "lila_bonnet"}, "departed_travels:lila_bonnet"),
        ({"new_name": "Margaux Petit", "new_id": "margaux_petit"}, "new_character_id:margaux_petit"),
        ({"new_name": "Romy Two", "new_id": "awa_two"}, "name_taken:Romy Two"),
    ],
)
def test_the_canon_guards_hold_in_a_moved_season(monkeypatch, change, reason):
    director = MovingDirector(lambda material: moving_draft(material, **change))
    monkeypatch.setattr(engine, "_client", lambda: director)
    record: dict = {}
    assert season_writer.draft_next_season(
        live=finished_life("partager"), world=season_world_bible("s1"), next_season=2, record=record
    ) is None
    assert record["refused"] == reason and director.calls == ["SeasonDraft"]


def test_margaux_cannot_travel_after_laisser_partir_and_the_closed_cafe_is_not_kept(monkeypatch):
    def draft(material):
        value = moving_draft(material, traveller="margaux_barman")
        return value

    director = MovingDirector(draft)
    monkeypatch.setattr(engine, "_client", lambda: director)
    record: dict = {}
    live = finished_life("laisser_partir")
    assert season_writer.draft_next_season(live=live, world=season_world_bible("s1"), next_season=2, record=record) is None
    assert record["refused"] == "departed_travels:margaux_barman"
    assert record["canon"]["closed_locations"] == ["le_mistral"]

    def keeps_the_cafe(material):
        value = moving_draft(material)
        value["setting"].update(city="Paris", keep_locations=["le_mistral"])
        return value

    director = MovingDirector(keeps_the_cafe)
    monkeypatch.setattr(engine, "_client", lambda: director)
    record = {}
    assert season_writer.draft_next_season(live=live, world=season_world_bible("s1"), next_season=2, record=record) is None
    assert record["refused"] == "closed_place:le_mistral"


def test_without_may_move_the_old_writer_is_untouched(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_SEASON_WRITER_MAY_MOVE", False)
    director = MovingDirector(moving_draft)
    monkeypatch.setattr(engine, "_client", lambda: director)
    thread, live, rolled = roll(director)
    assert rolled is False, "the old writer refuses a character the cast does not have"
    assert "may_move" not in director.payloads[0]


# ---------------------------------------------------------------------------
# 4. New characters render or degrade, never fail
# ---------------------------------------------------------------------------


def test_a_new_face_reaches_the_reader_as_rig_parameters():
    world = {"cast": [
        {"id": "romy_tremblay", "name": "Romy"},
        {"id": "awa_ndiaye", "name": "Awa Ndiaye", "rig": _rig(glasses="round", skin="ultraviolet")},
        {"id": "jo", "name": "Jo", "rig": "not a rig"},
    ]}
    db = SimpleNamespace(scalars=lambda query: [world])
    rigs = story_engine.cast_rigs(db, [SimpleNamespace(serial_thread_id="t")])
    assert [row["id"] for row in rigs] == ["awa_ndiaye"], "the fixed cast has its own rigs"
    assert rigs[0]["rig"]["skin"] == written_world.RIG_DEFAULTS["skin"], "an unknown value is the default"
    assert rigs[0]["rig"]["glasses"] == "round" and set(rigs[0]["rig"]) == set(written_world.RIG_VOCABULARY)
    assert story_engine.cast_rigs(db, []) == []
    # The projection documents it (E-5 validates real projections against these models).
    episode = {
        "id": "s", "scene_id": "s", "serial_thread_id": "t", "serial_episode_id": None, "journey_id": None,
        "title_fr": "Le port", "status": "available", "chapter": None, "panel_index": 0, "panels": [],
        "resolution": None, "grammar_focus": None, "cast_rigs": rigs,
    }
    assert StoryEpisodeRead.model_validate(episode).cast_rigs[0].id == "awa_ndiaye"


def test_a_written_rig_always_normalises():
    assert written_world.normalise_rig(None) == written_world.RIG_DEFAULTS
    rig = season_writer.RigDraft.model_validate({"hair": "Afro", "top_colour": "red colour", "skin": 7})
    assert (rig.hair, rig.top_colour, rig.skin) == ("afro", "red", written_world.RIG_DEFAULTS["skin"])
    schema = season_writer.SeasonDraft.model_json_schema()
    assert schema["$defs"]["RigDraft"]["properties"]["hair"]["enum"] == list(written_world.RIG_VOCABULARY["hair"])


def test_the_rig_vocabulary_is_the_drawn_sets_own():
    source = (ROOT / "web-frontend/components/cast/rig-params.ts").read_text(encoding="utf-8")
    block = source.split("export const RIG_VOCABULARY = {", 1)[1].split("} as const;", 1)[0]
    parsed = {
        key: tuple(re.findall(r"'([a-z_]+)'", values))
        for key, values in re.findall(r"^\s+([a-z_]+): \[(.*?)\],$", block, flags=re.MULTILINE)
    }
    assert parsed == written_world.RIG_VOCABULARY
    defaults = dict(re.findall(r"^\s+([a-z_]+): '([a-z_]+)',$", source.split("export const RIG_DEFAULTS", 1)[1].split("};", 1)[0], flags=re.MULTILINE))
    assert defaults == written_world.RIG_DEFAULTS


def test_the_merge_never_lets_a_new_face_replace_the_cast():
    world = SerialThreadService._load_world_bible()
    season = {"season_arcs": [], "cast_additions": [{"id": "marin_leveque", "name": "Impostor", "rig": {}}]}
    merged = SerialThreadService.merge_season_world_bible(world, season, next_season=2)
    marin = next(member for member in merged["cast"] if member["id"] == "marin_leveque")
    assert marin["name"] == "Marin Lévêque" and "rig" not in marin
