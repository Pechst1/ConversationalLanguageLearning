"""S4 stage 3 — the mail outbox: every message the app sends, until SMTP took it.

Grown from ``password_reset_deliveries`` (renamed by the migration, so pending
reset rows stay deliverable). ``kind`` names the template (``app/mail``);
``recipient`` is set when the message goes somewhere other than the account's
current address (the new address of a change, the old one after it).
``token_hash`` binds the row to the credential it carries: a newer code makes
the older message stale, and the outbox cancels it instead of sending.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class MailDelivery(Base):
    __tablename__ = "mail_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(32), nullable=False, default="password_reset", server_default="password_reset", index=True)
    recipient = Column(String(255), nullable=True)
    token_hash = Column(String(64), nullable=False)
    encrypted_payload = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
