"""#196 / #144 / #146: no fallback classify item carries a hard-coded English label.

Walk 2026-10-21 (French chrome): La Forge offered «Pronoun choice» and «different
grammar role» for «Tu peux me le prêter demain ?». The fallback set stored English
labels for every grammar profile, and the generic pair made the item trivial: every
sentence's answer was the profile label. Labels now come from ``learner_copy`` (the
stored label stays the answer key, ``label_l10n`` is what the learner reads in the
chrome language), and a unit without authored labels is sorted *right or wrong*
with the unit's own ✗/✓ pairs, which can actually be wrong for the sentence.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from app.db.models.grammar import GrammarConcept
from app.services import item_bank as ib
from app.services.atelier import FALLBACK_CONCEPTS, AtelierExerciseGenerator
from app.services.grammar_feedback import infer_grammar_profile
from app.services.learner_copy import LEARNER_COPY

LANGUAGES = ("en", "de", "fr")
DATA = Path(__file__).resolve().parents[1] / "app" / "data" / "grammar_review"


def _unit_concepts() -> list[GrammarConcept]:
    concepts: list[GrammarConcept] = []
    for number, path in enumerate(sorted(glob.glob(str(DATA / "units_*.json")))):
        rows = json.loads(Path(path).read_text(encoding="utf-8"))["units"]
        for index, row in enumerate(rows):
            if not isinstance(row, dict) or "external_id" not in row:
                continue
            concepts.append(
                GrammarConcept(
                    id=number * 1000 + index + 1,
                    external_id=row["external_id"],
                    name=row.get("name_en") or row["external_id"],
                    level=row.get("cefr_level") or "B1",
                    category=row.get("category") or "",
                    subskill=row.get("subskill") or "",
                    core_rule=row.get("core_rule") or "",
                    main_traps=row.get("main_traps") or "",
                    anchor_examples=row.get("anchor_examples") or "",
                    exercise_tags=row.get("exercise_tags") or "",
                )
            )
    for row in FALLBACK_CONCEPTS:
        concepts.append(
            GrammarConcept(
                id=9000 + len(concepts),
                external_id=row["external_id"],
                name=row["name"],
                level=row.get("level") or "B1",
                category=row.get("category") or "",
                subskill=row.get("subskill") or "",
                core_rule=row.get("core_rule") or "",
                main_traps=row.get("main_traps") or "",
            )
        )
    return concepts


def _one_concept_per_profile(per_profile: int = 2) -> list[GrammarConcept]:
    chosen: dict[str, list[GrammarConcept]] = {}
    for concept in _unit_concepts():
        key = infer_grammar_profile(concept).key
        if len(chosen.setdefault(key, [])) < per_profile:
            chosen[key].append(concept)
    return [concept for group in chosen.values() for concept in group]


def _copy_texts(language: str) -> set[str]:
    texts = {row[language] for row in LEARNER_COPY.values() if language in row}
    texts.update(ib.JUDGEMENT_LABELS[language].values())
    return texts


def test_the_check_covers_every_grammar_profile() -> None:
    keys = {infer_grammar_profile(concept).key for concept in _one_concept_per_profile()}
    assert {"pronoun_choice", "article_after_negation", "tense_aspect", "si_present_result_form"} <= keys
    assert len(keys) >= 8, keys


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_fallback_classify_label_is_localized_copy(language: str) -> None:
    generator = AtelierExerciseGenerator(None)
    missing: list[str] = []
    checked = 0
    for concept in _one_concept_per_profile():
        items = generator._fallback_classify_items(concept, prefix="t")
        assert items, concept.external_id
        for raw in items:
            item = ib.with_goal(raw, language)
            table = (item.get("label_l10n") or {}).get(language) or {}
            for label in item["labels"]:
                checked += 1
                shown = table.get(label)
                if not shown:
                    missing.append(f"{concept.external_id} [{infer_grammar_profile(concept).key}]: {label!r} has no {language} text")
                elif shown not in _copy_texts(language):
                    missing.append(f"{concept.external_id}: {shown!r} is not localized copy")
    assert checked > 30
    assert missing == [], "\n".join(missing[:12])


def test_a_fallback_classify_set_offers_labels_that_can_be_wrong() -> None:
    generator = AtelierExerciseGenerator(None)
    for concept in _one_concept_per_profile():
        items = generator._fallback_classify_items(concept, prefix="t")
        for item in items:
            assert len(set(item["labels"])) >= 2 and item["correct_label"] in item["labels"], item
            assert "different grammar role" not in item["labels"], item
        if len(items) >= 2:
            # Not every sentence has the same answer: the right button moves.
            assert len({item["correct_label"] for item in items}) >= 2, (
                concept.external_id,
                [(item["prompt"], item["correct_label"]) for item in items],
            )


def test_the_whole_fallback_set_still_validates_for_every_profile(db_session) -> None:
    generator = AtelierExerciseGenerator(db_session)
    for concept in _one_concept_per_profile(per_profile=1):
        payload = generator._fallback_payload(concept)
        assert generator._payload_validation_errors(payload, concept=concept) == [], concept.external_id


def test_a_fallback_judgement_is_graded_like_every_judgement() -> None:
    from app.services.atelier import AtelierCorrectionService

    concept = next(c for c in _unit_concepts() if c.external_id == "FR2_B11_DOUBLE_PRONOUNS")
    items = AtelierExerciseGenerator(None)._fallback_classify_items(concept, prefix="t")
    service = AtelierCorrectionService(None)
    service.explanation_language = "fr"
    for item in items:
        right = service._correct_recognize(concept, "classify", {"items": [item]}, {"answers": {item["id"]: item["correct_label"]}})
        assert right["verdict"] == "correct", item
        other = next(label for label in item["labels"] if label != item["correct_label"])
        miss = service._correct_recognize(concept, "classify", {"items": [item]}, {"answers": {item["id"]: other}})
        assert miss["verdict"] == "incorrect" and miss["errata"], item


def test_the_pronoun_unit_is_sorted_right_or_wrong_in_the_learners_language() -> None:
    concept = next(c for c in _unit_concepts() if c.external_id == "FR2_B11_DOUBLE_PRONOUNS")
    items = AtelierExerciseGenerator(None)._fallback_classify_items(concept, prefix="t")
    wrong = [item for item in items if item["correct_label"] == "À corriger"]
    assert wrong, "a sentence that is wrong is in the set"
    shown = ib.with_goal(wrong[0], "fr")
    assert shown["label_l10n"]["fr"]["À corriger"] and "Pronoun" not in str(shown["labels"])
    # A wrong sentence shows its right form once sorted, like every judgement (follow_up_key).
    assert wrong[0]["follow_up_key"]["corrected_fr"]
