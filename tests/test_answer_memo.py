"""Package V stage 4: the memo. The second identical answer to a keyed item costs no call.

Before, an answer outside an item's listed variants went to the model every time: a call
every time, and possibly another verdict every time (#174). Now a model verdict on a keyed
item (placement prompt, Forge item, drill) writes a candidate memo; a second, independent
check (another prompt that agrees, and rules that find nothing for «right») confirms it;
and the judge asks the memo before the model, so the same answer is settled as
``checked_by: key`` with no call. ``/pilot-ops`` lists the memos and can revoke one, which
takes back what it settled.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.celery_app import celery_app
from app.config import settings
from app.core.verdict import Call, CheckedBy, Outcome
from app.db.models.answer_memo import AnswerMemo
from app.db.models.gold import GoldLedgerEntry
from app.services import answer_memo, gold_ledger, judge, verdict_ledger
from app.services import placement as placement_module
from app.tasks import answer_memo as memo_task
from tests.test_placement_api import _email, login, placement_client  # noqa: F401 - fixture

ANSWER = "Je voudrais un café, s’il vous plaît."


class _Grader:
    """One fake provider for the grading call and the second reading; counts both."""

    def __init__(self, *, score: float = 3.0, second: float | None = None) -> None:
        self.score = score
        self.second = score if second is None else second
        self.gradings = 0
        self.second_readings = 0

    def generate_error_detection(self, messages, **kwargs):
        second = kwargs.get("system_prompt") == placement_module.CONFIRM_SYSTEM_PROMPT
        if second:
            self.second_readings += 1
            content = {"score_0_4": self.second}
        else:
            self.gradings += 1
            content = {
                "score_0_4": self.score,
                "demonstrated_band": None,
                "dimensions": {"range": 3, "accuracy": 3, "coherence": 3, "task": 3},
                "evidence_fr": "réponse complète",
                "off_task": False,
            }
        return SimpleNamespace(
            content=json.dumps(content),
            model="test-model",
            provider="test",
            prompt_tokens=90,
            completion_tokens=30,
            total_tokens=120,
            cost=0.0003,
        )


@pytest.fixture()
def grader(monkeypatch):
    fake = _Grader()
    monkeypatch.setattr(placement_module.PlacementService, "_get_llm_service", lambda self: fake)
    return fake


@pytest.fixture(autouse=True)
def one_prompt(monkeypatch):
    """Every learner meets the same first prompt (sessions are ordered differently on purpose)."""

    real = placement_module.prompt_for_session

    def same_order(band, *, session_key, turns=None):
        return real(band, session_key="memo-test", turns=turns)

    monkeypatch.setattr(placement_module, "prompt_for_session", same_order)


@pytest.fixture()
def eager(db_session, monkeypatch):
    """Celery runs the second check inline, on the test's session."""

    @contextmanager
    def same_session():
        yield db_session

    monkeypatch.setitem(celery_app.conf, "task_always_eager", True)
    monkeypatch.setattr(memo_task, "_session", same_session)
    monkeypatch.setattr(answer_memo, "dispatcher", answer_memo._dispatch_celery)


def _first_answer(client, headers):
    started = client.post("/api/v1/placement/start", headers=headers).json()
    reply = client.post(
        f"/api/v1/placement/{started['session_id']}/respond",
        headers=headers,
        json={"answer": ANSWER, "turn_index": 0},
    )
    assert reply.status_code == 200, reply.text
    return reply.json()


def test_the_second_identical_answer_makes_no_model_call(placement_client, grader, eager, db_session):  # noqa: F811
    first = _first_answer(placement_client, login(placement_client, _email()))
    assert first["check"]["checked_by"] == "model"
    # One grading call, then the second, independent reading that confirmed the memo.
    assert (grader.gradings, grader.second_readings) == (1, 1)
    memo = db_session.scalars(select(AnswerMemo).where(AnswerMemo.surface == "placement")).one()
    assert memo.state == "confirmed"

    second = _first_answer(placement_client, login(placement_client, _email()))

    assert (grader.gradings, grader.second_readings) == (1, 1), "the same answer went to the model again"
    assert second["check"]["outcome"] == first["check"]["outcome"] == "right"
    assert second["check"]["checked_by"] == "key"
    assert second["check"]["counts"] is True
    db_session.refresh(memo)
    assert memo.hits == 1


def test_an_unconfirmed_candidate_is_never_used(placement_client, monkeypatch, eager, db_session):  # noqa: F811
    fake = _Grader(score=3.0, second=1.0)  # the second reading disagrees
    monkeypatch.setattr(placement_module.PlacementService, "_get_llm_service", lambda self: fake)

    _first_answer(placement_client, login(placement_client, _email()))
    memo = db_session.scalars(select(AnswerMemo).where(AnswerMemo.surface == "placement")).one()
    assert (memo.state, memo.confirmation["status"]) == ("candidate", "disagreed")

    _first_answer(placement_client, login(placement_client, _email()))
    assert fake.gradings == 2


def test_a_lost_confirmation_is_sent_again_by_the_sweep(placement_client, grader, monkeypatch, db_session):  # noqa: F811
    def refused(_memo_id):
        raise ConnectionError("broker down")

    monkeypatch.setattr(answer_memo, "dispatcher", refused)
    _first_answer(placement_client, login(placement_client, _email()))
    memo = db_session.scalars(select(AnswerMemo).where(AnswerMemo.surface == "placement")).one()
    assert memo.state == "candidate"

    sent: list[str] = []
    monkeypatch.setattr(answer_memo, "dispatcher", sent.append)
    assert answer_memo.sweep(db_session) == 1
    assert sent == [str(memo.id)]
    assert answer_memo.confirm(db_session, memo.id) == "confirmed"


def test_rules_that_find_a_mistake_keep_a_right_memo_a_candidate(db_session, monkeypatch):
    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    monkeypatch.setitem(answer_memo.VERIFIERS, "forge", lambda _db, _memo: Outcome.RIGHT)
    task = judge.Task("forge", item="item-rules")
    # «à le» is always «au»: the rule pass finds it, so «right» is not confirmed.
    memo = answer_memo.remember(
        db_session, task=task, answer="Je vais à le marché.", outcome=Outcome.RIGHT,
        payload={"answer": "Je vais à le marché."},
    )
    assert answer_memo.confirm(db_session, memo.id) == "candidate"
    assert memo.confirmation["status"] == "rules_disagree"


def test_a_not_yet_memo_keeps_its_edits_so_the_same_miss_gets_the_same_explanation(db_session, monkeypatch):
    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    monkeypatch.setitem(answer_memo.VERIFIERS, "forge", lambda _db, _memo: Outcome.NOT_YET)
    task = judge.Task("forge", item="item-miss")
    answer = "Elle est allé au marché."
    memo = answer_memo.remember(
        db_session,
        task=task,
        answer=answer,
        outcome=Outcome.NOT_YET,
        payload={"answer": answer},
        proposed=[
            {"span": "allé", "replacement": "allée", "note": "accord avec elle"},
            {"span": "pas là", "replacement": "x"},  # not in the answer: never kept
        ],
    )
    assert answer_memo.confirm(db_session, memo.id) == "confirmed"

    ruling = judge.consult(task, "elle est allé au marché", memos=answer_memo.Memos(db_session))
    assert ruling is not None and ruling.stage == "memo"
    verdict = ruling.verdict
    assert (verdict.outcome, verdict.checked_by, verdict.call) == (Outcome.NOT_YET, CheckedBy.KEY, Call.NOT_CALLED)
    assert [(edit.span, edit.replacement, edit.note) for edit in verdict.edits] == [("allé", "allée", "accord avec elle")]
    assert verdict.counts is True


# ---------------------------------------------------------------------------
# Forge: the relecture asks the memo first; a revoke takes back what it paid
# ---------------------------------------------------------------------------


#: Right, and not the item's listed answer: without a memo, only the model can say so.
SENTENCE = "Si je finis tôt, je te téléphonerai ce soir."


def _forge_sentence(db_session, service, concept):
    from app.db.models.atelier import AtelierSession
    from tests.test_atelier import _attach_primed_exercise_set, _user

    user = _user(db_session)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": SENTENCE},
    )
    return user, attempt


def test_a_confirmed_forge_memo_settles_the_same_sentence_without_a_call_and_a_revoke_takes_it_back(
    db_session, monkeypatch
):
    from app.services.atelier import AtelierCorrectionService
    from tests.test_atelier import _concept, _FakeLLMService

    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")
    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    second_readings: list[str] = []

    def second_reading(_db, memo):
        second_readings.append(memo.answer_norm)
        return Outcome.RIGHT

    monkeypatch.setitem(answer_memo.VERIFIERS, "forge", second_reading)
    concept = _concept(db_session, "FR_B1_COND_001")
    fake_llm = _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})
    service = AtelierCorrectionService(db_session, llm_service=fake_llm)

    # Learner A: the relecture asks the model, and its reading becomes a candidate.
    _user_a, first = _forge_sentence(db_session, service, concept)
    service.run_ai_review_for_attempt(first.id)
    calls_after_a = len(fake_llm.calls)
    assert calls_after_a >= 1
    memo = db_session.scalars(select(AnswerMemo).where(AnswerMemo.surface == "forge")).one()
    assert memo.state == "candidate"
    assert answer_memo.confirm(db_session, memo.id) == "confirmed"
    assert len(second_readings) == 1

    # Learner B, the same sentence to the same item: settled on the spot, by the memo.
    user_b, second = _forge_sentence(db_session, service, concept)

    assert len(fake_llm.calls) == calls_after_a, "the same sentence went to the model again"
    assert second.verdict in {"correct", "accepted"}
    assert second.correction_payload["assessment_status"] == "checked"
    assert second.correction_payload["correction_debug"]["memo"] == str(memo.id)
    assert service.should_auto_start_ai_review(second) is False
    record = verdict_ledger.live_record(db_session, "forge_attempt", second.id)
    assert record.counts is True
    assert record.verdict["shown"]["checked_by"] == "key"
    db_session.refresh(memo)
    assert [row["subject_id"] for row in memo.settled] == [str(second.id)]

    # It pays like any checked answer…
    gold_ledger.record_forge_item(
        db_session, user=user_b, attempt=second, rung=1,
        verdict=SimpleNamespace(checked=True, outcome="correct"), mode="seance",
        reprise=False, below_level=False, level_before=None, contact_before=None,
    )
    entry = db_session.scalars(
        select(GoldLedgerEntry).where(GoldLedgerEntry.source_key == f"gold:forge:{second.id}")
    ).one()
    assert entry.state != "void"

    # …and a revoke takes it back: the record is superseded, the gold voided.
    result = answer_memo.revoke(db_session, memo.id, reason="too lenient")
    db_session.flush()

    assert result == {"state": "revoked", "taken_back": 1}
    db_session.refresh(entry)
    assert entry.state == "void"
    live = verdict_ledger.live_record(db_session, "forge_attempt", second.id)
    assert live.id != record.id and live.supersedes_id == record.id
    assert live.counts is False
    task = answer_memo.forge_task(
        round_name=second.round, mode=second.mode, prompt_payload=second.prompt_payload, concept_id=second.concept_id
    )
    assert judge.consult(task, SENTENCE, memos=answer_memo.Memos(db_session)) is None


def test_pilot_ops_lists_memos_and_revokes_one(client, db_session, monkeypatch):
    from tests.test_wp115a_vocabulary_memory import _login

    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    candidate = answer_memo.remember(
        db_session, task=judge.Task("forge", item="item-a"), answer="un", outcome=Outcome.RIGHT, payload={}
    )
    confirmed = answer_memo.remember(
        db_session, task=judge.Task("forge", item="item-b"), answer="deux", outcome=Outcome.RIGHT, payload={}
    )
    confirmed.state = "confirmed"
    db_session.commit()

    learner, test_user = _login(client, db_session)
    assert client.get("/api/v1/analytics/pilot-memos", headers=learner).status_code == 403

    test_user.role = "admin"
    db_session.commit()
    listed = client.get("/api/v1/analytics/pilot-memos", headers=learner).json()
    assert [row["id"] for row in listed["candidate"]] == [str(candidate.id)]
    assert [row["id"] for row in listed["confirmed"]] == [str(confirmed.id)]

    revoked = client.post(
        f"/api/v1/analytics/pilot-memos/{confirmed.id}/revoke", headers=learner, json={"reason": "too lenient"}
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["state"] == "revoked"
    assert client.get("/api/v1/analytics/pilot-memos", headers=learner).json()["confirmed"] == []


def test_a_confirmed_drill_memo_turns_a_miss_into_right(db_session, monkeypatch):
    from app.services.journey_learning import _memo_settles_recall

    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    drill = SimpleNamespace(
        task_type="translate", prompt_fr=None, source_fr=None, solution_fr="le colis",
        accepted_answers=["le colis"], target=SimpleNamespace(target_id=str(uuid.uuid4())),
    )
    task = answer_memo.recall_task(drill)
    assert _memo_settles_recall(db_session, drill, "le paquet") is False
    memo = answer_memo.remember(db_session, task=task, answer="le paquet", outcome=Outcome.RIGHT, payload={})
    memo.state = "confirmed"
    db_session.flush()
    assert _memo_settles_recall(db_session, drill, "Le paquet") is True


def test_pilot_ops_shows_the_memos_with_a_revoke_and_no_new_colour():
    from pathlib import Path

    web = Path(__file__).resolve().parents[1] / "web-frontend"
    page = (web / "pages" / "pilot-ops.tsx").read_text(encoding="utf-8")
    section = (web / "components" / "pilot" / "MemoSection.tsx").read_text(encoding="utf-8")
    assert "<MemoSection />" in page
    assert "/analytics/pilot-memos" in section and "/revoke" in section
    assert "#" not in "".join(line for line in section.splitlines() if "className" in line), "a hard-coded colour"
