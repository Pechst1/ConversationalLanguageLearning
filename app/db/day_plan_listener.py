"""S2.1: the stored day plan is written as the journey and Forge transitions flush.

Registered once, on import of :mod:`app.db.models`, like the verdict ledger. The work
is in :mod:`app.services.day_plan` (imported when the first flush runs, so the models
never import the services). Every hook returns at once while ``DAY_PLAN_STORED`` is off.

``after_flush`` notes what this flush changed (attribute history is still there);
``after_flush_postexec`` writes the plan once the rows are in, and the commit's next
flush round stores it.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session


def _on() -> bool:
    from app.config import settings

    return bool(getattr(settings, "DAY_PLAN_STORED", False))


@event.listens_for(Session, "after_flush")
def _note_day_plan(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    if not _on():
        return
    from app.services.day_plan import note_flush

    note_flush(session)


@event.listens_for(Session, "after_flush_postexec")
def _write_day_plan(session: Session, flush_context: Any) -> None:  # noqa: ARG001
    if not _on() and "day_plan_transitions" not in session.info:
        return
    from app.services.day_plan import apply_flush

    apply_flush(session)


@event.listens_for(Session, "after_soft_rollback")
def _forget_day_plan(session: Session, previous_transaction: Any) -> None:  # noqa: ARG001
    session.info.pop("day_plan_transitions", None)
