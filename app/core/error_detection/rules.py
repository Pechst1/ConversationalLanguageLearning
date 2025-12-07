"""Rule-based error detection heuristics for French learner text."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from spacy.tokens import Doc, Token


@dataclass
class DetectedError:
    """Representation of a detected learner error."""

    code: str
    message: str
    span: str
    suggestion: str
    category: str
    severity: str
    confidence: float


class ErrorRule(Protocol):
    """Interface shared by rule-based error detectors."""

    name: str

    def apply(self, doc: Doc) -> List[DetectedError]:  # pragma: no cover - interface definition
        """Inspect the document and return any detected errors."""


def _token_gender(token: Token) -> str | None:
    """Return the gender inferred from spaCy morphology or heuristics."""

    gender = token.morph.get("Gender")
    if gender:
        if "Fem" in gender:
            return "feminine"
        if "Masc" in gender:
            return "masculine"
    text = token.text.lower()
    feminine_endings = ("e", "ion", "té", "ure", "ade", "esse", "ice", "ode")
    masculine_endings = ("age", "eau", "isme", "ment", "oir", "teur", "ier", "on", "et")
    if text.endswith(feminine_endings):
        return "feminine"
    if text.endswith(masculine_endings):
        return "masculine"
    return None


@dataclass
class ArticleNounAgreementRule:
    """Detect simple article/noun gender mismatches."""

    name: str = "article_noun_agreement"

    feminine_articles: Iterable[str] = ("la", "une", "cette", "sa")
    masculine_articles: Iterable[str] = ("le", "un", "ce", "son")

    def apply(self, doc: Doc) -> List[DetectedError]:
        errors: List[DetectedError] = []
        tokens = list(doc)
        for index, token in enumerate(tokens[:-1]):
            article = token.text.lower()
            noun = tokens[index + 1]
            noun_gender = _token_gender(noun)
            if article in self.feminine_articles:
                if noun_gender == "masculine":
                    errors.append(
                        DetectedError(
                            code=self.name,
                            message="Possible feminine article used with masculine noun.",
                            span=f"{token.text} {noun.text}",
                            suggestion=f"le {noun.text}",
                            category="grammar",
                            severity="medium",
                            confidence=0.7,
                        )
                    )
            elif article in self.masculine_articles:
                if noun_gender == "feminine":
                    errors.append(
                        DetectedError(
                            code=self.name,
                            message="Possible masculine article used with feminine noun.",
                            span=f"{token.text} {noun.text}",
                            suggestion=f"la {noun.text}",
                            category="grammar",
                            severity="medium",
                            confidence=0.7,
                        )
                    )
        return errors


@dataclass
class VerbConjugationRule:
    """Identify infinitive verbs following personal pronouns."""

    name: str = "verb_conjugation"

    pronoun_expected_endings = {
        "je": ("e", "s", "x"),
        "tu": ("es", "x"),
        "il": ("e", "t"),
        "elle": ("e", "t"),
        "on": ("e", "t"),
        "nous": ("ons",),
        "vous": ("ez",),
        "ils": ("ent",),
        "elles": ("ent",),
    }

    def apply(self, doc: Doc) -> List[DetectedError]:
        errors: List[DetectedError] = []
        tokens = list(doc)
        for index, token in enumerate(tokens[:-1]):
            pronoun = token.text.lower()
            if pronoun not in self.pronoun_expected_endings:
                continue
            candidate = tokens[index + 1]
            if candidate.pos_ and candidate.pos_ not in {"VERB", "AUX"}:
                continue
            if candidate.tag_ and candidate.tag_ not in {"VERB", "AUX"}:
                continue
            lemma = candidate.lemma_.lower() if candidate.lemma_ else ""
            text = candidate.text.lower()
            if lemma and lemma != text and not lemma.endswith("er"):
                continue
            if text in {"suis", "ai", "vais", "fais"}:
                continue
            if text.endswith("er") or text.endswith("re") or text.endswith("ir"):
                errors.append(
                    DetectedError(
                        code=self.name,
                        message="Verb appears to be in infinitive form after pronoun.",
                        span=f"{token.text} {candidate.text}",
                        suggestion=f"{token.text} {candidate.text}e",
                        category="grammar",
                        severity="high",
                        confidence=0.6,
                    )
                )
                continue
            expected_endings = self.pronoun_expected_endings[pronoun]
            if not text.endswith(expected_endings):
                errors.append(
                    DetectedError(
                        code=self.name,
                        message="Verb ending may not match subject pronoun.",
                        span=f"{token.text} {candidate.text}",
                        suggestion=f"{token.text} {candidate.lemma_ or candidate.text}",
                        category="grammar",
                        severity="medium",
                        confidence=0.55,
                    )
                )
        return errors


@dataclass
class FalseFriendRule:
    """Highlight common English/French false friends."""

    name: str = "false_friend"

    false_friends: dict[str, str] = None

    def __post_init__(self) -> None:
        if self.false_friends is None:
            self.false_friends = {
                "actuellement": "Use 'en ce moment' for 'currently'.",
                "librairie": "Means 'bookshop'; use 'bibliothèque' for 'library'.",
                "sensible": "Means 'sensitive'; use 'raisonnable' for 'sensible'.",
                "déception": "Means 'disappointment'; use 'tromperie' for 'deception'.",
            }

    def apply(self, doc: Doc) -> List[DetectedError]:
        errors: List[DetectedError] = []
        for token in doc:
            explanation = self.false_friends.get(token.text.lower())
            if not explanation:
                continue
            suggestion_hint = None
            if ";" in explanation:
                suggestion_hint = explanation.split(";", 1)[-1].strip()
            suggestion = suggestion_hint or "Révisez l'usage correct de ce mot."
            errors.append(
                DetectedError(
                    code=self.name,
                    message=explanation,
                    span=token.text,
                    suggestion=suggestion,
                    category="vocabulary",
                    severity="low",
                    confidence=0.9,
                )
            )
        return errors


def build_default_rules() -> List[ErrorRule]:
    """Return the default rule set for the detector."""

    return [
        ArticleNounAgreementRule(),
        VerbConjugationRule(),
        FalseFriendRule(),
    ]


__all__ = [
    "ArticleNounAgreementRule",
    "DetectedError",
    "ErrorRule",
    "FalseFriendRule",
    "VerbConjugationRule",
    "build_default_rules",
]
