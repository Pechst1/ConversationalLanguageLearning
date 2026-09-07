"""Celery tasks for user notifications and reminders."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models.pilot_event import PilotEvent
from app.db.models.push_subscription import PushSubscription
from app.db.models.serial import SerialThread
from app.db.models.user import User
from app.db.session import SessionLocal

PARIS_TZ = ZoneInfo("Europe/Paris")
FRENCH_MONTHS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _preferred_notification_minute(user: User) -> int:
    value = str(getattr(user, "reminder_time", "") or "").strip()
    try:
        hour, minute = (int(part) for part in value.split(":", 1))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    except (TypeError, ValueError):
        pass
    preferred = getattr(user, "preferred_session_time", None)
    return preferred.hour * 60 + preferred.minute if preferred else 9 * 60


def _morning_copy(db, user: User, today: date) -> tuple[str, str]:
    """Build truthful copy only from the currently persisted prescription."""
    from app.services.atelier import AtelierScheduler
    from app.services.daily_words import DailyWordSlateService
    from app.services.serial import SerialThreadService

    selections = AtelierScheduler(db).select_today(user)
    slate = DailyWordSlateService(db).get_or_create(user=user)
    thread = db.scalar(
        select(SerialThread)
        .where(SerialThread.user_id == user.id, SerialThread.status == "active")
        .order_by(SerialThread.updated_at.desc())
    )
    character_name = ""
    if thread:
        cast = SerialThreadService(db).cast_payload(thread)
        current = SerialThreadService(db).current_episode(thread)
        required = [
            str(value)
            for value in ((current.brief_payload or {}).get("required_cast") or [])
            if str(value).strip()
        ] if current else []
        by_id = {str(member.get("id")): member for member in cast}
        member = next((by_id[value] for value in required if value in by_id), cast[0] if cast else None)
        character_name = str((member or {}).get("name") or "").strip()
    title = f"Votre édition du {today.day} {FRENCH_MONTHS[today.month - 1]} est parue"
    if character_name:
        message = f"{character_name} attend votre réponse. Votre prescription est prête dans La Une."
    elif selections:
        concept = str(getattr(selections[0].concept, "name", "") or "votre point fragile")
        message = f"Au programme : {concept}. Une séance courte suffit."
    else:
        words = [str(item.get("word") or "") for item in slate.get("words") or [] if item.get("word")]
        message = f"Vos mots du jour sont prêts : {', '.join(words[:2])}." if words else "Votre prescription est prête."
    return title, message


@celery_app.task(name="app.tasks.notifications.send_morning_editions")
def send_morning_editions() -> dict[str, int]:
    """Send each capable device its real edition near the learner's preferred time."""
    from app.services.notification_service import NotificationService
    from app.services.pilot_events import PilotEventService

    now = datetime.now(PARIS_TZ)
    current_minute = now.hour * 60 + now.minute
    db = SessionLocal()
    eligible = delivered = 0
    try:
        users = db.scalars(
            select(User)
            .join(PushSubscription, PushSubscription.user_id == User.id)
            .where(
                User.is_active.is_(True),
                User.notifications_enabled.is_(True),
                User.practice_reminders.is_(True),
            )
            .distinct()
        ).all()
        for user in users:
            minute_delta = abs(current_minute - _preferred_notification_minute(user))
            if min(minute_delta, 24 * 60 - minute_delta) > 7:
                continue
            dedupe_key = now.date().isoformat()
            sent = db.scalar(
                select(PilotEvent.id).where(
                    PilotEvent.user_id == user.id,
                    PilotEvent.event_type == "morning_edition_sent",
                    PilotEvent.entity_id == dedupe_key,
                )
            )
            if sent:
                continue
            eligible += 1
            try:
                title, message = _morning_copy(db, user, now.date())
                count = NotificationService(db).send_notification(
                    user.id,
                    message,
                    title,
                    data={"route": "/atelier", "kind": "morning_edition", "notification_id": dedupe_key},
                )
                if count:
                    delivered += count
                    PilotEventService(db).record(
                        "morning_edition_sent",
                        user_id=user.id,
                        entity_type="notification",
                        entity_id=dedupe_key,
                        payload={"title": title, "message": message, "deliveries": count},
                    )
                    db.commit()
            except Exception:
                db.rollback()
                logger.exception("Failed to prepare morning edition", user_id=str(user.id))
        return {"eligible_users": eligible, "notifications_sent": delivered}
    finally:
        db.close()


@celery_app.task(name="app.tasks.notifications.send_streak_reminders")
def send_streak_reminders() -> dict[str, int]:
    """Send reminders to users with active streaks who missed today."""
    from app.services.notification_service import NotificationService

    db = SessionLocal()
    notification_service = NotificationService(db)
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
            if not getattr(user, "streak_notifications", True):
                continue
            if user.preferred_session_time is not None:
                preferred_hour = user.preferred_session_time.hour
                current_hour = datetime.now(UTC).hour
                if abs(current_hour - preferred_hour) > 2:
                    continue

            delivered = notification_service.send_notification(
                user_id=user.id,
                title="Votre série continue aujourd’hui",
                message=f"Une courte édition suffit pour prolonger vos {user.current_streak} jours.",
                data={"route": "/atelier"},
            )
            notification_count += delivered

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
                if not user.notifications_enabled or not getattr(user, "practice_reminders", True):
                    continue
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
                delivered = notification_service.send_notification(
                    user_id=user.id,
                    message=message,
                    title="Votre édition du jour",
                    data={"route": "/atelier"},
                )
                sent_count += delivered
                
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


@celery_app.task(name="app.tasks.notifications.send_serial_edition_notification")
def send_serial_edition_notification(
    user_id: str,
    episode_index: int,
    title: str,
    message: str,
    dedupe_key: str,
) -> dict[str, str | int]:
    """Send the queued push for a newly available serial edition."""
    from app.services.notification_service import NotificationService

    db = SessionLocal()
    try:
        user = db.get(User, UUID(str(user_id)))
        if not user or not user.is_active:
            return {"status": "skipped", "reason": "inactive_user", "episode_index": int(episode_index)}
        if not user.notifications_enabled or not getattr(user, "serial_edition_notifications", True):
            return {"status": "skipped", "reason": "notifications_disabled", "episode_index": int(episode_index)}
        delivered = NotificationService(db).send_notification(
            user_id=user.id,
            title=title,
            message=message,
            data={"route": "/serial"},
        )
        logger.info(
            "Serial edition notification processed",
            user_id=str(user.id),
            episode_index=episode_index,
            dedupe_key=dedupe_key,
            deliveries=delivered,
        )
        return {
            "status": "sent" if delivered else "not_delivered",
            "episode_index": int(episode_index),
            "deliveries": delivered,
        }
    finally:
        db.close()
