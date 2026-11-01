"""#196 (re-test 31 Oct): no English task text reaches a French or German learner in La Forge.

Walk 29 Oct (b1-fr, French chrome): for «Deux pronoms ensemble» La Forge asked «A friend
asks for one concrete update about today. Answer in French with one complete sentence.»
and then «Message received: « Qu'est-ce qui se passe ? » Reply naturally in French.».
Every rule without its own task got these English fallback tasks (and an English
paragraph task), whatever the chrome language; La Forge serves its items through
``item_bank.public_item`` only, so their instruction stayed English too.

The tasks are now ``learner_copy`` rows. The stored ``prompt`` stays the English column
(what the grader reads), the item carries the task in every chrome language
(``prompt_l10n``), and a set cached before #196 is re-read from its stored text when it
is served.
"""
from __future__ import annotations

import re

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import item_bank as ib
from app.services.atelier import AtelierExerciseGenerator, _is_vague_output_prompt
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_V2_VERSION, catalog_rows
from app.services.grammar_feedback import infer_grammar_profile
from app.services.learner_copy import (
    FALLBACK_PROMPT_KEYS,
    LEARNER_COPY,
    fallback_prompt_key,
    learner_text,
)

ROUNDS = ("sentence", "speak", "conversation")

#: Words only an English sentence has (no German or French task text does).
ENGLISH = re.compile(
    r"\b(?:the|you|your|is|are|asks|what|with|and|answer|reply|write|say|give|french|sentence|"
    r"today|about|that|which|when|one|received|naturally|colleague|friend|yesterday|tomorrow)\b",
    re.IGNORECASE,
)
#: The French a task quotes («Message reçu : « Qu’est-ce qui se passe ? » …») is what the
#: learner answers, in every chrome: it is left out of every check below.
QUOTED = re.compile(r"«[^»]*»")

#: What a set cached before #196 holds, byte for byte (the old code's strings).
STORED_BEFORE = {
    "atelier.fallback.prompt.generic.sentence": "A friend asks for one concrete update about today. Answer in French with one complete sentence.",
    "atelier.fallback.prompt.generic.speak": "Ton amie demande : « Quel est ton programme pour demain matin ? » Donne une activité et une heure précises.",
    "atelier.fallback.prompt.generic.conversation": "Message received: « Qu'est-ce qui se passe ? » Reply naturally in French.",
    "atelier.fallback.prompt.tense_aspect.sentence": "Yesterday a friend asks why you arrived late. Explain what was happening and what happened in one French sentence.",
    "atelier.fallback.prompt.si_present_result_form.conversation": "Message received: « S'il pleut demain, on fait quoi ? » Reply with a real condition and its consequence.",
    "atelier.fallback.prompt.article_after_negation.speak": "At a cafe, someone asks what is available. Say one missing item with ne...pas de/d'.",
    "atelier.fallback.produce.tense_aspect": "A friend asks what happened yesterday when your plans changed. Write a short French note that contrasts the background scene with the completed events.",
    "atelier.fallback.produce.generic": (
        "A friend asks for a short update about today's plan. Write a French note with concrete details, "
        "making this pattern visible: subject + me/te/se/nous/vous + le/la/les + lui/leur + y + en + verb"
    ),
}


def _catalogue() -> list[GrammarConcept]:
    """Every rule the product serves (the v2 catalogue, 206 units)."""

    return [
        GrammarConcept(
            id=70000 + index,
            external_id=row["external_id"],
            name=row["name"],
            level=row["level"],
            category=row["category"],
            subskill=row["subskill"],
            description=row["description"],
            core_rule=row["core_rule"],
            main_traps=row["main_traps"],
            anchor_examples=row["anchor_examples"],
            exercise_tags=row["exercise_tags"],
        )
        for index, row in enumerate(catalog_rows(FRENCH_CORE_CATALOG_V2_VERSION), start=1)
    ]


def _english_in(text: str) -> list[str]:
    return ENGLISH.findall(QUOTED.sub(" ", text))


def _copy_column(language: str) -> set[str]:
    return {LEARNER_COPY[key][language] for key in FALLBACK_PROMPT_KEYS}


def _tasks(payload: dict) -> list[tuple[str, dict]]:
    out = [(round_name, item) for round_name in ROUNDS for item in payload["output_ladder"][round_name]["items"]]
    return [*out, ("produce", payload["produce"])]


def test_the_walk_covers_every_family_of_fallback_task() -> None:
    families = {infer_grammar_profile(concept).key for concept in _catalogue()}
    assert {"tense_aspect", "si_present_result_form", "article_after_negation"} <= families
    assert len(_catalogue()) >= 200


@pytest.mark.parametrize("language", ["fr", "de"])
def test_every_rules_fallback_tasks_reach_the_learner_in_their_chrome_language(db_session, language: str) -> None:
    """The guard the issue asks for: every rule's fallback set, as La Forge serves it."""

    generator = AtelierExerciseGenerator(db_session)
    column = _copy_column(language)
    problems: list[str] = []
    checked = 0
    for concept in _catalogue():
        served = ib.public_payload(generator._fallback_payload(concept), language)
        for round_name, task in _tasks(served):
            checked += 1
            prompt = str(task.get("prompt") or "")
            if prompt not in column:
                problems.append(f"{concept.external_id} {round_name}: not localized copy: {prompt!r}")
            for field in ("prompt", "instruction"):
                english = _english_in(str(task.get(field) or ""))
                if english:
                    problems.append(f"{concept.external_id} {round_name} {field}: English {english}: {task.get(field)!r}")
            table = task.get("prompt_l10n") or {}
            if "en" in table:
                problems.append(f"{concept.external_id} {round_name}: the English column was served")
    assert checked >= 200 * 4
    assert problems == [], "\n".join(problems[:15])


def test_an_english_learner_still_reads_the_english_task(db_session) -> None:
    generator = AtelierExerciseGenerator(db_session)
    concept = next(c for c in _catalogue() if c.external_id == "FR2_B11_DOUBLE_PRONOUNS")
    payload = generator._fallback_payload(concept)
    served = ib.public_payload(payload, "en")
    for round_name, task in _tasks(served):
        key = f"atelier.fallback.prompt.generic.{round_name}" if round_name in ROUNDS else "atelier.fallback.produce.generic"
        assert task["prompt"] == LEARNER_COPY[key]["en"], round_name
    # The stored prompt is the English column (the grader reads it), and the item
    # carries every column.
    stored = payload["output_ladder"]["sentence"]["items"][0]
    assert stored["prompt"] == STORED_BEFORE["atelier.fallback.prompt.generic.sentence"]
    assert set(stored["prompt_l10n"]) == {"en", "de", "fr"}
    assert stored["prompt_l10n"]["en"] == stored["prompt"]


@pytest.mark.parametrize("language", ["fr", "de", "en"])
def test_a_set_cached_before_the_fix_is_read_in_the_learners_language(language: str) -> None:
    """Sets are generated once and shared: the rows already stored hold the old text and no table."""

    for key, stored in STORED_BEFORE.items():
        assert fallback_prompt_key(stored) == key, stored
        if key.startswith("atelier.fallback.produce."):
            node = {"prompt": stored, "requirements": [{"concept_id": 1}], "source_fragment": "Je le lui donne."}
            served = ib.public_payload({"produce": node}, language)["produce"]
        else:
            item = {
                "id": "x-fallback-sentence",
                "type": "short_sentence",
                "instruction": "Use the target grammar visibly in your answer.",
                "prompt": stored,
            }
            served = ib.public_item(item, language)
            assert served["instruction"] == learner_text("atelier.fallback.output_instruction", language)
        assert served["prompt"] == learner_text(key, language), (key, served["prompt"])


def test_a_model_task_and_a_french_sentence_are_left_alone() -> None:
    for prompt in (
        "Ton collègue te dit : « Je viendrai au dîner si je finis tard. » Réponds en une phrase.",
        "Je le lui donne.",
        "A friend asks for one concrete update about today.",
    ):
        assert fallback_prompt_key(prompt) is None
        item = {"id": "m-1", "type": "short_sentence", "prompt": prompt}
        assert ib.public_item(item, "fr")["prompt"] == prompt
        assert "prompt_l10n" not in ib.public_item(item, "fr")


def test_a_vague_model_task_is_replaced_by_the_localized_fallback(db_session) -> None:
    generator = AtelierExerciseGenerator(db_session)
    concept = next(c for c in _catalogue() if c.external_id == "FR2_B11_DOUBLE_PRONOUNS")
    payload = generator._fallback_payload(concept)
    payload["produce"] = {"prompt": "Write a short paragraph using the target grammar.", "prompt_l10n": {"en": "stale"}}
    for round_name in ROUNDS:
        payload["output_ladder"][round_name]["items"][0] = {
            "type": "short_sentence",
            "prompt": "Write one sentence using the target grammar.",
        }
    normalized = generator._normalize_llm_exercise_payload(concept, payload)
    served = ib.public_payload(normalized, "fr")
    assert served["produce"]["prompt"] == learner_text("atelier.fallback.produce.generic", "fr")
    for round_name in ROUNDS:
        item = served["output_ladder"][round_name]["items"][0]
        assert item["prompt"] == learner_text(f"atelier.fallback.prompt.generic.{round_name}", "fr"), round_name


@pytest.mark.parametrize("key", FALLBACK_PROMPT_KEYS)
def test_the_task_copy_says_tu_in_french_and_du_in_german(key: str) -> None:
    french = QUOTED.sub(" ", LEARNER_COPY[key]["fr"])
    assert not re.search(r"\b(?:vous|votre|vos)\b", french, re.IGNORECASE), french
    imperatives = set(re.findall(r"\b\w+ez\b", french.lower())) - {"chez", "assez"}
    assert not imperatives, french
    german = QUOTED.sub(" ", LEARNER_COPY[key]["de"])
    assert not re.search(r"\b(?:Sie|Ihnen|Ihr|Ihre|Ihren)\b", german), german
    assert not _english_in(LEARNER_COPY[key]["de"]) and not _english_in(LEARNER_COPY[key]["fr"]), key


@pytest.mark.parametrize("key", FALLBACK_PROMPT_KEYS)
def test_every_fallback_task_is_concrete_enough_for_the_generator(key: str) -> None:
    """The generator replaces a vague model task with these: they must not be vague themselves."""

    assert not _is_vague_output_prompt(LEARNER_COPY[key]["en"]), key


def test_the_forge_speak_instruction_says_tu() -> None:
    assert ib.INSTRUCTIONS_L10N["forge.speak"]["fr"] == "Dis-le en français."
