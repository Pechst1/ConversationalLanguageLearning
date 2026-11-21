"""The one verdict shape on the wire, under the key ``check`` (see :mod:`app.core.verdict`).

Named ``check`` because several responses already use ``verdict`` for a stored word.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.verdict import Verdict


class VerdictEditView(BaseModel):
    span: str
    start: int
    end: int
    replacement: str
    note: str = ""
    by: Literal["key", "model", "rules"] = "model"
    rule_id: str | None = None


class VerdictView(BaseModel):
    outcome: Literal["right", "partly", "not_yet", "not_checked"]
    checked_by: Literal["key", "model", "rules", "none"]
    call: Literal["ok", "empty", "failed", "pending", "not_called"]
    failure: Literal["timeout", "provider_error", "invalid_output", "no_model", "no_check_target"] | None = None
    retryable: bool = False
    edits: list[VerdictEditView] = Field(default_factory=list)
    #: The learner's text with ``edits`` made. ``None`` when there is nothing to change.
    corrected: str | None = None
    #: Whether this may move a level, mint gold or mint a token.
    counts: bool
    #: Package V stage 3: when an answer saved unread was checked since (by the settlement
    #: job or «Ask again»). The screen says so the next time it is opened.
    checked_since: datetime | None = None

    @classmethod
    def of(cls, verdict: Verdict, *, checked_since: datetime | None = None) -> VerdictView:
        return cls.model_validate({**verdict.to_dict(), "checked_since": checked_since})


class AppealView(BaseModel):
    """Package V stage 5: what «I think this is right» came back with."""

    state: Literal["upheld", "refused", "unread"]
    check: VerdictView
    #: One sentence in the learner's language: why it is right, or the one thing that is not.
    reason: str | None = None
    remaining_today: int


__all__ = ["AppealView", "VerdictEditView", "VerdictView"]
