"""#1088: La Forge accepted «J ai» as «Richtig» without naming the apostrophe, and its end
sheet printed «Margaux demande ton âge. J ai trente-cinq ans.» as what the séance proved.

Explore walk 26 Nov 2026 (``a1-de-fresh``, day 2, Avoir, Stufe 3). Typed gap «Ergänze den
Satz: „Margaux fragt, wie alt du bist. Ich bin 35 Jahre alt.“ Margaux demande ton âge. ___
trente-cinq ans.». The grader reads an apostrophe typed as a space as typography and
accepts «J ai» for «J'ai»; nothing named what it forgave (an accent is named, #562), and
``_forge_proof_line`` printed the accepted spelling, not the accepted form.

What the grader forgives is told and stored in its right spelling: «J ai» is right with a
note naming the apostrophe, and the end sheet prints «J'ai trente-cinq ans.».
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.atelier import AtelierCorrectionService, AtelierSRSService
from tests.gold_transcripts.surfaces import make_concept

UNIT = "FR2_A11_AVOIR"
ITEM = {
    "id": "avoir-age",
    "prompt": "Margaux demande ton âge. ___ trente-cinq ans.",
    "meaning": "Margaux fragt, wie alt du bist. Ich bin 35 Jahre alt.",
    "correct_answer": "J'ai",
    "accepted_answers": ["J'ai"],
    "target_span": "J'ai",
    "lesson_external_id": UNIT,
}

#: The apostrophe, named in each explanation language.
APOSTROPHE = {"en": "apostrophe", "de": "Apostroph", "fr": "apostrophe"}


def _grade(answer: str, language: str) -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    return service._correct_recognize(
        make_concept(UNIT), "fill", {"items": [dict(ITEM)]}, {"answers": {ITEM["id"]: answer}}
    )


@pytest.mark.parametrize("language", ["de", "en", "fr"])
def test_j_ai_without_its_apostrophe_is_right_and_the_apostrophe_is_named(language: str) -> None:
    result = _grade("J ai", language)
    assert result["verdict"] == "correct", result["errata"]
    notes = " ".join(result.get("feedback_notes_native") or [])
    assert APOSTROPHE[language] in notes, f"«J ai» was accepted and nothing named the apostrophe: {notes!r}"
    assert "J'ai" in notes, notes
    # The card's «you were right up to …» flag (#562) is set for this item.
    assert any(note.get("item_id") == ITEM["id"] for note in result.get("accent_notes") or []), result


def test_the_right_spelling_says_nothing_more() -> None:
    result = _grade("J'ai", "de")
    assert result["verdict"] == "correct"
    assert not result.get("feedback_notes_native"), result


def _proof(answer: str) -> tuple[str, bool] | None:
    result = _grade(answer, "de")
    attempt = SimpleNamespace(
        correction_payload={**result, "assessment_status": "checked"},
        verdict=result["verdict"],
        prompt_payload={"items": [dict(ITEM)]},
        answer_payload={"answers": {ITEM["id"]: answer}},
        round="recognize",
        mode="fill",
    )
    return AtelierSRSService._forge_proof_line(attempt)


def test_the_end_sheet_prints_the_accepted_form_not_the_typed_spelling() -> None:
    assert _proof("J ai") == ("Margaux demande ton âge. J'ai trente-cinq ans.", False)


def test_the_end_sheet_keeps_a_right_answer_typed_right_and_a_miss_shows_the_key() -> None:
    assert _proof("J'ai") == ("Margaux demande ton âge. J'ai trente-cinq ans.", False)
    assert _proof("Je suis") == ("Margaux demande ton âge. J'ai trente-cinq ans.", True)
