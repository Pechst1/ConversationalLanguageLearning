"""#849 (live walk 17 Nov, A1.1 day 36): the rule drill keyed a cut piece of a scene line.

«Which sentence uses today's rule?» for «Question words: où, quand, comment, combien, quel»
offered «C'est une publicité pour des chaussettes.», «La huitième part, c'est pour le
train ?» and «le groupe qui tient le café ensemble ?», and keyed the last one. That string
is the tail of Marin's line «Comment on dit, déjà… le groupe qui tient le café ensemble ?»:

* the scene was cut after «déjà…», though the next word opens on a small letter, so the
  sentence goes on (a hesitation, not an end): the question word was cut off;
* what was left still passed the rule's detector on «qui»: a relative pronoun after a
  noun («le groupe qui tient»), which asks nothing.

A drill's keyed sentence now holds one of the rule's question words, used as one.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.db.models.grammar import GrammarConcept
from app.services import concept_life, grammar_items
from app.services import journey_planner as planner
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

MARIN = "Comment on dit, déjà… le groupe qui tient le café ensemble ?"
FRAGMENT = "le groupe qui tient le café ensemble ?"
QUESTION = "La huitième part, c'est pour le train ?"
AD = "C'est une publicité pour des chaussettes."
#: The rule's marker words, as its title names them.
MARKERS = re.compile(r"\b(?:où|quand|comment|combien|quel(?:le)?s?)\b", re.IGNORECASE)


def _question_words(db: Session) -> dict:
    FrenchCoreGrammarCatalog(db, "v2").ensure_catalog()
    concept = db.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A11_QUESTION_WORDS").one()
    return concept_life.concept_brief(db, concept, control_language="en")


def _key(task) -> str:
    return next(option["text_fr"] for option in task.options if option["id"] == task.correct_option_id)


def test_a_hesitation_that_runs_on_in_small_letters_is_one_sentence() -> None:
    assert planner.scene_sentences(MARIN) == [MARIN]
    # A real end still ends one, an ellipsis included.
    assert planner.scene_sentences("Je ne sais pas… Tu viens ?") == ["Je ne sais pas…", "Tu viens ?"]
    assert planner.scene_sentences(AD, QUESTION) == [AD, QUESTION]


def test_a_relative_qui_is_no_question_word(db_session: Session) -> None:
    brief = _question_words(db_session)
    assert grammar_items.rule_span(brief, FRAGMENT) is None
    assert grammar_items.rule_span(brief, "Tu connais le groupe qui joue ce soir ?") is None
    # The question word «qui» still counts, at the head of the question or after a preposition.
    for text in ("Qui vient ce soir ?", "C'est qui ?", "Tu parles à qui ?", "Avec qui tu viens ?",
                 "Qu'est-ce qui se passe ?", MARIN):
        assert grammar_items.rule_span(brief, text) is not None, text


def test_the_drill_never_keys_the_fragment_over_the_real_question(db_session: Session) -> None:
    """The done-when, with the walk's exact strings: «le groupe qui tient le café
    ensemble ?» is not the key while «La huitième part, c'est pour le train ?» is «Not
    this one»."""

    brief = _question_words(db_session)
    task = grammar_items.recognise_item(brief, sentences=[AD, QUESTION, FRAGMENT], language="en")
    if task is not None:
        assert _key(task) != FRAGMENT, [option["text_fr"] for option in task.options]
        assert MARKERS.search(_key(task)), _key(task)


def test_the_scene_drill_keys_a_sentence_with_a_question_word(db_session: Session) -> None:
    brief = _question_words(db_session)
    sentences = planner.scene_sentences(AD, QUESTION, MARIN)
    task = grammar_items.recognise_item(brief, sentences=sentences, language="en")
    assert task is not None
    texts = [option["text_fr"] for option in task.options]
    assert FRAGMENT not in texts, texts
    assert MARKERS.search(_key(task)), _key(task)
