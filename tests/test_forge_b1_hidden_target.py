"""Walk of 21 Nov 2026, finding 1: La Forge's own-sentence card at B1 refused correct French
on all 14 days, against a meaning the French screen never showed.

An English learner at B1 reads French chrome: the «say» card shows «Écris une courte phrase
à toi en français, avec cette règle.» and no meaning. Since R4 (19 Nov) the correction is
explained in the mother tongue, so ``explanation_language`` is ``en`` for that learner, and
the grader took it for the language of the screen: it handed the model the stored English
«Say in French: "…candles…"» and the model refused the day-6 sentence for not being about
candles. What the grader is told the card asked is decided by the language the screen was
in (the chrome), never by the language the reason is written in.

No model is called: the model's reading is the note the walk logged.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.services import item_bank as ib
from app.services.atelier import AtelierCorrectionService
from tests.gold_transcripts.surfaces import make_concept

PRONOUNS = "FR2_A22_PRONOUN_POSITION"
DOUBLE_PRONOUNS = "FR2_B11_DOUBLE_PRONOUNS"
REQUIREMENT = {"label": "Deux pronoms ensemble : je le lui donne", "external_id": DOUBLE_PRONOUNS, "target_count": 1}

#: The walk's day-6 card: its model line and the meaning the screen never showed.
MODEL = "Tes parents n'ont plus de bougies ? Je leur en apporte samedi."
MEANING = "Your parents have no candles left? I'm bringing them some on Saturday."
MEANING_DE = "Deine Eltern haben keine Kerzen mehr? Ich bringe ihnen am Samstag welche."
#: What the learner wrote on day 6: correct French, two pronouns together, not about candles.
DAY6 = "Romy veut la clé, mais je ne la lui donne pas encore parce que je ne la connais pas."
#: The note the model wrote (``b-d06-forge-hidden-prompt``).
WALK_NOTE = {
    "item_id": "x",
    "learner_text": DAY6,
    "corrected_target": "",
    "why_wrong": "Your sentence is grammatical and uses two pronouns, but it does not express the requested message about candles.",
    "task_error_type": "task_compliance",
}


def _card(*, german: bool = False) -> dict:
    base = ib.default_bank().generate(PRONOUNS, 1, seed="walk-1121")[0]
    item = replace(
        base,
        sentence=MODEL,
        en=MEANING,
        de=MEANING_DE if german else None,
        prefix="Tes parents n'ont plus de bougies ? Je ",
        target="leur en",
        suffix=" apporte samedi.",
        accepted=(MODEL,),
    )
    card = ib.output_item(item, round_name="sentence", requirement=REQUIREMENT)
    assert card is not None and card["type"] == "short_sentence"
    return card


def _service(*, chrome: str, explanation: str, native: str) -> AtelierCorrectionService:
    """The correction service as ``submit_attempt`` sets it for one learner."""

    service = AtelierCorrectionService.__new__(AtelierCorrectionService)
    service.explanation_language = explanation
    service._learner_chrome = chrome
    service._learner_native = native
    service._answer_truncated = False
    return service


def _graded(service: AtelierCorrectionService, card: dict, text: str, reading: dict) -> tuple[dict, dict]:
    concept = make_concept(DOUBLE_PRONOUNS)
    sent: dict = {}

    def fake_llm(**kwargs):
        sent.update(kwargs)
        return dict(reading)

    service._get_llm_service = lambda: object()
    service._correction_system_prompt = lambda: "system"
    service._llm_correction = fake_llm
    service._count_hits = lambda requirement, line: 0
    payload = {"round": "sentence", "items": [card]}
    fallback = service._correct_output_ladder_rule_based(concept, "sentence", payload, {"text": text})
    graded = service._correct_output_ladder_with_llm(concept, "sentence", payload, {"text": text}, fallback)
    return graded, sent


def test_the_walk_day6_sentence_at_b1_in_french_chrome_is_not_refused_for_the_hidden_meaning():
    """B1, English mother tongue, French chrome: the screen asked for a sentence of the
    learner's own with the rule, so that is all the grader is told and all it may require."""

    card = _card()
    service = _service(chrome="fr", explanation="en", native="en")
    asked = service._compact_llm_task({"items": [card]})["items"][0]
    assert asked.get("own_sentence") is True
    assert "candles" not in asked["prompt"] and "Say in French" not in asked["prompt"]
    assert "expected_answer" not in asked

    reading = {"verdict": "partial", "score_0_4": 2.0, "errata": [WALK_NOTE], "corrected_answer": DAY6}
    graded, sent = _graded(service, card, DAY6, reading)
    assert "candles" not in sent["messages"][0]["content"]
    assert graded["verdict"] in {"correct", "accepted"}
    assert not [item for item in graded["errata"] if item.get("task_error_type") == "task_compliance"]


@pytest.mark.parametrize(
    ("chrome", "explanation", "native", "german"),
    [
        ("en", "en", "en", False),  # A1/A2 English screen: «Say in French: "…"»
        ("de", "de", "de", True),  # A1/A2 German screen with a German meaning: «Sag auf Französisch: „…“»
    ],
)
def test_a_screen_that_quoted_the_meaning_keeps_it_as_the_task(chrome, explanation, native, german):
    asked = _service(chrome=chrome, explanation=explanation, native=native)._compact_llm_task(
        {"items": [_card(german=german)]}
    )["items"][0]
    assert "own_sentence" not in asked


@pytest.mark.parametrize(("explanation", "native"), [("de", "de"), ("en", "en"), ("fr", "fr")])
def test_every_french_screen_is_graded_as_an_own_sentence_whatever_the_mother_tongue(explanation, native):
    """B1 and above read French chrome in every mother tongue; even with a German meaning
    stored, the French screen does not quote it."""

    asked = _service(chrome="fr", explanation=explanation, native=native)._compact_llm_task(
        {"items": [_card(german=True)]}
    )["items"][0]
    assert asked.get("own_sentence") is True
    assert "candles" not in asked["prompt"] and "Kerzen" not in asked["prompt"]


def test_a_german_screen_without_a_german_meaning_is_an_own_sentence():
    asked = _service(chrome="de", explanation="de", native="de")._compact_llm_task({"items": [_card()]})["items"][0]
    assert asked.get("own_sentence") is True
