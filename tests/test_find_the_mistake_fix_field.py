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


# -- #395: the miss sheet shows the learner's own line, and blames only wrong words --

HAT_SOURCE = "On n'a pas un chapeau, Gus."
HAT_ANSWER = "On n'a pas de chapeau, Gus."


def _hat_miss(built: str) -> dict:
    base = default_bank().generate("FR2_A11_LE_LA", 1, seed=3)[0]
    item = dataclasses.replace(base, sentence=HAT_ANSWER, wrong_sentences=(HAT_SOURCE,), traps=("pas un",))
    payload = transform_item(item)
    assert payload is not None
    correction = AtelierCorrectionService(None)._correct_transform_rule_based(
        None, {"items": [payload]}, {"answers": {payload["id"]: built}}
    )
    assert correction["verdict"] == "incorrect"
    return correction["errata"][0]


@pytest.mark.parametrize(
    "built",
    [
        "On n'a pas d'chapeau, Gus.",  # «un» → «d'», the page joins the elision to the next word
        "On n'a pas d' chapeau, Gus.",
    ],
    ids=["elided", "spaced"],
)
def test_miss_shows_own_line(built: str) -> None:
    erratum = _hat_miss(built)

    # Case, punctuation and order are the learner's own, and nothing is spliced in twice.
    assert erratum["learner_text"] == built, "the struck-through line is the learner's own"
    assert erratum["corrected_target"] == HAT_ANSWER


@pytest.mark.parametrize(
    "built", ["On n'a pas d'chapeau, Gus.", "On n'a pas d' chapeau, Gus."], ids=["elided", "spaced"]
)
def test_no_right_word_blamed(built: str) -> None:
    from app.services.forge_grading import tokens

    erratum = _hat_miss(built)
    why = erratum["why_wrong"]
    wrong = [op["learner"] for op in erratum.get("diff") or [] if op.get("learner")]

    assert "«d'»" in why and "«de»" in why, why
    assert "chapeau" not in wrong, erratum.get("diff")
    assert "does not belong" not in why, why
    # The guard: no word named as wrong is a word the target line holds.
    assert not {word for word in wrong if word in tokens(HAT_ANSWER)}, wrong


def test_a_word_that_only_moved_is_not_called_extra() -> None:
    from app.services.forge_grading import describe_diff, token_diff

    ops = token_diff("Gus a un chapeau très beau", "Gus a un très beau chapeau")
    assert not [op for op in ops if op["kind"] == "extra" and op["learner"] in {"chapeau", "très", "beau"}], ops
    assert "does not belong" not in describe_diff(ops, "en")


def test_a_real_surplus_copy_is_still_extra() -> None:
    from app.services.forge_grading import token_diff

    ops = token_diff("Gus a un un chapeau", "Gus a un chapeau")
    assert [op["learner"] for op in ops if op["kind"] == "extra"] == ["un"], ops
