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


def test_yes_not_reasked(reading):
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
    ids=range(6),
)
def test_yes_no_answers(text):
    _, turns = _t4b()
    assert answers_question(turns[0], text), text


@pytest.mark.parametrize(
    "text",
    ["Je m'appelle Vincent.", "Bonjour !", "Il pleut beaucoup.", "Oui ? Pourquoi tu demandes ça ?", "Oui"],
    ids=range(5),
)
def test_open_cases(reading, text):
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


#: Authored yes/no questions of the season (day, turn): each takes a yes and a no.
YES_NO_TURNS = [
    ("t1", "a", "a.turn2"),
    ("t2", "a", "a.turn2"),
    ("t2", "b", "b.key"),
    ("t3", "b", "b.turn1"),
    ("t4", "b", "b.turn1"),
    ("t4", "b", "b.turn2"),
    ("t4", "b", "b.turn3r"),
]
#: Questions that ask for a thing: «Oui» is not an answer to them.
OPEN_TURNS = [("t2", "b", "b.turn1"), ("t2", "b", "b.turn2"), ("t6", "a", "a.turn1")]


def _turn_of(tentpole, day, turn_id):
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import resolve_day

    season = load_season("s1")
    page = resolve_day(season, tentpole, day, flags=effective_flags(season, {}, seed="x"), band="A1", language="en")
    turns = _scenario(page).story_context[runtime.SEASON_CONTEXT_KEY]["turns"]
    return next(turn for turn in turns if turn["id"] == turn_id)


@pytest.mark.parametrize(("tentpole", "day", "turn_id"), YES_NO_TURNS, ids=range(len(YES_NO_TURNS)))
def test_yes_no_turns(tentpole, day, turn_id):
    """The guard behind the walk: no authored page can re-ask a yes/no question that
    the learner has just answered with oui / non (the structure, not one turn)."""

    turn = _turn_of(tentpole, day, turn_id)
    assert answers_question(turn, "Oui, c'est vrai."), turn_id
    assert answers_question(turn, "Non, pas du tout."), turn_id


@pytest.mark.parametrize(("tentpole", "day", "turn_id"), OPEN_TURNS, ids=range(len(OPEN_TURNS)))
def test_open_turns(tentpole, day, turn_id):
    assert not answers_question(_turn_of(tentpole, day, turn_id), "Oui, c'est vrai."), turn_id


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


def test_label_not_said(reading, monkeypatch):
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


# ---------------------------------------------------------------------------
# #535 review of #567: the learner-sentence fallback is for a clue's tap target only
# ---------------------------------------------------------------------------


def _say_aloud(monkeypatch, turns, correction=None):
    from types import SimpleNamespace

    from app.config import settings
    from app.services import spoken_reply

    monkeypatch.setattr(settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    rows = [dict(row) for row in turns]
    if correction:
        rows[-1]["correction"] = {"corrected_fr": correction}
    return spoken_reply.repeat_line_for(SimpleNamespace(private_task={"turns": rows, "response_task": {}}))


@pytest.mark.parametrize(
    "learner",
    ["Je suis peur un peu", "Qu'est-ce que tu veux dire exactement ici ?"],
    ids=["error", "question"],
)
def test_fallback_says_nothing(monkeypatch, learner):
    """A route the page did not understand offers no line to say aloud: the learner's raw
    words (an uncorrected error, a question back to the character) are never the model."""

    line = _say_aloud(monkeypatch, [{"learner": learner, "route": {"turn": "x", "reply": "fallback"}}])
    assert line is None, f"offered {line!r} to say aloud"


def test_tap_without_correction_says_nothing(monkeypatch):
    """A clue's tap target with no correction on record: the uncorrected words are not offered."""

    line = _say_aloud(
        monkeypatch, [{"learner": "Je suis peur un peu", "route": {"turn": "x", "reply": "neon", "tap": True}}]
    )
    assert line is None, f"offered {line!r} to say aloud"


def test_tap_route_marks_itself(reading):
    scenario, turns = _t4a()
    turn = turns[0]
    scenario.character_id = turn["to"]
    reading.choice = ReplyChoice(reply_id="neon", confidence=0.9, clear=True)
    assert _say(scenario, WALK_5_NOV, [], 0).route.get("tap") is True
    reading.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.2, clear=False)
    assert "tap" not in _say(scenario, "Bonjour !", [], 0).route
