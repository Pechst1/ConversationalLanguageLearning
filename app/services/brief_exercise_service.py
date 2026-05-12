"""Brief exercise service for Daily Practice quick exercises.

Generates:
- 3 brief grammar exercises (faster than full 9-exercise structure)
- Error correction exercises based on user mistakes
"""
from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.core.prompts.brief_exercise_prompts import (
    get_brief_grammar_prompt,
    get_error_exercise_prompt,
    get_answer_check_prompt,
)
from app.db.models.error import UserError
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.error_memory import ErrorMemoryService
from app.services.grammar_feedback import infer_grammar_profile, is_concept_demonstrated
from app.services.llm_service import LLMService


class BriefExerciseService:
    """Service for generating brief exercises for Daily Practice."""

    def __init__(self, db: Session, llm_service: LLMService | None = None) -> None:
        self.db = db
        self.llm = llm_service or LLMService()

    def _parse_json_response(self, content: str) -> dict[str, Any]:
        """Extract and parse JSON from LLM response."""
        # Try to find JSON block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if json_match:
            content = json_match.group(1)
        
        # Clean up common issues
        content = content.strip()
        if not content.startswith('{'):
            start = content.find('{')
            if start != -1:
                content = content[start:]
        
        # Find the closing brace
        brace_count = 0
        end_idx = 0
        for i, char in enumerate(content):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx > 0:
            content = content[:end_idx]
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}, content: {content[:300]}")
            return {"error": "Failed to parse response", "raw": content[:500]}

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "")
        ascii_form = normalized.encode("ascii", "ignore").decode("ascii")
        return " ".join(ascii_form.lower().split())

    def _matches_concept_pattern(
        self,
        *,
        concept: GrammarConcept | None,
        prompt: str,
        correct_answer: str,
        user_answer: str,
    ) -> bool:
        if not concept:
            return False

        return is_concept_demonstrated(
            concept,
            user_answer,
            prompt=prompt,
            correct_answer=correct_answer,
        )

    def _build_grammar_override(
        self,
        *,
        concept: GrammarConcept | None,
        correct_answer: str,
    ) -> dict[str, Any]:
        sample_solution = correct_answer if correct_answer and correct_answer != "(Freie Antwort)" else concept.examples if concept else ""
        profile = infer_grammar_profile(concept)
        return {
            "is_correct": True,
            "feedback": "Das passt zur Grammatikaufgabe.",
            "explanation": profile.principle,
            "sample_solution": sample_solution or "",
            "score": 8,
            "detected_error_category": "Grammar",
            "detected_subcategory": profile.label if concept else None,
        }

    async def generate_grammar_exercises(
        self,
        concept_id: int,
    ) -> dict[str, Any]:
        """Generate 3 brief grammar exercises for a concept.
        
        Returns:
            Dict with exercises list and metadata
        """
        concept = self.db.get(GrammarConcept, concept_id)
        if not concept:
            return {"error": f"Concept {concept_id} not found", "exercises": []}
        
        prompt = get_brief_grammar_prompt(concept.name, concept.level)
        
        try:
            logger.info(f"Generating brief exercises for concept: {concept.name}")
            result = await self._generate_with_llm(prompt, max_tokens=1500)
            parsed = self._parse_json_response(result.content)
            
            if "error" in parsed:
                logger.error(f"Brief exercise generation failed: {parsed}")
                return self._fallback_grammar_exercises(concept)
            
            # Add metadata
            parsed["concept_id"] = concept.id
            parsed["concept_name"] = concept.name
            parsed["level"] = concept.level
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error generating brief exercises for {concept.name}: {e}")
            return self._fallback_grammar_exercises(concept)

    async def generate_error_exercise(
        self,
        error_id: UUID,
    ) -> dict[str, Any]:
        """Generate an exercise based on user's error.
        
        Returns:
            Dict with exercise details for correction practice
        """
        error = self.db.get(UserError, error_id)
        if not error:
            return {"error": f"Error {error_id} not found"}
        
        prompt = get_error_exercise_prompt(
            original_text=error.original_text,
            correction=error.correction,
            error_category=error.error_category,
            context=error.context_snippet
        )
        
        try:
            logger.info(f"Generating error exercise for: {error.original_text}")
            result = await self._generate_with_llm(prompt, max_tokens=800)
            parsed = self._parse_json_response(result.content)
            
            if "error" in parsed:
                logger.error(f"Error exercise generation failed: {parsed}")
                return self._fallback_error_exercise(error)
            
            # Add metadata
            parsed["error_id"] = str(error.id)
            parsed["original_text"] = error.original_text
            parsed["stored_correction"] = error.correction
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error generating error exercise: {e}")
            return self._fallback_error_exercise(error)

    async def check_answer(
        self,
        exercise_type: str,
        prompt: str,
        correct_answer: str,
        user_answer: str,
        user_id: str | UUID | None = None,
        concept_id: int | None = None,
    ) -> dict[str, Any]:
        """Check user's answer using LLM for flexible validation.
        
        Returns:
            Dict with is_correct, feedback, explanation, score
        """
        # Quick check for exact match (case-insensitive, trimmed)
        if user_answer.strip().lower() == correct_answer.strip().lower():
            return {
                "is_correct": True,
                "feedback": "Richtig! 🎉",
                "explanation": "",
                "score": 10
            }
        
        # Use LLM for flexible checking
        check_prompt = get_answer_check_prompt(
            exercise_type=exercise_type,
            prompt=prompt,
            correct_answer=correct_answer,
            user_answer=user_answer
        )
        
        try:
            result = await self._generate_with_llm(check_prompt, max_tokens=500)
            parsed = self._parse_json_response(result.content)
            
            if "error" in parsed:
                # Fallback to simple comparison
                return self._fallback_check(
                    correct_answer,
                    user_answer,
                    prompt=prompt,
                    concept_id=concept_id,
                )

            concept = self.db.get(GrammarConcept, concept_id) if concept_id else None
            if (
                not parsed.get("is_correct", False)
                and exercise_type in {"short_answer", "correction", "fill_blank", "translation"}
                and self._matches_concept_pattern(
                    concept=concept,
                    prompt=prompt,
                    correct_answer=correct_answer,
                    user_answer=user_answer,
                )
            ):
                return self._build_grammar_override(
                    concept=concept,
                    correct_answer=correct_answer,
                )

            # Persist error if wrong and user_id is provided
            if not parsed.get("is_correct", False) and user_id:
                try:
                    self._persist_grammar_error(
                        user_id=user_id,
                        prompt=prompt,
                        user_answer=user_answer,
                        correct_answer=correct_answer,
                        explanation=parsed.get("explanation", ""),
                        concept_id=concept_id,
                        detected_category=parsed.get("detected_error_category"),
                        detected_subcategory=parsed.get("detected_subcategory")
                    )
                except Exception as e:
                    logger.error(f"Failed to persist grammar error: {e}")
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error checking answer: {e}")
            return self._fallback_check(
                correct_answer,
                user_answer,
                prompt=prompt,
                concept_id=concept_id,
            )

    async def _generate_with_llm(self, prompt: str, max_tokens: int = 1000):
        """Generate response from LLM using thread pool for async."""
        messages = [{"role": "user", "content": prompt}]

        def _blocking_call():
            return self.llm.generate_chat_completion(
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

        return await asyncio.to_thread(_blocking_call)

    def _fallback_grammar_exercises(self, concept: GrammarConcept) -> dict[str, Any]:
        """Fallback exercises if LLM fails."""
        return {
            "concept_id": concept.id,
            "concept_name": concept.name,
            "level": concept.level,
            "exercises": [
                {
                    "id": "1",
                    "type": "short_answer",
                    "difficulty": "a",
                    "instruction": "Erkläre das Konzept",
                    "prompt": f"Erkläre '{concept.name}' kurz in deinen eigenen Worten.",
                    "correct_answer": "(Freie Antwort)",
                    "hint": "Denke an Beispiele"
                },
                {
                    "id": "2", 
                    "type": "short_answer",
                    "difficulty": "b",
                    "instruction": "Bilde einen Beispielsatz",
                    "prompt": f"Bilde einen Satz, der '{concept.name}' verwendet.",
                    "correct_answer": "(Freie Antwort)",
                    "hint": "Verwende Alltagssituationen"
                },
                {
                    "id": "3",
                    "type": "short_answer",
                    "difficulty": "c",
                    "instruction": "Vergleiche Konzepte",
                    "prompt": f"Was ist der Unterschied zu ähnlichen Konzepten?",
                    "correct_answer": "(Freie Antwort)",
                    "hint": "Denke an Ausnahmen"
                }
            ]
        }

    def _fallback_error_exercise(self, error: UserError) -> dict[str, Any]:
        """Fallback error exercise if LLM fails."""
        return {
            "error_id": str(error.id),
            "exercise_type": "correction",
            "instruction": "Korrigiere den Fehler",
            "prompt": error.original_text or "Korrigiere diesen Satz.",
            "correct_answer": error.correction or "(Korrektur nicht verfügbar)",
            "explanation": error.context_snippet or "Achte auf die Grammatikregel.",
            "memory_tip": "Übung macht den Meister!",
            "original_text": error.original_text,
            "stored_correction": error.correction
        }

    def _persist_grammar_error(
        self,
        user_id: str | UUID,
        prompt: str,
        user_answer: str,
        correct_answer: str,
        explanation: str,
        concept_id: int | None = None,
        detected_category: str | None = None,
        detected_subcategory: str | None = None,
    ) -> None:
        """Create a UserError entry for the mistake."""
        # Determine best category/subcategory
        category = detected_category or "Grammar"
        subcategory = detected_subcategory

        # Fallback to concept name if no specific subcategory detected
        concept = self.db.get(GrammarConcept, concept_id) if concept_id else None
        if not subcategory and concept:
            subcategory = infer_grammar_profile(concept).label
        
        # Default if still empty
        if not subcategory:
            subcategory = "Review"

        user = self.db.get(User, user_id)
        if not user:
            return
        ErrorMemoryService(self.db).record_erratum(
            user=user,
            erratum={
                "display_label": subcategory or "Brief exercise",
                "learner_text": user_answer,
                "corrected_target": correct_answer,
                "why_wrong": explanation,
                "repair_hint": infer_grammar_profile(concept).repair if concept else "Review the requested form, then answer a fresh version of this exercise.",
                "severity": 2,
                "recurring": True,
                "task_error_type": subcategory or "brief_exercise_error",
                "concept_id": concept_id,
            },
            source_type="brief_exercise",
            concept_id=concept_id,
            source_payload={"prompt": prompt, "exercise_category": category},
        )
        self.db.commit()

    def _fallback_check(
        self,
        correct_answer: str,
        user_answer: str,
        *,
        prompt: str = "",
        concept_id: int | None = None,
    ) -> dict[str, Any]:
        """Simple fallback check without LLM."""
        # Normalize for comparison
        correct_norm = self._normalize_text(correct_answer)
        user_norm = self._normalize_text(user_answer)

        is_correct = correct_norm == user_norm

        concept = self.db.get(GrammarConcept, concept_id) if concept_id else None
        if (
            not is_correct
            and self._matches_concept_pattern(
                concept=concept,
                prompt=prompt,
                correct_answer=correct_answer,
                user_answer=user_answer,
            )
        ):
            return self._build_grammar_override(
                concept=concept,
                correct_answer=correct_answer,
            )
        
        # Check for partial match
        similarity = 0
        if len(correct_norm) > 0 and len(user_norm) > 0:
            common = set(correct_norm.split()) & set(user_norm.split())
            total = set(correct_norm.split()) | set(user_norm.split())
            similarity = len(common) / len(total) if total else 0
        
        if is_correct:
            return {
                "is_correct": True,
                "feedback": "Richtig! 🎉",
                "explanation": "",
                "sample_solution": correct_answer,
                "score": 10,
            }
        elif similarity > 0.5:
            return {
                "is_correct": False,
                "feedback": f"Fast! Die richtige Antwort ist: {correct_answer}",
                "explanation": "",
                "sample_solution": correct_answer,
                "score": 5
            }
        else:
            return {
                "is_correct": False,
                "feedback": f"Leider falsch. Richtig wäre: {correct_answer}",
                "explanation": "",
                "sample_solution": correct_answer,
                "score": 2
            }


__all__ = ["BriefExerciseService"]
