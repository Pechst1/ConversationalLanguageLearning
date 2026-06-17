"""Concept-aware grammar feedback helpers shared across practice modes."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from app.db.models.grammar import GrammarConcept


_STOPWORDS = {
    "about",
    "after",
    "and",
    "avec",
    "before",
    "dans",
    "des",
    "for",
    "from",
    "grammar",
    "into",
    "les",
    "pour",
    "que",
    "qui",
    "rule",
    "sentence",
    "target",
    "the",
    "this",
    "use",
    "uses",
    "using",
    "with",
}

_FRENCH_MARKERS = {
    "je",
    "tu",
    "il",
    "elle",
    "nous",
    "vous",
    "ils",
    "elles",
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "que",
    "qui",
    "dont",
    "dans",
    "pour",
    "avec",
    "est",
    "sont",
}


@dataclass(frozen=True)
class GrammarFeedbackProfile:
    """Reusable language for one grammar concept family."""

    key: str
    label: str
    principle: str
    repair: str
    when: str
    pattern: str
    check: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def normalize_grammar_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[’']", "'", normalized)
    normalized = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ'\s-]", " ", normalized)
    return " ".join(normalized.split())


def iter_grammar_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_grammar_strings(child)
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            yield from iter_grammar_strings(child)


def concept_context_text(concept: GrammarConcept | None) -> str:
    if not concept:
        return ""
    return normalize_grammar_text(
        " ".join(
            iter_grammar_strings(
                [
                    concept.external_id,
                    concept.name,
                    concept.category,
                    concept.subskill,
                    concept.description,
                    concept.core_rule,
                    concept.main_traps,
                    concept.anchor_examples,
                    concept.examples,
                    concept.exercise_tags,
                ]
            )
        )
    )


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(marker in padded for marker in markers)


def _profile(
    key: str,
    label: str,
    principle: str,
    repair: str,
    when: str,
    pattern: str,
    check: str,
) -> GrammarFeedbackProfile:
    return GrammarFeedbackProfile(
        key=key,
        label=label,
        principle=principle,
        repair=repair,
        when=when,
        pattern=pattern,
        check=check,
    )


def infer_grammar_profile(
    concept: GrammarConcept | None = None,
    *,
    task_text: str = "",
    feature: str = "",
    label: str = "",
) -> GrammarFeedbackProfile:
    """Infer a concept family from explicit task text plus catalog metadata."""

    concept_text = concept_context_text(concept)
    task_norm = normalize_grammar_text(task_text)
    combined = f" {task_norm} {concept_text} ".strip()
    external_id = str(getattr(concept, "external_id", "") or "")
    fallback_label = label or (concept.name if concept else "") or feature or "Grammar target"
    fallback_feature = feature or (concept.name if concept else "the requested grammar concept")

    if external_id == "FR_B1_COND_001" or _contains_any(combined, (" si ", " s'il ", "type 1", "future condition", "condition in the present", "real future condition")):
        return _profile(
            "si_present_result_form",
            "Si clause frame",
            "The condition stays in the present, while the result gives the future or imperative consequence.",
            "Keep si with a present-tense condition, then choose the future or imperative consequence.",
            "Use this when something may happen and you want to say what will happen next if it does.",
            "si + present, then future simple or imperative.",
            "If you see si for a real future condition, do not put future simple immediately after si.",
        )
    if external_id == "FR_A2_NEG_001" or _contains_any(combined, (" negation ", " negative ", " ne pas ", " ne plus ", " ne jamais ", " partitive ", " article after negation ", " negated quantity ")):
        return _profile(
            "article_after_negation",
            "Article after negation",
            "A negated quantity changes du, de la, de l', des, un, or une to de or d', except after etre.",
            "Build the negative frame around the verb; after pas, change quantity articles to de/d' unless the verb is etre.",
            "Use this when a quantity becomes negative after ne...pas.",
            "pas + du/de la/de l'/des/un/une -> pas de/d', except with etre.",
            "After pas, check whether the original article expressed a quantity.",
        )
    if external_id == "FR_B1_TENSE_001" or _contains_any(combined, (" tense ", " temps ", " aspect ", " imparfait ", " passe compose ", " passé composé ", " completed event ", " bounded event ", " ongoing background ")):
        return _profile(
            "tense_aspect",
            "Background vs event",
            "The verb form has to show whether the action is background, habit, state, or a bounded completed event.",
            "Ask whether each verb sets the scene or advances it before choosing the tense.",
            "Use this when a sentence combines scene-setting background with completed events.",
            "imparfait = background/habit/state; passe compose = bounded completed event.",
            "Ask whether the action is an ongoing setting or a completed event.",
        )
    if _contains_any(combined, (" conditionnel ", " conditional ", " polite request ", " hypothetical ")):
        return _profile(
            "conditional_mood",
            "Conditional",
            "The conditional form presents the action as polite, hypothetical, or dependent on a condition.",
            "Check whether the sentence is making a polite request, imagining a result, or stating a hypothetical action.",
            "Use this for polite requests and imagined or conditional results.",
            "conditional stem + -ais/-ais/-ait/-ions/-iez/-aient.",
            "Look for the polite or hypothetical force before choosing the verb ending.",
        )
    if _contains_any(combined, (" subjonctif ", " subjunctive ", " il faut que ", " bien que ", " avant que ", " pour que ")):
        return _profile(
            "mood",
            "Subjunctive trigger",
            "The trigger expression asks for a subjunctive form in the dependent clause.",
            "Find the trigger expression, then choose the verb mood it requires.",
            "Use this after triggers of necessity, doubt, emotion, purpose, or concession.",
            "trigger + que + subjunctive.",
            "Check the trigger before deciding between indicative and subjunctive.",
        )
    if _contains_any(combined, (" relative ", " relatif ", " relative pronoun ", " pronom relatif ", " dont ", " lequel ", " laquelle ", " lesquelles ")):
        return _profile(
            "relative_pronoun",
            "Relative pronoun",
            "The pronoun has to match its role in the relative clause: subject, object, place, possession, or de-complement.",
            "Identify the missing role in the second clause before choosing the relative pronoun.",
            "Use this to connect two clauses without repeating the noun.",
            "qui/que/ou/dont/lequel according to the role inside the relative clause.",
            "Ask what job the missing word does in the second clause.",
        )
    if _contains_any(combined, (" pronoun ", " pronom ", " clitic ", " object pronoun ", " y ", " en ", " lui ", " leur ")):
        return _profile(
            "pronoun_choice",
            "Pronoun choice",
            "The pronoun has to replace the right noun phrase and sit in the correct position around the verb.",
            "Name what the pronoun replaces, then choose the matching French pronoun.",
            "Use this when a noun phrase is replaced instead of repeated.",
            "direct, indirect, y, en, reflexive, or stressed pronoun according to the complement.",
            "Check what the pronoun replaces before checking word order.",
        )
    if _contains_any(combined, (" determiner ", " article ", " definite ", " indefinite ", " partitive ", " possessive ", " demonstrative ")):
        return _profile(
            "determiner",
            "Determiner choice",
            "The determiner has to match the noun phrase and the meaning: specific, nonspecific, quantity, possession, or pointing.",
            "Check the noun and the intended meaning before choosing the determiner.",
            "Use this when a noun needs an article, possessive, demonstrative, or quantity marker.",
            "determiner + noun, with gender/number and meaning aligned.",
            "Ask whether the noun is specific, nonspecific, a quantity, possessed, or being pointed out.",
        )
    if _contains_any(combined, (" agreement ", " accord ", " gender ", " number ", " genre ", " nombre ", " adjective ", " participle ")):
        return _profile(
            "agreement",
            "Agreement",
            "The form has to agree with its controller in gender, number, or person.",
            "Find the word controlling the agreement, then match the ending.",
            "Use this when a form changes to match a noun, subject, or object.",
            "controller + agreeing determiner/adjective/verb/participle.",
            "Find the controller before checking the ending.",
        )
    if _contains_any(combined, (" preposition ", " preposition ", " a_vs_de ", " en_vs_dans ", " chez ", " depuis ", " pendant ")):
        return _profile(
            "preposition",
            "Preposition choice",
            "The preposition has to fit the verb, place, time, or complement that follows.",
            "Check whether the phrase needs direction, location, source, duration, possession, or a verb-governed preposition.",
            "Use this when a verb, place, time expression, or complement requires a specific linking word.",
            "verb/place/time expression + required preposition.",
            "Ask what relation the preposition expresses before choosing it.",
        )
    if _contains_any(combined, (" comparison ", " comparative ", " superlative ", " plus ", " moins ", " autant ", " aussi ")):
        return _profile(
            "comparison",
            "Comparison",
            "The comparison marker has to match whether you mean more, less, as much, or the most.",
            "Choose the comparison frame first, then complete the adjective, noun, adverb, or verb phrase.",
            "Use this when comparing degree, quantity, manner, or rank.",
            "plus/moins/aussi/autant... que, or superlative frame.",
            "Check what is being compared and whether it is equality or inequality.",
        )
    return _profile(
        "grammar_target",
        str(fallback_label)[:120],
        f"The answer has to make the requested grammar relation visible: {fallback_feature}.",
        "Use the task prompt and the concept rule to choose the exact French form.",
        "Use this when the sentence context calls for this grammar concept.",
        getattr(concept, "core_rule", None) or "Match the form to the target rule.",
        "Name the trigger, controller, or sentence role first, then choose the form.",
    )


def profile_search_terms(key: str) -> tuple[str, ...]:
    return {
        "si_present_result_form": ("si", "condition", "future", "futur"),
        "article_after_negation": ("negation", "negative", "partitive", "article"),
        "tense_aspect": ("tense", "temps", "aspect", "imparfait", "passe"),
        "conditional_mood": ("conditionnel", "conditional", "hypothetical"),
        "mood": ("subjunctive", "subjonctif", "mood"),
        "relative_pronoun": ("relative", "relatif", "dont", "lequel"),
        "pronoun_choice": ("pronoun", "pronom", "clitic", "y_en"),
        "determiner": ("determiner", "article", "partitive", "possessive"),
        "agreement": ("agreement", "accord", "gender", "number", "genre", "nombre"),
        "preposition": ("preposition", "chez", "depuis", "pendant"),
        "comparison": ("comparison", "comparative", "superlative", "plus", "moins"),
    }.get(key, ())


def _text_tokens(text: Any) -> set[str]:
    return set(re.findall(r"[a-zàâçéèêëîïôûùüÿñæœ']+", normalize_grammar_text(text)))


def _content_markers(concept: GrammarConcept | None) -> set[str]:
    markers = {
        token
        for token in _text_tokens(concept_context_text(concept))
        if len(token) >= 4 and token not in _STOPWORDS
    }
    return markers


def _contains_future_simple(text: str) -> bool:
    return bool(re.search(r"\b\w+(rai|ras|ra|rons|rez|ront)\b", normalize_grammar_text(text)))


def _contains_conditionnel_present(text: str) -> bool:
    return bool(re.search(r"\b\w+r(?:ais|ait|ions|iez|aient)\b", normalize_grammar_text(text)))


def _contains_subjunctive_form(text: str) -> bool:
    tokens = _text_tokens(text)
    common_subjunctive = {
        "sois",
        "soit",
        "soyons",
        "soyez",
        "soient",
        "aie",
        "aies",
        "ait",
        "ayons",
        "ayez",
        "aient",
        "fasse",
        "fasses",
        "fassions",
        "fassiez",
        "fassent",
        "puisse",
        "puisses",
        "puissions",
        "puissiez",
        "puissent",
        "aille",
        "ailles",
        "allions",
        "alliez",
        "aillent",
        "vienne",
        "viennes",
        "venions",
        "veniez",
        "viennent",
    }
    return bool({"que", "qu"}.intersection(tokens) and common_subjunctive.intersection(tokens))


def count_concept_hits(concept: GrammarConcept | None, text: str, *, task_text: str = "") -> int:
    normalized = normalize_grammar_text(text)
    tokens = _text_tokens(normalized)
    if not normalized.strip():
        return 0
    profile = infer_grammar_profile(concept, task_text=task_text)
    if profile.key == "si_present_result_form":
        clauses = re.findall(r"\b(?:si\s+|s')[^.!?;,]+[, ]+[^.!?;]+", normalized)
        return sum(1 for clause in clauses if _contains_future_simple(clause) or re.search(r"\b(prends|prenez|mange|mangez|allez|viens|venez|fais|faites)\b", clause))
    if profile.key == "tense_aspect":
        imparfait = re.findall(r"\b\w+(ais|ait|ions|iez|aient)\b", normalized)
        passe = re.findall(r"\b(ai|as|a|avons|avez|ont|suis|es|est|sommes|etes|sont)\s+\w+", normalized)
        return min(len(imparfait), len(passe)) if ("imparfait" in concept_context_text(concept) or "passe" in concept_context_text(concept)) else len(imparfait) + len(passe)
    if profile.key == "conditional_mood":
        return int(_contains_conditionnel_present(normalized) or bool(tokens & {"voudrais", "pourrais", "devrais", "aimerais"}))
    if profile.key == "article_after_negation":
        negation_frame = r"\b(?:ne\s+\w+|n'\w+)\s+[^.!?;]*\bpas\s+d(?:e\b|')"
        return len(re.findall(negation_frame, normalized))
    if profile.key == "mood":
        return int(_contains_subjunctive_form(normalized))
    if profile.key == "relative_pronoun":
        return len(tokens & {"qui", "que", "qu", "dont", "ou", "lequel", "laquelle", "lesquels", "lesquelles"})
    if profile.key == "pronoun_choice":
        return len(tokens & {"me", "te", "se", "nous", "vous", "le", "la", "les", "lui", "leur", "y", "en"})
    if profile.key == "determiner":
        return len(tokens & {"le", "la", "les", "un", "une", "des", "du", "de", "mon", "ma", "mes", "ce", "cette", "ces"})
    if profile.key == "agreement":
        return int(bool(tokens & {"le", "la", "les", "un", "une", "des", "ces", "mes", "sont", "sommes"} or re.search(r"\b\w+(e|es|s|ent)\b", normalized)))
    if profile.key == "preposition":
        return len(tokens & {"a", "de", "en", "dans", "chez", "sur", "pour", "par", "avec", "depuis", "pendant"})
    if profile.key == "comparison":
        return len(tokens & {"plus", "moins", "autant", "aussi", "meilleur", "mieux", "pire"})
    markers = _content_markers(concept)
    overlap = markers & tokens
    if overlap:
        return 1
    return int(len(tokens) >= 6 and bool(tokens & _FRENCH_MARKERS))


def is_concept_demonstrated(
    concept: GrammarConcept | None,
    text: str,
    *,
    prompt: str = "",
    correct_answer: str = "",
) -> bool:
    if not concept or len(_text_tokens(text)) < 3:
        return False
    if count_concept_hits(concept, text, task_text=f"{prompt} {correct_answer}") > 0:
        return True
    markers = _content_markers(concept) | _text_tokens(prompt) | _text_tokens(correct_answer)
    meaningful = {token for token in markers if len(token) >= 4 and token not in _STOPWORDS}
    return bool(meaningful & _text_tokens(text))


__all__ = [
    "GrammarFeedbackProfile",
    "concept_context_text",
    "count_concept_hits",
    "infer_grammar_profile",
    "is_concept_demonstrated",
    "iter_grammar_strings",
    "normalize_grammar_text",
    "profile_search_terms",
]
