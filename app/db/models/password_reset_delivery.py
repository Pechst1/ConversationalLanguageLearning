"""Kept for imports written before S4 stage 3: the reset outbox is now the mail outbox."""
from app.db.models.mail_delivery import MailDelivery as PasswordResetDelivery

__all__ = ["PasswordResetDelivery"]
