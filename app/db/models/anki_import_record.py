"""Model to persist raw Anki import content for rehydration."""
from __future__ import annotations

import uuid
from sqlalchemy import Column, DateTime, Boolean, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.base import Base


class AnkiImportRecord(Base):
    __tablename__ = "anki_import_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=True)
    deck_name = Column(String(255), nullable=True)
    preserve_scheduling = Column(Boolean, nullable=False, default=True)
    csv_content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

