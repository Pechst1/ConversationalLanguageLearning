"""The night shift's red/green proof (scripts/loop/red_green.py) on throwaway git repos."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "loop" / "red_green.py"
_SPEC = importlib.util.spec_from_file_location("red_green", _PATH)
assert _SPEC and _SPEC.loader
red_green = importlib.util.module_from_spec(_SPEC)
sys.modules["red_green"] = red_green  # dataclasses look their module up while the class is built
_SPEC.loader.exec_module(red_green)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],  # noqa: S603, S607
                   cwd=repo, check=True, capture_output=True)


def _repo(tmp_path: Path, monkeypatch: Any, fix: str, test: str) -> Path:
    """main holds a bug in calc.py; the branch applies `fix` and adds `test`."""
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "calc.py").write_text("def double(x):\n    return x + 2\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "fix")
    (repo / "calc.py").write_text(fix)
    (repo / "tests" / "test_calc.py").write_text(test)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "fix")
    monkeypatch.chdir(repo)
    return repo


FIXED = "def double(x):\n    return x * 2\n"


def test_a_test_that_catches_the_bug_is_proven(tmp_path: Path, monkeypatch: Any) -> None:
    repo = _repo(tmp_path, monkeypatch, FIXED, "from calc import double\n\ndef test_it():\n    assert double(3) == 6\n")
    verdict = red_green.prove("main")
    assert verdict.result == "proven", verdict
    assert verdict.reverted == ["calc.py"]
    assert (repo / "calc.py").read_text() == FIXED  # restored after the red run


def test_a_test_that_passes_without_the_fix_proves_nothing(tmp_path: Path, monkeypatch: Any) -> None:
    _repo(tmp_path, monkeypatch, FIXED, "from calc import double\n\ndef test_it():\n    assert double(2) == 4\n")
    assert red_green.prove("main").result == "red-passes"


def test_failing_only_on_a_missing_name_is_weak(tmp_path: Path, monkeypatch: Any) -> None:
    fix = FIXED + "\ndef triple(x):\n    return x * 3\n"
    _repo(tmp_path, monkeypatch, fix, "from calc import triple\n\ndef test_it():\n    assert triple(1) == 3\n")
    assert red_green.prove("main").result == "weak"


def test_no_test_and_dirty_tree(tmp_path: Path, monkeypatch: Any) -> None:
    repo = _repo(tmp_path, monkeypatch, FIXED, "")
    (repo / "tests" / "test_calc.py").unlink()
    _git(repo, "commit", "-qam", "drop test")
    assert red_green.prove("main").result == "no-test"
    (repo / "calc.py").write_text("oops\n")
    with pytest.raises(SystemExit, match="commit or stash"):
        red_green.prove("main")
