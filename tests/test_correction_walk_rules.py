"""#250, #133, #333: the rule pass on the sentences the live walks wrote, word for word.

When the model that checks a learner's French fails, the rule pass is all that is left. Each
rule here has a test on exact walk text, and ``tests/test_correction_negative_corpus.py`` holds
what the same rule must leave alone. No model call is made anywhere in this file.
"""

from __future__ import annotations

import re

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


def test_the_name_after_a_dropped_apostrophe_needs_a_noun_in_front():
    text = "Mon chat dort sur la cheminee. Gus, est-ce que tu sais ou est la cle d Odile ?"
    _finds(text, "d Odile", "d'Odile", "FR_APOSTROPHE")


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("Gus, est-ce que tu sais ou est la cle d Odile ?", "cle", "clé", id="250-cle"),
        pytest.param("Mon chat dort sur la cheminee.", "cheminee", "cheminée", id="250-cheminee"),
        pytest.param("Vient parler avec lui samedi, s il te plait.", "plait", "plaît", id="333-plait"),
        pytest.param("Je veux retourner le deux decembre, parce que je suis fatigue de Berlin.", "decembre", "décembre", id="gold-decembre"),
        pytest.param("Tu as menti pendant trois ans a ma grand-mere", "grand-mere", "grand-mère", id="250-grand-mere"),
        pytest.param("Pourquoi le appartement paie grand-pere dabord ?", "grand-pere", "grand-père", id="250-grand-pere"),
        pytest.param("Mais pourquoi vous etes tous en colere contre moi ?", "etes", "êtes", id="walk-7-nov-etes"),
        pytest.param("Mais pourquoi vous etes tous en colere contre moi ?", "colere", "colère", id="walk-7-nov-colere"),
        pytest.param("Les cles sont sur la table.", "cles", "clés", id="plural"),
        pytest.param("Cle en main, je pars.", "Cle", "Clé", id="capital-at-the-start"),
    ],
)
def test_a_missing_accent_comes_back_when_the_word_can_only_be_one_word(text, span, replacement):
    _finds(text, span, replacement, "FR_ACCENT")


@pytest.mark.parametrize(
    ("text", "bare"),
    [
        pytest.param("Ça m'enerve.", "enerve", id="énerve-or-énervé"),
        pytest.param("J'ai ecoute la radio.", "ecoute", id="écoute-or-écouté"),
        pytest.param("Il a complete le formulaire.", "complete", id="complète-or-complété"),
        pytest.param("Je suis desole.", "desole", id="désole-or-désolé"),
        pytest.param("Je mange un desert.", "desert", id="désert-or-dessert"),
        pytest.param("Je vais metre la table.", "metre", id="mètre-or-mettre"),
        pytest.param("Elle fait une pate.", "pate", id="pâte-or-pâté"),
        pytest.param("Je suis fatigue de Berlin.", "fatigue", id="fatigue-is-a-word"),
        pytest.param("Tu sais ou est la gare ?", "ou", id="ou-is-a-word"),
    ],
)
def test_a_word_that_can_be_two_words_gets_no_accent(text, bare):
    assert bare not in [edit.span for edit in cc.deterministic_edits(text)]


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("je ne était", "ne était", "n'était", id="walk-25-oct"),
        pytest.param("Je ne ai", "ne ai", "n'ai", id="ne-ai"),
        pytest.param("Il ne a rien.", "ne a", "n'a", id="with-a-partner"),
        pytest.param("Ce ne est pas", "ne est", "n'est", id="ce"),
    ],
)
def test_ne_elides_in_front_of_a_vowel_and_no_word_is_added(text, span, replacement):
    _finds(text, span, replacement, "FR_ELISION")
    assert "pas" not in replacement


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("Je pas ai beaucoup bagages", "Je pas ai", "Je n'ai pas", id="walk-25-oct"),
        pytest.param(
            "Je pas ai beaucoup bagages aujourd'hui, mais je viens chez toi samedi soir.",
            "Je pas ai",
            "Je n'ai pas",
            id="333-letter",
        ),
        pytest.param("Il pas est là.", "Il pas est", "Il n'est pas", id="vowel"),
        pytest.param("Je pas vais à Lyon.", "Je pas vais", "Je ne vais pas", id="consonant"),
        pytest.param("Elle pas porte de manteau.", "Elle pas porte", "Elle ne porte pas", id="a-verb-that-is-also-a-noun"),
    ],
)
def test_a_negation_in_front_of_the_verb_goes_around_it(text, span, replacement):
    _finds(text, span, replacement, "FR_NEGATION_ORDER")


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param("Qu est-ce que c est, jeudi a dix-huit heures ?", "a dix-huit", "à dix-huit", id="133-walk"),
        pytest.param("Jeudi a dix-huit heures.", "a dix-huit", "à dix-huit", id="310-review-words"),
        pytest.param("Rendez-vous a 18 heures.", "a 18", "à 18", id="310-review-digits"),
        pytest.param("Je viens demain a 8h.", "a 8h", "à 8h", id="digits-glued-to-h"),
        pytest.param("On se voit samedi a 10h30 chez Gus.", "a 10h30", "à 10h30", id="minutes"),
        pytest.param("Lundi matin a 9 h, je pars.", "a 9", "à 9", id="digits-then-h"),
        pytest.param("Camille a une clé, jeudi a dix-huit heures.", "a dix-huit", "à dix-huit", id="a-right-a-earlier"),
        pytest.param("Il vient ce soir a huit heures avec Lila.", "a huit", "à huit", id="more-after-the-hour"),
        pytest.param("Aujourd'hui a dix-huit heures, je pars.", "a dix-huit", "à dix-huit", id="aujourdhui"),
    ],
)
def test_a_before_a_clock_time_after_a_day_is_a_preposition(text, span, replacement):
    _finds(text, span, replacement, "FR_A_GRAVE")


def test_the_clock_fix_lands_on_the_a_it_means():
    line = "Camille a une clé, jeudi a dix-huit heures."
    checked = cc.verify_correction(line, None, cc.deterministic_errata(line))
    assert checked.corrected == "Camille a une clé, jeudi à dix-huit heures."


@pytest.mark.parametrize(
    ("text", "span", "replacement"),
    [
        pytest.param(
            "Non, Gus, je ne promets pas. Je pense que Solvel est une bon offre pour la maison.",
            "une bon",
            "une bonne",
            id="250-walk",
        ),
        pytest.param("Solvel fait une bon offre.", "une bon", "une bonne", id="gold-k11"),
        pytest.param("Une bon idée.", "Une bon", "Une bonne", id="capital-article"),
        pytest.param("Ma petit sœur arrive.", "Ma petit", "Ma petite", id="possessive"),
        pytest.param("Cette long histoire.", "Cette long", "Cette longue", id="cette"),
        pytest.param("La dernier fois.", "La dernier", "La dernière", id="dernier"),
        pytest.param("la vieux maison", "la vieux", "la vieille", id="vieux"),
        pytest.param("une beau fille", "une beau", "une belle", id="beau"),
        pytest.param("Sa grand chambre.", "Sa grand", "Sa grande", id="grand-not-a-compound"),
    ],
)
def test_a_feminine_noun_takes_the_feminine_adjective(text, span, replacement):
    _finds(text, span, replacement, "FR_ADJ_AGREE")


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("Une bon gâteau.", id="the-article-is-the-mistake"),
        pytest.param("Une bon zzyzx.", id="a-noun-nobody-knows"),
        pytest.param("Une petit enfant.", id="a-noun-of-either-gender"),
    ],
)
def test_the_adjective_stays_when_the_noun_does_not_say_feminine(text):
    assert "FR_ADJ_AGREE" not in [edit.rule_id for edit in cc.deterministic_edits(text)]


def test_grand_mere_without_its_hyphen_gets_the_hyphen_and_no_feminine():
    assert _pairs("Ma grand mère est là.") == [("grand mère", "grand-mère")]


@pytest.mark.parametrize(
    ("text", "fixed"),
    [
        pytest.param("Camille a une clé et je vais a Paris.", "Camille a une clé et je vais à Paris.", id="a-right-a-earlier"),
        pytest.param("La table est là et je vois le maison.", "La table est là et je vois la maison.", id="a-right-la-after"),
        pytest.param("La fille mange. Je vois le maison et la voiture.", "La fille mange. Je vois la maison et la voiture.", id="the-same-word-on-both-sides"),
        pytest.param("Je vois le chat et le maison.", "Je vois le chat et la maison.", id="a-right-le-earlier"),
        pytest.param("C est bon et c est bien.", "C'est bon et c'est bien.", id="both-wrong"),
        pytest.param("Lila a un chat. Je vais a Paris et je vais a Lyon.", "Lila a un chat. Je vais à Paris et je vais à Lyon.", id="two-after-a-right-one"),
    ],
)
def test_a_rule_fix_found_by_its_words_lands_on_the_word_it_means(text, fixed):
    checked = cc.verify_correction(text, None, cc.deterministic_errata(text))
    assert checked.corrected == fixed
    assert [row["reason"] for row in checked.refused] == []
    for edit in cc.deterministic_edits(text):
        assert re.search(rf"(?<!\w){re.escape(edit.span)}(?!\w)", text, re.IGNORECASE).start() == edit.start
        assert text[edit.start : edit.end] == edit.span
    assert cc.repair_text(text) == fixed


def test_the_sentence_the_failed_check_tests_lean_on_is_still_unseen_by_the_rules():
    from tests.test_failed_check_counts_for_nothing import UNSEEN_BY_RULES

    assert cc.deterministic_edits(UNSEEN_BY_RULES) == []
