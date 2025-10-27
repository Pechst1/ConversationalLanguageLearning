"""CLI script to manually trigger achievement checks."""
from __future__ import annotations

import argparse

from app.tasks.achievements import check_all_achievements, check_user_achievements


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manually trigger achievement checks",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        help="Check achievements for specific user only",
    )
    parser.add_argument(
        "--async",
        action="store_true",
        dest="use_async",
        help="Queue task asynchronously instead of running immediately",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check achievements for all active users",
    )

    args = parser.parse_args()

    if args.all:
        print("Checking achievements for all active users...")
        if args.use_async:
            task = check_all_achievements.apply_async()
            print(f"Task queued: {task.id}")
        else:
            result = check_all_achievements.run()
            print(f"Result: {result}")
    elif args.user_id:
        print(f"Checking achievements for user {args.user_id}")
        if args.use_async:
            task = check_user_achievements.apply_async(args=(args.user_id,))
            print(f"Task queued: {task.id}")
        else:
            result = check_user_achievements.run(args.user_id)
            print(f"Result: {result}")
    else:
        parser.error("Specify --user-id or --all")


if __name__ == "__main__":
    main()
