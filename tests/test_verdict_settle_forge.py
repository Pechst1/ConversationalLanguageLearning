"""Stage R1: a La Forge free sentence the model could not read is checked later, by the job.

12 Nov 2026: the provider refused every call for two nights. Every Forge free sentence
ended «Answer saved, not checked yet» and stayed that way: the Courrier and the Journal had
a background recheck (:mod:`app.services.verdict_settle`), the Forge did not. Now, behind
``VERDICT_SETTLE_FORGE``, a failed second check queues a settlement; the job puts the
review back to ``pending`` and runs the relecture an on-time check runs, so the late
reading writes the séance's evidence, the item's gold and the error memory exactly once.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.db.models.gold import GoldLedgerEntry
from app.db.models.verdict_settlement import VerdictSettlement
from app.services import verdict_ledger, verdict_settle, verdicts
from app.services.llm_service import LLMResult
from app.tasks import verdict_settle as settle_task
from tests.test_forge_integration import _forge_session

ANSWER = "Je ne bois pas de café le soir."
LATER = timedelta(days=1)


class _Model:
    """The model client: it fails ``failures`` times, then reads the sentence as right.

    ``during`` runs inside the next call (once): another run landing while this one reads.
    """

    def __init__(self, failures: int = 0):
        self.failures = failures
        self.calls = 0
        self.during = None

    def generate_error_detection(self, messages, **kwargs):
        from app.services.llm_service import LLMProviderError

        self.calls += 1
        during, self.during = self.during, None
        if during is not None:
            during()
        if self.calls <= self.failures:
            raise LLMProviderError("429: insufficient_quota")
        content = {
            "verdict": "accepted",
            "score_0_4": 4,
            "corrected_answer": ANSWER,
            "concept_hits": [],
            "missing_targets": [],
            "errata": [],
        }
        return LLMResult(
            provider="openai",
            model="gpt-4o",
            content=json.dumps(content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


@pytest.fixture(autouse=True)
def forge_settles(monkeypatch):
    monkeypatch.setattr(settings, "VERDICT_SETTLE_ENABLED", True)
    monkeypatch.setattr(settings, "VERDICT_SETTLE_FORGE", True)
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture()
def eager(db_session, monkeypatch):
    """Celery runs the job inline, on the test's session."""

    @contextmanager
    def same_session():
        yield db_session

    monkeypatch.setitem(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(settle_task, "_session", same_session)
    monkeypatch.setattr(verdict_settle, "dispatcher", verdict_settle._dispatch_celery)


@pytest.fixture()
def evidence_writes(monkeypatch):
    """Every piece of Forge evidence written (an unread answer writes none)."""

    from app.services.forge import ForgeService

    written: list = []
    original = ForgeService._write_evidence

    def counting(self, **kwargs):
        if kwargs["decision"].evidence is not None:
            written.append(kwargs["attempt"].id)
        return original(self, **kwargs)

    monkeypatch.setattr(ForgeService, "_write_evidence", counting)
    return written


def _answered(db_session: Session, monkeypatch, model: _Model, *, text: str | None = None, configured: bool = True):
    """A Forge séance at PRODUCE; one free sentence answered, its second check run once."""

    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: configured)
    monkeypatch.setattr(verdict_settle, "_forge_corrector", lambda db: AtelierCorrectionService(db, llm_service=model))
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    if text is None:
        text = ANSWER
    elif text == "key":
        text = str(nxt["item"]["example_answer"] if "item" in nxt else nxt["items"][0]["example_answer"])
    service = AtelierCorrectionService(db_session, llm_service=model)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": text},
    )
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    if configured:
        attempt = service.run_ai_review_for_attempt(attempt.id)
    return user, session, service, attempt


def _settlements(db, subject_id) -> list[VerdictSettlement]:
    db.flush()
    return list(
        db.scalars(
            select(VerdictSettlement)
            .where(VerdictSettlement.subject_id == str(subject_id))
            .order_by(VerdictSettlement.created_at, VerdictSettlement.attempt)
        )
    )


def _forge_gold(db, user_id, attempt_id) -> list[GoldLedgerEntry]:
    db.flush()
    return [
        entry
        for entry in db.scalars(
            select(GoldLedgerEntry).where(
                GoldLedgerEntry.user_id == user_id, GoldLedgerEntry.source_key == f"gold:forge:{attempt_id}"
            )
        )
        if entry.state != "void"
    ]


def _check(attempt) -> dict:
    return verdicts.from_forge(attempt.correction_payload, text=ANSWER, verdict=attempt.verdict).to_dict()


def test_fails_twice_then_is_checked_later_with_its_evidence_and_gold_once(
    db_session: Session, monkeypatch, eager, evidence_writes
) -> None:
    from app.services.atelier import AtelierSRSService

    # The relecture fails, then the job's first attempt fails, then the second reads it.
    model = _Model(failures=2)
    user, session, _service, attempt = _answered(db_session, monkeypatch, model)
    assert attempt.correction_payload["assessment_status"] == "unavailable"
    assert _check(attempt)["retryable"] is True
    assert [row.state for row in _settlements(db_session, attempt.id)] == ["queued"]
    unread = verdict_ledger.live_record(db_session, "forge_attempt", attempt.id)
    assert unread is not None and not unread.counts
    assert evidence_writes == [] and _forge_gold(db_session, user.id, attempt.id) == []

    # The séance closes while the answer is still unread.
    AtelierSRSService(db_session).complete_session(session=session, user=user)
    db_session.expire_all()
    assert session.status == "completed"

    clock = [datetime.now(UTC) + LATER]
    monkeypatch.setattr(verdict_settle, "_clock", lambda: clock[0])
    assert verdict_settle.sweep(db_session) == 1
    assert [row.state for row in _settlements(db_session, attempt.id)] == ["queued", "unread"]
    clock[0] += LATER
    assert verdict_settle.sweep(db_session) == 1

    db_session.expire_all()
    assert model.calls == 3
    assert [row.state for row in _settlements(db_session, attempt.id)][-1] == "settled"
    attempt = db_session.get(type(attempt), attempt.id)
    assert attempt.correction_payload["assessment_status"] == "checked"
    assert attempt.correction_payload["ai_review"]["status"] == "complete"
    assert _check(attempt)["counts"] is True, "the next load shows the settled verdict"
    live = verdict_ledger.live_record(db_session, "forge_attempt", attempt.id)
    assert live.counts and live.supersedes_id is not None
    assert verdict_settle.checked_since(db_session, "forge_attempt", attempt.id) is not None
    # The chain reaches back to the unread record it supersedes.
    from app.db.models.verdict_record import VerdictRecord

    chain, cursor = [], live
    while cursor is not None and cursor.supersedes_id is not None:
        cursor = db_session.get(VerdictRecord, cursor.supersedes_id)
        chain.append(cursor.id)
    assert unread.id in chain

    assert evidence_writes == [attempt.id], "the late reading counts once, after the séance closed"
    assert attempt.correction_payload["evidence_applied"]["mode"] == "forge"
    gold = _forge_gold(db_session, user.id, attempt.id)
    assert len(gold) == 1 and gold[0].state == "settled"

    # Nothing is sent again.
    clock[0] += LATER
    assert verdict_settle.sweep(db_session) == 0


def test_settling_twice_writes_evidence_and_pays_gold_once(
    db_session: Session, monkeypatch, evidence_writes
) -> None:
    model = _Model(failures=1)
    user, _session, _service, attempt = _answered(db_session, monkeypatch, model)
    later = datetime.now(UTC) + LATER

    assert verdict_settle.settle(db_session, "forge_attempt", attempt.id, now=later) == "settled"
    gold = [(entry.id, entry.amount) for entry in _forge_gold(db_session, user.id, attempt.id)]
    applied = db_session.get(type(attempt), attempt.id).correction_payload["evidence_applied"]

    # Again: the job retried, or the learner's «Check again» was queued too.
    assert verdict_settle.settle(db_session, "forge_attempt", attempt.id, now=later) == "settled"
    db_session.expire_all()
    assert model.calls == 2, "a settled answer is never read again"
    assert evidence_writes == [attempt.id]
    assert [(entry.id, entry.amount) for entry in _forge_gold(db_session, user.id, attempt.id)] == gold
    assert len(gold) == 1
    assert db_session.get(type(attempt), attempt.id).correction_payload["evidence_applied"] == applied


def test_a_run_that_lands_while_the_job_reads_is_kept_and_counted_once(
    db_session: Session, monkeypatch, evidence_writes
) -> None:
    """The race: «Check again» and the job both started from «failed», both read it."""

    from app.services.atelier import AtelierCorrectionService

    model = _Model(failures=1)
    user, _session, service, attempt = _answered(db_session, monkeypatch, model)
    attempt, started = service.mark_ai_review_pending(attempt)
    assert started
    other = AtelierCorrectionService(db_session, llm_service=_Model())
    model.during = lambda: other.run_ai_review_for_attempt(attempt.id)

    service.run_ai_review_for_attempt(attempt.id)  # lands second, under the row lock

    db_session.expire_all()
    attempt = db_session.get(type(attempt), attempt.id)
    assert attempt.correction_payload["ai_review"]["status"] == "complete"
    assert evidence_writes == [attempt.id]
    assert len(_forge_gold(db_session, user.id, attempt.id)) == 1


def test_a_failure_after_another_run_landed_does_not_undo_it(db_session: Session, monkeypatch, evidence_writes) -> None:
    from app.services.atelier import AtelierCorrectionService

    model = _Model(failures=2)
    user, _session, service, attempt = _answered(db_session, monkeypatch, model)
    attempt, _started = service.mark_ai_review_pending(attempt)
    other = AtelierCorrectionService(db_session, llm_service=_Model())
    model.during = lambda: other.run_ai_review_for_attempt(attempt.id)

    service.run_ai_review_for_attempt(attempt.id)  # this call fails, after the other landed

    db_session.expire_all()
    attempt = db_session.get(type(attempt), attempt.id)
    assert attempt.correction_payload["assessment_status"] == "checked"
    assert _check(attempt)["counts"] is True
    assert evidence_writes == [attempt.id]
    assert verdict_ledger.live_record(db_session, "forge_attempt", attempt.id).counts


def test_the_cap_leaves_it_not_checked_and_it_is_not_retried(db_session: Session, monkeypatch, eager) -> None:
    monkeypatch.setattr(settings, "VERDICT_SETTLE_MAX_ATTEMPTS", 2)
    model = _Model(failures=99)
    _user, _session, _service, attempt = _answered(db_session, monkeypatch, model)
    clock = [datetime.now(UTC) + LATER]
    monkeypatch.setattr(verdict_settle, "_clock", lambda: clock[0])

    for _ in range(5):
        verdict_settle.sweep(db_session)
        clock[0] += 2 * LATER
    states = [row.state for row in _settlements(db_session, attempt.id)]
    assert states == ["queued", "unread", "unread", "gave_up"]
    assert model.calls == 3, "the relecture, then two background attempts"
    assert verdict_settle.sweep(db_session) == 0
    db_session.expire_all()
    attempt = db_session.get(type(attempt), attempt.id)
    assert attempt.correction_payload["assessment_status"] == "unavailable"
    assert verdict_ledger.live_record(db_session, "forge_attempt", attempt.id).counts is False


def test_flag_off_queues_nothing_and_settles_nothing(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "VERDICT_SETTLE_FORGE", False)
    sent: list = []
    monkeypatch.setattr(verdict_settle, "dispatcher", lambda *args: sent.append(args))
    _user, _session, _service, attempt = _answered(db_session, monkeypatch, _Model(failures=99))

    assert attempt.correction_payload["assessment_status"] == "unavailable"
    assert _settlements(db_session, attempt.id) == []
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + LATER) == 0 and sent == []
    assert verdict_settle.settle(db_session, "forge_attempt", attempt.id) == "off"


def test_an_answer_the_key_accepts_is_never_queued(db_session: Session, monkeypatch) -> None:
    _user, _session, _service, attempt = _answered(db_session, monkeypatch, _Model(failures=99), text="key")

    assert attempt.correction_payload["local_status"] == "right"
    assert attempt.correction_payload["second_check"]["status"] == "failed"
    assert _check(attempt)["counts"] is True
    assert _settlements(db_session, attempt.id) == []


def test_with_no_model_configured_nothing_is_queued(db_session: Session, monkeypatch) -> None:
    _user, _session, _service, attempt = _answered(db_session, monkeypatch, _Model(), configured=False)

    assert attempt.correction_payload["ai_review"]["status"] == "failed"
    assert _check(attempt)["failure"] == "no_model"
    assert _settlements(db_session, attempt.id) == []


def test_a_review_that_could_not_run_is_failed_and_queued(db_session: Session, monkeypatch) -> None:
    """The worker died around the call: «pending» for ever becomes a failure the job retries."""

    from app.services import atelier as atelier_module
    from app.services.atelier import AtelierCorrectionService

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    user, concept, session, _shared = _forge_session(db_session)
    from app.core.forge import Rung
    from app.services.forge import ForgeService, _store_state, forge_state_of

    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    attempt = AtelierCorrectionService(db_session, llm_service=_Model()).submit_attempt(
        session=session, user=user, concept=concept, round_name="sentence", mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}", answer_payload={"text": ANSWER},
    )
    assert attempt.correction_payload["ai_review"]["status"] == "pending"

    def crash(self, attempt_id):
        raise RuntimeError("worker lost its connection")

    monkeypatch.setattr(AtelierCorrectionService, "run_ai_review_for_attempt", crash)
    monkeypatch.setattr(atelier_module, "SessionLocal", lambda: _Unclosed(db_session))
    atelier_module.run_atelier_ai_review(attempt.id)

    db_session.expire_all()
    attempt = db_session.get(type(attempt), attempt.id)
    assert attempt.correction_payload["ai_review"]["status"] == "failed"
    assert _check(attempt)["retryable"] is True
    assert [row.state for row in _settlements(db_session, attempt.id)] == ["queued"]


class _Unclosed:
    """The test's session, handed to the worker without letting it close."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        return None


def test_a_backlog_after_an_outage_never_spends_more_than_the_daily_budget(
    db_session: Session, monkeypatch
) -> None:
    """Forty unread sentences, budget twenty: twenty go today, the rest after midnight UTC."""

    monkeypatch.setattr(settings, "VERDICT_SETTLE_DAILY_BUDGET", 20)
    _user, _session, _service, attempt = _answered(db_session, monkeypatch, _Model(failures=99))
    import uuid as _uuid

    now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    first = _settlements(db_session, attempt.id)[0]
    for _ in range(39):  # the rest of the backlog, same learner
        db_session.add(
            VerdictSettlement(
                id=_uuid.uuid4(), user_id=first.user_id, subject_type="forge_attempt", subject_id=str(_uuid.uuid4()),
                source="auto", state="queued", attempt=0, next_at=now - timedelta(hours=1), created_at=now - timedelta(hours=2),
            )
        )
    first.next_at = now - timedelta(hours=1)
    db_session.commit()
    sent: list = []

    def run(subject_type, subject_id, source):
        sent.append(subject_id)
        verdict_settle._log(
            db_session, subject_type=subject_type, subject_id=subject_id, user_id=first.user_id, record=None,
            state="unread", attempt=1, next_at=now + timedelta(minutes=30), now=now,
        )
        db_session.commit()

    monkeypatch.setattr(verdict_settle, "dispatcher", run)
    assert verdict_settle.sweep(db_session, now=now) == 20
    assert verdict_settle.sweep(db_session, now=now + timedelta(hours=1)) == 0, "the day's budget is spent"
    assert verdict_settle.sweep(db_session, now=now + timedelta(hours=3)) == 0
    tomorrow = datetime(2026, 11, 14, 0, 5, tzinfo=UTC)
    assert verdict_settle.sweep(db_session, now=tomorrow) == 20
    assert len(sent) == 40
