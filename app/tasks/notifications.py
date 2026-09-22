"""Celery tasks for user notifications and reminders."""
from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
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

#: Kept for callers that computed "now" in Paris. WP-80: every schedule below is
#: the learner's own zone (`User.timezone`), which defaults to this one.
PARIS_TZ = ZoneInfo("Europe/Paris")
#: WP-80: the streak-at-risk push goes out at this local time…
STREAK_REMINDER_MINUTE = 19 * 60
#: …and the Lexique review reminder at this one, only once the day is done.
REVIEW_REMINDER_MINUTE = 18 * 60
#: A beat run every 15 minutes finds each learner inside this window once.
SCHEDULE_WINDOW_MINUTES = 15
STREAK_REMINDER_EVENT = "streak_reminder_sent"
REVIEW_REMINDER_EVENT = "review_reminder_sent"
MORNING_EVENT = "morning_edition_sent"
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


def _utc_now(now: datetime | str | None = None) -> datetime:
    """The one clock seam. Beat passes nothing; tests pass an ISO instant."""

    if isinstance(now, str) and now:
        now = datetime.fromisoformat(now)
    moment = now if isinstance(now, datetime) else datetime.now(UTC)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _local_now(user: User, now: datetime) -> datetime:
    from app.services.streak import local_now

    return local_now(user, now)


def _minute_of(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def _near(current_minute: int, target_minute: int, tolerance: int = 7) -> bool:
    delta = abs(current_minute - target_minute)
    return min(delta, 24 * 60 - delta) <= tolerance


def _in_window(current_minute: int, target_minute: int) -> bool:
    """``target <= now < target + window``: never early, at most one run late."""

    return 0 <= current_minute - target_minute < SCHEDULE_WINDOW_MINUTES


def _record_sent(db, user: User, event_type: str, key: str, payload: dict[str, Any]) -> None:
    from app.services.pilot_events import PilotEventService

    PilotEventService(db).record(
        event_type,
        user_id=user.id,
        entity_type="notification",
        entity_id=key,
        payload=payload,
    )
    db.commit()


def _morning_copy(db, user: User, today: date) -> tuple[str, str]:
    """Build truthful copy only from the currently persisted prescription."""
    from app.services.atelier import AtelierScheduler
    from app.services.daily_words import DailyWordSlateService
    from app.services.serial import SerialThreadService
    from app.services.serial_notifications import daily_journey_morning_copy

    # WP-19 / WP-80: cohort learners live in the V2 daily journey, so their
    # morning push is the story's teaser in a character's voice. Everyone else
    # keeps the edition copy below.
    journey_copy = daily_journey_morning_copy(db, user, today=today)
    if journey_copy is not None:
        return journey_copy

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


#: WP-37 §6. The day-before rehearsal nudge is a *second* push, not a variant of
#: the morning edition: ``_morning_copy`` returns exactly one (title, message)
#: per learner per day and this one is about something the learner said they
#: would do tomorrow. It therefore carries its own event type and its own key.
REHEARSAL_REMINDER_EVENT = "rehearsal_reminder_sent"


def _already_sent(db, user: User, event_type: str, key: str) -> bool:
    return (
        db.scalar(
            select(PilotEvent.id).where(
                PilotEvent.user_id == user.id,
                PilotEvent.event_type == event_type,
                PilotEvent.entity_id == key,
            )
        )
        is not None
    )


def _send_rehearsal_reminder(db, user: User, now: datetime) -> int:
    """WP-31 §7.2's copy, finally sent. Returns the number of deliveries.

    Independent of the edition push in both directions: a learner who already
    had their edition today must still be reminded about tomorrow's real
    situation, and a rehearsal reminder that fails must not cost them the
    edition. The copy decides whether there is anything to say — only an
    unplayed rehearsal with a resolved date the day before it happens — so this
    function only owns delivery and the key.
    """

    from app.services.notification_service import NotificationService
    from app.services.pilot_events import PilotEventService
    from app.services.serial_notifications import rehearsal_reminder_copy

    today = _local_now(user, now).date()
    key = f"rehearsal-ready:{user.id}:{today.isoformat()}"
    if _already_sent(db, user, REHEARSAL_REMINDER_EVENT, key):
        return 0
    reminder = rehearsal_reminder_copy(db, user, today=today)
    if reminder is None:
        return 0
    title, message = reminder
    count = NotificationService(db).send_notification(
        user.id,
        message,
        title,
        data={"route": "/repetition", "kind": "rehearsal_reminder", "notification_id": key},
    )
    if not count:
        # Nothing left the building, so nothing is marked as sent: tomorrow's
        # run may try again, and the day after there is nothing to remind about.
        return 0
    PilotEventService(db).record(
        REHEARSAL_REMINDER_EVENT,
        user_id=user.id,
        entity_type="notification",
        entity_id=key,
        payload={"title": title, "message": message, "deliveries": count},
    )
    db.commit()
    return count


def _morning_message(db, user: User, today: date) -> tuple[str, str, dict[str, Any]] | None:
    """(title, message, data) for one learner's morning, or ``None`` for silence.

    A journey learner gets WP-80's character push — or nothing once today's
    scene is done. Everyone else keeps the legacy edition.
    """

    from app.services.daily_journey import journey_enabled_for
    from app.services.serial_notifications import daily_journey_morning_push

    key = today.isoformat()
    if journey_enabled_for(user):
        push = daily_journey_morning_push(db, user, today=today)
        if push is None:
            return None
        return push.title, push.message, push.data("morning_teaser", key)
    title, message = _morning_copy(db, user, today)
    return title, message, {"route": "/atelier", "kind": "morning_edition", "notification_id": key}


def _push_users(db) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(PushSubscription, PushSubscription.user_id == User.id)
            .where(User.is_active.is_(True), User.notifications_enabled.is_(True))
            .distinct()
        ).all()
    )


@celery_app.task(name="app.tasks.notifications.send_morning_editions")
def send_morning_editions(now: str | None = None) -> dict[str, int]:
    """Send each device its morning at the learner's reminder time, in their zone."""
    from app.services.notification_service import NotificationService

    moment = _utc_now(now)
    db = SessionLocal()
    eligible = delivered = reminders = 0
    try:
        for user in _push_users(db):
            if not getattr(user, "practice_reminders", True):
                continue
            local = _local_now(user, moment)
            if not _near(_minute_of(local), _preferred_notification_minute(user)):
                continue
            dedupe_key = local.date().isoformat()
            if not _already_sent(db, user, MORNING_EVENT, dedupe_key):
                eligible += 1
                try:
                    prepared = _morning_message(db, user, local.date())
                    if prepared is not None:
                        title, message, data = prepared
                        count = NotificationService(db).send_notification(
                            user.id, message, title, data=data
                        )
                        if count:
                            delivered += count
                            _record_sent(
                                db, user, MORNING_EVENT, dedupe_key,
                                {"title": title, "message": message, "deliveries": count,
                                 "kind": data.get("kind"), "teaser_source": data.get("teaser_source")},
                            )
                except Exception:
                    db.rollback()
                    logger.exception("Failed to prepare morning edition", user_id=str(user.id))
            # WP-37 §6, applied. Outside the edition's dedupe on purpose: a
            # learner whose edition already went out today must still hear that
            # the real thing is tomorrow.
            try:
                reminders += _send_rehearsal_reminder(db, user, moment)
            except Exception:
                db.rollback()
                logger.exception("Failed to send rehearsal reminder", user_id=str(user.id))
        return {
            "eligible_users": eligible,
            "notifications_sent": delivered,
            "rehearsal_reminders_sent": reminders,
        }
    finally:
        db.close()


def _day_done(db, user: User, today: date, streak_today_done: bool) -> bool:
    """Today's practice is done: the journey scene, or any streak-moving session."""

    from app.services.serial_notifications import scene_done_today

    return streak_today_done or scene_done_today(db, user, today=today)


@celery_app.task(name="app.tasks.notifications.send_streak_reminders")
def send_streak_reminders(now: str | None = None) -> dict[str, int]:
    """WP-80: the evening push for a live streak (≥ 2 days) not yet extended today.

    At the learner's local 19:00, once per local day, in a character's voice.
    The streak is read through `app.services.streak` — checked on the date, so
    a learner whose chain already broke is not told it is at risk.
    """
    from app.services.notification_service import NotificationService
    from app.services.serial_notifications import streak_at_risk_push
    from app.services.streak import settle_streak

    moment = _utc_now(now)
    db = SessionLocal()
    eligible = delivered = 0
    try:
        for user in _push_users(db):
            if not getattr(user, "streak_notifications", True):
                continue
            local = _local_now(user, moment)
            if not _in_window(_minute_of(local), STREAK_REMINDER_MINUTE):
                continue
            today = local.date()
            key = today.isoformat()
            try:
                if _already_sent(db, user, STREAK_REMINDER_EVENT, key):
                    continue
                state = settle_streak(db, user, today=today)
                db.commit()
                if state.days < 2 or _day_done(db, user, today, state.today_done):
                    continue
                eligible += 1
                push = streak_at_risk_push(db, user, days=state.days)
                count = NotificationService(db).send_notification(
                    user.id, push.message, push.title,
                    data=push.data("streak_reminder", key),
                )
                if count:
                    delivered += count
                    _record_sent(
                        db, user, STREAK_REMINDER_EVENT, key,
                        {"title": push.title, "message": push.message, "days": state.days, "deliveries": count},
                    )
            except Exception:
                db.rollback()
                logger.exception("Failed to send streak reminder", user_id=str(user.id))
        logger.info("Streak reminders processed", eligible_users=eligible, notifications_sent=delivered)
        return {"eligible_users": eligible, "notifications_sent": delivered}
    finally:
        db.close()


def review_reminder_copy(total_due: int) -> tuple[str, str]:
    """«vous», no emoji, an honest count."""

    if total_due == 1:
        return "Le Lexique", "Un mot vous attend pour une révision rapide."
    return "Le Lexique", f"{total_due} mots vous attendent pour une révision rapide."


@celery_app.task(name="app.tasks.notifications.send_daily_srs_reminders")
def send_daily_srs_reminders(now: str | None = None) -> dict[str, int]:
    """WP-80: the Lexique review reminder, finally scheduled.

    At the learner's local 18:00, once per local day, only when something is
    due — and, for a journey learner, only once today's scene is done: the
    review is the extra, never a second call to the day's main thing.
    """
    from app.services.daily_journey import journey_enabled_for
    from app.services.notification_service import NotificationService
    from app.services.streak import read_streak
    from app.services.unified_srs import UnifiedSRSService

    moment = _utc_now(now)
    db = SessionLocal()
    total = delivered = 0
    try:
        for user in _push_users(db):
            if not getattr(user, "practice_reminders", True):
                continue
            local = _local_now(user, moment)
            if not _in_window(_minute_of(local), REVIEW_REMINDER_MINUTE):
                continue
            today = local.date()
            key = today.isoformat()
            total += 1
            try:
                if _already_sent(db, user, REVIEW_REMINDER_EVENT, key):
                    continue
                if journey_enabled_for(user) and not _day_done(
                    db, user, today, read_streak(user, today=today).today_done
                ):
                    continue
                total_due = int(UnifiedSRSService(db).get_due_summary(user.id).total_due or 0)
                if total_due <= 0:
                    continue
                title, message = review_reminder_copy(total_due)
                count = NotificationService(db).send_notification(
                    user_id=user.id,
                    message=message,
                    title=title,
                    data={"route": "/vocabulary/review", "kind": "review_reminder", "notification_id": key},
                )
                if count:
                    delivered += count
                    _record_sent(
                        db, user, REVIEW_REMINDER_EVENT, key,
                        {"title": title, "message": message, "due": total_due, "deliveries": count},
                    )
            except Exception as exc:
                db.rollback()
                logger.warning("Failed to send SRS reminder", user_id=str(user.id), error=str(exc))
        logger.info("Daily SRS reminders processed", total_users=total, notifications_sent=delivered)
        return {"total_users": total, "notifications_sent": delivered}
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
