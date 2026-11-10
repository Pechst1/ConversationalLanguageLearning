"""Red-thread design, slice 3: the ending keeps the day's «after».

10 November, the canapé day. The plan: «there is a menu, and one canapé has a name the
learner gave it». The learner asked «C'est quoi, un canapé ?». The ending read «je ne
choisis pas encore», the settle marked the beat done, and the next page stood on a menu
nobody had seen. With ``STORY_DAY_CONTRACT`` the day's ending is the contract's: every
route makes every ``lands`` fact true, the learner's own words fill the day's mark when
they gave some, and the season keeps a ledger of what became true and by which route.

Fake models only: nothing is spent.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.services import lane_guards
from app.services import living_story as engine
from app.services import story_lanes as lanes
from app.services.season import clock as season_clock
from app.services.season import day_contract
from app.services.season.format import LEVEL_FIELDS, Forbidden, load_season
from tests import test_journey_end_to_end as support
from tests.test_season_one import (  # noqa: F401 - fixture
    _latest_scene,
    _play,
    _season_state,
    _thread,
    season_on,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


@pytest.fixture
def contract_on(monkeypatch):
    monkeypatch.setattr(settings, "STORY_DAY_CONTRACT", True, raising=False)


def _beat(gap_id: str, premise: str):
    season = load_season("s1")
    gap, beat = day_contract.beat_for(season, gap_id, premise)
    return season, gap, beat


def _ctx(premise: str, *, day: int, segment: str = "g3", **extra) -> dict:
    return {
        "kind": "gap",
        "position": {"season_id": "s1", "segment": segment, "day_in_segment": day, "key": f"{segment}.{day}"},
        "checklist": {"premise_id": premise},
        "required_premise": premise,
        **extra,
    }


def _contract_days():
    season = load_season("s1")
    return [(gap, beat) for gap in season.gaps.values() for beat in gap.days if beat.contract]


# --- the flag off -------------------------------------------------------------


def test_off_by_default_no_turn_is_told_about_a_contract():
    season = load_season("s1")
    assert day_contract.for_turn(season, _ctx("les_canapes", day=5), band="A1") is None
    assert engine._contract_day({"season": _ctx("les_canapes", day=5)}) is None


def test_the_plain_schemas_do_not_carry_the_readings():
    # Every day without a contract sends the prompt it sent before: the two readings
    # live on a variant of the schema, under the same name.
    for base in (engine.SemanticTurn, lanes.StoryTurn):
        assert "contract_route" not in base.model_json_schema()["properties"]
        variant = engine._contract_turn_schema(base)
        assert variant.__name__ == base.__name__ and variant is engine._contract_turn_schema(base)
        assert {"contract_route", "contract_mark_fr"} <= set(variant.model_json_schema()["properties"])
        assert set(base.model_json_schema()["properties"]) < set(variant.model_json_schema()["properties"])


# --- what the lanes read ------------------------------------------------------


def test_the_lanes_read_the_floor_the_routes_and_the_mark(contract_on):
    season = load_season("s1")
    plan = day_contract.for_turn(season, _ctx("les_canapes", day=5), band="A1")
    assert plan["must_hold"] == ["The party has a menu of three canapés."]
    assert [route["id"] for route in plan["routes"]] == ["named", "picked", "elsewhere"]
    assert plan["default_route"] == "elsewhere"
    assert plan["mark"] == {"kind": "name", "max_words": 4, "ask": "Give the canapé a name."}
    # A page about something else, a bridge, a reprise: no contract.
    assert day_contract.for_turn(season, _ctx("sur_le_toit", day=5) | {"required_premise": "les_canapes"}, band="A1") is None
    assert day_contract.for_turn(season, _ctx("les_canapes", day=5, reprise={"of": "g3.5"}), band="A1") is None


def _lane_payload(contract: dict | None) -> dict:
    season_turn = {"may_set": [], "gate": None, **({"contract": contract} if contract else {})}
    return {
        "story": {"level": "A1", "learner": {"address": "neutral"}, "control_language": "de", "commitments": [], "season_turn": season_turn},
        "scene": {"character_id": "marin_leveque", "opening_line_fr": "Lequel reste ?", "objective_native": "", "panels": []},
        "learner_text": "C'est quoi, un canapé ?",
        "history": [],
        "targets": [],
        "turn_plan": {},
    }


def test_the_voice_reads_what_must_hold_and_never_the_routes(contract_on):
    season = load_season("s1")
    plan = day_contract.for_turn(season, _ctx("les_canapes", day=5), band="A1")
    voice = lanes.voice_payload(_lane_payload(plan))
    assert voice["contract"] == {"must_hold": plan["must_hold"], "mark": plan["mark"]}
    assert "contract" not in lanes.voice_payload(_lane_payload(None))
    assert "je ne choisis pas encore" in day_contract.voice_note("contract")
    assert day_contract.voice_note("contract").lstrip().startswith("contract is today's plan")
    assert "copied verbatim" in day_contract.ending_note()


# --- the code decides ---------------------------------------------------------


def _choose(premise: str, *, route=None, mark=None, lines=(), name="Vincent", gap_id="g3"):
    season, gap, beat = _beat(gap_id, premise)
    return day_contract.choose(season, gap, beat, route=route, mark=mark, learner_lines=list(lines), name=name)


def test_the_learners_name_for_the_canape_is_kept_word_for_word():
    choice = _choose("les_canapes", route="named", mark="le petit bateau", lines=["Le deux.", "Le petit bateau !"])
    assert choice == {
        "route": "named",
        "route_source": "learner",
        "mark": {"id": "g3.canape_name", "text": "Le petit bateau", "kept": True},
    }


def test_a_question_lands_on_the_default_route_with_the_authored_name():
    choice = _choose("les_canapes", route=None, mark=None, lines=["C'est quoi, un canapé ?"])
    assert choice["route"] == "elsewhere" and choice["route_source"] == "default"
    assert choice["mark"] == {"id": "g3.canape_name", "text": "le canapé de Vincent", "kept": False}
    # Nobody in the story knows the learner's name: the house's canapé, never a word
    # that would have to agree with them.
    assert _choose("les_canapes", lines=["Euh."], name=None)["mark"]["text"] == "le canapé de la maison"


@pytest.mark.parametrize(
    "mark, lines",
    [
        ("Le petit bateau", ["Le deux."]),  # the model's words, not the learner's
        ("C'est quoi ?", ["C'est quoi ?"]),  # a question is not a name
        ("le très petit bateau bleu de Marin", ["le très petit bateau bleu de Marin"]),  # six words for four
        ("", ["Le deux."]),
        ("{name}", ["{name}"]),
    ],
)
def test_a_mark_that_is_not_the_learners_own_short_words_is_never_kept(mark, lines):
    choice = _choose("les_canapes", route="named", mark=mark, lines=lines)
    assert choice["mark"]["kept"] is False and choice["mark"]["text"] == "le canapé de Vincent"
    # «named» without a name is «picked»: the learner did choose.
    assert choice["route"] == "picked" and choice["route_source"] == "learner"


def test_a_mark_never_carries_what_the_season_keeps_for_later():
    season, _gap, beat = _beat("g3", "les_canapes")
    secret = Forbidden(id="x", text="The city is a secret.", patterns=[r"\bberlin\b"])
    assert day_contract.kept_mark(beat.contract.mark, "Berlin", ["Berlin"], forbidden=[secret]) is None
    assert day_contract.kept_mark(beat.contract.mark, "Paris", ["Paris"], forbidden=[secret]) == "Paris"


def test_a_route_the_plan_does_not_have_is_the_default_one():
    for route in ("won", "", None, 3, "NAMED"):
        assert _choose("au_milieu_du_mur", route=route)["route"] == "elsewhere"
    assert _choose("au_milieu_du_mur", route="chose") == {"route": "chose", "route_source": "learner"}


# --- the ending ---------------------------------------------------------------


def _ending(premise: str, choice: dict, *, band="A1", language="de", character="marin_leveque", gap_id="g3"):
    _season, _gap, beat = _beat(gap_id, premise)
    return day_contract.ending(beat, choice, band=band, language=language, character_id=character)


def test_the_canape_day_with_the_learners_name():
    choice = _choose("les_canapes", route="named", mark="Le petit bateau", lines=["Le petit bateau"])
    assert _ending("les_canapes", choice) == {
        "resolution_fr": "« Le petit bateau ». J'adore. Voilà, le menu est fait : trois canapés pour samedi.",
        "summary_native": "Es gibt ein Menü. Ein Canapé heißt „Le petit bateau“.",
        "fact_fr": "Il y a un menu pour samedi. Un canapé s'appelle « Le petit bateau ».",
        "narrated": False,
    }


def test_the_canape_day_with_the_reply_of_10_november():
    # «C'est quoi, un canapé ?»: Marin chooses alone, and there is a menu.
    choice = _choose("les_canapes", lines=["C'est quoi, un canapé ?"])
    ending = _ending("les_canapes", choice, language="en", band="A2")
    assert ending["resolution_fr"] == (
        "Bon, je choisis. Celui-là, c'est « le canapé de Vincent ». Voilà, le menu est fait : trois canapés pour samedi."
    )
    assert ending["summary_native"] == "There is a menu for Saturday. One canapé is called “le canapé de Vincent”."
    assert "pas encore" not in ending["resolution_fr"]


def test_a_page_that_turned_to_someone_else_closes_on_what_changed_as_a_caption():
    choice = _choose("les_canapes", route="picked", lines=["Le deux."])
    ending = _ending("les_canapes", choice, character="lila_bonnet")
    assert ending["narrated"] is True
    assert ending["resolution_fr"] == "Il y a un menu. Un canapé s'appelle « le canapé de Vincent »."
    # The ticket day has no lead in the cast (an airline's voice): always a caption.
    ticket = _ending("le_billet_encore", _choose("le_billet_encore", route="moved"), character="clerk")
    assert ticket["narrated"] is True and ticket["resolution_fr"] == "Ton billet change. Tu restes après la fête."


def test_a_french_reader_gets_the_french_summary():
    ending = _ending("au_milieu_du_mur", _choose("au_milieu_du_mur", route="chose"), language="fr", character="lila_bonnet")
    assert ending["summary_native"] == "Le mur est prêt. Il y a une photo au milieu."


@pytest.mark.parametrize("band", ["A1", "A2", "B1", "C1"])
@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_every_route_of_every_day_lands_the_floor(band, language):
    """Whatever the learner says, the facts the day owes are on the page the learner
    reads: in the bubble or in «what changed»."""

    for gap, beat in _contract_days():
        contract = beat.contract
        season = load_season("s1")
        for route in contract.routes:
            for mark, lines in ((None, []), ("deux mots", ["deux mots"])):
                choice = day_contract.choose(season, gap, beat, route=route.id, mark=mark, learner_lines=lines, name="Vincent")
                ending = day_contract.ending(beat, choice, band=band, language=language, character_id=contract.lead)
                where = f"{gap.id}.{beat.day} {route.id} {band} {language}"
                for field in ("resolution_fr", "summary_native", "fact_fr"):
                    assert ending[field].strip(), where
                    assert "{" not in ending[field] and "}" not in ending[field], (where, ending[field])
                assert not ending["resolution_fr"].rstrip().endswith("?"), where
                assert len(ending["resolution_fr"]) <= 450 and len(ending["summary_native"]) <= 350, where
                if band == "A1":
                    assert len(ending["resolution_fr"].split()) <= 35, (where, ending["resolution_fr"])
                read = f"{ending['resolution_fr']} {ending['fact_fr']}".casefold()
                for fact in contract.lands:
                    assert all(word.casefold() in read for word in fact.show), (where, fact.id, read)
                if language != "fr":
                    assert ending["summary_native"] != ending["fact_fr"], where
                if contract.mark:
                    assert choice["mark"]["text"] in ending["fact_fr"], where
                assert ending["narrated"] is (route.line is None or contract.lead is None), where


def test_no_closing_line_breaks_the_season_and_none_ends_on_a_question():
    from app.services.season import director

    season = load_season("s1")
    for gap, beat in _contract_days():
        texts = [
            getattr(route.line, field)
            for route in beat.contract.routes
            if route.line
            for field in LEVEL_FIELDS
            if getattr(route.line, field, None)
        ]
        texts += [*beat.contract.after_fr.native.values(), *beat.contract.after_fr.native_a1.values()]
        assert not director.pattern_hits([*gap.must_not, *season.global_must_not], texts), (gap.id, beat.day)
        # The canon: nothing agrees with Toi, whoever they are; the bubble is the
        # lead's own voice and its summary tells the story.
        french = [text for text in texts if text not in beat.contract.after_fr.native.values() and text not in beat.contract.after_fr.native_a1.values()]
        french += [value for field in LEVEL_FIELDS if (value := getattr(beat.contract.after_fr, field, None))]
        for address in ("neutral", "feminine", "masculine"):
            lane_guards.check_lane_gender(french, address, field=f"{gap.id}.{beat.day}")
            lane_guards.check_agreement(french, address)
        if beat.contract.lead:
            assert beat.contract.lead in {member.id for member in season.cast}


# --- the ledger and «Précédemment» ------------------------------------------------


def test_the_ledger_keeps_what_became_true_and_by_which_route():
    _season, gap, beat = _beat("g3", "les_canapes")
    choice = _choose("les_canapes", route="named", mark="Le petit bateau", lines=["Le petit bateau"])
    after = "Il y a un menu pour samedi. Un canapé s'appelle « Le petit bateau »."
    state = day_contract.record({"id": "s1"}, gap, beat, choice, after_fr=after, event_id="e1", day_index=26, date="2026-11-10")
    ledger = state[day_contract.LEDGER_KEY]
    assert ledger["facts"] == [{"id": "g3.menu", "day": "g3.5", "route": "named", "source": "contract", "event_id": "e1"}]
    assert ledger["marks"]["g3.canape_name"] == {
        "text": "Le petit bateau", "kept": True, "kind": "name", "day": "g3.5", "comes_back": ["g3.7", "t4"], "event_id": "e1",
    }
    assert ledger["after"][-1]["text_fr"] == after and ledger["after"][-1]["day_index"] == 26
    # A replay of the same event writes nothing twice.
    assert day_contract.record(state, gap, beat, choice, after_fr=after, event_id="e1", day_index=26, date="2026-11-10") == state


def test_precedemment_ends_on_what_yesterday_changed(contract_on):
    _season, gap, beat = _beat("g3", "les_canapes")
    choice = _choose("les_canapes", lines=["Euh."])
    after = "Il y a un menu pour samedi. Un canapé s'appelle « le canapé de Vincent »."
    state = day_contract.record({"id": "s1"}, gap, beat, choice, after_fr=after, event_id="e1", day_index=26, date="2026-11-10")
    live = {"day_index": 26, "season_script": state}
    assert day_contract.previously(live, ["Marin a six recettes."]) == ["Marin a six recettes.", after]
    assert day_contract.previously(live, ["a", "b", "c"]) == ["b", "c", after]
    assert day_contract.previously(live, [after, "b"]) == ["b", after]
    # Another day was played since: the ledger row is history, the box keeps its own.
    assert day_contract.previously({**live, "day_index": 27}, ["a"]) == ["a"]


def test_precedemment_is_untouched_with_the_flag_off():
    live = {"day_index": 1, "season_script": {day_contract.LEDGER_KEY: {"after": [{"text_fr": "x", "day_index": 1}]}}}
    assert day_contract.previously(live, ["a"]) == ["a"]


# --- a whole day, through the journey ---------------------------------------------


def _canape_season_day() -> int:
    season = load_season("s1")
    index = [segment.id for segment in season.segments].index("g3")
    return sum(segment.days for segment in season.segments[:index]) + 5


def _reads(provider, monkeypatch, *, route: str | None, mark: str | None):
    """The fake model reads the learner: the route their words took, their own words."""

    reply = provider.generate_chat_completion
    seen: list[dict] = []

    def answer(messages, **kwargs):
        response = reply(messages, **kwargs)
        data = json.loads(messages[0]["content"])
        if data["output_schema"]["title"] not in ("StoryTurn", "SemanticTurn"):
            return response
        contract = ((data["data"].get("story") or {}).get("season_turn") or {}).get("contract")
        seen.append({"schema": data["output_schema"], "contract": contract, "system": kwargs.get("system_prompt")})
        if not contract or "contract_route" not in data["output_schema"]["properties"]:
            return response
        value = {**json.loads(response.content), "contract_route": route, "contract_mark_fr": mark}
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", answer)
    return seen


def _canape_day(assembled_client, db_session, clock, provider, answer: str):
    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    email = f"s1-contract-{uuid.uuid4()}@example.com"
    d = support.Driver(assembled_client, support.register(assembled_client, email, cefr="A1.2"), db=db_session)
    user = db_session.scalar(select(User).where(User.email == email))
    jump_to_day(db_session, user, day=_canape_season_day())
    # The four planned days before it were played: their premises are staged.
    thread = _thread(db_session, user.id)
    state = dict(thread.state or {})
    live = dict(state.get(engine.STATE_KEY) or {})
    season = dict(live.get(season_clock.SEASON_KEY) or {})
    staged = [beat.premise for beat in load_season("s1").gaps["g3"].days if beat.day < 5]
    season["premises"] = [*(season.get("premises") or []), *[{"gap": "g3", "premise": premise} for premise in staged]]
    thread.state = {**state, engine.STATE_KEY: {**live, season_clock.SEASON_KEY: season}}
    db_session.commit()
    journey = _play(d, provider, clock, answer)
    return d, user, journey


def _resolution(journey: dict) -> dict:
    return next(step for step in journey["steps"] if step["kind"] == "resolution")


@pytest.mark.parametrize("season_on", [False, True], ids=["one-actor", "lanes"], indirect=True)
def test_the_canape_day_lands_its_menu_whatever_the_model_wrote(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    provider = season_on
    seen = _reads(provider, monkeypatch, route=None, mark=None)
    d, user, journey = _canape_day(assembled_client, db_session, clock, provider, "C'est quoi, un canapé ?")

    scene = _latest_scene(db_session, user.id)
    assert (scene.script_payload or {}).get("season", {}).get("key") == "g3.5"
    assert seen and seen[-1]["contract"]["default_route"] == "elsewhere"
    # The page's writer read the contract too: who asks, where, the one ask.
    written_from = provider.director_contexts()[-1]["season_script"]["brief"]["today"]
    assert written_from["contract"]["lead"] == "marin_leveque"
    assert written_from["contract"]["ask"] == "Tell Marin which canapé stays."
    assert "contract_route" in seen[-1]["schema"]["properties"]
    prompt = _resolution(journey)["prompt"]
    # The fake model's own ending («La journée se termine.») is not what the day ends on.
    assert "le menu" in prompt["character_line_fr"] or "un menu" in prompt["character_line_fr"]
    assert "La journée se termine" not in prompt["character_line_fr"]
    ledger = _season_state(db_session, user.id)[day_contract.LEDGER_KEY]
    assert [row["id"] for row in ledger["facts"]] == ["g3.menu"]
    assert ledger["facts"][0]["route"] == "elsewhere"
    assert ledger["marks"]["g3.canape_name"]["kept"] is False
    assert ledger["after"][-1]["text_fr"].startswith("Il y a un menu pour samedi.")
    assert scene.recap_payload["resolution_fr"] == prompt["character_line_fr"]

    # The next day's «Précédemment» ends on what the canapé day changed.
    _play(d, provider, clock, "D'accord.")
    following = _latest_scene(db_session, user.id)
    assert (following.script_payload or {}).get("previously_fr", [])[-1] == ledger["after"][-1]["text_fr"]


@pytest.mark.parametrize("season_on", [False, True], ids=["one-actor", "lanes"], indirect=True)
def test_the_canape_day_keeps_the_name_the_learner_gave(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    provider = season_on
    _reads(provider, monkeypatch, route="named", mark="le petit bateau")
    _d, user, journey = _canape_day(assembled_client, db_session, clock, provider, "Le petit bateau.")

    prompt = _resolution(journey)["prompt"]
    assert "Le petit bateau" in prompt["character_line_fr"] + prompt["summary_native"]
    ledger = _season_state(db_session, user.id)[day_contract.LEDGER_KEY]
    assert ledger["marks"]["g3.canape_name"] == {
        "text": "Le petit bateau", "kept": True, "kind": "name", "day": "g3.5", "comes_back": ["g3.7", "t4"],
        "event_id": ledger["facts"][0]["event_id"],
    }
    assert ledger["facts"][0]["route"] == "named"


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_with_the_flag_off_the_day_ends_as_the_model_wrote_it(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch  # noqa: F811
):
    provider = season_on
    seen = _reads(provider, monkeypatch, route="named", mark="x")
    _d, user, journey = _canape_day(assembled_client, db_session, clock, provider, "Le petit bateau.")

    assert seen and all(row["contract"] is None for row in seen)
    assert "contract" not in provider.director_contexts()[-1]["season_script"]["brief"]["today"]
    assert all("contract_route" not in row["schema"]["properties"] for row in seen)
    assert _resolution(journey)["prompt"]["character_line_fr"] == "La journée se termine."
    assert day_contract.LEDGER_KEY not in _season_state(db_session, user.id)


@pytest.mark.parametrize("season_on", [True], ids=["lanes"], indirect=True)
def test_an_ending_the_guards_refuse_still_lands_on_the_learners_route(
    assembled_client, db_session, journey_enabled, clock, season_on, contract_on, monkeypatch  # noqa: F811
):
    """The story lane read the learner, then its own ending was refused on every
    attempt: the authored fallback closes the lane, and the day still ends on the
    contract, with the name the learner gave."""

    provider = season_on
    _reads(provider, monkeypatch, route="named", mark="Le petit bateau")
    read = provider.generate_chat_completion

    def no_ending(messages, **kwargs):
        response = read(messages, **kwargs)
        if json.loads(messages[0]["content"])["output_schema"]["title"] != "StoryTurn":
            return response
        value = {**json.loads(response.content), "resolution_fr": "", "summary_native": ""}
        return SimpleNamespace(**{**vars(response), "content": json.dumps(value, ensure_ascii=False)})

    monkeypatch.setattr(provider, "generate_chat_completion", no_ending)
    _d, user, journey = _canape_day(assembled_client, db_session, clock, provider, "Le petit bateau.")

    prompt = _resolution(journey)["prompt"]
    assert "Le petit bateau" in prompt["character_line_fr"] + prompt["summary_native"]
    assert "doit partir" not in prompt["character_line_fr"]
    ledger = _season_state(db_session, user.id)[day_contract.LEDGER_KEY]
    assert ledger["facts"][0]["route"] == "named" and ledger["marks"]["g3.canape_name"]["kept"] is True


# --- slice 4: the page is written to the contract ----------------------------------


def _brief_for(premise_day: int, *, band: str = "A1") -> dict:
    from app.services.season import director
    from app.services.season.flags import effective_flags

    season = load_season("s1")
    index = [segment.id for segment in season.segments].index("g3")
    played = [
        {"segment": segment.id, "day_in_segment": day, "event_id": f"{segment.id}.{day}"}
        for segment in season.segments[:index]
        for day in range(1, segment.days + 1)
    ]
    played += [{"segment": "g3", "day_in_segment": day, "event_id": f"g3.{day}"} for day in range(1, premise_day)]
    staged = [{"gap": "g3", "premise": beat.premise} for beat in season.gaps["g3"].days if beat.day < premise_day]
    state = {"id": "s1", "played": played, "premises": staged}
    from datetime import date, timedelta

    pos = season_clock.position(season, state, today=date(2026, 11, 27) + timedelta(days=premise_day))
    assert pos.key == f"g3.{premise_day}"
    return director.gap_brief(season, pos, flags=effective_flags(season, state, seed="x"), state=state, seed="x", band=band)


def test_the_brief_carries_no_contract_with_the_flag_off():
    assert "contract" not in _brief_for(5)["today"]


def test_the_writer_reads_who_asks_where_and_the_one_ask(contract_on):
    today = _brief_for(5)["today"]
    assert today["required_premise"]["id"] == "les_canapes"
    assert today["contract"] == {
        "lead": "marin_leveque",
        "places": ["marin_lila_flat", "le_mistral"],
        "ask": "Tell Marin which canapé stays.",
        "must_hold": ["The party has a menu of three canapés."],
        "routes": [
            "The learner picks one and names it.",
            "The learner picks one and gives no name.",
            "Anything else: a question, a refusal, silence. Marin chooses alone and takes the name from something the learner said.",
        ],
        "hook_fr": "Demain, j'ai besoin de toi. Il manque la photo du milieu.",
    }
    assert _brief_for(5, band="B1")["today"]["contract"]["ask"] == "Tell Marin kindly which canapé to keep and why."


def test_a_page_led_or_set_elsewhere_gets_a_hint_and_an_unbuilt_place_its_second(contract_on):
    plan = _brief_for(5)["today"]["contract"]
    speakers = {"marin_leveque", "lila_bonnet"}
    issue = day_contract.page_issue
    built = {"marin_lila_flat", "le_mistral", "user_apartment"}
    assert issue(plan, lead_id="marin_leveque", location_id="marin_lila_flat", speakers=speakers, places=built) is None
    assert "marin_leveque asks the learner" in issue(
        plan, lead_id="lila_bonnet", location_id="marin_lila_flat", speakers=speakers, places=built
    )
    assert "'marin_lila_flat'" in issue(plan, lead_id="marin_leveque", location_id="le_mistral", speakers=speakers, places=built)
    # «Erst erwähnen, dann betreten»: the flat is not built yet, the page is set at the Mistral.
    unbuilt = {"le_mistral", "user_apartment"}
    assert issue(plan, lead_id="marin_leveque", location_id="le_mistral", speakers=speakers, places=unbuilt) is None
    assert "'le_mistral'" in issue(plan, lead_id="marin_leveque", location_id="user_apartment", speakers=speakers, places=unbuilt)
    # Neither place is built, or the lead may not speak today: the writer chooses.
    assert issue(plan, lead_id="lila_bonnet", location_id="user_apartment", speakers={"lila_bonnet"}, places={"user_apartment"}) is None
    assert issue(None, lead_id="x", location_id="y", speakers=speakers, places=built) is None


def test_the_planner_and_the_director_are_told_only_on_a_contract_day(contract_on):
    from app.services import story_split

    on = {"season_script": {"brief": {"today": _brief_for(5)["today"]}}}
    off = {"season_script": {"brief": {"today": {"beat": {}}}}}
    assert story_split.planner_system(on) == story_split.PLANNER + day_contract.PLANNER_NOTE
    assert story_split.planner_system(off) == story_split.PLANNER
    # A later act of the day is its own scene: no contract.
    assert story_split._day_contract({**on, story_split.ACT_KEY: {"role": "soir"}}) is None
    assert "stops just before it" in day_contract.PLANNER_NOTE and "stops just before it" in day_contract.DIRECTOR_NOTE


def test_the_variety_rule_yields_to_the_contract(contract_on):
    plan = _brief_for(5)["today"]["contract"]
    assert day_contract.follows(plan, lead_id="marin_leveque", location_id="le_mistral") is True
    assert day_contract.follows(plan, lead_id="lila_bonnet", location_id="le_mistral") is False
    assert day_contract.follows(None, lead_id="marin_leveque", location_id="le_mistral") is False


def test_the_critic_reads_the_change_as_certain_on_a_contract_day(contract_on):
    from app.services.season import director

    brief = _brief_for(5)
    draft = {"objective_native": "Sag Marin, welches Canapé bleibt.", "character_id": "marin_leveque", "season_checklist": {}}
    turn = director.critic_payload(brief, draft)["learner_turn"]
    assert turn["guaranteed"] is True and turn["planned_change"] == "The party has a menu of three canapés."
    # A later act of the day is its own scene: nothing is guaranteed there.
    assert "guaranteed" not in director.critic_payload(brief, draft, act={"role": "soir"})["learner_turn"]
    assert "contradicts planned_change" in director.STORY_CRITIC_CONTRACT


def test_the_critic_reads_as_before_with_the_flag_off():
    from app.services.season import director

    turn = director.critic_payload(_brief_for(5), {"season_checklist": {"change_after": "x"}})["learner_turn"]
    assert "guaranteed" not in turn and turn["planned_change"] == "x"
