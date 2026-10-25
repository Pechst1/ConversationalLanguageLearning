"""#335 «Find the mistake»: the sentence the learner built is what is judged.

«Margaux aime la huile d'olive.» had its «la» tapped and «l'» typed into a field
that held «la» with the caret at its end: the word became «lal'» and the card said
«Well done». The field now opens with the word selected (the browser test
web-frontend/components/epreuve/forge-spot-field.test.js); this is the other half,
that a sentence built with «lal'» in it is a miss and only the stored fix is right.
The page sends the whole sentence with an elision joined (spotAnswer).
"""

from __future__ import annotations

import dataclasses

import pytest

from app.services.atelier import AtelierCorrectionService
from app.services.item_bank import default_bank, transform_item

SOURCE = "Margaux aime la huile d'olive."
ANSWER = "Margaux aime l'huile d'olive."


def _item() -> dict:
    base = default_bank().generate("FR2_A11_LE_LA", 1, seed=3)[0]
    item = dataclasses.replace(base, sentence=ANSWER, wrong_sentences=(SOURCE,), traps=("la huile",))
    payload = transform_item(item)
    assert payload is not None
    return payload


def _verdict(learner: str) -> str:
    item = _item()
    correction = AtelierCorrectionService(None)._correct_transform_rule_based(
        None, {"items": [item]}, {"answers": {item["id"]: learner}}
    )
    return str(correction["verdict"])


def test_the_card_asks_for_two_words_and_the_stored_fix_is_the_elided_line() -> None:
    item = _item()
    assert item["fix_words"] == 2
    assert item["expected_answer"] == ANSWER


@pytest.mark.parametrize(
    "built",
    [
        "Margaux aime lal'huile d'olive.",  # «la» + «l'» typed after it, joined by the page
        "Margaux aime lal' huile d'olive.",
        "Margaux aime l'la huile d'olive.",
        "Margaux aime la huile d'olive.",  # nothing fixed
        "Margaux aime l'l'huile d'olive.",
    ],
)
def test_a_sentence_built_with_a_leftover_word_is_a_miss(built: str) -> None:
    assert _verdict(built) == "incorrect", built


@pytest.mark.parametrize(
    "built",
    [
        "Margaux aime l'huile d'olive.",  # «la» → «l'», «huile» left as it was
        "Margaux aime l' huile d'olive.",
        "margaux aime l'huile d'olive",
    ],
)
def test_the_stored_fix_is_right(built: str) -> None:
    assert _verdict(built) == "correct", built
