"""Achievement service for gamification and learner motivation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.progress import UserVocabularyProgress
from app.db.models.session import LearningSession
from app.db.models.user import User
from app.utils.cache import build_cache_key, cache_backend

AchievementCategory = Literal["streak", "vocabulary", "xp", "session", "accuracy"]


@dataclass
class AchievementDefinition:
    """Template for defining achievements."""

    key: str
    name: str
    description: str
    category: AchievementCategory
    tier: str
    xp_reward: int
    icon_url: str | None = None
    unlock_criteria: Dict[str, Any] | None = None


@dataclass
class AchievementProgress:
    """Current progress toward an achievement."""

    achievement_id: int
    achievement_key: str
    name: str
    description: str | None
    tier: str
    xp_reward: int
    icon_url: str | None
    current_progress: int
    target_progress: int
    completed: bool
    unlocked_at: datetime | None


class AchievementNotFoundError(ValueError):
    """Raised when an achievement cannot be located."""


class AchievementService:
    """Manage achievement unlocks and progress tracking."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Achievement definition helpers
    # ------------------------------------------------------------------
    def seed_achievements(self, definitions: List[AchievementDefinition]) -> None:
        """Seed achievement templates into the database."""

        for defn in definitions:
            existing = (
                self.db.query(Achievement)
                .filter(Achievement.achievement_key == defn.key)
                .first()
            )
            if existing:
                existing.name = defn.name
                existing.description = defn.description
                existing.tier = defn.tier
                existing.xp_reward = defn.xp_reward
                existing.icon_url = defn.icon_url
            else:
                achievement = Achievement(
                    achievement_key=defn.key,
                    name=defn.name,
                    description=defn.description,
                    tier=defn.tier,
                    xp_reward=defn.xp_reward,
                    icon_url=defn.icon_url,
                )
                self.db.add(achievement)
        self.db.commit()
        cache_backend.invalidate("achievements:list", key="all")
        cache_backend.invalidate("achievements:user", prefix="")

    def list_all_achievements(self) -> List[Achievement]:
        """Return all achievement templates."""

        cache_key = "all"
        cached = cache_backend.get("achievements:list", cache_key)
        if cached is not None:
            return [Achievement(**item) for item in cached]

        achievements = self.db.query(Achievement).order_by(Achievement.id).all()
        payload = [
            {
                "id": a.id,
                "achievement_key": a.achievement_key,
                "name": a.name,
                "description": a.description,
                "tier": a.tier,
                "xp_reward": a.xp_reward,
                "icon_url": a.icon_url,
            }
            for a in achievements
        ]
        cache_backend.set("achievements:list", cache_key, payload, ttl_seconds=3600)
        return achievements

    # ------------------------------------------------------------------
    # User achievement tracking
    # ------------------------------------------------------------------
    def get_user_achievements(
        self, user_id: uuid.UUID, *, include_locked: bool = False
    ) -> List[AchievementProgress]:
        """Return user's achievement progress."""

        cache_key = build_cache_key(user_id=str(user_id), include_locked=include_locked)
        cached = cache_backend.get("achievements:user", cache_key)
        if cached is not None:
            items: List[AchievementProgress] = []
            for item in cached:
                unlocked_at = (
                    datetime.fromisoformat(item["unlocked_at"])
                    if item["unlocked_at"]
                    else None
                )
                items.append(
                    AchievementProgress(
                        achievement_id=item["achievement_id"],
                        achievement_key=item["achievement_key"],
                        name=item["name"],
                        description=item["description"],
                        tier=item["tier"],
                        xp_reward=item["xp_reward"],
                        icon_url=item["icon_url"],
                        current_progress=item["current_progress"],
                        target_progress=item["target_progress"],
                        completed=item["completed"],
                        unlocked_at=unlocked_at,
                    )
                )
            return items

        query = (
            self.db.query(UserAchievement, Achievement)
            .join(Achievement, UserAchievement.achievement_id == Achievement.id)
            .filter(UserAchievement.user_id == user_id)
        )

        if not include_locked:
            query = query.filter(UserAchievement.completed.is_(True))

        results = query.all()

        progress_items: List[AchievementProgress] = []
        for user_achievement, achievement in results:
            target = self._calculate_target_progress(achievement.achievement_key)
            progress_items.append(
                AchievementProgress(
                    achievement_id=achievement.id,
                    achievement_key=achievement.achievement_key,
                    name=achievement.name,
                    description=achievement.description,
                    tier=achievement.tier,
                    xp_reward=achievement.xp_reward,
                    icon_url=achievement.icon_url,
                    current_progress=user_achievement.progress,
                    target_progress=target,
                    completed=user_achievement.completed,
                    unlocked_at=
                        user_achievement.unlocked_at if user_achievement.completed else None,
                )
            )

        if include_locked:
            all_achievements = self.list_all_achievements()
            unlocked_ids = {item.achievement_id for item in progress_items}
            for achievement in all_achievements:
                if achievement.id in unlocked_ids:
                    continue
                target = self._calculate_target_progress(achievement.achievement_key)
                progress_items.append(
                    AchievementProgress(
                        achievement_id=achievement.id,
                        achievement_key=achievement.achievement_key,
                        name=achievement.name,
                        description=achievement.description,
                        tier=achievement.tier,
                        xp_reward=achievement.xp_reward,
                        icon_url=achievement.icon_url,
                        current_progress=0,
                        target_progress=target,
                        completed=False,
                        unlocked_at=None,
                    )
                )

        payload = [
            {
                "achievement_id": item.achievement_id,
                "achievement_key": item.achievement_key,
                "name": item.name,
                "description": item.description,
                "tier": item.tier,
                "xp_reward": item.xp_reward,
                "icon_url": item.icon_url,
                "current_progress": item.current_progress,
                "target_progress": item.target_progress,
                "completed": item.completed,
                "unlocked_at": item.unlocked_at.isoformat() if item.unlocked_at else None,
            }
            for item in progress_items
        ]
        cache_backend.set("achievements:user", cache_key, payload, ttl_seconds=300)
        return progress_items

    def _calculate_target_progress(self, achievement_key: str) -> int:
        """Return the target progress value for an achievement."""

        targets = {
            "first_session": 1,
            "session_streak_3": 3,
            "session_streak_7": 7,
            "session_streak_30": 30,
            "vocabulary_learner": 50,
            "vocabulary_expert": 200,
            "vocabulary_master": 500,
            "xp_bronze": 500,
            "xp_silver": 2000,
            "xp_gold": 5000,
            "accuracy_perfectionist": 100,
            "review_champion": 1000,
        }
        return targets.get(achievement_key, 1)

    # ------------------------------------------------------------------
    # Achievement unlock logic
    # ------------------------------------------------------------------
    def check_and_unlock(self, *, user: User) -> List[Achievement]:
        """Check all unlockable achievements and grant them to the user."""

        newly_unlocked: List[Achievement] = []

        checks = [
            self._check_streak_achievements,
            self._check_vocabulary_achievements,
            self._check_xp_achievements,
            self._check_session_achievements,
            self._check_accuracy_achievements,
        ]

        for check_fn in checks:
            unlocked = check_fn(user)
            newly_unlocked.extend(unlocked)

        if newly_unlocked:
            self._invalidate_user_cache(user.id)

        return newly_unlocked

    def _check_streak_achievements(self, user: User) -> List[Achievement]:
        """Check streak-based achievements."""

        unlocked: List[Achievement] = []
        streak_checks = [
            ("session_streak_3", 3),
            ("session_streak_7", 7),
            ("session_streak_30", 30),
        ]

        for key, required_streak in streak_checks:
            if user.current_streak >= required_streak:
                achievement = self._try_unlock(user.id, key, user.current_streak)
                if achievement:
                    unlocked.append(achievement)

        return unlocked

    def _check_vocabulary_achievements(self, user: User) -> List[Achievement]:
        """Check vocabulary mastery achievements."""

        mastered_count = (
            self.db.query(func.count(UserVocabularyProgress.id))
            .filter(
                UserVocabularyProgress.user_id == user.id,
                UserVocabularyProgress.state == "mastered",
            )
            .scalar()
        )

        unlocked: List[Achievement] = []
        vocab_checks = [
            ("vocabulary_learner", 50),
            ("vocabulary_expert", 200),
            ("vocabulary_master", 500),
        ]

        for key, required_count in vocab_checks:
            if mastered_count >= required_count:
                achievement = self._try_unlock(user.id, key, mastered_count)
                if achievement:
                    unlocked.append(achievement)

        return unlocked

    def _check_xp_achievements(self, user: User) -> List[Achievement]:
        """Check XP milestone achievements."""

        unlocked: List[Achievement] = []
        xp_checks = [
            ("xp_bronze", 500),
            ("xp_silver", 2000),
            ("xp_gold", 5000),
        ]

        for key, required_xp in xp_checks:
            if user.total_xp >= required_xp:
                achievement = self._try_unlock(user.id, key, user.total_xp)
                if achievement:
                    unlocked.append(achievement)

        return unlocked

    def _check_session_achievements(self, user: User) -> List[Achievement]:
        """Check session completion achievements."""

        session_count = (
            self.db.query(func.count(LearningSession.id))
            .filter(
                LearningSession.user_id == user.id,
                LearningSession.status == "completed",
            )
            .scalar()
        )

        if session_count >= 1:
            achievement = self._try_unlock(user.id, "first_session", session_count)
            if achievement:
                return [achievement]

        return []

    def _check_accuracy_achievements(self, user: User) -> List[Achievement]:
        """Check accuracy-based achievements."""

        perfect_sessions = (
            self.db.query(func.count(LearningSession.id))
            .filter(
                LearningSession.user_id == user.id,
                LearningSession.accuracy_rate >= 0.95,
                LearningSession.status == "completed",
            )
            .scalar()
        )

        if perfect_sessions >= 100:
            achievement = self._try_unlock(
                user.id, "accuracy_perfectionist", perfect_sessions
            )
            if achievement:
                return [achievement]

        return []

    def _try_unlock(
        self, user_id: uuid.UUID, achievement_key: str, current_progress: int
    ) -> Achievement | None:
        """Attempt to unlock an achievement for a user."""

        achievement = (
            self.db.query(Achievement)
            .filter(Achievement.achievement_key == achievement_key)
            .first()
        )

        if not achievement:
            return None

        existing = (
            self.db.query(UserAchievement)
            .filter(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.achievement_id == achievement.id,
                    UserAchievement.completed.is_(True),
                )
            )
            .first()
        )

        if existing:
            return None

        user_achievement = (
            self.db.query(UserAchievement)
            .filter(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.achievement_id == achievement.id,
                )
            )
            .first()
        )

        if not user_achievement:
            user_achievement = UserAchievement(
                user_id=user_id,
                achievement_id=achievement.id,
                progress=current_progress,
                completed=True,
                unlocked_at=datetime.now(timezone.utc),
            )
            self.db.add(user_achievement)
        else:
            user_achievement.progress = current_progress
            user_achievement.completed = True
            user_achievement.unlocked_at = datetime.now(timezone.utc)

        user = self.db.get(User, user_id)
        if user:
            user.total_xp += achievement.xp_reward

        self.db.commit()
        return achievement

    def _invalidate_user_cache(self, user_id: uuid.UUID) -> None:
        """Clear cached achievement data for a user."""

        for include_locked in (False, True):
            cache_backend.invalidate(
                "achievements:user",
                key=build_cache_key(user_id=str(user_id), include_locked=include_locked),
            )


__all__ = [
    "AchievementDefinition",
    "AchievementProgress",
    "AchievementService",
    "AchievementNotFoundError",
]
