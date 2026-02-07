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


@celery_app.task(name="app.tasks.notifications.send_daily_srs_reminders")
def send_daily_srs_reminders() -> dict[str, int]:
    """Send push notifications to users with due SRS items."""
    from app.services.notification_service import NotificationService
    from app.services.unified_srs import UnifiedSRSService
    
    db = SessionLocal()
    notification_service = NotificationService(db)
    srs_service = UnifiedSRSService(db)
    
    try:
        # Get all users with push subscriptions
        users = db.scalars(
            select(User).where(User.is_active.is_(True))
        ).all()
        
        sent_count = 0
        
        for user in users:
            try:
                # Get due summary for user
                summary = srs_service.get_due_summary(user.id)
                total_due = summary.total_due
                
                if total_due == 0:
                    continue
                
                # Build message
                if total_due == 1:
                    message = "Tu as 1 révision qui t'attend ! 📚"
                elif total_due < 10:
                    message = f"Tu as {total_due} révisions à faire aujourd'hui ! 📚"
                else:
                    message = f"Tu as {total_due} révisions ! C'est parti ! 💪"
                
                # Send notification
                notification_service.send_notification(
                    user_id=user.id,
                    message=message,
                    title="Pratique quotidienne"
                )
                sent_count += 1
                
                logger.debug(
                    "SRS reminder sent",
                    user_id=str(user.id),
                    due_items=total_due,
                )
            except Exception as e:
                logger.warning(
                    "Failed to send SRS reminder",
                    user_id=str(user.id),
                    error=str(e),
                )
        
        logger.info(
            "Daily SRS reminders sent",
            total_users=len(users),
            notifications_sent=sent_count,
        )
        
        return {
            "total_users": len(users),
            "notifications_sent": sent_count,
        }
        
    finally:
        db.close()
