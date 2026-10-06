"""Seed the achievement catalogue into the database (WP-79).

Optional since WP-79: :meth:`AchievementService.ensure_catalogue` upserts the
same catalogue before every achievement read or check, so a deploy never needs
this script. It remains a way to seed ahead of the first request.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.services.achievement import CATALOGUE, AchievementDefinition, AchievementService


def get_default_achievements() -> list[AchievementDefinition]:
    """The one catalogue, as defined in ``app/services/achievement.py``."""

    return list(CATALOGUE)


def main() -> None:
    db = SessionLocal()
    try:
        AchievementService(db).ensure_catalogue()
        print(f"Achievement catalogue in place: {len(CATALOGUE)} entries.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
