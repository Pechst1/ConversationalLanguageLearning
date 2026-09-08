"""Combine rule-based heuristics with LLM feedback for learner error detection."""
from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from loguru import logger

from app.config import settings
from app.core.conversation import build_error_detection_prompt
from app.services.learner_copy import learner_text
from app.services.llm_service import LLMResult

from .rules import DetectedError, ErrorRule, build_default_rules


@dataclass
class ErrorDetectionResult:
    """Structured result for an analyzed learner message."""

    errors: list[DetectedError]
    summary: str
    review_vocabulary: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SupportsChatCompletion(Protocol):
    """Protocol satisfied by the LLM service."""

    def generate_chat_completion(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = ...,
        max_tokens: int = ...,
        response_format: dict[str, Any] | None = ...,
        system_prompt: str | None = ...,
    ) -> LLMResult:
        ...


class ErrorDetector:
    """Run rule-based checks and optionally augment them with LLM analysis."""

    def __init__(
        self,
        *,
        llm_service: SupportsChatCompletion | None = None,
        rules: Iterable[ErrorRule] | None = None,
        nlp: Any | None = None,
        explanation_language: str | None = None,
    ) -> None:
        self.llm_service = llm_service
        # Explanations follow the learner's native language (contract: instruction
        # in L1). The old prompt hardcoded German for every learner.
        self.explanation_language = (explanation_language or "en").strip().lower()[:2] or "en"
        self.rules = list(rules) if rules is not None else build_default_rules()
        self._nlp = nlp or self._load_language_model()

    def _load_language_model(self) -> Any:
        try:
            import spacy
            model_name = settings.FRENCH_NLP_MODEL
            try:
                logger.debug("Loading spaCy model", model=model_name)
                return spacy.load(model_name)  # type: ignore[arg-type]
            except Exception:  # pragma: no cover - fallback path
                logger.warning("Falling back to blank French spaCy model", model=model_name)
                return spacy.blank("fr")
        except Exception as e:
            logger.error(f"Failed to import/load spaCy: {e}")
            # Return a dummy object that implements __call__ to return an empty doc-like object
            class DummyDoc:
                def __iter__(self): return iter([])
                def __len__(self): return 0
            class DummyNLP:
                def __call__(self, text): return DummyDoc()
            return DummyNLP()

    def analyze(
        self,
        learner_message: str,
        *,
        learner_level: str = "B1",
        target_vocabulary: Sequence[str] | None = None,
        use_llm: bool = True,
        explanation_language: str | None = None,
    ) -> ErrorDetectionResult:
        """Analyze a learner message and return detected issues."""

        # The learner's language can arrive per-call (a shared detector serves
        # several learners) — resolve it before the rules render their prose.
        if explanation_language:
            self.explanation_language = explanation_language.strip().lower()[:2] or self.explanation_language

        doc = self._nlp(learner_message)
        errors: list[DetectedError] = []
        for rule in self.rules:
            rule_errors = rule.apply(doc)
            logger.debug("Rule executed", rule=rule.name, count=len(rule_errors))
            errors.extend(self._localized(rule_errors))

        summary = learner_text("detect.summary_heuristic_only", self.explanation_language)
        review_vocabulary: list[str] = []
        metadata: dict[str, Any] = {"rule_error_count": len(errors)}

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

    def _localized(self, errors: list[DetectedError]) -> list[DetectedError]:
        """Render the deterministic rule prose in the learner's own language.

        Only rows that name a `message_key` are touched: a provider-authored
        message is already written in the learner's language by the prompt.
        """
        for error in errors:
            if error.message_key:
                error.message = learner_text(error.message_key, self.explanation_language)
        return errors

    _EXPLANATION_LANGUAGE_NAMES = {
        "en": "ENGLISH",
        "de": "GERMAN (Deutsch)",
        "fr": "FRENCH",
        "es": "SPANISH",
        "it": "ITALIAN",
        "pt": "PORTUGUESE",
        "nl": "DUTCH",
    }

    def _explanation_language_name(self) -> str:
        return self._EXPLANATION_LANGUAGE_NAMES.get(self.explanation_language, "ENGLISH")

    def _run_llm_analysis(
        self,
        learner_message: str,
        *,
        learner_level: str,
        target_vocabulary: Sequence[str],
    ) -> tuple[list[DetectedError], str, list[str], dict[str, Any]] | None:
        if not self.llm_service:
            return None
        prompt = build_error_detection_prompt(
            learner_message,
            target_vocabulary,
            learner_level,
        )
        # Prefer a broad JSON object mode for maximum provider compatibility.
        system_prompt = (
            "You are an expert French grammar and language teacher analyzing learner text for errors. "
            "Your primary goal is to help learners improve by identifying ALL grammatical mistakes, "
            "especially gender agreement (le/la, un/une), verb conjugation, and article usage. "
            "These errors are critical for French learners even if the text is understandable. "
            f"IMPORTANT: Write all explanations in {self._explanation_language_name()} since that is the "
            "learner's native language. Quote the French fragments verbatim. "
            "Return valid JSON matching the provided schema. Do not include any text outside the JSON."
        )
        try:
            # Use the dedicated error detection method which uses a stronger model
            if hasattr(self.llm_service, 'generate_error_detection'):
                result = self.llm_service.generate_error_detection(
                    [{"role": "user", "content": prompt}],
                    system_prompt=system_prompt,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=800,
                )
            else:
                # Fallback for testing/mocking
                result = self.llm_service.generate_chat_completion(
                    [{"role": "user", "content": prompt}],
                    system_prompt=system_prompt,
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=800,
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
    ) -> tuple[list[DetectedError], str, list[str]] | None:
        try:
            payload = json.loads(result.content)
        except json.JSONDecodeError:
            logger.warning("LLM returned invalid JSON", provider=result.provider)
            return None
        errors_payload = payload.get("errors", [])
        summary_payload = payload.get("summary", {})
        parsed_errors: list[DetectedError] = []
        for item in errors_payload:
            try:
                category = item.get("category", "grammar")
                subcategory = item.get("subcategory")
                
                # Use subcategory for code if available, otherwise fallback to category
                code = subcategory if subcategory else f"llm_{category}"
                
                parsed_errors.append(
                    DetectedError(
                        code=code,
                        message=item.get("explanation", ""),
                        span=item.get("span", ""),
                        suggestion=item.get("suggestion", ""),
                        category=category,
                        severity=item.get("severity", "medium"),
                        confidence=float(item.get("confidence", 0.5)),
                        subcategory=subcategory,
                    )
                )
            except Exception:  # pragma: no cover - skip malformed entries
                logger.debug("Skipping malformed LLM error", item=item)
        summary = summary_payload.get("overall_feedback") or learner_text(
            "detect.summary_default", self.explanation_language
        )
        review_vocabulary = summary_payload.get("review_vocabulary", [])
        if not isinstance(review_vocabulary, list):
            review_vocabulary = []
        return parsed_errors, summary, review_vocabulary


__all__ = ["ErrorDetector", "ErrorDetectionResult", "DetectedError"]
