"""Grammar exercise service with LLM-generated exercises.

Improved version with 3×3 exercise structure:
- 3 exercise blocks
- Each with 3 difficulty levels (a, b, c)
- Progressive challenge
- Concept info box
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from loguru import logger

from app.core.prompts.grammar_prompts import (
    ANSWER_CORRECTION_PROMPT,
    get_exercise_prompt,
    get_concept_explanation_prompt,
)
from app.db.models.grammar import GrammarConcept
from app.services.llm_service import LLMService


class GrammarExerciseService:
    """Service for generating and checking grammar exercises using LLM."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
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

    async def generate_exercises(
        self,
        concept: GrammarConcept,
    ) -> dict[str, Any]:
        """Generate 3×3 exercises for a grammar concept.
        
        Returns exercises in the new block structure:
        - 3 exercise blocks
        - Each with 3 items (a, b, c difficulty)
        """
        prompt = get_exercise_prompt(concept.name, concept.level)

        try:
            logger.info(f"Generating exercises for concept: {concept.name} (level: {concept.level})")
            result = await self._generate_with_llm(prompt, max_tokens=4000)
            logger.info(f"LLM response received, tokens: {result.total_tokens}, parsing JSON...")
            parsed = self._parse_json_response(result.content)

            if "error" in parsed:
                logger.error(f"Exercise generation failed to parse: {parsed}")
                return self._fallback_exercises(concept)
            
            # Add concept metadata
            parsed["concept_id"] = concept.id
            parsed["concept_name"] = concept.name
            parsed["level"] = concept.level
            
            # Flatten exercises for easier frontend handling
            parsed["flat_exercises"] = self._flatten_exercises(parsed.get("exercises", []))
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error generating exercises for {concept.name}: {e}")
            return self._fallback_exercises(concept)

    def _flatten_exercises(self, blocks: list[dict]) -> list[dict]:
        """Flatten block structure into a linear list for frontend."""
        flat = []
        for block in blocks:
            block_num = block.get("block", 1)
            block_type = block.get("type", "unknown")
            for item in block.get("items", []):
                flat.append({
                    "block": block_num,
                    "type": block_type,
                    "level": item.get("level", "a"),
                    "instruction": item.get("instruction", ""),
                    "prompt": item.get("prompt", ""),
                    "correct_answer": item.get("correct_answer", ""),
                    "explanation": item.get("explanation", ""),
                    "id": f"{block_num}{item.get('level', 'a')}",  # e.g., "1a", "2b"
                })
        return flat

    async def check_answers(
        self,
        concept: GrammarConcept,
        exercises: list[dict[str, Any]],
        user_answers: list[str],
    ) -> dict[str, Any]:
        """Check user answers with strict criteria."""
        # Build exercises with answers for prompt
        exercises_text = ""
        for i, (ex, answer) in enumerate(zip(exercises, user_answers)):
            block = ex.get('block', 1)
            level = ex.get('level', 'a')
            exercises_text += f"""
Block {block}, Teil {level}):
- Typ: {ex.get('type', 'unknown')}
- Aufgabe: {ex.get('prompt', '')}
- Erwartete Antwort: {ex.get('correct_answer', '')}
- Schüler-Antwort: {answer or '(leer)'}
"""

        prompt = ANSWER_CORRECTION_PROMPT.format(
            concept_name=concept.name,
            level=concept.level,
            exercises_with_answers=exercises_text,
        )

        try:
            result = await self._generate_with_llm(prompt, max_tokens=2500)
            parsed = self._parse_json_response(result.content)
            
            if "error" in parsed:
                return self._fallback_correction(exercises, user_answers)
            
            # Flatten results for frontend
            parsed["flat_results"] = self._flatten_results(parsed.get("results", []))
            
            # Validate and fix total_score if needed
            total_score = parsed.get("total_score", 0)
            if total_score > 10 or total_score < 0:
                # LLM gave wrong score, recalculate from individual points
                flat_results = parsed["flat_results"]
                if flat_results:
                    avg_points = sum(r.get("points", 0) for r in flat_results) / len(flat_results)
                    parsed["total_score"] = round(avg_points, 1)
                    logger.warning(f"Fixed invalid total_score {total_score} to {parsed['total_score']}")
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error checking answers: {e}")
            return self._fallback_correction(exercises, user_answers)

    def _flatten_results(self, block_results: list[dict]) -> list[dict]:
        """Flatten block results into linear list."""
        flat = []
        for block in block_results:
            for item in block.get("items", []):
                flat.append(item)
        return flat

    async def generate_concept_explanation(
        self,
        concept: GrammarConcept,
    ) -> dict[str, Any]:
        """Generate a comprehensive explanation of a grammar concept.
        
        Returns structured info for the concept info box.
        """
        prompt = get_concept_explanation_prompt(concept.name, concept.level)
        
        try:
            result = await self._generate_with_llm(prompt, max_tokens=1500)
            parsed = self._parse_json_response(result.content)
            
            if "error" in parsed:
                logger.error(f"Concept explanation failed: {parsed}")
                return self._fallback_explanation(concept)
            
            return parsed
            
        except Exception as e:
            logger.exception(f"Error generating explanation for {concept.name}: {e}")
            return self._fallback_explanation(concept)

    def _fallback_explanation(self, concept: GrammarConcept) -> dict[str, Any]:
        """Fallback explanation if LLM fails."""
        return {
            "definition": f"{concept.name} ist ein wichtiges Grammatikkonzept auf {concept.level}-Niveau.",
            "usage": ["In formellen Texten", "In der gesprochenen Sprache", "In schriftlichen Arbeiten"],
            "distinction": None,
            "examples": [{"fr": "(Beispiel folgt)", "de": "(Übersetzung folgt)"}],
            "common_mistakes": [{"wrong": "-", "correct": "-", "why": "Übung macht den Meister!"}],
            "memory_tip": "Übe regelmäßig mit verschiedenen Beispielen."
        }

    async def _generate_with_llm(self, prompt: str, max_tokens: int = 2000):
        """Generate response from LLM.

        Uses asyncio.to_thread to run the blocking LLM call in a thread pool,
        allowing proper async behavior.
        """
        messages = [{"role": "user", "content": prompt}]

        def _blocking_call():
            return self.llm.generate_chat_completion(
                messages,
                temperature=0.7,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )

        return await asyncio.to_thread(_blocking_call)

    def _fallback_exercises(self, concept: GrammarConcept) -> dict[str, Any]:
        """Return structured fallback exercises if LLM fails."""
        fallback_items = [
            {"level": "a", "instruction": "Einfache Anwendung", "prompt": f"Erkläre '{concept.name}' in einem Satz.", "correct_answer": "(Freie Antwort)", "explanation": "Grundverständnis"},
            {"level": "b", "instruction": "Mittlere Anwendung", "prompt": f"Bilde einen Beispielsatz mit '{concept.name}'.", "correct_answer": "(Freie Antwort)", "explanation": "Praktische Anwendung"},
            {"level": "c", "instruction": "Schwere Anwendung", "prompt": f"Erkläre den Unterschied zu einem ähnlichen Konzept.", "correct_answer": "(Freie Antwort)", "explanation": "Tiefes Verständnis"},
        ]
        
        exercises = [
            {"block": 1, "type": "production", "items": fallback_items},
            {"block": 2, "type": "production", "items": fallback_items},
            {"block": 3, "type": "production", "items": fallback_items},
        ]
        
        return {
            "concept_id": concept.id,
            "concept_name": concept.name,
            "level": concept.level,
            "exercises": exercises,
            "flat_exercises": self._flatten_exercises(exercises),
        }

    def _fallback_correction(
        self,
        exercises: list[dict[str, Any]],
        user_answers: list[str],
    ) -> dict[str, Any]:
        """Return simple fallback correction if LLM fails."""
        results = []
        correct_count = 0
        
        for i, (ex, answer) in enumerate(zip(exercises, user_answers)):
            correct = ex.get("correct_answer", "")
            # Simple string comparison for fallback
            is_correct = answer.strip().lower() == correct.strip().lower() if correct != "(Freie Antwort)" else len(answer.strip()) > 10
            if is_correct:
                correct_count += 1
            
            results.append({
                "level": ex.get("level", "a"),
                "is_correct": is_correct,
                "user_answer": answer,
                "correct_answer": correct,
                "feedback": "Gut!" if is_correct else f"Erwartet: {correct}",
                "points": 10 if is_correct else 3,
            })
        
        total = round((correct_count / len(exercises)) * 10) if exercises else 0
        
        return {
            "results": [],
            "flat_results": results,
            "total_score": total,
            "correct_count": correct_count,
            "total_count": len(exercises),
            "overall_feedback": f"{correct_count} von {len(exercises)} richtig.",
            "focus_areas": [],
        }


__all__ = ["GrammarExerciseService"]
