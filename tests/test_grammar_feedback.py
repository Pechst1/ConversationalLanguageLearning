"""Regression tests for shared concept-aware grammar feedback."""
from __future__ import annotations

from uuid import uuid4

from app.db.models.grammar import GrammarConcept
from app.services.grammar_feedback import count_concept_hits, infer_grammar_profile, is_concept_demonstrated


def _concept(**kwargs) -> GrammarConcept:
    return GrammarConcept(
        external_id=kwargs.get("external_id") or f"TEST_{uuid4().hex[:8]}",
        language="fr",
        name=kwargs["name"],
        level=kwargs.get("level", "B1"),
        category=kwargs.get("category"),
        subskill=kwargs.get("subskill"),
        core_rule=kwargs.get("core_rule"),
        main_traps=kwargs.get("main_traps"),
        anchor_examples=kwargs.get("anchor_examples"),
        examples=kwargs.get("examples"),
        exercise_tags=kwargs.get("exercise_tags", []),
        active=True,
    )


def test_relative_pronoun_profile_does_not_become_tense_feedback() -> None:
    concept = _concept(
        name="Relative pronouns: qui, que, dont",
        category="Pronouns",
        core_rule="Use qui, que, ou, or dont according to the role inside the relative clause.",
        exercise_tags=["relative_pronoun", "dont", "de_complement"],
    )

    profile = infer_grammar_profile(concept)

    assert profile.key == "relative_pronoun"
    assert "relative clause" in profile.principle
    assert "imparfait" not in profile.principle.lower()
    assert count_concept_hits(concept, "Le dossier dont je parle reste ici.") >= 1
    assert is_concept_demonstrated(concept, "Le dossier dont je parle reste ici.")


def test_conditional_and_subjunctive_profiles_are_detectable() -> None:
    conditional = _concept(
        name="Conditionnel present",
        core_rule="Use the conditional for polite requests.",
        examples="Je voudrais un cafe.",
    )
    subjunctive = _concept(
        name="Subjonctif present",
        core_rule="Use the subjunctive after expressions of necessity.",
        examples="Il faut que tu viennes.",
    )

    assert infer_grammar_profile(conditional).key == "conditional_mood"
    assert is_concept_demonstrated(conditional, "Je voudrais vous poser une question.")
    assert infer_grammar_profile(subjunctive).key == "mood"
    assert is_concept_demonstrated(subjunctive, "Il faut que tu viennes demain.")
