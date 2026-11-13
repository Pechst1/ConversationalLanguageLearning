"""#748 (child of #145): «One line to say aloud» never offers a thing the learner refused.

Live walk 13 Nov, scene «Marin fait une omelette». Reply 1 was «Non, je ne veux pas de
pizza. Je ai mangé hier. Pourquoi tu veux toujours manger, Lila ?», replies 2 and 3 were
about the parrot in the cellar and the stolen key, and the closing panel said «Tu ne veux
pas de pizza». The card still offered the opening beat's «Une pizza, s'il te plaît !».

The line goes against what the learner said, but the reader of what a reply says yes or
no to only knew «ne VERB pas» and «VERB pas INFINITIVE». The commonest way an A1 learner
refuses a thing, «pas de N» («je ne veux pas de pizza», «pas de café pour moi»), read the
thing as wanted, so the card took the refused pizza for something they had talked about.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import learner_facts, spoken_reply
from app.services.learner_facts import chips_for_thread, content_of, stance_of

OPENING_BEAT = "Une pizza, s'il te plaît !"
REFUSAL = "Non, je ne veux pas de pizza. Je ai mangé hier. Pourquoi tu veux toujours manger, Lila ?"
REFUSAL_SHOWN = "Non, je ne veux pas de pizza. J'ai mangé hier. Pourquoi tu veux toujours manger, Lila ?"


@pytest.fixture(autouse=True)
def spoken_on(monkeypatch):
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)


def _step(*said, suggested=""):
    turns = []
    for item in said:
        learner, corrected = item if isinstance(item, tuple) else (item, None)
        turn = {"learner": learner, "character": "Ah ?"}
        if corrected:
            turn["correction"] = {"corrected_fr": corrected}
        turns.append(turn)
    return SimpleNamespace(private_task={"turns": turns, "response_task": {"suggested_response_fr": suggested}})


def test_walk_13_nov():
    """Three replies, the first refusing pizza: the card offers the learner's own line."""

    step = _step(
        (REFUSAL, REFUSAL_SHOWN),
        "Le perroquet est dans la cave.",
        "Quelqu'un a volé la clé de Marin.",
        suggested=OPENING_BEAT,
    )
    line = spoken_reply.repeat_line_for(step)
    assert line != OPENING_BEAT, "the card offered the pizza the learner refused"
    assert line == REFUSAL_SHOWN


def test_refusal_taken_back():
    step = _step("Je ne veux pas de pizza.", "Bon, d'accord, je veux une pizza.", suggested=OPENING_BEAT)
    assert spoken_reply.repeat_line_for(step) == OPENING_BEAT


@pytest.mark.parametrize(
    ("said", "line"),
    [
        (REFUSAL, OPENING_BEAT),
        ("Pas de pizza pour moi.", OPENING_BEAT),
        ("Je ne bois jamais de café.", "Un café, s'il vous plaît."),
        ("Je ne veux plus de soupe.", "Encore de la soupe, s'il te plaît."),
        ("Je n'ai pas d'argent.", "J'ai de l'argent."),
    ],
    ids=["walk", "pas-de", "jamais-de", "plus-de", "pas-d"],
)
def test_line_gives_way(said, line):
    assert spoken_reply.repeat_line_for(_step(said, suggested=line)) != line


@pytest.mark.parametrize(
    ("text", "word"),
    [
        (REFUSAL, "pizza"),
        ("Pas de pizza pour moi.", "pizza"),
        ("Je ne bois jamais de café.", "café"),
        ("Je ne veux plus de soupe.", "soupe"),
        ("Je n'ai pas d'argent.", "argent"),
    ],
    ids=["walk", "pas-de", "jamais-de", "plus-de", "pas-d"],
)
def test_pas_de(text, word):
    assert stance_of(text).get(learner_facts._stem(word)) is False


@pytest.mark.parametrize(
    "text",
    ["Je mange plus de pizza.", "Je veux de la pizza.", "Une pizza, s'il te plaît !"],
    ids=["plus-without-ne", "de-la", "opening"],
)
def test_wanted(text):
    """«plus de» without «ne» is «more», and a plain «de» negates nothing."""

    assert stance_of(text).get(learner_facts._stem("pizza")) is True


def test_ne_is_no_word():
    """«ne» folded to «naître» and made every negative reply «about» being born."""

    assert content_of("Je ne veux pas de pizza.") == content_of("pizza")
    assert learner_facts._stem("naître") not in stance_of("Je ne partage pas la pizza.")


def test_chips_557():
    """#557's chips read the same stance: a chip asking for the refused pizza goes."""

    chips = [OPENING_BEAT, "Le perroquet est dans la cave ?"]
    assert chips_for_thread(chips, ["Non, je ne veux pas de pizza."]) == ["Le perroquet est dans la cave ?"]
