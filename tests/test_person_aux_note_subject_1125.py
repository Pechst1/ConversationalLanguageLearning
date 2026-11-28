"""#1125: the basic check's FR_PERSON_AUX note names the subject, not the word before the verb.

Walk of 28 Nov 2026 (a1-de-fresh, day 2, Journal retell): «Je lui a dit que je ne vend pas
tout de suite le appartement.» was fixed «lui a» → «lui ai» with the note «Nach « lui »
heißt es « ai », nicht « a ».». The fix is right; the reason taught a false rule: «ai» is
needed because the subject is «je» («il lui a dit» is right). #1114 taught the person to
look past «ne» and the object pronouns, but the note was still filled with the token right
before the verb.
"""
from __future__ import annotations

import pytest

from app.services.correction_contract import deterministic_edits

WALK = "Je lui a dit que je ne vend pas tout de suite le appartement."


def _person_notes(text: str) -> list[dict[str, str]]:
    return [edit.note for edit in deterministic_edits(text) if edit.rule_id == "FR_PERSON_AUX"]


@pytest.mark.parametrize(
    ("text", "subject", "not_named"),
    [
        (WALK, "je", "lui"),
        ("Je les a vus.", "je", "les"),
        ("Il lui ai dit.", "il", "lui"),
        ("Je n a pas faim.", "je", "n"),
        ("Je vous a appelé hier.", "je", "vous"),
        ("Elle leur ai parlé.", "elle", "leur"),
    ],
)
def test_the_note_names_the_resolved_subject(text: str, subject: str, not_named: str) -> None:
    notes = _person_notes(text)
    assert notes, f"no FR_PERSON_AUX edit for «{text}»"
    for note in notes:
        assert note["de"].startswith(f"Nach « {subject} »"), f"«{text}»: {note['de']}"
        assert note["en"].startswith(f"After « {subject} »"), f"«{text}»: {note['en']}"
        assert note["fr"].startswith(f"Après « {subject} »"), f"«{text}»: {note['fr']}"
        for lang in ("de", "en", "fr"):
            assert f"« {not_named} »" not in note[lang], f"«{text}» names «{not_named}»: {note[lang]}"


def test_the_walk_line_reads_je() -> None:
    notes = _person_notes(WALK)
    assert [note["de"] for note in notes] == ["Nach « je » heißt es « ai », nicht « a »."]


def test_je_ne_a_is_one_elided_fix_with_no_ne_in_a_person_note() -> None:
    edits = deterministic_edits("Je ne a pas faim.")
    assert [(e.span, e.replacement) for e in edits] == [("ne a", "n'ai")]
    for edit in edits:
        if edit.rule_id == "FR_PERSON_AUX":
            assert "« ne »" not in edit.note["de"], edit.note


@pytest.mark.parametrize(
    ("text", "note"),
    [
        ("Tu est là.", "Nach « tu » heißt es « es », nicht « est »."),
        ("Nous êtes ici.", "Nach « nous » heißt es « sommes », nicht « êtes »."),
    ],
)
def test_the_plain_subject_notes_stay(text: str, note: str) -> None:
    assert [n["de"] for n in _person_notes(text)] == [note]
