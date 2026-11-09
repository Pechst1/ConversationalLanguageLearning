"""#250, #133, #333: the rule pass on the sentences the live walks wrote, word for word.

When the model that checks a learner's French fails, the rule pass is all that is left. Each
rule here has a test on exact walk text, and ``tests/test_correction_negative_corpus.py`` holds
what the same rule must leave alone. No model call is made anywhere in this file.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract as cc


def _pairs(text: str) -> list[tuple[str, str]]:
    return [(edit.span, edit.replacement) for edit in cc.deterministic_edits(text)]


def _finds(text: str, span: str, replacement: str, rule_id: str) -> None:
    edits = cc.deterministic_edits(text)
    assert (span, replacement, rule_id) in [(edit.span, edit.replacement, edit.rule_id) for edit in edits], _pairs(text)
    for edit in edits:
        assert text[edit.start : edit.end] == edit.span
        assert edit.note_for("en") and edit.note_for("de") and edit.note_for("fr")


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("Camille a une clé aussi, c est bizarre.", "c est", "c'est", id="133-c-est"),
        pytest.param("Qu est-ce que c est, jeudi ?", "Qu est-ce", "Qu'est-ce", id="133-qu-est-ce"),
        pytest.param("Qu est-ce que c est, jeudi ?", "c est", "c'est", id="133-c-est-after-que"),
        pytest.param("Ce n est pas", "n est", "n'est", id="133-ce-n-est"),
        pytest.param("je pense qu il veut aider.", "qu il", "qu'il", id="333-qu-il"),
        pytest.param("Vient parler avec lui samedi, s il te plait.", "s il", "s'il", id="333-s-il"),
        pytest.param("Mais j ai peur de le restaurant.", "j ai", "j'ai", id="gold-j-ai"),
        pytest.param("Il n y a pas de pain dans la cuisine.", "n y", "n'y", id="gold-n-y"),
        pytest.param("Non, ce soir je dors a l hotel.", "l hotel", "l'hôtel", id="walk-7-nov-l-hotel"),
        pytest.param("Pourquoi votre grand-pere veut tout l immeuble ?", "l immeuble", "l'immeuble", id="walk-3-nov-l-immeuble"),
        pytest.param("a l hotel", "a l hotel", "à l'hôtel", id="brief-a-l-hotel"),
    ],
)
def test_a_dropped_apostrophe_comes_back(text, span, replacement):
    _finds(text, span, replacement, "FR_APOSTROPHE")


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("Je pense que cest Marin.", "cest", "c'est", id="gold-cest"),
        pytest.param("Je vais a la fête samedi avec Marchand, et jai un idée pour le café.", "jai", "j'ai", id="333-jai"),
        pytest.param("Oui, je vais parler à Lila demain matin… ce nest pas bien.", "nest", "n'est", id="397-nest"),
        pytest.param("Non, je ne suis pas daccord.", "daccord", "d'accord", id="250-daccord"),
        pytest.param("Pourquoi le appartement paie grand-pere dabord ?", "dabord", "d'abord", id="250-dabord"),
    ],
)
def test_a_glued_apostrophe_comes_back(text, span, replacement):
    _finds(text, span, replacement, "FR_SPELLING")


def test_the_apostrophe_keeps_the_learners_typography():
    assert ("c est", "c’est") in _pairs("J’ai une clé, c est bizarre.")


def test_a_fix_inside_the_apostrophe_is_listed_as_one():
    assert cc.repair_text("Nous sommes a l hotel avec Lila.") == "Nous sommes à l'hôtel avec Lila."
