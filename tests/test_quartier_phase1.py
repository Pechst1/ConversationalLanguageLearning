"""Le Quartier phase 1 (owner decision 2026-10-28, «Go with all five»).

The 3D's first day is the season's own T1 day A: the café crème and the key are
«Le choix» the 2D shows as cards and the 3D hears in French, the key comes back
on day B where it was left, the scene step carries the page as the 3D stages it,
each answer says what it staged, and the gestures that are not answers (walking
out, Margaux's text, a word with anyone in the room) are kept beside the story
and join the season when the day settles.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.schemas.daily_journey import AttemptStage, JourneyChoiceResult, SceneStage
from app.services import living_story as engine
from app.services.cast_registry import display_names
from app.services.season import gestures
from app.services.season.clock import SEASON_KEY
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from app.services.season.runtime import initial_state, projected_turns
from app.services.season.stage import scene_stage, stage_view
from app.services.story_page import episode_page
from tests import test_journey_end_to_end as support
from tests import test_season_one as season_one
from tests import test_season_story_qa as story_qa
from tests.test_living_story_longitudinal import TurnScript

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled
season_on = season_one.season_on
offline = story_qa.offline

SEASON = load_season("s1")
NAMES = display_names(SEASON.cast)
FAMILY = "Odile, c'est ma grand-mère."
SELLING = "Je viens pour vendre. L'appartement est à moi, maintenant."


def _page(day: str = "a", *, band: str = "A2", language: str = "en", **flags):
    base = effective_flags(SEASON, {}, seed="x")
    return resolve_day(SEASON, "t1", day, flags={**base, **flags}, band=band, language=language)


def _ids(rows) -> list[str]:
    return [str(row["id"]) for row in rows]


# ---------------------------------------------------------------------------
# 1. The café crème and the key, in T1 day A
# ---------------------------------------------------------------------------


def _walk(scenario, answers: list[str]) -> list[dict]:
    """Each answer's ``stage``, checked against the wire schema."""

    history: list[dict] = []
    staged = []
    for text in answers:
        evaluation = story_qa._say(scenario, text, history, len(history))
        staged.append(AttemptStage.model_validate(evaluation.stage).model_dump())
        story_qa._record(history, text, evaluation)
    return staged


def test_day_a_asks_the_cafe_and_the_key_in_the_order_the_page_reads():
    page = _page()
    assert _ids(page["movements"]) == ["a.p1", "a.p2", "a.p3", "a.p4", "a.p5", "a.turn1", "a.cafe", "a.turn2", "a.key", "a.hook"]
    turns = projected_turns(page)
    assert _ids(turns) == ["a.turn1", "a.cafe", "a.turn2", "a.key"]
    cafe, key = turns[1], turns[3]
    assert cafe["only_after"] == {"a.turn1": ["a", "c"]} and not key.get("only_after")
    assert [reply["label"] for reply in cafe["replies"]] == ["Merci.", "Non merci.", "Je n'ai rien commandé."]
    assert [reply["label"] for reply in key["replies"]] == ["Je la prends.", "Garde-la pour moi."]
    # The 3D hears them in French: each card has a meaning and other ways to say it.
    assert all(reply["means"] and len(reply["examples"]) >= 2 for turn in (cafe, key) for reply in turn["replies"])


def test_each_answer_stages_its_beats_and_the_question_now_asked(offline):
    staged = _walk(story_qa._scenario(_page()), ["Je m'appelle Vincent.", FAMILY, "Non merci.", "Oui, ce soir.", "Garde-la pour moi."])
    assert [(row["turn_id"], row["reply_id"], _ids(row["beats"]), row["next_turn_id"], row["closing"]) for row in staged] == [
        ("a.turn1", None, ["a.turn1.ask_again"], "a.turn1", False),
        ("a.turn1", "a", ["a.turn1.a.r1", "a.turn1.a.r2"], "a.cafe", False),
        ("a.cafe", "declined", ["a.cafe.declined.r1"], "a.turn2", False),
        ("a.turn2", "tonight", ["a.turn2.tonight.r1"], "a.key", False),
        # On closing, the page's tail under the hook panel's id: the 3D skips it there.
        ("a.key", "leave", ["a.key.leave.r1", "a.p8"], None, True),
    ]
    asked_again = staged[0]["beats"][0]["lines"]
    assert [line["who"] for line in asked_again] == ["augustin_de_roncourt"]
    assert staged[2]["beats"][0]["silence"] is True, "the cup slides to Odile's stool without a word"
    assert [line["text_fr"] for line in staged[4]["beats"][0]["lines"]] == ["Derrière la caisse."]


def test_the_cafe_is_asked_only_once_margaux_has_set_it_down(offline):
    staged = _walk(story_qa._scenario(_page()), [SELLING, "Oui, ce soir.", "Je la prends."])
    assert [(row["turn_id"], row["reply_id"], row["next_turn_id"]) for row in staged] == [
        ("a.turn1", "b", "a.turn2"),
        ("a.turn2", "tonight", "a.key"),
        ("a.key", "take", None),
    ]
    assert staged[-1]["closing"] is True


def test_a_choice_heard_in_french_routes_like_its_card_and_an_unclear_one_is_asked_again(offline):
    staged = _walk(story_qa._scenario(_page()), [FAMILY, "Il pleut beaucoup.", "Merci, c'est gentil.", "Oui, ce soir.", "Tu peux la garder ?"])
    assert [(row["turn_id"], row["reply_id"]) for row in staged] == [
        ("a.turn1", "a"),
        ("a.cafe", None),
        ("a.cafe", "drink"),
        ("a.turn2", "tonight"),
        ("a.key", "leave"),
    ]
    again = staged[1]["beats"][0]
    assert again["id"] == "a.cafe.ask_again"
    assert [(line["who"], line["text_fr"]) for line in again["lines"]] == [
        ("margaux_barman", "Pardon ? Le café crème est pour toi. Tu le prends ?")
    ]


@pytest.mark.parametrize(
    "answers, flags",
    [
        ([FAMILY, "Non merci.", "Oui, ce soir.", "Garde-la pour moi."], {"s1.cafe_creme": "declined", "s1.key_with": "margaux"}),
        ([FAMILY, "Je n'ai rien commandé.", "Oui, ce soir.", "Je la prends."], {"s1.cafe_creme": "refused", "s1.key_with": "toi"}),
        ([SELLING, "Oui, ce soir.", "Garde-la pour moi."], {"s1.cafe_creme": "not_offered", "s1.key_with": "margaux"}),
    ],
    ids=["declined-left", "refused-kept", "never-offered"],
)
def test_the_day_settles_what_was_chosen_and_never_a_cafe_that_was_not_offered(offline, answers, flags):
    from app.services.season.runtime import settle

    scenario = story_qa._scenario(_page())
    history: list[dict] = []
    evaluation = None
    for text in answers:
        evaluation = story_qa._say(scenario, text, history, len(history))
        story_qa._record(history, text, evaluation)
    assert evaluation is not None and evaluation.stage["closing"] is True
    details = dict(evaluation.consequence.details)
    live = {SEASON_KEY: initial_state("s1")}
    after = settle(live, story_context=scenario.story_context, details=details, event_id="e1", date_iso="2026-10-28", day_index=1)
    settled = effective_flags(SEASON, after[SEASON_KEY], seed="x")
    assert {flag: settled[flag] for flag in flags} == flags


# ---------------------------------------------------------------------------
# 2. Day B: the cold cup, and the key where it was left
# ---------------------------------------------------------------------------


def test_day_b_asks_for_the_key_only_when_it_was_left_with_margaux():
    left = _page("b", **{"s1.key_with": "margaux"})
    kept = _page("b", **{"s1.key_with": "toi"})
    assert "b.key" in _ids(left["movements"]) and "b.key" not in _ids(kept["movements"])
    turn = next(row for row in projected_turns(left) if row["id"] == "b.key")
    assert turn["task_native"] == "Ask Margaux for the key you left with her."
    assert {reply["id"]: reply["sets"] for reply in turn["replies"]} == {
        "asks": {"s1.key_with": "toi"},
        "clumsy": {"s1.key_with": "toi"},
        "other": {"s1.key_with": "toi"},
    }, "whatever is said, the learner leaves with their key"


def test_day_b_opens_on_the_cold_cup_only_after_a_no_thank_you():
    assert _ids(_page("b", **{"s1.cafe_creme": "declined"})["movements"])[0] == "b.cup"
    for value in ("drank", "refused", "not_offered"):
        assert "b.cup" not in _ids(_page("b", **{"s1.cafe_creme": value})["movements"])


# ---------------------------------------------------------------------------
# 3. The finished page draws what the learner chose, in their words
# ---------------------------------------------------------------------------


def _finished(routing):
    scene = SimpleNamespace(status="completed", script_payload={"season_page": _page(), "season_routing": routing}, recap_payload={})
    return episode_page(scene, [], NAMES)["rows"]


def test_the_finished_page_draws_the_chosen_card_or_the_learners_own_words():
    rows = _finished(
        [
            {"turn_id": "a.turn1", "reply_id": "a", "learner": FAMILY},
            {"turn_id": "a.cafe", "reply_id": "declined", "learner": "Non merci."},
            {"turn_id": "a.turn2", "reply_id": "tonight", "learner": "Oui, ce soir."},
            {"turn_id": "a.key", "reply_id": "leave", "learner": "Tu peux la garder ?"},
        ]
    )
    solves = {row["id"].split(":")[1]: row for row in rows if row["movement"] == "solve"}
    assert [(line["text_fr"], line["kind"]) for line in solves["a.cafe"]["dialogue"]] == [("Non merci.", "card")]
    assert [(line["text_fr"], line["kind"]) for line in solves["a.key"]["dialogue"]] == [("Tu peux la garder ?", "you")]
    reactions = [row["id"].split(":")[1] for row in rows if row["movement"] == "reaction"]
    assert "a.cafe.declined.r1" in reactions and "a.key.leave.r1" in reactions
    assert "a.cafe.drink.r1" not in reactions


def test_the_finished_page_leaves_out_the_question_the_day_passed_over():
    rows = _finished(
        [
            {"turn_id": "a.turn1", "reply_id": "b", "learner": SELLING},
            {"turn_id": "a.turn2", "reply_id": "tonight", "learner": "Oui, ce soir."},
            {"turn_id": "a.key", "reply_id": "take", "learner": "Je la prends."},
        ]
    )
    drawn = [row["id"].split(":")[1] for row in rows]
    assert "a.cafe" not in drawn and not any(panel.startswith("a.cafe.") for panel in drawn)
    assert "a.key" in drawn


# ---------------------------------------------------------------------------
# 4. The stage on the scene step
# ---------------------------------------------------------------------------


def _stage(page=None) -> dict:
    stage = scene_stage({"season_page": page or _page(), "season": {"day_in_segment": "a"}})
    assert stage is not None
    return SceneStage.model_validate(stage).model_dump(by_alias=True)


def test_the_stage_is_the_page_movement_by_movement_with_the_days_gestures():
    stage = _stage()
    assert (stage["key"], stage["number"], stage["band"], stage["language"]) == ("t1.a", 1, "A2", "en")
    assert stage["title_fr"] == "Le mauvais accueil" and stage["can_do_native"]
    movements = stage["movements"]
    assert [(row["kind"], row["id"]) for row in movements] == [
        *[("panel", f"a.p{n}") for n in range(1, 6)],
        ("turn", "a.turn1"),
        ("turn", "a.cafe"),
        ("turn", "a.turn2"),
        ("turn", "a.key"),
        ("hook", "a.hook"),
    ]
    turns = {row["id"]: row for row in movements if row["kind"] == "turn"}
    assert turns["a.turn1"]["choice"] is False and turns["a.turn1"]["to_name"] == "Gus"
    cafe = turns["a.cafe"]
    assert (cafe["choice"], cafe["to"], cafe["to_name"], cafe["only_after"]) == (True, "margaux_barman", "Margaux", {"a.turn1": ["a", "c"]})
    # Margaux asks it herself in the 3D (the 2D prints it as the cards' caption).
    assert [(line["who"], line["kind"], line["text_fr"]) for line in cafe["panel"]["lines"]] == [
        ("margaux_barman", "speech", "Le café crème est pour toi. Tu le prends ?")
    ]
    assert cafe["panel"]["in_frame"] == ["margaux_barman"]
    hook = movements[-1]
    assert hook["panel"]["id"] == "a.p8", "the closing beats' tail carries the same id"
    assert any(line["kind"] == "caption" and "suivre" in line["text_fr"] for line in hook["panel"]["lines"]), "the hook panel is whole"


def test_the_stage_offers_walking_out_margauxs_text_and_talk_to_everyone_in_the_room():
    storylets = {row["id"]: row for row in _stage()["storylets"]}
    assert list(storylets) == ["walk_out", "margaux_text", "talk"]
    walk = storylets["walk_out"]
    assert walk["cue"] == "walk_out" and [(line["id"], line["role"], line["during"]) for line in walk["lines"]] == [
        ("walk_out.asked", "asked", None),
        ("walk_out.back.gus", "back", "a.p2"),
        ("walk_out.back", "back", None),
    ]
    text = storylets["margaux_text"]
    assert (text["cue"], text["after_seconds"], text["chips"]) == ("away", 40, ["J'arrive.", "Merci. J'arrive.", "Demain."])
    assert [(line["role"], line["kind"], line["from_fr"]) for line in text["lines"]] == [("text", "sms", "Numéro inconnu"), ("answer", "sms", "Margaux")]
    people = storylets["talk"]["people"]
    assert [(row["who"], row["name"], row["register"]) for row in people] == [
        ("margaux_barman", "Margaux", "tu"),
        ("augustin_de_roncourt", "Gus", "vous"),
        ("marin_leveque", "Marin", "tu"),
        ("lila_bonnet", "Lila", "tu"),
        ("camille_marchand", "Camille", "vous"),
    ]
    assert all(row["hello"] and row["hello"]["text_fr"] for row in people)
    assert next(row for row in people if row["who"] == "lila_bonnet")["bye"]["text_fr"] == "Allez, file."


def test_a1_lines_carry_their_translation_and_b1_lines_none():
    a1 = scene_stage({"season_page": _page(band="A1", language="de")})
    b1 = scene_stage({"season_page": _page(band="B1", language="de")})
    lines = [line for row in a1["movements"] if row["kind"] == "panel" for line in row["lines"]]
    assert lines and all(line["text_native"] for line in lines if line["kind"] != "caption" or line["text_fr"] != "À suivre…")
    assert not any(line["text_native"] for row in b1["movements"] if row["kind"] == "panel" for line in row["lines"])


def test_day_b_and_a_day_off_the_season_stage_no_gestures():
    stage = scene_stage({"season_page": _page("b", **{"s1.key_with": "margaux"})})
    assert stage["key"] == "t1.b" and stage["storylets"] == []
    assert "b.key" in _ids(stage["movements"])
    assert scene_stage({}) is None and scene_stage({"season_page": {"movements": []}}) is None
    assert stage_view(None) is None


def test_the_gestures_file_holds_against_the_season():
    assert gestures.validate_quartier(SEASON) == []


# ---------------------------------------------------------------------------
# 5. Gestures: walking out, Margaux's text, a word with anyone in the room
# ---------------------------------------------------------------------------


def _gesture(state: dict, storylet_id: str, *, to: str | None = None, text: str | None = None, at: str | None = None, routes=None, journey_id="j1"):
    result, after = gestures.answer(
        None,
        None,
        day=gestures.day_for("s1", "t1.a"),
        state=state,
        journey_id=journey_id,
        scene_id="scene-1",
        storylet_id=storylet_id,
        at=at,
        to=to,
        text=text,
        band="A2",
        language="en",
        names=NAMES,
        season_flags=effective_flags(SEASON, {}, seed="x"),
        routes=routes or {},
        use_model=False,
    )
    return JourneyChoiceResult.model_validate(result).model_dump(by_alias=True), after


@pytest.fixture
def matcher():
    from app.services.season import runtime

    runtime._ROUTE_CACHE.clear()
    yield
    runtime._ROUTE_CACHE.clear()


def test_walking_out_is_answered_on_the_way_back_and_kept_for_the_season(matcher):
    during, state = _gesture({}, "walk_out", at="a.p2")
    assert [(beat["id"], beat["lines"][0]["who"]) for beat in during["beats"]] == [("walk_out.back.gus", "augustin_de_roncourt")]
    assert during["sets"] == {"user.walked_out": True}
    assert state["pending"] == {"user.walked_out": True}
    later, _ = _gesture(state, "walk_out", at="a.p5")
    assert [(beat["id"], beat["lines"][0]["text_fr"]) for beat in later["beats"]] == [("walk_out.back", "Te revoilà.")]


def test_margauxs_text_comes_and_answers_what_the_learner_writes(matcher):
    text, state = _gesture({}, "margaux_text")
    assert [(beat["id"], beat["lines"][0]["kind"], beat["lines"][0]["text_fr"]) for beat in text["beats"]] == [
        ("margaux_text.text", "sms", "C'est Margaux. Ta valise est toujours là.")
    ]
    answered, state = _gesture(state, "margaux_text", text="J'arrive.")
    assert [(beat["id"], beat["lines"][0]["text_fr"]) for beat in answered["beats"]] == [("margaux_text.answer", "Bon.")]
    assert state["pending"] == {"user.stayed_away": True}


def test_talk_with_no_words_is_the_hello_the_day_has_earned(matcher):
    hello, _ = _gesture({}, "talk", to="marin_leveque")
    assert _ids(hello["beats"]) == ["talk.marin.hello"]
    family, _ = _gesture({}, "talk", to="marin_leveque", routes={"a.turn1": "a"})
    assert _ids(family["beats"]) == ["talk.marin.family"]
    key, _ = _gesture({}, "talk", to="margaux_barman", routes={"a.key": "leave"})
    assert [line["text_fr"] for beat in key["beats"] for line in beat["lines"]] == ["Elle est derrière la caisse."]
    assert [(row["who"], row["register"]) for row in key["people"]][:2] == [("margaux_barman", "tu"), ("augustin_de_roncourt", "vous")]


def test_a_line_heard_plays_teaches_and_opens_the_next(matcher):
    told, state = _gesture({}, "talk", to="margaux_barman", text="Tu connaissais bien Odile ?")
    assert told["heard"] == "margaux.odile" and _ids(told["beats"]) == ["talk.margaux.odile"]
    assert [row["id"] for row in told["learned"]] == ["margaux.odile"] and told["learned"][0]["text_fr"]
    assert "Pourquoi elle est partie ?" in told["chips"], "what she told opens the next question"
    assert "Tu connaissais bien Odile ?" not in told["chips"]
    why, state = _gesture(state, "talk", to="margaux_barman", text="Pourquoi elle est partie ?")
    assert why["heard"] == "margaux.why_left"
    # What Margaux told is known all day, to everyone: Lila reacts to it.
    lila, _ = _gesture(state, "talk", to="lila_bonnet", text="Margaux m'a parlé d'Odile.")
    assert lila["heard"] == "lila.margaux_spoke"
    assert set(state["learned"]) == {"margaux.odile", "margaux.wont_say"}


def test_a_slip_of_register_is_answered_once_a_day(matcher):
    first, state = _gesture({}, "talk", to="augustin_de_roncourt", text="Tu viens souvent ici ?")
    assert _ids(first["beats"])[0] == "talk.augustin_de_roncourt.slip"
    second, state = _gesture(state, "talk", to="augustin_de_roncourt", text="Tu es élégant.")
    assert "talk.augustin_de_roncourt.slip" not in _ids(second["beats"])
    # The next day may slip again.
    tomorrow, _ = _gesture(state, "talk", to="augustin_de_roncourt", text="Tu es élégant.", journey_id="j2")
    assert _ids(tomorrow["beats"])[0] == "talk.augustin_de_roncourt.slip"
    polite, _ = _gesture({}, "talk", to="augustin_de_roncourt", text="Vous venez souvent ici ?")
    assert _ids(polite["beats"]) == ["talk.gus.zinc"]


def test_what_is_not_heard_gets_the_persons_own_fallback_in_turn(matcher):
    first, state = _gesture({}, "talk", to="camille_marchand", text="Le chat est noir.")
    assert first["heard"] is None and _ids(first["beats"]) == ["talk.camille_marchand.fallback"]
    english, state = _gesture(state, "talk", to="marin_leveque", text="I really like this place")
    assert _ids(english["beats"]) == ["talk.marin_leveque.fallback"]
    one, state = _gesture(state, "talk", to="margaux_barman", text="Le chat est noir.")
    two, state = _gesture(state, "talk", to="margaux_barman", text="Le chien est blanc.")
    assert [beat["lines"][0]["text_fr"] for beat in (*one["beats"], *two["beats"])] == ["Hm. Redis ?", "Plus simple. Je suis fatiguée."]


def test_a_line_that_plays_once_is_not_offered_again(matcher):
    first, state = _gesture({}, "talk", to="marin_leveque", text="Elle sent bon, ta soupe.")
    assert first["heard"] == "marin.soup" and "Elle sent bon, ta soupe." not in first["chips"]
    again, state = _gesture(state, "talk", to="marin_leveque", text="Elle sent bon, ta soupe.")
    assert again["heard"] != "marin.soup"
    hello, _ = _gesture(state, "talk", to="marin_leveque")
    assert _ids(hello["beats"]) == ["talk.marin.fed"]


def test_a_gesture_the_day_does_not_have_is_refused(matcher):
    with pytest.raises(gestures.GestureRefused):
        _gesture({}, "dance")
    with pytest.raises(gestures.GestureRefused):
        _gesture({}, "talk", to="odile")


def test_register_of_reads_tu_and_vous():
    assert gestures.register_of("Vous venez souvent ici ?") == "vous"
    assert gestures.register_of("Tu viens souvent ici ?") == "tu"
    assert gestures.register_of("T'es d'ici ?") == "tu"
    assert gestures.register_of("Bonsoir.") is None
    assert gestures.register_of("Tu sais, vous êtes gentils.") is None


# ---------------------------------------------------------------------------
# 6. Kept beside the story; joins the season at the settle
# ---------------------------------------------------------------------------


def test_gestures_join_the_season_when_the_day_settles():
    state = {"quartier": {"pending": {"user.walked_out": True, "user.stayed_away": True}, "learned": ["margaux.odile"]}}
    live = {SEASON_KEY: initial_state("s1")}
    gestures.fold_into_season(state, live)
    flags = effective_flags(SEASON, live[SEASON_KEY], seed="x")
    assert flags["user.walked_out"] is True and flags["user.stayed_away"] is True
    assert state["quartier"] == {"pending": {}, "learned": ["margaux.odile"]}
    # Nothing waits, or no season: nothing changes.
    untouched = {"quartier": {"pending": {}}}
    gestures.fold_into_season(untouched, live)
    assert untouched == {"quartier": {"pending": {}}}
    no_season: dict = {}
    gestures.fold_into_season({"quartier": {"pending": {"user.walked_out": True}}}, no_season)
    assert no_season == {}


def test_a_gesture_mid_day_never_makes_the_days_page_stale():
    assert gestures.STATE_KEY in engine.FINGERPRINT_IGNORED_STATE_KEYS
    thread = SimpleNamespace(id=uuid.uuid4(), state={"living_story": {"day": 1}}, current_episode_index=0, world_bible={})
    before = engine._fingerprint(thread)
    thread.state = {**thread.state, "quartier": {"pending": {"user.walked_out": True}, "log": [{"storylet": "walk_out"}]}}
    assert engine._fingerprint(thread) == before


# ---------------------------------------------------------------------------
# 7. The gate: T1 day A in the 3D, then T1 day B in the 2D
# ---------------------------------------------------------------------------


def _choose(d, body: dict, *, mutation_id: str | None = None):
    return d.client.post(
        f"/api/v1/daily-journeys/{d.id}/choices",
        headers=d.headers,
        json={"mutation_id": mutation_id or support.key(), **body},
    )


def _play_day(d, answer, *, before_turn=None) -> list[dict]:
    """The day, step by step: each respond answer's ``AttemptResult``. ``answer``
    reads the respond step (its cards); ``before_turn(n)`` runs before answer n."""

    results: list[dict] = []
    for _ in range(80):
        step = d.current()
        if step is None:
            break
        if step["kind"] == "recall":
            assert d.attempt(d.recall_answer(step, correct=True)).status_code == 200
            if d.journey.get("current_step_id") == step["id"]:
                d.advance()
            continue
        if step["kind"] != "respond":
            d.advance()
            continue
        if before_turn:
            before_turn(len(results))
        response = d.attempt({"mode": "text", "text": answer(step)})
        assert response.status_code == 200, response.text
        body = response.json()
        results.append(body)
        if not body.get("next_turn") and d.journey.get("current_step_id") == step["id"]:
            d.advance()
    return results


def test_t1_day_a_in_the_3d_then_day_b_in_the_2d_finds_the_key_where_it_was_left(
    assembled_client, db_session, journey_enabled, clock, season_on
):
    provider = season_on
    provider.routes = {
        FAMILY: "a",
        "Oui. Ce soir.": "tonight",
        "Ma clé, s'il te plaît.": "asks",
        "Tu connaissais bien Odile ?": "margaux.odile",
    }
    provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d = support.Driver(assembled_client, support.register(assembled_client, f"q1-{uuid.uuid4()}@example.com", cefr="A2.1"), db=db_session)

    # Day A, in the 3D: the scene step carries the stage.
    d.create()
    scene = support.step_of(d.journey, "scene")
    stage = scene["prompt"]["stage"]
    assert stage["key"] == "t1.a" and _ids(stage["movements"])[5:9] == ["a.turn1", "a.cafe", "a.turn2", "a.key"]
    assert _ids(stage["storylets"]) == ["walk_out", "margaux_text", "talk"]

    # The learner walks out during Gus's story and comes back.
    walked = _choose(d, {"storylet_id": "walk_out", "at": "a.p2"})
    assert walked.status_code == 200, walked.text
    assert _ids(walked.json()["beats"]) == ["walk_out.back.gus"]
    # The same gesture sent twice (a retry) is answered once.
    retry_id = support.key()
    first = _choose(d, {"storylet_id": "talk", "to": "lila_bonnet"}, mutation_id=retry_id)
    again = _choose(d, {"storylet_id": "talk", "to": "lila_bonnet"}, mutation_id=retry_id)
    assert first.status_code == again.status_code == 200 and first.json() == again.json()
    refused = _choose(d, {"storylet_id": "talk", "to": "odile"})
    assert refused.status_code == 409, refused.text

    answers = iter([FAMILY, "Non merci.", "Oui. Ce soir.", "Garde-la pour moi."])
    talked: list[dict] = []

    def between(n: int) -> None:
        if n == 2:  # after the café: a word with Margaux, who now holds the cup back
            response = _choose(d, {"storylet_id": "talk", "to": "margaux_barman", "text": "Tu connaissais bien Odile ?"})
            assert response.status_code == 200, response.text
            talked.append(response.json())

    results = _play_day(d, lambda step: next(answers), before_turn=between)
    staged = [row["stage"] for row in results]
    assert [(row["turn_id"], row["reply_id"], row["next_turn_id"]) for row in staged] == [
        ("a.turn1", "a", "a.cafe"),
        ("a.cafe", "declined", "a.turn2"),
        ("a.turn2", "tonight", "a.key"),
        ("a.key", "leave", None),
    ]
    assert staged[-1]["closing"] is True and _ids(staged[-1]["beats"])[-1] == "a.p8"
    # The 2D shows the café and the key as cards.
    cards = [[card["label_fr"] for card in row["next_turn"]["prompt"]["choices"]] for row in results[:3]]
    assert cards == [["Merci.", "Non merci.", "Je n'ai rien commandé."], [], ["Je la prends.", "Garde-la pour moi."]]
    assert talked and talked[0]["heard"] == "margaux.odile"
    assert d.finish("complete").status_code == 200

    # The walk after the end card is where most talk happens.
    after = _choose(d, {"storylet_id": "talk", "to": "margaux_barman"})
    assert after.status_code == 200, after.text
    assert [line["text_fr"] for beat in after.json()["beats"] for line in beat["lines"]] == ["Elle est derrière la caisse."]

    user_id = season_one._user_id_of(db_session, d.journey)
    flags = effective_flags(SEASON, season_one._season_state(db_session, user_id), seed=str(user_id))
    assert (flags["s1.cafe_creme"], flags["s1.key_with"], flags["user.walked_out"]) == ("declined", "margaux", True)

    # Day B, in the 2D: the cold cup, and the key asked for where it was left.
    clock.advance(days=1)
    d.create()
    stage_b = support.step_of(d.journey, "scene")["prompt"]["stage"]
    assert stage_b["key"] == "t1.b" and stage_b["storylets"] == []
    assert _ids(stage_b["movements"])[0] == "b.cup" and "b.key" in _ids(stage_b["movements"])
    assert _choose(d, {"storylet_id": "walk_out"}).status_code == 409, "day B has no gestures yet"

    asked: list[str] = []

    def day_b(step: dict) -> str:
        prompt = step["prompt"]
        asked.append(prompt["objective_native"])
        if prompt["choices"]:
            return prompt["choices"][0]["label_fr"]
        if prompt["objective_native"] == "Ask Margaux for the key you left with her.":
            return "Ma clé, s'il te plaît."
        return FAMILY

    results_b = _play_day(d, day_b)
    assert "Ask Margaux for the key you left with her." in asked
    key_turn = next(row["stage"] for row in results_b if row["stage"]["turn_id"] == "b.key")
    # The day's last question: Margaux gives the key back, then the page's tail plays.
    assert key_turn["reply_id"] == "asks" and _ids(key_turn["beats"])[0] == "b.key.asks.r1"
    assert key_turn["closing"] is True
    assert d.finish("complete").status_code == 200
    flags_b = effective_flags(SEASON, season_one._season_state(db_session, user_id), seed=str(user_id))
    assert flags_b["s1.key_with"] == "toi"
