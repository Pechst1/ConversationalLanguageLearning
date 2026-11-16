"""The repository root holds only what a build, a test run or a deploy reads (S6, stage 1).

The root once held a retired React Native client, one-off scripts, an empty database and
old planning notes beside the live data. This test lists what may sit at the root. A new
entry fails here: put code in `app/` or `scripts/`, data in `app/data/`, notes in `docs/`.
If a new root file really is read by a build, a test run or a deploy, add it below with
the reader named.
"""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or "git"

ALLOWED = {
    # Build and packaging
    "Dockerfile",  # the API image
    ".dockerignore",
    "pyproject.toml",  # pip install . in the Dockerfile and CI
    "constraints.txt",  # PIP_CONSTRAINT in the Dockerfile and CI
    "README.md",  # pyproject's readme, copied by the Dockerfile
    "alembic.ini",
    # Code and data
    "app",
    "alembic",
    "scripts",
    "tests",
    "conftest.py",  # pytest's root conftest
    "web-frontend",
    "docker",
    "docs",
    # Deploy and CI
    "render.yaml",
    ".github",
    ".env.example",
    ".env.prod.example",
    # Tooling
    ".gitignore",
    ".claude",  # launch.json for the dev servers, agent definitions
    "start-backend.sh",
    "start-celery.sh",
    "start-frontend.sh",
    # Open owner decision (S6 decision 1): keep, move to private storage, or delete.
    # Read by the lexicon build's provenance and three scripts; do not move without the owner.
    "Anki_cards___2025-11-01T13-09-36.csv",
    "Französisch_Grammatik_Tracker-2.xlsx",
}


def _nfc(name: str) -> str:
    return unicodedata.normalize("NFC", name)


def root_entries(root: Path = ROOT) -> set[str]:
    """Tracked and untracked-but-not-ignored top-level names, as git sees them."""
    output = subprocess.run(  # noqa: S603 - fixed git argv
        [GIT, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    deleted = subprocess.run(  # noqa: S603 - fixed git argv
        [GIT, "ls-files", "-z", "--deleted"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    gone = {path for path in deleted.split("\0") if path}
    return {
        _nfc(path.split("/", 1)[0])
        for path in output.split("\0")
        if path and path not in gone
    }


needs_git = pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(),
    reason="needs a git checkout",
)


@needs_git
def test_root_holds_only_allowed_entries() -> None:
    allowed = {_nfc(name) for name in ALLOWED}
    stray = sorted(root_entries() - allowed)
    assert not stray, (
        f"New entries at the repository root: {stray}. The root holds only what a build, "
        "a test run or a deploy reads. Move code to app/ or scripts/, data to app/data/, "
        "notes to docs/. If a build, test or deploy reads it, add it to ALLOWED with its reader."
    )


@needs_git
def test_a_stray_root_file_is_caught(tmp_path: Path) -> None:
    # A throwaway repository, so a shuffled or parallel run never sees the stray file in ours.
    subprocess.run([GIT, "init", "-q"], cwd=tmp_path, check=True)  # noqa: S603
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    (tmp_path / "fix_db.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.js").write_text("x\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    assert root_entries(tmp_path) - ALLOWED == {"fix_db.py"}


@needs_git
def test_retired_entries_stay_gone() -> None:
    retired = {
        "package.json", "jest.config.js", "jest.setup.ts", "tsconfig.json", "src",
        "templates", "vocabulary_fr_sample.csv", "data.db", "response.json", "pg2701-h",
    }
    assert not retired & ALLOWED
    assert not retired & root_entries()
