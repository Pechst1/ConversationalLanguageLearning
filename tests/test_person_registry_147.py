"""ROOT CAUSE #147: a person's address and relations live on the person, and there is one read.

Walk 8 Nov 2026 (#594): Margaux asks «Tu vas monter ?» and the learner's «toi» is «corrected»
because «Hier gilt „vous“: Augustin « Gus » de Roncourt siezt dich». The same night: Camille is
«Camille Marchand», vous, in the scene and «ton amie», tu, in the Courrier, and calls the
learner's grandmother hers. The register was declared per scene and page, and nothing said who
anybody is to the learner.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import address, cast_registry, living_story, story_lanes
from app.services.cast_registry import has_met, introduced_by, person
from app.services.season import runtime
from app.services.season.clock import SEASON_KEY
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from tests.test_season_story_qa import _page, _scenario

REPO = Path(__file__).resolve().parents[1]
GUS = "augustin_de_roncourt"
CAMILLE = "camille_marchand"
MARGAUX = "margaux_barman"


def _season_state(*, flags: dict | None = None, relationships: dict | None = None, played: list | None = None) -> dict:
    return {
        "relationships": relationships or {},
        "living_story": {
            SEASON_KEY: {
                "id": "s1",
                "played": played if played is not None else [{"segment": "t1", "day_in_segment": 1}],
                "flags": flags or {},
                "signals": [],
            },
        },
    }


# --------------------------------------------------------------------------- #
# The row: one address, the bible's relations
# --------------------------------------------------------------------------- #


def test_address_is_the_season_row_of_the_person():
    """``member.address`` and ``address.season_registers`` say the same for everyone."""

    season = load_season("s1")
    opening = address.season_registers(season, effective_flags(season, None))
    for cast_id, row in cast_registry.all_members().items():
        said = next(value for key, value in opening.items() if cast_registry.resolve_id(key) == cast_id)
        assert row.address == said, cast_id


def test_the_world_bible_says_the_same_register():
    world = json.loads((REPO / "app/data/season/s1/world.json").read_text(encoding="utf-8"))
    for row in world["cast"]:
        assert address.register_of(row["register_with_user"]) == cast_registry.member(row["id"]).address, row["id"]


def test_odile_is_the_learners_grandmother_and_camille_is_not_a_friend():
    odile = cast_registry.member("odile")
    assert odile.relation_to_learner.kind == "family"
    assert odile.relation_to_learner.label("fr") == "ta grand-mère"
    assert odile.relation_to_learner.label("de") == "deine Großmutter"

    camille = cast_registry.member(CAMILLE).relation_to_learner
    assert camille.kind == "other_side" and not camille.is_friend
    assert cast_registry.member("romy").relation_to_learner.is_friend


def test_camille_and_m_marchand_are_tied_both_ways():
    camille = cast_registry.member(CAMILLE).relations
    marchand = cast_registry.member("landlord_marchand").relations
    assert [(row.kind, row.other) for row in camille] == [("grandchild_of", "landlord_marchand")]
    assert [(row.kind, row.other) for row in marchand] == [("grandparent_of", CAMILLE)]
    # T1 B says it: «Mon grand-père a tout l'immeuble». Before that page nothing may.
    assert camille[0].known_from == (1, "b") == cast_registry.member(CAMILLE).first_day


def test_every_person_has_a_relation_in_three_languages_of_a_known_kind():
    data = json.loads(cast_registry.RELATIONS_PATH.read_text(encoding="utf-8"))
    for cast_id, row in cast_registry.all_members().items():
        relation = row.relation_to_learner
        assert relation is not None, cast_id
        assert relation.kind in data["kinds"], cast_id
        assert all(relation.label(code) for code in ("fr", "en", "de")), cast_id
    for cast_id in data["to_learner"]:
        assert cast_id in cast_registry.all_members(), cast_id


def test_a_relation_is_known_from_a_page_with_one_of_the_two_on_it():
    """Camille says it at T1 B, three tentpoles before M. Marchand walks in at T4 A."""

    members = cast_registry.all_members()
    for row in members.values():
        for tie in row.relations:
            assert min(row.first_day, members[tie.other].first_day) <= tie.known_from, (row.id, tie)


# --------------------------------------------------------------------------- #
# The one read
# --------------------------------------------------------------------------- #


def test_person_reads_name_role_relation_address_and_met():
    state = _season_state(played=[{"segment": "t1", "day_in_segment": 1}])
    margaux = person(MARGAUX, state, language="de")
    assert margaux.name == "Margaux"
    assert margaux.role == "Wirtin des Mistral"
    assert margaux.relation.kind == "host"
    assert margaux.address_now == "tu"
    assert margaux.met is True

    romy = person("romy", state)
    assert romy.id == "romy_tremblay" and romy.met is False


def test_someone_outside_the_registry_is_not_a_person_of_the_cast():
    """A one-letter extra has no relation and no face; the letter keeps its own tu or vous."""

    for outsider in ("boutique_anais", "agent_moreau", "clerk", ""):
        assert person(outsider, _season_state()) is None
    assert cast_registry.address_now("agent_moreau", None) is None


def test_a_first_letter_can_read_a_person_with_no_thread(monkeypatch):
    """The B1 first letter is written before any scene: Margaux reads with state None."""

    monkeypatch.setattr(runtime.settings, "ATELIER_SEASON_SCRIPT", "s1", raising=False)
    margaux = person(MARGAUX, None)
    assert margaux.address_now == "tu" and margaux.name == "Margaux"
    # ``met`` cannot tell without a story; a first letter asks the day instead.
    assert person("romy", None).met is True
    assert introduced_by("romy", 1, "a") is False
    assert introduced_by(MARGAUX, 1, "a") is True


def test_address_now_wraps_known_register_and_adds_no_second_reader(monkeypatch):
    seen = {}

    def known(state, character_id, *, registers=None):
        seen.update(state=state, character_id=character_id, registers=registers)
        return "tu"

    monkeypatch.setattr(address, "known_register", known)
    assert person(GUS, {"x": 1}, registers={"y": "vous"}).address_now == "tu"
    assert seen == {"state": {"x": 1}, "character_id": GUS, "registers": {"y": "vous"}}


def test_the_import_direction_stays_lazy():
    """``address`` is imported by the registry, and reads it only inside its functions."""

    tree = ast.parse((REPO / "app/services/address.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom | ast.Import):
            assert "cast_registry" not in ast.dump(node)


# --------------------------------------------------------------------------- #
# The rule: during a season the season decides, afterwards the relationship does
# --------------------------------------------------------------------------- #


def test_during_a_season_a_settle_writes_the_seasons_value_back():
    season = load_season("s1")
    relationships = {CAMILLE: {"register": "tu", "closeness": 3}}
    state = _season_state(relationships=relationships)
    runtime._apply_registers(season, state["living_story"][SEASON_KEY], relationships)
    assert relationships[CAMILLE]["register"] == "vous"
    assert person(CAMILLE, state).address_now == "vous"


def test_gus_moves_to_tu_with_the_flag():
    season = load_season("s1")
    before = _season_state()
    assert person(GUS, before).address_now == "vous"
    after = _season_state(flags={"register.augustin_de_roncourt": "tu"})
    relationships: dict = {}
    runtime._apply_registers(season, after["living_story"][SEASON_KEY], relationships)
    after["relationships"] = relationships
    assert person(GUS, after).address_now == "tu"


def test_afterwards_the_relationship_decides():
    """No season runs: an accepted «On se tutoie ?» is what the relationship map keeps."""

    state = {"relationships": {CAMILLE: {"register": "tu", "closeness": 5}}, "living_story": {"day_index": 200}}
    assert person(CAMILLE, state).address_now == "tu"
    # The landlord says vous whatever a row says.
    state["relationships"]["landlord_marchand"] = {"register": "tu"}
    assert person("landlord_marchand", state).address_now == "vous"


def test_the_story_does_not_ask_on_se_tutoie_while_a_season_runs():
    """``living_story`` never asks during a season. The rule above rests on this line."""

    source = (REPO / "app/services/living_story.py").read_text(encoding="utf-8")
    assert re.search(r"asking = None if season_today is not None else tutoiement_candidate\(", source)


# --------------------------------------------------------------------------- #
# The generated reply: the person first, the page only off a season
# --------------------------------------------------------------------------- #


def _payload(line: str, *, season_turn: dict | None = None, relationships: dict | None = None, who: str = GUS) -> dict:
    story: dict = {"relationships": relationships or {}}
    if season_turn is not None:
        story["season_turn"] = season_turn
    return {"story": story, "scene": {"character_id": who, "opening_line_fr": line, "panels": []}}


@pytest.mark.parametrize(
    "line, season_turn, relationships, who, expected",
    [
        # A season day: the season's value, whatever the page says.
        ("Tu viens ce soir ?", {"register": "vous"}, {}, GUS, "vous"),
        ("Vous deux, vous venez ?", {"register": "tu"}, {}, "lila_bonnet", "tu"),
        ("Tu… pardon. Vous venez ?", {"register": "vous"}, {}, GUS, "vous"),
        # A season day that holds no register for this speaker: never the page.
        ("Vous venez ?", {"may_set": [], "gate": None}, {}, GUS, None),
        # Off a season: the relationship, where «On se tutoie ?» is kept.
        ("Vous venez ?", None, {"lila_bonnet": {"register": "tu"}}, "lila_bonnet", "tu"),
        ("Vous venez ?", None, {"lila_bonnet": {"register": "tu"}}, "lila", "tu"),
        ("Tu viens ?", None, {CAMILLE: {"register": "vous / poli"}}, CAMILLE, "vous"),
        # Off a season, and the relationship does not say: the page, as an older story has it.
        ("Vous venez ?", None, {}, "romy_tremblay", "vous"),
        ("Tu viens ?", None, {}, "romy_tremblay", "tu"),
        ("Bonjour.", None, {}, "romy_tremblay", None),
    ],
)
def test_reply_register(line, season_turn, relationships, who, expected):
    payload = _payload(line, season_turn=season_turn, relationships=relationships, who=who)
    assert story_lanes._reply_register(payload) == expected


def test_a_later_acts_turn_carries_the_persons_register():
    """Source check: the act branch of ``_turn_payload`` writes ``season_turn.register`` too;
    without it a later act read as a season day with no register, and the reply had none."""

    source = (REPO / "app/services/living_story.py").read_text(encoding="utf-8")
    branch = source.split("the day's first act alone moves the season.", 1)[1].split('context["agendas"]', 1)[0]
    assert '"register": register' in branch


# --------------------------------------------------------------------------- #
# The tutor on an authored page reads the turn's addressee, not the first speaker
# --------------------------------------------------------------------------- #


def _t1a_scenario():
    return _scenario(_page())


def test_the_tutor_is_told_the_register_of_the_person_the_turn_is_for():
    """T1 A, turn 2: Margaux says tu and the scene's first speaker, Gus, says vous. A real
    model was told «register: vous» and could write the #594 correction in the margin."""

    scenario = _t1a_scenario()
    first_turn = scenario.story_context["season"]["turns"][0]
    history = [{"learner": "Non.", "route": {"turn": first_turn["id"], "reply": first_turn["replies"][0]["id"]}}]
    addressee = living_story._authored_addressee(scenario, history)
    assert addressee is not None
    assert addressee["id"] != GUS and addressee["register"] == "tu"

    scene = {"character_id": GUS, "opening_line_fr": "Vous êtes qui ?", "panels": []}
    payload = {"story": {}, "scene": scene, "addressee": addressee, "learner_text": "Oui", "history": []}
    assert story_lanes.tutor_payload(payload)["task"]["register"] == "tu"


def test_off_an_authored_page_there_is_no_addressee():
    scenario = SimpleNamespace(story_context={"season": {"kind": "gap"}}, character_id=GUS)
    assert living_story._authored_addressee(scenario, []) is None


def test_has_met_still_reads_the_season_reach():
    assert has_met(_season_state(played=[{"segment": "t4", "day_in_segment": 1}]), "romy") is True
    assert has_met(_season_state(), "romy") is False
