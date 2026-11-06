"""Walk 6 Nov (#556, #378, #535): the scene keeps what was answered.

Gus asked «Tu mets les photos au mur. Tu sais ça ?» (Nº 24, T4 day B). The learner
answered «Oui, je savais. Ma grand-mère elle a laissé le Mistral à moi, mais je suis
pas sûr de le garder.» Gus paraphrased it correctly and then said his authored
«Réponds ! Tu sais ça, oui ou non ?» as if nothing had been answered.

Why the code allowed it: «did the learner answer?» was a vocabulary-overlap test
(``answers_question``) against the words of the question. A yes/no question is answered
by «oui» / «non» / «je savais», words that are not in the question («sais» and «savais»
are two stems), so a plain yes was read as «answered nothing» and asked again. The
overlap test could only see topic words, never the answer's polarity.

#535: the «One line to say aloud» was «LARTSIM», the label of a card (a story prop, the
reversed neon sign). ``routed_sentence`` took the routed reply's first example as the
sentence the learner said, though for a tap card that example is the card's label.
"""

from __future__ import annotations

import pytest

from app.services.season import runtime
from app.services.season.runtime import ASK_AGAIN
from app.services.season.turns import ReplyChoice, answers_question
from tests.test_season_story_qa import _record, _say, _scenario

LEARNER = "Oui, je savais. Ma grand-mère elle a laissé le Mistral à moi, mais je suis pas sûr de le garder."
GUS_ACK = "Tu savais pour le Mistral, mais tu hésites à le garder."


@pytest.fixture
def reading(monkeypatch):
    state = type("Reading", (), {"choice": None})()

    def classify(db, user, **kwargs):
        return state.choice

    monkeypatch.setattr(runtime, "classify", classify)
    import app.services.living_story as engine
    import app.services.story_lanes as lanes

    monkeypatch.setattr(lanes, "margin_correction", lambda *a, **k: None)
    monkeypatch.setattr(engine, "story_revision", lambda *a, **k: "rev")
    runtime._ROUTE_CACHE.clear()
    yield state


def _t4b():
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, "t4", "b", flags=effective_flags(season, {}, seed="x"), band="A1", language="en")
    scenario = _scenario(page)
    return scenario, scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]


def test_a_yes_to_gus_question_is_not_asked_again(reading):
    scenario, turns = _t4b()
    turn = turns[0]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.3, clear=False, ack_fr=GUS_ACK)
    evaluation = _say(scenario, LEARNER, [], 0)
    said = " ".join(line["text_fr"] for line in evaluation.reply_lines)
    assert evaluation.route["reply"] != ASK_AGAIN, f"Gus re-asked an answered question: {said!r}"
    assert evaluation.turn_consumed is True
    assert "oui ou non" not in said.casefold()
    assert GUS_ACK in said, "the paraphrase of the answer is kept"


@pytest.mark.parametrize(
    "text",
    [
        "Oui, je savais.",
        "Non, je ne savais pas.",
        "Non ! Je savais pas, moi.",
        "Oui. Elle me l'a dit hier.",
        "Bien sûr que je le savais.",
        "Évidemment, je sais.",
    ],
)
def test_a_polar_answer_answers_a_polar_question(text):
    _, turns = _t4b()
    assert answers_question(turns[0], text), text


@pytest.mark.parametrize(
    "text", ["Je m'appelle Vincent.", "Bonjour !", "Il pleut beaucoup.", "Oui ? Pourquoi tu demandes ça ?", "Oui"]
)
def test_what_does_not_answer_is_still_asked_again(reading, text):
    scenario, turns = _t4b()
    turn = turns[0]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.2, clear=False)
    evaluation = _say(scenario, text, [], 0)
    # A bare «Oui» answers a yes/no question; the others do not.
    if text == "Oui":
        assert evaluation.route["reply"] != ASK_AGAIN
    else:
        assert evaluation.route == {"turn": turn["id"], "reply": ASK_AGAIN}


def test_every_authored_yes_no_question_takes_a_yes_and_a_no():
    """The guard behind the walk: no authored page can re-ask a polar question that the
    learner has just answered with oui / non (the structure, not one turn)."""

    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day
    from app.services.season.turns import is_polar_question

    season = load_season("s1")
    seen = 0
    for tentpole in ("t1", "t2", "t3", "t4", "t5", "t6"):
        for day in ("a", "b"):
            try:
                page = resolve_day(
                    season, tentpole, day, flags=effective_flags(season, {}, seed="x"), band="A1", language="en"
                )
            except Exception:  # noqa: BLE001, S112 - a tentpole the season does not have
                continue
            for turn in _scenario(page).story_context[runtime.SEASON_CONTEXT_KEY]["turns"]:
                if not is_polar_question(turn):
                    continue
                seen += 1
                assert answers_question(turn, "Oui, c'est vrai."), (tentpole, day, turn.get("id"))
                assert answers_question(turn, "Non, pas du tout."), (tentpole, day, turn.get("id"))
    assert seen >= 3, "the sweep found the season's yes/no questions"


# ---------------------------------------------------------------------------
# #535: «One line to say aloud» is a sentence of the learner's, never a card label
# ---------------------------------------------------------------------------

WALK_5_NOV = "Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sais pas. Margaux a raison."
WALK_5_NOV_CORRECTED = "Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sait pas. Margaux a raison."


def _t4a():
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, "t4", "a", flags=effective_flags(season, {}, seed="x"), band="A1", language="en")
    scenario = _scenario(page)
    return scenario, scenario.story_context[runtime.SEASON_CONTEXT_KEY]["turns"]


def _line_to_say(history, correction=None):
    from types import SimpleNamespace

    from app.services import spoken_reply

    turns = [dict(row) for row in history]
    if correction:
        turns[-1]["correction"] = {"corrected_fr": correction}
    step = SimpleNamespace(private_task={"turns": turns, "response_task": {}})
    return spoken_reply.repeat_line_for(step)


def test_a_card_label_is_never_the_line_to_say_aloud(reading, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    scenario, turns = _t4a()
    turn = turns[0]
    assert turn["id"] == "a.enquete" and turn["replies"][0]["examples"] == ["LARTSIM"]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(reply_id="neon", confidence=0.9, clear=True)
    history: list[dict] = []
    evaluation = _say(scenario, WALK_5_NOV, history, 0)
    _record(history, WALK_5_NOV, evaluation)
    assert evaluation.route["reply"] == "neon"
    assert evaluation.route.get("say_fr") != "LARTSIM", "the neon's label is a story prop, not a sentence"
    line = _line_to_say(history, WALK_5_NOV_CORRECTED)
    assert line == WALK_5_NOV_CORRECTED, f"the recap offers {line!r} to say aloud"


def test_a_tapped_choice_card_is_still_the_line_to_say():
    """The cards of «Le choix» are sentences to say («Pas encore»); only the tap targets
    of a clue (a neon sign, a pan) are not."""

    from app.services.season.runtime import routed_sentence

    _, turns = _t4a()
    assert routed_sentence({"examples": ["LARTSIM"]}, True, turn=turns[0]) is None
    assert routed_sentence({"examples": ["Pas encore"]}, True, turn={"choice": True, "from_solve": "choix"}) == "Pas encore"
    assert routed_sentence({"examples": ["Non ! Je ne sais pas."]}, True, turn={"id": "t"}) == "Non ! Je ne sais pas."
