"""Package V stage 4: the memo. A keyed item's answer, judged once, settled the same way after.

Before, a right answer outside an item's listed variants went to the model every time:
it cost a call every time and could be judged differently each time (#174). Now:

1. **Candidate.** When a model judges an answer to a keyed item (a drill, a Forge item, a
   placement prompt), :func:`remember` writes a ``candidate`` memo: the item's
   fingerprint, the normalised answer, the outcome, the verified edits and what the
   surface stored. Nothing reads a candidate.
2. **Confirmation.** :func:`confirm` (``app.tasks.answer_memo.confirm_memo``, sent when
   the candidate is written and again by the sweep) asks a second, independent check: a
   second call with a different prompt (:data:`VERIFIERS`). It is confirmed only when that
   check agrees, and, for «right», when the rules find nothing to correct.
3. **Lookup.** :func:`app.services.judge.consult` asks :class:`Memos` before the model.
   A confirmed memo settles the same answer as ``checked_by: key``: no model call, the
   same verdict for everyone, the same explanation for the same miss.
4. **Revoke.** :func:`revoke` (``/pilot-ops``) ends a memo and takes back what it settled:
   each Forge answer it settled is superseded by an unread record, and its gold is voided.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.verdict import Outcome, locate_edits
from app.db.models.answer_memo import AnswerMemo
from app.services.judge import Task

__all__ = [
    "VERIFIERS",
    "Memos",
    "confirm",
    "dispatcher",
    "fingerprint",
    "forge_task",
    "listing",
    "normalise",
    "note_use",
    "placement_outcome",
    "placement_task",
    "recall_task",
    "remember",
    "revoke",
    "sweep",
]

#: The surfaces whose items have a key. Only these are remembered.
SURFACES = ("recall", "forge", "placement")
#: Second checks per candidate before the sweep stops asking.
MAX_CONFIRM_ATTEMPTS = 3


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def enabled() -> bool:
    return bool(getattr(settings, "ANSWER_MEMO_ENABLED", True))


def normalise(answer: object) -> str:
    """The memo's key for an answer: typography folded, accents kept (stage 1 of the judge)."""

    from app.services.answer_acceptance import fold_typography

    return fold_typography(answer)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint(surface: str, item: Mapping[str, Any]) -> str:
    """One item, the same for every learner who meets it."""

    body = json.dumps({"surface": surface, **item}, sort_keys=True, ensure_ascii=False, default=str)
    return _hash(body)[:40]


# ---------------------------------------------------------------------------
# What a keyed item is, per surface
# ---------------------------------------------------------------------------


def placement_task(prompt: Any, language: str | None) -> Task:
    """A placement prompt. The grader's note is written in the learner's language, so a
    memo is per language too."""

    item = {"prompt_id": str(prompt.prompt_id), "language": str(language or "fr")}
    return Task("placement", item=fingerprint("placement", item))


def placement_outcome(score: Any) -> Outcome:
    value = float(score or 0)
    return Outcome.RIGHT if value >= 3 else Outcome.PARTLY if value >= 2 else Outcome.NOT_YET


def forge_task(*, round_name: str, mode: str, prompt_payload: Mapping[str, Any], concept_id: Any = None) -> Task | None:
    """A Forge item: its round, its prompt and its key. ``None`` for an item with no prompt."""

    from app.services.atelier import _accepted_answers

    items = prompt_payload.get("items") or []
    first = items[0] if items and isinstance(items[0], Mapping) else {}
    prompt = {
        key: first.get(key) or prompt_payload.get(key)
        for key in ("instruction", "instruction_fr", "prompt", "prompt_fr", "sentence", "source_fr", "example_answer")
        if first.get(key) or prompt_payload.get(key)
    }
    if not prompt:
        return None
    item = {
        "round": str(round_name),
        "mode": str(mode),
        "concept": str(concept_id or ""),
        "prompt": prompt,
        "accepted": sorted(_accepted_answers(dict(prompt_payload))),
    }
    return Task("forge", accepted=tuple(item["accepted"]), item=fingerprint("forge", item))


def recall_task(task: Any) -> Task:
    """A drill: its format, its prompt and its key."""

    item = {
        "type": str(getattr(task, "task_type", "")),
        "prompt": getattr(task, "prompt_fr", None),
        "source": getattr(task, "source_fr", None),
        "solution": getattr(task, "solution_fr", None),
        "accepted": sorted(str(value) for value in getattr(task, "accepted_answers", None) or []),
        "target": str(getattr(getattr(task, "target", None), "target_id", "") or ""),
    }
    return Task("recall", accepted=tuple(item["accepted"]), item=fingerprint("recall", item))


# ---------------------------------------------------------------------------
# Lookup (the judge's stage 3)
# ---------------------------------------------------------------------------


class Memos:
    """The confirmed memos, as :func:`app.services.judge.consult` reads them."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def lookup(self, task: Task, normalised: str) -> AnswerMemo | None:
        if not enabled() or not task.item or not normalised or task.surface not in SURFACES:
            return None
        try:
            with self.db.no_autoflush:
                return self.db.scalars(
                    select(AnswerMemo)
                    .where(
                        AnswerMemo.surface == task.surface,
                        AnswerMemo.item_fingerprint == task.item,
                        AnswerMemo.answer_hash == _hash(normalised),
                        AnswerMemo.state == "confirmed",
                    )
                    .order_by(AnswerMemo.confirmed_at.desc())
                    .limit(1)
                ).first()
        except Exception as exc:  # noqa: BLE001 - no memo table yet: the model decides, as before
            logger.warning("answer_memo: lookup failed ({})", exc)
            return None


def _find(db: Session, task: Task, normalised: str, states: Iterable[str]) -> AnswerMemo | None:
    with db.no_autoflush:
        return db.scalars(
            select(AnswerMemo).where(
                AnswerMemo.surface == task.surface,
                AnswerMemo.item_fingerprint == task.item,
                AnswerMemo.answer_hash == _hash(normalised),
                AnswerMemo.state.in_(tuple(states)),
            )
        ).first()


def note_use(
    db: Session,
    memo_id: Any,
    *,
    subject_type: str,
    subject_id: Any,
    user_id: Any = None,
    gold_key: str | None = None,
) -> None:
    """A memo settled ``subject``: counted, and kept so a revoke can take it back."""

    if not memo_id:
        return
    with db.no_autoflush:
        memo = db.get(AnswerMemo, uuid.UUID(str(memo_id)))
    if memo is None:
        return
    entry = {
        "subject_type": subject_type,
        "subject_id": str(subject_id),
        "user_id": str(user_id) if user_id else None,
        "gold_key": gold_key,
    }
    settled = list(memo.settled or [])
    if any(row.get("subject_type") == subject_type and row.get("subject_id") == str(subject_id) for row in settled):
        return
    memo.settled = [*settled, entry]
    memo.hits = int(memo.hits or 0) + 1
    flag_modified(memo, "settled")
    db.add(memo)


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


def _dispatch_celery(memo_id: str) -> None:
    from app.tasks.answer_memo import confirm_memo

    confirm_memo.apply_async(args=[memo_id], countdown=int(settings.ANSWER_MEMO_CONFIRM_DELAY_SECONDS))


#: How a confirmation is queued (tests swap it). The sweep re-sends what a refusal lost.
dispatcher: Callable[[str], None] = _dispatch_celery


def remember(
    db: Session,
    *,
    task: Task | None,
    answer: object,
    outcome: Outcome | str,
    payload: Mapping[str, Any],
    proposed: Iterable[Mapping[str, Any]] = (),
    backing: Mapping[str, Any] | None = None,
    label: str = "",
) -> AnswerMemo | None:
    """A model judged ``answer`` to the keyed item ``task``: write or back a candidate.

    Only a settled outcome is remembered (never «not checked»). The edits kept are the
    ones whose words are in the answer and that the variant gate lets through.
    """

    if not enabled() or task is None or not task.item or task.surface not in SURFACES:
        return None
    outcome = Outcome(outcome)
    if outcome is Outcome.NOT_CHECKED:
        return None
    text = "" if answer is None else str(answer)
    normalised = normalise(text)
    if not normalised:
        return None
    try:
        with db.begin_nested():
            memo = _find(db, task, normalised, ("candidate", "confirmed"))
            back = dict(backing or {})
            if memo is not None:
                if memo.outcome == outcome.value and back:
                    memo.backing = [*(memo.backing or []), back]
                    flag_modified(memo, "backing")
                    db.add(memo)
                elif memo.outcome != outcome.value and memo.state == "candidate":
                    # Two model readings of one answer disagree: it is not a fact yet.
                    memo.confirmation = {**(memo.confirmation or {}), "status": "readings_disagree"}
                    flag_modified(memo, "confirmation")
                    db.add(memo)
                return memo
            from app.services.judge import _gated

            edits = [
                {"span": edit.span, "replacement": edit.replacement, "note": edit.note, "by": edit.by, "rule_id": edit.rule_id}
                for edit in locate_edits(text, _gated(proposed))
            ]
            memo = AnswerMemo(
                id=uuid.uuid4(),
                surface=task.surface,
                item_fingerprint=task.item,
                answer_hash=_hash(normalised),
                answer_norm=normalised,
                item_label=label[:400],
                outcome=outcome.value,
                edits=edits,
                payload=dict(payload),
                state="candidate",
                confirmation={"status": "queued", "attempts": 0},
                backing=[back] if back else [],
                settled=[],
                hits=0,
            )
            db.add(memo)
            db.flush([memo])
    except Exception as exc:  # noqa: BLE001 - a memo is never worth the learner's answer
        logger.warning("answer_memo: could not remember ({})", exc)
        return None
    try:
        dispatcher(str(memo.id))
    except Exception as exc:  # noqa: BLE001 - the sweep sends it again
        logger.warning("answer_memo: confirmation not sent ({})", exc)
    return memo


# ---------------------------------------------------------------------------
# Confirmation: a second, independent check
# ---------------------------------------------------------------------------


def _rules_find_something(answer: str) -> list[dict[str, Any]]:
    from app.services.correction_contract import deterministic_errata
    from app.services.judge import _gated

    found = [
        {"span": row.get("learner_text"), "replacement": row.get("corrected_target")}
        for row in deterministic_errata(answer)
    ]
    return [row for row in _gated(found) if row.get("span")]


def _verify_placement(db: Session, memo: AnswerMemo) -> Outcome | None:
    """A second examiner, another prompt: score the same answer to the same prompt."""

    from app.services import placement

    prompt = placement.PROMPTS_BY_ID.get(str((memo.payload or {}).get("prompt_id") or ""))
    llm = placement.PlacementService(db)._get_llm_service()
    if prompt is None or llm is None:
        return None
    answer = str((memo.payload or {}).get("answer") or memo.answer_norm)
    result = llm.generate_error_detection(
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "prompt_band": prompt.band,
                        "prompt_fr": prompt.prompt_fr,
                        "prompt_intent": prompt.intent,
                        "learner_response": answer,
                    },
                    ensure_ascii=False,
                ),
            }
        ],
        system_prompt=placement.CONFIRM_SYSTEM_PROMPT,
        response_format=placement.CONFIRM_RESPONSE_FORMAT,
        temperature=0.0,
        max_tokens=settings.ATELIER_CORRECTION_LLM_MAX_TOKENS,
        model=settings.ATELIER_CORRECTION_LLM_MODEL,
        request_timeout=settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS,
        disable_retries=True,
        reasoning_effort=settings.ATELIER_CORRECTION_LLM_REASONING_EFFORT,
    )
    parsed = json.loads(result.content)
    score = parsed.get("score_0_4")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    return placement_outcome(score)


_FORGE_CONFIRM_PROMPT = (
    "You are a second, independent examiner of one French exercise answer. Read the "
    "instruction, the accepted answers and the learner's answer. Decide only whether the "
    "answer does what the instruction asks in correct French. Answer JSON: "
    '{"verdict": "correct" | "partial" | "wrong"}. Accept any correct French, not only the '
    "listed answers; spelling variants of the 1990 reform are correct."
)
_FORGE_WORDS = {"correct": Outcome.RIGHT, "partial": Outcome.PARTLY, "wrong": Outcome.NOT_YET}


def _verify_forge(db: Session, memo: AnswerMemo) -> Outcome | None:  # noqa: ARG001
    from app.services.llm_service import LLMService

    if not settings.ATELIER_CORRECTION_LLM_ENABLED:
        return None
    payload = memo.payload or {}
    result = LLMService().generate_error_detection(
        [
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "item": payload.get("item") or {},
                        "learner_answer": payload.get("answer") or memo.answer_norm,
                    },
                    ensure_ascii=False,
                ),
            }
        ],
        system_prompt=_FORGE_CONFIRM_PROMPT,
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=settings.ATELIER_CORRECTION_LLM_MAX_TOKENS,
        model=settings.ATELIER_CORRECTION_LLM_MODEL,
        request_timeout=settings.ATELIER_CORRECTION_LLM_TIMEOUT_SECONDS,
        disable_retries=True,
        reasoning_effort=settings.ATELIER_CORRECTION_LLM_REASONING_EFFORT,
    )
    word = str(json.loads(result.content).get("verdict") or "")
    return _FORGE_WORDS.get(word)


#: The second check per surface: another call, another prompt. ``None`` = could not check.
#: A drill memo is only written by an upheld appeal (stage 5), already a second reading.
VERIFIERS: dict[str, Callable[[Session, AnswerMemo], Outcome | None]] = {
    "placement": _verify_placement,
    "forge": _verify_forge,
}


def confirm(db: Session, memo_id: Any, *, now: datetime | None = None) -> str:
    """Run the second check on a candidate. Returns the memo's state. Flushes, never commits."""

    memo = db.get(AnswerMemo, uuid.UUID(str(memo_id)))
    if memo is None:
        return "missing"
    if memo.state != "candidate":
        return memo.state
    status = dict(memo.confirmation or {})
    if status.get("status") in {"disagreed", "rules_disagree", "readings_disagree"}:
        return memo.state
    attempts = int(status.get("attempts") or 0) + 1
    verifier = VERIFIERS.get(memo.surface)
    second: Outcome | None = None
    error = None
    if verifier is not None:
        try:
            second = verifier(db, memo)
        except Exception as exc:  # noqa: BLE001 - an unread second check is retried by the sweep
            error = f"{type(exc).__name__}: {exc}"[:200]
    at = _now(now).isoformat()
    if second is None:
        memo.confirmation = {**status, "status": "unread", "attempts": attempts, "error": error, "at": at}
    elif second.value != memo.outcome:
        memo.confirmation = {**status, "status": "disagreed", "attempts": attempts, "second": second.value, "at": at}
    elif memo.outcome == Outcome.RIGHT.value and (found := _rules_find_something(str((memo.payload or {}).get("answer") or memo.answer_norm))):
        memo.confirmation = {**status, "status": "rules_disagree", "attempts": attempts, "rules": found[:5], "at": at}
    else:
        memo.state = "confirmed"
        memo.confirmed_at = _now(now)
        memo.confirmation = {**status, "status": "agreed", "attempts": attempts, "second": second.value, "at": at}
    flag_modified(memo, "confirmation")
    db.add(memo)
    db.flush([memo])
    logger.info("answer_memo_confirm memo={} surface={} status={}", memo.id, memo.surface, memo.confirmation.get("status"))
    return memo.state


def sweep(db: Session, *, limit: int = 100) -> int:
    """Re-send the second check of every candidate still waiting for one. Commits nothing."""

    if not enabled():
        return 0
    sent = 0
    for memo in db.scalars(
        select(AnswerMemo).where(AnswerMemo.state == "candidate").order_by(AnswerMemo.created_at).limit(limit)
    ):
        status = dict(memo.confirmation or {})
        if status.get("status") not in {"queued", "unread"} or int(status.get("attempts") or 0) >= MAX_CONFIRM_ATTEMPTS:
            continue
        try:
            dispatcher(str(memo.id))
            sent += 1
        except Exception as exc:  # noqa: BLE001 - next sweep
            logger.warning("answer_memo: confirmation not sent ({})", exc)
            break
    return sent


# ---------------------------------------------------------------------------
# Revoke
# ---------------------------------------------------------------------------


def _take_back_forge(db: Session, row: Mapping[str, Any], memo: AnswerMemo, now: datetime) -> bool:
    """Supersede a Forge answer the memo settled with an unread reading, and void its gold."""

    from app.db.models.atelier import AtelierAttempt
    from app.db.models.gold import GoldLedgerEntry
    from app.services import gold_ledger

    attempt = db.get(AtelierAttempt, uuid.UUID(str(row["subject_id"])))
    if attempt is None:
        return False
    correction = dict(attempt.correction_payload or {})
    debug = correction.get("correction_debug") if isinstance(correction.get("correction_debug"), dict) else {}
    if str(debug.get("memo") or "") != str(memo.id):
        return False  # a later check already replaced the memo's reading
    reason = f"memo_revoked:{memo.id}"
    correction.update(
        {
            "verdict": "needs_review",
            "assessment_status": "unavailable",
            "local_status": None,
            "ai_review": {"status": "failed", "error": reason, "completed_at": now.isoformat()},
            "memo_revoked": {"memo": str(memo.id), "at": now.isoformat(), "was": correction.get("verdict")},
        }
    )
    attempt.correction_payload = correction
    attempt.verdict = "needs_review"
    flag_modified(attempt, "correction_payload")
    db.add(attempt)
    key = row.get("gold_key") or f"gold:forge:{attempt.id}"
    entry = db.scalars(
        select(GoldLedgerEntry).where(GoldLedgerEntry.user_id == attempt.user_id, GoldLedgerEntry.source_key == key)
    ).first()
    if entry is not None and entry.state != "void":
        gold_ledger.void_verdict_payment(db, entry=entry, reason=reason, now=now)
    return True


_TAKERS: dict[str, Callable[[Session, Mapping[str, Any], AnswerMemo, datetime], bool]] = {
    "forge_attempt": _take_back_forge,
}


def revoke(db: Session, memo_id: Any, *, reason: str = "", now: datetime | None = None) -> dict[str, Any]:
    """End a memo; take back every answer it settled that a surface can take back.

    A Forge answer is superseded (the ledger writes an unread record) and its gold voided.
    A placement turn keeps its grading: the placement it belongs to has ended, and it paid
    nothing. Flushes, never commits.
    """

    now = _now(now)
    memo = db.get(AnswerMemo, uuid.UUID(str(memo_id)))
    if memo is None:
        return {"state": "missing", "taken_back": 0}
    if memo.state == "revoked":
        return {"state": "revoked", "taken_back": 0}
    memo.state = "revoked"
    memo.revoked_at = now
    memo.revoked_reason = (reason or "revoked")[:400]
    db.add(memo)
    taken = 0
    for row in memo.settled or []:
        taker = _TAKERS.get(str(row.get("subject_type")))
        if taker is not None and taker(db, row, memo, now):
            taken += 1
    db.flush()
    logger.info("answer_memo_revoked memo={} taken_back={}", memo.id, taken)
    return {"state": "revoked", "taken_back": taken}


def listing(db: Session, *, limit: int = 100) -> dict[str, Any]:
    """For ``/pilot-ops``: candidates and confirmed memos, newest first."""

    def row(memo: AnswerMemo) -> dict[str, Any]:
        return {
            "id": str(memo.id),
            "surface": memo.surface,
            "item": memo.item_label,
            "answer": memo.answer_norm,
            "outcome": memo.outcome,
            "edits": len(memo.edits or []),
            "state": memo.state,
            "confirmation": (memo.confirmation or {}).get("status"),
            "hits": int(memo.hits or 0),
            "created_at": memo.created_at.isoformat() if memo.created_at else None,
            "confirmed_at": memo.confirmed_at.isoformat() if memo.confirmed_at else None,
        }

    out: dict[str, Any] = {}
    for state in ("candidate", "confirmed"):
        memos = db.scalars(
            select(AnswerMemo).where(AnswerMemo.state == state).order_by(AnswerMemo.created_at.desc()).limit(limit)
        ).all()
        out[state] = [row(memo) for memo in memos]
    return out
