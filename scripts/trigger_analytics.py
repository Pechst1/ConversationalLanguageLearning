"""CLI script to manually trigger analytics snapshot generation."""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.tasks.analytics import generate_daily_snapshots, generate_user_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually trigger analytics snapshot generation",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD format (default: yesterday)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Generate snapshot for specific user only",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        dest="use_async",
        help="Queue task asynchronously instead of running immediately",
    )

    args = parser.parse_args()

    target_date = args.date or (date.today() - timedelta(days=1)).isoformat()

    if args.user_id:
        print(f"Generating snapshot for user {args.user_id} on {target_date}")
        if args.use_async:
            task = generate_user_snapshot.apply_async(args=(args.user_id, target_date))
            print(f"Task queued: {task.id}")
        else:
            result = generate_user_snapshot.run(args.user_id, target_date)
            print(f"Result: {result}")
    else:
        print(f"Generating snapshots for all users on {target_date}")
        if args.use_async:
            task = generate_daily_snapshots.apply_async(args=(target_date,))
            print(f"Task queued: {task.id}")
        else:
            result = generate_daily_snapshots.run(target_date)
            print(f"Result: {result}")


if __name__ == "__main__":
    main()
