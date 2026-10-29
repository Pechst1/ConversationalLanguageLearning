"""#369 (root cause #250): a correction note is checked against the form it explains.

Live walk 29 Oct: «aujourdhui» -> «aujourd'hui» was explained as «an accent on « hui »».
The form has no accent anywhere. The note was the model's raw words; nothing compared it
with the corrected form. No model call is made in this file.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract as contract

APOSTROPHE_NOTE = "The standard spelling includes an apostrophe and an accent on « hui »"


def test_a_note_that_names_an_accent_the_form_lacks_is_replaced_by_one_from_the_form():
    assert not contract.note_matches_form("aujourdhui", "aujourd'hui", APOSTROPHE_NOTE)
    note = contract.note_for_form("aujourdhui", "aujourd'hui", APOSTROPHE_NOTE, language="en")
    assert "apostrophe" in note.casefold()
    assert "accent" not in note.casefold()
    assert "« hui »" not in note


@pytest.mark.parametrize(
    ("span", "fix", "note"),
    [
        ("cafe", "café", "Add an acute accent on the final « e »."),
        ("ecole", "école", "The first letter takes an accent: « é »."),
        ("garcon", "garçon", "Use a cedilla: « ç » before « o »."),
        ("aujourdhui", "aujourd'hui", "Add the apostrophe after « aujourd »."),
        ("un voiture", "une voiture", "voiture is feminine, so the article is « une »."),
        ("Je sui", "Je suis", "The ending « s » is missing."),
        ("a Paris", "à Paris", "Il faut un accent grave sur « à »."),
    ],
)
def test_a_note_that_matches_its_form_is_kept_as_written(span, fix, note):
    assert contract.note_matches_form(span, fix, note)
    assert contract.note_for_form(span, fix, note, language="en") == note


def test_an_accent_claim_on_a_pair_that_adds_no_accent_falls_back_to_what_changed():
    claim = "Needs an accent on « une »."
    assert not contract.note_matches_form("un voiture", "une voiture", claim)
    note = contract.note_for_form("un voiture", "une voiture", claim, language="en")
    assert "accent" not in note.casefold()
    assert note


def test_a_quoted_letter_that_is_not_in_the_corrected_form_is_a_wrong_note():
    # «the letter « ç »» when the fix has none
    assert not contract.note_matches_form("cafe", "café", "Use the cedilla: « ç ».")


def test_the_journal_and_the_scene_turn_use_the_same_note_check():
    text = "Gus, aujourdhui j ai écrit une carte."
    kept = contract.grounded_errata(
        text,
        [
            {
                "learner_text": "aujourdhui",
                "corrected_target": "aujourd'hui",
                "why_wrong": APOSTROPHE_NOTE,
                "repair_hint": APOSTROPHE_NOTE,
            }
        ],
        language="en",
    )
    assert len(kept) == 1
    assert "accent" not in f"{kept[0]['why_wrong']} {kept[0]['repair_hint']}".casefold()
    span, fix, note = contract.first_valid_edit(
        text, "aujourdhui", "aujourd'hui", APOSTROPHE_NOTE, language="en"
    )
    assert (span, fix) == ("aujourdhui", "aujourd'hui")
    assert note
    assert "accent" not in note.casefold()
