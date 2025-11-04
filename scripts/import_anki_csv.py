"""
Import Anki CSV into the app for a specific user.

Usage examples:

  python scripts/import_anki_csv.py --user-email learner@example.com \
      --csv Anki_cards___2025-11-01T13-09-36.csv --preserve-scheduling true

  python scripts/import_anki_csv.py --user-id 00000000-0000-0000-0000-000000000000 \
      --csv /path/to/export.csv --deck-name "Französisch 5000"

This script uses the same AnkiImportService as the API endpoint, so parsing and
scheduling preservation behave identically to uploading via /api/v1/anki/import.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.user import User
from app.services.anki_import import AnkiImportService, AnkiImportError


def _load_user(db: Session, *, user_id: Optional[str], user_email: Optional[str]) -> User:
    if user_id:
        user = db.get(User, user_id)
        if not user:
            raise SystemExit(f"No user found with id: {user_id}")
        return user
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            raise SystemExit(f"No user found with email: {user_email}")
        return user
    raise SystemExit("You must supply either --user-id or --user-email")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Anki CSV for a user")
    parser.add_argument("--csv", required=True, help="Path to Anki CSV export file")
    parser.add_argument("--user-id", help="User UUID to import for")
    parser.add_argument("--user-email", help="User email to import for")
    parser.add_argument("--deck-name", default=None, help="Override deck name for imported cards")
    parser.add_argument(
        "--preserve-scheduling",
        default="true",
        choices=["true", "false", "1", "0"],
        help="Preserve Anki scheduling data (default: true)",
    )

    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV file not found: {csv_path}")

    preserve = str(args.preserve_scheduling).lower() in {"true", "1", "yes", "y"}

    # Open DB session
    db = SessionLocal()
    try:
        user = _load_user(db, user_id=args.user_id, user_email=args.user_email)
        print(f"Importing Anki CSV for user {user.email} ({user.id}) from {csv_path}")

        # Read content as UTF-8 with replacement for any stray bytes
        try:
            with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
                csv_content = f.read()
        except Exception as e:  # pragma: no cover - CLI convenience
            raise SystemExit(f"Failed to read CSV: {e}")

        importer = AnkiImportService(db)
        try:
            stats = importer.import_cards_from_csv(
                csv_content=csv_content,
                user_id=str(user.id),
                deck_name=args.deck_name,
                preserve_scheduling=preserve,
            )
        except AnkiImportError as e:
            raise SystemExit(f"Import failed: {e}")

        print("Import completed:")
        print(f"  total processed:      {stats.get('total', 0)}")
        print(f"  imported:            {stats.get('imported', 0)}")
        print(f"  paired (both sides): {stats.get('paired', 0)}")
        print(f"  FR → DE:             {stats.get('french_to_german', 0)}")
        print(f"  DE → FR:             {stats.get('german_to_french', 0)}")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()

