"""Retry password recovery email from its durable database outbox."""
from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.services.password_reset_delivery import deliver_due_reset_emails


@celery_app.task(name="app.tasks.password_reset_delivery.deliver_due")
def deliver_due() -> dict[str, int]:
    with SessionLocal() as db:
        return deliver_due_reset_emails(db)
