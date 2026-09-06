#!/usr/bin/env python3
"""Print one day of pilot activity, spend, and failures.

The daily-journey section (WP-11) is part of the same report: start/completion/
early-stop counts, step drop-off, help use, the measured active-duration
distribution, provider waiting, retry and fallback rates, and cost coverage.
Every rate carries its denominator, and a day with too few journeys prints an
explicit insufficient-data line instead of a precise-looking number.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.db.session import SessionLocal
from app.services.pilot_events import PilotEventService, format_daily_digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--user-id")
    parser.add_argument(
        "--journey-only",
        action="store_true",
        help="Print only the daily-journey section (WP-11 release metrics).",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        report = PilotEventService(db).daily_rollup(args.day, user_id=args.user_id)
    if args.journey_only:
        from app.services.journey_events import format_journey_digest

        print("\n".join(format_journey_digest(report["journey"])))
        return
    print(format_daily_digest(report))


if __name__ == "__main__":
    main()
