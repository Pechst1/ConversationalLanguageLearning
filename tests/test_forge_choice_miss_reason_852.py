"""#852 (root cause #146): a La Forge choice miss gave the rule's general sentence.

Live walk 17 Nov (A1.1, La Forge «Question words»): «___ est-ce que Gus travaille ?
(Where does Gus work?)», the learner chose «Quand». The note read «You chose “Quand”;
Question words ask for information.», and nothing said «Quand» asks when while the
sentence asks where. The pre-scene «Quel heure est-il ?» miss got the same general
line, never «heure» is feminine (quelle).

The one slip classifier (``forge_grading.slip_kind``) knew articles, pronouns and verb
forms, but not a question word for another nor the agreement of «quel».
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import item_bank as ib
from app.services.forge_grading import slip_note, token_diff

UNIT = "FR2_A11_QUESTION_WORDS"
GENERAL = {
    "en": "Question words ask for information",
    "de": "Regel: Question words",
    "fr": "Règle : Question words",
}
#: what «Quand» asks about, and what the sentence asks about, per language
ASKS = {"en": ("when", "where"), "de": ("wann", "wo"), "fr": ("le moment", "le lieu")}


def _item(frame: str) -> dict:
    bank = ib.default_bank()
    for seed in range(80):
        for item in bank.generate(UNIT, 12, seed=f"guard-852-{seed}"):
            if item.frame_id.startswith(frame):
                payload = ib.fill_item(item, lesson_external_id=UNIT)
                if payload:
                    return payload
    raise AssertionError(f"no {frame} item in the bank")


def _erratum(db_session, language: str, item: dict, learner: str, target: str) -> dict:
    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id=UNIT, name="Question words", level="A1", category="Syntax")
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service._recognize_erratum(concept, "fill", item, learner, target)


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_quand_for_ou(db_session, language: str) -> None:
    item = _item("qw-where-cast")
    assert "Où" in item["choices"] and "Quand" in item["choices"], item
    erratum = _erratum(db_session, language, item, "Quand", "Où")
    why = erratum["why_wrong"]
    asked, needed = ASKS[language]
    assert GENERAL[language] not in why, f"the rule's general sentence, not why «Quand» is wrong: {why!r}"
    assert f"“{asked}”" in why or f"„{asked}“" in why or asked in why.split(";")[0], why
    assert needed in why, f"nothing says the sentence asks «{needed}»: {why!r}"


def test_quand_hint_survives_withholding(db_session) -> None:
    """Before «Show the solution» the note is scrubbed of the answer; the reason stays."""

    from app.services.solution_gate import leak_terms, scrub_hint

    erratum = _erratum(db_session, "en", _item("qw-where-cast"), "Quand", "Où")
    phrases, tokens = leak_terms({"errata": [erratum], "corrected_answer": {}}, "Quand")
    hint = scrub_hint(erratum["why_wrong"], phrases, tokens)
    assert "when" in hint and "where" in hint and "Où" not in hint, hint


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_quel_heure(db_session, language: str) -> None:
    feminine = {"en": "feminine", "de": "weiblich", "fr": "féminin"}[language]
    note = slip_note(token_diff("Quel heure est-il ?", "Quelle heure est-il ?", positions=True), language, "Quelle heure est-il ?")
    assert note and "heure" in note[0] and feminine in note[0], note

    item = _item("qw-what-time")
    erratum = _erratum(db_session, language, item, "À quel heure", "À quelle heure")
    assert feminine in erratum["why_wrong"] and "heure" in erratum["why_wrong"], erratum
    assert GENERAL[language] not in erratum["why_wrong"], erratum
