"""Regression tests for vocabulary enrichment helpers."""
from __future__ import annotations

from scripts.enrich_vocabulary import heuristic_pos, load_frequency


def test_load_frequency_treats_frequency_counts_as_descending_rank(tmp_path) -> None:
    frequency_csv = tmp_path / "frequency.csv"
    frequency_csv.write_text(
        "word,frequency\nrare,2\ncommun,12000\nmoyen,30\n",
        encoding="utf-8",
    )

    ranks = load_frequency(str(frequency_csv))

    assert ranks["commun"] == 1
    assert ranks["moyen"] == 2
    assert ranks["rare"] == 3


def test_load_frequency_preserves_explicit_rank_columns(tmp_path) -> None:
    frequency_csv = tmp_path / "rank.csv"
    frequency_csv.write_text(
        "word,rank\nrare,4000\ncommun,10\n",
        encoding="utf-8",
    )

    ranks = load_frequency(str(frequency_csv))

    assert ranks["commun"] == 10
    assert ranks["rare"] == 4000


def test_heuristic_pos_classifies_ment_adverbs_before_nouns() -> None:
    assert heuristic_pos("rapidement") == "adverb"
