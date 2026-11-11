"""#535, #556, #558 (children of #145): «One line to say aloud» is a whole, correct sentence
that goes along with what the learner said.

Walks of 5 to 9 Nov. The card offered «LARTSIM», a reversed neon sign; «Un peu. Tu dois
dire.», broken French; «Ça va, merci. Un peu triste.» after «je vais bien» and «fatigué»;
the learner's own «Je pense a ma grand-mere parce que lappartement…» with its mistakes in
it; and «Oui, on partage.» after «Non, je ne partage pas la pizza».

These read only which line the card offers, so a wrong reading costs a line, never a turn.
The list of lines that must stand guards the other way: a script the learner agrees with
keeps its place.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import learner_facts, spoken_reply
from app.services.learner_facts import has_verb, looks_misspelled, reads_as_sentence, stance_of


@pytest.fixture(autouse=True)
def spoken_on(monkeypatch):
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)


def _step(*said, suggested="", route=None):
    turns = []
    for item in said:
        learner, corrected = item if isinstance(item, tuple) else (item, None)
        turn = {"learner": learner, "character": "Ah ?"}
        if corrected:
            turn["correction"] = {"corrected_fr": corrected}
        turns.append(turn)
    if route is not None:
        turns[-1]["route"] = route
    return SimpleNamespace(private_task={"turns": turns, "response_task": {"suggested_response_fr": suggested}})


# ---------------------------------------------------------------------------
# The walks
# ---------------------------------------------------------------------------


WALK_9_NOV = (
    "Non, je ne partage pas la pizza… tu a menti à Margaux",
    "Non, je ne partage pas la pizza… tu as menti à Margaux.",
)


def test_the_line_never_says_yes_to_what_the_learner_refused():
    """9 Nov. Three replies later, the first «non» still stands: nothing took it back."""

    step = _step(
        WALK_9_NOV,
        "Mon chat s'appelle Napoléon. Il aime le poisson. Et toi ?",
        suggested="Oui, on partage.",
    )
    line = spoken_reply.repeat_line_for(step)
    assert line == WALK_9_NOV[1]


def test_a_later_yes_takes_the_refusal_back():
    step = _step("Non, je ne partage pas la pizza.", "Bon, d'accord, je partage la pizza.", suggested="Oui, on partage.")
    assert spoken_reply.repeat_line_for(step) == "Oui, on partage."


def test_the_line_is_not_a_feeling_the_learner_never_had():
    """7 Nov: they wrote «je vais bien» and «fatigué». Their own sentence is the line, and
    it is written as one."""

    step = _step("je vais bien", "fatigué", suggested="Ça va, merci. Un peu triste.")
    assert spoken_reply.repeat_line_for(step) == "Je vais bien."


def test_the_line_is_not_the_learners_words_with_their_mistakes_in_them():
    """8 Nov: the margin fixed only «lappartement», and the raw sentence came back."""

    raw = "Je pense a ma grand-mere parce que lappartement est petit."
    assert spoken_reply.repeat_line_for(_step(raw)) is None
    assert spoken_reply.repeat_line_for(_step(raw, suggested="Je ne suis pas sûr.")) is None
    partial = (raw, "Je pense a ma grand-mere parce que l'appartement est petit.")
    assert spoken_reply.repeat_line_for(_step(partial, suggested="Je ne suis pas sûr.")) is None


def test_words_the_margin_corrected_are_never_offered_when_the_correction_cannot_be():
    """A correction that is not a sentence does not bring the raw words back (#445)."""

    step = _step(("Je suis peur un peu", "J'ai peur"), suggested="La bouillotte est rouge.")
    assert spoken_reply.repeat_line_for(step) is None


def test_the_walk_of_5_nov_offers_the_corrected_sentence_with_a_verb():
    """#535: a clue's tap target («LARTSIM») is not a line; the correction is."""

    said = "Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sais pas. Margaux a raison."
    corrected = "Le feu est en haut, chez Odile. Gus dit en bas, mais il ne sait pas. Margaux a raison."
    step = _step((said, corrected), route={"turn": "a.enquete", "reply": "neon", "tap": True})
    line = spoken_reply.repeat_line_for(step)
    assert line == corrected
    assert reads_as_sentence(line)
    assert not reads_as_sentence("LARTSIM")


def test_the_a1_line_of_the_walk_of_6_nov_is_whole_french():
    """#558: «Un peu. Tu dois dire.» was the page's own line at A1."""

    levels = json.loads(Path("app/data/season/s1/levels_a.json").read_text(encoding="utf-8"))
    raw = json.dumps(levels, ensure_ascii=False)
    assert "Tu dois dire." not in raw
    assert "Un peu. Tu dois le dire." in raw


def test_the_walk_of_6_nov_offers_what_the_learner_said_corrected():
    """#558. The learner's reply is about the lie, the page's line about saying it, so the
    line is theirs, not a sentence a reader would have to take on."""

    said = "Oui, un peu. Tu as menti pendant trois ans a ma grand-mere. Mais je veux comprendre pourquoi tu as fait ca."
    corrected = "Oui, un peu. Tu as menti pendant trois ans à ma grand-mère. Mais je veux comprendre pourquoi tu as fait ça."
    route = {"turn": "b.turn2", "reply": "a_little", "say_fr": "Un peu. Tu dois le dire."}
    assert spoken_reply.repeat_line_for(_step((said, corrected), route=route)) == corrected


def test_the_pages_line_stands_when_the_reply_is_about_it():
    route = {"turn": "b.turn2", "reply": "a_little", "say_fr": "Un peu. Tu dois le dire."}
    step = _step("Un peu. Tu dois dire la vérité.", route=route)
    assert spoken_reply.repeat_line_for(step) == "Un peu. Tu dois le dire."


def test_a_page_line_too_short_to_practise_gives_way():
    step = _step("Oui, je reste ici ce soir.", route={"turn": "x", "reply": "yes", "say_fr": "Oui."})
    assert spoken_reply.repeat_line_for(step) == "Oui, je reste ici ce soir."


def test_a_page_line_whole_without_a_verb_stands():
    """The owner's lines are written whole: the verb rule is for text nobody wrote for this."""

    step = _step("Merci pour tout, vraiment.", route={"turn": "x", "reply": "yes", "say_fr": "Merci pour tout."})
    assert spoken_reply.repeat_line_for(step) == "Merci pour tout."


def test_the_audio_door_reads_the_same_line():
    step = _step(WALK_9_NOV, suggested="Oui, on partage.")
    shown = SimpleNamespace(corrected_fr=WALK_9_NOV[1])
    assert spoken_reply.repeat_line_for(step) == spoken_reply.repeat_line_for(step, shown)


# ---------------------------------------------------------------------------
# A line the learner agrees with keeps its place
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("said", "line"),
    [
        # A reply with nothing to go against.
        ("Oui.", "Oui, je reste."),
        ("Non.", "Non, je ne reste pas."),
        ("D'accord.", "Je garde la clé."),
        # About the same thing, in other words.
        ("Un café, s'il vous plaît.", "Je voudrais un café, s'il vous plaît."),
        ("Je veux garder la clé.", "Je garde la clé."),
        ("Je vais vendre l'appartement.", "Oui. Je vends et je rentre."),
        ("Je ne vends pas l'appartement.", "Non, je ne vends pas."),
        ("Je ne veux pas partager.", "Non, je ne partage pas."),
        # A «non» about one thing and a line about another word of the same reply.
        ("Non, je ne vends pas. Je garde la clé.", "Je garde la clé."),
        # What they refused stays refused in the line's own words.
        ("Je n'ai pas lu la lettre.", "Je n'ai pas lu la lettre, promis."),
        ("Je ne sais pas encore, mais je reste ce soir.", "Je reste ce soir."),
    ],
)
def test_a_written_line_the_learner_agrees_with_stands(said, line):
    assert spoken_reply.repeat_line_for(_step(said, suggested=line)) == line


@pytest.mark.parametrize(
    ("said", "line"),
    [
        ("Non, je ne partage pas la pizza.", "Oui, on partage."),
        ("Je partage pas.", "Oui, on partage."),
        ("Je veux pas lire la lettre.", "Bon, je lis la lettre avec toi."),
        ("Je ne veux pas lire la lettre.", "Je vais lire la lettre."),
        ("Je n'ai pas vendu l'appartement.", "J'ai vendu l'appartement."),
        ("Je vends l'appartement.", "Non, je ne vends pas l'appartement."),
        ("Non, merci.", "Oui, avec plaisir, merci."),
        ("Oui, merci.", "Non, pas ce soir, merci."),
    ],
)
def test_a_written_line_that_says_the_opposite_gives_way(said, line):
    assert spoken_reply.repeat_line_for(_step(said, suggested=line)) != line


# ---------------------------------------------------------------------------
# The readings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "word", "affirmed"),
    [
        ("Non, je ne partage pas la pizza.", "partager", False),
        ("Non, je ne partage pas la pizza.", "pizza", True),
        ("Je partage pas.", "partage", False),
        ("Je veux pas lire.", "lis", False),
        ("Je ne veux pas le partager.", "partage", False),
        ("Je n'ai pas vendu.", "vends", False),
        ("Je ne vois personne.", "voir", False),
        # «plus» means something else without «ne».
        ("Je mange plus.", "manger", True),
        # A question takes no side.
        ("Tu ne partages pas ?", "partager", None),
        # Both in one reply: nothing can be read from it.
        ("Je ne vends pas le café mais je vends la bouillotte.", "vendre", None),
        ("Je ne vends pas le café mais je vends la bouillotte.", "bouillotte", True),
    ],
)
def test_what_a_text_says_yes_or_no_to(text, word, affirmed):
    assert stance_of(text).get(learner_facts._stem(word)) is affirmed


@pytest.mark.parametrize(
    "text",
    ["Je vais bien.", "J'aime le café.", "Regarde la lettre !", "Parle avec Gus.", "C'est ça.", "Tu as menti."],
)
def test_a_sentence_has_a_verb(text):
    assert has_verb(text)


@pytest.mark.parametrize("text", ["LARTSIM", "Le feu en haut", "Un peu", "Et toi ?", "Pas encore"])
def test_a_fragment_has_no_verb(text):
    assert not has_verb(text)


@pytest.mark.parametrize("text", ["fatigué", "Pas encore", "Oui.", "Le feu en haut"])
def test_a_fragment_is_not_a_sentence(text):
    assert not reads_as_sentence(text)


@pytest.mark.parametrize(
    "text",
    [
        "La verite est ici.",
        "Ma grand-mere est partie.",
        "Le canape est rouge.",
        "Ca va bien.",
        "Je suis daccord.",
        "Je pense que lappartement est petit.",
        "Elle vient dabord.",
    ],
)
def test_a_word_without_its_accent_or_apostrophe_is_seen(text):
    assert looks_misspelled(text)


@pytest.mark.parametrize(
    "text",
    [
        "J'arrive le 5 mars.",
        "Je parle avec Gus.",
        "Il aime le poisson.",
        "Ma grand-mère est partie.",
        "Le canapé est rouge.",
        "Marin a un zootrope.",  # A word the lexicon does not know is left alone.
        "Napoleon mange.",  # So is a name.
        "Aujourd'hui, c'est d'accord.",
        "Qu'est-ce que tu as ?",
    ],
)
def test_correct_french_and_rare_words_are_left_alone(text):
    assert not looks_misspelled(text)


def test_a_clash_on_stance_counts_against_a_correction():
    assert learner_facts.contradicts("Non, je ne partage pas.", "Oui, je partage.")
    assert not learner_facts.contradicts("Non, je ne partage pas.", "Non, je ne partage pas.")
