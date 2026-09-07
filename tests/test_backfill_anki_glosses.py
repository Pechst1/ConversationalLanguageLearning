"""WP-21: the English-gloss backfill cannot spend money by accident.

The script is the only one in `scripts/` that calls a paid provider over the whole
deck, so its guards are worth pinning: a dry run is the default, `--live` refuses
to start without both ceilings stated, and a row that already has an English
gloss is never overwritten.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "backfill_anki_glosses.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("backfill_anki_glosses", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


backfill = _load_script()


def test_live_requires_both_ceilings(monkeypatch) -> None:
    for argv in (
        ["backfill", "--live"],
        ["backfill", "--live", "--max-rows", "10"],
        ["backfill", "--live", "--max-cost-usd", "1"],
        ["backfill", "--live", "--max-rows", "0", "--max-cost-usd", "1"],
        ["backfill", "--live", "--max-rows", "10", "--max-cost-usd", "0"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        with pytest.raises(SystemExit) as excinfo:
            backfill.main()
        assert excinfo.value.code == 2, argv


def test_parse_glosses_drops_malformed_entries() -> None:
    parsed = backfill.parse_glosses(
        '{"glosses": {"1": "copy", "2": "  ", "3.": "meeting", "9": "out of range", "x": "junk"}}',
        3,
    )
    assert parsed == {1: "copy", 3: "meeting"}
    assert backfill.parse_glosses("not json", 3) == {}
    assert backfill.parse_glosses('{"other": {}}', 3) == {}


def test_prompt_carries_the_context_the_row_already_has() -> None:
    rows = [
        SimpleNamespace(
            word="séance",
            normalized_word="seance",
            part_of_speech="noun",
            german_translation="Sitzung",
            example_sentence="La séance commence.",
        ),
        SimpleNamespace(
            word="élire",
            normalized_word="elire",
            part_of_speech=None,
            german_translation=None,
            example_sentence=None,
        ),
    ]
    prompt = backfill.build_prompt(rows)
    assert "1. séance  (noun; German: Sitzung; Used in: La séance commence.)" in prompt
    assert "2. élire" in prompt
    # No hint parentheses when the row carries nothing.
    assert "2. élire  (" not in prompt


def test_provenance_names_the_model_and_the_prompt_version() -> None:
    row = SimpleNamespace(usage_notes=None)
    backfill.record_provenance(row, model="test-model", ran_at="2026-09-07T00:00:00+00:00")
    assert backfill.GLOSS_PROMPT_VERSION in row.usage_notes
    assert "model=test-model" in row.usage_notes

    # An existing note is kept, not replaced.
    row = SimpleNamespace(usage_notes="handwritten note")
    backfill.record_provenance(row, model="test-model", ran_at="2026-09-07T00:00:00+00:00")
    assert row.usage_notes.startswith("handwritten note")
    assert backfill.PROVENANCE_KEY in row.usage_notes


def test_the_script_only_ever_selects_empty_english_columns() -> None:
    """A grep-level guard: the write path has no branch that replaces a gloss."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert "row.english_translation = gloss" in source
    assert 'if str(row.english_translation or "").strip():' in source
    assert "--overwrite" not in source
