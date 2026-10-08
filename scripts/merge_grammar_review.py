"""Merge the reviewed grammar shards into the fr-core-v2 catalogue (content program 2026-10-03).

Reads ``app/data/grammar_review/units_<BAND>.json`` (one reviewed row per unit, every
TSV column) and rewrites ``templates/french_core_grammar_v2.tsv``:

* an existing id is replaced by its reviewed row;
* a new id is appended;
* the file is re-sorted by sub-band, then teaching order;
* ``app/data/syllabus/can_dos_C1.json`` (when present) is merged into
  ``app/data/syllabus/fr_core_can_dos_v2.json`` as sub-bands C1.1 / C1.2.

It refuses to write when a shard row lacks a column, a prerequisite or contrast
partner does not resolve, or two shards claim the same id. ``--check`` validates
without writing.

    venv/bin/python scripts/merge_grammar_review.py [--check]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TSV = ROOT / "templates" / "french_core_grammar_v2.tsv"
SHARDS = ROOT / "app" / "data" / "grammar_review"
CAN_DOS = ROOT / "app" / "data" / "syllabus" / "fr_core_can_dos_v2.json"
CAN_DOS_C1 = ROOT / "app" / "data" / "syllabus" / "can_dos_C1.json"
SUB_BANDS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2", "B2.1", "B2.2", "C1.1", "C1.2")


def _ids(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def merge(check_only: bool, bands: set[str] | None = None) -> int:
    with TSV.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        columns = list(reader.fieldnames or [])
        rows = {row["external_id"]: row for row in reader}

    claimed: dict[str, str] = {}
    problems: list[str] = []
    replaced = added = 0
    for shard in sorted(SHARDS.glob("units_*.json")):
        if bands and shard.stem.removeprefix("units_") not in bands:
            continue
        payload = json.loads(shard.read_text(encoding="utf-8"))
        for unit in payload.get("units") or []:
            unit_id = str(unit.get("external_id") or "")
            if not unit_id:
                problems.append(f"{shard.name}: a unit without external_id")
                continue
            if unit_id in claimed:
                problems.append(f"{unit_id}: in {claimed[unit_id]} and {shard.name}")
                continue
            claimed[unit_id] = shard.name
            missing = [column for column in columns if column not in unit]
            if missing:
                problems.append(f"{unit_id}: missing columns {missing}")
                continue
            if unit.get("sub_band") not in SUB_BANDS:
                problems.append(f"{unit_id}: unknown sub_band {unit.get('sub_band')!r}")
            if unit_id in rows:
                replaced += 1
            else:
                added += 1
            rows[unit_id] = {column: str(unit[column]) for column in columns}

    for unit_id, row in rows.items():
        for ref in _ids(row.get("prerequisites", "")) + _ids(row.get("contrast_partners", "")):
            if ref not in rows:
                problems.append(f"{unit_id}: unresolved reference {ref}")

    # The foundation flag means "another unit depends on it" (WP-L2); the
    # reviewers' shards may have used it to steer order, which the engine now
    # takes from the sub-band (atelier._sub_band_rank), so it is recomputed here.
    depended_on = {ref for row in rows.values() for ref in _ids(row.get("prerequisites", ""))}
    for unit_id, row in rows.items():
        row["is_foundation"] = "true" if unit_id in depended_on else "false"

    ordered = sorted(
        rows.values(),
        key=lambda row: (SUB_BANDS.index(row["sub_band"]) if row["sub_band"] in SUB_BANDS else 99,
                         int(row.get("teaching_order") or 0), row["external_id"]),
    )

    can_dos = json.loads(CAN_DOS.read_text(encoding="utf-8"))
    if CAN_DOS_C1.exists() and (not bands or "C1" in bands):
        extra = json.loads(CAN_DOS_C1.read_text(encoding="utf-8"))
        for sub_band, tasks in extra.items():
            if sub_band in SUB_BANDS:
                can_dos.setdefault("sub_bands", {})[sub_band] = tasks
    for _sub_band, tasks in (can_dos.get("sub_bands") or {}).items():
        for task in tasks:
            for ref in task.get("units") or []:
                if ref not in rows:
                    problems.append(f"can-do {task.get('id')}: unresolved unit {ref}")

    print(f"{len(ordered)} units: {replaced} reviewed rows replaced, {added} added; "
          f"{sum(1 for r in ordered if r.get('review_status') == 'reviewed')} reviewed")
    if problems:
        print("\n".join(f"  ✗ {problem}" for problem in problems))
        return 1
    if check_only:
        return 0

    with TSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(ordered)
    CAN_DOS.write_text(json.dumps(can_dos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {TSV.relative_to(ROOT)} and {CAN_DOS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate without writing")
    parser.add_argument("--bands", help="only these shards, e.g. A1,A2,B1 (default: all)")
    args = parser.parse_args()
    sys.exit(merge(args.check, set(args.bands.split(",")) if args.bands else None))
