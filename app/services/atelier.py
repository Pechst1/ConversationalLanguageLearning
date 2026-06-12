"""Atelier grammar practice services."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.db.models.atelier import AtelierAttempt, AtelierExerciseSet, AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.exercise_generation import ExerciseGenerationService, ExerciseGenerationUnavailable
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.grammar import GrammarService
from app.services.grammar_feedback import count_concept_hits, infer_grammar_profile
from app.services.llm_service import LLMProviderError, LLMService
from app.services.progress import ProgressService
from app.services.vocabulary_credit import VocabularyCreditService

ATELIER_GENERATOR_VERSION = "atelier-v6"
ATELIER_CORRECTION_PROMPT_VERSION = "atelier-correction-v2"
ATELIER_AI_AUTO_ROUNDS = {"sentence", "speak", "conversation", "produce"}


class AtelierExerciseGenerationError(RuntimeError):
    """Raised when Atelier cannot produce an LLM-backed exercise payload."""


ATELIER_EXERCISE_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "atelier_exercise_set",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "recognize": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "fill": {"$ref": "#/$defs/fill_mode"},
                        "word_bank": {"$ref": "#/$defs/word_bank_mode"},
                        "classify": {"$ref": "#/$defs/classify_mode"},
                    },
                    "required": ["fill", "word_bank", "classify"],
                },
                "transform": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"$ref": "#/$defs/transform_item"},
                        }
                    },
                    "required": ["items"],
                },
                "produce": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "source_fragment": {"type": "string"},
                        "prompt": {"type": "string"},
                        "requirements": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"$ref": "#/$defs/requirement"},
                        },
                        "min_words": {"type": "integer"},
                        "max_words": {"type": "integer"},
                    },
                    "required": ["source_fragment", "prompt", "requirements", "min_words", "max_words"],
                },
                "output_ladder": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "sentence": {"$ref": "#/$defs/output_ladder_mode"},
                        "speak": {"$ref": "#/$defs/output_ladder_mode"},
                        "conversation": {"$ref": "#/$defs/output_ladder_mode"},
                    },
                    "required": ["sentence", "speak", "conversation"],
                },
            },
            "required": ["recognize", "transform", "produce", "output_ladder"],
            "$defs": {
                "requirement": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "target_count": {"type": "integer"},
                    },
                    "required": ["label", "target_count"],
                },
                "fill_mode": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"$ref": "#/$defs/fill_item"},
                        }
                    },
                    "required": ["items"],
                },
                "word_bank_mode": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"$ref": "#/$defs/word_bank_item"},
                        }
                    },
                    "required": ["items"],
                },
                "classify_mode": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 3,
                            "maxItems": 3,
                            "items": {"$ref": "#/$defs/classify_item"},
                        }
                    },
                    "required": ["items"],
                },
                "fill_item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "prompt": {"type": "string"},
                        "choices": {"type": "array", "minItems": 2, "items": {"type": "string"}},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["id", "prompt", "choices", "correct_answer"],
                },
                "word_bank_item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "prompt": {"type": "string"},
                        "tokens": {"type": "array", "minItems": 3, "items": {"type": "string"}},
                        "answer_tokens": {"type": "array", "minItems": 3, "items": {"type": "string"}},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["id", "prompt", "tokens", "answer_tokens", "correct_answer"],
                },
                "classify_item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "prompt": {"type": "string"},
                        "labels": {"type": "array", "minItems": 2, "items": {"type": "string"}},
                        "correct_label": {"type": "string"},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["id", "prompt", "labels", "correct_label", "correct_answer"],
                },
                "transform_item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string", "enum": ["directed_rewrite", "contrast_rewrite", "repair_rewrite"]},
                        "instruction": {"type": "string"},
                        "source": {"type": "string"},
                        "expected_answer": {"type": "string"},
                    },
                    "required": ["id", "type", "instruction", "source", "expected_answer"],
                },
                "output_ladder_mode": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "items": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "items": {"$ref": "#/$defs/output_item"},
                        }
                    },
                    "required": ["items"],
                },
                "output_item": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "id": {"type": "string"},
                        "type": {"type": "string", "enum": ["short_sentence", "spoken_response", "conversation_turn"]},
                        "instruction": {"type": "string"},
                        "prompt": {"type": "string"},
                        "example_answer": {"type": "string"},
                        "requirements": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"$ref": "#/$defs/requirement"},
                        },
                        "min_words": {"type": "integer"},
                        "max_words": {"type": "integer"},
                    },
                    "required": [
                        "id",
                        "type",
                        "instruction",
                        "prompt",
                        "example_answer",
                        "requirements",
                        "min_words",
                        "max_words",
                    ],
                },
            },
        },
    },
}


ATELIER_CORRECTION_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "atelier_correction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verdict": {"type": "string", "enum": ["correct", "partial", "incorrect", "accepted", "needs_review"]},
                "score_0_4": {"type": "number"},
                "corrected_answer": {"type": "string"},
                "corrected_answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item_id": {"type": "string"},
                            "corrected_answer": {"type": "string"},
                        },
                        "required": ["item_id", "corrected_answer"],
                    },
                },
                "concept_hits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "external_id": {"type": "string"},
                            "label": {"type": "string"},
                            "detected_count": {"type": "integer"},
                            "target_count": {"type": "integer"},
                        },
                        "required": ["external_id", "label", "detected_count", "target_count"],
                    },
                },
                "missing_targets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "external_id": {"type": "string"},
                            "label": {"type": "string"},
                            "detected_count": {"type": "integer"},
                            "target_count": {"type": "integer"},
                            "missing_count": {"type": "integer"},
                        },
                        "required": ["external_id", "label", "detected_count", "target_count", "missing_count"],
                    },
                },
                "errata": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "display_label": {"type": "string"},
                            "learner_text": {"type": "string"},
                            "corrected_target": {"type": "string"},
                            "why_wrong": {"type": "string"},
                            "repair_hint": {"type": "string"},
                            "severity": {"type": "integer"},
                            "recurring": {"type": "boolean"},
                            "task_error_type": {"type": "string"},
                            "external_id": {"type": "string"},
                        },
                        "required": [
                            "display_label",
                            "learner_text",
                            "corrected_target",
                            "why_wrong",
                            "repair_hint",
                            "severity",
                            "recurring",
                            "task_error_type",
                            "external_id",
                        ],
                    },
                },
            },
            "required": [
                "verdict",
                "score_0_4",
                "corrected_answer",
                "corrected_answers",
                "concept_hits",
                "missing_targets",
                "errata",
            ],
        },
    },
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("’", "'").replace("`", "'").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"'\s+", "'", text)
    text = re.sub(r"[.!?;:,\u00ab\u00bb]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _join_french_tokens(tokens: list[Any]) -> str:
    text = " ".join(str(token).strip() for token in tokens if str(token).strip())
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([cdjlmnst])'\s+", r"\1'", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _stable_scramble(tokens: list[Any], item_id: str) -> list[str]:
    clean = [str(token).strip() for token in tokens if str(token).strip()]
    if len(clean) < 3:
        return clean
    keyed = [
        (hashlib.sha256(f"{item_id}:{index}:{token}".encode("utf-8")).hexdigest(), index, token)
        for index, token in enumerate(clean)
    ]
    scrambled = [token for _, _, token in sorted(keyed)]
    if _normalize(_join_french_tokens(scrambled)) == _normalize(_join_french_tokens(clean)):
        scrambled = clean[1:] + clean[:1]
    while scrambled and scrambled[0] in {",", ".", ";", ":", "!", "?"}:
        scrambled = scrambled[1:] + scrambled[:1]
    return scrambled


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    raw = re.split(r"\s*[;|]\s*", value)
    return [item.strip() for item in raw if item.strip()]


def _dedupe_ints(values: list[Any]) -> list[int]:
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed in seen:
            continue
        ordered.append(parsed)
        seen.add(parsed)
    return ordered


def _compact_text(value: Any, *, max_length: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _vocabulary_anchor(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "word_id": item.get("word_id"),
        "word": item.get("word"),
        "translation": item.get("translation") or item.get("example_translation"),
        "sentence": item.get("example_sentence") or "",
        "example_sentence": item.get("example_sentence") or "",
        "example_translation": item.get("example_translation") or item.get("translation") or "",
    }


def _normalize_target_vocabulary(items: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            word_id = int(item.get("word_id"))
        except (TypeError, ValueError):
            continue
        word = _compact_text(item.get("word"), max_length=80)
        if not word or word_id in seen:
            continue
        normalized.append(
            {
                "word_id": word_id,
                "word": word,
                "translation": _compact_text(item.get("translation"), max_length=90),
                "translations": item.get("translations") if isinstance(item.get("translations"), dict) else {},
                "bucket": _compact_text(item.get("bucket"), max_length=30) or "due",
                "scheduler": _compact_text(item.get("scheduler"), max_length=40) or "fsrs",
                "priority_score": item.get("priority_score") or 0,
                "example_sentence": _compact_text(item.get("example_sentence"), max_length=180),
                "example_translation": _compact_text(item.get("example_translation"), max_length=180),
            }
        )
        seen.add(word_id)
    return normalized


def select_atelier_vocabulary(
    db: Session,
    *,
    user: User,
    preferred_word_ids: list[int] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_word_ids: set[int] = set()
    seen_surfaces: set[str] = set()
    native_language = (user.native_language or "").strip().lower()
    translation_order = [native_language[:2] if native_language else "", "de", "en", "fr"]

    def add_item(item: dict[str, Any]) -> None:
        if len(selected) >= limit:
            return
        try:
            word_id = int(item.get("word_id"))
        except (TypeError, ValueError):
            return
        word = _compact_text(item.get("word"), max_length=80)
        surface_key = _normalize(word)
        if not word or word_id in seen_word_ids or surface_key in seen_surfaces:
            return
        translations = item.get("translations") if isinstance(item.get("translations"), dict) else {}
        translation = _compact_text(item.get("translation"), max_length=90)
        if not translation:
            for language in translation_order:
                if not language:
                    continue
                translation = _compact_text(translations.get(language), max_length=90)
                if translation:
                    break
        selected.append(
            {
                "word_id": word_id,
                "word": word,
                "translation": translation,
                "translations": {
                    "de": _compact_text(translations.get("de"), max_length=90),
                    "en": _compact_text(translations.get("en"), max_length=90),
                    "fr": _compact_text(translations.get("fr"), max_length=90),
                },
                "bucket": item.get("bucket") or "due",
                "scheduler": item.get("scheduler") or "fsrs",
                "priority_score": item.get("priority_score") or 0,
                "example_sentence": _compact_text(item.get("example_sentence"), max_length=180),
                "example_translation": _compact_text(item.get("example_translation"), max_length=180),
            }
        )
        seen_word_ids.add(word_id)
        seen_surfaces.add(surface_key)

    preferred_ids = _dedupe_ints(preferred_word_ids or [])
    if preferred_ids:
        rows = db.query(VocabularyWord).filter(VocabularyWord.id.in_(preferred_ids)).all()
        by_id = {row.id: row for row in rows}
        for word_id in preferred_ids:
            word = by_id.get(word_id)
            if not word:
                continue
            add_item(
                {
                    "word_id": word.id,
                    "word": word.word,
                    "translations": {
                        "de": word.german_translation,
                        "en": word.english_translation,
                        "fr": word.french_translation,
                    },
                    "bucket": "preferred",
                    "scheduler": "explicit",
                    "priority_score": 1.0,
                    "example_sentence": word.example_sentence,
                    "example_translation": word.example_translation,
                }
            )

    if len(selected) >= limit:
        return selected[:limit]

    recommendations = ProgressService(db).get_vocabulary_recommendations(
        user=user,
        limit=limit * 2,
        due_limit=limit,
        fragile_limit=limit,
        new_limit=limit,
        direction="fr_to_de",
    )
    for item in recommendations.get("items") or []:
        add_item(item)
        if len(selected) >= limit:
            break
    return selected[:limit]


def session_vocabulary_context(session: AtelierSession) -> list[dict[str, Any]]:
    quote = session.quote_payload or {}
    items = quote.get("target_vocabulary") if isinstance(quote, dict) else []
    return _normalize_target_vocabulary(items if isinstance(items, list) else [])


def inject_vocabulary_context(
    payload: dict[str, Any],
    target_vocabulary: list[dict[str, Any]],
    *,
    concept_index: int = 0,
) -> dict[str, Any]:
    vocabulary = _normalize_target_vocabulary(target_vocabulary)
    if not vocabulary:
        return payload
    next_payload = json.loads(json.dumps(payload))
    next_payload["target_vocabulary"] = vocabulary
    next_payload["target_vocabulary_ids"] = [item["word_id"] for item in vocabulary]
    anchors = [_vocabulary_anchor(item) for item in vocabulary]
    anchor = anchors[concept_index % len(anchors)]

    def enrich_items(container: dict[str, Any]) -> None:
        items = container.get("items") if isinstance(container, dict) else None
        if not isinstance(items, list):
            return
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            item.setdefault("context_anchor", anchors[(concept_index + index) % len(anchors)])
            item.setdefault("vocabulary_task", True)
            item.setdefault("production_goal", "use_target_vocabulary_in_context")

    ladder = next_payload.get("output_ladder")
    if isinstance(ladder, dict):
        for container in ladder.values():
            if isinstance(container, dict):
                enrich_items(container)
    enrich_items(next_payload)

    produce = next_payload.get("produce")
    if isinstance(produce, dict):
        produce["context_anchors"] = anchors
        produce.setdefault("vocabulary_task", True)
        produce.setdefault("production_goal", "use_target_vocabulary_in_context")
    elif next_payload.get("round") == "produce":
        next_payload["context_anchors"] = anchors
        next_payload.setdefault("vocabulary_task", True)
        next_payload.setdefault("production_goal", "use_target_vocabulary_in_context")
    next_payload.setdefault("context_anchor", anchor)
    return next_payload


def _payload_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _correction_debug(*, model: str | None, fallback_used: bool, schema_valid: bool = True) -> dict[str, Any]:
    return {
        "model": model,
        "prompt_version": ATELIER_CORRECTION_PROMPT_VERSION,
        "fallback_used": fallback_used,
        "schema_valid": schema_valid,
    }


def _produce_target_count(db: Session | None, concept: GrammarConcept | None) -> int:
    if not concept:
        return 1
    if db is not None:
        try:
            blueprint = AtelierAssetService(db).approved_blueprint_payload(concept)
            paragraph = (
                ((blueprint.get("exercise_recipe") or {}).get("output_ladder") or {}).get("paragraph")
                if isinstance(blueprint, dict)
                else {}
            )
            target_count = int((paragraph or {}).get("target_count") or 0)
            if target_count > 0:
                return min(target_count, 3)
        except (TypeError, ValueError):
            pass
    return 2 if str(concept.level or "").upper() in {"B1", "B2", "C1", "C2"} else 1


def _concept_correction_instructions(concepts: list[GrammarConcept | None]) -> list[str]:
    instructions: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        if not concept:
            continue
        profile = infer_grammar_profile(concept)
        if profile.key in seen:
            continue
        seen.add(profile.key)
        instructions.append(
            f"For {profile.label.lower()} issues, apply this rule: {profile.principle} Repair cue: {profile.repair}"
        )
        if profile.key == "si_present_result_form":
            instructions.append(
                "When a si-frame is explicitly required, preserve si in corrected rewrites; do not replace it with quand unless the task asks for quand."
            )
    return instructions[:6]


@dataclass(frozen=True)
class ConceptSelection:
    concept: GrammarConcept
    role: str
    progress: UserGrammarProgress | None = None


FALLBACK_CONCEPTS: list[dict[str, Any]] = [
    {
        "external_id": "FR_B1_COND_001",
        "language": "fr",
        "level": "B1",
        "category": "Conditionals",
        "subskill": "conditionals",
        "name": "Si type 1: si + présent -> futur/impératif",
        "difficulty_order": 101,
        "is_foundation": False,
        "core_rule": "For a real future condition, keep the si-clause in the present. Put the future simple or an imperative in the result clause.",
        "main_traps": "using future directly after si; changing si into quand; using conditional for a real condition",
        "anchor_examples": "Si tu viens, on ira. | Si tu as faim, mange. | S'il pleut, prends ton manteau.",
        "exercise_tags": ["si", "present", "future", "imperative"],
        "active": True,
    },
    {
        "external_id": "FR_B1_TENSE_001",
        "language": "fr",
        "level": "B1",
        "category": "Tenses",
        "subskill": "tense_choice",
        "name": "Imparfait vs passé composé (core contrast)",
        "difficulty_order": 102,
        "is_foundation": False,
        "core_rule": "Use imparfait for background, habits, descriptions, and ongoing states. Use passé composé for completed, bounded events.",
        "main_traps": "marking background as passé composé; marking completed events as imparfait; ignoring time boundaries",
        "anchor_examples": "Il pleuvait quand je suis sorti. | Je marchais quand une voiture est passée. | Hier, j'ai attendu puis je suis entré.",
        "exercise_tags": ["imparfait", "passe_compose", "background", "event"],
        "active": True,
    },
    {
        "external_id": "FR_A2_NEG_001",
        "language": "fr",
        "level": "A2",
        "category": "Negation",
        "subskill": "articles_after_negation",
        "name": "De/d' after negation with partitive/indefinite (ne...pas de)",
        "difficulty_order": 80,
        "is_foundation": True,
        "core_rule": "After a negative quantity, change du, de la, de l', des, un, or une to de or d'. The être exception keeps the original article.",
        "main_traps": "keeping du/des after pas; changing articles after être; forgetting d' before a vowel",
        "anchor_examples": "Je bois du café. -> Je ne bois pas de café. | C'est du café. -> Ce n'est pas du café. | Il a une pomme. -> Il n'a pas de pomme.",
        "exercise_tags": ["negation", "articles", "quantity"],
        "active": True,
    },
]


LOCAL_QUOTES = [
    {
        "text": "La beaute est dans l'oeil de celui qui regarde.",
        "source": "Proverbe francais",
        "source_detail": "Local curated quote list",
    },
    {
        "text": "Il faut cultiver notre jardin.",
        "source": "Voltaire",
        "source_detail": "Candide",
    },
    {
        "text": "On ne voit bien qu'avec le coeur.",
        "source": "Antoine de Saint-Exupery",
        "source_detail": "Le Petit Prince",
    },
    {
        "text": "La clarte est la politesse de l'homme de lettres.",
        "source": "Jules Renard",
        "source_detail": "Journal",
    },
]


class AtelierScheduler:
    """Select the three concepts that define an Atelier session."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_catalog(self) -> None:
        """Seed/update the learner-facing grammar catalog from the curated core list."""
        FrenchCoreGrammarCatalog(self.db).ensure_catalog(archive_legacy=True)
        AtelierAssetService(self.db).ensure_assets_for_catalog("fr")

    def select_today(self, user: User) -> list[ConceptSelection]:
        self.ensure_catalog()
        selected: list[ConceptSelection] = []
        used_ids: set[int] = set()

        for concept in self._due_errata_concepts(user):
            if concept.id in used_ids:
                continue
            selected.append(ConceptSelection(concept=concept, role="fragile", progress=self._progress_for(user, concept.id)))
            used_ids.add(concept.id)
            if len(selected) == 2:
                break

        due = GrammarService(self.db).get_due_concepts(user=user, limit=30)
        for concept, progress in due:
            if not concept.active or not concept.external_id or concept.id in used_ids or progress is None:
                continue
            if progress.score < 7 or self._is_due(progress):
                selected.append(ConceptSelection(concept=concept, role="fragile", progress=progress))
                used_ids.add(concept.id)
            if len(selected) == 2:
                break

        active_query = self.db.query(GrammarConcept).filter(
            GrammarConcept.active.is_(True),
            GrammarConcept.external_id.isnot(None),
            GrammarConcept.external_id != "",
        )
        for external_id in ("FR_B1_COND_001", "FR_B1_TENSE_001", "FR_A2_NEG_001"):
            if len(selected) >= 2:
                break
            concept = active_query.filter(GrammarConcept.external_id == external_id).first()
            if concept and concept.id not in used_ids:
                progress = self._progress_for(user, concept.id)
                selected.append(ConceptSelection(concept=concept, role="fragile", progress=progress))
                used_ids.add(concept.id)

        contrast = (
            active_query.filter(
                GrammarConcept.id.notin_(used_ids),
                GrammarConcept.external_id == "FR_A2_NEG_001",
            )
            .first()
        )
        if not contrast:
            contrast = (
                active_query.filter(GrammarConcept.id.notin_(used_ids), GrammarConcept.is_foundation.is_(True))
                .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
                .first()
            )
        if not contrast:
            contrast = (
                active_query.filter(GrammarConcept.id.notin_(used_ids))
                .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
                .first()
            )
        if contrast:
            selected.append(
                ConceptSelection(concept=contrast, role="contrast", progress=self._progress_for(user, contrast.id))
            )
            used_ids.add(contrast.id)

        for concept in active_query.order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc()).all():
            if len(selected) >= 3:
                break
            if concept.id not in used_ids:
                selected.append(ConceptSelection(concept=concept, role="contrast", progress=self._progress_for(user, concept.id)))
                used_ids.add(concept.id)

        return selected[:3]

    def quote_for_today(self, today: date | None = None) -> dict[str, str]:
        today = today or date.today()
        return LOCAL_QUOTES[(today.timetuple().tm_yday - 1) % len(LOCAL_QUOTES)]

    def summary(self, user: User) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        total = (
            self.db.query(GrammarConcept)
            .filter(GrammarConcept.active.is_(True), GrammarConcept.external_id.isnot(None), GrammarConcept.external_id != "")
            .count()
        )
        due = (
            self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id)
            .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
            .filter(GrammarConcept.external_id.isnot(None), GrammarConcept.external_id != "")
            .filter((UserGrammarProgress.next_review.is_(None)) | (UserGrammarProgress.next_review <= now))
            .count()
        )
        fragile = (
            self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.score < 7)
            .join(GrammarConcept, GrammarConcept.id == UserGrammarProgress.concept_id)
            .filter(GrammarConcept.external_id.isnot(None), GrammarConcept.external_id != "")
            .count()
        )
        return {
            "concepts": total,
            "due": due,
            "fragile": fragile,
            "due_errata": len(self.due_errata(user)),
            "streak": getattr(user, "grammar_streak_days", 0) or 0,
            "longest_streak": getattr(user, "grammar_longest_streak", 0) or 0,
        }

    def atlas(self, user: User, limit: int = 12) -> list[dict[str, Any]]:
        rows = (
            self.db.query(GrammarConcept, UserGrammarProgress)
            .outerjoin(
                UserGrammarProgress,
                (UserGrammarProgress.concept_id == GrammarConcept.id)
                & (UserGrammarProgress.user_id == user.id),
            )
            .filter(GrammarConcept.active.is_(True))
            .filter(GrammarConcept.external_id.isnot(None), GrammarConcept.external_id != "")
            .order_by(UserGrammarProgress.score.asc().nullsfirst(), GrammarConcept.difficulty_order.asc())
            .limit(limit)
            .all()
        )
        return [
            {
                "concept_id": concept.id,
                "external_id": concept.external_id,
                "name": concept.name,
                "level": concept.level,
                "category": concept.category,
                "mastery": progress.score if progress else 0,
                "due": progress.next_review.isoformat() if progress and progress.next_review else None,
                "is_foundation": concept.is_foundation,
            }
            for concept, progress in rows
        ]

    def due_errata(self, user: User, limit: int = 20) -> list[dict[str, Any]]:
        return ErrorMemoryService(self.db).due_errata(user, limit=limit)

    def _load_template_rows(self) -> list[dict[str, Any]]:
        path = _repo_root() / "templates" / "french_grammar_concepts.csv"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for raw in csv.DictReader(handle):
                if not raw.get("concept_id"):
                    continue
                rows.append(
                    {
                        "external_id": raw.get("concept_id"),
                        "language": raw.get("language") or "fr",
                        "level": raw.get("cefr_level") or "A1",
                        "category": raw.get("category"),
                        "subskill": raw.get("subskill"),
                        "name": raw.get("concept_name") or raw.get("concept_id"),
                        "difficulty_order": int(raw.get("teaching_order") or 0),
                        "is_foundation": str(raw.get("is_foundation", "")).strip().lower() == "true",
                        "parent_external_id": raw.get("parent_concept_id") or None,
                        "prerequisites": _split_list(raw.get("prerequisite_ids")),
                        "core_rule": raw.get("core_rule"),
                        "main_traps": raw.get("main_traps"),
                        "anchor_examples": raw.get("anchor_examples"),
                        "exercise_tags": _split_list(raw.get("exercise_tags")),
                        "active": str(raw.get("active", "true")).strip().lower() != "false",
                    }
                )
        return rows

    def _progress_for(self, user: User, concept_id: int) -> UserGrammarProgress | None:
        return (
            self.db.query(UserGrammarProgress)
            .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept_id)
            .first()
        )

    def _due_errata_concepts(self, user: User, limit: int = 10) -> list[GrammarConcept]:
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(GrammarConcept)
            .join(UserError, UserError.concept_id == GrammarConcept.id)
            .filter(
                UserError.user_id == user.id,
                UserError.state != "mastered",
                GrammarConcept.active.is_(True),
                GrammarConcept.external_id.isnot(None),
                GrammarConcept.external_id != "",
            )
            .filter((UserError.next_review_date.is_(None)) | (UserError.next_review_date <= now))
            .order_by(UserError.lapses.desc(), UserError.occurrences.desc(), UserError.next_review_date.asc().nullsfirst())
            .limit(limit)
            .all()
        )
        concepts: list[GrammarConcept] = []
        seen: set[int] = set()
        for concept in rows:
            if concept.id in seen:
                continue
            concepts.append(concept)
            seen.add(concept.id)
        return concepts

    @staticmethod
    def _is_due(progress: UserGrammarProgress) -> bool:
        return not progress.next_review or progress.next_review <= datetime.now(timezone.utc)


class AtelierExerciseGenerator:
    """Generate and cache Atelier exercise payloads."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm_service = llm_service
        self._llm_unavailable = False

    def get_or_create(self, concept: GrammarConcept, *, user: User | None = None) -> AtelierExerciseSet:
        cached = (
            self.db.query(AtelierExerciseSet)
            .filter(
                AtelierExerciseSet.concept_id == concept.id,
                AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
                AtelierExerciseSet.source == "llm",
            )
            .order_by(AtelierExerciseSet.created_at.desc())
            .first()
        )
        if cached and self.validate_payload(cached.payload, concept=concept):
            return cached

        generated = self._generate_with_llm(concept, user=user)
        if not generated:
            raise AtelierExerciseGenerationError(
                f"Atelier exercise generation requires an LLM payload for {concept.external_id or concept.id}, "
                "but no valid LLM exercise set could be produced."
            )
        payload, model, validation_notes = generated
        source = "llm"

        content_hash = _payload_hash(payload)
        existing_same_hash = (
            self.db.query(AtelierExerciseSet)
            .filter(
                AtelierExerciseSet.concept_id == concept.id,
                AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
                AtelierExerciseSet.content_hash == content_hash,
            )
            .first()
        )
        if existing_same_hash:
            existing_same_hash.model = model
            existing_same_hash.source = source
            existing_same_hash.payload = payload
            existing_same_hash.validation_notes = validation_notes
            self.db.add(existing_same_hash)
            self.db.commit()
            self.db.refresh(existing_same_hash)
            return existing_same_hash

        exercise_set = AtelierExerciseSet(
            concept_id=concept.id,
            generator_version=ATELIER_GENERATOR_VERSION,
            model=model,
            source=source,
            content_hash=content_hash,
            payload=payload,
            validation_notes=validation_notes,
        )
        self.db.add(exercise_set)
        self.db.commit()
        self.db.refresh(exercise_set)
        return exercise_set

    @staticmethod
    def validate_payload(payload: dict[str, Any], concept: GrammarConcept | None = None) -> bool:
        return not AtelierExerciseGenerator._payload_validation_errors(payload, concept=concept)

    @staticmethod
    def _payload_validation_errors(payload: dict[str, Any], concept: GrammarConcept | None = None) -> list[str]:
        errors: list[str] = []

        def filled(value: Any) -> bool:
            return bool(str(value or "").strip())

        def item_id(item: Any) -> str:
            return str((item or {}).get("id") or "?")

        recognize = payload.get("recognize") or {}
        if set(recognize.keys()) != {"fill", "word_bank", "classify"}:
            errors.append("recognize must include fill, word_bank, and classify")
            return errors
        if any(len((recognize[mode] or {}).get("items") or []) != 3 for mode in recognize):
            errors.append("each recognize mode must have exactly 3 items")
        for item in (recognize.get("fill") or {}).get("items") or []:
            if not (
                filled(item.get("id"))
                and filled(item.get("prompt"))
                and filled(item.get("correct_answer"))
                and len(item.get("choices") or []) >= 2
            ):
                errors.append(f"fill item {item_id(item)} is incomplete")
        for item in (recognize.get("word_bank") or {}).get("items") or []:
            if not (
                filled(item.get("id"))
                and filled(item.get("prompt"))
                and filled(item.get("correct_answer"))
                and len(item.get("tokens") or []) >= 3
                and len(item.get("answer_tokens") or []) >= 3
            ):
                errors.append(f"word_bank item {item_id(item)} is incomplete")
        for item in (recognize.get("classify") or {}).get("items") or []:
            if not (
                filled(item.get("id"))
                and filled(item.get("prompt"))
                and filled(item.get("correct_label"))
                and len(item.get("labels") or []) >= 2
            ):
                errors.append(f"classify item {item_id(item)} is incomplete")
        transform = ((payload.get("transform") or {}).get("items") or [])
        if len(transform) != 3:
            errors.append("transform must have exactly 3 items")
        for item in transform:
            if not (
                filled(item.get("id"))
                and filled(item.get("instruction"))
                and filled(item.get("source"))
                and filled(item.get("expected_answer"))
            ):
                errors.append(f"transform item {item_id(item)} is incomplete")
        produce = payload.get("produce") or {}
        if not (
            filled(produce.get("source_fragment"))
            and filled(produce.get("prompt"))
            and bool(produce.get("requirements"))
        ):
            errors.append("produce source_fragment, prompt, or requirements missing")
        ladder = payload.get("output_ladder") or {}
        for key in ("sentence", "speak", "conversation"):
            items = (ladder.get(key) or {}).get("items") or []
            if len(items) != 1:
                errors.append(f"output_ladder.{key}.items must contain exactly 1 item")
                continue
            for item in items:
                if not (
                    filled(item.get("id"))
                    and filled(item.get("type"))
                    and filled(item.get("instruction"))
                    and filled(item.get("prompt"))
                    and filled(item.get("example_answer"))
                    and bool(item.get("requirements"))
                ):
                    errors.append(f"output_ladder.{key} item {item_id(item)} is incomplete")
                    continue
                if concept and count_concept_hits(
                    concept,
                    str(item.get("example_answer") or ""),
                    task_text=" ".join(
                        [
                            str(item.get("instruction") or ""),
                            str(item.get("prompt") or ""),
                            str(item.get("requirements") or ""),
                        ]
                    ),
                ) <= 0:
                    errors.append(
                        f"output_ladder.{key} item {item_id(item)} example_answer does not demonstrate target concept"
                    )
        return errors

    def _generate_with_llm(self, concept: GrammarConcept, *, user: User | None = None) -> tuple[dict[str, Any], str, str] | None:
        generation_service = ExerciseGenerationService(
            self.db,
            llm_service=self._get_llm_service(),
        )
        validation_feedback: list[str] | None = None
        try:
            for attempt_index in range(2):
                bundle = generation_service.generate_atelier_exercise(
                    concept=concept,
                    user=user,
                    validation_feedback=validation_feedback,
                )
                payload = self._normalize_llm_exercise_payload(concept, bundle.payload)
                validation_errors = self._payload_validation_errors(payload, concept=concept)
                if not validation_errors:
                    return (
                        payload,
                        bundle.model,
                        bundle.validation_notes,
                    )
                logger.warning(
                    "Atelier LLM exercise payload failed validation: {}",
                    validation_errors,
                    concept_id=concept.id,
                    external_id=concept.external_id,
                    attempt=attempt_index + 1,
                )
                validation_feedback = validation_errors
            return None
        except (ExerciseGenerationUnavailable, json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning(
                "Atelier LLM exercise generation failed",
                concept_id=concept.id,
                external_id=concept.external_id,
                error=str(exc),
            )
            return None

    def _normalize_llm_exercise_payload(self, concept: GrammarConcept, payload: dict[str, Any]) -> dict[str, Any]:
        incoming = dict(payload)
        incoming_xray = incoming.get("xray") if isinstance(incoming.get("xray"), dict) else {}
        examples = _split_list(concept.anchor_examples) or _split_list(concept.examples)
        base_sentence = (
            str(incoming_xray.get("sentence") or "").strip()
            or (examples[0] if examples else "")
            or concept.name
        )
        payload = self._base(
            concept,
            sentence=base_sentence,
            marks=incoming_xray.get("marks") if isinstance(incoming_xray.get("marks"), list) else [],
        )
        payload.update(incoming)
        payload["concept"] = serialize_concept(concept)
        for item in (((payload.get("recognize") or {}).get("word_bank") or {}).get("items") or []):
            item_id = str(item.get("id") or "word-bank")
            answer_tokens = item.get("answer_tokens") or item.get("tokens") or []
            if not isinstance(answer_tokens, list):
                answer_tokens = str(item.get("correct_answer") or "").split()
            item["answer_tokens"] = [str(token) for token in answer_tokens]
            item["correct_answer"] = _join_french_tokens(item["answer_tokens"])
            tokens = item.get("tokens") or item["answer_tokens"]
            if not isinstance(tokens, list):
                tokens = item["answer_tokens"]
            if _normalize(_join_french_tokens(tokens)) == _normalize(item["correct_answer"]):
                item["tokens"] = _stable_scramble(item["answer_tokens"], item_id)
            else:
                item["tokens"] = [str(token) for token in tokens]
        produce = dict(payload.get("produce") or {})
        requirements = produce.get("requirements") or []
        raw_requirement = requirements[0] if requirements else {}
        produce["requirements"] = [
            {
                "concept_id": concept.id,
                "external_id": concept.external_id,
                "label": raw_requirement.get("label") or concept.name,
                "target_count": int(
                    raw_requirement.get("target_count")
                    or _produce_target_count(self.db, concept)
                ),
            }
        ]
        produce["min_words"] = int(produce.get("min_words") or 70)
        produce["max_words"] = int(produce.get("max_words") or 140)
        payload["produce"] = produce
        output_ladder = dict(payload.get("output_ladder") or {})
        for round_name in ("sentence", "speak", "conversation"):
            container = dict(output_ladder.get(round_name) or {})
            items = container.get("items") or []
            if not isinstance(items, list) or not items:
                raise ValueError(f"Missing output_ladder.{round_name}.items")
            normalized_items: list[dict[str, Any]] = []
            for index, raw_item in enumerate(items):
                item = dict(raw_item or {})
                requirements = item.get("requirements") or []
                raw_requirement = requirements[0] if requirements else {}
                item["requirements"] = [
                    {
                        "concept_id": concept.id,
                        "external_id": concept.external_id,
                        "label": raw_requirement.get("label") or concept.name,
                        "target_count": int(raw_requirement.get("target_count") or 1),
                    }
                ]
                item["id"] = str(item.get("id") or f"{concept.external_id or concept.id}-{round_name}-{index + 1}")
                item["min_words"] = int(item.get("min_words") or (5 if round_name == "sentence" else 6))
                item["max_words"] = int(item.get("max_words") or (30 if round_name == "conversation" else 24))
                normalized_items.append(item)
            container["items"] = normalized_items
            output_ladder[round_name] = container
        payload["output_ladder"] = output_ladder
        return payload

    def _get_llm_service(self) -> LLMService | None:
        if self.llm_service:
            return self.llm_service
        if not settings.ATELIER_LLM_ENABLED:
            return None
        if self._llm_unavailable:
            return None
        try:
            self.llm_service = LLMService()
            return self.llm_service
        except Exception as exc:
            self._llm_unavailable = True
            logger.info("Atelier LLM generation unavailable", error=str(exc))
            return None

    def _base(self, concept: GrammarConcept, *, sentence: str, marks: list[dict[str, str]]) -> dict[str, Any]:
        blueprint = AtelierAssetService(self.db).approved_blueprint_payload(concept)
        pedagogy = blueprint.get("pedagogy") or {}
        xray = blueprint.get("sentence_xray") or {}
        blueprint_marks = [
            {"text": mark.get("token") or mark.get("text") or "", "label": mark.get("role") or mark.get("label") or ""}
            for mark in xray.get("marks", [])
            if mark.get("token") or mark.get("text")
        ]
        examples = _split_list(concept.anchor_examples) or _split_list(concept.examples)
        traps = _split_list(concept.main_traps)
        return {
            "concept": serialize_concept(concept),
            "xray": {"sentence": xray.get("sentence") or sentence, "marks": blueprint_marks or marks},
            "rule_panel": {
                "title": concept.name,
                "rule": pedagogy.get("core_rule")
                or concept.core_rule
                or concept.description
                or "Use the form required by the sentence context.",
                "when": pedagogy.get("when_to_use") or self._when_text(concept),
                "pattern": pedagogy.get("pattern") or self._pattern_text(concept),
                "check": self._check_text(concept),
                "examples": (pedagogy.get("micro_examples") or examples)[:3],
                "traps": (pedagogy.get("main_traps") or traps)[:3],
            },
        }

    def _when_text(self, concept: GrammarConcept) -> str:
        return infer_grammar_profile(concept).when

    def _pattern_text(self, concept: GrammarConcept) -> str:
        return infer_grammar_profile(concept).pattern

    def _check_text(self, concept: GrammarConcept) -> str:
        return infer_grammar_profile(concept).check


class AtelierCorrectionService:
    """Exercise-aware checking and structured correction payloads."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm_service = llm_service
        self._llm_unavailable = False
        self.generator = AtelierExerciseGenerator(db, llm_service=llm_service)

    def submit_attempt(
        self,
        *,
        session: AtelierSession,
        user: User,
        concept: GrammarConcept | None,
        round_name: str,
        mode: str,
        exercise_id: str,
        answer_payload: dict[str, Any],
    ) -> AtelierAttempt:
        prompt_payload = self._prompt_payload(concept, round_name, mode, exercise_id, user=user)
        target_vocabulary = session_vocabulary_context(session)
        if target_vocabulary:
            prompt_payload = inject_vocabulary_context(prompt_payload, target_vocabulary)
        correction = self._correct_deterministic(
            concept=concept,
            round_name=round_name,
            mode=mode,
            exercise_id=exercise_id,
            prompt_payload=prompt_payload,
            answer_payload=answer_payload,
            session=session,
        )
        if target_vocabulary:
            correction = self._apply_target_vocabulary_credit(
                user=user,
                session=session,
                target_vocabulary=target_vocabulary,
                answer_payload=answer_payload,
                correction=correction,
            )
        correction = {
            **correction,
            "ai_review": self._initial_ai_review(round_name=round_name, answer_payload=answer_payload),
        }
        attempt = AtelierAttempt(
            atelier_session_id=session.id,
            user_id=user.id,
            concept_id=concept.id if concept else None,
            round=round_name,
            mode=mode,
            exercise_id=exercise_id,
            prompt_payload=prompt_payload,
            answer_payload=answer_payload,
            correction_payload=correction,
            verdict=correction["verdict"],
            score_0_4=float(correction["score_0_4"]),
        )
        self.db.add(attempt)
        self.db.flush([attempt])
        memory_updates = ErrorMemoryService(self.db).record_atelier_attempt(user=user, attempt=attempt)
        if memory_updates:
            correction = self._attach_memory_updates(correction, memory_updates)
            attempt.correction_payload = correction
            flag_modified(attempt, "correction_payload")
            self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    @staticmethod
    def _attach_memory_updates(correction: dict[str, Any], memory_updates: list[dict[str, Any]]) -> dict[str, Any]:
        next_correction = {**correction, "memory_updates": memory_updates}
        errata = list(next_correction.get("errata") or [])
        for update in memory_updates:
            index = update.get("erratum_index")
            if isinstance(index, int) and index < len(errata):
                errata[index] = {
                    **errata[index],
                    "id": update.get("id") or update.get("error_id"),
                    "memory_key": update.get("memory_key"),
                    "review_mode": update.get("review_mode"),
                    "source_type": update.get("source_type"),
                    "source_label": update.get("source_label"),
                    "reason": update.get("reason"),
                    "next_review_date": update.get("next_review_date"),
                }
        next_correction["errata"] = errata
        return next_correction

    def _apply_target_vocabulary_credit(
        self,
        *,
        user: User,
        session: AtelierSession,
        target_vocabulary: list[dict[str, Any]],
        answer_payload: dict[str, Any],
        correction: dict[str, Any],
    ) -> dict[str, Any]:
        word_ids = _dedupe_ints([item.get("word_id") for item in target_vocabulary])
        if not word_ids:
            return correction
        words = self.db.query(VocabularyWord).filter(VocabularyWord.id.in_(word_ids)).all()
        by_id = {word.id: word for word in words}
        answer_text = self._answer_text(answer_payload)
        normalized_answer = _normalize(answer_text)
        if not normalized_answer:
            return {
                **correction,
                "vocabulary_credit": {
                    "summary": VocabularyCreditService(self.db).summarize([]),
                    "events": [],
                },
            }

        credit_service = VocabularyCreditService(self.db)
        results = []
        for item in target_vocabulary:
            word = by_id.get(int(item.get("word_id") or 0))
            if not word or _normalize(word.word) not in normalized_answer:
                continue
            results.append(
                credit_service.apply(
                    user=user,
                    word=word,
                    event_type="produced_correct",
                    source_type="atelier",
                    learner_text=answer_text,
                    context=(item.get("example_sentence") or item.get("translation") or ""),
                    source_payload={
                        "atelier_session_id": str(session.id),
                        "reason": "target_vocabulary_used",
                    },
                )
            )
        return {
            **correction,
            "vocabulary_credit": {
                "summary": credit_service.summarize(results),
                "events": [result.to_dict() for result in results],
            },
        }

    @staticmethod
    def _answer_text(answer_payload: dict[str, Any]) -> str:
        text = answer_payload.get("text")
        if isinstance(text, str):
            return text
        answers = answer_payload.get("answers")
        if isinstance(answers, dict):
            parts: list[str] = []
            for value in answers.values():
                if isinstance(value, list):
                    parts.append(_join_french_tokens(value))
                else:
                    parts.append(str(value or ""))
            return " ".join(part for part in parts if part.strip())
        return str(text or "")

    def _correct_deterministic(
        self,
        *,
        concept: GrammarConcept | None,
        round_name: str,
        mode: str,
        exercise_id: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        session: AtelierSession | None = None,
    ) -> dict[str, Any]:
        if round_name == "recognize":
            return self._correct_recognize(concept, mode, prompt_payload, answer_payload)
        if round_name == "transform":
            return self._correct_transform_rule_based(concept, prompt_payload, answer_payload)
        if round_name in {"sentence", "speak", "conversation"}:
            return self._correct_output_ladder_rule_based(concept, round_name, prompt_payload, answer_payload)
        if round_name == "produce":
            concepts = self._session_concepts(session) if session else ([concept] if concept else [])
            return self._correct_produce_rule_based(concepts, prompt_payload, answer_payload)
        return {
            "verdict": "needs_review",
            "score_0_4": 0,
            "corrected_answer": "",
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ai_provider_configured(self) -> bool:
        return self.llm_service is not None or bool(settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY)

    def _can_schedule_ai_review(self) -> bool:
        return bool(settings.ATELIER_CORRECTION_LLM_ENABLED) and self._ai_provider_configured()

    def _initial_ai_review(self, *, round_name: str, answer_payload: dict[str, Any]) -> dict[str, Any]:
        answer_text = self._answer_text(answer_payload).strip()
        model = settings.ATELIER_CORRECTION_LLM_MODEL
        if round_name == "recognize":
            return {"status": "not_applicable", "auto_started": False}
        if round_name == "transform":
            return {"status": "available", "auto_started": False, "model": model}
        if round_name in ATELIER_AI_AUTO_ROUNDS and answer_text:
            if self._can_schedule_ai_review():
                return {
                    "status": "pending",
                    "auto_started": True,
                    "model": model,
                    "started_at": self._now_iso(),
                }
            return {
                "status": "failed",
                "auto_started": False,
                "model": model,
                "error": "AI provider unavailable.",
            }
        return {"status": "not_applicable", "auto_started": False}

    @staticmethod
    def ai_review_from_correction(correction: dict[str, Any] | None) -> dict[str, Any]:
        review = (correction or {}).get("ai_review") or {}
        return review if isinstance(review, dict) else {}

    def should_auto_start_ai_review(self, attempt: AtelierAttempt) -> bool:
        review = self.ai_review_from_correction(attempt.correction_payload)
        return review.get("status") == "pending" and bool(review.get("auto_started"))

    def mark_ai_review_pending(self, attempt: AtelierAttempt, *, auto_started: bool = False) -> tuple[AtelierAttempt, bool]:
        correction = dict(attempt.correction_payload or {})
        review = self.ai_review_from_correction(correction)
        status = str(review.get("status") or "")
        if status in {"pending", "complete"}:
            return attempt, False
        if status == "not_applicable":
            return attempt, False
        if not self._can_schedule_ai_review():
            correction["ai_review"] = {
                **review,
                "status": "failed",
                "auto_started": auto_started,
                "model": settings.ATELIER_CORRECTION_LLM_MODEL,
                "completed_at": self._now_iso(),
                "error": "AI provider unavailable.",
            }
            attempt.correction_payload = correction
            flag_modified(attempt, "correction_payload")
            self.db.add(attempt)
            self.db.commit()
            self.db.refresh(attempt)
            return attempt, False
        correction["ai_review"] = {
            **review,
            "status": "pending",
            "auto_started": auto_started,
            "model": settings.ATELIER_CORRECTION_LLM_MODEL,
            "started_at": self._now_iso(),
            "completed_at": None,
            "error": None,
        }
        attempt.correction_payload = correction
        flag_modified(attempt, "correction_payload")
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt, True

    def run_ai_review_for_attempt(self, attempt_id: UUID | str) -> AtelierAttempt | None:
        attempt = self.db.get(AtelierAttempt, UUID(str(attempt_id)))
        if not attempt:
            return None
        correction = dict(attempt.correction_payload or {})
        review = self.ai_review_from_correction(correction)
        if review.get("status") != "pending":
            return attempt
        user = self.db.get(User, attempt.user_id)
        session = self.db.get(AtelierSession, attempt.atelier_session_id)
        concept = self.db.get(GrammarConcept, attempt.concept_id) if attempt.concept_id else None
        if not user or not session:
            return self._mark_ai_review_failed(attempt, "Attempt context unavailable.")

        try:
            ai_correction = self.correct(
                concept=concept,
                round_name=attempt.round,
                mode=attempt.mode,
                exercise_id=attempt.exercise_id,
                prompt_payload=attempt.prompt_payload or {},
                answer_payload=attempt.answer_payload or {},
                session=session,
            )
            if (ai_correction.get("correction_debug") or {}).get("fallback_used"):
                return self._mark_ai_review_failed(attempt, "AI correction did not complete.")
            ai_review = {
                **review,
                "status": "complete",
                "auto_started": bool(review.get("auto_started")),
                "model": (ai_correction.get("correction_debug") or {}).get("model") or review.get("model"),
                "completed_at": self._now_iso(),
                "error": None,
            }
            if review.get("started_at") and not ai_review.get("started_at"):
                ai_review["started_at"] = review["started_at"]
            if correction.get("vocabulary_credit") and not ai_correction.get("vocabulary_credit"):
                ai_correction["vocabulary_credit"] = correction["vocabulary_credit"]
            ai_correction["ai_review"] = ai_review
            attempt.correction_payload = ai_correction
            attempt.verdict = ai_correction["verdict"]
            attempt.score_0_4 = float(ai_correction["score_0_4"])
            flag_modified(attempt, "correction_payload")
            self.db.add(attempt)
            self.db.flush([attempt])

            memory_updates = ErrorMemoryService(self.db).record_atelier_attempt(
                user=user,
                attempt=attempt,
                merge_same_attempt=True,
            )
            if memory_updates:
                ai_correction = self._attach_memory_updates(ai_correction, memory_updates)
                attempt.correction_payload = ai_correction
                flag_modified(attempt, "correction_payload")
                self.db.add(attempt)
            self.db.commit()
            self.db.refresh(attempt)
            return attempt
        except Exception as exc:  # pragma: no cover - defensive guard around background work
            logger.warning("Atelier background AI review failed", attempt_id=str(attempt_id), error=str(exc))
            return self._mark_ai_review_failed(attempt, "AI correction failed.")

    def _mark_ai_review_failed(self, attempt: AtelierAttempt, error: str) -> AtelierAttempt:
        correction = dict(attempt.correction_payload or {})
        review = self.ai_review_from_correction(correction)
        correction["ai_review"] = {
            **review,
            "status": "failed",
            "auto_started": bool(review.get("auto_started")),
            "model": review.get("model") or settings.ATELIER_CORRECTION_LLM_MODEL,
            "completed_at": self._now_iso(),
            "error": error,
        }
        attempt.correction_payload = correction
        flag_modified(attempt, "correction_payload")
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def correct(
        self,
        *,
        concept: GrammarConcept | None,
        round_name: str,
        mode: str,
        exercise_id: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        session: AtelierSession | None = None,
    ) -> dict[str, Any]:
        if round_name == "recognize":
            return self._correct_recognize(concept, mode, prompt_payload, answer_payload)
        if round_name == "transform":
            return self._correct_transform(concept, prompt_payload, answer_payload)
        if round_name in {"sentence", "speak", "conversation"}:
            return self._correct_output_ladder(concept, round_name, prompt_payload, answer_payload)
        if round_name == "produce":
            concepts = self._session_concepts(session) if session else ([concept] if concept else [])
            return self._correct_produce(concepts, prompt_payload, answer_payload)
        return {
            "verdict": "needs_review",
            "score_0_4": 0,
            "corrected_answer": "",
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    def _prompt_payload(
        self,
        concept: GrammarConcept | None,
        round_name: str,
        mode: str,
        exercise_id: str,
        *,
        user: User | None = None,
    ) -> dict[str, Any]:
        if not concept:
            return {"id": exercise_id, "round": round_name, "mode": mode}
        payload = self.generator.get_or_create(concept, user=user).payload
        if round_name == "recognize":
            return {"round": round_name, "mode": mode, **payload["recognize"][mode]}
        if round_name == "transform":
            return {"round": round_name, "mode": mode, **payload["transform"]}
        if round_name in {"sentence", "speak", "conversation"}:
            ladder = (payload.get("output_ladder") or {}).get(round_name) or {}
            return {"round": round_name, "mode": mode, **ladder}
        if round_name == "produce":
            return {"round": round_name, "mode": mode, **payload["produce"]}
        return {"id": exercise_id, "round": round_name, "mode": mode}

    def _correct_recognize(
        self,
        concept: GrammarConcept | None,
        mode: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        answers = answer_payload.get("answers") or {}
        items = prompt_payload.get("items") or []
        errata: list[dict[str, Any]] = []
        corrected: dict[str, Any] = {}
        correct_count = 0
        for item in items:
            item_id = item["id"]
            learner = answers.get(item_id)
            learner_text = _join_french_tokens(learner) if mode == "word_bank" and isinstance(learner, list) else str(learner or "")
            learner_norm = _normalize(learner_text)
            target = item.get("correct_label") if mode == "classify" else item.get("correct_answer")
            target_norm = _normalize(target)
            corrected[item_id] = target
            if learner_norm == target_norm:
                correct_count += 1
                continue
            if mode == "word_bank":
                errata.append(self._word_bank_erratum(concept, item, learner_text, str(target or "")))
            else:
                errata.append(self._recognize_erratum(concept, mode, item, learner_text, str(target or "")))
        score = round((correct_count / max(len(items), 1)) * 4, 2)
        return {
            "verdict": "correct" if correct_count == len(items) else ("partial" if correct_count else "incorrect"),
            "score_0_4": score,
            "corrected_answer": corrected,
            "concept_hits": [serialize_concept_hit(concept, correct_count, len(items))] if concept else [],
            "missing_targets": [],
            "errata": errata,
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    def _recognize_erratum(
        self,
        concept: GrammarConcept | None,
        mode: str,
        item: dict[str, Any],
        learner_text: str,
        target: str,
    ) -> dict[str, Any]:
        if not learner_text.strip():
            return self._recognize_erratum_payload(
                concept,
                item,
                label="Missing answer",
                learner_text="",
                target=target,
                why="You left this recognition item blank, so there is no grammar choice to review.",
                repair="Answer the item first; blank recognition items are not scheduled as grammar errata.",
                task_type="task_compliance",
                severity=1,
                recurring=False,
            )
        if mode == "fill":
            return self._fill_erratum(concept, item, learner_text, target)
        if mode == "classify":
            return self._classify_erratum(concept, item, learner_text, target)
        return self._recognize_erratum_payload(
            concept,
            item,
            label=self._label_for(concept, item),
            learner_text=learner_text,
            target=target,
            why=item.get("why_wrong") or self._why_for(concept),
            repair=item.get("repair_hint") or self._repair_for(concept),
            task_type=self._task_type_for(concept, item),
        )

    def _fill_erratum(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner_text: str,
        target: str,
    ) -> dict[str, Any]:
        learner_norm = _normalize(learner_text)
        target_norm = _normalize(target)
        label = self._label_for(concept, item)
        why = f"You chose `{learner_text}`, but this blank needs `{target}`."
        repair = item.get("repair_hint") or self._repair_for(concept)
        profile_key = infer_grammar_profile(concept).key if concept else ""

        if profile_key == "si_present_result_form":
            label = "Target form needed"
            if target_norm == "appellerai":
                if learner_norm == "appelle":
                    why = "You used present `appelle` in the result clause. In si type 1, the si-clause stays present and the consequence takes future simple, so the blank needs `appellerai`."
                elif learner_norm == "appellerais":
                    why = "You used conditional `appellerais`, which belongs to a hypothetical si frame. This sentence is a real future condition, so the result needs future simple `appellerai`."
                elif learner_norm == "ai appele":
                    why = "You used past tense `ai appelé`, but the sentence says what will happen if the condition is met. The result needs future simple `appellerai`."
                else:
                    why = "This si-clause is in the present, so the result clause needs future simple here."
                repair = "Keep the verb after si in the present, then put the consequence in future simple."
            elif target_norm == "prends":
                label = "Imperative result"
                if learner_norm == "prendras":
                    why = "Future `prendras` can be grammatical in si type 1, but this blank is a direct instruction: `take your coat`. The expected result is imperative `prends`."
                else:
                    why = f"You chose `{learner_text}`, but the result clause is a command, so it needs the imperative `prends`."
                repair = "When the result tells someone what to do, use the imperative after the si-clause."
            elif target_norm == "irons":
                if learner_norm == "allons":
                    why = "You used present `allons` in the result clause. With a present si-clause, the consequence should be future simple: `irons`."
                elif learner_norm == "irions":
                    why = "You used conditional `irions`, but this is a real future condition, not a hypothetical one. Use future simple `irons`."
                else:
                    why = "The condition is present, so the consequence needs future simple `irons`."
                repair = "Use present after si, then future simple for the consequence."
        elif profile_key == "article_after_negation":
            label = "Article after negation"
            if learner_norm in {"du", "de la", "des", "un", "une", "la", "les"}:
                why = f"You kept `{learner_text}` after `pas`. For a negated quantity, du/de la/des/un/une become `de` or `d'` after `pas`, so this blank needs `{target}`."
            else:
                why = "After `pas`, a negated quantity uses `de` or `d'` before the noun."
            repair = "Check whether the original article expresses quantity; after ne...pas, change it to de/d' unless the verb is être."
        elif profile_key == "tense_aspect":
            label = "Background vs event"
            if target_norm in {"pleuvait", "visitions", "sonnait"}:
                why = f"You chose `{learner_text}`, but this verb describes the ongoing background of the sentence, so it needs imparfait: `{target}`."
            else:
                why = f"You chose `{learner_text}`, but this verb is the bounded completed event, so it needs passé composé: `{target}`."
            repair = "Ask whether the verb is ongoing background or a completed event, then choose imparfait or passé composé."

        return self._recognize_erratum_payload(
            concept,
            item,
            label=label,
            learner_text=learner_text,
            target=target,
            why=why,
            repair=repair,
            task_type=self._task_type_for(concept, item),
        )

    def _classify_erratum(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner_text: str,
        target: str,
    ) -> dict[str, Any]:
        prompt = str(item.get("prompt") or "the form")
        learner_label = learner_text or "no label"
        label = "Classification"
        why = f"You classified `{prompt}` as `{learner_label}`, but the target label is `{target}`."
        repair = item.get("repair_hint") or self._repair_for(concept)
        profile_key = infer_grammar_profile(concept).key if concept else ""

        if profile_key == "si_present_result_form":
            label = "Form classification"
            if target == "present":
                why = f"You classified `{prompt}` as `{learner_label}`, but `{prompt}` is present tense in the si-clause."
            elif target == "imperative":
                why = f"You classified `{prompt}` as `{learner_label}`, but here `{prompt}` is an imperative command form, which can serve as the result in si type 1."
            elif target == "future":
                why = f"You classified `{prompt}` as `{learner_label}`, but `{prompt}` is future simple; the `-rai` ending marks the future result."
            repair = "Name the verb form before reading the whole sentence frame."
        elif profile_key == "tense_aspect":
            label = "Background vs event"
            if target == "background":
                why = f"You classified `{prompt}` as `{learner_label}`, but it describes an ongoing scene or state, so it belongs to the background/imparfait side."
            else:
                why = f"You classified `{prompt}` as `{learner_label}`, but it is a bounded completed event, so it belongs to the passé composé side."
            repair = "Use background for ongoing scene-setting; use bounded event for a completed interruption or action."
        elif profile_key == "article_after_negation":
            label = "Negation pattern"
            if _normalize(target) == "etre exception":
                why = f"You classified this as `{learner_label}`, but with `être`, the original article stays: `ce n'est pas du café`."
            else:
                why = f"You classified this as `{learner_label}`, but this is a normal negated quantity where the article changes to de/d'."
            repair = "First check whether the verb is être; if it is not, a negated quantity changes to de/d'."

        return self._recognize_erratum_payload(
            concept,
            item,
            label=label,
            learner_text=learner_text,
            target=target,
            why=why,
            repair=repair,
            task_type=self._task_type_for(concept, item),
        )

    def _recognize_erratum_payload(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        *,
        label: str,
        learner_text: str,
        target: str,
        why: str,
        repair: str,
        task_type: str,
        severity: int = 2,
        recurring: bool = False,
    ) -> dict[str, Any]:
        return {
            "display_label": label[:120],
            "learner_text": learner_text,
            "corrected_target": target,
            "why_wrong": why,
            "repair_hint": repair,
            "severity": severity,
            "recurring": recurring,
            "task_error_type": task_type,
            "concept_id": concept.id if concept else None,
            "external_id": concept.external_id if concept else None,
        }

    def _word_bank_erratum(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner_text: str,
        target: str,
    ) -> dict[str, Any]:
        learner_norm = _normalize(learner_text)
        target_norm = _normalize(target)
        label = "Word bank"
        why = "The built sentence does not match the target sentence."
        repair = f"Rebuild the sentence as: {target}"
        task_type = self._task_type_for(concept, item)
        profile_key = infer_grammar_profile(concept).key if concept else ""

        if profile_key == "si_present_result_form":
            issues: list[str] = []
            if "maintenat" in learner_norm and "maintenant" in target_norm:
                issues.append("`maintenat` is a spelling slip; the target word is `maintenant`")
            if "repondrais" in learner_norm and "repondrai" in target_norm:
                label = "Conditional vs future"
                why = "You built the right si-frame, but the result verb is `répondrais`, which is conditional. In a real condition with si + present, the consequence uses future simple: `répondrai`."
                repair = "Keep `Si elle appelle` in the present, then change only the result verb to future simple: `je répondrai`."
                return self._word_bank_erratum_payload(concept, item, label, learner_text, target, why, repair, task_type)
            swapped_si_future = (
                re.search(r"\bsi\s+nous\s+arriverons\b", learner_norm)
                and re.search(r"\bnous\s+partons\b", learner_norm)
                and "si nous partons" in target_norm
                and "nous arriverons" in target_norm
            )
            if swapped_si_future:
                label = "Future placed after si"
                why = "You put future `arriverons` inside the si-clause and present `partons` in the result. In si type 1, the condition stays present: `Si nous partons maintenant`; the consequence carries the future: `nous arriverons tôt`."
                repair = "Put the present action after `si`, then put the future action after the comma: `Si nous partons maintenant, nous arriverons tôt`."
                return self._word_bank_erratum_payload(concept, item, label, learner_text, target, why, repair, task_type)
            has_specific_result_issue = False
            if "arrivons" in learner_norm and "arriverons" in target_norm:
                has_specific_result_issue = True
                issues.append("the result clause uses present `arrivons`; si type 1 needs future simple `arriverons`")
            if not has_specific_result_issue and re.search(r"\bsi\b", learner_norm) and not re.search(
                r"\b\w+(rai|ras|ra|rons|rez|ront)\b|\b(prends|mange|apporte|allez|viens)\b",
                learner_norm,
            ):
                issues.append("the si-clause is present, but the result clause does not carry a future or imperative form")
            if issues:
                label = "Future result" if len(issues) == 1 else "Future result + spelling"
                why = "The sentence frame is close, but " + "; ".join(dict.fromkeys(issues)) + "."
                repair = "Keep the si-clause in the present, fix any spelling slips, and put the consequence in future simple or imperative."
        elif profile_key == "article_after_negation":
            if re.search(r"\bpas\s+(du|de la|des|un|une)\b", learner_norm):
                label = "Article after negation"
                why = "After pas, a negated quantity changes du/de la/des/un/une to de or d'."
                repair = "Keep ne...pas around the verb, then use de or d' before the noun unless the verb is être."
        elif profile_key == "tense_aspect":
            if learner_norm != target_norm:
                label = "Background vs event"
                why = "The sentence needs the same background/event contrast as the target."
            repair = "Use imparfait for the ongoing scene and passé composé for the bounded event."

        learner_tokens = learner_norm.split()
        target_tokens = target_norm.split()
        if label == "Word bank" and sorted(learner_tokens) == sorted(target_tokens):
            label = "Word order"
            why = "The right words are present, but they are not assembled in the target order."
            repair = f"Move the chips into this order: {target}"
        elif label == "Word bank":
            label = "Target sentence"

        return self._word_bank_erratum_payload(concept, item, label, learner_text, target, why, repair, task_type)

    def _word_bank_erratum_payload(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        label: str,
        learner_text: str,
        target: str,
        why: str,
        repair: str,
        task_type: str,
    ) -> dict[str, Any]:
        return {
            "display_label": label,
            "learner_text": learner_text,
            "corrected_target": target,
            "why_wrong": why,
            "repair_hint": repair,
            "severity": 2,
            "recurring": False,
            "task_error_type": task_type,
            "concept_id": concept.id if concept else None,
            "external_id": concept.external_id if concept else None,
        }

    def _correct_transform(
        self,
        concept: GrammarConcept | None,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._correct_transform_rule_based(concept, prompt_payload, answer_payload)
        if fallback["verdict"] == "correct" or not self._should_use_correction_llm():
            return fallback
        return self._correct_transform_with_llm(concept, prompt_payload, answer_payload, fallback) or fallback

    def _correct_transform_rule_based(
        self,
        concept: GrammarConcept | None,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        answers = answer_payload.get("answers") or {}
        items = prompt_payload.get("items") or []
        errata: list[dict[str, Any]] = []
        corrected: dict[str, str] = {}
        correct_count = 0
        for item in items:
            item_id = item["id"]
            learner = answers.get(item_id, "")
            target = item["expected_answer"]
            corrected[item_id] = target
            if not str(learner).strip():
                errata.append(
                    {
                        "display_label": "Missing rewrite",
                        "learner_text": "",
                        "corrected_target": target,
                        "why_wrong": "This rewrite was not attempted.",
                        "repair_hint": "Submit the rewrite when you want it reviewed; missed transform rows are not scheduled as grammar errata.",
                        "severity": 1,
                        "recurring": False,
                        "task_error_type": "task_compliance",
                        "concept_id": concept.id if concept else None,
                        "external_id": concept.external_id if concept else None,
                    }
                )
                continue
            if self._close_enough_transform(concept, learner, target):
                correct_count += 1
                continue
            errata.append(self._erratum(concept, item, learner, target, severity=3, recurring=True))
        score = round((correct_count / max(len(items), 1)) * 4, 2)
        return {
            "verdict": "correct" if correct_count == len(items) else ("partial" if correct_count else "incorrect"),
            "score_0_4": score,
            "corrected_answer": corrected,
            "concept_hits": [serialize_concept_hit(concept, correct_count, len(items))] if concept else [],
            "missing_targets": [],
            "errata": errata,
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    def _correct_output_ladder(
        self,
        concept: GrammarConcept | None,
        round_name: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._correct_output_ladder_rule_based(concept, round_name, prompt_payload, answer_payload)
        if not str(answer_payload.get("text") or "").strip() or not self._should_use_correction_llm():
            return fallback
        return self._correct_output_ladder_with_llm(concept, round_name, prompt_payload, answer_payload, fallback) or fallback

    def _correct_output_ladder_rule_based(
        self,
        concept: GrammarConcept | None,
        round_name: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        text = str(answer_payload.get("text") or "").strip()
        item = ((prompt_payload.get("items") or [{}])[0] or {})
        requirements = item.get("requirements") or (
            [
                {
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "label": concept.name,
                    "target_count": 1,
                }
            ]
            if concept
            else []
        )
        hits: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        total_required = sum(int(req.get("target_count") or 1) for req in requirements)
        total_hits = 0
        for req in requirements:
            detected = self._count_hits(req, text)
            total_hits += min(detected, int(req.get("target_count") or 1))
            hit = {**req, "detected_count": detected}
            hits.append(hit)
            if detected < int(req.get("target_count") or 1):
                missing.append(
                    {
                        **hit,
                        "missing_count": int(req.get("target_count") or 1) - detected,
                    }
                )

        errata: list[dict[str, Any]] = []
        if not text:
            errata.append(
                {
                    "display_label": "Missing output",
                    "learner_text": "",
                    "corrected_target": item.get("example_answer") or item.get("prompt") or "",
                    "why_wrong": "This output step was left blank, so it cannot strengthen active use yet.",
                    "repair_hint": "Produce one sentence or turn before submitting; blank output is not scheduled as grammar errata.",
                    "severity": 1,
                    "recurring": False,
                    "task_error_type": "task_compliance",
                    "concept_id": concept.id if concept else None,
                    "external_id": concept.external_id if concept else None,
                }
            )
        else:
            for req in missing:
                errata.append(
                    {
                        "display_label": item.get("errata_label") or self._label_for(concept, item),
                        "learner_text": text,
                        "corrected_target": item.get("example_answer") or req.get("label") or "",
                        "why_wrong": f"You submitted output, but this step needs {req.get('target_count', 1)} visible use of {req.get('label')} and only detected {req.get('detected_count', 0)}.",
                        "repair_hint": item.get("repair_hint") or self._repair_for(concept),
                        "severity": 1,
                        "recurring": False,
                        "task_error_type": "task_compliance",
                        "concept_id": req.get("concept_id"),
                        "external_id": req.get("external_id"),
                    }
                )

        score = round((total_hits / max(total_required, 1)) * 4, 2)
        if text and not missing:
            verdict = "accepted"
            score = max(score, 3.0)
        elif text:
            verdict = "partial"
        else:
            verdict = "needs_review"
        return {
            "verdict": verdict,
            "score_0_4": score,
            "corrected_answer": text or (item.get("example_answer") or ""),
            "concept_hits": hits,
            "missing_targets": missing,
            "errata": errata,
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    def _correct_produce(
        self,
        concepts: list[GrammarConcept | None],
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._correct_produce_rule_based(concepts, prompt_payload, answer_payload)
        if not str(answer_payload.get("text") or "").strip() or not self._should_use_correction_llm():
            return fallback
        return self._correct_produce_with_llm(concepts, prompt_payload, answer_payload, fallback) or fallback

    def _correct_produce_rule_based(
        self,
        concepts: list[GrammarConcept | None],
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        text = str(answer_payload.get("text") or "")
        requirements = self._integrated_requirements(concepts, prompt_payload)
        hits: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        total_required = sum(int(req["target_count"]) for req in requirements)
        total_hits = 0
        for req in requirements:
            count = self._count_hits(req, text)
            total_hits += min(count, int(req["target_count"]))
            hit = {**req, "detected_count": count}
            hits.append(hit)
            if count < int(req["target_count"]):
                missing.append({**hit, "missing_count": int(req["target_count"]) - count})
        errata = [
            {
                "display_label": "Missing writing target",
                "learner_text": text,
                "corrected_target": req["label"],
                "why_wrong": f"The writing submitted successfully, but it used this target {req['detected_count']} time(s) instead of {req['target_count']}.",
                "repair_hint": "Add the target naturally in revision; do not block submission for this.",
                "severity": 1,
                "recurring": False,
                "task_error_type": "task_compliance",
                "concept_id": req.get("concept_id"),
                "external_id": req.get("external_id"),
            }
            for req in missing
        ]
        score = round((total_hits / max(total_required, 1)) * 4, 2)
        verdict = "accepted" if text.strip() else "needs_review"
        return {
            "verdict": verdict,
            "score_0_4": score,
            "corrected_answer": text,
            "concept_hits": hits,
            "missing_targets": missing,
            "errata": errata,
            "correction_debug": _correction_debug(model=None, fallback_used=True),
        }

    def _compact_llm_concept(self, concept: GrammarConcept | None) -> dict[str, Any]:
        if not concept:
            return {}
        profile = infer_grammar_profile(concept)
        return {
            "id": concept.id,
            "external_id": concept.external_id,
            "name": concept.name,
            "core_rule": _compact_text(concept.core_rule or concept.description, max_length=360),
            "profile": profile.key,
        }

    def _compact_llm_task(self, prompt_payload: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key in ("round", "mode", "prompt", "source_fragment", "min_words", "max_words"):
            if prompt_payload.get(key) is not None:
                compact[key] = prompt_payload.get(key)
        if prompt_payload.get("requirements"):
            compact["requirements"] = prompt_payload.get("requirements")

        items = prompt_payload.get("items")
        if isinstance(items, list):
            compact_items: list[dict[str, Any]] = []
            for raw_item in items[:3]:
                if not isinstance(raw_item, dict):
                    continue
                item = {
                    key: raw_item.get(key)
                    for key in (
                        "id",
                        "type",
                        "instruction",
                        "prompt",
                        "source",
                        "expected_answer",
                        "example_answer",
                        "requirements",
                        "min_words",
                        "max_words",
                    )
                    if raw_item.get(key) is not None
                }
                compact_items.append(item)
            compact["items"] = compact_items
        return compact

    @staticmethod
    def _compact_llm_answer(answer_payload: dict[str, Any]) -> dict[str, Any]:
        if "text" in answer_payload:
            return {"text": _compact_text(answer_payload.get("text"), max_length=520)}
        answers = answer_payload.get("answers")
        if isinstance(answers, dict):
            return {
                "answers": {
                    str(key): _compact_text(value, max_length=220)
                    for key, value in list(answers.items())[:5]
                }
            }
        return {"raw": _compact_text(answer_payload, max_length=520)}

    @staticmethod
    def _compact_llm_assessment(fallback: dict[str, Any]) -> dict[str, Any]:
        return {
            "verdict": fallback.get("verdict"),
            "score_0_4": fallback.get("score_0_4"),
            "corrected_answer": fallback.get("corrected_answer"),
            "concept_hits": (fallback.get("concept_hits") or [])[:4],
            "missing_targets": (fallback.get("missing_targets") or [])[:4],
            "errata": [
                {
                    key: erratum.get(key)
                    for key in (
                        "display_label",
                        "learner_text",
                        "corrected_target",
                        "why_wrong",
                        "repair_hint",
                        "task_error_type",
                    )
                    if erratum.get(key) is not None
                }
                for erratum in (fallback.get("errata") or [])[:2]
                if isinstance(erratum, dict)
            ],
        }

    def _correct_output_ladder_with_llm(
        self,
        concept: GrammarConcept | None,
        round_name: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any] | None:
        llm = self._get_llm_service()
        if not llm or not concept:
            return None
        system_prompt = self._correction_system_prompt()
        user_payload = {
            "round": round_name,
            "concept": self._compact_llm_concept(concept),
            "task": self._compact_llm_task(prompt_payload),
            "answer": self._compact_llm_answer(answer_payload),
            "requirements": ((prompt_payload.get("items") or [{}])[0] or {}).get("requirements") or [],
            "deterministic_assessment": self._compact_llm_assessment(fallback),
            "instructions": [
                "This is part of a guided output ladder: short sentence, spoken transcript, or conversation turn.",
                "Accept natural original French if it uses the target concept correctly; it does not need to match the example answer.",
                "Address feedback directly with 'you'; never say 'the learner' or 'the user'.",
                "Create recurring grammar errata only for concrete errors in the submitted output, not for missing target counts.",
                "For spoken_response, treat the typed text as the transcript of what the person said.",
                "For conversation_turn, judge whether the reply is plausible in context and uses the target concept.",
            ],
        }
        return self._llm_correction(
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
            system_prompt=system_prompt,
            concepts=[concept],
            fallback=fallback,
            corrected_answer_mode="text",
        )

    def _correct_transform_with_llm(
        self,
        concept: GrammarConcept | None,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any] | None:
        llm = self._get_llm_service()
        if not llm or not concept:
            return None
        system_prompt = self._correction_system_prompt()
        user_payload = {
            "round": "transform",
            "concept": self._compact_llm_concept(concept),
            "task": self._compact_llm_task(prompt_payload),
            "answer": self._compact_llm_answer(answer_payload),
            "deterministic_target": fallback.get("corrected_answer"),
            "deterministic_assessment": self._compact_llm_assessment(fallback),
            "instructions": [
                "Review each rewrite against the exercise instruction and concept rule.",
                "Address feedback directly with 'you'; never say 'the learner' or 'the user'.",
                "For every erratum, explain the exact form you wrote, why that form fails this task, and what the target form does differently.",
                "Errata should be recurring only for grammar mistakes, not blank or task-compliance misses.",
            ]
            + _concept_correction_instructions([concept]),
        }
        return self._llm_correction(
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
            system_prompt=system_prompt,
            concepts=[concept],
            fallback=fallback,
            corrected_answer_mode="map",
        )

    def _correct_produce_with_llm(
        self,
        concepts: list[GrammarConcept | None],
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any] | None:
        llm = self._get_llm_service()
        clean_concepts = [concept for concept in concepts if concept]
        if not llm or not clean_concepts:
            return None
        system_prompt = self._correction_system_prompt()
        user_payload = {
            "round": "produce",
            "concepts": [self._compact_llm_concept(concept) for concept in clean_concepts],
            "task": self._compact_llm_task(prompt_payload),
            "answer": self._compact_llm_answer(answer_payload),
            "requirements": self._integrated_requirements(clean_concepts, prompt_payload),
            "deterministic_assessment": self._compact_llm_assessment(fallback),
            "instructions": [
                "Accept the writing even when required targets are missing; missing targets are task-compliance slips.",
                "Address feedback directly with 'you'; never say 'the learner' or 'the user'.",
                "Create grammar errata only for concrete French grammar errors visible in the submitted text.",
                "Separate grammar, pronoun, vocabulary/lexical-choice, spelling, and task-compliance issues instead of collapsing them into one label.",
                "If you flag wrong vocabulary, use task_error_type 'lexical_choice' or 'vocabulary_choice' and explain the intended meaning.",
            ]
            + _concept_correction_instructions(clean_concepts),
        }
        return self._llm_correction(
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
            system_prompt=system_prompt,
            concepts=clean_concepts,
            fallback=fallback,
            corrected_answer_mode="text",
        )

    def _llm_correction(
        self,
        *,
        messages: list[dict[str, str]],
        system_prompt: str,
        concepts: list[GrammarConcept],
        fallback: dict[str, Any],
        corrected_answer_mode: str,
    ) -> dict[str, Any] | None:
        llm = self._get_llm_service()
        if not llm:
            return None
        try:
            result = llm.generate_error_detection(
                messages,
                system_prompt=system_prompt,
                response_format=ATELIER_CORRECTION_RESPONSE_FORMAT,
                temperature=0.1,
                max_tokens=settings.ATELIER_CORRECTION_LLM_MAX_TOKENS,
                model=settings.ATELIER_CORRECTION_LLM_MODEL,
                request_timeout=settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
                reasoning_effort=settings.ATELIER_CORRECTION_LLM_REASONING_EFFORT,
            )
            parsed = json.loads(result.content)
            return self._normalize_llm_correction(
                parsed,
                concepts=concepts,
                fallback=fallback,
                corrected_answer_mode=corrected_answer_mode,
                model=result.model,
            )
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Atelier LLM correction failed; using deterministic fallback", error=str(exc))
            return None

    def _normalize_llm_correction(
        self,
        parsed: dict[str, Any],
        *,
        concepts: list[GrammarConcept],
        fallback: dict[str, Any],
        corrected_answer_mode: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        concept_by_external_id = {concept.external_id: concept for concept in concepts}
        default_concept = concepts[0] if len(concepts) == 1 else None

        corrected_answer: Any
        if corrected_answer_mode == "map":
            corrected_answer = dict(fallback.get("corrected_answer") or {})
            for item in parsed.get("corrected_answers") or []:
                item_id = item.get("item_id")
                if item_id:
                    corrected_answer[item_id] = item.get("corrected_answer") or corrected_answer.get(item_id, "")
            if any(infer_grammar_profile(concept).key == "si_present_result_form" for concept in concepts):
                fallback_answers = fallback.get("corrected_answer") or {}
                for item_id, answer in list(corrected_answer.items()):
                    if "quand" in _normalize(answer) and item_id in fallback_answers:
                        corrected_answer[item_id] = fallback_answers[item_id]
        else:
            corrected_answer = parsed.get("corrected_answer") or fallback.get("corrected_answer") or ""

        concept_hits = []
        for hit in parsed.get("concept_hits") or []:
            external_id = hit.get("external_id")
            concept = concept_by_external_id.get(external_id)
            concept_hits.append(
                {
                    "concept_id": concept.id if concept else None,
                    "external_id": external_id,
                    "label": hit.get("label") or (concept.name if concept else "Grammar target"),
                    "detected_count": int(hit.get("detected_count") or 0),
                    "target_count": int(hit.get("target_count") or 0),
                }
            )
        if not concept_hits:
            concept_hits = fallback.get("concept_hits") or []

        missing_targets = []
        for missing in parsed.get("missing_targets") or []:
            external_id = missing.get("external_id")
            concept = concept_by_external_id.get(external_id)
            missing_targets.append(
                {
                    "concept_id": concept.id if concept else None,
                    "external_id": external_id,
                    "label": missing.get("label") or (concept.name if concept else "Grammar target"),
                    "detected_count": int(missing.get("detected_count") or 0),
                    "target_count": int(missing.get("target_count") or 0),
                    "missing_count": int(missing.get("missing_count") or 0),
                }
            )

        errata = []
        for item in parsed.get("errata") or []:
            external_id = item.get("external_id")
            concept = concept_by_external_id.get(external_id) or default_concept
            severity = max(1, min(4, int(item.get("severity") or 2)))
            task_error_type = item.get("task_error_type") or self._task_type_for(concept, {})
            why_wrong = self._clean_feedback_text(item.get("why_wrong") or self._why_for(concept))
            repair_hint = self._clean_feedback_text(item.get("repair_hint") or self._repair_for(concept))
            display_label = str(item.get("display_label") or "")
            if display_label.strip().lower() in {"", "target form needed", "grammar target", "word order"}:
                display_label = self._label_for(concept, {})
            corrected_target = str(item.get("corrected_target") or "")
            if concept and infer_grammar_profile(concept).key == "si_present_result_form" and "quand" in _normalize(corrected_target):
                fallback_answers = fallback.get("corrected_answer") or {}
                si_target = next((value for value in fallback_answers.values() if " si " in f" {_normalize(value)} "), "")
                corrected_target = str(si_target or corrected_target)
            errata.append(
                {
                    "display_label": display_label[:120],
                    "learner_text": str(item.get("learner_text") or ""),
                    "corrected_target": corrected_target,
                    "why_wrong": why_wrong,
                    "repair_hint": repair_hint,
                    "severity": severity,
                    "recurring": bool(item.get("recurring")) and task_error_type != "task_compliance",
                    "task_error_type": str(task_error_type),
                    "concept_id": concept.id if concept else None,
                    "external_id": external_id or (concept.external_id if concept else None),
                }
            )
        if not errata and fallback.get("errata"):
            errata = fallback["errata"]

        verdict = parsed.get("verdict") or fallback.get("verdict") or "needs_review"
        if verdict not in {"correct", "partial", "incorrect", "accepted", "needs_review"}:
            verdict = fallback.get("verdict") or "needs_review"
        score = float(parsed.get("score_0_4") if parsed.get("score_0_4") is not None else fallback.get("score_0_4", 0))
        score = max(0.0, min(4.0, round(score, 2)))
        return {
            "verdict": verdict,
            "score_0_4": score,
            "corrected_answer": corrected_answer,
            "concept_hits": concept_hits,
            "missing_targets": missing_targets if parsed.get("missing_targets") is not None else fallback.get("missing_targets", []),
            "errata": errata,
            "correction_debug": _correction_debug(model=model, fallback_used=False),
        }

    def _correction_system_prompt(self) -> str:
        return (
            "You are Atelier's French grammar correction engine. "
            "Return only JSON matching the strict schema. "
            "The correction must be exercise-aware: judge the submitted answer against the requested task, not just grammatical French. "
            "Address the person directly as 'you'. Never write 'the learner', 'learner', or 'the user' in why_wrong or repair_hint. "
            "Use the concept profile to create accessible, specific labels rather than generic grammar buckets. "
            "The why field must name the concrete submitted form, the expected target form, and the grammar reason. "
            "The repair field must give a concrete next action, not generic advice. "
            "Task-compliance slips can be shown, but do not mark them recurring unless they are repeated grammar errors."
        )

    def _clean_feedback_text(self, text: Any) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return ""
        substitutions = [
            (r"\bThe learner's\b", "Your"),
            (r"\bthe learner's\b", "your"),
            (r"\bThe user's\b", "Your"),
            (r"\bthe user's\b", "your"),
            (r"\bThe learner\b", "You"),
            (r"\bthe learner\b", "you"),
            (r"\bThe user\b", "You"),
            (r"\bthe user\b", "you"),
            (r"\bLearner\b", "You"),
            (r"\blearner\b", "you"),
            (r"\bUser\b", "You"),
            (r"\buser\b", "you"),
        ]
        for pattern, replacement in substitutions:
            cleaned = re.sub(pattern, replacement, cleaned)
        return cleaned

    def _get_llm_service(self) -> LLMService | None:
        if self.llm_service:
            return self.llm_service
        if not settings.ATELIER_LLM_ENABLED:
            return None
        if self._llm_unavailable:
            return None
        try:
            self.llm_service = LLMService()
            return self.llm_service
        except Exception as exc:
            self._llm_unavailable = True
            logger.info("Atelier LLM correction unavailable; using deterministic fallback", error=str(exc))
            return None

    def _should_use_correction_llm(self) -> bool:
        return self.llm_service is not None or bool(settings.ATELIER_CORRECTION_LLM_ENABLED)

    def _session_concepts(self, session: AtelierSession | None) -> list[GrammarConcept]:
        if not session:
            return []
        ids = session.selected_concept_ids or []
        return list(self.db.query(GrammarConcept).filter(GrammarConcept.id.in_(ids)).all())

    def _integrated_requirements(
        self,
        concepts: list[GrammarConcept | None],
        prompt_payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if concepts:
            requirements = []
            for concept in concepts:
                if not concept:
                    continue
                count = _produce_target_count(self.db, concept)
                requirements.append(
                    {
                        "concept_id": concept.id,
                        "external_id": concept.external_id,
                        "label": concept.name,
                        "target_count": count,
                    }
                )
            return requirements
        return prompt_payload.get("requirements") or []

    def _count_hits(self, requirement: dict[str, Any], text: str) -> int:
        concept = self._concept_for_requirement(requirement)
        return count_concept_hits(
            concept,
            text,
            task_text=" ".join(str(requirement.get(key) or "") for key in ("label", "external_id")),
        )

    def _concept_for_requirement(self, requirement: dict[str, Any]) -> GrammarConcept | None:
        concept_id = requirement.get("concept_id")
        if concept_id:
            try:
                concept = self.db.get(GrammarConcept, int(concept_id))
                if concept:
                    return concept
            except (TypeError, ValueError):
                pass
        external_id = requirement.get("external_id")
        if external_id:
            return self.db.query(GrammarConcept).filter(GrammarConcept.external_id == str(external_id)).first()
        return None

    def _close_enough_transform(self, concept: GrammarConcept | None, learner: str, target: str) -> bool:
        learner_norm = _normalize(learner)
        target_norm = _normalize(target)
        if learner_norm == target_norm:
            return True
        profile = infer_grammar_profile(concept) if concept else None
        if profile and profile.key == "si_present_result_form":
            if "quand" in learner_norm:
                return False
            return " si " in f" {learner_norm} " and not re.search(r"\b(si\s+\w+ra|si\s+\w+ras|si\s+\w+rai)\b", learner_norm)
        if profile and profile.key == "article_after_negation":
            return "pas de" in learner_norm or "pas d'" in learner_norm
        return False

    def _erratum(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner: Any,
        target: Any,
        *,
        severity: int,
        recurring: bool,
    ) -> dict[str, Any]:
        is_rewrite = bool(item.get("type"))
        return {
            "display_label": self._label_for(concept, item),
            "learner_text": "" if learner is None else (" ".join(learner) if isinstance(learner, list) else str(learner)),
            "corrected_target": "" if target is None else str(target),
            "why_wrong": self._why_for(concept) if is_rewrite else (item.get("why_wrong") or self._why_for(concept)),
            "repair_hint": self._repair_for(concept) if is_rewrite else (item.get("repair_hint") or self._repair_for(concept)),
            "severity": severity,
            "recurring": recurring,
            "task_error_type": self._task_type_for(concept, item),
            "concept_id": concept.id if concept else None,
            "external_id": concept.external_id if concept else None,
        }

    def _label_for(self, concept: GrammarConcept | None, item: dict[str, Any]) -> str:
        if item.get("errata_label"):
            label = str(item["errata_label"])
        elif concept:
            label = infer_grammar_profile(concept, task_text=" ".join(str(item.get(key) or "") for key in ("instruction", "prompt", "label"))).label
        else:
            label = "Grammar target"
        return label[:120]

    def _task_type_for(self, concept: GrammarConcept | None, item: dict[str, Any]) -> str:
        if concept:
            return infer_grammar_profile(concept, task_text=" ".join(str(item.get(key) or "") for key in ("instruction", "prompt", "label"))).key
        return str(item.get("type") or "grammar_target")

    def _why_for(self, concept: GrammarConcept | None) -> str:
        return infer_grammar_profile(concept).principle if concept else "The answer does not match the requested grammar target."

    def _repair_for(self, concept: GrammarConcept | None) -> str:
        return infer_grammar_profile(concept).repair if concept else "Name the trigger, then apply the target form."


def run_atelier_ai_review(attempt_id: UUID | str) -> None:
    """Run optional Atelier AI enrichment outside the request session."""
    db = SessionLocal()
    try:
        AtelierCorrectionService(db).run_ai_review_for_attempt(attempt_id)
    except Exception as exc:  # pragma: no cover - background safety net
        logger.warning("Atelier AI review worker could not run", attempt_id=str(attempt_id), error=str(exc))
    finally:
        db.close()


class AtelierSRSService:
    """Update concept mastery, recurring errata, and recap state."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def complete_session(self, *, session: AtelierSession, user: User) -> dict[str, Any]:
        attempts = list(
            self.db.query(AtelierAttempt)
            .filter(AtelierAttempt.atelier_session_id == session.id)
            .order_by(AtelierAttempt.created_at.asc())
            .all()
        )
        scores_by_concept: dict[int, list[float]] = defaultdict(list)
        errata_count = 0
        errata_rows: list[dict[str, Any]] = []
        error_memory = ErrorMemoryService(self.db)
        for attempt in attempts:
            if attempt.concept_id:
                scores_by_concept[attempt.concept_id].append(float(attempt.score_0_4 or 0))
            correction_payload = attempt.correction_payload or {}
            memory_updates = correction_payload.get("memory_updates") or error_memory.record_atelier_attempt(
                user=user,
                attempt=attempt,
            )
            if memory_updates and not correction_payload.get("memory_updates"):
                correction_payload["memory_updates"] = memory_updates
                attempt.correction_payload = correction_payload
                self.db.add(attempt)
            for persisted in memory_updates:
                if persisted.get("action") != "skipped":
                    errata_count += 1
                    errata_rows.append(persisted)

        progress_rows = []
        grammar_service = GrammarService(self.db)
        concept_ids = [int(item) for item in (session.selected_concept_ids or [])]
        for concept_id in concept_ids:
            values = scores_by_concept.get(concept_id) or [0.0]
            quality = round((sum(values) / len(values)) / 4 * 10, 1)
            progress = grammar_service.record_review(
                user=user,
                concept_id=concept_id,
                score=quality,
                notes=f"Atelier session {session.id}",
            )
            progress_rows.append(
                {
                    "concept_id": concept_id,
                    "score": progress.score,
                    "state": progress.state,
                    "next_review": progress.next_review.isoformat() if progress.next_review else None,
                }
            )

        previous_streak = getattr(user, "grammar_streak_days", 0) or 0
        self._update_streak(user)
        recap = {
            "concepts_repaired": len([row for row in progress_rows if row["score"] >= 5]),
            "errata_logged": errata_count,
            "strengthened": len(progress_rows),
            "streak_before": previous_streak,
            "streak_after": getattr(user, "grammar_streak_days", 0) or 0,
            "concepts": progress_rows,
            "attempts": len(attempts),
            "errata": errata_rows,
        }
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        session.recap_payload = recap
        self.db.add(session)
        self.db.commit()
        return recap

    def _update_streak(self, user: User) -> None:
        today = date.today()
        last = getattr(user, "grammar_last_review_date", None)
        if last == today:
            return
        if last == today - timedelta(days=1):
            user.grammar_streak_days = (user.grammar_streak_days or 0) + 1
        else:
            user.grammar_streak_days = 1
        user.grammar_last_review_date = today
        user.grammar_longest_streak = max(user.grammar_longest_streak or 0, user.grammar_streak_days or 0)
        user.mark_activity(today)
        self.db.add(user)


def serialize_concept(concept: GrammarConcept) -> dict[str, Any]:
    return {
        "id": concept.id,
        "external_id": concept.external_id,
        "name": concept.name,
        "level": concept.level,
        "category": concept.category,
        "subskill": concept.subskill,
        "core_rule": concept.core_rule,
        "main_traps": _split_list(concept.main_traps),
        "anchor_examples": _split_list(concept.anchor_examples),
        "exercise_tags": concept.exercise_tags or [],
        "is_foundation": concept.is_foundation,
    }


def serialize_concept_hit(concept: GrammarConcept | None, count: int, total: int) -> dict[str, Any]:
    if not concept:
        return {"concept_id": None, "label": "Unknown", "detected_count": count, "target_count": total}
    return {
        "concept_id": concept.id,
        "external_id": concept.external_id,
        "label": concept.name,
        "detected_count": count,
        "target_count": total,
    }


def serialize_erratum_record(error: UserError) -> dict[str, Any]:
    return serialize_error_memory(error)


__all__ = [
    "ATELIER_GENERATOR_VERSION",
    "AtelierCorrectionService",
    "AtelierExerciseGenerationError",
    "AtelierExerciseGenerator",
    "AtelierScheduler",
    "AtelierSRSService",
    "run_atelier_ai_review",
    "serialize_erratum_record",
    "serialize_concept",
]
