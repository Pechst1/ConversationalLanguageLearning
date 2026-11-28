"""#1086: La Forge answered «Tu est» / «Tu suis» with only «Être heißt sein.»

Explore walk 26 Nov 2026 (``a1-de-fresh``, day 1, «Ich bin, du bist: Subjektpronomen und
être»). Three-option choice items, first miss, before the solution: «Nous êtes» and «Ils
est» got the person hint «Schau, wer es tut, und nimm die Form von «être» für diese
Person.», but the two «tu» items (answer «es») got the rule's gloss alone. The walk of 28
Nov saw the same on the tile build («Tu est à la rédaction ?») and the dictée («Tu est
italienne ?»).

The answer-leak scrub (``solution_gate.leak_terms`` / ``scrub_hint``) compared the French
answer's tokens with every word of the German sentence, so the German pronoun «es» counted
as the French answer «es» and the whole person hint was dropped. A word of the learner's
own language names the answer only where the hint quotes it as French («es», „es“,
'es'); a French form that is no word of that language («sommes») leaks quoted or not.
"""
from __future__ import annotations

import pytest

from app.services import solution_gate
from app.services.atelier import AtelierCorrectionService
from tests.gold_transcripts.surfaces import make_concept

UNIT = "FR2_A11_ETRE"
PERSON_HINT = "Schau, wer es tut, und nimm die Form von «être» für diese Person."


def _withheld(mode: str, item: dict, answer: str, language: str = "de", drill: str | None = None) -> dict:
    """The first miss as the card shows it while the solution waits."""

    service = AtelierCorrectionService(None)
    service.explanation_language = language
    if drill:
        service._posed_drill = drill
    payload = {"items": [item]}
    answers = {"answers": {item["id"]: answer}}
    correction = service._correct_recognize(make_concept(UNIT), mode, payload, answers)
    assert correction["verdict"] != "correct", correction
    marked = solution_gate.mark(correction, chance=True, language=language)
    view = solution_gate.learner_view(marked, answer_payload=answers, context=solution_gate.task_text(payload))
    [shown] = view["errata"]
    return shown


def _choice(prompt: str, choices: list[str], answer: str) -> dict:
    return {"id": "etre-1", "prompt": prompt, "choices": choices, "correct_answer": answer, "lesson_external_id": UNIT}


@pytest.mark.parametrize(
    ("prompt", "choices", "picked"),
    [
        ("Tu ___ à Paris cette semaine ?", ["es", "est", "êtes"], "est"),
        ("Tu ___ à l'hôtel ?", ["es", "suis", "sont"], "suis"),
    ],
    ids=["tu-est", "tu-suis"],
)
def test_tu_choice(prompt: str, choices: list[str], picked: str) -> None:
    hint = _withheld("fill", _choice(prompt, choices, "es"), picked)["hint"]
    assert hint == PERSON_HINT, f"«{picked}» for «es» was not told to look at the person: {hint!r}"


def test_nous_ils_keep_hint() -> None:
    nous = _choice("Nous ___ à la rédaction avec Lila.", ["sommes", "êtes", "sont"], "sommes")
    ils = _choice("Ils ___ à la poste.", ["sont", "est", "sommes"], "sont")
    assert _withheld("fill", nous, "êtes")["hint"] == PERSON_HINT
    assert _withheld("fill", ils, "est")["hint"] == PERSON_HINT


@pytest.mark.parametrize(
    ("key", "built", "drill"),
    [
        ("Tu es à la rédaction ?", "Tu est à la rédaction ?", "tiles"),
        ("Tu es italienne ?", "Tu est italienne ?", "dictation"),
    ],
    ids=["tiles", "dictee"],
)
def test_tu_build(key: str, built: str, drill: str) -> None:
    """The walk of 28 Nov: the tile build and the dictée of the same slip."""

    words = key.replace("?", " ?").split()
    item = {
        "id": "etre-b",
        "prompt": "Bau den Satz.",
        "answer_tokens": words,
        "tokens": [*words, "est"],
        "correct_answer": key,
        "lesson_external_id": UNIT,
    }
    hint = _withheld("word_bank", item, built, drill=drill)["hint"]
    assert "Schau, wer es tut" in hint, f"{drill}: the person hint was scrubbed: {hint!r}"


def _served(hint: str, picked: str, answer: str, language: str) -> str:
    """What ``learner_view`` serves of a stored hint while the solution waits."""

    erratum = {"item_id": "etre-1", "learner_text": picked, "corrected_target": answer, "hint": hint, "why_wrong": "", "repair_hint": ""}
    correction = solution_gate.mark(
        {"verdict": "incorrect", "errata": [erratum], "corrected_answer": answer}, chance=True, language=language
    )
    view = solution_gate.learner_view(correction, answer_payload={"answers": {"etre-1": picked}})
    return view["errata"][0]["hint"]


def test_quoted_dropped() -> None:
    named = "Mit «tu» heißt «être» «es», nicht «est»."
    assert _served(f"{named} {PERSON_HINT}", "est", "es", "de") == PERSON_HINT
    assert "es»" not in _served(named, "est", "es", "de")
    assert "„es“" not in _served("Mit tu heißt être „es“.", "est", "es", "de")


@pytest.mark.parametrize("quoted", ["'es'", "‚es‘", "‘es’"], ids=["straight", "low", "curly"])
def test_single_quotes(quoted: str) -> None:
    """Verify of #1094: single quotes are quotes too; the person hint after it stays."""

    served = _served(f"Mit tu nimmt man {quoted}. {PERSON_HINT}", "est", "es", "de")
    assert "nimmt man" not in served, f"the answer was shown in {quoted}: {served!r}"
    assert served == PERSON_HINT


def test_elision_no_quote() -> None:
    """«l'hôtel» is no quote: the German «es» after it stays German."""

    hint = "Im Satz über l'hôtel: schau, wer es tut."
    assert _served(hint, "est", "es", "de") == hint


def test_unquoted_leaks() -> None:
    """A word that is no German word («sommes») leaks quoted or not; a French or English
    hint keeps the strict reading for words of French («es» in a French sentence)."""

    assert "sommes" not in _served("Nimm hier sommes.", "êtes", "sommes", "de")
    assert "dit es" not in _served("Avec tu, on dit es.", "est", "es", "fr")
    assert "es" not in _served("With tu, être is es.", "est", "es", "en").split()
