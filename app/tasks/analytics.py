"""Celery tasks for analytics generation and maintenance."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from loguru import logger
from sqlalchemy import select

from app.celery_app import celery_app
from app.db.models.analytics import AnalyticsSnapshot
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.analytics import AnalyticsService


@celery_app.task(name="app.tasks.analytics.generate_daily_snapshots", bind=True)
def generate_daily_snapshots(self, target_date: str | None = None) -> dict[str, int]:
    """Generate analytics snapshots for all active users."""

    db = SessionLocal()
    snapshot_date = (
        date.fromisoformat(target_date)
        if target_date
        else (datetime.now(timezone.utc) - timedelta(days=1)).date()
    )

    try:
        cutoff_date = snapshot_date - timedelta(days=90)
        active_users = db.scalars(
            select(User)
            .where(User.is_active.is_(True))
            .where(User.last_activity_date.is_not(None))
            .where(User.last_activity_date >= cutoff_date)
        ).all()

        success_count = 0
        failure_count = 0

        for user in active_users:
            try:
                service = AnalyticsService(db)
                service.generate_daily_snapshot(user=user, snapshot_date=snapshot_date)
                success_count += 1

                if success_count % 100 == 0:
                    logger.info(
                        "Analytics snapshot progress",
                        processed=success_count,
                        total=len(active_users),
                    )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(
                    "Failed to generate snapshot",
                    user_id=str(user.id),
                    error=str(exc),
                )
                failure_count += 1
                continue

        logger.info(
            "Daily analytics snapshots completed",
            date=snapshot_date.isoformat(),
            success=success_count,
            failures=failure_count,
        )

        return {
            "date": snapshot_date.isoformat(),
            "success": success_count,
            "failures": failure_count,
            "total": len(active_users),
        }

    finally:
        db.close()


@celery_app.task(name="app.tasks.analytics.cleanup_old_snapshots")
def cleanup_old_snapshots(retention_days: int = 365) -> dict[str, int]:
    """Remove analytics snapshots older than the retention period."""

    db = SessionLocal()
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=retention_days)).date()

    try:
        deleted = (
            db.query(AnalyticsSnapshot)
            .filter(AnalyticsSnapshot.snapshot_date < cutoff_date)
            .delete(synchronize_session=False)
        )
        db.commit()

        logger.info(
            "Old analytics snapshots cleaned up",
            deleted_count=deleted,
            cutoff_date=cutoff_date.isoformat(),
        )

        return {"deleted": deleted, "cutoff_date": cutoff_date.isoformat()}

    except Exception as exc:  # pragma: no cover - defensive logging
        db.rollback()
        logger.error("Failed to cleanup old snapshots", error=str(exc))
        raise
    finally:
        db.close()


@celery_app.task(name="app.tasks.analytics.generate_user_snapshot")
def generate_user_snapshot(user_id: str, target_date: str | None = None) -> dict[str, str]:
    """Generate a snapshot for a specific user."""

    db = SessionLocal()
    snapshot_date = (
        date.fromisoformat(target_date)
        if target_date
        else (datetime.now(timezone.utc) - timedelta(days=1)).date()
    )

    try:
        try:
            user_uuid = UUID(user_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"User {user_id} not found") from exc

        user = db.get(User, user_uuid)
        if not user:
            raise ValueError(f"User {user_id} not found")

        service = AnalyticsService(db)
        snapshot = service.generate_daily_snapshot(user=user, snapshot_date=snapshot_date)

        logger.info(
            "User analytics snapshot generated",
            user_id=user_id,
            date=snapshot_date.isoformat(),
        )

        return {
            "user_id": user_id,
            "snapshot_id": str(snapshot.id),
            "date": snapshot_date.isoformat(),
        }

    finally:
        db.close()
