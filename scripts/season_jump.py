#!/usr/bin/env python
"""Put a TEST learner on season 1 at a given story day (WP-111), for the owner's play.

    venv/bin/python scripts/season_jump.py \\
        --database-url postgresql://localhost/atelier_e2e_0926 \\
        --email qa-walk-0928a@example.com --day 8

The learner's next story day becomes season day ``--day`` (8 = T2 Day A, «Là-haut»):
their thread moves to the season-1 world, the days before it are recorded as played
(the bible's calendar, no weekend flex), every tentpole already passed leaves its fixed
facts, and the flags take their defaults unless ``--flag s1.fire_photo=margaux`` says
otherwise (repeatable; ``true``/``false`` for booleans). An open chapter is closed so
the day opens cleanly. Nothing is deleted.

It refuses the owner's live ``language_learning`` database, and it does nothing without
``--apply`` (the default prints what it would write).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def _parse_flag(raw: str) -> tuple[str, object]:
    key, _, value = raw.partition("=")
    if not key or not _:
        raise SystemExit(f"--flag needs key=value, got {raw!r}")
    lowered = value.strip().casefold()
    return key.strip(), True if lowered == "true" else False if lowered == "false" else value.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--day", type=int, required=True, help="the season day to play next (1..59)")
    parser.add_argument("--season", default="s1")
    parser.add_argument("--flag", action="append", default=[], help="key=value, repeatable")
    parser.add_argument("--apply", action="store_true", help="write the change (default: print it)")
    args = parser.parse_args()
    if "language_learning" in args.database_url:
        raise SystemExit("Refusing the owner's live language_learning database.")
    os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models.user import User
    from app.services.season.admin import jump_to_day

    url = args.database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    with Session(create_engine(url)) as db:
        user = db.scalar(select(User).where(User.email == args.email))
        if user is None:
            raise SystemExit(f"no user {args.email}")
        summary = jump_to_day(
            db, user, day=args.day, season_id=args.season, flags=dict(_parse_flag(raw) for raw in args.flag)
        )
        print(json.dumps({"user": args.email, **summary}, ensure_ascii=False, indent=1))
        if not args.apply:
            print("(dry run: add --apply to write)")
            db.rollback()
            return 0
        db.commit()
        print(f"{args.email} now plays season day {args.day} ({summary['next']['key']}) next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
