"""Package V stage 3: an answer nobody could read is checked later, by a job, and paid then.

Before, an answer saved during a provider outage stayed «not checked» until the learner
pressed «Check again», and a letter finished in that state never paid its gold or its token.
Now the ledger record of an unread answer queues ``settle_verdict``
(:mod:`app.services.verdict_settle`, run by :mod:`app.tasks.verdict_settle`):

* capped attempts with backoff, and a per-learner daily budget of background checks;
* a broker that refuses the task leaves the record retryable, and the sweep sends it again;
* when the check lands, the new record supersedes the unread one, and a finished letter
  pays its gold and its token then, once;
* the screen says it was checked since («checked_since» on the check).

The end-to-end test goes through the real routes with Celery eager.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

import app.services.missions as missions_module
from app.celery_app import celery_app
from app.config import settings
from app.db.models.gold import GoldLedgerEntry
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.verdict_settlement import VerdictSettlement
from app.services import verdict_ledger, verdict_settle
from app.services.llm_service import LLMProviderError
from app.services.missions import MissionConversationService
from app.tasks import verdict_settle as settle_task
from tests import test_journal_api as _journal
from tests.test_failed_check_counts_for_nothing import (
    SEEN_BY_RULES,
    UNSEEN_BY_RULES,
    _a_grade,
    _begin,
    _Client,
)

LATER = timedelta(days=1)

# The journal API's fixtures, by name (assigned, not imported, so a test's parameter reads as one).
fake_checker = _journal.fake_checker
journal_client = _journal.journal_client
journal_table = _journal.journal_table


@pytest.fixture(autouse=True)
def gold_on(monkeypatch):
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture()
def eager(db_session, monkeypatch):
    """Celery runs the job inline, on the test's session."""

    @contextmanager
    def same_session():
        yield db_session

    monkeypatch.setattr(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(settle_task, "_session", same_session)
    monkeypatch.setattr(verdict_settle, "dispatcher", verdict_settle._dispatch_celery)


def _letter_gold(db, user_id) -> list[GoldLedgerEntry]:
    db.flush()
    return [
        entry
        for entry in db.scalars(select(GoldLedgerEntry).where(GoldLedgerEntry.user_id == user_id))
        if entry.state != "void"
    ]


def _settlements(db, subject_id) -> list[VerdictSettlement]:
    db.flush()
    return list(
        db.scalars(
            select(VerdictSettlement)
            .where(VerdictSettlement.subject_id == str(subject_id))
            .order_by(VerdictSettlement.created_at, VerdictSettlement.attempt)
        )
    )


def _down_letter(client, db_session, monkeypatch):
    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=LLMProviderError("down")))
    sent = client.post(
        f"/api/v1/missions/{mission_id}/submit", json={"text": UNSEEN_BY_RULES, "mode": "writing"}, headers=headers
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["check"]["counts"] is False
    db_session.expire_all()
    attempt = db_session.scalars(
        select(RealWorldMissionAttempt).where(RealWorldMissionAttempt.mission_id == UUID(mission_id))
    ).one()
    return headers, mission_id, attempt


def test_an_answer_saved_unread_is_checked_later_and_its_letter_pays_once(client, db_session, monkeypatch, eager):
    minted: list = []
    monkeypatch.setattr(
        "app.services.atelier_rewards.AtelierRewardService.mint_logo_token_for_mission",
        lambda self, mission: minted.append(mission.id) or [{"kind": "logo_token"}],
    )
    headers, mission_id, attempt = _down_letter(client, db_session, monkeypatch)
    user_id = attempt.user_id

    # The unread answer is queued, not left to the learner.
    queued = _settlements(db_session, attempt.id)
    assert [row.state for row in queued] == ["queued"]

    assert client.post(f"/api/v1/missions/{mission_id}/complete", headers=headers).status_code == 200
    assert _letter_gold(db_session, user_id) == [] and minted == []

    # The provider comes back; the sweep sends the job; Celery runs it.
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=_a_grade(UNSEEN_BY_RULES)))
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + LATER) == 1

    db_session.expire_all()
    record = verdict_ledger.live_record(db_session, "courrier_attempt", attempt.id)
    assert record is not None and record.counts and record.supersedes_id is not None
    gold = _letter_gold(db_session, user_id)
    assert len(gold) == 1 and gold[0].source_key == f"gold:letter:{mission_id}"
    assert minted == [UUID(mission_id)]
    assert _settlements(db_session, attempt.id)[-1].state == "settled"

    # The screen says it was checked since.
    page = client.get(f"/api/v1/missions/{mission_id}", headers=headers).json()["mission"]
    check = page["attempts"][0]["check"]
    assert check["counts"] is True and check["outcome"] != "not_checked"
    assert check["checked_since"]
    recap = db_session.get(RealWorldMission, UUID(mission_id)).recap_payload
    assert recap["checked_since"]

    # Once: another sweep and the job sent again change nothing.
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + 2 * LATER) == 0
    assert verdict_settle.settle(db_session, "courrier_attempt", attempt.id) == "settled"
    assert len(_letter_gold(db_session, user_id)) == 1
    assert minted == [UUID(mission_id)]

    # A later record of that attempt that no longer counts takes the letter's gold back.
    row = db_session.get(RealWorldMissionAttempt, attempt.id)
    row.correction_payload = {
        **row.correction_payload,
        "verdict": "unassessed",
        "correction_debug": {"fallback_used": True, "failure": "timeout"},
    }
    row.verdict = "unassessed"
    db_session.flush()
    assert _letter_gold(db_session, user_id) == []
    voided = verdict_ledger.live_record(db_session, "courrier_attempt", attempt.id)
    assert voided.counts is False and voided.paid["gold"] < 0


def test_a_broker_that_refuses_leaves_the_record_retryable(client, db_session, monkeypatch):
    _headers, _mission_id, attempt = _down_letter(client, db_session, monkeypatch)

    def refuse(*_args, **_kwargs):
        raise ConnectionError("broker down")

    monkeypatch.setattr(verdict_settle, "dispatcher", refuse)
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + LATER) == 0
    rows = _settlements(db_session, attempt.id)
    assert rows[-1].state == "refused" and "broker down" in (rows[-1].error or "")
    record = verdict_ledger.live_record(db_session, "courrier_attempt", attempt.id)
    assert record.counts is False and record.verdict["shown"]["retryable"] is True

    sent: list = []
    monkeypatch.setattr(verdict_settle, "dispatcher", lambda *args, **kwargs: sent.append(args))
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + 2 * LATER) == 1
    assert sent == [("courrier_attempt", str(attempt.id), "auto")]


def test_attempts_are_capped_with_backoff(client, db_session, monkeypatch, eager):
    monkeypatch.setattr(settings, "VERDICT_SETTLE_MAX_ATTEMPTS", 3)
    _headers, _mission_id, attempt = _down_letter(client, db_session, monkeypatch)
    clock = [datetime.now(UTC) + LATER]
    monkeypatch.setattr(verdict_settle, "_clock", lambda: clock[0])

    # Due now; right after a failed attempt it is not due again until its backoff passes.
    assert verdict_settle.sweep(db_session) == 1
    assert verdict_settle.sweep(db_session) == 0
    for _ in range(5):
        clock[0] += LATER
        verdict_settle.sweep(db_session)
    states = [row.state for row in _settlements(db_session, attempt.id)]
    assert states.count("unread") == 3
    assert states[-1] == "gave_up"
    assert verdict_settle.sweep(db_session) == 0, "a job that gave up is not sent again"
    assert verdict_ledger.live_record(db_session, "courrier_attempt", attempt.id).counts is False


def test_background_checks_stop_at_the_daily_budget(client, db_session, monkeypatch, eager):
    monkeypatch.setattr(settings, "VERDICT_SETTLE_DAILY_BUDGET", 1)
    _headers, _mission_id, attempt = _down_letter(client, db_session, monkeypatch)
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    turn = client.post(
        f"/api/v1/missions/{_mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=_headers
    ).json()["user_turn"]

    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + LATER) == 2
    states = {
        subject: _settlements(db_session, subject)[-1].state for subject in (str(attempt.id), turn["id"])
    }
    assert sorted(states.values()) == ["over_budget", "unread"]


def test_ask_again_runs_the_same_job(client, db_session, monkeypatch):
    headers, mission_id = _begin(client, monkeypatch)
    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(error=LLMProviderError("down")))
    monkeypatch.setattr(MissionConversationService, "respond", lambda self, **_k: "Ah bon ? Raconte-moi.")
    turn_id = client.post(
        f"/api/v1/missions/{mission_id}/turns", json={"text": SEEN_BY_RULES, "mode": "chat"}, headers=headers
    ).json()["user_turn"]["id"]

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: _Client(content=_a_grade(SEEN_BY_RULES)))
    again = client.post(f"/api/v1/missions/{mission_id}/turns/{turn_id}/correction", headers=headers).json()
    assert again["check"]["counts"] is True
    assert again["check"]["checked_since"]
    rows = _settlements(db_session, turn_id)
    assert (rows[-1].source, rows[-1].state) == ("ask", "settled")
    # Asked again once it counts: nothing to do, nothing paid twice.
    assert verdict_settle.settle(db_session, "courrier_turn", turn_id, source="ask") == "settled"


def test_a_journal_paragraph_saved_unread_is_checked_later(journal_client, db_session, fake_checker, eager):
    from app.services.llm_service import LLMProviderError

    email = _journal._email()
    headers = _journal.login(journal_client, email)
    _journal._seed_scene(db_session, email)
    entry_id = journal_client.get("/api/v1/journal/state", headers=headers).json()["entry"]["id"]
    working = fake_checker.generate_error_detection

    def broken(messages, **kwargs):
        raise LLMProviderError("request timeout")

    fake_checker.generate_error_detection = broken
    written = journal_client.post(
        f"/api/v1/journal/{entry_id}/write", headers=headers, json={"text": "J’ai rapporté la livre à Romy."}
    ).json()["entry"]["correction"]["check"]
    assert written["counts"] is False and written["checked_since"] is None
    assert [row.state for row in _settlements(db_session, entry_id)] == ["queued"]

    fake_checker.generate_error_detection = working
    assert verdict_settle.sweep(db_session, now=datetime.now(UTC) + LATER) == 1
    entries = journal_client.get("/api/v1/journal/entries", headers=headers).json()
    check = next(entry for entry in entries if entry["id"] == entry_id)["correction"]["check"]
    assert check["counts"] is True and check["checked_since"]
