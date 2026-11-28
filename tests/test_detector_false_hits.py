"""Detectors that told the front page a story used the day's rule when it did not.

Real-data run 2026-11-22 (three seeded learners, six real stories): «Le Papier» said a story
gave occasion to use the place prepositions because it read «9,9 % sur un an», and the qui/que
relatives because it read «L'Académie pense qu'…». The detectors run from the catalogue TSV
(merged from ``app/data/grammar_review``), so the TSV row is what is checked here.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.services.grammar_catalog import detector_matches, parse_detector

TSV = Path(__file__).resolve().parents[1] / "app" / "data" / "grammar_catalog" / "french_core_grammar_v2.tsv"


def _detector(unit_id: str) -> dict[str, str]:
    with TSV.open(encoding="utf-8", newline="") as handle:
        row = next(row for row in csv.DictReader(handle, delimiter="\t") if row["external_id"] == unit_id)
    detector = parse_detector(row["detector"])
    assert detector is not None
    return detector


@pytest.mark.parametrize("text", [
    "Les prix ont augmenté de 9,9 % sur un an.",
    "Le chômage baisse sur un an.",
    "Une hausse de 3 % sur une année.",
    "Le loyer est payé sur 12 mois.",
    "Il gagne 2 000 euros sur dix ans.",
])
def test_a_ratio_or_duration_is_not_a_place(text: str) -> None:
    """D3: «sur un an» is a duration, not where something is."""

    assert not detector_matches(_detector("FR2_A12_PLACE_PREPOSITIONS"), text)


@pytest.mark.parametrize("text", [
    "Les clés sont sur la table.",
    "Il y a un chat sur un mur.",
    "Le livre est sur une chaise.",
    "La pharmacie est en face de la poste.",
    "Le chat dort sous le lit.",
])
def test_a_real_place_still_counts(text: str) -> None:
    assert detector_matches(_detector("FR2_A12_PLACE_PREPOSITIONS"), text)


@pytest.mark.parametrize("text", [
    "L'Académie pense qu'il faut changer la règle.",
    "Le ministre dit que la grève est finie.",
    "Les élèves croient que le bac est facile.",
    "La mairie espère que les touristes viendront.",
    "Le maire sait que la ville est sale.",
    "Mon frère trouve que le film est long.",
    "Le gouvernement annonce qu'il va payer.",
])
def test_que_after_a_verb_of_thinking_or_saying_is_not_a_relative(text: str) -> None:
    """D4: «pense qu'…», «dit que…» open a completive clause, not a relative."""

    assert not detector_matches(_detector("FR2_A22_RELATIVE_QUI_QUE"), text)


@pytest.mark.parametrize("text", [
    "Les gens qui travaillent ici sont gentils.",
    "Le livre que je lis est super.",
    "J'ai une collègue qui parle cinq langues.",
    "Voici l'appartement qu'on a visité samedi.",
    "La femme qui travaille avec moi habite l'appartement que tu as visité.",
])
def test_a_real_relative_still_counts(text: str) -> None:
    assert detector_matches(_detector("FR2_A22_RELATIVE_QUI_QUE"), text)
