"""Celery tasks for achievement processing."""
from __future__ import annotations

from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.achievement import AchievementService


@celery_app.task(name="app.tasks.achievements.check_user_achievements")
def check_user_achievements(user_id: str) -> dict[str, int | list[str] | str]:
    """Check and unlock achievements for a specific user."""

    db = SessionLocal()
    try:
        try:
            user_uuid = UUID(user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid user ID: {user_id}") from exc

        user = db.get(User, user_uuid)
        if not user:
            raise ValueError(f"User {user_id} not found")

        service = AchievementService(db)
        newly_unlocked = service.check_and_unlock(user=user)

        logger.info(
            "User achievement check completed",
            user_id=user_id,
            unlocked_count=len(newly_unlocked),
        )

        return {
            "user_id": user_id,
            "newly_unlocked": len(newly_unlocked),
            "achievement_keys": [a.achievement_key for a in newly_unlocked],
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Achievement check failed", user_id=user_id, error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.achievements.check_all_achievements")
def check_all_achievements() -> dict[str, int]:
    """Check achievements for all active users (periodic task)."""

    db = SessionLocal()
    try:
        active_users = db.scalars(select(User).where(User.is_active.is_(True))).all()

        total_checked = 0
        total_unlocked = 0

        for user in active_users:
            try:
                service = AchievementService(db)
                newly_unlocked = service.check_and_unlock(user=user)
                total_checked += 1
                total_unlocked += len(newly_unlocked)

                if total_checked % 100 == 0:
                    logger.info(
                        "Achievement check progress",
                        checked=total_checked,
                        total=len(active_users),
                    )

            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(
                    "Achievement check failed for user",
                    user_id=str(user.id),
                    error=str(exc),
                )
                continue

        logger.info(
            "Bulk achievement check completed",
            users_checked=total_checked,
            total_unlocked=total_unlocked,
        )

        return {
            "users_checked": total_checked,
            "total_unlocked": total_unlocked,
        }

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Bulk achievement check failed", error=str(exc))
        raise
    finally:
        db.close()
