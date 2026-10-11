"""QA-STORY (2026-10-03): the owner played T1 day A as an A1 learner reading German.

Regressions pinned here:

1. an A1 line is shown with its *own* translation, never the A2 line's — and the
   word drills cut from the scene read the same (French, translation) pair;
3. a reply that expresses none of the routes («Je m'appelle Vincent.») is asked
   again once, in character, with the learner's own name; only a second unclear
   reply takes the turn's fallback — nothing the learner did not say is assumed;
4. each next question brings its own task line (and hint);
5. Camille Marchand is named Camille, never «M. Marchand»;
6. the route an exchange took is kept with it, so a replay never re-reads it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.season import runtime
from app.services.season.flags import effective_flags
from app.services.season.format import load_season
from app.services.season.levels import iter_says
from app.services.season.page import resolve_day
from app.services.season.runtime import (
    ASK_AGAIN,
    SEASON_CONTEXT_KEY,
    evaluate_tentpole_turn,
    page_tail,
    projected_turns,
)
from app.services.season.turns import _short, learner_name, match_reply


def _page(tentpole="t1", day="a", band="A1", language="de"):
    season = load_season("s1")
    flags = effective_flags(season, {}, seed="x")
    return resolve_day(season, tentpole, day, flags=flags, band=band, language=language)


def _lines(node):
    if isinstance(node, dict):
        if "text_fr" in node and "who" in node:
            yield node
        for value in node.values():
            yield from _lines(value)
    elif isinstance(node, list):
        for value in node:
            yield from _lines(value)


# ---------------------------------------------------------------------------
# 1. An A1 line reads its own translation
# ---------------------------------------------------------------------------


def test_day_one_at_a1_shows_each_line_with_its_own_translation():
    season = load_season("s1")
    own = {}
    for tentpole in season.tentpoles.values():
        for say in iter_says(tentpole.model_dump()):
            a1 = say.get("a1")
            if a1 and " ".join(a1.split()) != " ".join(say["a2"].split()):
                own[a1] = say
    page = _page()
    checked = 0
    for line in _lines(page["movements"]):
        say = own.get(line["text_fr"])
        if say is None:
            continue
        checked += 1
        assert line["text_native"] == say["native_a1"]["de"], line["text_fr"]
    assert checked >= 10
    # The line the owner met: Margaux sets down Odile's usual coffee.
    texts = {line["text_fr"]: line["text_native"] for line in _lines(page["movements"])}
    assert "C'est son café." not in texts
    assert "Bravo, Gus. Sept sur vingt." not in texts
    assert "Das hat sie immer genommen." not in texts.values()


def test_every_a1_variant_that_differs_from_a2_carries_en_and_de():
    season = load_season("s1")
    missing = []
    for tentpole in season.tentpoles.values():
        for say in iter_says(tentpole.model_dump()):
            a1 = say.get("a1")
            if a1 and " ".join(a1.split()) != " ".join(say["a2"].split()):
                native = say.get("native_a1") or {}
                if not (native.get("en") and native.get("de")):
                    missing.append(a1)
    assert not missing, missing[:5]


def test_a_b1_learner_reads_no_translation_and_an_a2_learner_the_a2_one():
    b1 = _page(band="B1", language="en")
    assert all(line["text_native"] is None for line in _lines(b1["movements"]))
    a2 = _page(band="A2", language="de")
    first = a2["movements"][0]["lines"][0]
    assert first["text_native"].startswith("Paris. Der 11. November")


def test_scene_drills_read_the_served_pair():
    """The unscramble / «Wer hat das gesagt?» drills take (text_fr, translation) from
    the published draft, which is built from the page: the same A1 pair."""

    from app.services.scene_items import line_meanings

    page = _page()
    turns = projected_turns(page)
    today = SimpleNamespace(
        season=load_season("s1"),
        language="de",
        band="A1",
        pos=SimpleNamespace(key="t1:a", tentpole_day="a", is_tentpole=True),
    )
    draft = runtime.authored_draft(today, page, turns)
    draft.pop("_ending", None)
    scenario = SimpleNamespace(story_context={"draft": draft})
    meanings = line_meanings(scenario)
    assert meanings, "the drills have translated lines to cut from"
    served = {line["text_fr"]: line["text_native"] for line in _lines(page["movements"]) if line.get("text_native")}
    for french, native in meanings.items():
        if french in served:
            assert served[french] == native, french
    # The opening question («Alors ? …») and its translation are one pair too.
    opening = projected_turns(page)[0]["panel"]["lines"][0]
    assert meanings[opening["text_fr"]] == opening["text_native"]


# ---------------------------------------------------------------------------
# 3, 4, 6. Off-target replies, the task per question, the kept route
# ---------------------------------------------------------------------------


@pytest.fixture
def offline(monkeypatch):
    """The deterministic matcher reads every reply (no model), no margin correction."""

    real = runtime.classify

    def classify(db, user, **kwargs):
        kwargs["use_model"] = False
        return real(db, user, **kwargs)

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    import app.services.living_story as engine

    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield


def _scenario(page):
    turns = projected_turns(page)
    return SimpleNamespace(
        story_context={
            "scene_id": "qa-story",
            SEASON_CONTEXT_KEY: {
                "id": "s1",
                "kind": "tentpole",
                "page": page,
                "turns": turns,
                "tail": page_tail(page),
                "ending": {},
                "position": {"key": "t1:a"},
            },
        },
        character_id="augustin_de_roncourt",
        title_fr=page["title_fr"],
    )


def _say(scenario, text, history, turn_index):
    return evaluate_tentpole_turn(
        None,
        user=None,
        scenario=scenario,
        task=SimpleNamespace(max_turns=6),
        answer=SimpleNamespace(text=text, is_blank=False),
        turn_index=turn_index,
        assistance="none",
        history=history,
    )


def _record(history, text, evaluation):
    history.append(
        {
            "learner": text,
            "character": evaluation.character_reply_fr,
            "free": bool(evaluation.needs_repair and not evaluation.turn_consumed),
            **({"route": dict(evaluation.route)} if evaluation.route else {}),
        }
    )


def test_only_a_name_is_asked_again_in_character_never_routed_as_family(offline):
    page = _page()
    scenario = _scenario(page)
    history: list[dict] = []
    first = _say(scenario, "Je m'appelle Vincent.", history, 0)
    assert first.turn_consumed is False and first.needs_repair is True
    assert first.route == {"turn": "a.turn1", "reply": ASK_AGAIN}
    assert "Vincent" in first.character_reply_fr
    said = " ".join(line["text_fr"] for line in first.reply_lines)
    assert "café" not in said and "famille" not in said.casefold(), "nothing the learner did not say"
    assert [line["speaker_id"] for line in first.reply_lines] == ["augustin_de_roncourt"]
    assert first.next_task_native == "Sag, wer du bist und warum du hier bist."
    _record(history, "Je m'appelle Vincent.", first)

    # A second unclear reply is not asked a third time: the turn's fallback route.
    second = _say(scenario, "Il pleut beaucoup.", history, 0)
    assert second.route["turn"] == "a.turn1" and second.route["reply"] != ASK_AGAIN
    assert second.turn_consumed is True


def test_a_clear_reply_routes_at_once(offline):
    scenario = _scenario(_page())
    evaluation = _say(scenario, "Odile est ma grand-mère.", [], 0)
    assert evaluation.route == {"turn": "a.turn1", "reply": "a"}
    assert evaluation.turn_consumed is True


def test_the_next_question_brings_its_own_task_and_hint(offline):
    scenario = _scenario(_page())
    evaluation = _say(scenario, "Odile est ma grand-mère.", [], 0)
    turn2 = projected_turns(_page())[1]
    assert evaluation.next_task_native == turn2["task_native"]
    assert "hochgehst" in evaluation.next_task_native
    assert "Urteil" not in (evaluation.next_task_native or "")
    assert evaluation.next_hint_native and evaluation.next_hint_native.startswith("Zum Beispiel")
    assert evaluation.next_suggested_fr in [ex for reply in turn2["replies"] for ex in reply["examples"]]


def test_a_replay_follows_the_kept_route_not_a_new_reading(offline):
    scenario = _scenario(_page())
    # The route says «b» although the matcher would read the words otherwise.
    history = [{"learner": "Bonsoir.", "character": "…", "free": False, "route": {"turn": "a.turn1", "reply": "b"}}]
    evaluation = _say(scenario, "Oui, ce soir.", history, 1)
    assert evaluation.route["turn"] == "a.turn2"


def test_every_tentpole_turn_has_a_plain_task_and_an_ask_again_decision():
    season = load_season("s1")
    for tentpole in season.tentpoles.values():
        for day in tentpole.days:
            page = resolve_day(season, tentpole.id, day.day, flags=effective_flags(season, {}, seed="x"), band="A1", language="de")
            if page is None:
                continue
            for movement in page["movements"]:
                if movement.get("kind") in ("turn", "solve"):
                    task = movement["task_native"]
                    assert task and len(task) < 160, (tentpole.id, movement["id"], task)


def test_names_and_learner_names():
    assert _short("Camille Marchand", "camille_marchand") == "Camille"
    assert _short("M. Marchand", "landlord_marchand") == "M. Marchand"
    assert learner_name("Je m'appelle Vincent.") == "Vincent"
    assert learner_name("je suis la famille d'Odile") is None
    assert learner_name("Je suis Odile", not_names={"Odile"}) is None


def test_the_matcher_never_claims_a_route_it_did_not_hear():
    page = _page()
    turn = projected_turns(page)[0]
    _reply_id, score = match_reply(turn, "Je m'appelle Vincent.")
    assert score < runtime.MATCH_THRESHOLD
