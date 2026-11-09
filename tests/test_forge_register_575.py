"""#575 - La Forge speaks to the learner in one register, the one setting's.

Live walk 7 Nov 2026: item 7 «Ta sœur te montre sa nouvelle chambre… Décris-la» (tu), item 8
«Votre sœur vous demande où se trouve votre clé. Que lui dites-vous ? Répondez par une phrase
complète.» (vous): the same sister, the same learner, minutes apart.

ROOT CAUSE: the situation of a Forge item is written by the model, and the guard on it
(`situation_problems`) knew who asks whom and what a price is a price of, but not how the app
addresses the learner. The model was never told the setting (`address.LEARNER_ADDRESS`) either,
so each item chose its own register. #144 closed with the UI strings and the templates only.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.address import LEARNER_ADDRESS, address_instruction
from app.services.atelier import AtelierExerciseGenerator
from app.services.exercise_generation import (
    ExerciseGenerationService,
    ExerciseGenerationUnavailable,
    validate_atelier_generation_payload,
)
from tests.services.test_atelier_validation import _concept, _payload

ITEM_7 = "Ta sœur te demande comment est ta nouvelle chambre. Décris-la-lui."
ITEM_8 = (
    "Votre sœur vous demande où se trouve votre clé. Que lui dites-vous ? "
    "Répondez par une phrase complète."
)
QUOTED = "À la boulangerie, la vendeuse te dit : « Vous désirez ? » Réponds-lui."


def _with_prompt(db_session, round_name: str, prompt: str) -> tuple[object, dict]:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    assert AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept) == []
    if round_name == "produce":
        payload["produce"]["prompt"] = prompt
    else:
        payload["output_ladder"][round_name]["items"][0]["prompt"] = prompt
    return concept, payload


@pytest.mark.parametrize("round_name", ["sentence", "speak", "conversation", "produce"])
def test_a_vous_item_is_refused_when_the_setting_is_tu(db_session, round_name: str) -> None:
    assert LEARNER_ADDRESS["fr"] == "tu"
    concept, payload = _with_prompt(db_session, round_name, ITEM_8)
    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)
    assert any("tu" in error and "vous" in error for error in errors), errors
    assert validate_atelier_generation_payload(payload) != [], "the generator's own validator agrees"


@pytest.mark.parametrize("round_name", ["sentence", "speak", "conversation", "produce"])
def test_a_tu_item_and_a_quoted_character_line_are_kept(db_session, round_name: str) -> None:
    for prompt in (ITEM_7, QUOTED):
        concept, payload = _with_prompt(db_session, round_name, prompt)
        assert AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept) == [], prompt
        assert validate_atelier_generation_payload(payload) == [], prompt


def test_the_model_is_told_the_setting(db_session) -> None:
    """The scenario generator reads the register from the one setting, in its own prompt."""

    seen: list[str] = []

    class Llm:
        def generate_chat_completion(self, messages, *, system_prompt="", **kwargs):
            seen.append(system_prompt)
            return SimpleNamespace(content="not json", provider="stub", model="stub")

    concept = _concept(db_session, "FR_A2_NEG_001")
    with pytest.raises(ExerciseGenerationUnavailable):
        ExerciseGenerationService(db_session, llm_service=Llm()).generate_atelier_exercise(
            concept=concept, user=None, target_vocabulary=[]
        )
    assert seen, "the model was not called"
    assert address_instruction("fr") in seen[0]


def test_the_curated_scenes_all_say_tu() -> None:
    """The cause was shared: the authored fallback scenes (55 of them) said «Vous décrivez…
    Répondez…» too, and are what a learner gets when the model is unavailable."""

    from pathlib import Path

    from app.services.forge_item_validator import address_problems

    lines = Path("app/data/seance_challenges.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 50
    for line in lines:
        external_id, _marked, scene = line.split("|")
        assert address_problems(scene) == [], f"{external_id}: {scene}"
