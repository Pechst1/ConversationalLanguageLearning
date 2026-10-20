"""#239 / #146: no miss ends in the generic «name the trigger» line.

Nightly walk 2026-10-20: every La Forge miss of a German learner printed «Benenne
den Auslöser und wende dann die Zielform an.», whatever the rule. For French and
German the repair line was one fixed sentence (``atelier.generic.repair``); only the
English branch asked the concept. The line a learner reads after a miss now comes
from the unit's own authored slips (✗ wrong → ✓ right), in every language.
"""
from __future__ import annotations

import pytest

from app.db.models.grammar import GrammarConcept
from app.services.atelier import AtelierCorrectionService, AtelierScheduler
from app.services.learner_copy import LEARNER_COPY

#: The placeholders and stand-ins a profile used to print.
FORBIDDEN = ("this unit teaches", "Name the trigger", "Benenne den Auslöser", "Nomme le déclencheur", "Zielform an")


def _v2_concepts() -> list[GrammarConcept]:
    """Every reviewed v2 unit as the (unsaved) concept the Forge hands to the feedback."""

    from app.services.grammar_feedback import _v2_units

    return [
        GrammarConcept(
            external_id=key, name=row["name_en"], level=row["cefr_level"], category=row["category"],
            subskill=row["subskill"], description=row["when_to_use"], core_rule=row["core_rule"],
            main_traps=row["main_traps"], anchor_examples=row["anchor_examples"],
        )
        for key, row in _v2_units().items()
    ]


def _service(db_session, language: str) -> AtelierCorrectionService:
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    return service


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_no_concept_of_the_catalogue_gets_the_generic_repair_line(db_session, language: str) -> None:
    AtelierScheduler(db_session).ensure_catalog()
    service = _service(db_session, language)
    generic = {text for text in LEARNER_COPY["atelier.generic.repair"].values()}
    concepts = [*db_session.query(GrammarConcept).all(), *_v2_concepts()]
    assert len(concepts) > 250
    bad: list[str] = []
    for concept in concepts:
        repair = service._repair_for(concept)
        if not repair.strip() or repair in generic or any(marker in repair for marker in FORBIDDEN):
            bad.append(f"{concept.external_id}: {repair!r}")
    assert bad == [], f"{len(bad)} concepts print a generic repair line, e.g. {bad[:5]}"


def test_a_repair_line_names_the_units_own_slip(db_session) -> None:
    AtelierScheduler(db_session).ensure_catalog()
    concept = next(c for c in _v2_concepts() if c.external_id == "FR2_A11_ETRE")
    for language in ("de", "fr"):
        repair = _service(db_session, language)._repair_for(concept)
        assert "Je es français" in repair and "Je suis français" in repair
