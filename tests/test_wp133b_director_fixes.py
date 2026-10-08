"""WP-133b's two blocking director findings, fixed (live read 2026-10-06).

1. **The continuation brought back a character the ending removed.** Run 8 (B2), day
   62, «le matin après le départ de Lila» — and Lila on the quai, speaking. The cast a
   finished season says are gone (``epilogue.departed_cast``: Lila in Berlin after
   every ending, Margaux in Brittany after «Laisser partir») is never on a generated
   page: refused with a precise hint, and a second refusal is a lost day the reprise
   re-reads.
2. **The A1 rule-card example was woven verbatim.** Run 1 (A1), day 3: Margaux, «tu»
   since T1, asked «Je suis Margaux et vous êtes… ? Vous êtes l'héritier ?». The
   example is now a gender-neutral «tu» sentence; a season «tu» character's «vous» is
   refused (``season_register_vous``); and a person noun that genders the learner in
   second person is refused (``gendered_learner_noun``).

The offending lines of the live read are quoted verbatim as fixtures below.
"""

from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models.user import User
from app.services import living_story as engine
from app.services.grammar_units import plain
from app.services.season import epilogue as ep
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.reprise import REPRISE_SCENARIO_PREFIX
from tests import test_journey_end_to_end as support
from tests.test_living_story import _scene_context, draft
from tests.test_season_one import _latest_scene, season_on  # noqa: F401 - fixture
from tests.test_wp132b_epilogue import (
    ENDING_FLAGS,
    FINALE_DAY,
    _finished_state,
    needs_hooks,
    no_epilogue,  # noqa: F401 - fixture
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled

PATHS = {
    "romance": [{"gate": 1, "signal": "romance"}, {"gate": 4, "signal": "romance"}],
    "friendship": [{"gate": 1, "signal": "friendship"}, {"gate": 4, "signal": "friendship"}],
    "open": [],
}

# --- The live read's offending lines, verbatim -------------------------------------
# docs/implementation/atelier-v2/wp133b/r8-B2.1.md, day 62 (after the epilogue).
R8_PREMISE = (
    "Le matin après le départ de Lila. Sur le quai, on voit de l'autre côté de la canal "
    "une fenêtre encore allumée au troisième de la rue de Lancry. Lila a laissé un billet : "
    "qui est «L.» ?"
)
R8_P1_VISUAL = (
    "Plan large du quai de Valmy. Le canal, les arbres, la façade opposée avec une seule "
    "fenêtre allumée. Lila et Gus, debout sur le trottoir, regardent la fenêtre; Marin "
    "arrive en portant un thermos."
)
R8_P4_VISUAL = (
    "Plan rapproché sur Marin qui attend la réponse du lecteur, l'expression douce, un peu "
    "inquiète; Lila à côté, silencieuse, les mains dans les poches."
)
R8_LILA_LINES = ("Regarde — encore cette lumière.", "Si c'est Odile, elle nous enverrait un signe étrange, comme d'habitude.")
# docs/implementation/atelier-v2/wp133b/r1-A1.1.md, day 3 «La même chose ?».
R1_D3_MARGAUX = ("Je suis Margaux et vous êtes... ?", "Je suis ici depuis vingt ans. Vous êtes l'héritier ?", "La même chose ?")
# Same run, day 4 «Romy pose la question».
R1_D4_ROMY = "C'est vous, l'héritage ? Et vous, qu'en pensez-vous de Solvel ?"


def _state(ending: str, path: str = "open", *, upto: str = "t8") -> tuple:
    season = load_season("s1")
    state = _finished_state(season, ending, upto=upto)
    state["signals"] = list(PATHS[path])
    return season, state, effective_flags(season, state, seed="x")


# ---------------------------------------------------------------------------
# 1. Who the ending removed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", list(PATHS))
@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_each_ending_and_lila_path_names_who_has_left(ending, path, no_epilogue):  # noqa: F811
    season, state, flags = _state(ending, path)
    assert flags["s1.lila_path"] == path
    gone = {row["id"]: row for row in ep.departed_cast(season, state, flags)}
    # Lila leaves for Berlin on every ending and every path (T8 state_out).
    assert "lila_bonnet" in gone and gone["lila_bonnet"]["names"] == ["Lila"]
    assert ("margaux_barman" in gone) == (ending == "laisser_partir")
    assert set(gone) <= {"lila_bonnet", "margaux_barman"}, "no absence the season does not define"
    carried = ep.carried(season, state, flags, band="B2", language="en")
    assert [row["id"] for row in carried["departed"]] == list(gone)
    assert carried["registers"]["margaux_barman"] == "tu"
    assert carried["registers"]["camille_marchand"] == "vous"


def test_nobody_has_left_before_the_finale_is_played(no_epilogue):  # noqa: F811
    season, state, flags = _state("laisser_partir", upto="t7")
    assert ep.departed_cast(season, state, flags) == []


def test_a_seeded_life_without_the_stored_flag_still_reads_the_finale(no_epilogue):  # noqa: F811
    season, state, flags = _state("garder")
    flags = {key: value for key, value in flags.items() if key != "lila.in_berlin"}
    assert [row["id"] for row in ep.departed_cast(season, state, flags)] == ["lila_bonnet"]


def test_the_authored_epilogue_agrees_never_a_line_for_who_has_left():
    """The rule the guard enforces is the epilogue's own: on every branch Lila reaches
    Toi only by «sms», and on «Laisser partir» Margaux only by «card»."""

    season = load_season("s1")
    if not ep.has_epilogue(season):
        pytest.skip("the WP-132B epilogue is not on disk")
    for ending in ENDING_FLAGS:
        for path in PATHS:
            flags = {"s1.ending": ending, "s1.lila_path": path, "lila.in_berlin": True}
            gone = {member_id for member_id, *_ in ep.DEPARTED_BY_FLAG}
            gone |= {member_id for member_id, _ in ep.DEPARTED_BY_ENDING.get(ending, ())}
            for segment in ep.epilogue_ids(season):
                for letter in "ab":
                    page = resolve_day(season, segment, letter, flags=flags, band="B1", language="en")
                    speakers = set(re.findall(r'"who": "(\w+)"', json.dumps(page or {})))
                    assert not speakers & gone, (ending, path, segment, letter, speakers & gone)


@pytest.mark.parametrize("text", [R8_P1_VISUAL, R8_P4_VISUAL, "Lila sourit et pose son verre.", "Lila and Gus stand on the pavement."])
def test_a_panel_that_shows_lila_is_presence(text):
    assert ep.presence_on_page(text, ["Lila"])


@pytest.mark.parametrize(
    "text",
    [
        R8_PREMISE,
        "Evening. Toi's phone lights up on the table: a message from Lila, with a photo of a grey canal under rain, in Berlin.",
        "Lila's empty stool at the end of the zinc.",
        "Marin pense à Lila et sourit.",
        "Sur le frigo, une photo de Lila à Berlin.",
        "Gus lit à voix haute : Lila écrit qu'il pleut.",
        "Le canal, les arbres, une fenêtre allumée.",
    ],
)
def test_a_mention_a_memory_or_a_message_is_not_presence(text):
    assert ep.presence_on_page(text, ["Lila"]) is None


def _continuation_context(ending: str, *, level: str = "A2") -> dict:
    season, state, flags = _state(ending)
    context = _scene_context(level=level)
    context["world"] = {
        **context["world"],
        "cast": [
            {"id": "romy_tremblay", "name": "Romy Tremblay"},
            {"id": "lila_bonnet", "name": "Lila Bonnet"},
            {"id": "marin_leveque", "name": "Marin Lévêque"},
            {"id": "margaux_barman", "name": "Margaux"},
            {"id": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt"},
        ],
    }
    context["season_script"] = {
        "id": "s1",
        ep.CARRIED_KEY: ep.carried(season, state, flags, band=level, language="en"),
        "phase": "continuation",
    }
    context[engine.SEASON_TODAY_KEY] = SimpleNamespace(season=season, flags=flags)
    return context


def _tu_draft(context: dict, *, speaker: str = "marin_leveque") -> dict:
    value = deepcopy(draft(context, 0))
    value["character_id"] = speaker
    value["opening_line_fr"] = "Tu vois la fenêtre ? Qui peut être là, à ton avis ?"
    value["panels"][1]["dialogue"] = [{"character_id": speaker, "text_fr": "Tu as une idée ?"}]
    value["panels"][1]["visual_direction"] = "Marin leans on the parapet with a thermos."
    return value


def test_r8_day_62_is_refused_with_a_precise_hint(no_epilogue):  # noqa: F811
    context = _continuation_context("laisser_partir")
    value = _tu_draft(context)
    value["premise_fr"] = R8_PREMISE
    value["panels"][0]["visual_direction"] = R8_P1_VISUAL
    value["panels"][0]["dialogue"] = [{"character_id": "lila_bonnet", "text_fr": R8_LILA_LINES[0]}]
    with pytest.raises(engine.StoryUnavailable, match="departed_cast_on_page") as refused:
        engine._validate_scene(engine.SceneDraft.model_validate(value), context)
    assert "Lila" in refused.value.hint and "Berlin" in refused.value.hint
    assert "message" in refused.value.hint, "the hint names the way out"


@pytest.mark.parametrize("ending", list(ENDING_FLAGS))
def test_lila_on_the_page_is_refused_after_every_ending(ending, no_epilogue):  # noqa: F811
    context = _continuation_context(ending)
    # Only shown in a panel, never speaking (the r8 P4 panel).
    shown = _tu_draft(context)
    shown["panels"][1]["visual_direction"] = R8_P4_VISUAL
    with pytest.raises(engine.StoryUnavailable, match="departed_cast_on_page"):
        engine._validate_scene(engine.SceneDraft.model_validate(shown), context)
    # The character the learner talks to.
    addressed = _tu_draft(context, speaker="lila_bonnet")
    with pytest.raises(engine.StoryUnavailable, match="departed_cast_on_page"):
        engine._validate_scene(engine.SceneDraft.model_validate(addressed), context)
    # Mentioned, remembered, writing from Berlin: served.
    mentioned = _tu_draft(context)
    mentioned["premise_fr"] = R8_PREMISE
    mentioned["panels"][0]["visual_direction"] = "Toi's phone lights up: a message from Lila, a photo of Berlin."
    mentioned["panels"][1]["dialogue"].append({"character_id": "marin_leveque", "text_fr": "Lila me manque, tu sais."})
    engine._validate_scene(engine.SceneDraft.model_validate(mentioned), context)


def test_margaux_is_gone_only_after_laisser_partir(no_epilogue):  # noqa: F811
    for ending, refused in (("laisser_partir", True), ("garder", False), ("partager", False)):
        context = _continuation_context(ending)
        value = _tu_draft(context)
        value["panels"][1]["dialogue"].append({"character_id": "margaux_barman", "text_fr": "Tu as faim ?"})
        proposal = engine.SceneDraft.model_validate(value)
        if refused:
            with pytest.raises(engine.StoryUnavailable, match="departed_cast_on_page"):
                engine._validate_scene(proposal, context)
        else:
            engine._validate_scene(proposal, context)


def test_before_the_finale_lila_is_on_the_page_as_ever():
    context = _scene_context()
    value = deepcopy(draft(context, 0))
    value["panels"][1]["visual_direction"] = R8_P4_VISUAL
    engine._validate_scene(engine.SceneDraft.model_validate(value), context)


def _learner(client, db, *, cefr: str):
    email = f"wp133b-{uuid.uuid4()}@example.com"
    driver = support.Driver(client, support.register(client, email, cefr=cefr), db=db)
    return driver, db.scalar(select(User).where(User.email == email))


def _day(driver, clock):  # noqa: F811
    driver.create()
    journey = driver.journey
    assert journey["status"] == "active", journey
    driver.play(answer="Je ne sais pas.")
    assert driver.finish("complete").status_code == 200
    clock.advance(days=1)
    return journey


@needs_hooks
def test_a_director_that_keeps_staging_lila_loses_the_day_to_the_reprise(
    assembled_client, db_session, journey_enabled, clock, season_on, no_epilogue  # noqa: F811
):
    from app.services.season.admin import jump_to_day

    provider = season_on
    driver, user = _learner(assembled_client, db_session, cefr="B2.1")
    jump_to_day(db_session, user, day=FINALE_DAY, flags=ENDING_FLAGS["laisser_partir"])
    db_session.commit()
    for _ in range(3):  # T8 A, T8 B, the archive day
        _day(driver, clock)
    # The fake director's own continuation passes every guard: a generated day.
    journey = _day(driver, clock)
    assert not journey["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX), journey["scenario"]
    contexts = provider.director_contexts()
    assert [row["id"] for row in contexts[-1]["season_script"][ep.CARRIED_KEY]["departed"]] == [
        "lila_bonnet",
        "margaux_barman",
    ]

    def stages_lila(schema, value):
        if schema == "SceneDraft":
            value = deepcopy(value)
            value["panels"][0]["visual_direction"] = R8_P1_VISUAL
            value["panels"][0]["dialogue"] = [{"character_id": "lila_bonnet", "text_fr": R8_LILA_LINES[0]}]
        return value

    provider.transform = stages_lila
    before = len(provider.director_contexts())
    journey = _day(driver, clock)
    assert journey["scenario"]["scenario_key"].startswith(REPRISE_SCENARIO_PREFIX), journey["scenario"]
    assert len(provider.director_contexts()) - before >= 2, "the retry was told why, then the day is lost"
    retry = json.dumps(provider.director_contexts()[-1], ensure_ascii=False)
    assert "puts Lila on the page" in retry, "the retry carries the precise hint"


# ---------------------------------------------------------------------------
# 2a. The A1 example
# ---------------------------------------------------------------------------

#: The season's named cast (not «L'employée», «Un enfant»), as a page names them.
CAST_FIRST_NAMES = {
    member.name.split()[0] for member in load_season("s1").cast if not member.minor
} | {"Gus", "Marchand", "Odile"}


def _rule_cards(band: str) -> dict:
    return json.loads((Path(__file__).resolve().parents[1] / "app" / "data" / "rule_cards" / f"fr2_{band}.json").read_text(encoding="utf-8"))["cards"]


def _units(band: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "app" / "data" / "grammar_review" / f"units_{band}.json"
    return {unit["external_id"]: unit for unit in json.loads(path.read_text(encoding="utf-8"))["units"]}


def test_the_etre_example_is_a_gender_neutral_tu_sentence():
    card = _rule_cards("A1")["FR2_A11_ETRE"]
    unit = _units("A1")["FR2_A11_ETRE"]
    for sentence in (plain(card["example"]["fr"]), unit["xray_sentence"]):
        assert engine._address_register([sentence]) == "tu", sentence
        folded = f" {engine._folded(sentence)} "
        assert not engine._agreement_hits(folded, engine._MASCULINE_AGREEMENT + engine._FEMININE_AGREEMENT)
        assert not engine._person_noun_hits(folded, engine._MASCULINE_PERSON_NOUNS + engine._FEMININE_PERSON_NOUNS)
        assert not set(re.findall(r"\w+", sentence)) & CAST_FIRST_NAMES, sentence
        assert re.search(unit["detector"].removeprefix("regex:"), sentence, re.IGNORECASE)
    assert set(card["example"]["tr"]) == {"en", "de"}
    assert "du" in re.findall(r"\w+", card["example"]["tr"]["de"]) and "you" in card["example"]["tr"]["en"]
    for token in (item.split("=>")[0] for item in unit["xray_marks"].split("||")):
        assert token.casefold() in unit["xray_sentence"].casefold()


def test_the_old_example_is_caught_by_the_new_guards():
    """Had it been woven again, «le nouveau voisin» is a gendered learner noun."""

    with pytest.raises(engine.StoryUnavailable, match="gendered_(?:agreement|learner_noun)"):
        engine._check_address(["Je suis Margaux. Et vous, vous êtes le nouveau voisin ?"], "neutral")


@pytest.mark.parametrize("band", ["A1", "A2"])
def test_no_a1_a2_example_genders_the_learner_or_meets_the_cast_as_strangers(band):
    """The same defect anywhere else in A1/A2: an example a director weaves must not
    agree with «tu»/«vous», name the learner with a gendered noun, or introduce a
    season cast member as someone the learner does not know."""

    cards, units = _rule_cards(band), _units(band)
    adjectives = engine._MASCULINE_AGREEMENT + engine._FEMININE_AGREEMENT
    nouns = engine._MASCULINE_PERSON_NOUNS + engine._FEMININE_PERSON_NOUNS
    stranger = re.compile(
        rf"\b(?i:je suis|je m'appelle|vous connaissez|tu connais|c'est)\s+(?:{'|'.join(sorted(CAST_FIRST_NAMES))})\b"
    )
    for unit_id, unit in units.items():
        card = cards.get(unit_id) or {}
        sentences = [unit.get("xray_sentence") or "", *(part.strip() for part in (unit.get("anchor_examples") or "").split("|"))]
        sentences += [plain((card.get("example") or {}).get("fr") or "")]
        for sentence in filter(None, sentences):
            folded = f" {engine._folded(sentence)} "
            assert not engine._agreement_hits(folded, adjectives), (unit_id, sentence)
            assert not engine._person_noun_hits(folded, nouns), (unit_id, sentence)
            assert not stranger.search(sentence), (unit_id, sentence)


# ---------------------------------------------------------------------------
# 2b. The season's register, per character
# ---------------------------------------------------------------------------


def _register_context(flags: dict | None = None) -> dict:
    context = _scene_context()
    context["world"] = {
        **context["world"],
        "cast": [
            {"id": "margaux_barman", "name": "Margaux"},
            {"id": "romy_tremblay", "name": "Romy Tremblay"},
            {"id": "lila_bonnet", "name": "Lila Bonnet"},
            {"id": "marin_leveque", "name": "Marin Lévêque"},
            {"id": "mme_diallo", "name": "Mme Diallo"},
            {"id": "augustin_de_roncourt", "name": "Augustin « Gus » de Roncourt"},
        ],
    }
    context[engine.SEASON_TODAY_KEY] = SimpleNamespace(season=load_season("s1"), flags=dict(flags or {}))
    return context


def _spoken(context: dict, speaker: str, lines: tuple[str, ...], opening: str) -> engine.SceneDraft:
    value = deepcopy(draft(context, 0))
    value["character_id"] = speaker
    value["opening_line_fr"] = opening
    value["panels"][1]["dialogue"] = [{"character_id": speaker, "text_fr": line} for line in lines[:3]]
    return engine.SceneDraft.model_validate(value)


def test_r1_day_3_margaux_vous_is_refused():
    context = _register_context()
    lines = ("Je suis Margaux et vous êtes... ?", "Je suis ici depuis vingt ans. Vous êtes là ?", "La même chose ?")
    with pytest.raises(engine.StoryUnavailable, match="season_register_vous") as refused:
        engine._check_season_register(_spoken(context, "margaux_barman", lines, R1_D3_MARGAUX[0]), context)
    assert "Margaux" in refused.value.hint and "tu" in refused.value.hint
    # The verbatim day is refused by the whole validator too (the noun guard is first).
    with pytest.raises(engine.StoryUnavailable, match="gendered_learner_noun|season_register_vous"):
        engine._validate_scene(_spoken(context, "margaux_barman", R1_D3_MARGAUX, R1_D3_MARGAUX[0]), context)


def test_r1_day_4_romy_vous_is_refused():
    context = _register_context()
    proposal = _spoken(context, "romy_tremblay", ("C'est quoi, la vraie histoire ?", R1_D4_ROMY), R1_D4_ROMY)
    with pytest.raises(engine.StoryUnavailable, match="season_register_vous"):
        engine._check_season_register(proposal, context)


def test_strangers_officials_and_plurals_keep_their_vous():
    context = _register_context()
    engine._check_season_register(
        _spoken(context, "mme_diallo", ("Vous prenez une baguette ?",), "Vous voulez autre chose ?"), context
    )
    # Gus's weaponised vous until T3 (register.augustin_de_roncourt defaults to vous).
    engine._check_season_register(
        _spoken(context, "augustin_de_roncourt", ("Vous êtes en retard.",), "Vous venez ?"), context
    )
    # Marin to the learner and Lila at once.
    engine._check_season_register(
        _spoken(context, "marin_leveque", ("Vous venez tous les deux ?",), "Vous deux, vous restez dîner ?"), context
    )
    # A tu character saying tu: served.
    engine._check_season_register(_spoken(context, "margaux_barman", ("La même chose ?",), "Tu es où ?"), context)
    # Off a season, nothing to compare with.
    plain_context = _scene_context()
    engine._check_season_register(_spoken(plain_context, "romy_tremblay", (R1_D4_ROMY,), R1_D4_ROMY), plain_context)


def test_a_register_flag_moves_a_character_to_tu():
    context = _register_context({"register.augustin_de_roncourt": "tu"})
    with pytest.raises(engine.StoryUnavailable, match="season_register_vous"):
        engine._check_season_register(
            _spoken(context, "augustin_de_roncourt", ("Vous êtes en retard.",), "Vous venez ?"), context
        )


# ---------------------------------------------------------------------------
# 2c. Person nouns that gender the learner
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        R1_D3_MARGAUX[1],  # «Vous êtes l'héritier ?»
        "Tu es la voisine du troisième ?",
        "C'est toi, le voisin du troisième ?",
        "Vous êtes bien l'héritière d'Odile ?",
        "Tu n'es pas un étranger ici.",
        "Alors c'est vous, l'invité de Gus ?",
    ],
)
def test_a_gendered_person_noun_said_to_the_learner_is_refused(line):
    with pytest.raises(engine.StoryUnavailable, match="gendered_learner_noun") as refused:
        engine._check_address([line], "neutral")
    assert "learner" in refused.value.hint


@pytest.mark.parametrize(
    "line",
    [
        "Il est l'héritier d'Odile.",
        "Odile parle souvent de son héritier.",
        "Elle est la nouvelle voisine du troisième.",
        "Vous êtes chez la voisine ?",
        "Vous êtes les nouveaux voisins ?",
        R1_D4_ROMY.replace("Et vous, qu'en pensez-vous", "Et toi, tu en penses quoi"),
        "Tu connais le voisin du dessous ?",
    ],
)
def test_third_person_and_plural_mentions_pass(line):
    engine._check_address([line], "neutral")


def test_the_learners_own_address_and_words_are_honoured():
    engine._check_address(["Tu es la nouvelle voisine ?"], "feminine")
    engine._check_address(["Vous êtes l'héritier ?"], "masculine")
    with pytest.raises(engine.StoryUnavailable, match="gendered_learner_noun"):
        engine._check_address(["Vous êtes l'héritière ?"], "masculine")
    own = engine.learner_self_forms(["Je suis la nouvelle voisine."])
    assert "voisine" in own
    engine._check_address(["Ah, tu es la voisine !"], "neutral", own=own)


# ---------------------------------------------------------------------------
# The walk checks
# ---------------------------------------------------------------------------


def _walk_day(day: int, last: str, played: int, lines: list[tuple[str, str]], key: str = "story_x") -> dict:
    page = [{"dialogue": [{"character_id": who, "text_fr": text} for who, text in lines]}]
    return {
        "day": day,
        "season": {"id": "s1", "played": played, "last": last},
        "journey": {"day": day, "scenario": {"scenario_key": key}, "events": [{"page": page}]},
    }


def test_the_walk_checks_fire_on_the_live_reads_days_and_only_then():
    from tests import walk_checks_wp133b_director as checks

    margaux_vous = [("margaux_barman", line) for line in R1_D3_MARGAUX]
    authored_t1 = [("marin_leveque", "…Vous allez vraiment vendre l'appartement d'Odile ?")]
    bad = {
        "days": [
            _walk_day(1, "t1.a", 1, authored_t1),  # T1 A: Marin's first-meeting vous is the bible's
            _walk_day(3, "g1.1", 3, margaux_vous),
            _walk_day(59, "t8.b", 59, [("lila_bonnet", "Alors. Une dernière chose vraie ?")]),
            _walk_day(60, "t8.b", 59, [("lila_bonnet", R8_LILA_LINES[0]), ("marin_leveque", "Tu vois la fenêtre ?")]),
        ]
    }
    register = checks.check_season_tu_register(bad)
    assert len(register) == 1 and register[0].startswith("day 3: margaux_barman")
    departed = checks.check_departed_after_finale(bad)
    assert departed == ["day 60: Lila is on a generated page after the finale (she is in Berlin)"]
    nouns = [problem for day in bad["days"] for problem in checks.check_gendered_learner_nouns(day["journey"])]
    assert len(nouns) == 1 and "héritier" in nouns[0]

    good = {
        "days": [
            _walk_day(1, "t1.a", 1, authored_t1),
            _walk_day(3, "g1.1", 3, [("margaux_barman", "La même chose ?"), ("margaux_barman", "Tu es où ?")]),
            _walk_day(59, "t8.b", 59, [("lila_bonnet", "Alors. Une dernière chose vraie ?")]),
            _walk_day(60, "t8.b", 59, [("marin_leveque", "Lila me manque. Tu vois la fenêtre ?")]),
            _walk_day(61, "t8.b", 59, [("lila_bonnet", "Lis.")], key=f"{REPRISE_SCENARIO_PREFIX}t8.b"),
        ]
    }
    assert checks.check_season_tu_register(good) == []
    assert checks.check_departed_after_finale(good) == []
    assert not [problem for day in good["days"] for problem in checks.check_gendered_learner_nouns(day["journey"])]
