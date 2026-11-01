#!/usr/bin/env python3
"""Package O-1 — l'or in shadow: the §18 report, from the ledger, on demand.

The nightly job (``app.tasks.gold.nightly_report``) keeps the same report as a
``gold_shadow_report`` pilot event; this prints it now, for the owner or the
nightly loop. Read-only.

Usage::

    .venv/bin/python scripts/gold_ledger_report.py              # last 14 days, markdown
    .venv/bin/python scripts/gold_ledger_report.py --days 7 --json
"""
from __future__ import annotations

import argparse
import json

from app.db.session import SessionLocal
from app.services.gold_report import build_gold_report, report_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--days", type=int, default=14, help="local days to cover (1–120)")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        report = build_gold_report(db, days=args.days)
    finally:
        db.close()
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str) if args.json else report_markdown(report))


if __name__ == "__main__":
    main()
