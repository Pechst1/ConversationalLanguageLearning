"""WP-21: the part-of-speech resolver consults the curated file before guessing.

The old rule was one line — longer than four letters and ending in -er/-ir/-re/
-oir means verb — and it printed `plaisir`, `avenir` and `exemplaire` to the
learner as verbs on the review card. `scripts/audit_pos_heuristic.py` measures
that against spaCy; this file pins the resolution order the audit's output feeds.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.services import vocabulary_coverage
from app.services.vocabulary_coverage import (
    POS_OVERRIDES_PATH,
    heuristic_part_of_speech,
    inferred_part_of_speech,
    normalize_pos_tag,
    pos_overrides,
    reload_pos_overrides,
)


def word(surface: str, **fields):
    """A stand-in for a deck row: the resolver only reads attributes."""
    return SimpleNamespace(word=surface, normalized_word=surface, **fields)


@pytest.fixture(autouse=True)
def _fresh_overrides():
    reload_pos_overrides()
    yield
    reload_pos_overrides()


def test_override_file_is_well_formed() -> None:
    payload = json.loads(POS_OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert payload["version"]
    overrides = payload["overrides"]
    assert isinstance(overrides, dict) and overrides
    allowed = {"verb", "noun", "adjective", "adverb", "function"}
    for surface, tag in overrides.items():
        assert surface == surface.lower().strip(), surface
        assert tag in allowed, f"{surface} -> {tag}"


def test_the_known_wrong_words_are_covered() -> None:
    """The exact set the review card was printing as verbs."""
    for surface, expected in [
        ("plaisir", "noun"),
        ("avenir", "noun"),
        ("souvenir", "noun"),
        ("exemplaire", "noun"),
        ("désir", "noun"),
        ("loisir", "noun"),
        ("dernier", "adjective"),
        ("premier", "adjective"),
        ("pratiquement", "adverb"),
    ]:
        assert heuristic_part_of_speech(word(surface)) != expected, (
            f"{surface} no longer needs an override; drop it from the file"
        )
        assert inferred_part_of_speech(word(surface)) == expected, surface


def test_real_verbs_are_untouched() -> None:
    for surface in ("manger", "finir", "prendre", "vouloir", "abaisser"):
        assert inferred_part_of_speech(word(surface)) == "verb", surface


def test_resolution_order_is_overrides_then_spacy_then_column_then_heuristic() -> None:
    # 1. The curated file wins over everything, including a stored column.
    assert inferred_part_of_speech(word("plaisir", part_of_speech="VERB")) == "noun"
    # 2. A tagger's answer attached by a caller beats the stored column.
    assert inferred_part_of_speech(word("bidule", spacy_pos="ADJ", part_of_speech="noun")) == "adjective"
    # 3. The stored column beats the suffix guess.
    assert inferred_part_of_speech(word("chanter", part_of_speech="noun")) == "noun"
    # 4. And the suffix guess is the last resort.
    assert inferred_part_of_speech(word("chanter")) == "verb"


def test_tags_are_normalized_to_one_vocabulary() -> None:
    assert normalize_pos_tag("VERB") == "verb"
    assert normalize_pos_tag("AUX") == "verb"
    assert normalize_pos_tag("PROPN") == "noun"
    assert normalize_pos_tag("adj") == "adjective"
    assert normalize_pos_tag("DET") == "function"
    assert normalize_pos_tag(None) == ""


def test_a_missing_or_broken_file_falls_back_to_the_heuristic(tmp_path, monkeypatch) -> None:
    """A bad deploy must degrade to the old behaviour, not blank the card."""
    broken = tmp_path / "pos_overrides.json"
    broken.write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(vocabulary_coverage, "POS_OVERRIDES_PATH", broken)
    reload_pos_overrides()
    assert pos_overrides() == {}
    assert inferred_part_of_speech(word("plaisir")) == "verb"

    monkeypatch.setattr(vocabulary_coverage, "POS_OVERRIDES_PATH", tmp_path / "missing.json")
    reload_pos_overrides()
    assert pos_overrides() == {}
