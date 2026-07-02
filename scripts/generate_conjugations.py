#!/usr/bin/env python3
"""Generate deterministic French conjugation rows for vocabulary verbs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.models.vocabulary import VerbConjugation  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.conjugation import ConjugationService  # noqa: E402


def generate(*, limit: int | None, essentials_only: bool, dry_run: bool) -> dict[str, int | bool]:
    db = SessionLocal()
    try:
        service = ConjugationService(db)
        changed = service.seed_essential_irregulars()
        if not essentials_only:
            changed += service.ensure_verb_rows_from_vocabulary(limit=limit)
        total_rows = db.query(VerbConjugation).count()
        irregular_rows = db.query(VerbConjugation).filter(VerbConjugation.is_irregular.is_(True)).count()
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "changed_rows": changed,
            "total_rows": total_rows,
            "irregular_rows": irregular_rows,
            "dry_run": dry_run,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate verb_conjugations for drills and coverage.")
    parser.add_argument("--limit", type=int, default=None, help="Optional enriched vocabulary verb limit.")
    parser.add_argument("--essentials-only", action="store_true", help="Only seed curated essential irregulars.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and roll back changes.")
    args = parser.parse_args()
    report = generate(limit=args.limit, essentials_only=args.essentials_only, dry_run=args.dry_run)
    for key, value in report.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
