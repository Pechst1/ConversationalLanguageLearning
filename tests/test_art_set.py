"""WP-116 phase 0: the painted art set can be checked and brought back."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("art_set", REPO / "scripts/art/art_set.py")
art_set = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(art_set)


def _tag_exists() -> bool:
    out = subprocess.run(["git", "-C", str(REPO), "tag", "-l", art_set.TAG], capture_output=True, text=True)
    return art_set.TAG in out.stdout.split()


def test_manifest_covers_every_painted_folder():
    manifest = json.loads((REPO / art_set.MANIFEST).read_text())
    paths = [entry["path"] for entry in manifest["files"]]
    for folder in art_set.PAINTED_DIRS:
        assert any(p.startswith(folder + "/") for p in paths), folder
    assert any(p.endswith("romy_tremblay/portrait-neutral.webp") for p in paths)
    assert manifest["tag"] == art_set.TAG
    assert manifest["readers"]


def test_the_painted_set_is_intact_in_the_repo():
    assert art_set.verify(REPO) == 0


@pytest.mark.skipif(not _tag_exists(), reason="the painted-set tag only exists in the owner's checkout")
def test_restore_brings_back_a_deleted_and_a_changed_file(tmp_path):
    manifest = json.loads((REPO / art_set.MANIFEST).read_text())
    (tmp_path / art_set.MANIFEST).parent.mkdir(parents=True)
    shutil.copy(REPO / art_set.MANIFEST, tmp_path / art_set.MANIFEST)
    for entry in manifest["files"]:
        target = tmp_path / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / entry["path"], target)
    gone = tmp_path / manifest["files"][0]["path"]
    gone.unlink()
    changed = tmp_path / manifest["files"][1]["path"]
    changed.write_bytes(b"not a portrait")

    assert art_set.verify(tmp_path) == 1
    assert art_set.restore(tmp_path, REPO) == 0
    assert art_set.verify(tmp_path) == 0
