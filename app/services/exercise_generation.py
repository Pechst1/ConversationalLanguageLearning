"""Shared AI exercise generation engine."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import not_
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User
from app.services.atelier_assets import AtelierAssetService
from app.services.error_memory import ErrorMemoryService, serialize_error_memory
from app.services.grammar import GrammarService
from app.services.grammar_feedback import infer_grammar_profile
from app.services.llm_service import LLMProviderError, LLMService
from app.services.progress import ProgressService
from app.services.unified_srs import InterleavingMode, ItemType, UnifiedSRSService

EXERCISE_ENGINE_VERSION = "ai-exercise-engine-v1"


class ExerciseGenerationUnavailable(RuntimeError):
    """Raised when AI exercise generation cannot produce a safe learner payload."""


@dataclass(frozen=True, slots=True)
class DailyExerciseContext:
    """Compact context used by all AI exercise generation calls."""

    user_id: str | None
    target_language: str
    generated_at: str
    concepts: list[dict[str, Any]]
    due_errata: list[dict[str, Any]]
    due_vocabulary: list[dict[str, Any]]
    unified_queue: list[dict[str, Any]]
    concept_blueprints: dict[str, dict[str, Any]]

    def prompt_payload(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "target_language": self.target_language,
            "generated_at": self.generated_at,
            "daily_grammar_concepts": self.concepts,
            "due_errata": self.due_errata,
            "due_vocabulary": self.due_vocabulary,
            "unified_queue": self.unified_queue,
            "concept_blueprints": self.concept_blueprints,
        }


@dataclass(frozen=True, slots=True)
class GeneratedExerciseBundle:
    """Validated AI generation result plus its trace metadata."""

    exercise_kind: str
    payload: dict[str, Any]
    context: DailyExerciseContext
    provider: str
    model: str
    prompt_version: str
    validation_notes: str


BRIEF_GRAMMAR_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "brief_grammar_exercises",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "exercises": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "string"},
                            "type": {
                                "type": "string",
                                "enum": ["fill_blank", "translation", "correction", "short_answer"],
                            },
                            "difficulty": {"type": "string", "enum": ["a", "b", "c"]},
                            "instruction": {"type": "string"},
                            "prompt": {"type": "string"},
                            "correct_answer": {"type": "string"},
                            "hint": {"type": "string"},
                        },
                        "required": [
                            "id",
                            "type",
                            "difficulty",
                            "instruction",
                            "prompt",
                            "correct_answer",
                            "hint",
                        ],
                    },
                }
            },
            "required": ["exercises"],
        },
    },
}


ERROR_EXERCISE_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "error_repair_exercise",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "exercise_type": {"type": "string", "enum": ["correction", "rewrite", "short_answer"]},
                "instruction": {"type": "string"},
                "prompt": {"type": "string"},
                "correct_answer": {"type": "string"},
                "explanation": {"type": "string"},
                "memory_tip": {"type": "string"},
            },
            "required": [
                "exercise_type",
                "instruction",
                "prompt",
                "correct_answer",
                "explanation",
                "memory_tip",
            ],
        },
    },
}


PASSAGE_READING_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "guided_reading_episode_exercises",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "comprehension": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                            "evidence": {"type": "string"},
                        },
                        "required": ["question", "answer", "evidence"],
                    },
                },
                "vocabulary": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "word": {"type": "string"},
                            "context_sentence": {"type": "string"},
                            "gloss_hint": {"type": "string"},
                        },
                        "required": ["word", "context_sentence", "gloss_hint"],
                    },
                },
                "grammar": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "pattern": {"type": "string"},
                            "prompt": {"type": "string"},
                            "answer": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["pattern", "prompt", "answer", "explanation"],
                    },
                },
                "production": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "prompt": {"type": "string"},
                        "example_answer": {"type": "string"},
                        "success_criteria": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 4,
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["prompt", "example_answer", "success_criteria"],
                },
            },
            "required": ["comprehension", "vocabulary", "grammar", "production"],
        },
    },
}


def _compact_text(value: Any, *, max_length: int = 800) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."


def _split_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_compact_text(item, max_length=220) for item in value if _compact_text(item, max_length=220)]
    if not value:
        return []
    parts = re.split(r"\s*[;|]\s*", str(value))
    return [_compact_text(item, max_length=220) for item in parts if item.strip()]


def _atelier_target_contract(concept: GrammarConcept) -> str:
    profile = infer_grammar_profile(concept)
    if profile.key == "tense_aspect":
        return (
            "For output_ladder example_answer, use a standalone answer that contains both an imparfait "
            "background/habit/state verb and a passe compose completed-event verb."
        )
    if profile.key == "si_present_result_form":
        return (
            "For output_ladder example_answer, use a full standalone si or s' present-tense condition "
            "plus a future simple or imperative result. Do not return only the result fragment, and do not use conditionnel."
        )
    if profile.key == "article_after_negation":
        return (
            "For output_ladder example_answer, use a full standalone ne/n' ... pas de/d' quantity frame "
            "unless the task is explicitly the etre exception."
        )
    return (
        "For output_ladder example_answer, use a full standalone answer that visibly demonstrates "
        f"the target grammar: {profile.pattern}"
    )


def _serialize_concept(concept: GrammarConcept, *, role: str, progress: UserGrammarProgress | None = None) -> dict[str, Any]:
    return {
        "id": concept.id,
        "external_id": concept.external_id,
        "role": role,
        "name": concept.name,
        "level": concept.level,
        "category": concept.category,
        "subskill": concept.subskill,
        "description": _compact_text(concept.description, max_length=360),
        "core_rule": _compact_text(concept.core_rule, max_length=360),
        "main_traps": _split_list(concept.main_traps)[:4],
        "anchor_examples": _split_list(concept.anchor_examples or concept.examples)[:4],
        "exercise_tags": concept.exercise_tags or [],
        "is_foundation": concept.is_foundation,
        "progress": {
            "score": progress.score if progress else None,
            "reps": progress.reps if progress else 0,
            "state": progress.state if progress else "new",
            "next_review": progress.next_review.isoformat() if progress and progress.next_review else None,
        },
    }


def _serialize_word(item: dict[str, Any]) -> dict[str, Any]:
    translations = item.get("translations") if isinstance(item.get("translations"), dict) else {}
    return {
        "word_id": item.get("word_id"),
        "word": _compact_text(item.get("word"), max_length=80),
        "translation": _compact_text(
            item.get("translation")
            or translations.get("de")
            or translations.get("en")
            or translations.get("fr"),
            max_length=90,
        ),
        "bucket": _compact_text(item.get("bucket"), max_length=40),
        "priority_score": item.get("priority_score") or 0,
        "example_sentence": _compact_text(item.get("example_sentence"), max_length=180),
        "example_translation": _compact_text(item.get("example_translation"), max_length=180),
    }


def _filled(value: Any) -> bool:
    return bool(str(value or "").strip())


def _quoted_fragments(value: Any) -> list[str]:
    text = str(value or "")
    fragments: list[str] = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"|«([^»]+)»", text):
        fragment = next((group for group in match.groups() if group), "")
        if fragment.strip():
            fragments.append(fragment.strip())
    return fragments


def _directed_rewrite_instruction_errors(item: dict[str, Any]) -> list[str]:
    if item.get("type") != "directed_rewrite":
        return []
    instruction = str(item.get("instruction") or "")
    source = str(item.get("source") or "")
    expected = str(item.get("expected_answer") or "")
    quoted = _quoted_fragments(instruction)
    normalized_source = _compact_text(source, max_length=500).lower()
    normalized_expected = _compact_text(expected, max_length=500).lower()
    has_source_fragment = any(fragment.lower() in normalized_source for fragment in quoted)
    has_target_form = any(fragment.lower() in normalized_expected for fragment in quoted if not fragment.lower() in normalized_source)
    has_target_marker = bool(re.search(r"\b(?:to|into|use|target|form|present|future|imparfait|passe|passé|conditional|conditionnel|subjunctive|subjonctif)\b", instruction, re.I))
    if not has_source_fragment:
        return ["directed_rewrite instructions must quote the source word or phrase to change"]
    if not (has_target_form or has_target_marker):
        return ["directed_rewrite instructions must name the target form to use"]
    return []


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ExerciseGenerationService:
    """Build SRS context and request strict AI exercise payloads."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm_service = llm_service
        self._llm_unavailable = False

    def build_daily_context(
        self,
        *,
        user: User | None = None,
        target_concept: GrammarConcept | None = None,
        target_error: UserError | None = None,
    ) -> DailyExerciseContext:
        target_language = (
            getattr(user, "target_language", None)
            or getattr(target_concept, "language", None)
            or "fr"
        ).strip() or "fr"
        try:
            from app.services.atelier import AtelierScheduler

            AtelierScheduler(self.db).ensure_catalog()
        except Exception as exc:
            logger.debug("Exercise generation catalog context unavailable", error=str(exc))
        selected = self.select_daily_concepts(
            user=user,
            target_language=target_language,
            target_concept=target_concept,
        )
        errata = self._due_errata_context(user=user, target_error=target_error)
        vocabulary = self._due_vocabulary_context(user=user)
        unified_queue = self._unified_queue_context(user=user)
        blueprints = self._blueprint_context([concept for concept, _, _ in selected])
        return DailyExerciseContext(
            user_id=str(user.id) if user else None,
            target_language=target_language,
            generated_at=datetime.now(UTC).isoformat(),
            concepts=[
                _serialize_concept(concept, role=role, progress=progress)
                for concept, role, progress in selected
            ],
            due_errata=errata,
            due_vocabulary=vocabulary,
            unified_queue=unified_queue,
            concept_blueprints=blueprints,
        )

    def select_daily_concepts(
        self,
        *,
        user: User | None,
        target_language: str = "fr",
        target_concept: GrammarConcept | None = None,
    ) -> list[tuple[GrammarConcept, str, UserGrammarProgress | None]]:
        selected: list[tuple[GrammarConcept, str, UserGrammarProgress | None]] = []
        seen: set[int] = set()

        def progress_for(concept_id: int) -> UserGrammarProgress | None:
            if not user:
                return None
            return (
                self.db.query(UserGrammarProgress)
                .filter(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.concept_id == concept_id,
                )
                .first()
            )

        def add(concept: GrammarConcept | None, role: str, progress: UserGrammarProgress | None = None) -> None:
            if not concept or concept.id in seen or len(selected) >= 3:
                return
            selected.append((concept, role, progress if progress is not None else progress_for(concept.id)))
            seen.add(concept.id)

        if user:
            for error in ErrorMemoryService(self.db).due_error_records(
                user,
                limit=20,
                review_modes={"grammar", "spelling", "speaking"},
            ):
                if not error.concept_id:
                    continue
                concept = self.db.get(GrammarConcept, int(error.concept_id))
                if concept and concept.active and concept.language == target_language:
                    add(concept, "errata")
                if len(selected) >= 3:
                    return selected

            for concept, progress in GrammarService(self.db).get_due_concepts(user=user, limit=30):
                if not concept.active or concept.language != target_language:
                    continue
                fragile = progress is None or float(progress.score or 0) < 7.0
                next_review = _as_aware(progress.next_review) if progress else None
                due = progress is None or next_review is None or next_review <= datetime.now(UTC)
                if fragile or due:
                    add(concept, "fragile", progress)
                if len(selected) >= 3:
                    return selected

        if target_concept and target_concept.active:
            add(target_concept, "target")

        active_query = self.db.query(GrammarConcept).filter(
            GrammarConcept.active.is_(True),
            GrammarConcept.language == target_language,
        )
        if seen:
            active_query = active_query.filter(not_(GrammarConcept.id.in_(seen)))
        for concept in (
            active_query.filter(GrammarConcept.is_foundation.is_(True))
            .order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())
            .limit(12)
            .all()
        ):
            add(concept, "foundation")
            if len(selected) >= 3:
                return selected

        active_query = self.db.query(GrammarConcept).filter(
            GrammarConcept.active.is_(True),
            GrammarConcept.language == target_language,
        )
        if seen:
            active_query = active_query.filter(not_(GrammarConcept.id.in_(seen)))
        for concept in active_query.order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc()).limit(12).all():
            add(concept, "contrast")
            if len(selected) >= 3:
                return selected

        if len(selected) != 3:
            raise ExerciseGenerationUnavailable("Daily exercise generation requires exactly 3 grammar concepts.")
        return selected

    def generate_atelier_exercise(
        self,
        *,
        concept: GrammarConcept,
        user: User | None = None,
        target_vocabulary: list[dict[str, Any]] | None = None,
        validation_feedback: list[str] | None = None,
    ) -> GeneratedExerciseBundle:
        llm = self._get_llm_service()
        context = self.build_daily_context(user=user, target_concept=concept)
        context_payload = context.prompt_payload()
        if target_vocabulary:
            context_payload["target_vocabulary"] = [
                {
                    "word_id": item.get("word_id"),
                    "word": item.get("word"),
                    "translation": item.get("translation"),
                    "bucket": item.get("bucket"),
                    "example_sentence": item.get("example_sentence"),
                    "example_translation": item.get("example_translation"),
                }
                for item in target_vocabulary[:4]
                if isinstance(item, dict) and item.get("word")
            ]
        profile = infer_grammar_profile(concept)
        context_payload["learner_cefr_level"] = (
            getattr(user, "cefr_estimate", None)
            or getattr(user, "proficiency_level", None)
            or concept.level
            or "A2"
        )
        context_payload["target_concept"] = {
            **_serialize_concept(concept, role="target"),
            "profile": profile.as_dict(),
        }
        target_contract = _atelier_target_contract(concept)
        system_prompt = (
            "You generate compact French grammar exercise payloads for Atelier. "
            "Return only valid JSON matching the provided schema. "
            "Every recognize mode must contain exactly 3 subitems, transform must contain exactly 3 rewrite tasks, "
            "and output_ladder must include exactly 1 concise item for each of sentence, speak, and conversation. "
            "Each word_bank item must be a full French sentence-building task: prompt must not contain a blank, "
            "meaning_cue must be the learner's L1 (English) translation of the exact target sentence (you may prefix it with 'Express: '); "
            "it must NEVER be a generic build instruction such as 'write a complete sentence using X' or 'use every target chip' — always the real English meaning, "
            "answer_tokens must be the complete ordered French sentence, and tokens must contain those exact answer_tokens "
            "scrambled plus at least one plausible distractor chip. The meaning_cue must match the correct_answer without exposing the French target sentence. "
            "For verb patterns, make one distractor an adjacent wrong form "
            "of the target verb, such as present vs future or future vs conditional. Use fill only for blanks; never pad answer_tokens just to reach a length. "
            "Fill items must have at least three distinct choices: the answer plus two plausible wrong forms. "
            "Classify labels must name contrastive grammatical forms, never generic affirmative/negative or true/false labels. "
            "Transform instructions must QUOTE the exact source word or phrase to change (in quotes) and name the grammatical target category "
            "(a tense or rule name such as 'the imparfait', 'the future', 'its negated form'), but MUST NOT spell out the corrected word or the answer. "
            "For example: \"Change 'pleut' to the imparfait\" (never \"change pleut to pleuvait\"); "
            "\"Change the article 'une' after 'pas' to its negated form\" (never \"change 'une' to de\"). "
            "Each output_ladder example_answer must be a standalone full French answer that visibly uses the target grammar; "
            "do not split required grammar between prompt and answer. "
            "Every output_ladder prompt (sentence, speak, conversation) and the produce.prompt must set a concrete, real-life mini-situation the learner reacts to "
            "— a short incoming message, a question from a person, or a brief scene — that naturally forces the target grammar in the reply. "
            "Never use a generic instruction like 'write/say/answer one sentence using the target grammar'; give an actual situation with a who/what/where. "
            "When context.target_vocabulary is provided, naturally weave those French words into prompts or examples where they fit. "
            "When context.due_errata includes task_error_type or error_pattern, aim at those sub-patterns directly. "
            "Worked examples: fill = prompt 'Je ne bois pas ____ café.' choices ['de','du'] correct_answer 'de'; "
            "word_bank = prompt 'Build the full French sentence.' meaning_cue 'Express: I do not drink coffee.' "
            "answer_tokens ['Je','ne','bois','pas','de','café']; "
            "classify = labels ['article changes','être exception']; "
            "transform = directed_rewrite with instruction \"Change the article 'du' after the negation to its negated partitive form\" "
            "(source 'du', expected_answer 'de') — quote the source and name the grammatical target in plain learner words; "
            "NEVER invent internal codes like 'être-exception contrast' or 'its contrast with negation', and never spell out the answer in the instruction. "
            f"{target_contract} "
            "Generate the exercise prompts, answer keys, and short target examples; the backend supplies rule-card and correction copy. "
            "Use accurate French accents and learner-facing wording rather than internal codes. "
            "Do not use filler encouragement, meta copy, examples inside instructions, or motivational prefaces. "
            "Every displayed sentence must be useful for completing the exercise."
        )
        user_payload = {
            "engine_version": EXERCISE_ENGINE_VERSION,
            "exercise_kind": "atelier_full_set",
            "target_concept_id": concept.id,
            "target_concept_external_id": concept.external_id,
            "strict_contract": {
                "recognize_modes": ["fill", "classify", "word_bank"],
                "recognize_items_per_mode": 3,
                "word_bank_format": "full_sentence_build_no_blanks_no_padding_with_distractor_chip",
                "word_bank_requires_meaning_cue": True,
                "minimum_fill_choices": 3,
                "minimum_word_bank_distractors": 1,
                "transform_types": ["directed_rewrite", "contrast_rewrite", "repair_rewrite"],
                "directed_rewrite_requires_explicit_source_and_target": True,
                "output_ladder_rounds": ["sentence", "speak", "conversation"],
                "learner_fallback_allowed": False,
                "output_ladder_example_contract": target_contract,
            },
            "context": context_payload,
        }
        if validation_feedback:
            user_payload["validation_feedback"] = {
                "previous_attempt_rejected_for": validation_feedback,
                "repair_instruction": (
                    "Regenerate the whole payload. Fix every listed issue while preserving the strict schema. "
                    "Do not repeat the rejected output_ladder examples."
                ),
            }
        try:
            from app.services.atelier import ATELIER_EXERCISE_RESPONSE_FORMAT

            result = llm.generate_chat_completion(
                [{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
                system_prompt=system_prompt,
                response_format=ATELIER_EXERCISE_RESPONSE_FORMAT,
                temperature=0.35,
                max_tokens=2500,
                model=settings.ATELIER_EXERCISE_LLM_MODEL,
                request_timeout=settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
                reasoning_effort=settings.ATELIER_EXERCISE_LLM_REASONING_EFFORT,
            )
            parsed = self._parse_json(result.content)
            validation_errors = validate_atelier_generation_payload(parsed)
            if validation_errors:
                raise ExerciseGenerationUnavailable("; ".join(validation_errors))
            return GeneratedExerciseBundle(
                exercise_kind="atelier_full_set",
                payload=parsed,
                context=context,
                provider=result.provider,
                model=result.model,
                prompt_version=EXERCISE_ENGINE_VERSION,
                validation_notes=f"Generated by {result.provider}:{result.model} with strict Atelier exercise schema.",
            )
        except ExerciseGenerationUnavailable:
            raise
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning(
                "AI Atelier exercise generation unavailable",
                concept_id=concept.id,
                external_id=concept.external_id,
                error=str(exc),
            )
            raise ExerciseGenerationUnavailable(str(exc)) from exc

    def generate_brief_grammar_exercises(
        self,
        *,
        concept: GrammarConcept,
        user: User | None = None,
    ) -> GeneratedExerciseBundle:
        llm = self._get_llm_service()
        context = self.build_daily_context(user=user, target_concept=concept)
        payload = {
            "engine_version": EXERCISE_ENGINE_VERSION,
            "exercise_kind": "brief_grammar",
            "target_concept_id": concept.id,
            "target_concept": _serialize_concept(concept, role="target"),
            "strict_contract": {
                "exercise_count": 3,
                "learner_fallback_allowed": False,
                "progression": ["recognition", "controlled_production", "contrast_or_repair"],
            },
            "context": context.prompt_payload(),
        }
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                system_prompt=(
                    "Generate exactly three brief learner-facing French grammar exercises. "
                    "Return only JSON matching the schema. Keep prompts concrete, answerable, and tied to the target concept."
                ),
                response_format=BRIEF_GRAMMAR_RESPONSE_FORMAT,
                temperature=0.35,
                max_tokens=1200,
                model=settings.ATELIER_EXERCISE_LLM_MODEL,
                request_timeout=settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
            )
            parsed = self._parse_json(result.content)
            errors = validate_brief_grammar_payload(parsed)
            if errors:
                raise ExerciseGenerationUnavailable("; ".join(errors))
            parsed["concept_id"] = concept.id
            parsed["concept_name"] = concept.name
            parsed["level"] = concept.level
            parsed["source"] = "llm"
            parsed["model"] = result.model
            return GeneratedExerciseBundle(
                exercise_kind="brief_grammar",
                payload=parsed,
                context=context,
                provider=result.provider,
                model=result.model,
                prompt_version=EXERCISE_ENGINE_VERSION,
                validation_notes=f"Generated by {result.provider}:{result.model} with strict brief grammar schema.",
            )
        except ExerciseGenerationUnavailable:
            raise
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Brief grammar exercise generation unavailable", concept_id=concept.id, error=str(exc))
            raise ExerciseGenerationUnavailable(str(exc)) from exc

    def generate_error_exercise(
        self,
        *,
        error: UserError,
        user: User | None = None,
    ) -> GeneratedExerciseBundle:
        llm = self._get_llm_service()
        user = user or self.db.get(User, error.user_id)
        concept = self.db.get(GrammarConcept, error.concept_id) if error.concept_id else None
        context = self.build_daily_context(user=user, target_concept=concept, target_error=error)
        prompt_payload = {
            "engine_version": EXERCISE_ENGINE_VERSION,
            "exercise_kind": "error_repair",
            "target_error": serialize_error_memory(error),
            "linked_concept": _serialize_concept(concept, role="linked_erratum") if concept else None,
            "strict_contract": {
                "exercise_count": 1,
                "learner_fallback_allowed": False,
                "prompt_must_not_copy_unusable_empty_fields": True,
            },
            "context": context.prompt_payload(),
        }
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False, default=str)}],
                system_prompt=(
                    "Generate one brief French repair exercise from the stored learner error. "
                    "Return only JSON matching the schema. The prompt must be answerable without exposing the answer."
                ),
                response_format=ERROR_EXERCISE_RESPONSE_FORMAT,
                temperature=0.3,
                max_tokens=800,
                model=settings.ATELIER_EXERCISE_LLM_MODEL,
                request_timeout=settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
            )
            parsed = self._parse_json(result.content)
            errors = validate_error_exercise_payload(parsed)
            if errors:
                raise ExerciseGenerationUnavailable("; ".join(errors))
            parsed["error_id"] = str(error.id)
            parsed["original_text"] = error.original_text
            parsed["stored_correction"] = error.correction
            parsed["source"] = "llm"
            parsed["model"] = result.model
            return GeneratedExerciseBundle(
                exercise_kind="error_repair",
                payload=parsed,
                context=context,
                provider=result.provider,
                model=result.model,
                prompt_version=EXERCISE_ENGINE_VERSION,
                validation_notes=f"Generated by {result.provider}:{result.model} with strict error exercise schema.",
            )
        except ExerciseGenerationUnavailable:
            raise
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Error repair exercise generation unavailable", error_id=str(error.id), error=str(exc))
            raise ExerciseGenerationUnavailable(str(exc)) from exc

    def generate_passage_exercises(
        self,
        *,
        passage_text: str,
        episode_title: str,
        cefr_level: str,
        user: User | None = None,
        vocab_seed: list[dict[str, Any]] | None = None,
        grammar_seed: list[dict[str, Any]] | None = None,
    ) -> GeneratedExerciseBundle:
        """Generate guided-reading exercises grounded in one uploaded-book passage."""

        llm = self._get_llm_service()
        target_language = (getattr(user, "target_language", None) or "fr").strip() or "fr"
        context = DailyExerciseContext(
            user_id=str(user.id) if user else None,
            target_language=target_language,
            generated_at=datetime.now(UTC).isoformat(),
            concepts=[],
            due_errata=self._due_errata_context(user=user, target_error=None),
            due_vocabulary=self._due_vocabulary_context(user=user),
            unified_queue=self._unified_queue_context(user=user),
            concept_blueprints={},
        )
        prompt_payload = {
            "engine_version": EXERCISE_ENGINE_VERSION,
            "exercise_kind": "guided_reading_episode",
            "episode_title": _compact_text(episode_title, max_length=180),
            "learner_cefr_level": _compact_text(cefr_level, max_length=20),
            "target_language": target_language,
            "passage": _compact_text(passage_text, max_length=5000),
            "vocab_seed": vocab_seed or [],
            "grammar_seed": grammar_seed or [],
            "strict_contract": {
                "ground_every_item_in_passage": True,
                "comprehension_count": "2-3",
                "vocabulary_count": "3-5",
                "grammar_count": "1-3",
                "production_count": 1,
                "learner_fallback_allowed": False,
            },
            "context": context.prompt_payload(),
        }
        try:
            result = llm.generate_chat_completion(
                [{"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False, default=str)}],
                system_prompt=(
                    "Generate compact French guided-reading exercises for one uploaded-book episode. "
                    "Return only JSON matching the schema. Every question, vocabulary item, grammar prompt, "
                    "and production task must be visibly grounded in the provided passage. Keep the level "
                    "appropriate for the learner CEFR level, and prefer French prompts with concise support."
                ),
                response_format=PASSAGE_READING_RESPONSE_FORMAT,
                temperature=0.3,
                max_tokens=1600,
                model=settings.ATELIER_EXERCISE_LLM_MODEL,
                request_timeout=settings.ATELIER_EXERCISE_LLM_TIMEOUT_SECONDS,
                disable_retries=True,
            )
            parsed = self._parse_json(result.content)
            errors = validate_passage_reading_payload(parsed)
            if errors:
                raise ExerciseGenerationUnavailable("; ".join(errors))
            parsed["source"] = "llm"
            parsed["engine_version"] = EXERCISE_ENGINE_VERSION
            parsed["model"] = result.model
            parsed["episode_title"] = episode_title
            parsed["cefr_level"] = cefr_level
            return GeneratedExerciseBundle(
                exercise_kind="guided_reading_episode",
                payload=parsed,
                context=context,
                provider=result.provider,
                model=result.model,
                prompt_version=EXERCISE_ENGINE_VERSION,
                validation_notes=f"Generated by {result.provider}:{result.model} with strict passage-reading schema.",
            )
        except ExerciseGenerationUnavailable:
            raise
        except (json.JSONDecodeError, LLMProviderError, ValueError, TypeError) as exc:
            logger.warning("Passage exercise generation unavailable", episode_title=episode_title, error=str(exc))
            raise ExerciseGenerationUnavailable(str(exc)) from exc

    def _get_llm_service(self) -> LLMService:
        if self.llm_service:
            return self.llm_service
        if not settings.ATELIER_LLM_ENABLED:
            raise ExerciseGenerationUnavailable("AI exercise generation is disabled.")
        if self._llm_unavailable:
            raise ExerciseGenerationUnavailable("AI exercise generation is unavailable.")
        try:
            self.llm_service = LLMService()
            return self.llm_service
        except Exception as exc:
            self._llm_unavailable = True
            raise ExerciseGenerationUnavailable(str(exc)) from exc

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("Exercise generation returned a non-object payload.")
        return parsed

    def _due_errata_context(
        self,
        *,
        user: User | None,
        target_error: UserError | None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(error: UserError | None) -> None:
            if not error or str(error.id) in seen:
                return
            serialized = serialize_error_memory(error)
            items.append(
                {
                    "id": serialized.get("id"),
                    "concept_id": serialized.get("concept_id"),
                    "linked_word_id": serialized.get("linked_word_id"),
                    "display_label": _compact_text(serialized.get("display_label"), max_length=120),
                    "original_text": _compact_text(serialized.get("original_text"), max_length=180),
                    "correction": _compact_text(serialized.get("correction"), max_length=180),
                    "why_wrong": _compact_text(serialized.get("why_wrong") or serialized.get("context"), max_length=240),
                    "repair_hint": _compact_text(serialized.get("repair_hint"), max_length=220),
                    "task_error_type": _compact_text(serialized.get("task_error_type"), max_length=90),
                    "error_pattern": _compact_text(serialized.get("error_pattern"), max_length=120),
                    "review_mode": serialized.get("review_mode"),
                    "lapses": serialized.get("lapses") or 0,
                    "occurrences": serialized.get("occurrences") or 0,
                }
            )
            seen.add(str(error.id))

        add(target_error)
        if user:
            for error in ErrorMemoryService(self.db).due_error_records(user, limit=8):
                add(error)
        return items[:8]

    def _due_vocabulary_context(self, *, user: User | None) -> list[dict[str, Any]]:
        if not user:
            return []
        try:
            recommendations = ProgressService(self.db).get_vocabulary_recommendations(
                user=user,
                limit=8,
                due_limit=4,
                fragile_limit=2,
                new_limit=2,
                direction="fr_to_de",
            )
        except Exception as exc:
            logger.debug("Exercise generation vocabulary context unavailable", error=str(exc))
            return []
        return [_serialize_word(item) for item in recommendations.get("items") or [] if isinstance(item, dict)]

    def _unified_queue_context(self, *, user: User | None) -> list[dict[str, Any]]:
        if not user:
            return []
        try:
            queue = UnifiedSRSService(self.db).get_daily_practice_queue(
                user_id=user.id,
                time_budget_minutes=8,
                interleaving_mode=InterleavingMode.PRIORITY,
            ).queue
        except Exception as exc:
            logger.debug("Exercise generation unified SRS context unavailable", error=str(exc))
            return []
        compact: list[dict[str, Any]] = []
        for item in queue[:10]:
            metadata = item.metadata or {}
            compact.append(
                {
                    "item_type": item.item_type.value if isinstance(item.item_type, ItemType) else str(item.item_type),
                    "original_id": str(item.original_id),
                    "priority_score": round(float(item.priority_score or 0), 3),
                    "display_title": _compact_text(item.display_title, max_length=120),
                    "level": item.level,
                    "due_since_days": item.due_since_days,
                    "metadata": {
                        "concept_id": metadata.get("concept_id"),
                        "word_id": metadata.get("word_id"),
                        "linked_word_id": metadata.get("linked_word_id"),
                        "lapses": metadata.get("lapses") or 0,
                        "score": metadata.get("score"),
                        "review_mode": metadata.get("review_mode"),
                    },
                }
            )
        return compact

    def _blueprint_context(self, concepts: list[GrammarConcept]) -> dict[str, dict[str, Any]]:
        service = AtelierAssetService(self.db)
        blueprints: dict[str, dict[str, Any]] = {}
        for concept in concepts:
            try:
                blueprint = service.approved_blueprint_payload(concept)
            except Exception as exc:
                logger.debug("Exercise generation blueprint context unavailable", concept_id=concept.id, error=str(exc))
                blueprint = {}
            pedagogy = blueprint.get("pedagogy") if isinstance(blueprint, dict) else {}
            xray = blueprint.get("sentence_xray") if isinstance(blueprint, dict) else {}
            recipe = blueprint.get("exercise_recipe") if isinstance(blueprint, dict) else {}
            blueprints[str(concept.id)] = {
                "display_title": _compact_text(blueprint.get("display_title") or concept.name, max_length=160)
                if isinstance(blueprint, dict)
                else concept.name,
                "core_rule": _compact_text((pedagogy or {}).get("core_rule") or concept.core_rule, max_length=360),
                "pattern": _compact_text((pedagogy or {}).get("pattern"), max_length=180),
                "main_traps": ((pedagogy or {}).get("main_traps") or _split_list(concept.main_traps))[:4],
                "anchor_sentence": _compact_text((xray or {}).get("sentence") or concept.anchor_examples, max_length=220),
                "recipe": {
                    "recognize": (recipe or {}).get("recognize") or {},
                    "subskills": (recipe or {}).get("subskills") or [],
                    "output_ladder": (recipe or {}).get("output_ladder") or {},
                },
            }
        return blueprints


def validate_atelier_generation_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    recognize = payload.get("recognize") if isinstance(payload.get("recognize"), dict) else {}
    if set(recognize.keys()) != {"fill", "word_bank", "classify"}:
        errors.append("recognize must include fill, word_bank, and classify")
        return errors
    for mode in ("fill", "classify", "word_bank"):
        items = (recognize.get(mode) or {}).get("items") if isinstance(recognize.get(mode), dict) else None
        if not isinstance(items, list) or len(items) != 3:
            errors.append(f"recognize.{mode}.items must contain exactly 3 items")
    for item in ((recognize.get("fill") or {}).get("items") or []):
        if not (_filled(item.get("id")) and _filled(item.get("prompt")) and _filled(item.get("correct_answer"))):
            errors.append("fill items require id, prompt, and correct_answer")
        if len(item.get("choices") or []) < 2:
            errors.append("fill items require at least 2 choices")
    for item in ((recognize.get("word_bank") or {}).get("items") or []):
        if not (
            _filled(item.get("id"))
            and _filled(item.get("prompt"))
            and _filled(item.get("meaning_cue"))
            and _filled(item.get("correct_answer"))
        ):
            errors.append("word_bank items require id, prompt, meaning_cue, and correct_answer")
        if len(item.get("tokens") or []) < 1 or len(item.get("answer_tokens") or []) < 1:
            errors.append("word_bank items require at least 1 token and answer_token")
    for item in ((recognize.get("classify") or {}).get("items") or []):
        if not (_filled(item.get("id")) and _filled(item.get("prompt")) and _filled(item.get("correct_label"))):
            errors.append("classify items require id, prompt, and correct_label")
        if len(item.get("labels") or []) < 2:
            errors.append("classify items require at least 2 labels")
    transform = (payload.get("transform") or {}).get("items") if isinstance(payload.get("transform"), dict) else None
    if not isinstance(transform, list) or len(transform) != 3:
        errors.append("transform.items must contain exactly 3 items")
    else:
        for item in transform:
            if not (
                _filled(item.get("id"))
                and _filled(item.get("instruction"))
                and _filled(item.get("source"))
                and _filled(item.get("expected_answer"))
            ):
                errors.append("transform items require id, instruction, source, and expected_answer")
                continue
            errors.extend(_directed_rewrite_instruction_errors(item))
    produce = payload.get("produce") if isinstance(payload.get("produce"), dict) else {}
    if not (_filled(produce.get("source_fragment")) and _filled(produce.get("prompt")) and produce.get("requirements")):
        errors.append("produce requires source_fragment, prompt, and requirements")
    ladder = payload.get("output_ladder") if isinstance(payload.get("output_ladder"), dict) else {}
    for round_name in ("sentence", "speak", "conversation"):
        items = (ladder.get(round_name) or {}).get("items") if isinstance(ladder.get(round_name), dict) else None
        if not isinstance(items, list) or len(items) != 1:
            errors.append(f"output_ladder.{round_name}.items must contain exactly 1 item")
            continue
        item = items[0]
        if not (
            _filled(item.get("id"))
            and _filled(item.get("instruction"))
            and _filled(item.get("prompt"))
            and _filled(item.get("example_answer"))
            and item.get("requirements")
        ):
            errors.append(f"output_ladder.{round_name} item is incomplete")
    return errors


def validate_brief_grammar_payload(payload: dict[str, Any]) -> list[str]:
    exercises = payload.get("exercises")
    if not isinstance(exercises, list) or len(exercises) != 3:
        return ["brief grammar payload must contain exactly 3 exercises"]
    errors: list[str] = []
    for item in exercises:
        if not isinstance(item, dict):
            errors.append("brief grammar exercise must be an object")
            continue
        for key in ("id", "type", "difficulty", "instruction", "prompt", "correct_answer", "hint"):
            if not _filled(item.get(key)):
                errors.append(f"brief grammar exercise missing {key}")
    return errors


def validate_error_exercise_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("exercise_type", "instruction", "prompt", "correct_answer", "explanation", "memory_tip"):
        if not _filled(payload.get(key)):
            errors.append(f"error exercise missing {key}")
    if str(payload.get("prompt") or "").strip() == str(payload.get("correct_answer") or "").strip():
        errors.append("error exercise prompt must not reveal the answer")
    return errors


def validate_passage_reading_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, minimum in (("comprehension", 2), ("vocabulary", 3), ("grammar", 1)):
        items = payload.get(key)
        if not isinstance(items, list) or len(items) < minimum:
            errors.append(f"passage reading payload requires at least {minimum} {key} items")
            continue
        for item in items:
            if not isinstance(item, dict):
                errors.append(f"{key} item must be an object")
                continue
            required = {
                "comprehension": ("question", "answer", "evidence"),
                "vocabulary": ("word", "context_sentence", "gloss_hint"),
                "grammar": ("pattern", "prompt", "answer", "explanation"),
            }[key]
            for field in required:
                if not _filled(item.get(field)):
                    errors.append(f"{key} item missing {field}")
    production = payload.get("production")
    if not isinstance(production, dict):
        errors.append("passage reading payload requires production")
    else:
        for key in ("prompt", "example_answer"):
            if not _filled(production.get(key)):
                errors.append(f"production missing {key}")
        criteria = production.get("success_criteria")
        if not isinstance(criteria, list) or len(criteria) < 2:
            errors.append("production requires at least 2 success criteria")
    return errors


__all__ = [
    "BRIEF_GRAMMAR_RESPONSE_FORMAT",
    "DailyExerciseContext",
    "ERROR_EXERCISE_RESPONSE_FORMAT",
    "EXERCISE_ENGINE_VERSION",
    "ExerciseGenerationService",
    "ExerciseGenerationUnavailable",
    "GeneratedExerciseBundle",
    "PASSAGE_READING_RESPONSE_FORMAT",
    "validate_atelier_generation_payload",
    "validate_brief_grammar_payload",
    "validate_error_exercise_payload",
    "validate_passage_reading_payload",
]
