"""Atelier grammar practice services."""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.db.session import SessionLocal
from app.db.models.atelier import AtelierAttempt, AtelierExerciseSet, AtelierGenerationEvent, AtelierSession
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.progress import UserVocabularyProgress
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

ATELIER_GENERATOR_VERSION = "atelier-v8"
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
                        "meaning_cue": {"type": "string"},
                        "tokens": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "answer_tokens": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        "correct_answer": {"type": "string"},
                    },
                    "required": ["id", "prompt", "meaning_cue", "tokens", "answer_tokens", "correct_answer"],
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
                            "item_id": {"type": "string"},
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
                            "item_id",
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


ATELIER_EXERCISE_CRITIQUE_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "atelier_exercise_critique",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "item_id": {"type": "string"},
                            "round": {"type": "string"},
                            "mode": {"type": "string"},
                            "passes": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["item_id", "round", "mode", "passes", "reason"],
                    },
                }
            },
            "required": ["verdicts"],
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


def _tokenize_french_sentence(sentence: str) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?|[.,!?;:]", sentence)
    return [token.replace("’", "'") for token in tokens if token.strip()]


def _bounded_edit_distance(left: str, right: str, *, limit: int) -> int:
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for row_index, left_char in enumerate(left, start=1):
        current = [row_index]
        row_min = current[0]
        for column_index, right_char in enumerate(right, start=1):
            substitution_cost = 0 if left_char == right_char else 1
            value = min(
                previous[column_index] + 1,
                current[column_index - 1] + 1,
                previous[column_index - 1] + substitution_cost,
            )
            current.append(value)
            row_min = min(row_min, value)
        if row_min > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _multiset_subset(required: list[Any], available: list[Any]) -> bool:
    required_counts = Counter(_normalize(token) for token in required if _normalize(token))
    available_counts = Counter(_normalize(token) for token in available if _normalize(token))
    return all(available_counts[token] >= count for token, count in required_counts.items())


def _has_adjacent_duplicate_tokens(tokens: list[Any]) -> bool:
    normalized = [_normalize(token) for token in tokens if _normalize(token)]
    return any(left == right for left, right in zip(normalized, normalized[1:], strict=False))


def _normalized_counter(values: list[Any]) -> Counter[str]:
    return Counter(_normalize(value) for value in values if _normalize(value))


def _extra_normalized_tokens(answer_tokens: list[Any], tokens: list[Any]) -> list[str]:
    answer_counts = _normalized_counter(answer_tokens)
    extras: list[str] = []
    for token in tokens:
        normalized = _normalize(token)
        if not normalized:
            continue
        if answer_counts[normalized] > 0:
            answer_counts[normalized] -= 1
        else:
            extras.append(normalized)
    return extras


_FALLBACK_MEANING_CUES: dict[str, str] = {
    "si tu viens demain nous partirons tot": "Express: If you come tomorrow, we will leave early.",
    "s il pleut prends ton manteau": "Express: If it rains, take your coat.",
    "si elle appelle je repondrai tout de suite": "Express: If she calls, I will answer right away.",
    "je ne bois pas de cafe": "Express: I do not drink coffee.",
    "elle n a pas d idee": "Express: She does not have an idea.",
    "nous n avons pas de dossier aujourd hui": "Express: We do not have a file today.",
    "je marchais quand une voiture est passee": "Express: I was walking when a car passed.",
    "il faisait froid puis nous sommes entres": "Express: It was cold, then we went in.",
    "elle attendait quand j ai repondu": "Express: She was waiting when I replied.",
    "je voudrais partir demain": "Express: I would like to leave tomorrow.",
    "nous pourrions venir plus tot": "Express: We could come earlier.",
    "elle aimerait parler avec vous": "Express: She would like to speak with you.",
    "il faut que tu sois pret": "Express: You have to be ready.",
    "je veux qu elle vienne demain": "Express: I want her to come tomorrow.",
    "bien qu il soit tard nous continuons": "Express: Although it is late, we are continuing.",
    "c est le livre que j ai lu": "Express: It is the book that I read.",
    "voici l ami qui arrive": "Express: Here is the friend who is arriving.",
    "la ville ou j habite est calme": "Express: The city where I live is calm.",
}


def _word_bank_meaning_cue(concept: GrammarConcept | None, correct_answer: Any) -> str:
    answer = _join_french_tokens(correct_answer) if isinstance(correct_answer, list) else str(correct_answer or "")
    normalized = _normalize(answer)
    if _FALLBACK_MEANING_CUES.get(normalized):
        return _FALLBACK_MEANING_CUES[normalized]
    profile = infer_grammar_profile(concept) if concept else None
    label = profile.label.lower() if profile else "the target grammar"
    return f"Express a complete sentence in French using {label}; use every target chip once."


def _quoted_fragments(value: Any) -> list[str]:
    fragments: list[str] = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"|«([^»]+)»", str(value or "")):
        fragment = next((group for group in match.groups() if group), "")
        if fragment.strip():
            fragments.append(fragment.strip())
    return fragments


def _directed_rewrite_instruction_errors(item: dict[str, Any]) -> list[str]:
    if item.get("type") != "directed_rewrite":
        return []
    instruction = str(item.get("instruction") or "")
    source = _normalize(item.get("source"))
    expected = _normalize(item.get("expected_answer"))
    quoted = _quoted_fragments(instruction)
    has_source_fragment = any(_normalize(fragment) and _normalize(fragment) in source for fragment in quoted)
    has_target_form = any(
        _normalize(fragment)
        and _normalize(fragment) in expected
        and _normalize(fragment) not in source
        for fragment in quoted
    )
    has_target_marker = bool(
        re.search(
            r"\b(?:to|into|use|target|form|present|future|imparfait|passe|passé|conditional|conditionnel|subjunctive|subjonctif)\b",
            instruction,
            re.I,
        )
    )
    if not has_source_fragment:
        return ["directed_rewrite instructions must quote the source word or phrase to change"]
    if not (has_target_form or has_target_marker):
        return ["directed_rewrite instructions must name the target form to use"]
    return []


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for left_char, right_char in zip(left, right, strict=False):
        if left_char != right_char:
            break
        count += 1
    return count


def _looks_like_adjacent_form(target: Any, candidate: Any) -> bool:
    target_norm = _normalize(target)
    candidate_norm = _normalize(candidate)
    if not target_norm or not candidate_norm or target_norm == candidate_norm:
        return False
    if len(target_norm) < 3 or len(candidate_norm) < 3:
        return False
    prefix_threshold = 3 if len(target_norm) <= 3 or len(candidate_norm) <= 3 else 4
    return _common_prefix_length(target_norm, candidate_norm) >= prefix_threshold or _bounded_edit_distance(
        target_norm,
        candidate_norm,
        limit=3,
    ) <= 3


def _contains_blank_marker(value: Any) -> bool:
    text = str(value or "")
    return "___" in text or "____" in text or bool(re.search(r"\b(blank|gap)\b", text, flags=re.IGNORECASE))


_GENERIC_CLASSIFY_LABEL_SETS: tuple[set[str], ...] = (
    {"affirmative", "negative"},
    {"positive", "negative"},
    {"positif", "negatif"},
    {"vrai", "faux"},
    {"true", "false"},
    {"yes", "no"},
    {"oui", "non"},
)


def _is_generic_classify_labels(labels: list[Any]) -> bool:
    normalized = {_normalize(label) for label in labels if _normalize(label)}
    if len(normalized) != 2:
        return False
    return any(normalized == generic for generic in _GENERIC_CLASSIFY_LABEL_SETS)


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


_ATELIER_STARTER_VOCABULARY = (
    "aller",
    "avoir",
    "être",
    "faire",
    "prendre",
    "venir",
    "voir",
    "savoir",
    "dire",
    "jour",
    "temps",
    "maison",
    "travail",
    "ville",
    "marché",
    "train",
    "métro",
    "café",
    "dossier",
    "livre",
    "ami",
    "famille",
    "soir",
    "matin",
)


def _has_vocabulary_history(db: Session, user: User) -> bool:
    return (
        db.query(UserVocabularyProgress.id)
        .filter(UserVocabularyProgress.user_id == user.id)
        .first()
        is not None
    )


def _starter_vocabulary_items(db: Session, *, user: User, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    target_language = (user.target_language or "fr").strip() or "fr"
    stopwords = ProgressService._queue_stopwords()
    starter_surfaces = {_normalize(surface) for surface in _ATELIER_STARTER_VOCABULARY} | {
        surface.strip().lower() for surface in _ATELIER_STARTER_VOCABULARY
    }
    base_query = (
        db.query(VocabularyWord)
        .filter(VocabularyWord.language == target_language)
        .filter(func.length(VocabularyWord.word) > 2)
        .filter(func.lower(VocabularyWord.word).notin_(stopwords))
        .filter((VocabularyWord.direction == "fr_to_de") | (VocabularyWord.direction.is_(None)))
    )

    curated_rows = (
        base_query.filter(
            (func.lower(VocabularyWord.normalized_word).in_(starter_surfaces))
            | (func.lower(VocabularyWord.word).in_(starter_surfaces))
        )
        .order_by(
            VocabularyWord.frequency_rank.asc().nullslast(),
            VocabularyWord.difficulty_level.asc().nullslast(),
            func.lower(VocabularyWord.word).asc(),
        )
        .limit(max(limit * 4, 24))
        .all()
    )
    rows = list(curated_rows)
    if len(rows) < limit:
        existing_ids = {row.id for row in rows}
        fallback_query = base_query
        if existing_ids:
            fallback_query = fallback_query.filter(VocabularyWord.id.notin_(existing_ids))
        rows.extend(
            fallback_query.order_by(
                VocabularyWord.frequency_rank.asc().nullslast(),
                VocabularyWord.difficulty_level.asc().nullslast(),
                func.lower(VocabularyWord.word).asc(),
            )
            .limit(limit - len(rows))
            .all()
        )

    return [
        {
            "word_id": word.id,
            "word": word.word,
            "translations": {
                "de": word.german_translation,
                "en": word.english_translation,
                "fr": word.french_translation,
            },
            "bucket": "starter",
            "scheduler": "curated_starter",
            "priority_score": 0.8,
            "example_sentence": word.example_sentence,
            "example_translation": word.example_translation,
        }
        for word in rows[:limit]
    ]


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

    if not _has_vocabulary_history(db, user):
        for item in _starter_vocabulary_items(db, user=user, limit=limit):
            add_item(item)
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


def _session_exercise_set_ids(session: AtelierSession) -> dict[str, str]:
    quote = session.quote_payload if isinstance(session.quote_payload, dict) else {}
    raw = quote.get("exercise_set_ids") if isinstance(quote, dict) else {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if value}


def _store_session_exercise_set_id(session: AtelierSession, concept: GrammarConcept, exercise_set: AtelierExerciseSet) -> None:
    quote = dict(session.quote_payload or {})
    exercise_set_ids = dict(quote.get("exercise_set_ids") or {})
    exercise_set_ids[str(concept.id)] = str(exercise_set.id)
    quote["exercise_set_ids"] = exercise_set_ids
    session.quote_payload = quote
    flag_modified(session, "quote_payload")


def _session_has_concept_attempt(db: Session, *, session: AtelierSession, concept: GrammarConcept) -> bool:
    return (
        db.query(AtelierAttempt.id)
        .filter(
            AtelierAttempt.atelier_session_id == session.id,
            AtelierAttempt.concept_id == concept.id,
        )
        .first()
        is not None
    )


def _latest_valid_shared_llm_exercise_set(db: Session, concept: GrammarConcept) -> AtelierExerciseSet | None:
    candidates = (
        db.query(AtelierExerciseSet)
        .filter(
            AtelierExerciseSet.concept_id == concept.id,
            AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
            AtelierExerciseSet.source == "llm",
        )
        .order_by(AtelierExerciseSet.created_at.desc())
        .limit(5)
        .all()
    )
    for candidate in candidates:
        if AtelierExerciseGenerator.validate_payload(candidate.payload, concept=concept):
            return candidate
    return None


def session_exercise_set(
    db: Session,
    *,
    user: User,
    session: AtelierSession,
    concept: GrammarConcept,
    target_vocabulary: list[dict[str, Any]] | None = None,
) -> AtelierExerciseSet:
    stored_ids = _session_exercise_set_ids(session)
    stored_id = stored_ids.get(str(concept.id))
    if stored_id:
        exercise_set = db.get(AtelierExerciseSet, UUID(str(stored_id)))
        if (
            exercise_set
            and exercise_set.concept_id == concept.id
            and exercise_set.generator_version == ATELIER_GENERATOR_VERSION
            and AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)
        ):
            if exercise_set.source == "fallback" and not _session_has_concept_attempt(db, session=session, concept=concept):
                cached_llm = _latest_valid_shared_llm_exercise_set(db, concept)
                if cached_llm:
                    _store_session_exercise_set_id(session, concept, cached_llm)
                    db.add(session)
                    db.commit()
                    db.refresh(session)
                    return cached_llm
            return exercise_set

    exercise_set = AtelierExerciseGenerator(db).get_or_create(
        concept,
        user=user,
        session_id=session.id,
        target_vocabulary=target_vocabulary,
        reuse_shared_cache=False,
    )
    _store_session_exercise_set_id(session, concept, exercise_set)
    db.add(session)
    db.commit()
    db.refresh(session)
    return exercise_set


def pregenerate_next_atelier_session(user_id: UUID | str) -> None:
    if not settings.ATELIER_BACKGROUND_PREGENERATION_ENABLED:
        return
    db = SessionLocal()
    try:
        user = db.get(User, UUID(str(user_id)))
        if not user:
            return
        existing = (
            db.query(AtelierSession)
            .filter(AtelierSession.user_id == user.id, AtelierSession.status == "prepared")
            .order_by(AtelierSession.created_at.desc())
            .first()
        )
        if existing:
            return
        scheduler = AtelierScheduler(db)
        scheduler.ensure_catalog()
        selections = scheduler.select_today(user)
        if not selections:
            return
        target_vocabulary = select_atelier_vocabulary(db, user=user, limit=3)
        quote = {
            **scheduler.quote_for_today(),
            "target_vocabulary_ids": [int(item["word_id"]) for item in target_vocabulary if item.get("word_id")],
            "target_vocabulary": target_vocabulary,
            "prepared": True,
        }
        session = AtelierSession(
            user_id=user.id,
            selected_concept_ids=[selection.concept.id for selection in selections],
            quote_payload=quote,
            status="prepared",
            recap_payload={},
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        for selection in selections:
            exercise_set = AtelierExerciseGenerator(db).get_or_create(
                selection.concept,
                user=user,
                session_id=session.id,
                target_vocabulary=target_vocabulary,
                reuse_shared_cache=False,
            )
            _store_session_exercise_set_id(session, selection.concept, exercise_set)
        db.add(session)
        db.commit()
    except Exception as exc:  # pragma: no cover - background pre-generation must not affect live sessions
        logger.warning("Atelier background pre-generation failed", user_id=str(user_id), error=str(exc))
        db.rollback()
    finally:
        db.close()


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


@dataclass(frozen=True)
class ItemVerdict:
    item_id: str
    round: str
    mode: str
    passes: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "round": self.round,
            "mode": self.mode,
            "passes": self.passes,
            "reason": self.reason,
        }


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

    _llm_backoff_until: float = 0.0
    _llm_backoff_reason: str | None = None

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm_service = llm_service
        self._external_llm_service = llm_service is not None
        self._llm_unavailable = False

    def get_or_create(
        self,
        concept: GrammarConcept,
        *,
        user: User | None = None,
        session_id: UUID | str | None = None,
        target_vocabulary: list[dict[str, Any]] | None = None,
        reuse_shared_cache: bool | None = None,
    ) -> AtelierExerciseSet:
        use_shared_cache = (user is None and session_id is None) if reuse_shared_cache is None else reuse_shared_cache
        cached_shared_llm: AtelierExerciseSet | None = None
        if use_shared_cache:
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
        else:
            cached_shared_llm = (
                self.db.query(AtelierExerciseSet)
                .filter(
                    AtelierExerciseSet.concept_id == concept.id,
                    AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
                    AtelierExerciseSet.source == "llm",
                )
                .order_by(AtelierExerciseSet.created_at.desc())
                .first()
            )

        cached_fallback = (
            self.db.query(AtelierExerciseSet)
            .filter(
                AtelierExerciseSet.concept_id == concept.id,
                AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
                AtelierExerciseSet.source == "fallback",
            )
            .order_by(AtelierExerciseSet.created_at.desc())
            .first()
        )

        generated = self._generate_with_llm(
            concept,
            user=user,
            session_id=session_id,
            target_vocabulary=target_vocabulary,
        )
        if not generated:
            if cached_shared_llm and self.validate_payload(cached_shared_llm.payload, concept=concept):
                return cached_shared_llm
            if cached_fallback and self.validate_payload(cached_fallback.payload, concept=concept):
                return cached_fallback
            payload = self._fallback_payload(concept)
            validation_errors = self._payload_validation_errors(payload, concept=concept)
            if validation_errors:
                raise AtelierExerciseGenerationError(
                    f"Atelier fallback payload for {concept.external_id or concept.id} failed validation: "
                    + "; ".join(validation_errors)
                )
            model = None
            validation_notes = "Deterministic fallback after LLM exercise generation failed validation or was unavailable."
            source = "fallback"
        else:
            payload, model, validation_notes = generated
            source = "llm_user" if user or session_id else "llm"

        payload_hash = _payload_hash(payload)
        content_hash = payload_hash
        if not use_shared_cache:
            content_hash = _payload_hash(
                {
                    "payload_hash": payload_hash,
                    "user_id": str(user.id) if user else None,
                    "session_id": str(session_id) if session_id else None,
                }
            )
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
            self._record_generation_event(
                concept=concept,
                user=user,
                session_id=session_id,
                exercise_set=existing_same_hash,
                event_type="exercise_set",
                source=source,
                model=model,
                passed=True,
                payload={
                    "content_hash": content_hash,
                    "payload_hash": payload_hash,
                    "reused_existing_hash": True,
                },
            )
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
        self.db.flush([exercise_set])
        self._record_generation_event(
            concept=concept,
            user=user,
            session_id=session_id,
            exercise_set=exercise_set,
            event_type="exercise_set",
            source=source,
            model=model,
            passed=True,
            payload={"content_hash": content_hash, "payload_hash": payload_hash},
        )
        self.db.commit()
        self.db.refresh(exercise_set)
        return exercise_set

    def _record_generation_event(
        self,
        *,
        concept: GrammarConcept | None,
        user: User | None,
        session_id: UUID | str | None,
        event_type: str,
        source: str | None,
        model: str | None,
        passed: bool,
        payload: dict[str, Any],
        exercise_set: AtelierExerciseSet | None = None,
    ) -> None:
        try:
            event = AtelierGenerationEvent(
                user_id=user.id if user else None,
                concept_id=concept.id if concept else None,
                atelier_session_id=UUID(str(session_id)) if session_id else None,
                exercise_set_id=exercise_set.id if exercise_set else None,
                generator_version=ATELIER_GENERATOR_VERSION,
                event_type=event_type,
                source=source,
                model=model,
                passed=passed,
                payload=payload,
            )
            self.db.add(event)
        except Exception as exc:  # pragma: no cover - logging must never block generation
            logger.debug("Atelier generation event logging skipped", error=str(exc))

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
                continue
            errors.extend(AtelierExerciseGenerator._fill_quality_errors(item, concept=concept))
        for item in (recognize.get("word_bank") or {}).get("items") or []:
            if not (
                filled(item.get("id"))
                and filled(item.get("prompt"))
                and filled(item.get("meaning_cue"))
                and filled(item.get("correct_answer"))
                and len(item.get("tokens") or []) >= 1
                and len(item.get("answer_tokens") or []) >= 1
            ):
                errors.append(f"word_bank item {item_id(item)} is incomplete")
                continue
            tokens = item.get("tokens") if isinstance(item.get("tokens"), list) else []
            answer_tokens = item.get("answer_tokens") if isinstance(item.get("answer_tokens"), list) else []
            if _contains_blank_marker(item.get("prompt")) or any(_contains_blank_marker(token) for token in tokens):
                errors.append(f"word_bank item {item_id(item)} must not contain blanks")
            if not _multiset_subset(answer_tokens, tokens):
                errors.append(f"word_bank item {item_id(item)} answer_tokens are not available in tokens")
            joined_answer = _join_french_tokens(answer_tokens)
            if _normalize(item.get("correct_answer")) != _normalize(joined_answer):
                errors.append(f"word_bank item {item_id(item)} correct_answer must match answer_tokens")
            errors.extend(AtelierExerciseGenerator._word_bank_quality_errors(item, concept=concept))
        for item in (recognize.get("classify") or {}).get("items") or []:
            if not (
                filled(item.get("id"))
                and filled(item.get("prompt"))
                and filled(item.get("correct_label"))
                and len(item.get("labels") or []) >= 2
            ):
                errors.append(f"classify item {item_id(item)} is incomplete")
                continue
            labels = item.get("labels") if isinstance(item.get("labels"), list) else []
            if _normalize(item.get("correct_label")) not in {_normalize(label) for label in labels}:
                errors.append(f"classify item {item_id(item)} correct_label is not one of labels")
            errors.extend(AtelierExerciseGenerator._classify_quality_errors(item))
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
                continue
            for error in _directed_rewrite_instruction_errors(item):
                errors.append(f"transform item {item_id(item)} {error}")
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
        return errors

    @staticmethod
    def _fill_quality_errors(item: dict[str, Any], *, concept: GrammarConcept | None = None) -> list[str]:
        errors: list[str] = []
        item_id = str(item.get("id") or "?")
        prompt = str(item.get("prompt") or "")
        choices = item.get("choices") if isinstance(item.get("choices"), list) else []
        normalized_choices = [_normalize(choice) for choice in choices if _normalize(choice)]
        unique_choices = set(normalized_choices)
        correct = _normalize(item.get("correct_answer"))
        if not _contains_blank_marker(prompt):
            errors.append(f"fill item {item_id} must contain a visible blank")
        if len(unique_choices) < 3:
            errors.append(f"fill item {item_id} needs at least 3 distinct choices")
        if correct not in unique_choices:
            errors.append(f"fill item {item_id} correct_answer must be one of choices")
        if any(choice in {"forme cible", "autre forme", "target form", "correct form", "other form"} for choice in unique_choices):
            errors.append(f"fill item {item_id} uses generic placeholder choices")
        if concept and infer_grammar_profile(concept).key == "si_present_result_form" and len(correct) >= 4:
            if not any(_looks_like_adjacent_form(correct, choice) for choice in unique_choices if choice != correct):
                errors.append(f"fill item {item_id} needs an adjacent verb-form distractor")
        return errors

    @staticmethod
    def _word_bank_quality_errors(item: dict[str, Any], *, concept: GrammarConcept | None = None) -> list[str]:
        errors: list[str] = []
        item_id = str(item.get("id") or "?")
        tokens = item.get("tokens") if isinstance(item.get("tokens"), list) else []
        answer_tokens = item.get("answer_tokens") if isinstance(item.get("answer_tokens"), list) else []
        normalized_answer = [_normalize(token) for token in answer_tokens if _normalize(token)]
        cue = _normalize(item.get("meaning_cue"))
        joined_answer = _normalize(_join_french_tokens(answer_tokens))
        if len(normalized_answer) < 4:
            errors.append(f"word_bank item {item_id} answer must be a complete sentence")
        if cue and joined_answer and joined_answer in cue:
            errors.append(f"word_bank item {item_id} meaning_cue must not expose the French answer")
        if _has_adjacent_duplicate_tokens(answer_tokens):
            errors.append(f"word_bank item {item_id} has duplicated adjacent answer tokens")
        extras = _extra_normalized_tokens(answer_tokens, tokens)
        if not extras:
            errors.append(f"word_bank item {item_id} needs at least 1 distractor token")
        if any(extra in {"forme cible", "autre forme", "target form", "correct form", "other form"} for extra in extras):
            errors.append(f"word_bank item {item_id} uses a generic distractor token")
        if concept and infer_grammar_profile(concept).key == "si_present_result_form":
            if not AtelierExerciseGenerator._has_si_adjacent_word_bank_distractor(answer_tokens, extras):
                errors.append(f"word_bank item {item_id} needs an adjacent si verb-form distractor")
        return errors

    @staticmethod
    def _has_si_adjacent_word_bank_distractor(answer_tokens: list[Any], extras: list[str]) -> bool:
        normalized_answer = [_normalize(token) for token in answer_tokens if _normalize(token)]
        future_targets = [
            token
            for token in normalized_answer
            if re.fullmatch(r"\w+(rai|ras|ra|rons|rez|ront)", token)
        ]
        imperative_targets = [
            token
            for token in normalized_answer
            if token in {"prends", "mange", "apporte", "allez", "viens"}
        ]
        targets = future_targets or imperative_targets
        if not targets:
            return True
        return any(_looks_like_adjacent_form(target, extra) for target in targets for extra in extras)

    @staticmethod
    def _classify_quality_errors(item: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        item_id = str(item.get("id") or "?")
        prompt = _normalize(item.get("prompt"))
        labels = item.get("labels") if isinstance(item.get("labels"), list) else []
        normalized_labels = [_normalize(label) for label in labels if _normalize(label)]
        if _is_generic_classify_labels(labels):
            errors.append(f"classify item {item_id} uses generic labels")
        if len(set(normalized_labels)) < 2:
            errors.append(f"classify item {item_id} needs contrastive labels")
        if re.fullmatch(r"(target|form|item|example)\s*(form)?\s*\d*", prompt):
            errors.append(f"classify item {item_id} uses a generic prompt")
        return errors

    def _generate_with_llm(
        self,
        concept: GrammarConcept,
        *,
        user: User | None = None,
        session_id: UUID | str | None = None,
        target_vocabulary: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], str, str] | None:
        llm_service = self._get_llm_service()
        if not llm_service:
            return None
        generation_service = ExerciseGenerationService(
            self.db,
            llm_service=llm_service,
        )
        target_vocabulary = target_vocabulary if target_vocabulary is not None else (
            select_atelier_vocabulary(self.db, user=user) if user else []
        )
        validation_feedback: list[str] | None = None
        try:
            for attempt_index in range(2):
                bundle = generation_service.generate_atelier_exercise(
                    concept=concept,
                    user=user,
                    target_vocabulary=target_vocabulary,
                    validation_feedback=validation_feedback,
                )
                payload = self._normalize_llm_exercise_payload(concept, bundle.payload)
                validation_errors = self._payload_validation_errors(payload, concept=concept)
                if validation_errors:
                    self._record_generation_event(
                        concept=concept,
                        user=user,
                        session_id=session_id,
                        event_type="structural_guard",
                        source="llm",
                        model=bundle.model,
                        passed=False,
                        payload={"attempt": attempt_index + 1, "errors": validation_errors},
                    )
                    logger.warning(
                        "Atelier LLM exercise payload failed structural guard: {}",
                        validation_errors,
                        concept_id=concept.id,
                        external_id=concept.external_id,
                        attempt=attempt_index + 1,
                    )
                    validation_feedback = validation_errors
                    continue

                critique = self._downgrade_nonblocking_critique(
                    self.critique_exercise_payload(concept, payload, user=user, session_id=session_id)
                )
                failed_critique = [verdict for verdict in critique if not verdict.passes]
                if failed_critique:
                    critique_feedback = [
                        f"{verdict.round}.{verdict.mode}.{verdict.item_id}: {verdict.reason}"
                        for verdict in failed_critique
                    ]
                    self._record_generation_event(
                        concept=concept,
                        user=user,
                        session_id=session_id,
                        event_type="ai_critique",
                        source="llm",
                        model=settings.ATELIER_CRITIQUE_LLM_MODEL,
                        passed=False,
                        payload={
                            "attempt": attempt_index + 1,
                            "verdicts": [verdict.to_dict() for verdict in critique],
                        },
                    )
                    logger.warning(
                        "Atelier LLM exercise payload failed AI critique: {}",
                        critique_feedback,
                        concept_id=concept.id,
                        external_id=concept.external_id,
                        attempt=attempt_index + 1,
                    )
                    validation_feedback = critique_feedback
                    continue

                self._record_generation_event(
                    concept=concept,
                    user=user,
                    session_id=session_id,
                    event_type="ai_critique",
                    source="llm",
                    model=settings.ATELIER_CRITIQUE_LLM_MODEL if critique else None,
                    passed=True,
                    payload={
                        "attempt": attempt_index + 1,
                        "verdicts": [verdict.to_dict() for verdict in critique],
                    },
                )
                if not validation_errors:
                    return (
                        payload,
                        bundle.model,
                        bundle.validation_notes
                        + (" AI critique passed." if critique else " AI critique unavailable; structural guard passed."),
                    )
            return None
        except (ExerciseGenerationUnavailable, json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            if self._is_provider_failure(exc):
                self._mark_llm_generation_unavailable(str(exc))
            logger.warning(
                "Atelier LLM exercise generation failed",
                concept_id=concept.id,
                external_id=concept.external_id,
                error=str(exc),
            )
            return None

    def critique_exercise_payload(
        self,
        concept: GrammarConcept,
        payload: dict[str, Any],
        *,
        user: User | None = None,
        session_id: UUID | str | None = None,
    ) -> list[ItemVerdict]:
        if not settings.ATELIER_EXERCISE_CRITIQUE_ENABLED:
            return []
        llm = self._get_llm_service()
        if not llm:
            return []
        items = self._critique_items(payload)
        if not items:
            return []
        profile = infer_grammar_profile(concept)
        user_payload = {
            "target_concept": {
                "id": concept.id,
                "external_id": concept.external_id,
                "name": concept.name,
                "level": concept.level,
                "core_rule": _compact_text(concept.core_rule or concept.description, max_length=420),
                "anchor_examples": _split_list(concept.anchor_examples or concept.examples)[:4],
                "profile": profile.as_dict(),
            },
            "learner": {
                "id": str(user.id) if user else None,
                "cefr": getattr(user, "cefr_estimate", None)
                or getattr(user, "proficiency_level", None)
                or concept.level,
            },
            "items": items,
            "instructions": [
                "Judge each item independently.",
                "Fail an item if it is not solvable from its choices/chips, if the answer key is wrong, if it does not test the target concept, or if the French is unnatural/incorrect.",
                "Fail trivial items whose prompt or labels reveal the answer without testing the concept.",
                "For fill, require at least 3 distinct choices with plausible wrong forms, not placeholders.",
                "For word_bank, meaning_cue must tell the learner what sentence to build, must match the answer sentence's meaning, must not expose the French target sentence, prompt/tokens must not contain blanks, answer_tokens must form the complete target French sentence, and tokens must include at least one plausible distractor chip. Do NOT fail word_bank items for chip order, token ordering, placement clarity, or extra plausible distractors; chips are intentionally unordered.",
                "For transform items, judge ONLY the learner-facing `instruction` text (never the `expected_answer` field — that is the hidden grading key and is SUPPOSED to contain the full corrected sentence; never treat expected_answer as a spoiler). A good instruction quotes the exact source word or phrase to change (in quotes) and names the grammatical target CATEGORY in plain learner language (a tense or rule name such as 'the imparfait', 'the future', 'its negated form', 'the partitive after a negation'). Do NOT require the instruction to spell out the corrected/conjugated answer word, and do NOT fail it for omitting that word. FAIL a transform item only if the instruction itself spells out the answer word, OR if it is too vague to point at one grammatical target (e.g. coined jargon like 'être-exception contrast' or 'its contrast with negation' that a learner cannot act on).",
                "Do not rewrite items. Return pass/fail and one concise reason only.",
            ],
        }
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
                system_prompt=(
                    "You are Atelier's AI exercise critic. Return only JSON matching the schema. "
                    "Be strict about answer keys, natural French, and whether the target grammar is actually practiced."
                ),
                response_format=ATELIER_EXERCISE_CRITIQUE_RESPONSE_FORMAT,
                temperature=0.0,
                max_tokens=settings.ATELIER_CRITIQUE_LLM_MAX_TOKENS,
                model=settings.ATELIER_CRITIQUE_LLM_MODEL,
                request_timeout=settings.ATELIER_CRITIQUE_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
                reasoning_effort=settings.ATELIER_CRITIQUE_LLM_REASONING_EFFORT,
            )
            parsed = json.loads(result.content)
            verdicts: list[ItemVerdict] = []
            for raw in parsed.get("verdicts") or []:
                if not isinstance(raw, dict):
                    continue
                item_id = _compact_text(raw.get("item_id"), max_length=120)
                if not item_id:
                    continue
                verdicts.append(
                    ItemVerdict(
                        item_id=item_id,
                        round=_compact_text(raw.get("round"), max_length=40),
                        mode=_compact_text(raw.get("mode"), max_length=40),
                        passes=bool(raw.get("passes")),
                        reason=_compact_text(raw.get("reason"), max_length=240) or "No reason supplied.",
                    )
                )
            return verdicts
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning(
                "Atelier exercise critique unavailable",
                concept_id=concept.id,
                external_id=concept.external_id,
                session_id=str(session_id) if session_id else None,
                error=str(exc),
            )
            self._record_generation_event(
                concept=concept,
                user=user,
                session_id=session_id,
                event_type="ai_critique",
                source="llm",
                model=settings.ATELIER_CRITIQUE_LLM_MODEL,
                passed=True,
                payload={"unavailable": True, "error": str(exc)},
            )
            return []

    @staticmethod
    def _downgrade_nonblocking_critique(verdicts: list[ItemVerdict]) -> list[ItemVerdict]:
        adjusted: list[ItemVerdict] = []
        for verdict in verdicts:
            if verdict.passes or not AtelierExerciseGenerator._is_nonblocking_word_bank_critique(verdict):
                adjusted.append(verdict)
                continue
            adjusted.append(
                ItemVerdict(
                    item_id=verdict.item_id,
                    round=verdict.round,
                    mode=verdict.mode,
                    passes=True,
                    reason=f"Advisory only; structural guard passed. {verdict.reason}",
                )
            )
        return adjusted

    @staticmethod
    def _is_nonblocking_word_bank_critique(verdict: ItemVerdict) -> bool:
        if verdict.round != "recognize" or verdict.mode != "word_bank":
            return False
        reason = _normalize(verdict.reason)
        hard_markers = (
            "answer key",
            "wrong answer",
            "correct answer is wrong",
            "answer tokens do not form",
            "answer tokens dont form",
            "cannot build",
            "not solvable",
            "not available in tokens",
            "missing correct token",
            "omits correct token",
            "meaning cue",
            "expose",
            "blank",
            "unnatural",
            "incorrect french",
            "does not practice",
            "doesn't practice",
            "doesnt practice",
            "not test the target",
            "not testing the target",
            "target concept",
        )
        if any(marker in reason for marker in hard_markers):
            return False
        soft_markers = (
            "placement clarity",
            "chip order",
            "token order",
            "tokens order",
            "ordering",
            "extra distractor",
            "too many distractors",
            "distractors are allowed",
            "tokens include",
        )
        return any(marker in reason for marker in soft_markers)

    @staticmethod
    def _critique_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        recognize = payload.get("recognize") if isinstance(payload.get("recognize"), dict) else {}
        for mode in ("fill", "classify", "word_bank"):
            for raw_item in ((recognize.get(mode) or {}).get("items") or []):
                if not isinstance(raw_item, dict):
                    continue
                item = {
                    "round": "recognize",
                    "mode": mode,
                    "id": raw_item.get("id"),
                    "prompt": raw_item.get("prompt"),
                    "correct_answer": raw_item.get("correct_answer"),
                }
                for key in ("choices", "meaning_cue", "tokens", "answer_tokens", "labels", "correct_label"):
                    if raw_item.get(key) is not None:
                        item[key] = raw_item.get(key)
                items.append(item)
        for raw_item in ((payload.get("transform") or {}).get("items") or []):
            if isinstance(raw_item, dict):
                items.append(
                    {
                        "round": "transform",
                        "mode": "transform",
                        "id": raw_item.get("id"),
                        "type": raw_item.get("type"),
                        "instruction": raw_item.get("instruction"),
                        "source": raw_item.get("source"),
                        "expected_answer": raw_item.get("expected_answer"),
                    }
                )
        produce = payload.get("produce") if isinstance(payload.get("produce"), dict) else {}
        if produce:
            items.append(
                {
                    "round": "produce",
                    "mode": "produce",
                    "id": "produce",
                    "source_fragment": produce.get("source_fragment"),
                    "prompt": produce.get("prompt"),
                    "requirements": produce.get("requirements"),
                }
            )
        ladder = payload.get("output_ladder") if isinstance(payload.get("output_ladder"), dict) else {}
        for round_name in ("sentence", "speak", "conversation"):
            for raw_item in ((ladder.get(round_name) or {}).get("items") or []):
                if isinstance(raw_item, dict):
                    items.append(
                        {
                            "round": round_name,
                            "mode": round_name,
                            "id": raw_item.get("id"),
                            "type": raw_item.get("type"),
                            "instruction": raw_item.get("instruction"),
                            "prompt": raw_item.get("prompt"),
                            "example_answer": raw_item.get("example_answer"),
                            "requirements": raw_item.get("requirements"),
                        }
                    )
        return items

    def _fallback_payload(self, concept: GrammarConcept) -> dict[str, Any]:
        profile = infer_grammar_profile(concept)
        sentences = self._fallback_sentences(concept)
        prefix = re.sub(r"[^a-z0-9]+", "-", _normalize(concept.external_id or concept.id)).strip("-") or "atelier"
        payload = self._base(concept, sentence=sentences[0], marks=[])
        payload.update(
            {
                "recognize": {
                    "fill": {"items": self._fallback_fill_items(concept, prefix=prefix)},
                    "word_bank": {"items": self._fallback_word_bank_items(concept, sentences, prefix=prefix)},
                    "classify": {"items": self._fallback_classify_items(concept, prefix=prefix)},
                },
                "transform": {"items": self._fallback_transform_items(concept, sentences, prefix=prefix)},
                "produce": {
                    "source_fragment": sentences[0],
                    "prompt": f"Write a short French note that uses {profile.label.lower()} clearly.",
                    "requirements": [
                        {
                            "concept_id": concept.id,
                            "external_id": concept.external_id,
                            "label": concept.name,
                            "target_count": _produce_target_count(self.db, concept),
                        }
                    ],
                    "min_words": 40,
                    "max_words": 110,
                },
                "output_ladder": {
                    "sentence": {
                        "items": [
                            self._fallback_output_item(
                                concept,
                                prefix=prefix,
                                round_name="sentence",
                                kind="short_sentence",
                                prompt="Write one sentence using the target grammar.",
                                example=sentences[0],
                                min_words=5,
                                max_words=24,
                            )
                        ]
                    },
                    "speak": {
                        "items": [
                            self._fallback_output_item(
                                concept,
                                prefix=prefix,
                                round_name="speak",
                                kind="spoken_response",
                                prompt="Say one natural response using the target grammar.",
                                example=sentences[1],
                                min_words=5,
                                max_words=24,
                            )
                        ]
                    },
                    "conversation": {
                        "items": [
                            self._fallback_output_item(
                                concept,
                                prefix=prefix,
                                round_name="conversation",
                                kind="conversation_turn",
                                prompt="Answer in one conversational turn using the target grammar.",
                                example=sentences[2],
                                min_words=6,
                                max_words=30,
                            )
                        ]
                    },
                },
            }
        )
        return payload

    def _fallback_sentences(self, concept: GrammarConcept) -> list[str]:
        profile = infer_grammar_profile(concept)
        default_candidates = {
            "si_present_result_form": [
                "Si tu viens demain, nous partirons tôt.",
                "S'il pleut, prends ton manteau.",
                "Si elle appelle, je répondrai tout de suite.",
            ],
            "article_after_negation": [
                "Je ne bois pas de café.",
                "Elle n'a pas d'idée.",
                "Nous n'avons pas de dossier aujourd'hui.",
            ],
            "tense_aspect": [
                "Je marchais quand une voiture est passée.",
                "Il faisait froid, puis nous sommes entrés.",
                "Elle attendait quand j'ai répondu.",
            ],
            "conditional_mood": [
                "Je voudrais partir demain.",
                "Nous pourrions venir plus tôt.",
                "Elle aimerait parler avec vous.",
            ],
            "mood": [
                "Il faut que tu sois prêt.",
                "Je veux qu'elle vienne demain.",
                "Bien qu'il soit tard, nous continuons.",
            ],
            "relative_pronoun": [
                "C'est le livre que j'ai lu.",
                "Voici l'ami qui arrive.",
                "La ville où j'habite est calme.",
            ],
            "pronoun_choice": [
                "Je le vois demain.",
                "Nous lui parlons ce soir.",
                "Elle en prend deux.",
            ],
            "determiner": [
                "Je prends un café.",
                "Elle cherche la gare.",
                "Nous avons des billets.",
            ],
            "agreement": [
                "Les maisons sont grandes.",
                "Cette robe bleue est jolie.",
                "Ils sont arrivés hier.",
            ],
            "preposition": [
                "Je vais chez Marie.",
                "Nous parlons de ce projet.",
                "Il habite dans cette rue.",
            ],
            "comparison": [
                "Elle est plus rapide que moi.",
                "Ce café est moins cher.",
                "Il travaille aussi bien que toi.",
            ],
        }.get(
            profile.key,
            [
                "Je pratique cette règle dans une phrase claire.",
                "Nous utilisons ce point de grammaire aujourd'hui.",
                "Elle choisit la forme correcte dans le contexte.",
            ],
        )
        raw_examples = _split_list(concept.anchor_examples) + _split_list(getattr(concept, "examples", None))
        examples = []
        for example in raw_examples:
            cleaned = re.split(r"\s*->\s*", example)[-1].strip()
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if cleaned:
                examples.append(cleaned)

        candidates = [*default_candidates, *examples]
        accepted: list[str] = []
        seen: set[str] = set()
        for sentence in candidates:
            if _normalize(sentence) in seen:
                continue
            if count_concept_hits(concept, sentence, task_text=concept.core_rule or concept.name or "") <= 0:
                continue
            accepted.append(sentence)
            seen.add(_normalize(sentence))
            if len(accepted) >= 3:
                break
        if not accepted:
            accepted = default_candidates[:1]
        while len(accepted) < 3:
            accepted.append(accepted[len(accepted) % len(accepted)])
        return accepted[:3]

    def _fallback_word_bank_items(self, concept: GrammarConcept, sentences: list[str], *, prefix: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for index, sentence in enumerate(sentences[:3], start=1):
            answer_tokens = _tokenize_french_sentence(sentence)
            item_id = f"{prefix}-fallback-bank-{index}"
            distractors = self._word_bank_distractors(concept, answer_tokens)
            tokens = _stable_scramble([*answer_tokens, *distractors], item_id)
            items.append(
                {
                    "id": item_id,
                    "prompt": "Build the full French sentence.",
                    "meaning_cue": _word_bank_meaning_cue(concept, sentence),
                    "tokens": tokens,
                    "answer_tokens": answer_tokens,
                    "correct_answer": _join_french_tokens(answer_tokens),
                }
            )
        return items

    def _word_bank_distractors(self, concept: GrammarConcept, answer_tokens: list[Any]) -> list[str]:
        profile = infer_grammar_profile(concept)
        normalized_answer = {_normalize(token) for token in answer_tokens if _normalize(token)}
        distractors: list[str] = []

        def add(token: str) -> None:
            normalized = _normalize(token)
            if not normalized or normalized in normalized_answer:
                return
            if normalized in {_normalize(existing) for existing in distractors}:
                return
            distractors.append(token)

        if profile.key == "si_present_result_form":
            try:
                comma_index = [str(token) for token in answer_tokens].index(",")
                result_tokens = answer_tokens[comma_index + 1 :]
            except ValueError:
                result_tokens = answer_tokens
            for token in result_tokens:
                for distractor in self._si_verb_distractors(str(token)):
                    add(distractor)
                    if distractors:
                        return distractors[:2]
            add("conditionnel")
        elif profile.key == "article_after_negation":
            if "de" in normalized_answer:
                add("du")
            if any(token.startswith("d'") for token in normalized_answer):
                add("une")
            add("des")
        elif profile.key == "tense_aspect":
            for token in answer_tokens:
                normalized = _normalize(token)
                if normalized.endswith("ais"):
                    add(normalized[:-3] + "erai")
                    break
                if normalized.endswith("ait"):
                    add(normalized[:-3] + "era")
                    break
            add("soudain")
        else:
            for token in answer_tokens:
                normalized = _normalize(token)
                if len(normalized) >= 5:
                    add(f"{token}s")
                    break
            add("autrement")
        return distractors[:2] or ["autrement"]

    @staticmethod
    def _si_verb_distractors(token: str) -> list[str]:
        normalized = _normalize(token)
        if not normalized:
            return []
        irregular = {
            "prends": ["prendras", "prendrais"],
            "mange": ["mangeras", "mangerais"],
            "apporte": ["apporteras", "apporterais"],
            "allez": ["irez", "iriez"],
            "viens": ["viendras", "viendrais"],
            "repondrai": ["répondrais", "réponds"],
            "répondrai": ["répondrais", "réponds"],
        }
        if normalized in irregular:
            return irregular[normalized]
        if normalized.endswith("rai"):
            return [f"{token}s"]
        if normalized.endswith("ras"):
            return [f"{token[:-3]}rais"]
        if normalized.endswith("ra"):
            return [f"{token[:-2]}rait"]
        if normalized.endswith("rons"):
            if normalized.endswith("erons") or normalized.endswith("irons"):
                return [f"{token[:-5]}ons", f"{token[:-1]}ions"]
            return [f"{token[:-4]}ions"]
        if normalized.endswith("rez"):
            return [f"{token[:-3]}riez"]
        if normalized.endswith("ront"):
            return [f"{token[:-4]}raient"]
        return []

    def _fallback_fill_items(self, concept: GrammarConcept, *, prefix: str) -> list[dict[str, Any]]:
        profile = infer_grammar_profile(concept)
        if profile.key == "article_after_negation":
            return [
                {"id": f"{prefix}-fallback-fill-1", "prompt": "Je ne bois pas ____ café.", "choices": ["de", "du", "un"], "correct_answer": "de"},
                {"id": f"{prefix}-fallback-fill-2", "prompt": "Elle n'a pas ____ idée.", "choices": ["d'", "une", "de la"], "correct_answer": "d'"},
                {"id": f"{prefix}-fallback-fill-3", "prompt": "Nous n'avons pas ____ dossier.", "choices": ["de", "du", "le"], "correct_answer": "de"},
            ]
        if profile.key == "tense_aspect":
            return [
                {"id": f"{prefix}-fallback-fill-1", "prompt": "Je ____ quand elle est arrivée.", "choices": ["marchais", "ai marché", "marcherai"], "correct_answer": "marchais"},
                {"id": f"{prefix}-fallback-fill-2", "prompt": "Soudain, il ____ la porte.", "choices": ["ouvrait", "a ouvert", "ouvrira"], "correct_answer": "a ouvert"},
                {"id": f"{prefix}-fallback-fill-3", "prompt": "Tous les dimanches, nous ____ au marché.", "choices": ["allions", "sommes allés", "irons"], "correct_answer": "allions"},
            ]
        if profile.key == "si_present_result_form":
            return [
                {"id": f"{prefix}-fallback-fill-1", "prompt": "Si je finis tôt, je t'_____.", "choices": ["appellerai", "appelle", "appellerais"], "correct_answer": "appellerai"},
                {"id": f"{prefix}-fallback-fill-2", "prompt": "S'il pleut demain, ____ ton manteau.", "choices": ["prends", "prendras", "prenais"], "correct_answer": "prends"},
                {"id": f"{prefix}-fallback-fill-3", "prompt": "Si nous partons maintenant, nous ____ tôt.", "choices": ["arriverons", "arrivons", "arriverions"], "correct_answer": "arriverons"},
            ]
        items: list[dict[str, Any]] = []
        sentences = self._fallback_sentences(concept)
        for index, sentence in enumerate(sentences[:3], start=1):
            tokens = _tokenize_french_sentence(sentence)
            answer = next(
                (
                    token
                    for token in tokens
                    if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?", token)
                    and len(_normalize(token)) >= 4
                ),
                tokens[0] if tokens else profile.label,
            )
            prompt = re.sub(re.escape(answer), "____", sentence, count=1)
            distractor = f"{answer}s" if not str(answer).endswith("s") else str(answer).rstrip("s")
            items.append(
                {
                    "id": f"{prefix}-fallback-fill-{index}",
                    "prompt": prompt,
                    "choices": [str(answer), distractor, "autrement"],
                    "correct_answer": str(answer),
                }
            )
        return items

    def _fallback_classify_items(self, concept: GrammarConcept, *, prefix: str) -> list[dict[str, Any]]:
        profile = infer_grammar_profile(concept)
        if profile.key == "article_after_negation":
            labels = ["article changes", "être exception"]
            return [
                {"id": f"{prefix}-fallback-classify-1", "prompt": "pas de café", "labels": labels, "correct_label": "article changes", "correct_answer": "article changes"},
                {"id": f"{prefix}-fallback-classify-2", "prompt": "Ce n'est pas du café", "labels": labels, "correct_label": "être exception", "correct_answer": "être exception"},
                {"id": f"{prefix}-fallback-classify-3", "prompt": "pas d'idée", "labels": labels, "correct_label": "article changes", "correct_answer": "article changes"},
            ]
        if profile.key == "tense_aspect":
            return [
                {"id": f"{prefix}-fallback-classify-1", "prompt": "marchais", "labels": ["background/habit", "bounded event"], "correct_label": "background/habit", "correct_answer": "background/habit"},
                {"id": f"{prefix}-fallback-classify-2", "prompt": "a ouvert", "labels": ["background/habit", "bounded event"], "correct_label": "bounded event", "correct_answer": "bounded event"},
                {"id": f"{prefix}-fallback-classify-3", "prompt": "allions", "labels": ["background/habit", "bounded event"], "correct_label": "background/habit", "correct_answer": "background/habit"},
            ]
        if profile.key == "si_present_result_form":
            labels = ["present condition", "future result", "imperative result"]
            return [
                {"id": f"{prefix}-fallback-classify-1", "prompt": "si tu viens", "labels": labels, "correct_label": "present condition", "correct_answer": "present condition"},
                {"id": f"{prefix}-fallback-classify-2", "prompt": "je répondrai", "labels": labels, "correct_label": "future result", "correct_answer": "future result"},
                {"id": f"{prefix}-fallback-classify-3", "prompt": "prends ton manteau", "labels": labels, "correct_label": "imperative result", "correct_answer": "imperative result"},
            ]
        labels = [profile.label, "different grammar role"]
        sentences = self._fallback_sentences(concept)
        return [
            {
                "id": f"{prefix}-fallback-classify-{index}",
                "prompt": sentence,
                "labels": labels,
                "correct_label": profile.label,
                "correct_answer": profile.label,
            }
            for index, sentence in enumerate(sentences[:3], start=1)
        ]

    def _fallback_transform_items(
        self,
        concept: GrammarConcept,
        sentences: list[str],
        *,
        prefix: str,
    ) -> list[dict[str, Any]]:
        profile = infer_grammar_profile(concept)
        if profile.key == "article_after_negation":
            return [
                {"id": f"{prefix}-fallback-transform-1", "type": "directed_rewrite", "instruction": "Negate the quantity; change 'du' to 'de' after pas.", "source": "Je bois du café.", "expected_answer": "Je ne bois pas de café."},
                {"id": f"{prefix}-fallback-transform-2", "type": "contrast_rewrite", "instruction": "Use the être exception; keep 'du' after n'est pas.", "source": "C'est du café.", "expected_answer": "Ce n'est pas du café."},
                {"id": f"{prefix}-fallback-transform-3", "type": "repair_rewrite", "instruction": "Repair the article; change 'une' to d' after pas.", "source": "Elle n'a pas une idée.", "expected_answer": "Elle n'a pas d'idée."},
            ]
        if profile.key == "tense_aspect":
            return [
                {"id": f"{prefix}-fallback-transform-1", "type": "directed_rewrite", "instruction": "Change 'pleut' to background imparfait and 'sors' to passé composé.", "source": "Il pleut quand je sors.", "expected_answer": "Il pleuvait quand je suis sorti."},
                {"id": f"{prefix}-fallback-transform-2", "type": "contrast_rewrite", "instruction": "Change the habit 'lisais' into one completed event.", "source": "Je lisais souvent ce livre.", "expected_answer": "J'ai lu ce livre hier."},
                {"id": f"{prefix}-fallback-transform-3", "type": "repair_rewrite", "instruction": "Repair the contrast by making 'être' background and 'sonner' a completed event.", "source": "Je suis fatigué quand le téléphone sonnait.", "expected_answer": "J'étais fatigué quand le téléphone a sonné."},
            ]
        if profile.key == "si_present_result_form":
            return [
                {"id": f"{prefix}-fallback-transform-1", "type": "directed_rewrite", "instruction": "Change 'quand il arrivera' to a si-clause with present 'arrive'.", "source": "Quand il arrivera, on commencera.", "expected_answer": "S'il arrive, on commencera."},
                {"id": f"{prefix}-fallback-transform-2", "type": "contrast_rewrite", "instruction": "Change 'avais' to present 'as' and 'viendrais' to future 'viendras'.", "source": "Si tu avais le temps, tu viendrais.", "expected_answer": "Si tu as le temps, tu viendras."},
                {"id": f"{prefix}-fallback-transform-3", "type": "repair_rewrite", "instruction": "Repair 'viendras' after si; use present 'viens'.", "source": "Si tu viendras demain, apporte le livre.", "expected_answer": "Si tu viens demain, apporte le livre."},
            ]
        return [
            {
                "id": f"{prefix}-fallback-transform-{index}",
                "type": kind,
                "instruction": f"Rewrite the sentence so the exact target form shows {profile.label.lower()}.",
                "source": sentence,
                "expected_answer": sentence,
            }
            for index, (kind, sentence) in enumerate(
                zip(
                    ["directed_rewrite", "contrast_rewrite", "repair_rewrite"],
                    sentences,
                    strict=False,
                ),
                start=1,
            )
        ]

    def _fallback_output_item(
        self,
        concept: GrammarConcept,
        *,
        prefix: str,
        round_name: str,
        kind: str,
        prompt: str,
        example: str,
        min_words: int,
        max_words: int,
    ) -> dict[str, Any]:
        return {
            "id": f"{prefix}-fallback-{round_name}",
            "type": kind,
            "instruction": "Use the target grammar visibly in your answer.",
            "prompt": prompt,
            "example_answer": example,
            "requirements": [
                {
                    "concept_id": concept.id,
                    "external_id": concept.external_id,
                    "label": concept.name,
                    "target_count": 1,
                }
            ],
            "min_words": min_words,
            "max_words": max_words,
        }

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
            if not str(item.get("correct_answer") or "").strip():
                item["correct_answer"] = _join_french_tokens(item["answer_tokens"])
            if not str(item.get("meaning_cue") or "").strip():
                item["meaning_cue"] = _word_bank_meaning_cue(concept, item.get("correct_answer") or item["answer_tokens"])
            # Always build the chips from the answer tokens (+ distractors) so the answer is
            # guaranteed buildable from the offered chips — the LLM's own token list is unreliable.
            chips = [str(token) for token in item["answer_tokens"]]
            for distractor in self._word_bank_distractors(concept, item["answer_tokens"]):
                if _normalize(distractor) not in {_normalize(token) for token in chips}:
                    chips.append(str(distractor))
            item["tokens"] = _stable_scramble(chips, item_id)
        for item in (((payload.get("recognize") or {}).get("fill") or {}).get("items") or []):
            # Guarantee the correct answer is always one of the choices.
            choices = [str(choice) for choice in (item.get("choices") or [])]
            answer = str(item.get("correct_answer") or "").strip()
            if answer and _normalize(answer) not in {_normalize(choice) for choice in choices}:
                choices = [answer, *choices]
            item["choices"] = choices
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
        backoff_remaining = self._llm_backoff_remaining_seconds()
        if backoff_remaining > 0:
            logger.info(
                "Atelier LLM generation skipped during provider backoff",
                remaining_seconds=round(backoff_remaining, 1),
                reason=self.__class__._llm_backoff_reason,
            )
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

    @classmethod
    def _llm_backoff_remaining_seconds(cls) -> float:
        return max(0.0, cls._llm_backoff_until - time.monotonic())

    def _mark_llm_generation_unavailable(self, reason: str) -> None:
        if self._external_llm_service:
            return
        backoff_seconds = max(0.0, float(settings.ATELIER_LLM_FAILURE_BACKOFF_SECONDS or 0.0))
        if backoff_seconds <= 0:
            return
        self.__class__._llm_backoff_until = time.monotonic() + backoff_seconds
        self.__class__._llm_backoff_reason = _compact_text(reason, max_length=240)

    @staticmethod
    def _is_provider_failure(exc: BaseException) -> bool:
        if isinstance(exc, LLMProviderError):
            return True
        cause = getattr(exc, "__cause__", None)
        return isinstance(cause, LLMProviderError)

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
        prompt_payload = self._prompt_payload(concept, round_name, mode, exercise_id, user=user, session=session)
        target_vocabulary = session_vocabulary_context(session)
        if target_vocabulary:
            prompt_payload = inject_vocabulary_context(prompt_payload, target_vocabulary)
        correction = self.correct(
            concept=concept,
            round_name=round_name,
            mode=mode,
            exercise_id=exercise_id,
            prompt_payload=prompt_payload,
            answer_payload=answer_payload,
            session=session,
        )
        rule_reference = self._rule_reference(
            concept=concept,
            prompt_payload=prompt_payload,
            round_name=round_name,
            mode=mode,
        )
        if rule_reference:
            correction = {
                **correction,
                "rule_reference": rule_reference,
            }
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
            "ai_review": self._initial_ai_review(
                round_name=round_name,
                answer_payload=answer_payload,
                correction=correction,
            ),
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
            return self._correct_recognize_ai_first(concept, mode, prompt_payload, answer_payload)
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

    def _initial_ai_review(
        self,
        *,
        round_name: str,
        answer_payload: dict[str, Any],
        correction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Every round is now corrected AI-first synchronously in correct(); the
        # AI verdict is already baked into `correction` by the time we get here.
        # We no longer expose a manual "AI correction" trigger or surface an
        # "AI unavailable" state: when the live model succeeds we mark the review
        # complete, and when it quietly falls back to the deterministic engine we
        # simply treat the AI review as not applicable rather than nagging the
        # learner with a button or an error line.
        correction_debug = (correction or {}).get("correction_debug") or {}
        if correction_debug and not correction_debug.get("fallback_used"):
            return {
                "status": "complete",
                "auto_started": False,
                "model": correction_debug.get("model") or settings.ATELIER_CORRECTION_LLM_MODEL,
                "completed_at": self._now_iso(),
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
            return self._correct_recognize_ai_first(concept, mode, prompt_payload, answer_payload)
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
        session: AtelierSession | None = None,
    ) -> dict[str, Any]:
        if not concept:
            return {"id": exercise_id, "round": round_name, "mode": mode}
        if user and session:
            payload = session_exercise_set(
                self.db,
                user=user,
                session=session,
                concept=concept,
                target_vocabulary=session_vocabulary_context(session),
            ).payload
        else:
            payload = self.generator.get_or_create(concept, user=user).payload
        base_payload = {
            "round": round_name,
            "mode": mode,
            "rule_panel": payload.get("rule_panel") or {},
        }
        if round_name == "recognize":
            return {**base_payload, **payload["recognize"][mode]}
        if round_name == "transform":
            return {**base_payload, **payload["transform"]}
        if round_name in {"sentence", "speak", "conversation"}:
            ladder = (payload.get("output_ladder") or {}).get(round_name) or {}
            return {**base_payload, **ladder}
        if round_name == "produce":
            return {**base_payload, **payload["produce"]}
        return {"id": exercise_id, "round": round_name, "mode": mode}

    def _rule_reference(
        self,
        *,
        concept: GrammarConcept | None,
        prompt_payload: dict[str, Any],
        round_name: str,
        mode: str,
    ) -> str:
        rule_panel = prompt_payload.get("rule_panel") if isinstance(prompt_payload, dict) else {}
        if not isinstance(rule_panel, dict):
            rule_panel = {}
        if mode == "classify":
            candidate = rule_panel.get("check") or rule_panel.get("pattern")
        elif round_name in {"fill", "recognize", "transform"}:
            candidate = rule_panel.get("pattern") or rule_panel.get("check")
        else:
            candidate = rule_panel.get("check") or rule_panel.get("pattern") or rule_panel.get("rule")
        if candidate:
            return _compact_text(candidate, max_length=220)
        if concept:
            profile = infer_grammar_profile(concept)
            return _compact_text(profile.check if mode == "classify" else profile.pattern, max_length=220)
        return ""

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
                errata.extend(self._word_bank_errata(concept, item, learner_text, str(target or "")))
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

    def _correct_recognize_ai_first(
        self,
        concept: GrammarConcept | None,
        mode: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._correct_recognize(concept, mode, prompt_payload, answer_payload)
        if not self._should_use_correction_llm() or not concept:
            return fallback
        return self._correct_recognize_with_llm(concept, mode, prompt_payload, answer_payload, fallback) or fallback

    def _correct_recognize_with_llm(
        self,
        concept: GrammarConcept,
        mode: str,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any] | None:
        llm = self._get_llm_service()
        if not llm:
            return None
        system_prompt = self._correction_system_prompt()
        user_payload = {
            "round": "recognize",
            "mode": mode,
            "concept": self._compact_llm_concept(concept),
            "task": self._compact_llm_task(prompt_payload),
            "answer": self._compact_llm_answer(answer_payload),
            "deterministic_assessment": self._compact_llm_assessment(fallback),
            "instructions": [
                "Review each recognition item against the answer key and the target concept.",
                "For word_bank, judge the built chip sentence as a French sentence and explain the exact wrong form or order.",
                "For fill, name the submitted blank value and the target form.",
                "For classify, explain the grammatical contrast between the chosen label and the correct label.",
                "Address feedback directly with 'you'; never say 'the learner' or 'the user'.",
                "Do not use template phrasing like 'Rebuild the sentence as'; give a contextual micro-correction.",
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
            "item_id": item.get("id"),
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

    def _word_bank_errata(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner_text: str,
        target: str,
    ) -> list[dict[str, Any]]:
        learner_norm = _normalize(learner_text)
        target_norm = _normalize(target)
        label = "Word bank"
        why = "The built sentence does not match the target sentence."
        repair = f"Rebuild the sentence as: {target}"
        task_type = self._task_type_for(concept, item)
        profile_key = infer_grammar_profile(concept).key if concept else ""

        if profile_key == "si_present_result_form":
            issues: list[dict[str, Any]] = []
            grammar_focus_tokens: set[str] = set()
            if "repondrais" in learner_norm and "repondrai" in target_norm:
                grammar_focus_tokens.add("repondrai")
                issues.append(
                    self._word_bank_erratum_payload(
                        concept,
                        item,
                        "Conditional vs future",
                        learner_text,
                        target,
                        "You built the right si-frame, but the result verb is `répondrais`, which is conditional. In a real condition with si + present, the consequence uses future simple: `répondrai`.",
                        "Keep `Si elle appelle` in the present, then change only the result verb to future simple: `je répondrai`.",
                        "future_result",
                    )
                )
            swapped_si_future = (
                re.search(r"\bsi\s+nous\s+arriverons\b", learner_norm)
                and re.search(r"\bnous\s+partons\b", learner_norm)
                and "si nous partons" in target_norm
                and "nous arriverons" in target_norm
            )
            if swapped_si_future:
                grammar_focus_tokens.update({"partons", "arriverons"})
                issues.append(
                    self._word_bank_erratum_payload(
                        concept,
                        item,
                        "Future placed after si",
                        learner_text,
                        target,
                        "You put future `arriverons` inside the si-clause and present `partons` in the result. In si type 1, the condition stays present: `Si nous partons maintenant`; the consequence carries the future: `nous arriverons tôt`.",
                        "Put the present action after `si`, then put the future action after the comma: `Si nous partons maintenant, nous arriverons tôt`.",
                        "si_clause_frame",
                    )
                )
            has_specific_result_issue = False
            learner_result_token, target_result_token = self._si_result_clause_future_pair(learner_text, target)
            if learner_result_token and target_result_token and learner_result_token != target_result_token:
                has_specific_result_issue = True
                grammar_focus_tokens.add(_normalize(target_result_token))
                issues.append(
                    self._word_bank_erratum_payload(
                        concept,
                        item,
                        "Future result",
                        learner_text,
                        target,
                        f"The result clause uses `{learner_result_token}`, but si type 1 needs future simple `{target_result_token}` here.",
                        "Keep the si-clause in the present, then put the consequence in future simple.",
                        "future_result",
                    )
                )
            if not has_specific_result_issue and re.search(r"\bsi\b", learner_norm) and not re.search(
                r"\b\w+(rai|ras|ra|rons|rez|ront)\b|\b(prends|mange|apporte|allez|viens)\b",
                learner_norm,
            ):
                grammar_focus_tokens.update(self._si_result_clause_focus_tokens(target))
                issues.append(
                    self._word_bank_erratum_payload(
                        concept,
                        item,
                        "Future result",
                        learner_text,
                        target,
                        "The si-clause is present, but the result clause does not carry the future or imperative form that this pattern needs.",
                        "Use present after `si`, then put the consequence in future simple or imperative.",
                        "future_result",
                    )
                )
            issues.extend(
                self._word_bank_spelling_errata(
                    concept,
                    item,
                    learner_text,
                    target,
                    excluded_target_tokens=grammar_focus_tokens,
                )
            )
            if issues:
                unique_issues: list[dict[str, Any]] = []
                seen_signatures: set[tuple[str, str, str]] = set()
                for issue in issues:
                    signature = (
                        str(issue.get("display_label") or ""),
                        str(issue.get("task_error_type") or ""),
                        str(issue.get("why_wrong") or ""),
                    )
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)
                    unique_issues.append(issue)
                return unique_issues
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

        return [self._word_bank_erratum_payload(concept, item, label, learner_text, target, why, repair, task_type)]

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
            "item_id": item.get("id"),
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

    def _si_result_clause_future_pair(self, learner_text: str, target: str) -> tuple[str | None, str | None]:
        target_tokens = _tokenize_french_sentence(target)
        learner_tokens = _tokenize_french_sentence(learner_text)
        target_result_tokens = self._si_result_clause_alpha_tokens(target_tokens)
        learner_result_tokens = self._si_result_clause_alpha_tokens(learner_tokens)
        for index, target_token in enumerate(target_result_tokens):
            target_norm = _normalize(target_token)
            if not re.fullmatch(r"\w+(rai|ras|ra|rons|rez|ront)", target_norm):
                continue
            learner_token = learner_result_tokens[index] if index < len(learner_result_tokens) else ""
            learner_norm = _normalize(learner_token)
            if learner_norm and learner_norm != target_norm:
                return learner_token, target_token
        return None, None

    def _si_result_clause_focus_tokens(self, target: str) -> set[str]:
        target_tokens = _tokenize_french_sentence(target)
        focus: set[str] = set()
        for token in self._si_result_clause_alpha_tokens(target_tokens):
            token_norm = _normalize(token)
            if re.fullmatch(r"\w+(rai|ras|ra|rons|rez|ront)", token_norm):
                focus.add(token_norm)
        return focus

    def _si_result_clause_alpha_tokens(self, tokens: list[str]) -> list[str]:
        try:
            comma_index = tokens.index(",")
            clause_tokens = tokens[comma_index + 1 :]
        except ValueError:
            clause_tokens = tokens
        return [token for token in clause_tokens if re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿ]+)?", token)]

    def _word_bank_spelling_errata(
        self,
        concept: GrammarConcept | None,
        item: dict[str, Any],
        learner_text: str,
        target: str,
        *,
        excluded_target_tokens: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        learner_tokens = _tokenize_french_sentence(learner_text)
        target_tokens = _tokenize_french_sentence(target)
        excluded = {token for token in (excluded_target_tokens or set()) if token}
        issues: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()

        for learner_token, target_token in zip(learner_tokens, target_tokens, strict=False):
            learner_norm = _normalize(learner_token)
            target_norm = _normalize(target_token)
            if not learner_norm or not target_norm or learner_norm == target_norm:
                continue
            if target_norm in excluded:
                continue
            if not learner_norm.isalpha() or not target_norm.isalpha():
                continue
            if len(learner_norm) < 4 or len(target_norm) < 4:
                continue
            if _bounded_edit_distance(learner_norm, target_norm, limit=1) != 1:
                continue
            pair = (learner_norm, target_norm)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            issues.append(
                self._word_bank_erratum_payload(
                    concept,
                    item,
                    "Spelling slip",
                    learner_text,
                    target,
                    f"You wrote `{learner_token}`, but the target word here is `{target_token}`.",
                    f"Keep the sentence frame, then fix the spelling of `{target_token}`.",
                    "orthography",
                )
            )
        return issues

    def _correct_transform(
        self,
        concept: GrammarConcept | None,
        prompt_payload: dict[str, Any],
        answer_payload: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._correct_transform_rule_based(concept, prompt_payload, answer_payload)
        if not self._should_use_correction_llm():
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
        rule_panel = prompt_payload.get("rule_panel")
        if isinstance(rule_panel, dict):
            compact["rule_panel"] = {
                key: _compact_text(rule_panel.get(key), max_length=240)
                for key in ("rule", "pattern", "check")
                if rule_panel.get(key)
            }
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
                        "item_id",
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

        fallback_errata = [
            erratum
            for erratum in (fallback.get("errata") or [])
            if isinstance(erratum, dict)
        ]

        def fallback_item_id_for(parsed_erratum: dict[str, Any]) -> str:
            item_id = str(parsed_erratum.get("item_id") or "").strip()
            if item_id:
                return item_id
            learner_norm = _normalize(parsed_erratum.get("learner_text"))
            target_norm = _normalize(parsed_erratum.get("corrected_target"))
            label_norm = _normalize(parsed_erratum.get("display_label"))
            matches = []
            for fallback_erratum in fallback_errata:
                if not fallback_erratum.get("item_id"):
                    continue
                fallback_target_norm = _normalize(fallback_erratum.get("corrected_target"))
                fallback_learner_norm = _normalize(fallback_erratum.get("learner_text"))
                if target_norm and target_norm != fallback_target_norm:
                    continue
                if learner_norm and learner_norm != fallback_learner_norm:
                    continue
                matches.append(fallback_erratum)
            if len(matches) == 1:
                return str(matches[0].get("item_id") or "")
            if label_norm:
                label_matches = [
                    fallback_erratum
                    for fallback_erratum in matches
                    if _normalize(fallback_erratum.get("display_label")) == label_norm
                ]
                if len(label_matches) == 1:
                    return str(label_matches[0].get("item_id") or "")
            return ""

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
                    "item_id": fallback_item_id_for(item),
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
            "item_id": item.get("id"),
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
    "ItemVerdict",
    "pregenerate_next_atelier_session",
    "run_atelier_ai_review",
    "serialize_erratum_record",
    "serialize_concept",
    "session_exercise_set",
]
