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


def _bare_concepts() -> list[GrammarConcept]:
    """Units with no authored pairs and a generic profile. The first attempt (#275, review of
    21 Oct) returned two items for these and the whole fallback payload failed validation."""

    return [
        GrammarConcept(
            id=99001,
            external_id="TEST_X",
            name="Gender and number basics",
            level="A2",
            core_rule="Adjectives and participles agree in gender and number with what they describe.",
            exercise_tags=["agreement"],
        ),
        GrammarConcept(id=99002, external_id="TEST_Y", name="Misc", level="B1", core_rule="A rule."),
    ]


def test_a_fallback_classify_set_is_always_three_items_even_without_authored_pairs() -> None:
    generator = AtelierExerciseGenerator(None)
    for concept in [*_bare_concepts(), *_one_concept_per_profile()]:
        items = generator._fallback_classify_items(concept, prefix="t")
        assert len(items) == 3, (concept.external_id, [item["prompt"] for item in items])
        assert len({item["id"] for item in items}) == 3
        for item in items:
            assert "different grammar role" not in item["labels"]


def test_the_bare_units_fallback_payload_validates(db_session) -> None:
    generator = AtelierExerciseGenerator(db_session)
    for concept in _bare_concepts():
        payload = generator._fallback_payload(concept)
        assert generator._payload_validation_errors(payload, concept=concept) == [], concept.external_id


def test_a_set_stored_before_the_fix_is_still_shown_in_the_learners_language() -> None:
    """The English pair the 25 Oct walk saw is already in cached sets."""

    table = ib.label_table(["Pronoun choice", "different grammar role"])
    assert table["fr"]["different grammar role"] and table["fr"]["Pronoun choice"]
    assert table["de"]["different grammar role"] != "different grammar role"
    assert table["fr"]["Pronoun choice"] != "Pronoun choice"


# --------------------------------------------------------------------------- #
# #447 / #448 / #146: the fallback pools are drawn from the day's concept
# --------------------------------------------------------------------------- #
#
# Walk 2026-11-01 (b1-fr-chrome): «Pour, sans, avant de + infinitif» was served
# «Il habite à cette rue» → «dans» (a place preposition), «Deux pronoms ensemble»
# was served single-pronoun swaps, and both sets offered «prêters», «encores»,
# «peuxs», «J'économises» and a fixed «autrement». The rows were filed by the
# concept's *family* («preposition», «pronoun_choice»), and the wrong options were
# `token + "s"`. A row now serves a concept only when the concept's own detector
# recognises its form in it, and a wrong option is a real French word.


def _detector(concept: GrammarConcept) -> list[str]:
    from app.services.grammar_units import regex_patterns, unit_detectors

    return regex_patterns(unit_detectors(concept))


def _spans(concept: GrammarConcept, sentence: str) -> list[tuple[int, int]]:
    from app.services.grammar_units import detector_spans

    return detector_spans(_detector(concept), sentence)


def _authored_words(concept: GrammarConcept, generator: AtelierExerciseGenerator) -> set[str]:
    """Every word of the sentences the concept authors, folded (whole and in pieces)."""

    import re

    from app.services.grammar_units import contrast_pairs
    from app.services.lexical_coverage import fold

    sentences = [
        *re.split(r"\s*[;|]\s*", concept.anchor_examples or ""),
        *generator._fallback_sentences(concept),
    ]
    for pair in contrast_pairs(concept):
        sentences.extend([pair["wrong"], pair["right"]])
    words: set[str] = set()
    for sentence in sentences:
        for token in re.findall(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", sentence):
            words.add(fold(token))
            words.update(fold(piece) for piece in re.findall(r"[^\W\d_]+", token))
    return words


def _is_french(word: str, authored: set[str]) -> bool:
    from app.services.lexical_coverage import fold, load_lexicon, tokenize

    if not any(char.isalpha() for char in word):
        return True
    if fold(word) in authored:
        return True
    lexicon = load_lexicon()
    keys = [token.key for token in tokenize(word)]
    return bool(keys) and all(key in lexicon.lemmas or key in lexicon.forms or key in lexicon.atomic for key in keys)


def test_the_guard_walks_every_unit_of_the_seed() -> None:
    concepts = _unit_concepts()
    assert len(concepts) > 150
    assert all(_detector(concept) for concept in concepts), "every seeded unit has a detector to be held to"


def test_no_invented_form() -> None:
    """«prêters», «encores», «peuxs», «J'économises»: a word bank's tiles and a fill's
    choices are words of the concept's sentences or words the lexicon knows."""

    generator = AtelierExerciseGenerator(None)
    invented: list[str] = []
    autrement = 0
    for concept in _unit_concepts():
        authored = _authored_words(concept, generator)
        sentences = generator._fallback_sentences(concept)
        for item in generator._fallback_word_bank_items(concept, sentences, prefix="t"):
            for tile in item["tokens"]:
                autrement += tile.lower() == "autrement" and "autrement" not in authored
                if not _is_french(tile, authored):
                    invented.append(f"{concept.external_id} tile {tile!r}")
        for item in generator._fallback_fill_items(concept, prefix="t"):
            for choice in item["choices"]:
                autrement += choice.lower() == "autrement" and "autrement" not in authored
                if not _is_french(choice, authored):
                    invented.append(f"{concept.external_id} choice {choice!r}")
    assert invented == [], f"{len(invented)} invented forms, e.g. " + "; ".join(invented[:8])
    assert autrement == 0, "«autrement» is not a distractor every bank may carry"


def test_walked_units_real() -> None:
    generator = AtelierExerciseGenerator(None)
    by_id = {concept.external_id: concept for concept in _unit_concepts()}
    offered: set[str] = set()
    for external_id in ("FR2_B11_DOUBLE_PRONOUNS", "FR2_B11_PREP_INFINITIVE"):
        concept = by_id[external_id]
        for item in generator._fallback_word_bank_items(concept, generator._fallback_sentences(concept), prefix="t"):
            offered.update(item["tokens"])
        for item in generator._fallback_fill_items(concept, prefix="t"):
            offered.update(item["choices"])
    for invented in ("prêters", "encores", "peuxs", "J'économises", "dossiers", "Lave-tois", "autrement"):
        assert invented not in offered, invented


def test_blank_is_ruled() -> None:
    """The blank sits inside the span the concept's detector recognises in the finished
    sentence: it is a word today's rule decides, not the first word of four letters."""

    import re

    generator = AtelierExerciseGenerator(None)
    off_rule: list[str] = []
    for concept in _unit_concepts():
        items = generator._fallback_fill_items(concept, prefix="t")
        assert len(items) == 3, (concept.external_id, [item["prompt"] for item in items])
        for item in items:
            blank = re.search(r"_{2,}", item["prompt"])
            assert blank, item
            answer = item["correct_answer"]
            assert answer in item["choices"] and len(set(item["choices"])) == len(item["choices"]) >= 3, item
            filled = item["prompt"][: blank.start()] + answer + item["prompt"][blank.end():]
            covered = any(
                blank.start() < end and start < blank.start() + len(answer) for start, end in _spans(concept, filled)
            )
            if not covered:
                off_rule.append(f"{concept.external_id}: {item['prompt']!r} -> {answer!r}")
                continue
    assert off_rule == [], f"{len(off_rule)} blanks off the rule, e.g. " + "; ".join(off_rule[:6])


def test_wrong_option_breaks() -> None:
    """«Tu peux me la prêter» is as right as «me le»: a wrong option must be a word that
    makes the detector lose the form in the blank, and a real one."""

    import re

    generator = AtelierExerciseGenerator(None)
    by_id = {concept.external_id: concept for concept in _unit_concepts()}
    for external_id in ("FR2_B11_DOUBLE_PRONOUNS", "FR2_B11_PREP_INFINITIVE"):
        concept = by_id[external_id]
        for item in generator._fallback_fill_items(concept, prefix="t"):
            blank = re.search(r"_{2,}", item["prompt"])
            assert blank, item
            for choice in item["choices"]:
                if choice == item["correct_answer"]:
                    continue
                other = item["prompt"][: blank.start()] + choice + item["prompt"][blank.end():]
                shown = any(
                    blank.start() < end and start < blank.start() + len(choice) for start, end in _spans(concept, other)
                )
                assert not shown, (external_id, other)


def test_row_fits_concept() -> None:
    """A row is filed under a concept only when the concept's detector recognises the
    form in it (its answer, or its source for a unit whose detector flags the slip): no place-preposition rows under «Pour, sans, avant de», no
    single-pronoun swaps under «Deux pronoms ensemble»."""

    generator = AtelierExerciseGenerator(None)
    misfiled: list[str] = []
    for concept in _unit_concepts():
        items = generator._fallback_transform_items(concept, generator._fallback_sentences(concept), prefix="t")
        # The validator takes one item or three, never the same correction twice.
        assert len(items) in {1, 3}, (concept.external_id, items)
        assert len({item["source"] for item in items}) == len(items), (concept.external_id, items)
        for item in items:
            # A register unit («ne» dropped) has its detector on the ✗ side of a pair.
            if not (_spans(concept, item["expected_answer"]) or _spans(concept, item["source"])):
                misfiled.append(f"{concept.external_id}: {item['source']!r} -> {item['expected_answer']!r}")
    assert misfiled == [], f"{len(misfiled)} misfiled rows, e.g. " + "; ".join(misfiled[:6])


def test_no_off_rule_row() -> None:
    generator = AtelierExerciseGenerator(None)
    by_id = {concept.external_id: concept for concept in _unit_concepts()}
    prep = generator._fallback_transform_items(by_id["FR2_B11_PREP_INFINITIVE"], [], prefix="t")
    assert not {"Il habite dans cette rue.", "Je vais chez Marie.", "Nous parlons de ce projet."} & {
        item["expected_answer"] for item in prep
    }
    pronouns = generator._fallback_transform_items(by_id["FR2_B11_DOUBLE_PRONOUNS"], [], prefix="t")
    assert not {"Je le vois demain.", "Nous lui parlons ce soir.", "Elle en prend deux."} & {
        item["expected_answer"] for item in pronouns
    }


def test_rewrite_goal() -> None:
    """«Corrige l'erreur dans la phrase» is the goal of a repair. A directed or a contrast
    rewrite starts from a right sentence: it has no error to correct."""

    rows = {
        "directed_rewrite": ("Je bois du café.", "Je ne bois pas de café."),
        "contrast_rewrite": ("C'est du café.", "Ce n'est pas du café."),
        "repair_rewrite": ("Elle n'a pas une idée.", "Elle n'a pas d'idée."),
    }
    for language, repair_goal in (("fr", "Corrige l’erreur dans la phrase."), ("de", "Korrigiere den Fehler im Satz.")):
        goals = {
            kind: ib.with_goal({"id": kind, "type": kind, "source": source, "expected_answer": answer}, language).get(
                "goal_native"
            )
            for kind, (source, answer) in rows.items()
        }
        assert goals["repair_rewrite"] == repair_goal, (language, goals)
        assert goals["directed_rewrite"] != repair_goal, (language, goals)
        assert goals["contrast_rewrite"] != repair_goal, (language, goals)


def test_no_underscore() -> None:
    """The end sheet printed «Tu peux_ me le prêter demain ?»: the blank is four
    underscores and the sheet replaced three."""

    from types import SimpleNamespace

    from app.services.atelier import AtelierSRSService

    for blank in ("___", "____", "_____"):
        item = {"id": "f", "prompt": f"Tu {blank} me le prêter demain ?", "choices": ["peux", "veux"], "correct_answer": "peux"}
        attempt = SimpleNamespace(
            correction_payload={},
            verdict="correct",
            prompt_payload={"items": [item]},
            answer_payload={"answers": {"f": "peux"}},
            round="recognize",
            mode="fill",
        )
        proof = AtelierSRSService._forge_proof_line(attempt)
        assert proof is not None and proof[0] == "Tu peux me le prêter demain ?", (blank, proof)
