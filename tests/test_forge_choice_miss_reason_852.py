"""#852 (root cause #146): a La Forge choice miss gave the rule's general sentence.

Live walk 17 Nov (A1.1, La Forge «Question words»): «___ est-ce que Gus travaille ?
(Where does Gus work?)», the learner chose «Quand». The note read «You chose “Quand”;
Question words ask for information.», and nothing said «Quand» asks when while the
sentence asks where. The pre-scene «Quel heure est-il ?» miss got the same general
line, never «heure» is feminine (quelle).

The slip classifier (``forge_grading.slip_category``) knew articles, pronouns and verb
forms, but not a question word for another nor the agreement of «quel». Whether a word
asks a question is read from the line it stands in (a relative «où» asks nothing).
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
#: what «Quand» asks about, and what the sentence asks about, as the note words them
ASKS = {
    "en": ("asks “when”", "asks “where”"),
    "de": ("fragt „wann“", "fragt „wo“"),
    "fr": ("demande le moment", "demande le lieu"),
}


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
    assert asked in why, f"nothing says what «Quand» asks ({asked!r}): {why!r}"
    assert needed in why, f"nothing says what the sentence asks ({needed!r}): {why!r}"


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


# Attempt 1 of #852 (#862) was rejected: it told «this question asks “where”» about a
# relative «où» (A2 «Le relatif où»), where «quand» for «où» is the unit's own point
# («le jour où», never «le jour quand»). A question word is named only where it asks.
RELATIVE = "FR2_A22_RELATIVE_OU"
QUESTION_TALK = ("this question asks", "diese Frage fragt", "cette question demande", "Read what the question asks")
#: the main-branch note keeps the unit's own rule line (in English, its explanation)
RULE_LINE = {"en": "Où links a place or a moment", "de": "Regel:"}


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize(
    ("prompt", "choices", "learner"),
    [
        ("Je me souviens du jour ___ Gus et Marin sont rentrés avec Romy.", ["où", "quand", "que"], "quand"),
        ("C'est le restaurant ___ Lila dîne.", ["qui", "que", "où"], "qui"),
    ],
)
def test_relative_ou_is_no_question(db_session, language: str, prompt: str, choices: list, learner: str) -> None:
    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id=RELATIVE, name="Le relatif où", level="A2", category="Syntax")
    item = {
        "id": "rel", "prompt": prompt, "choices": choices, "correct_answer": "où", "lesson_external_id": RELATIVE,
        "explanation": "Où links a place or a moment: la ville où j'habite, le jour où je suis arrivé.",
    }
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    erratum = service._recognize_erratum(concept, "fill", item, learner, "où")
    note = f"{erratum['why_wrong']} {erratum['repair_hint']}"
    assert not any(talk in note for talk in QUESTION_TALK), f"a relative «où» told as a question: {note!r}"
    assert RULE_LINE[language] in erratum["why_wrong"], f"the unit's own rule line is gone: {erratum['why_wrong']!r}"


@pytest.mark.parametrize(
    ("wrong", "right"),
    [
        ("C'est le jour quand je suis arrivé.", "C'est le jour où je suis arrivé."),
        ("L'homme où parle est mon père.", "L'homme qui parle est mon père."),
    ],
)
def test_relative_sentence_is_no_question(wrong: str, right: str) -> None:
    """A transform or judged relative sentence: no question note, with or without the line."""

    for note in (
        slip_note(token_diff(wrong, right), "en"),
        slip_note(token_diff(wrong, right, positions=True), "en", right),
    ):
        assert not note or "question" not in note[0], note


@pytest.mark.parametrize(
    ("line", "word", "asks"),
    [
        ("Où est-ce que Gus travaille ?", "Où", True),
        ("Où est le carton ?", "Où", True),
        ("D'où viens-tu ?", "où", True),
        ("Depuis quand est-ce que tu habites ici ?", "quand", True),
        ("Tu travailles où ?", "où", True),
        ("Je me souviens du jour où Gus est rentré.", "où", False),
        ("C'est le restaurant où Lila dîne ?", "où", False),
        ("Quand il pleut, je reste à la maison.", "Quand", False),
    ],
)
def test_asks_a_question(line: str, word: str, asks: bool) -> None:
    from app.services.forge_grading import asks_a_question

    assert asks_a_question(line, word) is asks, line
