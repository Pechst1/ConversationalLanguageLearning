"""WP-16 §5 — the Séance correction's request bound and its cost row.

Both belong to the correction call site in :mod:`app.services.atelier`, which is
under a concurrent lease, so the logic lives here and that file only calls it.

Two gaps WP-15 recorded and could not close inside its own files:

* the learner answer went to the paid checker with **no length cap at all**
  after the whole-answer grading rework, so request size on a paid endpoint was
  learner-controlled;
* the correction call kept no usage metadata at all, so
  ``PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD`` did not cover the most-used paid
  endpoint in the app and ``scripts/pilot_digest.py`` had nothing to print.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from loguru import logger
from sqlalchemy.orm import Session

from app.services.pilot_events import PilotEventService

#: Ceiling on the learner text sent to the paid correction checker. Generous by
#: design — a long integrated-writing answer is roughly 1,500 characters, so
#: nothing a learner actually writes is cut. It exists so that one pasted
#: document cannot size a paid request.
ANSWER_MAX_CHARS = 4000

#: The pilot-ledger event type. `scripts/pilot_digest.py` reads it by name.
CORRECTION_EVENT_TYPE = "atelier_correction"


def bound_learner_answer(
    answer_payload: dict[str, Any], *, max_chars: int = ANSWER_MAX_CHARS
) -> tuple[dict[str, Any], bool]:
    """Compact the learner's answer for the checker, within one char budget.

    Returns ``(block, truncated)``. Keyed answers share a single budget, so a
    long first answer cannot buy the request more room by splitting. A
    truncation is *declared* rather than hidden: the checker sees it in the
    payload and the learner sees it as ``assessment_truncated``, so a verdict
    on part of an answer is never presented as a verdict on the whole.
    """

    budget = max(0, int(max_chars))
    truncated = False

    def bound(value: Any) -> str:
        nonlocal budget, truncated
        text = str(value or "")
        if len(text) <= budget:
            budget -= len(text)
            return text
        clipped = text[:budget]
        budget = 0
        truncated = True
        return clipped

    if "text" in answer_payload:
        block: dict[str, Any] = {"text": bound(answer_payload.get("text"))}
    else:
        answers = answer_payload.get("answers")
        if not isinstance(answers, dict):
            return {}, False
        block = {"answers": {str(key): bound(value) for key, value in answers.items()}}
    if truncated:
        block["truncated"] = True
    return block, truncated


def record_correction_cost(
    db: Session,
    result: Any,
    *,
    user_id: UUID | None,
    session_id: UUID | None,
    answer_truncated: bool = False,
) -> None:
    """One pilot-cost row per real Séance correction call.

    Mirrors :class:`AudioSessionService`'s ``speaking_turn`` row: the provider's
    own usage metadata, priced by the LLM service, written through the caller's
    transaction and never committed here. A provider that reports no cost gets
    a 0.0 row rather than an invented one — the token counts still make the call
    visible. Telemetry must never cost a learner their check, so every failure
    is swallowed with a log line.
    """

    try:
        PilotEventService(db).record(
            CORRECTION_EVENT_TYPE,
            user_id=user_id,
            entity_type="atelier_session",
            entity_id=session_id,
            payload={
                "provider": getattr(result, "provider", None),
                "model": getattr(result, "model", None),
                "prompt_tokens": int(getattr(result, "prompt_tokens", 0) or 0),
                "completion_tokens": int(getattr(result, "completion_tokens", 0) or 0),
                "total_tokens": int(getattr(result, "total_tokens", 0) or 0),
                "answer_truncated": bool(answer_truncated),
            },
            cost_usd=float(getattr(result, "cost", 0.0) or 0.0),
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Atelier correction cost row could not be written")


__all__ = [
    "ANSWER_MAX_CHARS",
    "CORRECTION_EVENT_TYPE",
    "bound_learner_answer",
    "record_correction_cost",
]
