"""#949 (child of #145): «One line to say aloud» is one short main clause, never the whole reply
and never a subordinate fragment.

Live walk 20 Nov (A1.1, day 38): after the scene's last reply the card offered the learner's
fourth reply verbatim, 21 words, two sentences, a vocative and a joke about a cat:
«Oui, il ne veut plus boire, il prend son bain avec moi. Maintenant, Lila, je pense que je
garde la carte de ma grand-mère.» Seen again 21 Nov with the learner's slip in it: «Non,
Bastien est pas un ami. Je garde la banquette et je dis à Bastien de partir.» («n'» missing,
and the scene gave no correction for it).

The line is picked from the learner's text, which has no length, and nothing at the card's
exit held it to one. The review of the first fix (#1014) added three rules this file pins:
a clause that opens on «parce que», «si», «quand»… is never offered on its own; the clause
about the question's line beats the first clause; and no line over ten words is offered, not
even one that carries a date or a reason: a shorter form keeps the fact, or the card hides.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.services import spoken_reply

WALK_20_NOV = (
    "Oui, il ne veut plus boire, il prend son bain avec moi. "
    "Maintenant, Lila, je pense que je garde la carte de ma grand-mère."
)
WALK_21_NOV = "Non, Bastien est pas un ami. Je garde la banquette et je dis à Bastien de partir."

#: The scene of 20 Nov, as the learner wrote it: four replies, the cat, then the decision.
SCENE_20_NOV = (
    "Bonjour Lila. Je vais bien, merci.",
    "Mon chat s'appelle Minou. Il est petit.",
    "Il boit du lait le matin.",
    WALK_20_NOV,
)

#: The most words the card may offer (the done-when of #949).
MAX_WORDS = 10
#: A line written before the learner spoke, about something they never brought up, so the
#: card falls back to what they said (#558).
SCRIPTED = "Ça va, merci. Un peu triste."
#: What a clause that cannot stand alone opens on.
SUBORDINATE = re.compile(
    r"^(?:parce\s+qu|puisqu|car\b|si\b|s['’]|quand\b|lorsqu|comme\b|que\b|qu['’]|pour\s+qu|bien\s+qu)",
    re.IGNORECASE,
)


@pytest.fixture(autouse=True)
def spoken_on(monkeypatch):
    monkeypatch.setattr(spoken_reply.settings, "ATELIER_SPOKEN_REPLY_ENABLED", True)
    monkeypatch.setattr(spoken_reply.settings, "STORY_SCENE_RECORD", True)


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


def _sentences(line: str) -> list[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+", line.strip()) if part]


def _assert_one_short_main_clause(line: str | None) -> None:
    assert line, "the card hid: the learner said a whole sentence it could have offered"
    assert len(line.split()) <= MAX_WORDS, f"{len(line.split())} words to say aloud at A1: «{line}»"
    assert len(_sentences(line)) == 1, f"{len(_sentences(line))} sentences to say aloud: «{line}»"
    assert not SUBORDINATE.match(line), f"a subordinate fragment to say aloud: «{line}»"


# ---------------------------------------------------------------------------
# The walks
# ---------------------------------------------------------------------------


def test_the_walk_of_20_nov_offers_the_decision_not_the_whole_reply():
    """The exact reply of the issue, the learner's own fourth turn, no correction needed: the
    card offers the decision, not 21 words, not the cat's bath, not «Lila»."""

    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV, suggested=SCRIPTED))
    _assert_one_short_main_clause(line)
    assert line != WALK_20_NOV
    assert line == "Je garde la carte de ma grand-mère."


def test_the_walk_of_20_nov_as_shown_corrected_is_cut_down_too():
    """The same reply handed in as the correction the margin showed (no change needed)."""

    shown = SimpleNamespace(corrected_fr=WALK_20_NOV)
    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV), shown)
    _assert_one_short_main_clause(line)
    assert "garde la carte" in line


def test_the_sentence_offered_is_the_one_about_the_scenes_question():
    """The question was written to elicit a line about the card; the learner decided the other
    way, so their own sentence is the line: the decision, not the cat's bath."""

    line = spoken_reply.repeat_line_for(_step(*SCENE_20_NOV, suggested="Non, je ne garde pas la carte."))
    _assert_one_short_main_clause(line)
    assert "garde la carte de ma grand-mère" in line
    assert "Lila" not in line


def test_the_walk_of_21_nov_never_offers_the_slip():
    """«Bastien est pas un ami» drops «ne»: it is not the model line. Of the two decisions
    after it, the one about Bastien (what the question's line is about) is offered."""

    line = spoken_reply.repeat_line_for(_step(WALK_21_NOV, suggested="Oui, Bastien est un ami."))
    _assert_one_short_main_clause(line)
    assert "est pas" not in line
    assert line == "Je dis à Bastien de partir."
    line = spoken_reply.repeat_line_for(_step(WALK_21_NOV, suggested=SCRIPTED))
    _assert_one_short_main_clause(line)
    assert line == "Je garde la banquette."


# ---------------------------------------------------------------------------
# Review of #1014, point 1: a subordinate clause is never the line
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("said", "main"),
    [
        (
            "Parce que je suis fatigué, je ne vais pas au cinéma avec Marie ce soir.",
            "Je ne vais pas au cinéma avec Marie ce soir.",
        ),
        (
            "Si tu veux vraiment savoir la vérité, je pense que Bastien a menti à tout le monde.",
            "Bastien a menti à tout le monde.",
        ),
        (
            "Quand Lila arrive au café demain, je lui donne la clé de l'appartement.",
            "Je lui donne la clé de l'appartement.",
        ),
        (
            "Quand il fait beau et que je suis libre, je vais au parc avec mes amis le dimanche.",
            "Je vais au parc avec mes amis le dimanche.",
        ),
    ],
)
def test_the_main_clause_is_offered_never_the_subordinate_one(said, main):
    line = spoken_reply.repeat_line_for(_step(said, suggested=SCRIPTED))
    _assert_one_short_main_clause(line)
    assert line == main


def test_a_reply_of_only_subordinate_clauses_hides_the_card():
    """«Parce que je suis fatigué.» alone answers nothing: no line rather than a fragment."""

    line = spoken_reply.repeat_line_for(_step("Parce que je suis fatigué et que je travaille demain.", suggested=SCRIPTED))
    assert line is None or not SUBORDINATE.match(line), f"a fragment to say aloud: «{line}»"


# ---------------------------------------------------------------------------
# Review of #1014, point 2: the clause about the question beats the first clause
# ---------------------------------------------------------------------------


def test_the_decision_in_the_second_clause_beats_the_first_clause():
    said = "Non, je ne sais pas trop, mais je garde la carte de ma grand-mère avec moi."
    line = spoken_reply.repeat_line_for(_step(said, suggested="Non, je ne garde pas la carte."))
    _assert_one_short_main_clause(line)
    assert line == "Je garde la carte de ma grand-mère avec moi."


def test_the_learners_own_decision_beats_a_clause_about_not_knowing():
    said = "Je ne sais pas pourquoi, mais je pense que je vais garder la clé de mon père."
    line = spoken_reply.repeat_line_for(_step(said, suggested="Je donne la clé à Lila."))
    _assert_one_short_main_clause(line)
    assert "garder la clé de mon père" in line


# ---------------------------------------------------------------------------
# Review of #1014, point 3: never more than ten words, a date or a reason included
# ---------------------------------------------------------------------------


def test_a_long_sentence_with_a_date_is_cut_to_a_line_that_keeps_the_date():
    said = "Je pars le 5 mars avec ma sœur et mon frère pour voir notre grand-mère malade."
    line = spoken_reply.repeat_line_for(_step(said, suggested=SCRIPTED))
    _assert_one_short_main_clause(line)
    assert line == "Je pars le 5 mars."


def test_a_long_list_is_cut_to_ten_words():
    said = "J'ai trois chats, deux chiens et un poisson rouge dans mon petit appartement à Paris."
    line = spoken_reply.repeat_line_for(_step(said, suggested=SCRIPTED))
    _assert_one_short_main_clause(line)
    assert line.startswith("J'ai trois chats")


def test_a_date_and_a_reason_never_make_a_line_longer_than_ten_words():
    """#379 keeps the learner's own date against a scripted one; the line is still short."""

    said = "Je veux retourner le deux décembre, parce que je suis fatigué de Berlin."
    scripted = "Je rentre le 19 décembre, parce que je reste pour la fête."
    line = spoken_reply.repeat_line_for(_step(said, suggested=scripted))
    _assert_one_short_main_clause(line)
    assert line == "Je veux retourner le deux décembre."


# ---------------------------------------------------------------------------
# Every source of the line goes through the same exit
# ---------------------------------------------------------------------------


def test_a_short_sentence_still_stands_whole():
    step = _step("Oui, je reste ici ce soir.", suggested=SCRIPTED)
    assert spoken_reply.repeat_line_for(step) == "Oui, je reste ici ce soir."


def test_a_generated_line_of_two_sentences_is_cut_to_one():
    """The question's example is written by a model and has no length either."""

    step = _step("Je vais vendre l'appartement.", suggested="Oui. Je vends et je rentre.")
    assert spoken_reply.repeat_line_for(step) == "Je vends et je rentre."


def test_a_long_page_line_is_cut_to_one_sentence():
    """The page's own lines can be long too (s1: «Je lis ta carte. C'est… adieu ? Ou pardon ?
    Je comprends pas bien. Je veux pas adieu.»)."""

    route = {
        "turn": "x",
        "reply": "card",
        "say_fr": "Je lis ta carte. C'est… adieu ? Ou pardon ? Je comprends pas bien. Je veux pas adieu.",
    }
    line = spoken_reply.repeat_line_for(_step("Je lis ta lettre.", route=route))
    _assert_one_short_main_clause(line)


def test_a_short_page_line_stands_whole():
    route = {"turn": "b.turn2", "reply": "a_little", "say_fr": "Un peu. Tu dois le dire."}
    step = _step("Un peu. Tu dois dire la vérité.", route=route)
    assert spoken_reply.repeat_line_for(step) == "Un peu. Tu dois le dire."


def test_a_card_is_not_a_reason():
    """«la carte de ma grand-mère» was read as «car te de ma grand-mère», a reason the learner
    never gave."""

    from app.services.learner_facts import facts_of, reason_of

    assert reason_of("je garde la carte de ma grand-mère") == frozenset(), "«carte» read as «car …»"
    assert "reason" not in facts_of(WALK_20_NOV)
    assert reason_of("Je reste, car je suis fatigué.") == frozenset({"fatig"})


def test_the_hooks_and_the_card_share_one_ne_rule():
    """Review of #1014: one «ne» rule, not two. It catches the 21 Nov slip («pas» after a
    noun subject), which the hooks' own rule (rien, jamais, personne after a pronoun) missed."""

    from app.services import learner_facts, story_teaser

    drops_ne = story_teaser.drops_ne
    assert drops_ne("Non, Bastien est pas un ami."), "the hooks' rule misses a «pas» without «ne»"
    assert drops_ne("J'ai rien entendu.")
    assert drops_ne("Tu viens jamais au café.")
    for fine in ("Pourquoi pas ?", "Pas ce soir.", "Rien de grave.", "Je viens, pas toi ?", "Bastien n'est pas un ami."):
        assert not drops_ne(fine), fine
    assert getattr(learner_facts, "drops_ne", None) is drops_ne, "two «ne» rules, not one"
