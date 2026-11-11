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

from app.services import scene_ledger
from app.services.season import runtime
from app.services.season.runtime import ASK_AGAIN
from app.services.season.turns import ReplyChoice, answers_question, classifier_payload
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


# ---------------------------------------------------------------------------
# #145: the reader of an authored day reads the scene's record
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "polar"),
    [
        ("Tu mets les photos au mur. Tu sais ça ?", True),
        ("Réponds ! Tu sais ça, oui ou non ?", True),
        ("C'est vrai ?", True),
        ("Tu es en colère contre moi ?", True),
        ("Le feu : en bas, ou en haut ? Montre.", False),
        ("Tu restes combien de temps ?", False),
        ("Et toi ?", False),
        ("Odile ?", False),
    ],
)
def test_which_questions_a_yes_or_a_no_answers(line, polar):
    assert scene_ledger.asks_yes_or_no(line) is polar


@pytest.mark.parametrize(
    ("text", "answered"),
    [
        ("Si, je savais.", True),
        ("Si tu veux, je peux demander à Odile.", False),
        ("Oui ? Pourquoi tu demandes ça ?", False),
        ("Non ?", False),
    ],
)
def test_si_and_a_word_thrown_back_as_a_question(text, answered):
    _, turns = _t4b()
    assert answers_question(turns[0], text) is answered


def test_the_readers_own_reading_outranks_the_opening_words():
    _, turns = _t4b()
    assert answers_question(turns[0], "Oui et non, peut-être.") is False
    assert answers_question(turns[0], "Oui et non, peut-être.", intent="yes") is True


def test_the_reader_is_told_the_record_of_the_scene():
    _, turns = _t4b()
    ledger = scene_ledger.build(opening_line_fr="Tu mets les photos au mur. Tu sais ça ?", history=[], learner_text=LEARNER)
    payload = classifier_payload(turns[0], LEARNER, [], band="a1", ledger=ledger)
    assert payload["ledger"]["last_turn"]["intent"] == "yes"
    assert payload["ledger"]["asked"][0]["answered_at"] == 0
    assert "stands" in payload["ledger"]
    assert "ledger" not in classifier_payload(turns[0], LEARNER, [], band="a1")


def test_the_readers_reading_stays_with_the_exchange(reading):
    scenario, turns = _t4b()
    scenario.character_id = turns[0]["to"]
    reading.choice = ReplyChoice(reply_id=str(turns[0]["fallback"]), confidence=0.3, clear=True, learner_intent="no")
    evaluation = _say(scenario, "Je ne savais rien de tout ça.", [], 0)
    assert evaluation.heard["intent"] == "no"
    assert scene_ledger.read_turn("Je ne savais rien.", heard=evaluation.heard)["read_by"] == "voice"


@pytest.mark.parametrize(
    "ack",
    [
        # The walk's own question, asked back at someone who has just answered it.
        "Réponds ! Tu sais ça, oui ou non ?",
        # Words the learner never wrote, quoted at them.
        "Tu dis : « je vends le café ».",
    ],
)
def test_a_first_line_against_the_record_is_dropped_and_the_page_plays(reading, ack):
    scenario, turns = _t4b()
    scenario.character_id = turns[0]["to"]
    reading.choice = ReplyChoice(reply_id=str(turns[0]["fallback"]), confidence=0.3, clear=True, ack_fr=ack)
    evaluation = _say(scenario, LEARNER, [], 0)
    said = [line["text_fr"] for line in evaluation.reply_lines]
    assert ack not in said
    assert said, "the authored reaction still plays"


def test_a_first_line_that_holds_to_the_record_is_played_first(reading):
    scenario, turns = _t4b()
    scenario.character_id = turns[0]["to"]
    reading.choice = ReplyChoice(reply_id=str(turns[0]["fallback"]), confidence=0.3, clear=True, ack_fr=GUS_ACK)
    evaluation = _say(scenario, LEARNER, [], 0)
    assert evaluation.reply_lines[0]["text_fr"] == GUS_ACK


def test_the_walks_reply_about_the_fire_is_taken_up_before_the_clue(reading):
    """#535 (b): the line after the reply follows from it, then the page's own clue."""

    scenario, turns = _t4a()
    turn = turns[0]
    scenario.character_id = turn["to"]
    ack = "En haut, chez Odile ? Gus dit le contraire."
    reading.choice = ReplyChoice(reply_id=str(turn["fallback"]), confidence=0.3, clear=True, ack_fr=ack)
    evaluation = _say(scenario, WALK_5_NOV, [], 0)
    said = [line["text_fr"] for line in evaluation.reply_lines]
    assert said[0] == ack
    assert "LARTSIM" not in evaluation.route.get("say_fr", "")
