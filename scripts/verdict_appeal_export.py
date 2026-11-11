#!/usr/bin/env python3
"""Package V stage 5: write upheld appeals as corpus candidates for the night shift.

Each upheld appeal is a case where the judge said «not yet» and the stronger model said
the learner was right. This script writes the ones not exported yet to
``tests/verdict_corpus/candidates/appeals-<date>.jsonl``, one JSON object per line:
``id``, ``surface``, ``text`` (the learner's answer), ``item`` (the exercise as the
appeal model read it), ``was`` (the verdict appealed), ``expected`` (``right``), the
model's ``reason`` and the ``judge_version``. The night shift reads the folder and opens
a PR that adds the case to the replay corpus (``scripts/verdict_replay.py``), so the next
judge change is measured against it. It marks each row exported, so a case is written once.

Usage::

    python scripts/verdict_appeal_export.py              # into tests/verdict_corpus/candidates/
    python scripts/verdict_appeal_export.py --out DIR
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "tests" / "verdict_corpus" / "candidates"


def export(db: Session, *, out_dir: Path = CANDIDATES, now: datetime | None = None) -> list[Path]:
    """Write every upheld appeal not exported yet. Returns the files written. Commits."""

    from app.db.models.verdict_appeal import VerdictAppeal
    from app.services.judge import judge_version

    now = now or datetime.now(UTC)
    rows = db.scalars(
        select(VerdictAppeal)
        .where(VerdictAppeal.state == "upheld", VerdictAppeal.exported_at.is_(None))
        .order_by(VerdictAppeal.created_at)
    ).all()
    if not rows:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"appeals-{now.date().isoformat()}.jsonl"
    version = judge_version()
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            case = {
                "id": f"appeal-{row.id}",
                "surface": row.surface,
                "text": row.answer_text,
                "item": row.item,
                "was": (row.verdict_before or {}).get("outcome"),
                "expected": "right",
                "reason": row.reason,
                "judge_version": version,
                "appealed_at": row.created_at.isoformat() if row.created_at else None,
            }
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
            row.exported_at = now
            db.add(row)
    db.commit()
    return [path]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=CANDIDATES)
    args = parser.parse_args()
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        written = export(db, out_dir=args.out)
    finally:
        db.close()
    print("\n".join(str(path) for path in written) or "no upheld appeal to export")


if __name__ == "__main__":
    main()
