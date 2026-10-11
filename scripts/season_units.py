"""Which grammar units each tentpole day uses, and the can-do it credits (T-1, D7).

On a tentpole day the authored page is served as written, so the day must not
introduce a grammar unit the page never uses (content audit 2026-10-03, §4).
Instead the Règle step reviews a unit the page *does* use. This script runs every
reviewed detector of ``templates/french_core_grammar_v2.tsv`` over each tentpole
day's French (the bible's A2 text, every variant and branch) and writes
``app/data/season/<id>/units.json``:

    {"version": "season-units-v1", "catalogue": "<tsv sha8>",
     "days": {"t1a": {"units": ["FR2_A11_ETRE", …], "can_do": "CD_A11_GREET"}, …}}

Units are listed in catalogue order (A1.1 first). Re-run after the catalogue or a
tentpole changes; ``tests/test_season_levels.py`` checks the file is current.

    venv/bin/python scripts/season_units.py [--season s1] [--check]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.grammar_catalog import detector_matches, parse_detector  # noqa: E402
from app.services.season.levels import iter_says  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "templates" / "french_core_grammar_v2.tsv"
CAN_DOS = ROOT / "app" / "data" / "syllabus" / "fr_core_can_dos_v2.json"

#: The authored can-do of each tentpole day («can_do» in t*.json), matched by hand
#: to the syllabus can-do it practises. A day with no faithful match credits none.
CAN_DO_BY_DAY: dict[str, str | None] = {
    "t1a": "CD_A11_GREET",
    "t1b": "CD_A22_FUTURE_PLANS",
    "t2a": "CD_A21_COMPARE",
    "t2b": "CD_A21_EXPLAIN_WHY",
    "t3a": "CD_A12_INVITE",
    "t3b": "CD_B11_OPINION",
    "t4a": "CD_A22_ANECDOTE",
    "t4b": "CD_A21_EXPLAIN_WHY",
    "t5a": "CD_A22_PASS_MESSAGE",
    "t5b": "CD_A22_PASS_MESSAGE",
    "t6a": "CD_B11_OPINION",
    "t6b": "CD_A21_EXPLAIN_WHY",
    "t7a": "CD_B11_HYPOTHESIS",
    "t7b": "CD_B11_CONDITIONS",
    "t8a": "CD_B11_STORY",
    "t8b": None,
}


def catalogue_fingerprint() -> str:
    return hashlib.sha256(CATALOGUE.read_bytes()).hexdigest()[:8]


def build(season_dir: Path) -> dict:
    with CATALOGUE.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle, delimiter="\t") if row.get("review_status") == "reviewed"]
    detectors = [(row["external_id"], parse_detector(row["detector"])) for row in rows]
    can_dos = {
        task["id"]
        for tasks in json.loads(CAN_DOS.read_text(encoding="utf-8"))["sub_bands"].values()
        for task in tasks
    }
    days: dict[str, dict] = {}
    for path in sorted(season_dir.glob("t[0-9].json")):
        tentpole = json.loads(path.read_text(encoding="utf-8"))
        for day in tentpole.get("days") or []:
            key = f"{tentpole['id']}{day['day']}"
            texts = [say["a2"] for say in iter_says(day)]
            found = days.setdefault(key, {"units": [], "can_do": None})
            for unit_id, detector in detectors:
                if unit_id not in found["units"] and any(detector_matches(detector, text) for text in texts):
                    found["units"].append(unit_id)
            can_do = CAN_DO_BY_DAY.get(key)
            found["can_do"] = can_do if can_do in can_dos else None
    order = {row["external_id"]: index for index, row in enumerate(rows)}
    for found in days.values():
        found["units"].sort(key=lambda unit: order.get(unit, 10**6))
    return {"version": "season-units-v1", "catalogue": catalogue_fingerprint(), "days": days}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--season", default="s1")
    parser.add_argument("--check", action="store_true", help="exit 1 when units.json is stale")
    args = parser.parse_args()
    season_dir = ROOT / "app" / "data" / "season" / args.season
    payload = build(season_dir)
    target = season_dir / "units.json"
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        print("current" if current == text else "stale: run scripts/season_units.py")
        return 0 if current == text else 1
    target.write_text(text, encoding="utf-8")
    for key, found in payload["days"].items():
        print(f"{key}: {len(found['units'])} units, can-do {found['can_do']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
