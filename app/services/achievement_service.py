"""Achievement service for grammar-related achievements and streak tracking."""
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models.achievement import Achievement, UserAchievement
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.user import User

if TYPE_CHECKING:
    pass


class AchievementService:
    """Service for managing grammar achievements and streaks."""

    def __init__(self, db: Session):
        self.db = db

    def update_grammar_streak(self, user: User) -> dict:
        """
        Update user's grammar streak after a review.

        Returns dict with streak info and whether streak milestone was reached.
        """
        today = date.today()

        # Check if this is a new day for grammar
        if user.grammar_last_review_date == today:
            # Already reviewed today, no streak update needed
            return {
                "streak_days": user.grammar_streak_days or 0,
                "is_new_day": False,
                "milestone_reached": None,
            }

        # Calculate streak
        if user.grammar_last_review_date is None:
            # First ever grammar review
            new_streak = 1
        elif (today - user.grammar_last_review_date).days == 1:
            # Consecutive day - extend streak
            new_streak = (user.grammar_streak_days or 0) + 1
        elif (today - user.grammar_last_review_date).days > 1:
            # Missed a day - reset streak
            new_streak = 1
        else:
            # Same day (shouldn't reach here) or future date
            new_streak = user.grammar_streak_days or 1

        # Update user
        user.grammar_streak_days = new_streak
        user.grammar_last_review_date = today

        # Update longest streak if needed
        if new_streak > (user.grammar_longest_streak or 0):
            user.grammar_longest_streak = new_streak

        self.db.commit()

        # Check for milestone (7, 30, etc.)
        milestone_reached = None
        if new_streak in [7, 30, 60, 100, 365]:
            milestone_reached = new_streak

        return {
            "streak_days": new_streak,
            "is_new_day": True,
            "milestone_reached": milestone_reached,
        }

    def check_and_unlock_achievements(
        self, user: User, score: float | None = None, concept: GrammarConcept | None = None
    ) -> list[Achievement]:
        """
        Check for any achievements that should be unlocked after a grammar review.

        Args:
            user: The user to check achievements for
            score: The score from the last review (0-10)
            concept: The concept that was just reviewed

        Returns:
            List of newly unlocked Achievement objects
        """
        unlocked = []

        # Get all grammar achievements the user hasn't unlocked yet
        existing_achievement_ids = self.db.execute(
            select(UserAchievement.achievement_id).where(
                UserAchievement.user_id == user.id,
                UserAchievement.completed == True
            )
        ).scalars().all()

        achievements = self.db.execute(
            select(Achievement).where(
                Achievement.category == "grammar",
                ~Achievement.id.in_(existing_achievement_ids) if existing_achievement_ids else True
            )
        ).scalars().all()

        for achievement in achievements:
            should_unlock = self._check_achievement_trigger(user, achievement, score, concept)

            if should_unlock:
                # Create user achievement
                user_achievement = UserAchievement(
                    user_id=user.id,
                    achievement_id=achievement.id,
                    completed=True,
                    progress=achievement.trigger_value or 1,
                    unlocked_at=datetime.now(timezone.utc),
                )
                self.db.add(user_achievement)

                # Award XP
                user.total_xp = (user.total_xp or 0) + (achievement.xp_reward or 0)

                unlocked.append(achievement)

        if unlocked:
            self.db.commit()

        return unlocked

    def _check_achievement_trigger(
        self, user: User, achievement: Achievement, score: float | None, concept: GrammarConcept | None
    ) -> bool:
        """Check if a specific achievement's trigger condition is met."""
        trigger_type = achievement.trigger_type
        trigger_value = achievement.trigger_value

        if not trigger_type:
            return False

        if trigger_type == "grammar_review":
            # First grammar review achievement
            count = self.db.execute(
                select(func.count(UserGrammarProgress.id)).where(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.reps > 0
                )
            ).scalar()
            return count >= trigger_value

        elif trigger_type == "streak":
            # Streak milestones
            return (user.grammar_streak_days or 0) >= trigger_value

        elif trigger_type == "perfect_score":
            # Perfect score achievement
            return score is not None and score >= trigger_value

        elif trigger_type == "level_master":
            # Master all concepts in a level
            level_map = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1", 6: "C2"}
            level = level_map.get(trigger_value)
            if not level:
                return False

            # Count total concepts in level
            total_in_level = self.db.execute(
                select(func.count(GrammarConcept.id)).where(
                    GrammarConcept.level == level
                )
            ).scalar()

            if total_in_level == 0:
                return False

            # Count mastered concepts in level
            mastered_count = self.db.execute(
                select(func.count(UserGrammarProgress.id)).where(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.state == "gemeistert",
                    UserGrammarProgress.concept_id.in_(
                        select(GrammarConcept.id).where(GrammarConcept.level == level)
                    )
                )
            ).scalar()

            return mastered_count >= total_in_level

        elif trigger_type == "error_crusher":
            # Master concepts that came from errors
            # This would need integration with the error tracking system
            # For now, check if user has mastered at least trigger_value concepts
            mastered_count = self.db.execute(
                select(func.count(UserGrammarProgress.id)).where(
                    UserGrammarProgress.user_id == user.id,
                    UserGrammarProgress.state == "gemeistert"
                )
            ).scalar()
            return mastered_count >= trigger_value

        return False

    def get_user_achievements(self, user: User, category: str | None = None) -> list[dict]:
        """
        Get all achievements with user unlock status.

        Returns list of dicts with achievement info and unlock status.
        """
        query = select(Achievement)
        if category:
            query = query.where(Achievement.category == category)
        query = query.order_by(Achievement.tier.desc(), Achievement.xp_reward.desc())

        achievements = self.db.execute(query).scalars().all()

        # Get user's unlocked achievements
        user_achievements = self.db.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == user.id
            )
        ).scalars().all()

        unlocked_map = {ua.achievement_id: ua for ua in user_achievements}

        result = []
        for achievement in achievements:
            user_ach = unlocked_map.get(achievement.id)
            result.append({
                "id": achievement.id,
                "key": achievement.achievement_key,
                "name": achievement.name,
                "description": achievement.description,
                "icon_url": achievement.icon_url,
                "xp_reward": achievement.xp_reward,
                "tier": achievement.tier,
                "category": achievement.category,
                "is_unlocked": user_ach is not None and user_ach.completed,
                "unlocked_at": user_ach.unlocked_at.isoformat() if user_ach and user_ach.unlocked_at else None,
                "progress": user_ach.progress if user_ach else 0,
            })

        return result

    def get_grammar_streak_info(self, user: User) -> dict:
        """Get user's current grammar streak information."""
        return {
            "current_streak": user.grammar_streak_days or 0,
            "longest_streak": user.grammar_longest_streak or 0,
            "last_review_date": user.grammar_last_review_date.isoformat() if user.grammar_last_review_date else None,
            "is_active_today": user.grammar_last_review_date == date.today() if user.grammar_last_review_date else False,
        }


__all__ = ["AchievementService"]
