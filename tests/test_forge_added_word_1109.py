"""#1109: La Forge's typed gap answered «ils ont écouté à» with the avoir gloss and the key.

Walk of 27 Nov 2026, ``a2-en``, day 1, La Forge on «Passé composé with avoir». The typed
gap «Hier soir, ___ Lila.» (key «ils ont écouté») took «ils ont écouté à», an English
speaker's «listen to»: auxiliary and participle right, an extra «à». The card said «You
wrote “ils ont écouté à”; this item needs “ils ont écouté”. Most verbs say the past with
avoir + …» above «Find it yourself first; the solution comes after.»

Two flaws. ``_miss_outside_the_rule`` noticed only a learner who dropped or changed a word
every choice shares; one who ADDED a word no choice and no ``target_span`` holds passed as
«on the rule», so the rule's gloss was cited. And the answer-leak scrub kept every phrase
the learner's line already holds, so a key that is the line minus the added word was
never read as the answer.
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import solution_gate
from app.services.atelier import AtelierCorrectionService

UNIT = "FR2_A21_PC_AVOIR"
KEY = "ils ont écouté"
ITEM = {
    "id": "pc-1",
    "prompt": "Hier soir, ___ Lila.",
    "choices": [KEY, "ils ont écouter"],
    "correct_answer": KEY,
    "target_span": KEY,
    "accepted_answers": [KEY],
    "meaning": "Last night, they listened to Lila.",
    "goal_native": 'Complete: "Last night, they listened to Lila."',
    "lesson_external_id": UNIT,
}


def _attempt(answer: str, language: str, item: dict | None = None) -> tuple[dict, dict]:
    """The typed gap through the attempt path: the stored correction and what is served
    while the solution waits."""

    item = item or ITEM
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    service._posed_drill = "typed"
    concept = GrammarConcept(id=1, external_id=UNIT, name="Passé composé with avoir", level="A2", category="Grammar")
    payload = {"items": [item]}
    answers = {"answers": {item["id"]: answer}}
    correction = service._correct_recognize(concept, "fill", payload, answers)
    marked = solution_gate.mark(correction, chance=True, language=language)
    view = solution_gate.learner_view(marked, answer_payload=answers, context=solution_gate.task_text(payload))
    return correction, view


def _avoir_gloss(text: str) -> bool:
    lowered = text.lower()
    return "avoir" in lowered and any(word in lowered for word in ("participle", "partizip", "participe", "-é/-i/-u"))


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_added_word(language: str) -> None:
    correction, _view = _attempt("ils ont écouté à", language)
    [erratum] = correction["errata"]
    for field in ("why_wrong", "hint", "repair_hint"):
        assert not _avoir_gloss(str(erratum.get(field) or "")), f"{language}: the avoir gloss blamed an extra «à» ({field}): {erratum.get(field)!r}"
    other_words = {
        "en": "another word of the line differs",
        "de": "ein anderes wort der zeile",
        "fr": "un autre mot de la ligne",
    }[language]
    assert other_words in erratum["why_wrong"].lower(), erratum["why_wrong"]


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_key_hidden(language: str) -> None:
    _correction, view = _attempt("ils ont écouté à", language)
    shown = [view.get("corrected_answer") or "", *view.get("notes_native", [])]
    for erratum in view["errata"]:
        shown += [erratum.get(field) or "" for field in ("why_wrong", "hint", "repair_hint", "corrected_target")]
    for text in shown:
        # The learner's own line may be quoted back; the key on its own may not.
        rest = str(text).replace("ils ont écouté à", "")
        assert KEY not in rest, f"{language}: the key was shown before «Show the solution»: {text!r}"
    assert all(str(erratum.get("hint") or "").strip() for erratum in view["errata"]), "the miss still says something"


def test_line_marked() -> None:
    _correction, view = _attempt("ils ont écouté à", "en")
    [erratum] = view["errata"]
    assert erratum["learner_text"] == "ils ont écouté à"
    assert view["marks"], "the learner's line is still marked"


def test_rule_slip() -> None:
    """«ils ont écouter» (the infinitive for the participle) is the rule's own slip."""

    correction, _view = _attempt("ils ont écouter", "en")
    [erratum] = correction["errata"]
    assert "another word of the line differs" not in erratum["why_wrong"].lower()


def test_on_a_lire() -> None:
    """The walk of 25 Nov: «on a lire» (choices «on a lu» / «on a lire») is on the rule."""

    item = {**ITEM, "id": "pc-2", "prompt": "Hier, ___ un roman.", "choices": ["on a lu", "on a lire"], "correct_answer": "on a lu", "target_span": "on a lu", "accepted_answers": ["on a lu"]}
    correction, _view = _attempt("on a lire", "en", item)
    [erratum] = correction["errata"]
    assert "another word of the line differs" not in erratum["why_wrong"].lower()


def test_tu_a_dit() -> None:
    """The walk of 25 Nov: «Tu a dit» (choices «Tu as dit» / «Tu as dire») keeps the verdict
    it had («Another word …», changed shared word «as»); no word was added, and #1067 owns
    whether that verdict is right."""

    item = {**ITEM, "id": "pc-3", "prompt": "___ bonjour à Romy.", "choices": ["Tu as dit", "Tu as dire"], "correct_answer": "Tu as dit", "target_span": "Tu as dit", "accepted_answers": ["Tu as dit"]}
    [erratum] = _attempt("Tu a dit", "en", item)[0]["errata"]
    assert "another word of the line differs" in erratum["why_wrong"].lower()
