"""#1086: La Forge answered «Tu est» / «Tu suis» with only «Être heißt sein.»

Explore walk 26 Nov 2026 (``a1-de-fresh``, day 1, «Ich bin, du bist: Subjektpronomen und
être»). Three-option choice items, first miss, before the solution: «Nous êtes» and «Ils
est» got the person hint «Schau, wer es tut, und nimm die Form von «être» für diese
Person.», but the two «tu» items (answer «es») got the rule's gloss alone.

The answer-leak scrub (``solution_gate.leak_terms`` / ``scrub_hint``) compared the French
answer's tokens with every word of the German sentence, so the German pronoun «es» counted
as the French answer «es» and the whole person hint was dropped. A French form leaks when
it is quoted as French («es»), or when it is no word of the learner's language; a word of
the learner's own sentence is not the answer.
"""
from __future__ import annotations

import pytest

from app.services import solution_gate
from app.services.atelier import AtelierCorrectionService
from tests.gold_transcripts.surfaces import make_concept

UNIT = "FR2_A11_ETRE"
PERSON_HINT = "Schau, wer es tut, und nimm die Form von «être» für diese Person."


def _service(language: str) -> AtelierCorrectionService:
    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = language
    service._learner_native = language
    service._answer_truncated = False
    return service


def _first_miss(prompt: str, choices: list[str], picked: str, answer: str, language: str = "de") -> str:
    """The reason a first miss shows while the solution waits (the walk's card)."""

    concept = make_concept(UNIT)
    item = {"id": "etre-1", "prompt": prompt, "choices": choices, "correct_answer": answer, "lesson_external_id": UNIT}
    erratum = _service(language)._recognize_erratum(concept, "fill", item, picked, answer)
    correction = solution_gate.mark(
        {"verdict": "incorrect", "errata": [erratum], "corrected_answer": answer}, chance=True, language=language
    )
    view = solution_gate.learner_view(correction, answer_payload={"answers": {"etre-1": picked}}, context=prompt)
    [shown] = view["errata"]
    return shown["hint"]


@pytest.mark.parametrize(
    ("prompt", "choices", "picked"),
    [
        ("Tu ___ à Paris cette semaine ?", ["es", "est", "êtes"], "est"),
        ("Tu ___ à l'hôtel ?", ["es", "suis", "sont"], "suis"),
    ],
)
def test_a_tu_miss_gets_the_person_hint_not_only_the_gloss(prompt: str, choices: list[str], picked: str) -> None:
    hint = _first_miss(prompt, choices, picked, "es")
    assert hint == PERSON_HINT, f"«{picked}» for «es» was not told to look at the person: {hint}"


def test_the_nous_and_ils_misses_keep_the_person_hint() -> None:
    assert _first_miss("Nous ___ à la rédaction avec Lila.", ["sommes", "êtes", "sont"], "êtes", "sommes") == PERSON_HINT
    assert _first_miss("Ils ___ à la poste.", ["sont", "est", "sommes"], "est", "sont") == PERSON_HINT


def _served(hint: str, picked: str, answer: str, language: str) -> str:
    """What ``learner_view`` serves of a stored hint while the solution waits."""

    erratum = {"item_id": "etre-1", "learner_text": picked, "corrected_target": answer, "hint": hint,
               "why_wrong": "", "repair_hint": ""}
    correction = solution_gate.mark(
        {"verdict": "incorrect", "errata": [erratum], "corrected_answer": answer}, chance=True, language=language
    )
    view = solution_gate.learner_view(correction, answer_payload={"answers": {"etre-1": picked}})
    return view["errata"][0]["hint"]


def test_a_clause_that_quotes_the_answer_as_french_is_still_dropped() -> None:
    named = "Mit «tu» heißt «être» «es», nicht «est»."
    assert _served(f"{named} {PERSON_HINT}", "est", "es", "de") == PERSON_HINT
    assert "es»" not in _served(named, "est", "es", "de")
    assert _served("Mit tu heißt être „es“.", "est", "es", "de") != "Mit tu heißt être „es“."


def test_an_unquoted_french_answer_still_leaks() -> None:
    """A word that is no German word («sommes») leaks quoted or not; a French hint keeps
    the strict reading («es» in a French sentence is the answer)."""

    assert "sommes" not in _served("Nimm hier sommes.", "êtes", "sommes", "de")
    assert "dit es" not in _served("Avec tu, on dit es.", "est", "es", "fr")
    assert "es" not in _served("With tu, être is es.", "est", "es", "en").split()
