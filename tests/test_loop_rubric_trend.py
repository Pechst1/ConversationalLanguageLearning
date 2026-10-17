"""The rubric trend page (scripts/loop/rubric_trend.py) reads the walk reports' score tables."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "loop" / "rubric_trend.py"
_SPEC = importlib.util.spec_from_file_location("rubric_trend", _PATH)
assert _SPEC and _SPEC.loader
rubric_trend = importlib.util.module_from_spec(_SPEC)
sys.modules["rubric_trend"] = rubric_trend
_SPEC.loader.exec_module(rubric_trend)

TABLE = """# Walk {day}

| # | question | {cols} |
|---|---|{sep}
| 1 | Where am I | {q1} |
| 10 | Right answers accepted | {q10} |

after the table
"""


def _report(folder: Path, day: str, cols: list[str], q1: list[str], q10: list[str]) -> None:
    (folder / f"{day}.md").write_text(TABLE.format(
        day=day, cols=" | ".join(cols), sep="---|" * len(cols), q1=" | ".join(q1), q10=" | ".join(q10)))


def test_copied_columns_count_once_and_live_stays_apart(tmp_path: Path) -> None:
    _report(tmp_path, "2026-10-15", ["a2-en d1", "live 15 Oct (A1.1, day 4)"], ["4", "3"], ["5", "4"])
    _report(tmp_path, "2026-10-16", ["a1-de d1 16 Oct", "a2-en d1 15 Oct", "live 16 Oct"], ["4", "4", "4"],
            ["2", "5", "1"])
    (tmp_path / "TREND.md").write_text("| # | question | x |\n")  # its own output is not a report
    titles, scores = rubric_trend.collect(tmp_path)
    assert titles == {1: "Where am I", 10: "Right answers accepted"}
    oct15, oct16 = date(2026, 10, 15), date(2026, 10, 16)
    assert scores[(oct15, "explore")][10] == [5.0]  # «a2-en d1 15 Oct» copied into the 16th: once
    assert scores[(oct16, "explore")][10] == [2.0]
    assert scores[(oct16, "live")][10] == [1.0]
    text = rubric_trend.table(titles, scores)
    assert "| 10 | Right answers accepted | 5 | 4 | 2 | 1 |" in text


def test_fake_and_na_cells_are_not_scores(tmp_path: Path) -> None:
    _report(tmp_path, "2026-10-16", ["a1-de d1", "a1-de d2"], ["fake", "n/a"], ["3", "4"])
    _, scores = rubric_trend.collect(tmp_path)
    assert 1 not in scores[(date(2026, 10, 16), "explore")]
    assert scores[(date(2026, 10, 16), "explore")][10] == [3.0, 4.0]
