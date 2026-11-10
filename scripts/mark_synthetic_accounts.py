"""Mark walk and test accounts as synthetic, so the cohort view leaves them out (S6).

Which accounts are synthetic is the owner's call; nothing marks one by guessing.

    venv/bin/python scripts/mark_synthetic_accounts.py walk@example.com tester@example.com
    venv/bin/python scripts/mark_synthetic_accounts.py --unmark someone@example.com
    venv/bin/python scripts/mark_synthetic_accounts.py --list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models.user import User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("emails", nargs="*")
    parser.add_argument("--unmark", action="store_true", help="Set the flag back to false.")
    parser.add_argument("--list", action="store_true", help="Print the accounts marked synthetic.")
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        if args.list:
            for user in db.query(User).filter(User.is_synthetic.is_(True)).order_by(User.email):
                print(user.email)
            return 0
        missing = []
        for email in args.emails:
            user = db.query(User).filter(User.email == email.strip().lower()).one_or_none()
            if user is None:
                missing.append(email)
                continue
            user.is_synthetic = not args.unmark
            print(f"{email}: {'not synthetic' if args.unmark else 'synthetic'}")
        db.commit()
    for email in missing:
        print(f"{email}: no such account", file=sys.stderr)
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
