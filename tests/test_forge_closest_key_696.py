"""#696: a La Forge fill miss is diffed against the closest accepted answer.

Walk of 11 Nov 2026 (persona a2-en, «Passé composé with avoir»): «They sent a
message to Romy last night, Gus.» keys «Elles ont envoyé» and also accepts «Ils ont
envoyé». The learner typed «Ils ont envoye»: the right subject, the participle's
accent missing — the day's own rule (-er → -é). The card answered «this item needs
“Elles ont envoyé” … read the English line again», and the erratum was stored as
«Ils ont envoye → Elles ont envoyé», so the review would later ask to change a
correct «Ils».

The grader picked the key it measured the miss against by ranking a miss without
an accent slip above a miss with one, so the farther key («Elles», a whole word
away) beat the nearer one («Ils ont envoyé», an accent away).
"""

from __future__ import annotations

import pytest

from app.services import item_bank as ib
from app.services.answer_acceptance import judge
from app.services.atelier import AtelierCorrectionService

PC_AVOIR = "FR2_A21_PC_AVOIR"


def _concept():
    from app.db.models.grammar import GrammarConcept

    return GrammarConcept(id=39, external_id=PC_AVOIR, name="Passé composé with avoir", level="A2", category="Grammar")


@pytest.fixture(scope="module")
def sent_a_message() -> dict:
    bank = ib.default_bank()
    for seed in range(600):
        for item in bank.generate(PC_AVOIR, 12, seed=seed):
            if item.sentence.startswith("Elles ont envoyé un message à Romy"):
                payload = ib.fill_item(item, lesson_external_id=PC_AVOIR)
                assert payload is not None
                assert payload["correct_answer"] == "Elles ont envoyé"
                assert "Ils ont envoyé" in payload["accepted_answers"]
                assert payload["meaning"].startswith("They sent")
                return payload
    raise AssertionError("no «Elles ont envoyé un message à Romy» item in the bank")


def _grade(item: dict, answer: str, language: str = "en") -> dict:
    service = AtelierCorrectionService(None)
    service.explanation_language = language
    return service._correct_recognize(_concept(), "fill", {"items": [item]}, {"answers": {item["id"]: answer}})


def test_an_accent_slip_on_an_accepted_answer_is_measured_against_that_answer(sent_a_message: dict) -> None:
    result = _grade(sent_a_message, "Ils ont envoye")
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    assert erratum["corrected_target"] == "Ils ont envoyé", erratum
    assert result["corrected_answer"][sent_a_message["id"]] == "Ils ont envoyé"
    why = erratum["why_wrong"]
    assert "Elles" not in why, why
    assert "the rule is not what differs" not in why.lower(), why
    assert "read the english line again" not in erratum["repair_hint"].lower(), erratum["repair_hint"]
    assert "«envoyé», not «envoye»" in why, why


def test_the_named_accent_is_in_the_learners_language(sent_a_message: dict) -> None:
    [erratum] = _grade(sent_a_message, "Ils ont envoye", language="de")["errata"]
    assert erratum["corrected_target"] == "Ils ont envoyé"
    assert "«envoyé», nicht «envoye»" in erratum["why_wrong"], erratum["why_wrong"]


def test_the_key_still_answers_a_miss_that_is_closest_to_it(sent_a_message: dict) -> None:
    [erratum] = _grade(sent_a_message, "Elles ont envoyer")["errata"]
    assert erratum["corrected_target"] == "Elles ont envoyé"
    [erratum] = _grade(sent_a_message, "Elles ont envoye")["errata"]
    assert erratum["corrected_target"] == "Elles ont envoyé"


def test_judge_measures_a_miss_against_the_nearest_accepted_answer() -> None:
    """The shared grader: among misses, an accent away beats a word away."""

    verdict = judge("Ils ont envoye", ["Elles ont envoyé", "Ils ont envoyé"], accents="strict", typo=False)
    assert not verdict.correct
    assert verdict.expected == "Ils ont envoyé"
    assert verdict.note == "accent"
    assert (verdict.learner_word, verdict.expected_word) == ("envoye", "envoyé")


def test_a_rewrite_miss_is_measured_against_the_nearest_accepted_rewrite() -> None:
    """The same cause on the rewrite rung: its erratum and diff came from the stored key."""

    service = AtelierCorrectionService(None)
    service.explanation_language = "en"
    item = {
        "id": "t1",
        "type": "directed_rewrite",
        "instruction": "Put the line in the passé composé.",
        "source": "Elles envoient un message à Romy.",
        "expected_answer": "Elles ont envoyé un message à Romy.",
        "accepted_answers": ["Ils ont envoyé un message à Romy."],
    }
    result = service._correct_transform_rule_based(
        _concept(), {"items": [item]}, {"answers": {"t1": "Ils ont envoye un message à Romy."}}
    )
    assert result["verdict"] == "incorrect"
    [erratum] = result["errata"]
    assert erratum["corrected_target"] == "Ils ont envoyé un message à Romy.", erratum
    assert "Elles" not in erratum["why_wrong"], erratum["why_wrong"]
    assert "«envoyé», not «envoye»" in erratum["why_wrong"], erratum["why_wrong"]


def test_judge_still_prefers_a_clean_accept_over_an_accent_accept() -> None:
    verdict = judge("ils ont envoye", ["Ils ont envoye", "Ils ont envoyé"], accents="lenient", typo=False)
    assert verdict.correct and verdict.exact
