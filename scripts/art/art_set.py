#!/usr/bin/env python
"""The painted art set: keep it, check it, bring it back (WP-116 phase 0).

The drawn cast (SVG rigs) replaces the painted cast step by step. Until the owner
has said yes twice, every painted file stays where it is, and this script is the
safety net:

    venv/bin/python scripts/art/art_set.py build     # write the manifest (once, at the tag)
    venv/bin/python scripts/art/art_set.py verify    # every painted file present and unchanged
    venv/bin/python scripts/art/art_set.py restore   # bring back missing/changed files from the tag
    venv/bin/python scripts/art/art_set.py report    # which set the app is switched to

``restore`` reads each file with ``git show <tag>:<path>``. It never runs checkout,
stash or reset, because other sessions share this checkout. ``--root`` points every
command at another tree (the tests use a temporary copy).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TAG = "art-painted-2026-10-01"
MANIFEST = Path("docs/art/painted-set-2026-10-01.json")

#: Every folder whose files make up the painted set.
PAINTED_DIRS = (
    "web-frontend/public/assets/serial/characters",
    "web-frontend/public/assets/serial/scenes",
    "docs/design-reference/cast",
)

#: The code that reads painted files (inventory of 2026-10-01). Kept in the manifest
#: so whoever restores the set knows what consumes it.
READERS = (
    "web-frontend/lib/onboarding-portraits.ts (portraitSrc)",
    "web-frontend/lib/cast-faces.ts (faceSrcFor)",
    "web-frontend/components/atelier-v2/ui/CastPortrait.tsx",
    "web-frontend/components/atelier-v2/ui/Feedback.tsx (Portrait)",
    "web-frontend/components/feuilleton/archive/Trombinoscope.tsx",
    "web-frontend/pages/audio-session.tsx",
    "web-frontend/pages/vocabulary/review.tsx",
    "app/services/serial.py (_portrait_url)",
    "app/services/serial_notifications.py (portrait_path)",
    "app/services/panel_art.py (CAST_REFERENCES)",
    "app/services/journey_content.py (authored_panels)",
    "app/prompts/serial/world_bible_paris_v2.json (cast reference_images)",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _painted_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for folder in PAINTED_DIRS:
        base = root / folder
        if base.is_dir():
            files.extend(p for p in sorted(base.rglob("*")) if p.is_file() and not p.name.startswith("."))
    return files


def build(root: Path) -> int:
    entries = [
        {"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": _sha256(p)}
        for p in _painted_files(root)
    ]
    manifest = {
        "tag": TAG,
        "note": "The painted cast set kept for WP-116. Restore with scripts/art/art_set.py restore.",
        "files": entries,
        "readers": list(READERS),
    }
    target = root / MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(entries)} painted files written to {MANIFEST}")
    return 0


def _load(root: Path) -> dict:
    path = root / MANIFEST
    if not path.exists():
        raise SystemExit(f"no manifest at {MANIFEST}; run `build` first")
    return json.loads(path.read_text(encoding="utf-8"))


def _problems(root: Path, manifest: dict) -> list[tuple[str, str]]:
    problems: list[tuple[str, str]] = []
    for entry in manifest["files"]:
        path = root / entry["path"]
        if not path.exists():
            problems.append((entry["path"], "missing"))
        elif _sha256(path) != entry["sha256"]:
            problems.append((entry["path"], "changed"))
    return problems


def verify(root: Path) -> int:
    manifest = _load(root)
    problems = _problems(root, manifest)
    for path, why in problems:
        print(f"{why:8} {path}")
    print(f"{len(manifest['files']) - len(problems)}/{len(manifest['files'])} painted files intact")
    return 1 if problems else 0


def restore(root: Path, repo: Path) -> int:
    manifest = _load(root)
    problems = _problems(root, manifest)
    for rel, why in problems:
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"{manifest['tag']}:{rel}"],
            check=True,
            capture_output=True,
        ).stdout
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        print(f"restored ({why}) {rel}")
    remaining = _problems(root, manifest)
    print(f"{len(problems)} restored, {len(remaining)} still wrong")
    return 1 if remaining else 0


def report(root: Path) -> int:
    flags_path = root / "web-frontend/launch-flags.json"
    flags = json.loads(flags_path.read_text()) if flags_path.exists() else {}
    print(f"frontend build default (launch-flags.json artSet): {flags.get('artSet', 'painted')}")
    print(f"backend ATELIER_ART_SET (environment): {os.environ.get('ATELIER_ART_SET', 'painted (default)')}")
    print("on a device: Settings › Affichage › Personnages, or localStorage key atelier.artSet")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("build", "verify", "restore", "report"))
    parser.add_argument("--root", type=Path, default=REPO, help="tree to act on (default: this repo)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if args.command == "build":
        return build(root)
    if args.command == "verify":
        return verify(root)
    if args.command == "restore":
        return restore(root, REPO)
    return report(root)


if __name__ == "__main__":
    sys.exit(main())
