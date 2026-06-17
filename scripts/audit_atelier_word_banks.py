#!/usr/bin/env python
"""Audit latest LLM Atelier word-bank payloads for invalid token contracts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.db.session import SessionLocal
from app.services.atelier import ATELIER_GENERATOR_VERSION
from app.services.atelier_audit import audit_atelier_word_banks

DEFAULT_OUTPUT = Path("tests/fixtures/atelier_bad_word_banks.json")


def audit(*, generator_version: str | None, latest_per_concept: bool) -> list[dict[str, object]]:
    db = SessionLocal()
    try:
        return audit_atelier_word_banks(
            db,
            generator_version=generator_version,
            latest_per_concept=latest_per_concept,
        )
    finally:
        db.close()


def _print_table(flagged: list[dict[str, object]]) -> None:
    if not flagged:
        print("No invalid latest LLM word-bank items found.")
        return
    print(f"{'concept_id':<10} {'external_id':<18} {'source':<9} {'item_id':<28} reason")
    print("-" * 92)
    for row in flagged:
        print(
            f"{str(row.get('concept_id')):<10} "
            f"{str(row.get('external_id') or ''):<18} "
            f"{str(row.get('source') or ''):<9} "
            f"{str(row.get('item_id') or ''):<28} "
            f"{row.get('reason')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit latest LLM Atelier word-bank payloads")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JSON fixture path to write")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Audit all generated LLM rows instead of only the latest row per concept",
    )
    parser.add_argument(
        "--generator-version",
        default=ATELIER_GENERATOR_VERSION,
        help="Generator version to audit; pass an empty string to audit every version",
    )
    args = parser.parse_args()

    flagged = audit(
        generator_version=args.generator_version or None,
        latest_per_concept=not args.all,
    )
    _print_table(flagged)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(flagged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(flagged)} flagged rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
