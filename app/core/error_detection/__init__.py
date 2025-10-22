"""Error detection utilities combining rule-based heuristics with LLM feedback."""

from .detector import ErrorDetectionResult, ErrorDetector
from .rules import (
    ArticleNounAgreementRule,
    DetectedError,
    ErrorRule,
    FalseFriendRule,
    VerbConjugationRule,
    build_default_rules,
)

__all__ = [
    "ArticleNounAgreementRule",
    "DetectedError",
    "ErrorDetectionResult",
    "ErrorDetector",
    "ErrorRule",
    "FalseFriendRule",
    "VerbConjugationRule",
    "build_default_rules",
]
