"""#596 (root cause #146): a miss is explained by the learner's slip, not the day's card.

La Forge answered «Marin cherche le clé.» with the rule card's headline and its first
trap «✗ J'aime café.» (a missing article), and «est» typed for «tu» with «here it is
«es»» followed by «✗ Je es français.», crossing out the form it had just asked for.
One classifier (``forge_grading.slip_kind``) now names the slip, and the same one
picks the card's example (``grammar_feedback.authored_repair``).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.forge_grading import slip_kind, slip_note, token_diff
from app.services.grammar_feedback import authored_repair

ETRE = SimpleNamespace(external_id="FR2_A11_ETRE")
LE_LA = SimpleNamespace(external_id="FR2_A11_LE_LA")


@pytest.mark.parametrize(
    ("learner", "target", "kind"),
    [("le", "la", "gender"), ("un", "une", "gender"), ("le", "les", "number"), ("est", "es", "person"),
     ("je", "j'", "elision"), ("lui", "le", "object_pronoun"), ("petit", "petite", None), ("mange", "mangé", None)],
)
def test_one_classifier_names_the_kind_of_slip(learner, target, kind):
    assert slip_kind(learner, target) == kind


def test_an_article_gender_miss_names_the_noun_and_its_gender():
    why, repair = slip_note(token_diff("Marin cherche le clé.", "Marin cherche la clé."), "de", "Marin cherche la clé.")
    assert "«clé»" in why and "weiblich" in why and "«la clé»" in why
    assert "J'aime" not in why + repair


def test_an_article_number_miss_says_plural():
    why, _repair = slip_note(token_diff("Le lits sont là.", "Les lits sont là."), "en", "Les lits sont là.")
    assert "plural" in why and "«les lits»" in why


def test_a_verb_form_miss_names_the_subject_when_the_sentence_has_one():
    why, _repair = slip_note(token_diff("Tu est à l'hôpital ?", "Tu es à l'hôpital ?"), "en", "Tu es à l'hôpital ?")
    assert why == "With «tu», «être» is «es», not «est»."


def test_the_cards_example_never_crosses_out_the_form_the_answer_needed():
    trap = authored_repair(ETRE, "est", "es")
    assert "Je es" not in trap, trap
    assert authored_repair(ETRE, "Je es là.", "Je suis là.") == "✗ Je es français. → ✓ Je suis français."


def test_the_cards_example_is_the_same_kind_of_slip_when_the_card_has_one():
    assert authored_repair(LE_LA, "Marin cherche le clé.", "Marin cherche la clé.") == "✗ la problème → ✓ le problème"
    # Without the miss, the unit's first trap, as before.
    assert authored_repair(LE_LA) == "✗ J'aime café. → ✓ J'aime le café."


def test_the_forge_miss_on_le_cle_is_about_the_noun(db_session):
    from app.db.models.grammar import GrammarConcept
    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id="FR2_A11_LE_LA", name="Le, la, l', les", level="A1", category="Articles")
    item = {
        "id": "pick", "prompt": "Welcher Satz sagt: „Marin sucht den Schlüssel.“?",
        "choices": ["Marin cherche le clé.", "Marin cherche la clé."],
        "correct_answer": "Marin cherche la clé.", "lesson_external_id": "FR2_A11_LE_LA",
    }
    service = AtelierCorrectionService(db_session)
    service.explanation_language = "de"
    erratum = service._recognize_erratum(concept, "choice", item, "Marin cherche le clé.", "Marin cherche la clé.")
    assert "weiblich" in erratum["why_wrong"], erratum
    assert "J'aime café" not in f"{erratum['why_wrong']} {erratum['repair_hint']}"
