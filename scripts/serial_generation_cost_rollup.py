"""Print weekly Serial Feuilleton generation cost estimates."""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from uuid import UUID

from app.db.session import SessionLocal
from app.services.serial_costs import SerialGenerationCostService, format_rollup_table


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Roll up Serial Feuilleton generation spend by learner and ISO week")
    parser.add_argument("--start-date", help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument("--end-date", help="Exclusive end date, YYYY-MM-DD")
    parser.add_argument("--weeks", type=int, default=4, help="Look back this many weeks when --start-date is omitted")
    parser.add_argument("--user-id", help="Limit to one learner UUID")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args()

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date) or (date.today() + timedelta(days=1))
    if start_date is None:
        start_date = end_date - timedelta(weeks=max(1, args.weeks))
    user_id = UUID(args.user_id) if args.user_id else None

    db = SessionLocal()
    try:
        rows = SerialGenerationCostService(db).weekly_rollup(
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
    finally:
        db.close()

    if args.format == "json":
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    print(format_rollup_table(rows))


if __name__ == "__main__":
    main()
