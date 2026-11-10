"""#562 — La Forge reads a missing accent one way, on every judge (root cause #174).

A gap item took «etes» and «le musee» as right and said nothing; a sentence item
sent «Israel» (key «Israël») to «not checked». The keyed rungs and the model's
relecture already read an accent through :func:`answer_acceptance.judge`; the gap's
note was dropped and the free answer's instant check compared strictly. Every judge
now asks the one function, and an accent-only difference is right, named, and
printed with its accent.
"""

from __future__ import annotations

import pytest

from app.services import forge_grading as grading
from app.services.atelier import AtelierCorrectionService


def _gap(db_session, prompt: str, key: str, typed: str, language: str = "de") -> dict:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    item = {"id": "g1", "prompt": prompt, "correct_answer": key}
    return service.correct(
        concept=None,
        round_name="recognize",
        mode="fill",
        exercise_id="X:fill:g1",
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"g1": typed}},
    )


@pytest.mark.parametrize(
    ("prompt", "key", "typed", "accented"),
    [
        ("Vous ___ à Toulouse cette semaine ?", "êtes", "etes", "êtes"),
        ("Où est ___ ?", "le musée", "le musee", "musée"),
    ],
    ids=["etes", "musee"],
)
def test_gap_without_accent_right_and_named(db_session, prompt, key, typed, accented):
    correction = _gap(db_session, prompt, key, typed)
    assert correction["verdict"] == "correct", correction
    assert correction["assessment_status"] == "checked"
    assert correction["errata"] == []
    assert correction["corrected_answer"]["g1"] == key, "the sentence is printed with its accent"
    assert any(f"«{accented}»" in note for note in correction["notes_native"]), correction["notes_native"]


def test_a_gap_answered_with_its_accent_has_no_accent_note(db_session):
    correction = _gap(db_session, "Vous ___ à Toulouse cette semaine ?", "êtes", "êtes")
    assert correction["verdict"] == "correct"
    assert correction["notes_native"] == []


def _sentence(db_session, typed: str, accepted: list[str], language: str = "de") -> dict:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service.correct(
        concept=None,
        round_name="sentence",
        mode="sentence",
        exercise_id="forge:1:sentence:s1",
        prompt_payload={"items": [{"id": "s1", "accepted_answers": accepted}]},
        answer_payload={"text": typed},
    )


def test_sentence_without_accent_right_and_named(db_session, monkeypatch):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    key = ["Elles sont en Israël cette semaine.", "Ils sont en Israël cette semaine."]
    correction = _sentence(db_session, "Ils sont en Israel cette semaine.", key)
    assert correction["verdict"] == "correct", correction
    assert correction["assessment_status"] == "checked", "no model is needed to read an accent"
    assert correction["local_status"] == grading.LOCAL_RIGHT
    assert correction["corrected_answer"] == "Ils sont en Israël cette semaine."
    assert any("«Israël»" in note for note in correction["notes_native"]), correction["notes_native"]


def test_a_grammar_accent_in_a_sentence_is_not_right_on_the_spot(db_session, monkeypatch):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    correction = _sentence(db_session, "Elle a mange une pomme.", ["Elle a mangé une pomme."])
    assert correction["verdict"] != "correct", correction
