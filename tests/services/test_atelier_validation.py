"""Focused validation tests for generated Atelier exercise payloads."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierExerciseGenerator, AtelierScheduler


FIXTURE_PATH = Path("tests/fixtures/atelier_bad_word_banks.json")


def _concept(db_session, external_id: str) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


def _payload(concept: GrammarConcept) -> dict:
    return {
        "recognize": {
            "fill": {
                "items": [
                    {"id": "fill-1", "prompt": "Je ne bois pas ____ café.", "choices": ["de", "du", "un"], "correct_answer": "de"},
                    {"id": "fill-2", "prompt": "Ce n'est pas ____ café.", "choices": ["du", "de", "un"], "correct_answer": "du"},
                    {"id": "fill-3", "prompt": "Elle n'a pas ____ idée.", "choices": ["d'", "une", "de la"], "correct_answer": "d'"},
                ]
            },
            "word_bank": {
                "items": [
                    {
                        "id": "wb-good-1",
                        "prompt": "Build the full French sentence.",
                        "meaning_cue": "Express: I do not drink coffee.",
                        "tokens": ["pas", "de", "Je", "café", "ne", "bois", "du"],
                        "answer_tokens": ["Je", "ne", "bois", "pas", "de", "café"],
                        "correct_answer": "Je ne bois pas de café",
                    },
                    {
                        "id": "wb-good-2",
                        "prompt": "Build the full French sentence.",
                        "meaning_cue": "Express: It is not coffee.",
                        "tokens": ["du", "pas", "Ce", "café", "n'est", "de"],
                        "answer_tokens": ["Ce", "n'est", "pas", "du", "café"],
                        "correct_answer": "Ce n'est pas du café",
                    },
                    {
                        "id": "wb-good-3",
                        "prompt": "Build the full French sentence.",
                        "meaning_cue": "Express: She does not have an idea.",
                        "tokens": ["n'a", "pas", "Elle", "d'idée", "une"],
                        "answer_tokens": ["Elle", "n'a", "pas", "d'idée"],
                        "correct_answer": "Elle n'a pas d'idée",
                    },
                ]
            },
            "classify": {
                "items": [
                    {"id": "classify-1", "prompt": "pas de café", "labels": ["article changes", "être exception"], "correct_label": "article changes", "correct_answer": "article changes"},
                    {"id": "classify-2", "prompt": "Ce n'est pas du café", "labels": ["article changes", "être exception"], "correct_label": "être exception", "correct_answer": "être exception"},
                    {"id": "classify-3", "prompt": "pas d'idée", "labels": ["article changes", "être exception"], "correct_label": "article changes", "correct_answer": "article changes"},
                ]
            },
        },
        "transform": {
            "items": [
                {"id": "transform-1", "type": "directed_rewrite", "instruction": "Change 'du' to 'de' after pas.", "source": "Je bois du café.", "expected_answer": "Je ne bois pas de café."},
                {"id": "transform-2", "type": "contrast_rewrite", "instruction": "Keep 'du' after n'est pas for the être exception.", "source": "C'est du café.", "expected_answer": "Ce n'est pas du café."},
                {"id": "transform-3", "type": "repair_rewrite", "instruction": "Change 'une' to d' after pas.", "source": "Elle n'a pas une idée.", "expected_answer": "Elle n'a pas d'idée."},
            ]
        },
        "produce": {
            "source_fragment": "Le comptoir est presque vide.",
            "prompt": "A roommate asks what supplies are missing before shopping. Write a short French note naming what you do not have.",
            "requirements": [{"label": concept.name, "target_count": 1}],
            "min_words": 40,
            "max_words": 100,
        },
        "output_ladder": {
            "sentence": {"items": [_output_item("sentence", concept, "Je n'ai pas de dossier aujourd'hui.")]},
            "speak": {"items": [_output_item("speak", concept, "Nous n'avons pas de café.")]},
            "conversation": {"items": [_output_item("conversation", concept, "Je ne vois pas de métro ici.")]},
        },
    }


def _output_item(item_id: str, concept: GrammarConcept, example: str) -> dict:
    kind = {
        "sentence": "short_sentence",
        "speak": "spoken_response",
        "conversation": "conversation_turn",
    }[item_id]
    return {
        "id": item_id,
        "type": kind,
        "instruction": "Use the target grammar visibly.",
        "prompt": {
            "sentence": "A friend asks what food or drink is left at home today. Say one thing you do not have.",
            "speak": "At a cafe, someone asks what is available. Say one missing item with ne...pas de/d'.",
            "conversation": "Message received: « Tu as encore du café ? » Reply with a negated quantity.",
        }[item_id],
        "example_answer": example,
        "requirements": [{"label": concept.name, "target_count": 1}],
        "min_words": 5,
        "max_words": 24,
    }


def test_payload_validation_accepts_full_sentence_word_bank_and_etre_exception(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")

    assert AtelierExerciseGenerator._payload_validation_errors(_payload(concept), concept=concept) == []


def test_payload_validation_rejects_known_bad_word_bank_fixture(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert {"wb1", "wb2", "wb3"}.issubset({row["item_id"] for row in fixture})
    payload = _payload(concept)
    payload["recognize"]["word_bank"]["items"] = [
        {
            "id": "wb1",
            "prompt": "Build the sentence with ___.",
            "meaning_cue": "Express: I do not drink coffee.",
            "tokens": ["Je", "ne", "bois", "pas", "de", "café"],
            "answer_tokens": ["Je", "ne", "bois", "pas", "de", "café"],
            "correct_answer": "Je ne bois pas de café",
        },
        {
            "id": "wb2",
            "prompt": "Build the full French sentence.",
            "meaning_cue": "Express: I do not drink coffee.",
            "tokens": ["Je", "ne", "bois", "pas", "café"],
            "answer_tokens": ["Je", "ne", "bois", "pas", "de", "café"],
            "correct_answer": "Je ne bois pas de café",
        },
        {
            "id": "wb3",
            "prompt": "Build the full French sentence.",
            "meaning_cue": "Express: de café de.",
            "tokens": ["de", "café", "de"],
            "answer_tokens": ["de", "café", "de"],
            "correct_answer": "de café de",
        },
    ]

    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    assert any("wb1" in error and "blank" in error for error in errors)
    assert any("wb2" in error and "not available" in error for error in errors)
    assert any("wb3" in error and "complete sentence" in error for error in errors)


def test_payload_validation_rejects_correct_answer_that_does_not_match_tokens(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    payload["recognize"]["word_bank"]["items"][0]["correct_answer"] = "Je bois du café"

    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    assert any("correct_answer must match answer_tokens" in error for error in errors)


def test_payload_validation_rejects_ambiguous_directed_rewrite(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    payload["transform"]["items"][0]["instruction"] = "Rewrite this sentence correctly."

    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    assert any("directed_rewrite" in error and "source word" in error for error in errors)


def test_payload_validation_rejects_generic_classify_labels_before_ai_critic(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _payload(concept)
    payload["recognize"]["classify"]["items"][0]["labels"] = ["affirmative", "negative"]
    payload["recognize"]["classify"]["items"][0]["correct_label"] = "negative"

    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    assert any("classify-1" in error and "generic labels" in error for error in errors)


def test_payload_validation_rejects_duplicate_adjacent_answer_tokens_before_ai_critic(db_session) -> None:
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = deepcopy(_payload(concept))
    item = payload["recognize"]["word_bank"]["items"][0]
    item["tokens"] = ["Je", "ne", "ne", "bois", "pas", "de", "café", "du"]
    item["answer_tokens"] = ["Je", "ne", "ne", "bois", "pas", "de", "café"]
    item["correct_answer"] = "Je ne ne bois pas de café"

    errors = AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    assert any("wb-good-1" in error and "duplicated adjacent" in error for error in errors)
