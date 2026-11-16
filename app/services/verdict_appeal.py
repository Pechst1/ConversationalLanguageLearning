"""Package V stage 5: the appeal. «I think this is right», re-judged by the stronger model.

Under a «not yet» or «partly» drill verdict, the learner can say the judge is wrong. Before,
a wrong verdict could only be found by a walk (#174). Now :func:`appeal`:

1. checks the answer is the learner's, still appealable, appealed once, and within the
   day's limit (:data:`settings.VERDICT_APPEAL_DAILY_LIMIT`, three; owner decision 4);
2. asks the stronger model (:data:`settings.VERDICT_APPEAL_MODEL`) with the appeal
   prompt. The model only rules; :func:`app.services.judge.judge` makes the verdict from
   its ruling, as from any reading;
3. **upheld**: a ledger record supersedes the drill's record, the step's stored result is
   amended, and the memo gains the answer (confirmed: an appeal upheld *is* the second,
   independent reading), so the next learner who writes it is right with no call.
   ``scripts/verdict_appeal_export.py`` writes the case to ``tests/verdict_corpus/candidates/``
   for the night shift;
4. **refused**: the learner gets the model's reason, one sentence in their language;
5. a model that could not be asked leaves the verdict as it was and does not count.

The appeal is answered inline, like «Check again» (stage 3): the learner taps and waits
for one call.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.core.verdict import Call, CheckedBy, Outcome, Verdict
from app.db.models.verdict_appeal import VerdictAppeal
from app.services.judge import Reading, judge

__all__ = [
    "APPEAL_SYSTEM_PROMPT",
    "AppealClosed",
    "AppealLimit",
    "AppealResult",
    "AppealRuling",
    "appeal",
    "appealable",
    "remaining_today",
]

#: The verdicts a learner may appeal.
APPEALABLE = (Outcome.NOT_YET, Outcome.PARTLY)


class AppealRuling(BaseModel):
    """What the stronger model answers. ``reason_native``: one sentence, the learner's language."""

    upheld: bool
    reason_native: str = Field(default="", max_length=400)


APPEAL_SYSTEM_PROMPT = (
    "You are the appeal judge of a French course. A learner answered one exercise, was told "
    "the answer is not right yet, and says it is right. Read the exercise, its expected "
    "answers and the learner's answer, and decide fairly whether the learner's answer does "
    "what the exercise asks in correct French. Accept any correct French: other words or word "
    "order, both apostrophes, «?» with or without a space, and the spellings of the 1990 "
    "reform. A missing accent that changes the word, a wrong agreement, a wrong form of the "
    "taught rule, or an answer that does not do the task is not right. "
    "Set upheld to true only if the answer is right. reason_native is ONE short sentence in "
    "the language whose code is reason_language, said to the learner with «tu»/«du»: why it "
    "is right, or the one thing that is not. Quote French words in French. "
    "Return only JSON matching output_schema."
)


class AppealLimit(Exception):
    """The learner has used the day's appeals."""


class AppealClosed(Exception):
    """Nothing to appeal here: not theirs, not a «not yet» or «partly», or not a drill."""


@dataclass(frozen=True)
class AppealResult:
    state: str
    verdict: Verdict
    reason: str | None
    remaining: int
    appeal_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "check": self.verdict.to_dict(),
            "reason": self.reason,
            "remaining_today": self.remaining,
            "appeal_id": self.appeal_id,
        }


def _now(now: datetime | None = None) -> datetime:
    return now or datetime.now(UTC)


def _day_start(now: datetime) -> datetime:
    return datetime.combine(now.astimezone(UTC).date(), time.min, tzinfo=UTC)


def _client() -> Any:
    """The provider (the walk's fake-provider server replaces this, like the story engine's)."""

    from app.services.llm_service import LLMService

    return LLMService()


def _model() -> str:
    return str(settings.VERDICT_APPEAL_MODEL or settings.STORY_CRITIC_MODEL or settings.OPENAI_MODEL)


def used_today(db: Session, user_id: Any, *, now: datetime | None = None) -> int:
    """Appeals that asked the model today (an unread one does not count)."""

    start = _day_start(_now(now))
    return int(
        db.scalar(
            select(func.count(VerdictAppeal.id)).where(
                VerdictAppeal.user_id == user_id,
                VerdictAppeal.created_at >= start,
                VerdictAppeal.created_at < start + timedelta(days=1),
                VerdictAppeal.state.in_(("upheld", "refused")),
            )
        )
        or 0
    )


def remaining_today(db: Session, user_id: Any, *, now: datetime | None = None) -> int:
    return max(0, int(settings.VERDICT_APPEAL_DAILY_LIMIT) - used_today(db, user_id, now=now))


def appealable(check: Any) -> bool:
    """Whether a verdict (a ``Verdict`` or its dict) shows the appeal line."""

    outcome = check.outcome.value if isinstance(check, Verdict) else (check or {}).get("outcome")
    return bool(settings.VERDICT_APPEAL_ENABLED) and outcome in {item.value for item in APPEALABLE}


# ---------------------------------------------------------------------------
# The drill a learner appeals
# ---------------------------------------------------------------------------


@dataclass
class _Drill:
    step: Any
    task: Any
    text: str
    verdict: Verdict
    item: dict[str, Any]


def _drill(db: Session, *, user: Any, step_id: Any) -> _Drill:
    from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
    from app.services import verdicts
    from app.services.daily_journey import _recall_task_from_json
    from app.services.journey_contracts import TaskOutcome

    try:
        step = db.get(DailyJourneyStep, uuid.UUID(str(step_id)))
    except ValueError as exc:
        raise AppealClosed("not_found") from exc
    journey = db.get(DailyJourney, step.journey_id) if step is not None else None
    if step is None or journey is None or str(journey.user_id) != str(user.id):
        raise AppealClosed("not_found")
    private = dict(step.private_task or {})
    result = dict(private.get("result") or {})
    if not private.get("recall_task") or not result:
        raise AppealClosed("not_a_drill")
    task = _recall_task_from_json(private["recall_task"])
    text = str(result.get("answer_text") or "")
    if not text.strip() or result.get("failure_reason") == "empty_answer":
        raise AppealClosed("no_answer")
    try:
        outcome = TaskOutcome(str(result.get("outcome") or ""))
    except ValueError as exc:
        raise AppealClosed("not_appealable") from exc
    verdict = verdicts.from_recall(outcome=outcome, text=text)
    item = {
        "format": task.task_type,
        "instruction_native": task.instruction_native,
        "prompt_fr": task.prompt_fr,
        "source_fr": task.source_fr,
        "expected_fr": [*(task.accepted_answers or []), *([task.solution_fr] if task.solution_fr else [])][:6],
        "options": [option.get("text") or option.get("label_fr") for option in (task.options or [])][:6],
        "target": getattr(task.target, "label_fr", None),
    }
    return _Drill(step=step, task=task, text=text, verdict=verdict, item=item)


def _ask(item: dict[str, Any], answer: str, language: str) -> AppealRuling:
    schema = AppealRuling.model_json_schema()
    content = json.dumps(
        {
            "output_schema": schema,
            "data": {"exercise": item, "learner_answer": answer, "reason_language": language},
        },
        ensure_ascii=False,
    )
    result = _client().generate_chat_completion(
        [{"role": "user", "content": content}],
        system_prompt=APPEAL_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=600,
        response_format={"type": "json_object"},
        model=_model(),
        reasoning_effort=settings.VERDICT_APPEAL_REASONING_EFFORT,
    )
    return AppealRuling.model_validate(json.loads(result.content))


def _amend_step(db: Session, drill: _Drill, appeal_id: str, now: datetime) -> None:
    """Upheld settles the whole item, not only its verdict (#729).

    The miss left two things beside its verdict: the stored outcome, and the item queued once
    more at the end of its set. Both go: the outcome is «met», and the retry leaves the day.
    """

    from app.services.daily_journey import withdraw_retry
    from app.services.journey_contracts import TaskOutcome

    private = dict(drill.step.private_task or {})
    result = dict(private.get("result") or {})
    result["appeal"] = {"state": "upheld", "id": appeal_id, "at": now.isoformat(), "was": result.get("outcome")}
    result["outcome"] = str(TaskOutcome.MET)
    private["result"] = result
    drill.step.private_task = private
    flag_modified(drill.step, "private_task")
    withdraw_retry(db, drill.step)


def _remember(db: Session, drill: _Drill, appeal_id: str, now: datetime) -> Any:
    """An appeal upheld is the second, independent reading: the memo is confirmed at once."""

    from app.services import answer_memo

    if drill.task.task_type in {"choice", "classify", "listen_tap", "who_said", "match_pairs", "tiles", "word_bank", "unscramble", "dictation"}:
        return None
    memo = answer_memo.remember(
        db,
        task=answer_memo.recall_task(drill.task),
        answer=drill.text,
        outcome=Outcome.RIGHT,
        payload={"answer": drill.text, "appeal": appeal_id},
        backing={"subject_type": "journey_step", "subject_id": str(drill.step.id), "appeal": appeal_id},
        label=f"{drill.task.task_type} · {drill.task.prompt_fr or drill.task.source_fr or drill.task.solution_fr or ''}",
    )
    if memo is not None and memo.state == "candidate":
        memo.state = "confirmed"
        memo.confirmed_at = now
        memo.confirmation = {**(memo.confirmation or {}), "status": "appeal_upheld", "appeal": appeal_id}
        flag_modified(memo, "confirmation")
        db.add(memo)
    return memo


def appeal(
    db: Session,
    *,
    user: Any,
    subject_type: str,
    subject_id: Any,
    language: str = "en",
    now: datetime | None = None,
) -> AppealResult:
    """Appeal one verdict. Raises :class:`AppealClosed` or :class:`AppealLimit`. Commits."""

    from app.services import verdict_ledger

    now = _now(now)
    if not settings.VERDICT_APPEAL_ENABLED or subject_type != "journey_step":
        raise AppealClosed("not_appealable")
    drill = _drill(db, user=user, step_id=subject_id)
    previous = db.scalars(
        select(VerdictAppeal)
        .where(
            VerdictAppeal.subject_type == subject_type,
            VerdictAppeal.subject_id == str(drill.step.id),
            VerdictAppeal.state.in_(("upheld", "refused")),
        )
        .limit(1)
    ).first()
    if previous is not None:
        # One appeal per answer: asking again returns the same ruling, and costs nothing.
        shown = drill.verdict
        return AppealResult(previous.state, shown, previous.reason, remaining_today(db, user.id, now=now), str(previous.id))
    if not appealable(drill.verdict):
        raise AppealClosed("not_appealable")
    if remaining_today(db, user.id, now=now) <= 0:
        raise AppealLimit("daily_limit")

    row = VerdictAppeal(
        id=uuid.uuid4(),
        user_id=user.id,
        surface="recall",
        subject_type=subject_type,
        subject_id=str(drill.step.id),
        answer_text=drill.text,
        item=drill.item,
        verdict_before=drill.verdict.to_dict(),
        state="unread",
        reason_language=language,
        created_at=now,
    )
    try:
        ruling = _ask(drill.item, drill.text, language)
    except Exception as exc:  # noqa: BLE001 - an appeal nobody could read changes nothing and costs nothing
        logger.warning("verdict_appeal: the appeal model did not answer ({})", exc)
        row.ruling = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        db.add(row)
        db.commit()
        return AppealResult("unread", drill.verdict, None, remaining_today(db, user.id, now=now), str(row.id))

    row.ruling = {**ruling.model_dump(), "model": _model()}
    row.reason = (ruling.reason_native or "").strip()[:400] or None
    task = drill.task
    from app.services import answer_memo

    judge_task = answer_memo.recall_task(task)
    before = Reading(outcome=drill.verdict.outcome, by=drill.verdict.checked_by, call=drill.verdict.call)
    if ruling.upheld:
        reading = Reading(outcome=Outcome.RIGHT, by=CheckedBy.MODEL, call=Call.OK)
        row.state = "upheld"
        # The ledger keeps the drill's verdict and the appeal's, the second superseding the first.
        if verdict_ledger.live_record(db, "journey_step", drill.step.id) is None:
            verdict_ledger.supersede(
                db, user_id=user.id, surface="recall", subject_type="journey_step", subject_id=drill.step.id,
                answer=drill.text, reading=before, task=judge_task, now=now,
            )
        record = verdict_ledger.supersede(
            db, user_id=user.id, surface="recall", subject_type="journey_step", subject_id=drill.step.id,
            answer=drill.text, reading=reading, task=judge_task, now=now,
        )
        row.record_id = record.id if record is not None else None
        _amend_step(db, drill, str(row.id), now)
        memo = _remember(db, drill, str(row.id), now)
        row.memo_id = memo.id if memo is not None else None
    else:
        reading = before
        row.state = "refused"
    verdict = judge(judge_task, drill.text, reading=reading, user=user)
    db.add(row)
    db.commit()
    logger.info("verdict_appeal state={} step={} user={}", row.state, drill.step.id, user.id)
    return AppealResult(row.state, verdict, row.reason, remaining_today(db, user.id, now=now), str(row.id))
