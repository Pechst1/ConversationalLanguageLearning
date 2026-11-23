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
def test_unshown_message_refused(db_session, round_name: str) -> None:
    concept, payload = _with(db_session, round_name, WALK_PROMPT, WALK_INSTRUCTION)
    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)
    assert any("message" in error for error in errors), (
        f"the set was kept with «{WALK_PROMPT}» and no French message on screen: {errors}"
    )
    assert any("message" in error for error in validate_atelier_generation_payload(payload)), (
        "the generator's own validator kept the item that answers no message"
    )


@pytest.mark.parametrize("round_name", ["sentence", "conversation"])
def test_instruction_promise(db_session, round_name: str) -> None:
    """«answering the text» in the instruction, over a prompt that quotes nothing."""

    concept, payload = _with(db_session, round_name, "Your friend wants to know what you eat in the morning.", WALK_INSTRUCTION)
    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)
    assert any("message" in error for error in errors), errors


@pytest.mark.parametrize("round_name", ["sentence", "speak", "conversation", "produce"])
def test_quoted_message_kept(db_session, round_name: str) -> None:
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
    ids=["write-a-message", "told-not-quoted", "french-quoted"],
)
def test_no_promise_kept(prompt: str) -> None:
    from app.services.forge_item_validator import message_problems

    assert message_problems(prompt, "Write one sentence.") == []


def test_stored_item_skipped() -> None:
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


def test_authored_tasks_clean() -> None:
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


def _built_items(payload: dict) -> list[tuple[str, object, object]]:
    """(round, prompt, instruction) of every task a fallback set poses."""

    built = [
        (round_name, item.get("prompt"), item.get("instruction"))
        for round_name in ("sentence", "speak", "conversation")
        for item in (payload.get("output_ladder") or {}).get(round_name, {}).get("items") or []
    ]
    produce = payload.get("produce") or {}
    return [*built, ("produce", produce.get("prompt"), produce.get("instruction"))]


def test_curated_cue_answers_a_shown_message() -> None:
    """Attempt 1's review: three curated scenes ask the learner to *put* a question
    («Quelle question lui poses-tu avec est-ce que ?»), and their free-use cue said
    «Réponds au message …»: a message to answer that no screen shows."""

    from app.services.seance_curriculum import curriculum
    from tests.test_seance_contract import concept_for

    unshown = []
    for key in curriculum():
        payload = AtelierExerciseGenerator(None)._fallback_payload(concept_for(key))
        for round_name, prompt, instruction in _built_items(payload):
            promises = "au message" in str(instruction or "") or "answering the text" in str(instruction or "")
            if promises and "«" not in str(prompt or ""):
                unshown.append(f"{key} {round_name}: «{prompt}» / «{instruction}»")
    assert unshown == [], f"a curated task answers a message it does not show: {unshown}"


def test_builders_promise_no_unshown_message(db_session) -> None:
    """The done-when's «test over the item builders»: the real fallback set of every
    catalog rule (each curated lesson, each generic family) and every fallback task row
    paired with the instruction it is served with, in every chrome language."""

    from app.db.models.grammar import GrammarConcept
    from app.services.forge_item_validator import message_problems
    from app.services.learner_copy import LEARNER_COPY

    _concept(db_session, "FR_A2_NEG_001")  # seeds the catalog
    concepts = db_session.query(GrammarConcept).all()
    assert len(concepts) > 50
    found = []
    for concept in concepts:
        payload = AtelierExerciseGenerator(db_session)._fallback_payload(concept)
        for round_name, prompt, instruction in _built_items(payload):
            if message_problems(prompt, instruction):
                found.append(f"{concept.external_id} {round_name}: «{prompt}» / «{instruction}»")
    cue = LEARNER_COPY["atelier.fallback.output_instruction"]
    for key, row in LEARNER_COPY.items():
        if key.startswith(("atelier.fallback.prompt.", "atelier.fallback.produce.")):
            for language, text in row.items():
                if message_problems(text, cue.get(language)):
                    found.append(f"{key} [{language}]: «{text}» / «{cue.get(language)}»")
    assert found == [], found


def test_retired_cue_read_as_served() -> None:
    """A stored set still carries the retired cue «Answer the message in French, with the
    rule of the day.», which the learner is served as «Write it in French, with this rule.»:
    its free-use item answers no message and stays in the séance (review of attempt 1)."""

    payload = {
        "output_ladder": {
            "conversation": {
                "items": [
                    {
                        "id": "c1",
                        "type": "conversation_turn",
                        "prompt": "A friend asks for one concrete update about today.",
                        "instruction": "Answer the message in French, with the rule of the day.",
                    },
                ]
            },
        },
    }
    served = PayloadItemProvider({1: payload}).item_at(concept_id=1, rung=Rung.FREE_USE, exclude=set())
    assert served is not None and served.item_id == "c1", "the conversation rung went empty"
