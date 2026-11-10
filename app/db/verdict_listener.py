"""Package V stage 2: every session writes the verdict ledger as it flushes.

Registered once, on import of :mod:`app.db.models`. The work is in
:func:`app.services.verdict_ledger.record_flush`; it is imported when the first flush
runs, so the models never import the services.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session


@event.listens_for(Session, "before_flush")
def _record_verdicts(session: Session, flush_context: Any, instances: Any) -> None:  # noqa: ARG001
    from app.services.verdict_ledger import record_flush

    record_flush(session)


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_soft_rollback")
def _forget_pending(session: Session, *args: Any) -> None:  # noqa: ARG001
    session.info.pop("verdict_ledger_live", None)
