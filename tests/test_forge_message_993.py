"""#993 - a La Forge item that asks the learner to answer a French message holds that message.

Live walk 22 Nov 2026, La Forge item 4 of 9 («Un, une, des»): «Your friend asks in French what
you want for breakfast.» / «Write one sentence answering the text; use an indefinite article
before the food item.» and no French line anywhere: the learner answered a text that was never
shown. Other items of the same séance quote the question («The baker asks: « Vous voulez
combien de pâtisseries ? »»).

ROOT CAUSE (#146, #542): the situation guard (``scenario_problems``) checked who asks whom and
how the learner is addressed, never that a task which promises a message carries one. So the
generator kept the set, and La Forge served its stored item as it was.
"""
from __future__ import annotations

import pytest

from app.core.forge import Rung
from app.services.atelier import AtelierExerciseGenerator
from app.services.exercise_generation import validate_atelier_generation_payload
from app.services.forge import PayloadItemProvider
from tests.services.test_atelier_validation import _concept, _payload

WALK_PROMPT = "Your friend asks in French what you want for breakfast."
WALK_INSTRUCTION = "Write one sentence answering the text; use an indefinite article before the food item."
QUOTED_PROMPT = "Your friend asks: « Tu veux quoi pour le petit-déjeuner ? »"


def _with(db_session, round_name: str, prompt: str, instruction: str | None = None):
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    assert AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept) == []
    if round_name == "produce":
        payload["produce"]["prompt"] = prompt
    else:
        item = payload["output_ladder"][round_name]["items"][0]
        item["prompt"] = prompt
        if instruction is not None:
            item["instruction"] = instruction
    return concept, payload


@pytest.mark.parametrize("round_name", ["sentence", "speak", "conversation", "produce"])
def test_a_task_that_answers_a_message_it_does_not_show_is_refused(db_session, round_name: str) -> None:
    concept, payload = _with(db_session, round_name, WALK_PROMPT, WALK_INSTRUCTION)
    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)
    assert any("message" in error for error in errors), (
        f"the set was kept with «{WALK_PROMPT}» and no French message on screen: {errors}"
    )
    assert any("message" in error for error in validate_atelier_generation_payload(payload)), (
        "the generator's own validator kept the item that answers no message"
    )


@pytest.mark.parametrize("round_name", ["sentence", "conversation"])
def test_the_instruction_alone_can_promise_the_message(db_session, round_name: str) -> None:
    """«answering the text» in the instruction, over a prompt that quotes nothing."""

    concept, payload = _with(db_session, round_name, "Your friend wants to know what you eat in the morning.", WALK_INSTRUCTION)
    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)
    assert any("message" in error for error in errors), errors


@pytest.mark.parametrize("round_name", ["sentence", "speak", "conversation", "produce"])
def test_a_task_that_quotes_the_message_is_kept(db_session, round_name: str) -> None:
    concept, payload = _with(db_session, round_name, QUOTED_PROMPT, WALK_INSTRUCTION)
    assert AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept) == []
    assert validate_atelier_generation_payload(payload) == []


@pytest.mark.parametrize(
    "prompt",
    [
        "Write a short message in French to your friend about your breakfast.",
        "A friend asks what you will do if it rains tomorrow. Say one natural si + present answer.",
        "À la boulangerie, la vendeuse te dit : « Vous désirez ? » Réponds-lui.",
    ],
)
def test_a_task_that_promises_no_message_is_not_touched(prompt: str) -> None:
    from app.services.forge_item_validator import message_problems

    assert message_problems(prompt, "Write one sentence.") == []


def test_a_stored_set_never_serves_the_item_without_its_message() -> None:
    """A set stored before the guard still holds the walk's item: La Forge poses the next one."""

    payload = {
        "output_ladder": {
            "sentence": {
                "items": [
                    {"id": "s1", "type": "short_sentence", "prompt": WALK_PROMPT, "instruction": WALK_INSTRUCTION},
                    {"id": "s2", "type": "short_sentence", "prompt": QUOTED_PROMPT, "instruction": WALK_INSTRUCTION},
                ]
            },
        },
    }
    served = PayloadItemProvider({1: payload}).item_for(concept_id=1, rung=Rung.PRODUCE, exclude=set())
    assert served is not None
    assert served.item_id == "s2", (
        f"La Forge posed «{served.payload.get('prompt')}» / «{served.payload.get('instruction')}»: "
        "a text to answer that is not on screen"
    )


def test_no_authored_task_promises_a_message_it_does_not_show() -> None:
    """The item builders' own words (the fallback tasks, the curated scenes, the bank's cues)
    never promise a French message without quoting it."""

    from pathlib import Path

    from app.services.forge_item_validator import message_problems
    from app.services.item_bank import _CUES
    from app.services.learner_copy import LEARNER_COPY

    texts = [text for row in LEARNER_COPY.values() for text in row.values() if isinstance(text, str)]
    texts += Path("app/data/seance_challenges.txt").read_text(encoding="utf-8").splitlines()
    texts += [text for row in _CUES.values() for text in (row.values() if isinstance(row, dict) else [row]) if isinstance(text, str)]
    assert len(texts) > 100
    assert [text for text in texts if message_problems(text)] == []
