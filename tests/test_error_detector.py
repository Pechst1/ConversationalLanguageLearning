import json
from typing import List

import spacy

from app.core.error_detection import ErrorDetector
from app.services.llm_service import LLMResult


class StubLLMService:
    def __init__(self, responses: List[LLMResult]):
        self._responses = responses

    def generate_chat_completion(self, *args, **kwargs):
        return self._responses.pop(0)


def test_detector_combines_rule_and_llm_feedback():
    nlp = spacy.blank("fr")
    heuristic_text = "je manger actuellement"
    llm_payload = {
        "errors": [
            {
                "span": "je manger",
                "explanation": "Conjugate the verb after 'je'.",
                "suggestion": "je mange",
                "category": "grammar",
                "severity": "high",
                "confidence": 0.9,
            }
        ],
        "summary": {
            "overall_feedback": "Focus on verb conjugations.",
            "review_vocabulary": ["manger"],
        },
    }
    stub_result = LLMResult(
        provider="openai",
        model="gpt-4o-mini",
        content=json.dumps(llm_payload),
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost=0.002,
        raw_response={},
    )
    detector = ErrorDetector(llm_service=StubLLMService([stub_result]), nlp=nlp)

    result = detector.analyze(heuristic_text, learner_level="A2", target_vocabulary=["manger"])

    assert any(err.code == "verb_conjugation" for err in result.errors)
    assert any(err.code == "llm_grammar" for err in result.errors)
    assert result.summary == "Focus on verb conjugations."
    assert result.review_vocabulary == ["manger"]
    assert result.metadata["llm_provider"] == "openai"


def test_detector_handles_invalid_llm_json_gracefully():
    nlp = spacy.blank("fr")
    stub_result = LLMResult(
        provider="openai",
        model="gpt-4o-mini",
        content="not-json",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost=0.0,
        raw_response={},
    )
    detector = ErrorDetector(llm_service=StubLLMService([stub_result]), nlp=nlp)

    result = detector.analyze("je manger", learner_level="A2", target_vocabulary=[])

    assert all(not err.code.startswith("llm_") for err in result.errors)
