"""Error concept registry for intelligent error grouping.

Error concepts provide a hierarchical grouping of grammar and usage errors
to prevent over-representation of common mistake types in the SRS system.

Hierarchy:
    ErrorConcept (SRS-tracked) → ErrorPattern (stats) → ErrorInstance (individual)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence


@dataclass(frozen=True, slots=True)
class ErrorConcept:
    """A high-level grammar or usage concept that groups related error patterns."""
    
    id: str
    name: str
    name_de: str  # German name for UI
    description: str
    patterns: tuple[str, ...]  # Pattern codes that belong to this concept
    cefr_level: str = "A1"  # When typically learned
    example_correct: str = ""  # Example of correct usage
    example_incorrect: str = ""  # Example of common mistake
    

# Core error concepts with pattern mappings
# Patterns are matched against error_pattern from UserError
ERROR_CONCEPT_REGISTRY: Dict[str, ErrorConcept] = {
    "gender_agreement": ErrorConcept(
        id="gender_agreement",
        name="Gender Agreement",
        name_de="Genus-Übereinstimmung",
        description="Matching articles, adjectives, and participles with noun gender",
        patterns=(
            "gender_agreement", "un_une", "le_la", "adjective_gender",
            "past_participle_gender", "article_mismatch", "gender_mismatch",
            "masculine_feminine", "feminine_masculine",
        ),
        cefr_level="A1",
        example_correct="une femme intelligente",
        example_incorrect="un femme intelligent",
    ),
    "verb_conjugation": ErrorConcept(
        id="verb_conjugation",
        name="Verb Conjugation",
        name_de="Verbkonjugation",
        description="Correct verb forms for person, number, and tense",
        patterns=(
            "verb_conjugation", "present_tense", "passe_compose", "imparfait",
            "futur_simple", "conditionnel", "subjonctif", "subjunctive",
            "irregular_verb", "être_avoir", "verb_form", "conjugation",
        ),
        cefr_level="A1",
        example_correct="je suis, tu es, il est",
        example_incorrect="je est, tu suis",
    ),
    "prepositions": ErrorConcept(
        id="prepositions",
        name="Preposition Usage",
        name_de="Präpositionsgebrauch",
        description="Correct preposition choice in context",
        patterns=(
            "preposition", "prepositions", "a_vs_de", "en_vs_dans",
            "par_vs_pour", "chez_vs_a", "sur_vs_dans", "preposition_choice",
        ),
        cefr_level="A2",
        example_correct="je pense à toi",
        example_incorrect="je pense de toi",
    ),
    "negation": ErrorConcept(
        id="negation",
        name="Negation",
        name_de="Verneinung",
        description="Proper negation structure with ne...pas, ne...jamais, etc.",
        patterns=(
            "negation", "missing_ne", "missing_pas", "double_negation",
            "ne_pas", "ne_plus", "ne_jamais", "negative_structure",
        ),
        cefr_level="A1",
        example_correct="je ne sais pas",
        example_incorrect="je sais pas (informal) / je ne sais",
    ),
    "word_order": ErrorConcept(
        id="word_order",
        name="Word Order",
        name_de="Wortstellung",
        description="Correct placement of adjectives, adverbs, and pronouns",
        patterns=(
            "word_order", "adjective_placement", "adverb_position",
            "pronoun_placement", "bangs_adjectives", "object_pronoun",
        ),
        cefr_level="A2",
        example_correct="une grande maison, je le vois",
        example_incorrect="une maison grande, je vois le",
    ),
    "accents_spelling": ErrorConcept(
        id="accents_spelling",
        name="Accents & Spelling",
        name_de="Akzente & Rechtschreibung",
        description="Correct use of French accents and spelling",
        patterns=(
            "accent", "accents", "spelling", "missing_accent", "wrong_accent",
            "cedilla", "aigu", "grave", "circonflexe", "orthography",
        ),
        cefr_level="A1",
        example_correct="français, café, être",
        example_incorrect="francais, cafe, etre",
    ),
    "articles": ErrorConcept(
        id="articles",
        name="Article Usage",
        name_de="Artikelgebrauch",
        description="When to use definite, indefinite, or partitive articles",
        patterns=(
            "article", "articles", "definite_article", "indefinite_article",
            "partitive", "du_de_la", "missing_article", "extra_article",
        ),
        cefr_level="A1",
        example_correct="j'aime le chocolat, je mange du pain",
        example_incorrect="j'aime chocolat, je mange le pain",
    ),
    "agreement": ErrorConcept(
        id="agreement",
        name="Subject-Verb Agreement",
        name_de="Subjekt-Verb-Kongruenz",
        description="Matching verb forms to subject number and person",
        patterns=(
            "agreement", "subject_verb", "plural_singular", "number_agreement",
        ),
        cefr_level="A1",
        example_correct="les enfants jouent",
        example_incorrect="les enfants joue",
    ),
    "tense_usage": ErrorConcept(
        id="tense_usage",
        name="Tense Usage",
        name_de="Tempusgebrauch",
        description="Choosing the appropriate tense for the context",
        patterns=(
            "tense", "tense_usage", "passe_vs_imparfait", "tense_choice",
            "sequence_of_tenses", "conditional_usage",
        ),
        cefr_level="B1",
        example_correct="Quand j'étais jeune, j'ai visité Paris",
        example_incorrect="Quand j'ai été jeune, je visitais Paris",
    ),
    "pronouns": ErrorConcept(
        id="pronouns",
        name="Pronouns",
        name_de="Pronomen",
        description="Correct pronoun forms and usage",
        patterns=(
            "pronoun", "pronouns", "direct_object", "indirect_object",
            "relative_pronoun", "qui_que", "y_en", "reflexive_pronoun",
        ),
        cefr_level="A2",
        example_correct="je lui parle, j'y vais",
        example_incorrect="je le parle, je vais y",
    ),
}


def get_concept_for_pattern(pattern: str | None) -> ErrorConcept | None:
    """Find the concept that contains this error pattern.
    
    Args:
        pattern: The error_pattern code from UserError
        
    Returns:
        The matching ErrorConcept or None if no match found
    """
    if not pattern:
        return None
        
    pattern_lower = pattern.lower().replace("-", "_").replace(" ", "_")
    
    for concept in ERROR_CONCEPT_REGISTRY.values():
        for p in concept.patterns:
            if p in pattern_lower or pattern_lower in p:
                return concept
    
    return None


def get_concept_for_category(category: str) -> ErrorConcept | None:
    """Fallback: map error category to a default concept.
    
    Args:
        category: The error_category from UserError (e.g. "grammar", "spelling")
        
    Returns:
        A reasonable default concept or None
    """
    category_mapping = {
        "grammar": "gender_agreement",  # Most common grammar error
        "spelling": "accents_spelling",
        "vocabulary": None,  # Vocabulary errors don't fit concept model well
        "punctuation": None,
        "syntax": "word_order",
        "style": None,
    }
    
    concept_id = category_mapping.get(category.lower())
    return ERROR_CONCEPT_REGISTRY.get(concept_id) if concept_id else None


def list_concepts() -> List[ErrorConcept]:
    """Return all registered error concepts."""
    return list(ERROR_CONCEPT_REGISTRY.values())


def get_concept(concept_id: str) -> ErrorConcept | None:
    """Get a concept by ID."""
    return ERROR_CONCEPT_REGISTRY.get(concept_id)


__all__ = [
    "ErrorConcept",
    "ERROR_CONCEPT_REGISTRY",
    "get_concept_for_pattern",
    "get_concept_for_category",
    "list_concepts",
    "get_concept",
]
