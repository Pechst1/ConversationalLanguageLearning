"""Package V stage 4: the memo. An answer to a keyed item, judged once and remembered.

One row per (surface, item, normalised answer). A model verdict on a keyed item (a drill,
a Forge item, a placement prompt) writes a ``candidate``. A second, independent check
(another call, another prompt, that agrees; and for «right», rules that find nothing)
makes it ``confirmed``. A confirmed memo settles the same answer next time as
``checked_by: key``: no model call, the same verdict for everyone. ``revoked`` ends it,
and the answers it settled are taken back (:func:`app.services.answer_memo.revoke`).

``edits`` are the verified edits of a «not yet», so the same miss gets the same
explanation. ``payload`` is what the surface stores for a graded answer, so a memo hit
can be written exactly like the model's reading was. ``backing`` lists the model readings
the memo was built from; ``settled`` the answers it settled since (subject, learner,
the gold key it paid), which a revoke takes back.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.models._clock import app_now

_JSON = JSONB().with_variant(JSON(), "sqlite")

MEMO_STATES = ("candidate", "confirmed", "revoked")


class AnswerMemo(Base):
    __tablename__ = "answer_memos"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    surface: Mapped[str] = mapped_column(String(32), nullable=False)
    item_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    answer_norm: Mapped[str] = mapped_column(Text, nullable=False)
    item_label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    edits: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    confirmation: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, default=dict)
    backing: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False, default=list)
    settled: Mapped[list[dict[str, Any]]] = mapped_column(_JSON, nullable=False, default=list)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=app_now
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_answer_memos_lookup", "surface", "item_fingerprint", "answer_hash", "state"),
        Index("ix_answer_memos_state", "state", "created_at"),
    )
