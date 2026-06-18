"""Regression tests for the Atelier practice system."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.core.error_detection.rules import DetectedError
from app.core.security import decode_token
from app.db.models.atelier import (
    AtelierAttempt,
    AtelierCollectible,
    AtelierConceptBlueprint,
    AtelierExerciseSet,
    AtelierGenerationEvent,
    AtelierLanguagePack,
    AtelierSession,
)
from app.db.models.error import UserError, UserErrorConcept
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.error_memory import ErrorMemoryService
from app.services.atelier import (
    ATELIER_EXERCISE_RESPONSE_FORMAT,
    ATELIER_GENERATOR_VERSION,
    AtelierCorrectionService,
    AtelierExerciseGenerator,
    AtelierSRSService,
    AtelierScheduler,
    select_atelier_vocabulary,
)
from app.services.atelier_assets import AtelierAssetService
from app.services.atelier_rewards import AtelierRewardService
from app.services.grammar_feedback import count_concept_hits
from app.services.llm_service import LLMProviderError, LLMResult


def _user(db_session) -> User:
    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        hashed_password="test",
        target_language="fr",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _concept(db_session, external_id: str) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


def _clear_exercise_sets(db_session, concept: GrammarConcept) -> None:
    db_session.query(AtelierExerciseSet).filter(AtelierExerciseSet.concept_id == concept.id).delete()
    db_session.commit()


def _prime_exercise_set(db_session, concept: GrammarConcept) -> None:
    _test_generated_payload(db_session, concept)


def _prime_llm_exercise_set(db_session, concept: GrammarConcept) -> AtelierExerciseSet:
    return AtelierExerciseGenerator(
        db_session,
        llm_service=_FakeLLMService(_raw_llm_payload(concept)),
    ).get_or_create(concept)


def _attach_primed_exercise_set(db_session, session: AtelierSession, concept: GrammarConcept) -> AtelierExerciseSet:
    exercise_set = _prime_llm_exercise_set(db_session, concept)
    quote_payload = dict(session.quote_payload or {})
    exercise_set_ids = dict(quote_payload.get("exercise_set_ids") or {})
    exercise_set_ids[str(concept.id)] = str(exercise_set.id)
    quote_payload["exercise_set_ids"] = exercise_set_ids
    session.quote_payload = quote_payload
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return exercise_set


def _prime_core_exercise_sets(db_session) -> None:
    AtelierScheduler(db_session).ensure_catalog()
    concepts = (
        db_session.query(GrammarConcept)
        .filter(
            GrammarConcept.external_id.in_(
                ["FR_B1_COND_001", "FR_B1_TENSE_001", "FR_A2_NEG_001"]
            )
        )
        .all()
    )
    for concept in concepts:
        _prime_llm_exercise_set(db_session, concept)


def _fill(item_id: str, prompt: str, choices: list[str], answer: str) -> dict:
    return {"id": item_id, "prompt": prompt, "choices": choices, "correct_answer": answer}


def _bank(item_id: str, prompt: str, answer_tokens: list[str]) -> dict:
    joined = " ".join(answer_tokens).replace(" ,", ",")
    meaning_cue = prompt.replace("Build:", "Express:").strip()
    if not meaning_cue or meaning_cue == prompt or "sentence" in meaning_cue.lower():
        meaning_cue = "Express the target meaning as a complete French sentence."
    distractor = "autrement"
    if "répondrai" in joined:
        distractor = "répondrais"
    elif "arriverons" in joined:
        distractor = "arrivons"
    elif "partirons" in joined:
        distractor = "partons"
    elif "mange" in answer_tokens:
        distractor = "mangeras"
    elif "prends" in answer_tokens:
        distractor = "prendras"
    elif "de" in answer_tokens:
        distractor = "du"
    elif "du" in answer_tokens:
        distractor = "de"
    elif any(str(token).startswith("d'") for token in answer_tokens):
        distractor = "une"
    elif "marchais" in answer_tokens:
        distractor = "marcherai"
    elif "a" in answer_tokens and "ouvert" in answer_tokens:
        distractor = "ouvrait"
    return {
        "id": item_id,
        "prompt": prompt,
        "meaning_cue": meaning_cue,
        "tokens": [*reversed(answer_tokens), distractor],
        "answer_tokens": answer_tokens,
        "correct_answer": joined,
    }


def _classify(item_id: str, prompt: str, labels: list[str], answer: str) -> dict:
    return {
        "id": item_id,
        "prompt": prompt,
        "labels": labels,
        "correct_label": answer,
        "correct_answer": answer,
    }


def _transform(item_id: str, kind: str, instruction: str, source: str, expected: str) -> dict:
    return {
        "id": item_id,
        "type": kind,
        "instruction": instruction,
        "source": source,
        "expected_answer": expected,
    }


def _output_item(item_id: str, kind: str, concept: GrammarConcept, prompt: str, example: str) -> dict:
    return {
        "id": item_id,
        "type": kind,
        "instruction": "Write a concise French answer using the target grammar.",
        "prompt": prompt,
        "example_answer": example,
        "requirements": [{"label": concept.name, "target_count": 1}],
        "min_words": 5,
        "max_words": 24,
    }


def _raw_llm_payload(concept: GrammarConcept) -> dict:
    external_id = concept.external_id or ""
    if external_id == "FR_B1_TENSE_001":
        return {
            "recognize": {
                "fill": {
                    "items": [
                        _fill("tense-fill-1", "Hier, je ____ quand elle est arrivee.", ["marchais", "ai marche", "marcherai"], "marchais"),
                        _fill("tense-fill-2", "Soudain, il ____ la porte.", ["ouvrait", "a ouvert", "ouvrira"], "a ouvert"),
                        _fill("tense-fill-3", "Tous les dimanches, nous ____ au marche.", ["allions", "sommes alles", "irons"], "allions"),
                    ]
                },
                "word_bank": {
                    "items": [
                        _bank("tense-bank-1", "Build the sentence.", ["Je", "marchais", "quand", "une", "voiture", "est", "passée"]),
                        _bank("tense-bank-2", "Build the sentence.", ["Il", "faisait", "froid", ",", "puis", "nous", "sommes", "entrés"]),
                        _bank("tense-bank-3", "Build the sentence.", ["Elle", "attendait", "quand", "j'ai", "répondu"]),
                    ]
                },
                "classify": {
                    "items": [
                        _classify("tense-classify-1", "marchais", ["background", "bounded event"], "background"),
                        _classify("tense-classify-2", "a ouvert", ["background", "bounded event"], "bounded event"),
                        _classify("tense-classify-3", "allions", ["habit", "single event"], "habit"),
                    ]
                },
            },
            "transform": {
                "items": [
                    _transform("tense-transform-1", "directed_rewrite", "Change 'pleut' to imparfait and 'sors' to passé composé.", "Il pleut quand je sors.", "Il pleuvait quand je suis sorti."),
                    _transform("tense-transform-2", "contrast_rewrite", "Turn the habit into one completed event.", "Je lisais souvent ce livre.", "J'ai lu ce livre hier."),
                    _transform("tense-transform-3", "repair_rewrite", "Repair the tense contrast.", "Je suis fatigué quand le téléphone sonnait.", "J'étais fatigué quand le téléphone a sonné."),
                ]
            },
            "produce": {
                "source_fragment": "Un matin, la ville etait calme.",
                "prompt": "Write a short paragraph contrasting background and events.",
                "requirements": [{"label": concept.name, "target_count": 2}],
                "min_words": 50,
                "max_words": 120,
            },
            "output_ladder": {
                "sentence": {"items": [_output_item("tense-sentence", "short_sentence", concept, "Describe a background interrupted by an event.", "Je marchais quand une voiture est passée.")]},
                "speak": {"items": [_output_item("tense-speak", "spoken_response", concept, "Say what was happening when something changed.", "Je lisais quand il est entré.")]},
                "conversation": {"items": [_output_item("tense-conversation", "conversation_turn", concept, "Answer with one background and one completed event.", "Il faisait froid, puis nous sommes entrés.")]},
            },
        }
    if external_id == "FR_A2_NEG_001":
        return {
            "recognize": {
                "fill": {
                    "items": [
                        _fill("neg-fill-1", "Je ne bois pas ____ café.", ["de", "du", "un"], "de"),
                        _fill("neg-fill-2", "Ce n'est pas ____ café.", ["de", "du", "des"], "du"),
                        _fill("neg-fill-3", "Elle n'a pas ____ idée.", ["d'", "une", "de la"], "d'"),
                    ]
                },
                "word_bank": {
                    "items": [
                        _bank("neg-bank-1", "Build the sentence.", ["Je", "n'ai", "pas", "de", "café"]),
                        _bank("neg-bank-2", "Build the sentence.", ["Ce", "n'est", "pas", "du", "café"]),
                        _bank("neg-bank-3", "Build the sentence.", ["Elle", "n'a", "pas", "d'idée"]),
                    ]
                },
                "classify": {
                    "items": [
                        _classify("neg-classify-1", "pas de café", ["article changes", "être exception"], "article changes"),
                        _classify("neg-classify-2", "Ce n'est pas du café", ["article changes", "être exception"], "être exception"),
                        _classify("neg-classify-3", "pas d'idée", ["article changes", "être exception"], "article changes"),
                    ]
                },
            },
            "transform": {
                "items": [
                    _transform("neg-transform-1", "directed_rewrite", "Change 'du café' to 'de café' and 'une pomme' to 'de pomme' after pas.", "Je bois du café et je mange une pomme.", "Je ne bois pas de café et je ne mange pas de pomme."),
                    _transform("neg-transform-2", "contrast_rewrite", "Keep the être exception.", "C'est du café.", "Ce n'est pas du café."),
                    _transform("neg-transform-3", "repair_rewrite", "Repair the article after negation.", "Elle n'a pas une idée.", "Elle n'a pas d'idée."),
                ]
            },
            "produce": {
                "source_fragment": "Le comptoir est presque vide.",
                "prompt": "Write a short note using negated quantities.",
                "requirements": [{"label": concept.name, "target_count": 1}],
                "min_words": 40,
                "max_words": 100,
            },
            "output_ladder": {
                "sentence": {"items": [_output_item("neg-sentence", "short_sentence", concept, "Say what you do not have today.", "Je n'ai pas de dossier aujourd'hui.")]},
                "speak": {"items": [_output_item("neg-speak", "spoken_response", concept, "Say what is missing.", "Nous n'avons pas de café.")]},
                "conversation": {"items": [_output_item("neg-conversation", "conversation_turn", concept, "Answer with one negative quantity.", "Je ne vois pas de métro ici.")]},
            },
        }
    return {
        "recognize": {
            "fill": {
                "items": [
                    _fill("si-fill-1", "Si je finis tôt, je t'_____.", ["appelle", "appellerai", "appellerais", "ai appelé"], "appellerai"),
                    _fill("si-fill-2", "S'il pleut demain, _____ ton manteau.", ["prends", "prendras", "prenais", "as pris"], "prends"),
                    _fill("si-fill-3", "Si nous avons le temps, nous _____ au marché.", ["irons", "allons", "irions", "sommes allés"], "irons"),
                ]
            },
            "word_bank": {
                "items": [
                    _bank("si-bank-1", "Build: If she calls, I will answer.", ["Si", "elle", "appelle", ",", "je", "répondrai"]),
                    _bank("si-bank-2", "Build: If you are hungry, eat.", ["Si", "tu", "as", "faim", ",", "mange"]),
                    _bank("si-bank-3", "Build: If we leave now, we will arrive early.", ["Si", "nous", "partons", "maintenant", ",", "nous", "arriverons", "tôt"]),
                ]
            },
            "classify": {
                "items": [
                    _classify("si-classify-1", "finis", ["present", "future", "conditional", "imperative"], "present"),
                    _classify("si-classify-2", "prends", ["present", "future", "conditional", "imperative"], "imperative"),
                    _classify("si-classify-3", "appellerai", ["present", "future", "conditional", "imperative"], "future"),
                ]
            },
        },
        "transform": {
            "items": [
                _transform("si-transform-1", "directed_rewrite", "Change 'Quand il arrivera' to si + present 'S'il arrive' while keeping the future consequence.", "Quand il arrivera, on commencera le dîner.", "S'il arrive, on commencera le dîner."),
                _transform("si-transform-2", "contrast_rewrite", "Change the unreal condition into a real future condition.", "Si tu avais le temps, tu viendrais.", "Si tu as le temps, tu viendras."),
                _transform("si-transform-3", "repair_rewrite", "Repair only the si construction.", "Si tu viendras demain, apporte le livre.", "Si tu viens demain, apporte le livre."),
            ]
        },
        "produce": {
            "source_fragment": "Le directeur attend une reponse avant le depart.",
            "prompt": "Write a short paragraph with real future conditions.",
            "requirements": [{"label": concept.name, "target_count": 2}],
            "min_words": 50,
            "max_words": 120,
        },
        "output_ladder": {
            "sentence": {"items": [_output_item("si-sentence", "short_sentence", concept, "Write one real future condition.", "Si je finis tôt, je t'appellerai.")]},
            "speak": {"items": [_output_item("si-speak", "spoken_response", concept, "Say what you will do if it rains.", "S'il pleut, je prendrai le métro.")]},
            "conversation": {"items": [_output_item("si-conversation", "conversation_turn", concept, "Answer with a si-clause and a consequence.", "Si elle appelle, je répondrai tout de suite.")]},
        },
    }


def _test_generated_payload(db_session, concept: GrammarConcept) -> dict:
    return AtelierExerciseGenerator(
        db_session,
        llm_service=_FakeLLMService(_raw_llm_payload(concept)),
    ).get_or_create(concept).payload


def _token(client: TestClient) -> str:
    email = f"{uuid4()}@example.com"
    password = "atelier-secure"
    client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "target_language": "fr",
            "native_language": "en",
        },
    )
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()["access_token"]


class _FakeLLMService:
    def __init__(self, content: dict):
        self.content = content
        self.calls: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        self.calls.append({"method": "generate_chat_completion", "messages": messages, **kwargs})
        return self._result(model=kwargs.get("model", "gpt-4o-mini"))

    def generate_error_detection(self, messages, **kwargs):
        self.calls.append({"method": "generate_error_detection", "messages": messages, **kwargs})
        return self._result(model="gpt-4o")

    def _result(self, model: str = "gpt-4o-mini") -> LLMResult:
        return LLMResult(
            provider="openai",
            model=model,
            content=json.dumps(self.content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


class _SequencedFakeLLMService(_FakeLLMService):
    def __init__(self, contents: list[dict]):
        super().__init__(contents[0])
        self.contents = contents

    def _result(self, model: str = "gpt-4o-mini") -> LLMResult:
        index = min(len(self.calls) - 1, len(self.contents) - 1)
        return LLMResult(
            provider="openai",
            model=model,
            content=json.dumps(self.contents[index]),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


class _GenerationCritiqueFakeLLMService(_FakeLLMService):
    def __init__(self, generation_contents: list[dict], critique_contents: list[dict] | None = None):
        super().__init__(generation_contents[0])
        self.generation_contents = generation_contents
        self.critique_contents = critique_contents or [{"verdicts": []}]
        self.generation_calls = 0
        self.critique_calls = 0

    def generate_chat_completion(self, messages, **kwargs):
        response_name = (((kwargs.get("response_format") or {}).get("json_schema") or {}).get("name") or "")
        kind = "critique" if response_name == "atelier_exercise_critique" else "generation"
        self.calls.append({"method": "generate_chat_completion", "kind": kind, "messages": messages, **kwargs})
        if kind == "critique":
            index = min(self.critique_calls, len(self.critique_contents) - 1)
            self.critique_calls += 1
            return self._json_result(self.critique_contents[index], model=kwargs.get("model", "gpt-4o-mini"))
        index = min(self.generation_calls, len(self.generation_contents) - 1)
        self.generation_calls += 1
        return self._json_result(self.generation_contents[index], model=kwargs.get("model", "gpt-4o-mini"))

    @staticmethod
    def _json_result(content: dict, model: str = "gpt-4o-mini") -> LLMResult:
        return LLMResult(
            provider="openai",
            model=model,
            content=json.dumps(content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


class _FailingLLMService:
    def generate_chat_completion(self, messages, **kwargs):
        raise LLMProviderError("exercise generation unavailable")


class _FailingCorrectionLLMService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_chat_completion(self, messages, **kwargs):
        raise LLMProviderError("exercise generation unavailable")

    def generate_error_detection(self, messages, **kwargs):
        self.calls.append({"method": "generate_error_detection", "messages": messages, **kwargs})
        raise LLMProviderError("correction unavailable")


def test_generator_creates_three_recognize_modes_and_three_transform_items(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")

    payload = _test_generated_payload(db_session, concept)

    assert set(payload["recognize"]) == {"fill", "word_bank", "classify"}
    assert all(len(mode["items"]) == 3 for mode in payload["recognize"].values())
    assert len(payload["transform"]["items"]) == 3
    assert payload["produce"]["requirements"][0]["target_count"] == 2
    assert set(payload["output_ladder"]) == {"sentence", "speak", "conversation"}
    assert payload["output_ladder"]["sentence"]["items"][0]["type"] == "short_sentence"
    assert payload["output_ladder"]["speak"]["items"][0]["type"] == "spoken_response"
    assert payload["output_ladder"]["conversation"]["items"][0]["type"] == "conversation_turn"
    first_bank = payload["recognize"]["word_bank"]["items"][0]
    assert first_bank["tokens"] != first_bank["answer_tokens"]
    assert first_bank["correct_answer"] == "Si elle appelle, je répondrai"


def test_generator_does_not_reuse_cached_fallback_when_llm_required(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    stale_payload = _raw_llm_payload(concept)
    stale = AtelierExerciseSet(
        concept_id=concept.id,
        generator_version=ATELIER_GENERATOR_VERSION,
        model=None,
        source="fallback",
        content_hash="stale-fallback",
        payload=stale_payload,
        validation_notes="stale deterministic payload",
    )
    db_session.add(stale)
    db_session.commit()

    llm_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    llm_payload["xray"] = {"sentence": "Si la réunion commence, nous écouterons.", "marks": []}
    fake_llm = _FakeLLMService(llm_payload)

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert exercise_set.id != stale.id
    assert exercise_set.payload["xray"]["sentence"] == "Si la réunion commence, nous écouterons."
    assert fake_llm.calls[0]["model"] == settings.ATELIER_EXERCISE_LLM_MODEL
    assert fake_llm.calls[0]["request_timeout"] == settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS
    assert fake_llm.calls[0]["disable_retries"] is True


def test_generator_serves_valid_fallback_when_llm_generation_fails(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=_FailingLLMService()).get_or_create(concept)

    assert exercise_set.source == "fallback"
    assert exercise_set.model is None
    assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)


def test_personalized_generation_uses_shared_llm_cache_before_deterministic_fallback(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    shared_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    shared_payload["xray"] = {"sentence": "Si la réunion commence, nous écouterons.", "marks": []}
    shared_set = AtelierExerciseGenerator(
        db_session,
        llm_service=_FakeLLMService(shared_payload),
    ).get_or_create(concept, reuse_shared_cache=True)
    user = _user(db_session)

    exercise_set = AtelierExerciseGenerator(
        db_session,
        llm_service=_FailingLLMService(),
    ).get_or_create(concept, user=user, target_vocabulary=[{"word": "réunion"}])

    assert exercise_set.id == shared_set.id
    assert exercise_set.source == "llm"
    assert exercise_set.payload["xray"]["sentence"] == "Si la réunion commence, nous écouterons."


def test_llm_generated_exercise_can_omit_rule_card_and_xray_fields(db_session):
    concept = _concept(db_session, "FR_B1_TENSE_001")
    _clear_exercise_sets(db_session, concept)
    llm_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    fake_llm = _FakeLLMService(llm_payload)

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert exercise_set.payload["rule_panel"]["title"] == concept.name
    assert exercise_set.payload["xray"]["sentence"]
    assert exercise_set.payload["recognize"]["word_bank"]["items"][0]["correct_answer"]
    assert "fallback_shape_reference" not in fake_llm.calls[0]["messages"][0]["content"]


def test_generator_falls_back_after_ai_critic_rejects_word_bank(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    llm_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    llm_payload["recognize"]["word_bank"]["items"][1].update(
        {
            "tokens": ["Je", "ne", "bois", "pas", "de", "café", "du"],
            "answer_tokens": ["Je", "ne", "bois", "pas", "de", "café"],
            "correct_answer": "Je ne bois pas de café",
        }
    )
    fake_llm = _GenerationCritiqueFakeLLMService(
        [llm_payload],
        critique_contents=[
            {
                "verdicts": [
                    {
                        "item_id": "si-bank-2",
                        "round": "recognize",
                        "mode": "word_bank",
                        "passes": False,
                        "reason": "This does not practice the target si-clause concept.",
                    }
                ]
            }
        ],
    )

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "fallback"
    assert fake_llm.critique_calls == 2
    assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)


def test_generator_does_not_fallback_for_word_bank_chip_order_critique(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    llm_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    fake_llm = _GenerationCritiqueFakeLLMService(
        [llm_payload],
        critique_contents=[
            {
                "verdicts": [
                    {
                        "item_id": "si-bank-2",
                        "round": "recognize",
                        "mode": "word_bank",
                        "passes": False,
                        "reason": "Tokens include extra distractors and the chip ordering lacks placement clarity, but distractors are allowed.",
                    }
                ]
            }
        ],
    )

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert fake_llm.critique_calls == 1
    assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)
    event = (
        db_session.query(AtelierGenerationEvent)
        .filter(
            AtelierGenerationEvent.concept_id == concept.id,
            AtelierGenerationEvent.event_type == "ai_critique",
        )
        .order_by(AtelierGenerationEvent.created_at.desc())
        .first()
    )
    assert event.passed is True
    assert event.payload["verdicts"][0]["passes"] is True
    assert "Advisory only" in event.payload["verdicts"][0]["reason"]


def test_generator_rejects_cached_llm_payload_without_required_item_ids(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    stale_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    stale_payload["recognize"]["fill"]["items"][0].pop("id")
    stale = AtelierExerciseSet(
        concept_id=concept.id,
        generator_version=ATELIER_GENERATOR_VERSION,
        model="old-model",
        source="llm",
        content_hash="stale-missing-id",
        payload=stale_payload,
        validation_notes="old incomplete payload",
    )
    db_session.add(stale)
    db_session.commit()
    fake_llm = _FakeLLMService(_raw_llm_payload(concept))

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert exercise_set.id != stale.id
    assert exercise_set.payload["recognize"]["fill"]["items"][0]["id"] == "si-fill-1"
    assert fake_llm.calls


def test_generator_falls_back_after_output_ladder_example_that_does_not_show_concept(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    llm_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    llm_payload["output_ladder"]["sentence"]["items"][0].update(
        {
            "prompt": "Si tu étudies,",
            "example_answer": "tu réussiras.",
        }
    )
    fake_llm = _GenerationCritiqueFakeLLMService(
        [llm_payload],
        critique_contents=[
            {
                "verdicts": [
                    {
                        "item_id": "si-sentence",
                        "round": "sentence",
                        "mode": "sentence",
                        "passes": False,
                        "reason": "The example answer omits the target condition.",
                    }
                ]
            }
        ],
    )

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "fallback"
    assert (
        db_session.query(AtelierGenerationEvent)
        .filter(
            AtelierGenerationEvent.concept_id == concept.id,
            AtelierGenerationEvent.event_type == "ai_critique",
            AtelierGenerationEvent.passed.is_(False),
        )
        .count()
        >= 2
    )
    assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)


def test_generator_retries_with_validation_feedback_after_bad_output_example(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    invalid_payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    invalid_payload["output_ladder"]["sentence"]["items"][0].update(
        {
            "prompt": "Si tu étudies,",
            "example_answer": "tu réussiras.",
        }
    )
    valid_payload = _raw_llm_payload(concept)
    fake_llm = _GenerationCritiqueFakeLLMService(
        [invalid_payload, valid_payload],
        critique_contents=[
            {
                "verdicts": [
                    {
                        "item_id": "si-sentence",
                        "round": "sentence",
                        "mode": "sentence",
                        "passes": False,
                        "reason": "The example answer is a fragment and does not show the si-clause.",
                    }
                ]
            },
            {
                "verdicts": [
                    {
                        "item_id": "si-sentence",
                        "round": "sentence",
                        "mode": "sentence",
                        "passes": True,
                        "reason": "The target concept is visible and the item is solvable.",
                    }
                ]
            },
        ],
    )

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.payload["output_ladder"]["sentence"]["items"][0]["example_answer"].startswith("Si")
    assert fake_llm.generation_calls == 2
    assert fake_llm.critique_calls == 2
    generation_calls = [call for call in fake_llm.calls if call["kind"] == "generation"]
    retry_payload = json.loads(generation_calls[1]["messages"][0]["content"])
    assert retry_payload["validation_feedback"]["previous_attempt_rejected_for"]


def test_atelier_output_example_detector_accepts_n_apostrophe_negation(db_session):
    concept = _concept(db_session, "FR_A2_NEG_001")

    assert count_concept_hits(concept, "Non, je n'ai pas de bonbons.") == 1
    assert count_concept_hits(concept, "Je ne bois pas de café.") == 1


def test_atelier_exercise_schema_requires_real_word_bank_and_one_ladder_item():
    defs = ATELIER_EXERCISE_RESPONSE_FORMAT["json_schema"]["schema"]["$defs"]

    word_bank_items = defs["word_bank_mode"]["properties"]["items"]
    assert word_bank_items["minItems"] == 3
    assert word_bank_items["maxItems"] == 3
    assert defs["word_bank_item"]["properties"]["tokens"]["minItems"] == 1
    assert defs["word_bank_item"]["properties"]["answer_tokens"]["minItems"] == 1

    ladder_items = defs["output_ladder_mode"]["properties"]["items"]
    assert ladder_items["minItems"] == 1
    assert ladder_items["maxItems"] == 1


def test_generated_word_bank_keeps_french_accents(db_session):
    concept = _concept(db_session, "FR_B1_TENSE_001")

    payload = _test_generated_payload(db_session, concept)
    word_bank = payload["recognize"]["word_bank"]["items"]

    assert word_bank[0]["correct_answer"] == "Je marchais quand une voiture est passée"
    assert "passée" in word_bank[0]["tokens"]
    assert word_bank[1]["correct_answer"] == "Il faisait froid, puis nous sommes entrés"
    assert "entrés" in word_bank[1]["tokens"]
    assert word_bank[2]["correct_answer"] == "Elle attendait quand j'ai répondu"
    assert "répondu" in word_bank[2]["tokens"]


def test_atelier_asset_service_creates_language_pack_and_blueprint(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    asset_service = AtelierAssetService(db_session)

    language_pack = asset_service.ensure_language_pack("fr")
    blueprint = asset_service.ensure_concept_blueprint(concept)

    assert isinstance(language_pack, AtelierLanguagePack)
    assert isinstance(blueprint, AtelierConceptBlueprint)
    assert language_pack.payload["correction_style"]["address"] == "you"
    assert blueprint.review_status == "approved"
    assert asset_service.validate_blueprint_payload(blueprint.payload)
    assert blueprint.payload["pedagogy"]["pattern"] == "si + present -> future simple / imperative"
    assert blueprint.payload["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint.payload["visual_motif"]["primitives"][0]["role"] == "condition"
    assert "the learner" not in json.dumps(blueprint.payload["correction_rubric"]["why_templates"]).lower()


def test_atelier_today_returns_blueprint_payload(client: TestClient):
    token = _token(client)
    response = client.get("/api/v1/atelier/today", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    concept = response.json()["concepts"][0]
    blueprint = concept["atelier_blueprint"]
    assert blueprint["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint["exercise_recipe"]["recognize"]["word_bank"]["subitems"] == 3
    assert blueprint["correction_rubric"]["tone"]["address"] == "you"


def test_start_session_with_preferred_concept_keeps_full_atelier_set(client: TestClient, db_session):
    token = _token(client)
    AtelierScheduler(db_session).ensure_catalog()
    _prime_core_exercise_sets(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()

    response = client.post(
        "/api/v1/atelier/sessions",
        json={"preferred_concept_id": concept.id},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["concepts"][0]["id"] == concept.id
    assert len(payload["concepts"]) == 3


def test_start_session_threads_vocabulary_examples_into_output_ladder(client: TestClient, db_session):
    token = _token(client)
    AtelierScheduler(db_session).ensure_catalog()
    _prime_core_exercise_sets(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    word = VocabularyWord(
        language="fr",
        word="dossier",
        normalized_word="dossier",
        frequency_rank=400,
        german_translation="Akte",
        example_sentence="Le dossier reste sur la table.",
        example_translation="Die Akte bleibt auf dem Tisch.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(word)
    db_session.commit()

    response = client.post(
        "/api/v1/atelier/sessions",
        json={"preferred_concept_id": concept.id, "preferred_vocabulary_ids": [word.id]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["target_vocabulary_ids"][0] == word.id
    exercise_payload = payload["exercise_sets"][0]["payload"]
    sentence_item = exercise_payload["output_ladder"]["sentence"]["items"][0]
    assert sentence_item["context_anchor"]["word"] == "dossier"
    assert sentence_item["context_anchor"]["sentence"] == "Le dossier reste sur la table."
    assert exercise_payload["produce"]["context_anchors"][0]["word"] == "dossier"


def test_report_exercise_records_generation_event(client: TestClient, db_session):
    token = _token(client)
    AtelierScheduler(db_session).ensure_catalog()
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    start = client.post(
        "/api/v1/atelier/sessions",
        json={"preferred_concept_id": concept.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert start.status_code == 201
    session_payload = start.json()
    exercise_set = session_payload["exercise_sets"][0]

    response = client.post(
        "/api/v1/atelier/exercises/report",
        json={
            "session_id": session_payload["session_id"],
            "concept_id": concept.id,
            "exercise_set_id": exercise_set["id"],
            "round": "recognize",
            "mode": "word_bank",
            "item_id": "neg-bank-1",
            "reason": "The chips look impossible to solve.",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    event = db_session.get(AtelierGenerationEvent, UUID(response.json()["event_id"]))
    assert event is not None
    assert event.event_type == "user_report"
    assert event.concept_id == concept.id
    assert event.exercise_set_id == UUID(exercise_set["id"])
    assert event.payload["item_id"] == "neg-bank-1"
    assert event.passed is False


def test_select_atelier_vocabulary_uses_curated_starter_for_new_user(db_session):
    user = _user(db_session)
    db_session.add_all(
        [
            VocabularyWord(
                language="fr",
                word="abaisser",
                normalized_word="abaisser",
                frequency_rank=1,
                german_translation="senken",
                direction="fr_to_de",
                is_anki_card=True,
            ),
            VocabularyWord(
                language="fr",
                word="venir",
                normalized_word="venir",
                frequency_rank=80,
                german_translation="kommen",
                direction="fr_to_de",
                is_anki_card=True,
            ),
        ]
    )
    db_session.commit()

    vocabulary = select_atelier_vocabulary(db_session, user=user, limit=1)

    assert vocabulary[0]["word"] == "venir"
    assert vocabulary[0]["bucket"] == "starter"


def test_atelier_sentence_context_anchor_credits_used_vocabulary(client: TestClient, db_session):
    token = _token(client)
    AtelierScheduler(db_session).ensure_catalog()
    _prime_core_exercise_sets(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    word = VocabularyWord(
        language="fr",
        word="dossier",
        normalized_word="dossier",
        frequency_rank=400,
        german_translation="Akte",
        example_sentence="Le dossier reste sur la table.",
        example_translation="Die Akte bleibt auf dem Tisch.",
        direction="fr_to_de",
        deck_name="French 5000",
        is_anki_card=True,
    )
    db_session.add(word)
    db_session.commit()

    start = client.post(
        "/api/v1/atelier/sessions",
        json={"preferred_concept_id": concept.id, "preferred_vocabulary_ids": [word.id]},
        headers={"Authorization": f"Bearer {token}"},
    )
    session_id = start.json()["session_id"]

    response = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        json={
            "concept_id": concept.id,
            "round": "sentence",
            "mode": "sentence",
            "exercise_id": f"{concept.external_id}:sentence",
            "answer_payload": {"text": "Je n'ai pas de dossier aujourd'hui."},
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    correction = response.json()["correction"]
    assert correction["vocabulary_credit"]["summary"]["produced_correct"] == 1
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    assert user is not None
    progress = (
        db_session.query(UserVocabularyProgress)
        .filter(
            UserVocabularyProgress.user_id == user.id,
            UserVocabularyProgress.word_id == word.id,
        )
        .one()
    )
    assert progress.times_used_correctly == 1


def test_atelier_blueprint_template_works_for_non_french_concept(db_session):
    concept = GrammarConcept(
        external_id="ES_A1_ART_001",
        language="es",
        name="Definite articles el/la/los/las",
        level="A1",
        category="Articles",
        subskill="definite_articles",
        core_rule="Use el, la, los, or las according to noun gender and number.",
        main_traps="using el with feminine nouns; forgetting plural agreement",
        anchor_examples="el libro | la mesa | los amigos",
        exercise_tags=["articles", "gender", "number"],
        is_foundation=True,
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    db_session.refresh(concept)

    asset_service = AtelierAssetService(db_session)
    asset_service.ensure_language_pack("es")
    blueprint = asset_service.ensure_concept_blueprint(concept)

    assert blueprint.language == "es"
    assert blueprint.payload["concept_external_id"] == "ES_A1_ART_001"
    assert blueprint.payload["visual_motif"]["style"] == "atelier_bauhaus_v1"
    assert blueprint.payload["exercise_recipe"]["output_ladder"]["conversation_turn"]["subitems"] == 1


def test_output_ladder_counts_non_tense_concept_from_metadata(db_session):
    concept = GrammarConcept(
        external_id=f"FR_B1_REL_{uuid4().hex[:8]}",
        language="fr",
        name="Relative pronouns: qui, que, dont",
        level="B1",
        category="Pronouns",
        subskill="relative_clauses",
        core_rule="Use qui, que, ou, or dont according to the role inside the relative clause.",
        main_traps="using que where dont is needed after a de-complement",
        anchor_examples="Le dossier dont je parle reste ici.",
        exercise_tags=["relative_pronoun", "dont", "de_complement"],
        active=True,
    )
    db_session.add(concept)
    db_session.commit()
    item = _output_item(
        "relative-output",
        "short_sentence",
        concept,
        "Mention a file without repeating le dossier.",
        "Le dossier dont je parle reste ici.",
    )

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="sentence",
        mode="short_sentence",
        exercise_id="relative-output",
        prompt_payload={"items": [item]},
        answer_payload={"text": "Le dossier dont je parle reste sur la table."},
    )

    assert correction["verdict"] == "accepted"
    assert correction["missing_targets"] == []
    assert correction["concept_hits"][0]["detected_count"] >= 1


def test_word_bank_accepts_natural_comma_spacing(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-bank-1": "Si elle appelle, je repondrai",
                "si-bank-2": "Si tu as faim, mange",
                "si-bank-3": "Si nous partons maintenant, nous arriverons tot",
            }
        },
    )

    assert correction["verdict"] == "correct"
    assert correction["errata"] == []


def test_generated_session_copy_keeps_french_accents(db_session):
    negation = _concept(db_session, "FR_A2_NEG_001")
    tense = _concept(db_session, "FR_B1_TENSE_001")
    si_type = _concept(db_session, "FR_B1_COND_001")

    neg_payload = _test_generated_payload(db_session, negation)
    tense_payload = _test_generated_payload(db_session, tense)
    si_payload = _test_generated_payload(db_session, si_type)

    assert "café" in neg_payload["transform"]["items"][0]["source"]
    assert "idée" in neg_payload["transform"]["items"][2]["source"]
    assert neg_payload["recognize"]["classify"]["items"][1]["labels"] == ["article changes", "être exception"]
    assert "dîner" in si_payload["transform"]["items"][0]["expected_answer"]
    assert "métro" in si_payload["output_ladder"]["speak"]["items"][0]["example_answer"]
    assert "passé composé" in tense_payload["transform"]["items"][0]["instruction"]
    assert "passée" in tense_payload["output_ladder"]["sentence"]["items"][0]["example_answer"]


def test_word_bank_reports_specific_si_type_errors(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-bank-1": "Si elle appelle, je repondrai",
                "si-bank-2": "Si tu as faim, mange",
                "si-bank-3": "Si nous partons maintenat, nous arrivons tot",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 2
    assert {erratum["display_label"] for erratum in correction["errata"]} == {"Future result", "Spelling slip"}
    assert {erratum["item_id"] for erratum in correction["errata"]} == {"si-bank-3"}
    assert any("arrivons" in erratum["why_wrong"] for erratum in correction["errata"])
    assert any("maintenat" in erratum["why_wrong"] for erratum in correction["errata"])


def test_word_bank_explains_conditional_instead_of_future(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": [items[0]]},
        answer_payload={"answers": {"si-bank-1": "Si elle appelle, je repondrais"}},
    )

    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Conditional vs future"
    assert "conditional" in erratum["why_wrong"]
    assert "répondrai" in erratum["repair_hint"]


def test_word_bank_splits_same_row_future_and_spelling_for_generic_si_sentence(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    item = _bank("si-bank-generic", "Build the sentence.", ["Si", "tu", "viens", "demain", ",", "nous", "partirons", "tôt"])

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"si-bank-generic": "Si tu viens demaim, nous partons tot"}},
    )

    assert correction["verdict"] == "incorrect"
    assert len(correction["errata"]) == 2
    assert {erratum["display_label"] for erratum in correction["errata"]} == {"Future result", "Spelling slip"}
    assert {erratum["item_id"] for erratum in correction["errata"]} == {"si-bank-generic"}
    assert any("partons" in erratum["why_wrong"] and "partirons" in erratum["why_wrong"] for erratum in correction["errata"])
    assert any("demaim" in erratum["why_wrong"] and "demain" in erratum["why_wrong"] for erratum in correction["errata"])


def test_word_bank_explains_future_inside_si_clause(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["word_bank"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank",
        prompt_payload={"items": [items[2]]},
        answer_payload={"answers": {"si-bank-3": "si nous arriverons maintenant, nous partons tot"}},
    )

    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Future placed after si"
    assert "future `arriverons` inside the si-clause" in erratum["why_wrong"]
    assert "Si nous partons maintenant, nous arriverons tôt" in erratum["repair_hint"]


def test_fill_mode_reports_specific_si_type_feedback(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["fill"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-fill-1": "appelle",
                "si-fill-2": "prends",
                "si-fill-3": "irons",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Target form needed"
    assert "future simple" in erratum["why_wrong"]
    assert "the learner" not in erratum["why_wrong"].lower()


def test_classify_mode_reports_specific_feedback(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["classify"]["items"]

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="classify",
        exercise_id="FR_B1_COND_001:classify",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-classify-1": "present",
                "si-classify-2": "future",
                "si-classify-3": "future",
            }
        },
    )

    assert correction["verdict"] == "partial"
    assert len(correction["errata"]) == 1
    erratum = correction["errata"][0]
    assert erratum["display_label"] == "Form classification"
    assert "imperative command" in erratum["why_wrong"]
    assert "the learner" not in erratum["why_wrong"].lower()


def test_classify_ai_correction_rehydrates_item_ids_for_repeated_wrong_label(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    items = payload["recognize"]["classify"]["items"]
    fake_llm = _FakeLLMService(
        {
            "verdict": "partial",
            "score_0_4": 1.33,
            "corrected_answer": "",
            "corrected_answers": [
                {"item_id": "si-classify-1", "corrected_answer": "present"},
                {"item_id": "si-classify-2", "corrected_answer": "imperative"},
                {"item_id": "si-classify-3", "corrected_answer": "future"},
            ],
            "concept_hits": [
                {
                    "external_id": "FR_B1_COND_001",
                    "label": concept.name,
                    "detected_count": 1,
                    "target_count": 3,
                }
            ],
            "missing_targets": [],
            "errata": [
                {
                    "item_id": "",
                    "display_label": "Form classification",
                    "learner_text": "present",
                    "corrected_target": "imperative",
                    "why_wrong": "You classified `prends` as `present`, but here it is an imperative command.",
                    "repair_hint": "You should name the verb form before reading the whole sentence frame.",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "si_present_result_form",
                    "external_id": "FR_B1_COND_001",
                },
                {
                    "item_id": "",
                    "display_label": "Form classification",
                    "learner_text": "present",
                    "corrected_target": "future",
                    "why_wrong": "You classified `appellerai` as `present`, but `-rai` marks future simple.",
                    "repair_hint": "You should name the verb form before reading the whole sentence frame.",
                    "severity": 2,
                    "recurring": True,
                    "task_error_type": "si_present_result_form",
                    "external_id": "FR_B1_COND_001",
                },
            ],
        }
    )

    correction = AtelierCorrectionService(db_session, llm_service=fake_llm).correct(
        concept=concept,
        round_name="recognize",
        mode="classify",
        exercise_id="FR_B1_COND_001:classify",
        prompt_payload={"items": items},
        answer_payload={
            "answers": {
                "si-classify-1": "present",
                "si-classify-2": "present",
                "si-classify-3": "present",
            }
        },
    )

    assert correction["correction_debug"]["fallback_used"] is False
    assert {
        erratum["corrected_target"]: erratum["item_id"]
        for erratum in correction["errata"]
    } == {
        "imperative": "si-classify-2",
        "future": "si-classify-3",
    }


def test_classify_mode_grades_against_correct_label_not_explanatory_answer(db_session):
    concept = _concept(db_session, "FR_B1_TENSE_001")
    item = _classify(
        "tense-classify-live",
        "a sonné",
        ["background", "bounded event"],
        "bounded event",
    )
    item["correct_answer"] = "passé composé completed event"

    correction = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="recognize",
        mode="classify",
        exercise_id="FR_B1_TENSE_001:classify",
        prompt_payload={"items": [item]},
        answer_payload={"answers": {"tense-classify-live": "bounded event"}},
    )

    assert correction["verdict"] == "correct"
    assert correction["errata"] == []


def test_generator_uses_strict_structured_output_when_llm_available(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    _clear_exercise_sets(db_session, concept)
    payload = json.loads(json.dumps(_raw_llm_payload(concept)))
    fake_llm = _FakeLLMService(payload)

    exercise_set = AtelierExerciseGenerator(db_session, llm_service=fake_llm).get_or_create(concept)

    assert exercise_set.source == "llm"
    assert exercise_set.model == settings.ATELIER_EXERCISE_LLM_MODEL
    assert fake_llm.calls[0]["response_format"]["type"] == "json_schema"
    assert fake_llm.calls[0]["response_format"]["json_schema"]["strict"] is True
    assert len(exercise_set.payload["recognize"]["word_bank"]["items"]) == 3


def test_transform_correction_uses_structured_llm_output(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    fake_llm = _FakeLLMService(
        {
            "verdict": "incorrect",
            "score_0_4": 1,
            "corrected_answer": "",
            "corrected_answers": [
                {"item_id": "si-transform-1", "corrected_answer": "S'il arrive, on commencera le diner."}
            ],
            "concept_hits": [
                {
                    "external_id": "FR_B1_COND_001",
                    "label": concept.name,
                    "detected_count": 0,
                    "target_count": 1,
                }
            ],
            "missing_targets": [],
            "errata": [
                {
                    "display_label": "Si clause frame",
                    "learner_text": "Quand il arrivera, on commencera le diner.",
                    "corrected_target": "S'il arrive, on commencera le diner.",
                    "why_wrong": "The learner changed the requested si frame into quand.",
                    "repair_hint": "The learner should keep si, use present in the condition, and put future in the result.",
                    "severity": 3,
                    "recurring": True,
                    "task_error_type": "si_present_result_form",
                    "external_id": "FR_B1_COND_001",
                }
            ],
        }
    )

    result = AtelierCorrectionService(db_session, llm_service=fake_llm).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    assert result["corrected_answer"]["si-transform-1"].startswith("S'il arrive")
    assert result["errata"][0]["item_id"] == "si-transform-1"
    assert result["errata"][0]["concept_id"] == concept.id
    assert "si frame" in result["errata"][0]["why_wrong"]
    assert "the learner" not in result["errata"][0]["why_wrong"].lower()
    assert result["errata"][0]["why_wrong"].startswith("You")
    assert result["errata"][0]["repair_hint"].startswith("You")
    assert result["correction_debug"]["model"] == "gpt-4o"
    assert result["correction_debug"]["prompt_version"].startswith("atelier-correction")
    assert fake_llm.calls[0]["method"] == "generate_error_detection"
    assert fake_llm.calls[0]["response_format"]["json_schema"]["strict"] is True
    assert fake_llm.calls[0]["request_timeout"] == settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS
    assert fake_llm.calls[0]["model"] == settings.ATELIER_CORRECTION_LLM_MODEL
    assert fake_llm.calls[0]["max_tokens"] == settings.ATELIER_CORRECTION_LLM_MAX_TOKENS
    assert fake_llm.calls[0]["disable_retries"] is True
    compact_payload = json.loads(fake_llm.calls[0]["messages"][0]["content"])
    assert "task" in compact_payload
    assert "answer" in compact_payload
    assert "prompt_payload" not in compact_payload
    assert "answer_payload" not in compact_payload
    assert "context_anchor" not in fake_llm.calls[0]["messages"][0]["content"]


def test_si_rewrite_stays_in_si_frame_and_not_quand(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    assert result["verdict"] != "correct"
    assert result["corrected_answer"]["si-transform-1"].startswith("S'il arrive")
    assert "si" in result["errata"][0]["repair_hint"].lower()


def test_negation_correction_names_article_change(db_session):
    concept = _concept(db_session, "FR_A2_NEG_001")
    payload = _test_generated_payload(db_session, concept)

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="neg-transform",
        prompt_payload=payload["transform"],
        answer_payload={"answers": {"neg-transform-1": "Je ne bois pas du cafe et je ne mange pas une pomme."}},
    )

    erratum = result["errata"][0]
    assert "quantity" in erratum["why_wrong"].lower()
    assert "de/d'" in erratum["repair_hint"]


def test_produce_accepts_submission_with_missing_targets(db_session):
    user = _user(db_session)
    concepts = [_concept(db_session, "FR_B1_COND_001"), _concept(db_session, "FR_B1_TENSE_001"), _concept(db_session, "FR_A2_NEG_001")]
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id for concept in concepts])
    db_session.add(session)
    db_session.commit()

    result = AtelierCorrectionService(db_session).correct(
        concept=None,
        round_name="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        prompt_payload={},
        answer_payload={"text": "Je vais regarder la course a Barcelone avec des amis."},
        session=session,
    )

    assert result["verdict"] == "accepted"
    assert result["missing_targets"]
    assert all(erratum["task_error_type"] == "task_compliance" for erratum in result["errata"])


def test_output_ladder_short_sentence_scores_active_use(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    prompt_payload = {"round": "sentence", "mode": "sentence", **payload["output_ladder"]["sentence"]}

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        prompt_payload=prompt_payload,
        answer_payload={"text": "Si je finis tot, je t'appellerai."},
    )

    assert result["verdict"] == "accepted"
    assert result["score_0_4"] >= 3
    assert result["concept_hits"][0]["detected_count"] == 1
    assert result["errata"] == []


def test_output_ladder_missing_target_is_not_recurring_erratum(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    payload = _test_generated_payload(db_session, concept)
    prompt_payload = {"round": "conversation", "mode": "conversation", **payload["output_ladder"]["conversation"]}

    result = AtelierCorrectionService(db_session).correct(
        concept=concept,
        round_name="conversation",
        mode="conversation",
        exercise_id="FR_B1_COND_001:conversation",
        prompt_payload=prompt_payload,
        answer_payload={"text": "On attend au cafe."},
    )

    assert result["verdict"] == "partial"
    assert result["missing_targets"][0]["missing_count"] == 1
    assert result["errata"][0]["task_error_type"] == "task_compliance"
    assert result["errata"][0]["recurring"] is False


def test_sentence_submit_uses_llm_correction_and_marks_review_complete(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    fake_llm = _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})

    attempt = AtelierCorrectionService(db_session, llm_service=fake_llm).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )

    assert fake_llm.calls[0]["method"] == "generate_error_detection"
    assert attempt.correction_payload["correction_debug"]["fallback_used"] is False
    assert attempt.correction_payload["ai_review"]["status"] == "complete"
    assert attempt.correction_payload["ai_review"]["auto_started"] is False
    assert AtelierCorrectionService(db_session, llm_service=fake_llm).should_auto_start_ai_review(attempt) is False


def test_transform_submit_uses_llm_correction_without_background_review(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _prime_llm_exercise_set(db_session, concept)
    fake_llm = _FakeLLMService({"verdict": "correct", "score_0_4": 4, "errata": []})

    attempt = AtelierCorrectionService(db_session, llm_service=fake_llm).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="FR_B1_COND_001:transform",
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le dîner."}},
    )

    assert fake_llm.calls[0]["method"] == "generate_error_detection"
    assert attempt.correction_payload["correction_debug"]["fallback_used"] is False
    assert attempt.correction_payload["ai_review"]["status"] == "complete"
    assert AtelierCorrectionService(db_session, llm_service=fake_llm).should_auto_start_ai_review(attempt) is False


def test_recognize_submit_uses_llm_correction_but_never_queues_ai_review(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _prime_llm_exercise_set(db_session, concept)
    fake_llm = _FakeLLMService({"verdict": "correct", "score_0_4": 4, "errata": []})

    attempt = AtelierCorrectionService(db_session, llm_service=fake_llm).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={"answers": {"si-fill-1": "appelle"}},
    )

    assert fake_llm.calls[0]["method"] == "generate_error_detection"
    assert attempt.correction_payload["ai_review"]["status"] == "complete"
    assert AtelierCorrectionService(db_session, llm_service=fake_llm).should_auto_start_ai_review(attempt) is False


def test_recognize_submit_offers_ai_review_when_immediate_llm_correction_falls_back(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _prime_llm_exercise_set(db_session, concept)
    failing_llm = _FailingCorrectionLLMService()

    attempt = AtelierCorrectionService(db_session, llm_service=failing_llm).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={"answers": {"si-fill-1": "appelle"}},
    )

    assert failing_llm.calls[0]["method"] == "generate_error_detection"
    assert attempt.correction_payload["correction_debug"]["fallback_used"] is True
    assert attempt.correction_payload["ai_review"]["status"] == "available"
    assert AtelierCorrectionService(db_session, llm_service=failing_llm).should_auto_start_ai_review(attempt) is False


def test_manual_ai_review_is_idempotent_for_pending_and_complete(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    seed_service = AtelierCorrectionService(db_session)
    attempt = seed_service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="FR_B1_COND_001:transform",
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le dîner."}},
    )
    assert attempt.correction_payload["ai_review"]["status"] == "available"
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService({"verdict": "correct", "score_0_4": 4, "errata": []}))

    attempt, should_enqueue = service.mark_ai_review_pending(attempt, auto_started=False)
    assert should_enqueue is True
    assert attempt.correction_payload["ai_review"]["status"] == "pending"

    attempt, should_enqueue = service.mark_ai_review_pending(attempt, auto_started=False)
    assert should_enqueue is False
    complete_payload = dict(attempt.correction_payload)
    complete_payload["ai_review"] = {**complete_payload["ai_review"], "status": "complete"}
    attempt.correction_payload = complete_payload
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)

    attempt, should_enqueue = service.mark_ai_review_pending(attempt, auto_started=False)
    assert should_enqueue is False
    assert attempt.correction_payload["ai_review"]["status"] == "complete"


def test_background_ai_review_success_updates_attempt_correction(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _prime_llm_exercise_set(db_session, concept)
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService({"verdict": "correct", "score_0_4": 4, "errata": []}))
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )

    updated = service.run_ai_review_for_attempt(attempt.id)

    assert updated is not None
    assert updated.correction_payload["ai_review"]["status"] == "complete"
    assert updated.correction_payload["correction_debug"]["fallback_used"] is False
    assert updated.score_0_4 == 4
    assert service.llm_service.calls[0]["method"] == "generate_error_detection"


def test_background_ai_review_failure_preserves_deterministic_correction(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _prime_llm_exercise_set(db_session, concept)
    service = AtelierCorrectionService(db_session, llm_service=_FailingCorrectionLLMService())
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Je vais au café."},
    )
    deterministic_answer = attempt.correction_payload["corrected_answer"]

    updated = service.run_ai_review_for_attempt(attempt.id)

    assert updated is not None
    assert updated.correction_payload["ai_review"]["status"] == "failed"
    assert updated.correction_payload["corrected_answer"] == deterministic_answer
    assert updated.correction_payload["correction_debug"]["fallback_used"] is True


def test_ai_memory_merge_refines_same_attempt_without_incrementing_lapses(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    seed_service = AtelierCorrectionService(db_session)
    attempt = seed_service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="FR_B1_COND_001:transform",
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le dîner."}},
    )
    initial_error = db_session.query(UserError).filter(UserError.source_attempt_id == attempt.id).one()
    initial_occurrences = initial_error.occurrences
    initial_lapses = initial_error.lapses
    initial_erratum = attempt.correction_payload["errata"][0]
    item_id = next(iter(attempt.correction_payload["corrected_answer"]))
    fake_llm = _FakeLLMService(
        {
            "verdict": "incorrect",
            "score_0_4": 1,
            "corrected_answer": "",
            "corrected_answers": [
                {"item_id": item_id, "corrected_answer": attempt.correction_payload["corrected_answer"][item_id]}
            ],
            "concept_hits": [],
            "missing_targets": [],
            "errata": [
                {
                    "display_label": initial_erratum["display_label"],
                    "learner_text": initial_erratum["learner_text"],
                    "corrected_target": initial_erratum["corrected_target"],
                    "why_wrong": "AI-specific explanation for the same slip.",
                    "repair_hint": "AI-specific repair for this exact rewrite.",
                    "severity": 3,
                    "recurring": True,
                    "task_error_type": initial_erratum["task_error_type"],
                    "external_id": concept.external_id,
                }
            ],
        }
    )
    review_service = AtelierCorrectionService(db_session, llm_service=fake_llm)
    attempt, should_enqueue = review_service.mark_ai_review_pending(attempt, auto_started=False)
    assert should_enqueue is True

    updated = review_service.run_ai_review_for_attempt(attempt.id)

    assert updated is not None
    errors = db_session.query(UserError).filter(UserError.source_attempt_id == attempt.id).all()
    assert len(errors) == 1
    assert errors[0].occurrences == initial_occurrences
    assert errors[0].lapses == initial_lapses
    assert errors[0].why_wrong == "AI-specific explanation for the same slip."
    assert updated.correction_payload["memory_updates"][0]["action"] == "refined"


def test_complete_session_schedules_recurring_errata_and_updates_progress(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)

    AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id="si-transform",
        answer_payload={"answers": {"si-transform-1": "Quand il arrivera, on commencera le diner."}},
    )

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)

    assert recap["errata_logged"] == 1
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 1
    assert db_session.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id).count() == 1


def test_atelier_attempt_persists_error_memory_before_completion(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)

    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={"answers": {"si-fill-1": "appelle", "si-fill-2": "prends", "si-fill-3": "irons"}},
    )

    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert error.source_type == "atelier"
    assert error.review_mode == "grammar"
    assert error.source_attempt_id == attempt.id
    assert error.memory_key
    assert attempt.correction_payload["memory_updates"][0]["id"] == str(error.id)
    assert attempt.correction_payload["errata"][0]["id"] == str(error.id)


def test_multiple_errata_can_share_one_error_concept_memory(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)

    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="fill",
        exercise_id="FR_B1_COND_001:fill",
        answer_payload={
            "answers": {
                "si-fill-1": "appelle",
                "si-fill-2": "mangeras",
                "si-fill-3": "irons",
            }
        },
    )

    assert len(attempt.correction_payload["memory_updates"]) == 2
    assert len(attempt.correction_payload["errata"]) == 2
    assert {erratum["item_id"] for erratum in attempt.correction_payload["errata"]} == {"si-fill-1", "si-fill-2"}
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 2
    concept_memories = db_session.query(UserErrorConcept).filter(UserErrorConcept.user_id == user.id).all()
    assert len(concept_memories) == 1
    assert concept_memories[0].total_occurrences == 2


def test_due_errata_pulls_linked_concept_into_atelier_selection(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    db_session.add(
        UserError(
            user_id=user.id,
            concept_id=concept.id,
            error_category="grammar",
            error_pattern="pronoun_choice",
            display_label="Pronoun choice",
            task_error_type="pronoun_choice",
            original_text="en",
            correction="la",
            why_wrong="You used the wrong pronoun.",
            repair_hint="Choose the pronoun that matches the object.",
            next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
            state="new",
            lapses=2,
            occurrences=3,
        )
    )
    db_session.commit()

    selected = AtelierScheduler(db_session).select_today(user)

    assert selected[0].concept.id == concept.id


def test_lexical_errata_are_persisted_as_vocabulary_errors(db_session):
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=concept.id,
        round="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        correction_payload={
            "errata": [
                {
                    "display_label": "Vocabulary choice",
                    "learner_text": "tu me maintiens",
                    "corrected_target": "tu me soutiendras",
                    "why_wrong": "You chose the wrong verb for the intended meaning.",
                    "repair_hint": "Use soutenir when the intended meaning is support or take care of someone.",
                    "severity": 3,
                    "recurring": True,
                    "task_error_type": "lexical_choice",
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                }
            ]
        },
        verdict="incorrect",
        score_0_4=1,
    )
    db_session.add(attempt)
    db_session.commit()

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()

    assert recap["errata_logged"] == 1
    assert error.error_category == "vocabulary"
    assert error.next_review_date is not None
    word = db_session.query(VocabularyWord).filter(VocabularyWord.normalized_word == "soutenir").one()
    progress = db_session.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == user.id,
        UserVocabularyProgress.word_id == word.id,
    ).one()
    assert progress.state == "relearning"
    assert progress.next_review_date is not None


def test_error_memory_records_conversation_lexical_error_and_links_vocabulary(db_session):
    user = _user(db_session)
    update = ErrorMemoryService(db_session).record_detected_error(
        user=user,
        source_type="conversation",
        detected_error=DetectedError(
            code="lexical_choice",
            message="You used maintenir, but the intended meaning is to support someone.",
            span="tu me maintiens",
            suggestion="tu me soutiens",
            category="vocabulary",
            severity="high",
            confidence=0.92,
            subcategory="lexical_choice",
        ),
        source_payload={"mode": "chat"},
    )
    db_session.commit()

    assert update
    error = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert error.source_type == "conversation"
    assert error.review_mode == "vocabulary"
    assert error.linked_word_id is not None
    word = db_session.get(VocabularyWord, error.linked_word_id)
    assert word.normalized_word == "soutenir"
    progress = db_session.query(UserVocabularyProgress).filter(
        UserVocabularyProgress.user_id == user.id,
        UserVocabularyProgress.word_id == word.id,
    ).one()
    assert progress.state == "relearning"


def test_error_memory_repeats_same_pattern_without_duplicate_rows(db_session):
    user = _user(db_session)
    service = ErrorMemoryService(db_session)
    error = DetectedError(
        code="pronoun_choice",
        message="You used en for a direct object that needs la.",
        span="en",
        suggestion="la",
        category="grammar",
        severity="medium",
        confidence=0.9,
        subcategory="pronoun_choice",
    )

    first = service.record_detected_error(user=user, source_type="story", detected_error=error)
    second = service.record_detected_error(user=user, source_type="audio", detected_error=error)
    db_session.commit()

    assert first["action"] == "created"
    assert second["action"] == "repeated"
    row = db_session.query(UserError).filter(UserError.user_id == user.id).one()
    assert row.occurrences == 2
    assert row.lapses == 1


def test_atelier_api_today_session_attempt_and_complete(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)

    today = client.get("/api/v1/atelier/today", headers=headers)
    assert today.status_code == 200
    assert len(today.json()["concepts"]) == 3

    started = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert started.status_code == 201
    data = started.json()
    session_id = data["session_id"]
    concept = data["concepts"][0]
    exercise_set = next(item for item in data["exercise_sets"] if item["concept_id"] == concept["id"])
    fill_items = exercise_set["payload"]["recognize"]["fill"]["items"]

    attempt = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "recognize",
            "mode": "fill",
            "exercise_id": f"{concept['external_id']}:fill",
            "answer_payload": {
                "answers": {item["id"]: item["correct_answer"] for item in fill_items}
            },
        },
    )
    assert attempt.status_code == 200
    assert attempt.json()["verdict"] == "correct"
    assert attempt.json()["ai_review"]["status"] == "not_applicable"
    assert attempt.json()["correction"]["rule_reference"]
    assert attempt.json()["minted_collectibles"][0]["kind"] == "logo_token"

    read_attempt = client.get(f"/api/v1/atelier/attempts/{attempt.json()['attempt_id']}", headers=headers)
    assert read_attempt.status_code == 200
    assert read_attempt.json()["attempt_id"] == attempt.json()["attempt_id"]
    assert read_attempt.json()["correction"]["ai_review"]["status"] == "not_applicable"
    assert read_attempt.json()["minted_collectibles"] == []

    unavailable_review = client.post(f"/api/v1/atelier/attempts/{attempt.json()['attempt_id']}/ai-review", headers=headers)
    assert unavailable_review.status_code == 400

    duplicate = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "recognize",
            "mode": "fill",
            "exercise_id": f"{concept['external_id']}:fill",
            "answer_payload": {
                "answers": {item["id"]: item["correct_answer"] for item in fill_items}
            },
        },
    )
    assert duplicate.status_code == 409

    active = client.get("/api/v1/atelier/sessions/active", headers=headers)
    assert active.status_code == 200
    active_session = active.json()["session"]
    assert active_session["session_id"] == session_id
    assert active_session["submitted_map"][f"recognize:fill:{concept['id']}"] is True
    assert active_session["attempts"][0]["round"] == "recognize"

    read_session = client.get(f"/api/v1/atelier/sessions/{session_id}", headers=headers)
    assert read_session.status_code == 200
    assert read_session.json()["current_position"]["round"] == "recognize"
    assert read_session.json()["current_position"]["mode"] == "classify"

    writing = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": None,
            "round": "produce",
            "mode": "integrated_writing",
            "exercise_id": "integrated-writing",
            "answer_payload": {"text": "Si je vais a Barcelone, je regarderai la course."},
        },
    )
    assert writing.status_code == 200
    assert writing.json()["verdict"] == "accepted"

    completed = client.post(f"/api/v1/atelier/sessions/{session_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert "streak_after" in completed.json()["recap"]
    assert completed.json()["minted_collectibles"] == []

    almanac = client.get("/api/v1/atelier/almanac", headers=headers)
    assert almanac.status_code == 200
    assert almanac.json()["totals"]["logo_token"] == 1
    assert almanac.json()["progress"]["plate_semaine"]["available"] == 1

    compose = client.post("/api/v1/atelier/workshop/compose", headers=headers, json={"target": "plate_semaine"})
    assert compose.status_code == 409
    assert compose.json()["detail"]["shortfall"] == 6


def test_workshop_compose_preserves_nested_members(db_session):
    user = _user(db_session)
    for index in range(7):
        db_session.add(
            AtelierCollectible(
                user_id=user.id,
                kind="logo_token",
                source_kind="screen",
                source_ref=f"test-screen-{index}",
                metadata_payload={"index": index},
            )
        )
    db_session.commit()

    result = AtelierRewardService(db_session).compose(user_id=user.id, target="plate_semaine")

    assert result["plate"]["kind"] == "plate_semaine"
    assert len(result["members"]) == 7
    assert result["progress"]["plate_semaine"]["available"] == 0
    assert db_session.query(AtelierCollectible).filter(
        AtelierCollectible.user_id == user.id,
        AtelierCollectible.kind == "logo_token",
        AtelierCollectible.composed.is_(True),
    ).count() == 7

    almanac = AtelierRewardService(db_session).almanac(user_id=user.id)
    assert almanac["plates"][0]["kind"] == "plate_semaine"
    assert len(almanac["plates"][0]["members"]) == 7


def test_atelier_today_includes_due_errata_and_review_endpoint(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    user_id = decode_token(token)["sub"]
    user = db_session.get(User, UUID(user_id))
    concept = _concept(db_session, "FR_A2_NEG_001")
    erratum = UserError(
        user_id=user.id,
        concept_id=concept.id,
        error_category="grammar",
        error_pattern="pronoun_choice",
        display_label="Pronoun choice",
        task_error_type="pronoun_choice",
        original_text="en",
        correction="la",
        why_wrong="You used en for a direct object that needs la.",
        repair_hint="Use la when the pronoun replaces a specific feminine direct object.",
        next_review_date=datetime.now(timezone.utc) - timedelta(days=1),
        state="new",
        lapses=1,
        occurrences=2,
    )
    db_session.add(erratum)
    db_session.commit()

    today = client.get("/api/v1/atelier/today", headers=headers)
    assert today.status_code == 200
    payload = today.json()
    assert payload["due_errata"]
    selected = next(item for item in payload["concepts"] if item["id"] == concept.id)
    assert selected["due_errata"][0]["display_label"] == "Pronoun choice"

    task = client.get(f"/api/v1/atelier/errata/{erratum.id}/task", headers=headers)
    assert task.status_code == 200
    assert task.json()["task"]["target_answer"] == "la"
    assert task.json()["task"]["display_label"] == "Pronoun choice"

    wrong_attempt = client.post(
        f"/api/v1/atelier/errata/{erratum.id}/attempt",
        headers=headers,
        json={"answer_text": "en"},
    )
    assert wrong_attempt.status_code == 200
    wrong_payload = wrong_attempt.json()
    assert wrong_payload["verdict"] == "needs_repair"
    assert wrong_payload["is_correct"] is False
    assert wrong_payload["erratum"]["state"] == "relearning"
    assert wrong_payload["erratum"]["metadata"]["review_attempts"][0]["answer_text"] == "en"

    repaired_attempt = client.post(
        f"/api/v1/atelier/errata/{erratum.id}/attempt",
        headers=headers,
        json={"answer_text": "la"},
    )
    assert repaired_attempt.status_code == 200
    repaired_payload = repaired_attempt.json()
    assert repaired_payload["verdict"] == "repaired"
    assert repaired_payload["is_correct"] is True
    assert repaired_payload["closure"]["label"] == "Corrected. Filed."
    assert repaired_payload["closure"]["next_review_date"]
    assert repaired_payload["erratum"]["state"] == "review"
    assert len(repaired_payload["erratum"]["metadata"]["review_attempts"]) == 2
    assert repaired_payload["erratum"]["metadata"]["last_closure"]["label"] == "Corrected. Filed."
