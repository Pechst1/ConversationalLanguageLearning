"""#919: a scene reply with three slips showed one correction.

Live walk 19 Nov (A1.1, day 37): «Je ne sais pas ce que est Solvel, mais je pense que c
est une entreprise dangereux. Je suis allé au usine hier.» got one card, «c'est une
entreprise dangereuse». «ce que est» (ce qu'est) and «au usine» (à l'usine) were left
unmarked. The Courrier and the Journal add the model-free pass to the model's list
(``correction_contract.merge_deterministic_errata``); the scene used that pass only when
the model kept nothing, and then cut the list to one below B1.

Pinned with the tutor's live answer stubbed (no model):

* the model-free pass finds «que est» and «au usine» in the exact sentence;
* the scene's tutor verdict lists the model's correction and the basic check's two, at
  A1, and the turn shows the first with the other two under it;
* the basic check's edits never touch a word the model's correction already covers.
"""

from __future__ import annotations

import pytest

from app.services import correction_contract
from app.services import story_lanes as lanes

ISSUE_TEXT = (
    "Je ne sais pas ce que est Solvel, mais je pense que c est une entreprise dangereux. "
    "Je suis allé au usine hier."
)

#: What the tutor answered live: one correction, the agreement.
MODEL_AGREEMENT = {
    "span_fr": "c est une entreprise dangereux",
    "corrected_fr": "c'est une entreprise dangereuse",
    "note_native": "« entreprise » is feminine, so the adjective is feminine too: « dangereuse ».",
    "rule_id": None,
}


def _payload(text: str, *, level: str = "A1") -> dict:
    return {
        "learner_text": text,
        "history": [],
        "scene": {},
        "story": {
            "learner": {"address": "neutral"},
            "level": level,
            "commitments": [],
            "control_language": "en",
        },
        "targets": [],
        "turn_plan": {},
    }


def _verdict(*corrections: dict) -> lanes.TutorVerdict:
    return lanes.TutorVerdict.model_validate(
        {"outcome": "met", "evidence_quotes": ["je pense que c est une entreprise dangereux"],
         "corrections": list(corrections)}
    )


def _pairs(edits) -> list[tuple[str, str]]:
    return [(e.span, e.replacement) for e in edits]


def test_the_basic_check_finds_que_est_and_au_usine_in_the_issue_sentence():
    pairs = _pairs(correction_contract.deterministic_edits(ISSUE_TEXT))

    assert ("que est", "qu'est") in pairs
    assert ("au usine", "à l'usine") in pairs


@pytest.mark.parametrize("level", ["A1", "A2", "B1"])
def test_the_scene_lists_the_models_correction_and_the_basic_checks(level):
    verdict = _verdict(MODEL_AGREEMENT)
    lanes.validate_tutor(verdict, _payload(ISSUE_TEXT, level=level))

    shown = [(c.span_fr, c.corrected_fr) for c in verdict.corrections]
    assert shown[0] == ("c est une entreprise dangereux", "c'est une entreprise dangereuse"), shown
    assert ("que est", "qu'est") in shown, f"«ce que est» left unmarked: {shown}"
    assert ("au usine", "à l'usine") in shown, f"«au usine» left unmarked: {shown}"
    # «c est» is inside the model's span: the basic check does not mark it twice.
    assert ("c est", "c'est") not in shown
    assert all(c.note_native for c in verdict.corrections)
    assert verdict.correction_span_fr == "c est une entreprise dangereux"


def test_the_turn_shows_the_first_and_the_basic_checks_under_it():
    verdict = _verdict(MODEL_AGREEMENT)
    lanes.validate_tutor(verdict, _payload(ISSUE_TEXT))
    correction = lanes.turn_correction(verdict, ISSUE_TEXT)

    assert correction.corrected_fr == "c'est une entreprise dangereuse"
    assert sorted(c.corrected_fr for c in correction.more) == ["qu'est", "à l'usine"]


def test_a_model_that_kept_nothing_still_gets_every_basic_check_edit():
    verdict = _verdict()
    lanes.validate_tutor(verdict, _payload(ISSUE_TEXT))

    shown = [(c.span_fr, c.corrected_fr) for c in verdict.corrections]
    assert ("que est", "qu'est") in shown
    assert ("au usine", "à l'usine") in shown
    assert ("c est", "c'est") in shown


def test_a_reply_the_check_finds_nothing_in_keeps_the_models_one():
    text = "Je pense que c'est une entreprise dangereux."
    verdict = _verdict({**MODEL_AGREEMENT, "span_fr": "entreprise dangereux",
                        "corrected_fr": "entreprise dangereuse"})
    lanes.validate_tutor(verdict, _payload(text))

    assert [c.corrected_fr for c in verdict.corrections] == ["entreprise dangereuse"]


@pytest.mark.parametrize(
    "text",
    [
        "Je vais au cinéma avec Odile.",
        "Il est au hasard de la rue.",  # h aspiré: «au hasard» stays
        "On se voit au Opéra ce soir.",  # a name, capitalised: left to the model
        "Je suis au-dessus du café.",
        "Il parle du haut de la tour.",  # h aspiré
        "Je pense que oui.",
        "Ce qu'est Solvel, je ne sais pas.",
    ],
)
def test_correct_or_unsure_french_gets_no_new_edit(text):
    rules = {e.rule_id for e in correction_contract.deterministic_edits(text)}
    pairs = _pairs(correction_contract.deterministic_edits(text))

    assert "FR_ELIDED_ARTICLE" not in rules, pairs
    assert not any(span.casefold().startswith("que ") for span, _ in pairs), pairs


@pytest.mark.parametrize(
    ("text", "span", "fixed"),
    [
        ("Je vais au école demain.", "au école", "à l'école"),
        ("Je bois un verre du eau.", "du eau", "de l'eau"),
        ("Il travaille au hôpital.", "au hôpital", "à l'hôpital"),
        ("Je sais ce que était le problème.", "que était", "qu'était"),
    ],
)
def test_more_slips_of_the_same_kind(text, span, fixed):
    assert (span, fixed) in _pairs(correction_contract.deterministic_edits(text))
