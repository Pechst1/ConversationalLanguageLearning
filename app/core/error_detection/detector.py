"""Combine rule-based heuristics with LLM feedback for learner error detection."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

import spacy
from loguru import logger
from spacy.language import Language

from app.config import settings
from app.core.conversation import build_error_detection_prompt, build_error_detection_schema
from app.services.llm_service import LLMResult

from .rules import DetectedError, ErrorRule, build_default_rules


@dataclass
class ErrorDetectionResult:
    """Structured result for an analyzed learner message."""

    errors: List[DetectedError]
    summary: str
    review_vocabulary: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SupportsChatCompletion(Protocol):
    """Protocol satisfied by the LLM service."""

    def generate_chat_completion(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        temperature: float = ...,
        max_tokens: int = ...,
        response_format: Optional[Dict[str, Any]] = ...,
        system_prompt: Optional[str] = ...,
    ) -> LLMResult:
        ...


class ErrorDetector:
    """Run rule-based checks and optionally augment them with LLM analysis."""

    def __init__(
        self,
        *,
        llm_service: Optional[SupportsChatCompletion] = None,
        rules: Optional[Iterable[ErrorRule]] = None,
        nlp: Optional[Language] = None,
    ) -> None:
        self.llm_service = llm_service
        self.rules = list(rules) if rules is not None else build_default_rules()
        self._nlp = nlp or self._load_language_model()

    def _load_language_model(self) -> Language:
        model_name = settings.FRENCH_NLP_MODEL
        try:
            logger.debug("Loading spaCy model", model=model_name)
            return spacy.load(model_name)  # type: ignore[arg-type]
        except Exception:  # pragma: no cover - fallback path
            logger.warning("Falling back to blank French spaCy model", model=model_name)
            return spacy.blank("fr")

    def analyze(
        self,
        learner_message: str,
        *,
        learner_level: str = "B1",
        target_vocabulary: Optional[Sequence[str]] = None,
        use_llm: bool = True,
    ) -> ErrorDetectionResult:
        """Analyze a learner message and return detected issues."""

        doc = self._nlp(learner_message)
        errors: List[DetectedError] = []
        for rule in self.rules:
            rule_errors = rule.apply(doc)
            logger.debug("Rule executed", rule=rule.name, count=len(rule_errors))
            errors.extend(rule_errors)

        summary = "Automated heuristic review only."
        review_vocabulary: List[str] = []
        metadata: Dict[str, Any] = {"rule_error_count": len(errors)}

        if use_llm and self.llm_service:
            llm_result = self._run_llm_analysis(
                learner_message,
                learner_level=learner_level,
                target_vocabulary=target_vocabulary or [],
            )
            if llm_result:
                llm_errors, summary, review_vocabulary, provider_meta = llm_result
                errors.extend(llm_errors)
                metadata.update(provider_meta)
        return ErrorDetectionResult(errors=errors, summary=summary, review_vocabulary=review_vocabulary, metadata=metadata)

    def _run_llm_analysis(
        self,
        learner_message: str,
        *,
        learner_level: str,
        target_vocabulary: Sequence[str],
    ) -> Optional[tuple[List[DetectedError], str, List[str], Dict[str, Any]]]:
        if not self.llm_service:
            return None
        prompt = build_error_detection_prompt(
            learner_message,
            target_vocabulary,
            learner_level,
        )
        # Prefer a broad JSON object mode for maximum provider compatibility.
        system_prompt = (
            "You are a meticulous French writing tutor. Return JSON matching the provided schema "
            "and avoid additional commentary."
        )
        try:
            result = self.llm_service.generate_chat_completion(
                [{"role": "user", "content": prompt}],
                system_prompt=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=600,
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.warning("LLM analysis failed", error=str(exc))
            return None

        parsed = self._parse_llm_response(result)
        if not parsed:
            return None
        errors, summary, review_vocabulary = parsed
        metadata = {
            "llm_provider": result.provider,
            "llm_model": result.model,
            "llm_tokens": result.total_tokens,
            "llm_cost": result.cost,
        }
        return errors, summary, review_vocabulary, metadata

    def _parse_llm_response(
        self, result: LLMResult
    ) -> Optional[tuple[List[DetectedError], str, List[str]]]:
        try:
            payload = json.loads(result.content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON", provider=result.provider)
            return None
        errors_payload = payload.get("errors", [])
        summary_payload = payload.get("summary", {})
        parsed_errors: List[DetectedError] = []
        for item in errors_payload:
            try:
                parsed_errors.append(
                    DetectedError(
                        code="llm_" + item.get("category", "unknown"),
                        message=item.get("explanation", ""),
                        span=item.get("span", ""),
                        suggestion=item.get("suggestion", ""),
                        category=item.get("category", "grammar"),
                        severity=item.get("severity", "medium"),
                        confidence=float(item.get("confidence", 0.5)),
                    )
                )
            except Exception:  # pragma: no cover - skip malformed entries
                logger.debug("Skipping malformed LLM error", item=item)
        summary = summary_payload.get("overall_feedback", "Great job—keep practicing!")
        review_vocabulary = summary_payload.get("review_vocabulary", [])
        if not isinstance(review_vocabulary, list):
            review_vocabulary = []
        return parsed_errors, summary, review_vocabulary


__all__ = ["ErrorDetector", "ErrorDetectionResult", "DetectedError"]
