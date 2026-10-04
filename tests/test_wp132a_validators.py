"""WP-132A (owner decision 7, proposed): three glossed past chunks for Odile's past at A1.

``scripts/season_levels.py`` lets an A1 line say «elle est partie», «c'était» or
«elle savait» (subject «elle» or «Odile») so that a woman who left in 2023 and has
since died never reads as leaving now. The exception is narrow:

* the grammar detectors read the chunk as the present form A1 already allows, and
  only that chunk — any other past form on the line still fails;
* the coverage counts the chunk's words one by one (never one token), and the
  chunks are reported apart;
* one chunk per line, and it takes the line's one word outside the A1 list.

With today's data (no chunk anywhere) the script's output is unchanged.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from app.services.grammar_catalog import detector_matches, parse_detector

REPO = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location("season_levels_wp132a", REPO / "scripts" / "season_levels.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


season_levels = _load_script()


def _detector(unit: str) -> dict:
    with (REPO / "templates" / "french_core_grammar_v2.tsv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row["external_id"] == unit:
                return parse_detector(row["detector"])
    raise AssertionError(unit)


@pytest.mark.parametrize(
    ("text", "masked", "chunks"),
    [
        ("Alors ? Pourquoi elle est partie, Odile ?", "Alors ? Pourquoi elle part, Odile ?", ["elle est partie"]),
        ("Odile est partie.", "Odile part.", ["elle est partie"]),
        ("C'était son idée ? Montre.", "C'est son idée ? Montre.", ["c'était"]),
        ("Partir, c’était son idée.", "Partir, c'est son idée.", ["c'était"]),
        ("Ta grand-mère ? Elle savait tout.", "Ta grand-mère ? Elle sait tout.", ["elle savait"]),
        ("Au début, elle ne savait pas.", "Au début, elle ne sait pas.", ["elle savait"]),
    ],
)
def test_each_chunk_reads_as_its_present_form(text, masked, chunks):
    assert season_levels.mask_a1_past_chunks(text) == (masked, chunks)


@pytest.mark.parametrize(
    "text",
    [
        "Il est parti.",  # another subject
        "Marin savait.",  # another subject
        "Elle était là.",  # «elle était» is not «c'était»
        "Elle est venue.",  # another verb
        "Elle a dit au revoir.",  # passé composé with avoir
        "Elles sont parties.",
    ],
)
def test_nothing_else_is_masked(text):
    assert season_levels.mask_a1_past_chunks(text) == (text, [])


def test_the_detectors_still_see_every_other_past_form_on_the_line():
    pc_etre = _detector("FR2_A21_PC_ETRE")
    imparfait = _detector("FR2_A22_IMPARFAIT")
    line = "Pourquoi elle est partie, Odile ?"
    assert detector_matches(pc_etre, line)  # the raw chunk is above A1 …
    assert not detector_matches(pc_etre, season_levels.mask_a1_past_chunks(line)[0])  # … the exception lifts it
    mixed = "Elle est partie. Il était triste."
    assert detector_matches(imparfait, season_levels.mask_a1_past_chunks(mixed)[0])


# ---------------------------------------------------------------------------
# The whole script, on a scratch copy of season 1
# ---------------------------------------------------------------------------

#: T2 A, a.turn1 — Lila: «Alors ? Pourquoi elle est partie, à ton avis ?»
KEY = "7a7fc80c9768"


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    root = tmp_path_factory.mktemp("season")
    shutil.copytree(REPO / "app" / "data" / "season" / "s1", root / "s1")
    return root


def _run(root: Path, a1: str | None, monkeypatch, capsys) -> tuple[int, str]:
    season = root / "s1"
    path = season / "levels_a.json"
    original = path.read_text(encoding="utf-8")
    try:
        if a1 is not None:
            data = json.loads(original)
            data["lines"][KEY]["a1"] = a1
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        monkeypatch.setattr(season_levels, "SEASON_ROOT", root)
        monkeypatch.setattr(sys, "argv", ["season_levels.py", "--file", "t2", "--strict"])
        code = season_levels.main()
        return code, capsys.readouterr().out
    finally:
        path.write_text(original, encoding="utf-8")


def _running(out: str) -> int:
    match = re.search(r"t2\s+a1:\s+[\d.]+% of (\d+)", out)
    assert match, out
    return int(match.group(1))


def test_todays_data_reports_no_chunk(baseline, monkeypatch, capsys):
    code, out = _run(baseline, None, monkeypatch, capsys)
    assert code == 0, out
    assert "glossed A1 past chunks" not in out


def test_a_glossed_chunk_passes_and_is_reported_apart_with_its_words_counted(baseline, monkeypatch, capsys):
    _code, before = _run(baseline, None, monkeypatch, capsys)
    old = "Alors ? Pourquoi elle part, Odile ?"
    new = "Alors ? Pourquoi elle est partie, Odile ?"
    code, out = _run(baseline, new, monkeypatch, capsys)
    assert code == 0, out
    assert re.search(rf"glossed A1 past chunks.*\n\s+t2\s+a1: 1 — {KEY}", out), out
    # «est partie» is two running words in the coverage, never one token.
    resolver = season_levels.default_resolver()
    known = season_levels._known("A1", frozenset({"odile"}))
    grown = season_levels.text_coverage(new, known, resolver=resolver).running_words - season_levels.text_coverage(
        old, known, resolver=resolver
    ).running_words
    assert grown == 1
    assert _running(out) == _running(before) + grown


@pytest.mark.parametrize(
    ("a1", "why"),
    [
        ("Elle est partie. C'était son idée.", "more than one glossed past chunk"),
        ("Pourquoi elle est partie ? Silence.", "takes the line's word outside"),
        ("Pourquoi il est parti, Odile ?", "FR2_A21_PC_ETRE is above A1"),
    ],
)
def test_the_exception_stays_narrow(baseline, monkeypatch, capsys, a1, why):
    code, out = _run(baseline, a1, monkeypatch, capsys)
    assert code == 1
    assert why in out, out
