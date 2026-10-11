#!/usr/bin/env python
"""WP-115e: vocabulary retention, read honestly from the review log.

    venv/bin/python scripts/vocab_retention_report.py \\
        --database-url postgresql://localhost/atelier_e2e_0926 --days 28 [--email a@b.c]

Prints JSON: calibration (predicted vs actual recall), the forgetting curve by lag
(overall, per format, per place), the story-vs-cahier pilot on hard words, and load.
Read-only. It refuses the owner's live ``language_learning`` database unless
``--allow-live`` is given (the owner runs that one).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--email", action="append", default=[], help="limit to these learners (repeatable)")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if "language_learning" in args.database_url and not args.allow_live:
        raise SystemExit("Refusing the live language_learning database without --allow-live.")
    os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models.user import User
    from app.services.vocab_metrics import retention_report

    url = args.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    with Session(create_engine(url)) as db:
        user_ids = None
        if args.email:
            user_ids = list(db.scalars(select(User.id).where(User.email.in_(args.email))))
        print(json.dumps(retention_report(db, days=args.days, user_ids=user_ids), ensure_ascii=False, indent=1))
        db.rollback()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
