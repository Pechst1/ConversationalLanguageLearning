"""#239 / #146: a concept's feedback comes from the concept, never from a stand-in.

Walk 2026-10-19: a miss on «Samedi dernier, ils ont vendus un tableau» printed
«auxiliary or stem + the ending or participle this unit teaches.» The passé
composé unit had no feedback profile of its own, so ``infer_grammar_profile``
matched the word «passé composé» to the generic ``tense_form`` profile, whose
text is a template with a hole in it. Only the v1 core catalogue was consulted
for authored text; the 206 reviewed v2 units (``french_core_grammar_v2.tsv``)
were not, so every one of them got a keyword-matched profile.

The guard: every unit of both catalogues resolves to a profile built from its own
authored fields, and no profile text is a template.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.db.models.grammar import GrammarConcept
from app.services.grammar_feedback import infer_grammar_profile

ROOT = Path(__file__).resolve().parents[1]
CATALOGUES = ("templates/french_core_grammar_v1.tsv", "templates/french_core_grammar_v2.tsv")

#: Words that only a template with a hole in it can print to a learner.
PLACEHOLDERS = (
    "this unit teaches",
    "the requested grammar concept",
    "the requested grammar",
    "the target rule",
    "the target grammar pattern",
)


def _rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for relative in CATALOGUES:
        with (ROOT / relative).open(encoding="utf-8") as source:
            rows.extend(csv.DictReader(source, delimiter="\t"))
    return rows


def _concept(row: dict[str, str]) -> GrammarConcept:
    """The concept row as the catalogue loader stores it."""
    return GrammarConcept(
        external_id=row["external_id"],
        language="fr",
        name=row.get("name_en") or row.get("name") or row["external_id"],
        level=row["cefr_level"],
        category=row.get("category"),
        subskill=row.get("subskill"),
        core_rule=row.get("core_rule"),
        main_traps=row.get("main_traps"),
        anchor_examples=row.get("anchor_examples"),
        exercise_tags=[],
        active=True,
    )


def test_no_unit_of_either_catalogue_gets_a_template_for_a_profile() -> None:
    offenders = []
    for row in _rows():
        profile = infer_grammar_profile(_concept(row))
        text = " ".join(profile.as_dict().values()).lower()
        offenders += [(row["external_id"], hole) for hole in PLACEHOLDERS if hole in text]
    assert offenders == [], f"a learner would be shown a placeholder: {offenders[:5]}"


def test_every_unit_is_taught_with_its_own_authored_pattern() -> None:
    """The pattern line a learner reads after a miss is the unit's, not a family's."""
    wrong = [
        row["external_id"]
        for row in _rows()
        if infer_grammar_profile(_concept(row)).pattern.strip() != row["pattern"].strip()
    ]
    assert wrong == [], f"{len(wrong)} units get a stand-in pattern: {wrong[:8]}"


def _unit(external_id: str) -> GrammarConcept:
    return _concept(next(row for row in _rows() if row["external_id"] == external_id))


def test_passe_compose_with_avoir_has_its_own_profile() -> None:
    profile = infer_grammar_profile(_unit("FR2_A21_PC_AVOIR"))
    assert profile.key == "tense_form"
    assert "ai/as/a/avons/avez/ont" in profile.pattern
    # The repair line is one of the unit's own slips (✗ wrong → ✓ right), not a prompt.
    assert "✗" in profile.repair and "✓" in profile.repair
    assert "participle" in profile.principle.lower()


def test_passe_compose_with_etre_names_the_etre_forms_and_the_agreement() -> None:
    profile = infer_grammar_profile(_unit("FR2_A21_PC_ETRE"))
    assert profile.key == "tense_form"
    assert "suis/es/est/sommes" in profile.pattern
    assert "+ e / + s / + es" in profile.pattern, "the agreement is part of the pattern"
    assert "être" in profile.principle.lower() or "etre" in profile.principle.lower()


def test_a_concept_the_catalogue_does_not_know_never_prints_a_template() -> None:
    stray = GrammarConcept(
        external_id="TEST_UNKNOWN_TENSE", language="fr", name="Passé composé: a stray unit",
        level="A2", category="Tenses", subskill="passe_compose", core_rule=None, exercise_tags=[], active=True,
    )
    profile = infer_grammar_profile(stray)
    text = " ".join(profile.as_dict().values()).lower()
    assert not [hole for hole in PLACEHOLDERS if hole in text], text
