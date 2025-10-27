"""Seed default achievements into the database."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.services.achievement import AchievementDefinition, AchievementService


def get_default_achievements() -> list[AchievementDefinition]:
    """Return the default achievement set."""

    return [
        AchievementDefinition(
            key="first_session",
            name="First Steps",
            description="Complete your first learning session",
            category="session",
            tier="bronze",
            xp_reward=50,
            icon_url="/icons/achievements/first_session.svg",
        ),
        AchievementDefinition(
            key="session_streak_3",
            name="Getting Started",
            description="Complete sessions 3 days in a row",
            category="streak",
            tier="bronze",
            xp_reward=100,
            icon_url="/icons/achievements/streak_3.svg",
        ),
        AchievementDefinition(
            key="session_streak_7",
            name="Week Warrior",
            description="Complete sessions 7 days in a row",
            category="streak",
            tier="silver",
            xp_reward=250,
            icon_url="/icons/achievements/streak_7.svg",
        ),
        AchievementDefinition(
            key="session_streak_30",
            name="Dedication Master",
            description="Complete sessions 30 days in a row",
            category="streak",
            tier="gold",
            xp_reward=1000,
            icon_url="/icons/achievements/streak_30.svg",
        ),
        AchievementDefinition(
            key="vocabulary_learner",
            name="Word Collector",
            description="Master 50 vocabulary words",
            category="vocabulary",
            tier="bronze",
            xp_reward=200,
            icon_url="/icons/achievements/vocab_50.svg",
        ),
        AchievementDefinition(
            key="vocabulary_expert",
            name="Vocabulary Expert",
            description="Master 200 vocabulary words",
            category="vocabulary",
            tier="silver",
            xp_reward=500,
            icon_url="/icons/achievements/vocab_200.svg",
        ),
        AchievementDefinition(
            key="vocabulary_master",
            name="Language Master",
            description="Master 500 vocabulary words",
            category="vocabulary",
            tier="gold",
            xp_reward=1500,
            icon_url="/icons/achievements/vocab_500.svg",
        ),
        AchievementDefinition(
            key="xp_bronze",
            name="Bronze Learner",
            description="Earn 500 total XP",
            category="xp",
            tier="bronze",
            xp_reward=100,
            icon_url="/icons/achievements/xp_bronze.svg",
        ),
        AchievementDefinition(
            key="xp_silver",
            name="Silver Scholar",
            description="Earn 2,000 total XP",
            category="xp",
            tier="silver",
            xp_reward=300,
            icon_url="/icons/achievements/xp_silver.svg",
        ),
        AchievementDefinition(
            key="xp_gold",
            name="Golden Polyglot",
            description="Earn 5,000 total XP",
            category="xp",
            tier="gold",
            xp_reward=1000,
            icon_url="/icons/achievements/xp_gold.svg",
        ),
        AchievementDefinition(
            key="accuracy_perfectionist",
            name="Perfectionist",
            description="Complete 100 sessions with 95%+ accuracy",
            category="accuracy",
            tier="gold",
            xp_reward=2000,
            icon_url="/icons/achievements/perfectionist.svg",
        ),
        AchievementDefinition(
            key="review_champion",
            name="Review Champion",
            description="Complete 1,000 vocabulary reviews",
            category="session",
            tier="gold",
            xp_reward=800,
            icon_url="/icons/achievements/review_champion.svg",
        ),
    ]


def main() -> None:
    """Seed achievements into the database."""

    db = SessionLocal()
    try:
        service = AchievementService(db)
        definitions = get_default_achievements()

        print(f"Seeding {len(definitions)} achievement definitions...")
        service.seed_achievements(definitions)

        print("✓ Achievement seeding complete!")
        print(f"  Total achievements: {len(definitions)}")
        print("  Categories: session, streak, vocabulary, xp, accuracy")

    except Exception as exc:  # pragma: no cover - CLI feedback
        print(f"✗ Error seeding achievements: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
