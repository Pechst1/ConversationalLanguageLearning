"""Celery tasks for user notifications and reminders."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models.user import User
from app.db.session import SessionLocal


@celery_app.task(name="app.tasks.notifications.send_streak_reminders")
def send_streak_reminders() -> dict[str, int]:
    """Send reminders to users with active streaks who missed today."""

    db = SessionLocal()
    today = date.today()
    yesterday = today - timedelta(days=1)

    try:
        users = db.scalars(
            select(User)
            .where(User.is_active.is_(True))
            .where(User.notifications_enabled.is_(True))
            .where(User.current_streak >= 3)
            .where(User.last_activity_date == yesterday)
        ).all()

        notification_count = 0

        for user in users:
            if user.preferred_session_time is not None:
                preferred_hour = user.preferred_session_time.hour
                current_hour = datetime.now(timezone.utc).hour
                if abs(current_hour - preferred_hour) > 2:
                    continue

            logger.info(
                "Streak reminder needed",
                user_id=str(user.id),
                email=user.email,
                current_streak=user.current_streak,
            )
            notification_count += 1

        logger.info(
            "Streak reminders processed",
            total_users=len(users),
            notifications_sent=notification_count,
        )

        return {
            "eligible_users": len(users),
            "notifications_sent": notification_count,
        }

    finally:
        db.close()
