# ruff: noqa: F811
"""Package O-1 — l'or in shadow: the ledger, written from every answer path.

The pure table is pinned in ``tests/test_gold_core.py``. These tests drive the
real writers (the journey over HTTP, La Forge with its relecture, the Courrier,
the critic's corrections, the nightly job) and read the ledger back. Every
writer runs inside a savepoint that swallows its failure; the autouse
``ledger_never_swallows`` fixture turns a swallowed failure back into a test
failure, so a broken writer cannot pass as «wrote nothing».
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.core import gold as core
from app.core.forge import Rung
from app.db.models.atelier import AtelierAttempt
from app.db.models.cefr import UserLevelCheckpoint
from app.db.models.daily_journey import DailyJourneyStep
from app.db.models.gold import GoldBalance, GoldLedgerEntry
from app.db.models.grammar import UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.streak_day import STREAK_DAY_PRACTISED, STREAK_DAY_RELACHE, StreakDay
from app.db.models.user import User
from app.services import gold_ledger, journey_capabilities
from app.services.atelier import AtelierCorrectionService
from app.services.forge import ForgeService, _store_state
from app.services.gold_report import build_gold_report, report_markdown
from app.services.journey_contracts import (
    AssistanceLevel,
    CapabilityKey,
    Correction,
    EvidenceKind,
    InputMode,
    RecallEvaluation,
    ResponseEvaluation,
    TargetKind,
    TargetObservation,
    TargetRef,
    TaskOutcome,
)
from app.tasks.gold import REPORT_EVENT, run_nightly
from tests.test_atelier import _concept, _FakeLLMService, _user
from tests.test_daily_journey_api import (  # noqa: F401  (fixtures)
    correct_recall_input,
    create_journey,
    journey_client,
    journey_enabled,
    key,
    login,
    walk_keys,
)
from tests.test_forge_level_402 import _day as _forge_day
from tests.test_forge_one_update_path import MODEL_SAYS_WRONG, USES_THE_FORM, _seated, _sentence

NOW = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)  # a Tuesday, 11:00 in Paris
MET_REPLY = "Je voudrais un café en terrasse, s'il vous plaît."
ACCEPTED = {"verdict": "accepted", "score_0_4": 4, "errata": []}
#: What a respond turn keeps; the models read these dicts, so a grade never joins them.
TURN_KEYS = {"learner", "character", "correction", "free", "lines", "route", "heard"}
#: The tests whose writers are meant to fail inside their savepoint.
FAILURE_EXPECTED = {
    "test_a_failing_ledger_never_costs_the_answer",
    "test_a_writer_gives_up_on_a_locked_learner_before_the_deadlock_detector",
    "test_a_journey_answer_waiting_on_a_writers_row_is_never_the_deadlock_victim",
}


@pytest.fixture(autouse=True)
def gold_in_shadow(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "shadow")


@pytest.fixture(autouse=True)
def ledger_never_swallows(request, caplog) -> Iterator[None]:
    caplog.set_level(logging.WARNING, logger=gold_ledger.__name__)
    yield
    if request.node.originalname in FAILURE_EXPECTED:
        return
    swallowed = [
        record.getMessage() for record in caplog.get_records("call") if record.name == gold_ledger.__name__
    ]
    assert not swallowed, f"a gold writer failed inside its savepoint: {swallowed}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entries(db: Session, user_id: Any, *, source_kind: str | None = None) -> list[GoldLedgerEntry]:
    db.flush()
    db.expire_all()
    query = db.query(GoldLedgerEntry).filter(GoldLedgerEntry.user_id == user_id)
    if source_kind is not None:
        query = query.filter(GoldLedgerEntry.source_kind == source_kind)
    return query.order_by(GoldLedgerEntry.created_at, GoldLedgerEntry.source_key).all()


def _settled(db: Session, user_id: Any) -> int:
    return sum(int(entry.amount) for entry in _entries(db, user_id) if entry.state == core.STATE_SETTLED)


def _balance(db: Session, user_id: Any) -> int:
    db.flush()
    db.expire_all()
    row = db.get(GoldBalance, user_id)
    return int(row.balance) if row is not None else 0


def _journey(*kinds: str) -> tuple[SimpleNamespace, list[SimpleNamespace]]:
    steps = [SimpleNamespace(id=uuid.uuid4(), ordinal=index, kind=kind) for index, kind in enumerate(kinds)]
    return SimpleNamespace(id=uuid.uuid4(), steps=steps, local_date=None), steps


def _word(target_id: Any) -> TargetRef:
    return TargetRef(kind=TargetKind.VOCABULARY, id=str(target_id), label_fr="mot")


def _rule(target_id: Any) -> TargetRef:
    return TargetRef(kind=TargetKind.GRAMMAR, id=str(target_id), label_fr="règle")


def _observations(targets: tuple[TargetRef, ...], evidence: EvidenceKind, assistance: AssistanceLevel):
    return [
        TargetObservation(target=target, evidence_kind=evidence, assistance=assistance, modality=InputMode.TEXT)
        for target in targets
    ]


def _recall(
    *targets: TargetRef,
    outcome: TaskOutcome = TaskOutcome.MET,
    evidence: EvidenceKind = EvidenceKind.PRODUCED_INDEPENDENT,
    assistance: AssistanceLevel = AssistanceLevel.NONE,
    slip_kind: str | None = None,
) -> RecallEvaluation:
    return RecallEvaluation(
        outcome=outcome,
        assistance=assistance,
        observations=_observations(targets, evidence, assistance),
        slip_kind=slip_kind,
    )


def _pay_recall(
    db: Session,
    user: User,
    journey: Any,
    step: Any,
    evaluation: RecallEvaluation,
    *,
    fmt: str = "short_answer",
    assistance: str = "none",
    retry: bool = False,
    contacts: dict[str, datetime | None] | None = None,
    now: datetime = NOW,
) -> None:
    gold_ledger.record_journey_recall(
        db,
        user=user,
        journey=journey,
        step=step,
        task=SimpleNamespace(evidence_format=None, task_type=fmt),
        evaluation=evaluation,
        assistance=assistance,
        retry=retry,
        contacts=contacts,
        now=now,
    )


def _reply(
    outcome: TaskOutcome = TaskOutcome.MET,
    *,
    targets: tuple[TargetRef, ...] = (),
    needs_repair: bool = False,
    turn_consumed: bool = True,
    correction: Correction | None = None,
    concept_evidence: list[dict[str, Any]] | None = None,
) -> ResponseEvaluation:
    return ResponseEvaluation(
        outcome=outcome,
        assistance=AssistanceLevel.NONE,
        observations=_observations(targets, EvidenceKind.PRODUCED_INDEPENDENT, AssistanceLevel.NONE),
        correction=correction,
        needs_repair=needs_repair,
        turn_consumed=turn_consumed,
        concept_evidence=list(concept_evidence or []),
    )


REPLY_TASK = SimpleNamespace(max_turns=3, repair_allowed=True)


def _pay_reply(
    db: Session,
    user: User,
    journey: Any,
    step: Any,
    evaluation: ResponseEvaluation,
    *,
    task: Any = REPLY_TASK,
    assistance: str = "none",
    turn_position: int = 0,
    turn_index: int | None = None,
    consumed_before: int | None = None,
    previous_outcome: str | None = None,
    now: datetime = NOW,
) -> None:
    gold_ledger.record_journey_reply(
        db,
        user=user,
        journey=journey,
        step=step,
        task=task,
        evaluation=evaluation,
        assistance=assistance,
        turn_position=turn_position,
        turn_index=turn_position if turn_index is None else turn_index,
        consumed_before=turn_position if consumed_before is None else consumed_before,
        previous_outcome=previous_outcome,
        now=now,
    )


def _forge_attempt(concept_id: int, *, round_name: str = "transform", created_at: datetime = NOW):
    return SimpleNamespace(
        id=uuid.uuid4(), concept_id=concept_id, round=round_name, atelier_session_id=None, created_at=created_at
    )


def _forge_verdict(outcome: str = "correct", *, checked: bool = True, local: str | None = None):
    return SimpleNamespace(checked=checked, outcome=outcome, correct=outcome == "correct", local=local)


# ---------------------------------------------------------------------------
# The journey, over HTTP
# ---------------------------------------------------------------------------


def _walk_the_day(client: TestClient, headers: dict[str, str], db: Session) -> tuple[dict[str, Any], list[Any]]:
    """Every step answered right and unaided, then «complete». Returns the final
    snapshot and every body the learner's client received on the way."""

    state = create_journey(client, headers)
    bodies: list[Any] = [state]
    journey_id = state["id"]
    for _ in range(40):
        current = state.get("current_step_id")
        if current is None:
            break
        step = next(item for item in state["steps"] if item["id"] == current)
        if step["kind"] in {"recall", "respond"} and step["status"] != "completed":
            answer = (
                correct_recall_input(db, current)
                if step["kind"] == "recall"
                else {"mode": "text", "text": MET_REPLY}
            )
            response = client.post(
                f"/api/v1/daily-journeys/{journey_id}/steps/{current}/attempts",
                headers=headers,
                json={"mutation_id": key(), "expected_revision": state["revision"], "input": answer},
            )
            assert response.status_code == 200, response.text
            bodies.append(response.json())
            state = response.json()["journey"]
            continue
        response = client.post(
            f"/api/v1/daily-journeys/{journey_id}/advance",
            headers=headers,
            json={"mutation_id": key(), "expected_revision": state["revision"], "current_step_id": current},
        )
        assert response.status_code == 200, response.text
        bodies.append(response.json())
        state = response.json()
    finished = client.post(
        f"/api/v1/daily-journeys/{journey_id}/finish",
        headers=headers,
        json={"mutation_id": key(), "expected_revision": state["revision"], "finish_kind": "complete"},
    )
    assert finished.status_code == 200, finished.text
    bodies.append(finished.json())
    return finished.json(), bodies


def _learner(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def test_an_unaided_day_writes_its_gold_and_no_response_shows_any(
    journey_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    email = f"gold-day-{uuid.uuid4().hex[:8]}@example.com"
    headers = login(journey_client, email)
    final, bodies = _walk_the_day(journey_client, headers, db_session)
    assert final["status"] == "completed"
    user = _learner(db_session, email)
    entries = _entries(db_session, user.id)

    recalls = [entry for entry in entries if entry.source_kind == gold_ledger.SOURCE_JOURNEY_TARGET]
    assert recalls, "every answered recall item is in the ledger"
    for entry in recalls:
        step = db_session.get(DailyJourneyStep, uuid.UUID(entry.evidence["step_id"]))
        task = dict(step.private_task or {})["recall_task"]
        fmt = task.get("evidence_format") or task.get("task_type")
        assert entry.state == core.STATE_SETTLED
        assert entry.breakdown["value"] == core.BASE_VALUE[core.category_for_format(fmt)], fmt
        assert entry.amount == entry.breakdown["value"] - entry.breakdown["best_before"]
        assert entry.evidence["warmup"] is False, "these items follow the scene: never a delayed recall"
    replies = [
        (entry.amount, entry.breakdown["category"])
        for entry in entries
        if entry.source_kind == gold_ledger.SOURCE_JOURNEY_REPLY and entry.entry_kind == gold_ledger.ENTRY_EARN
    ]
    assert replies == [(5, "free")], "one exchange, met and unaided: production libre"
    [perfect] = [entry for entry in entries if entry.entry_kind == gold_ledger.ENTRY_MILESTONE]
    assert perfect.amount == core.MILESTONE_VALUE[core.Milestone.PERFECT_DAY]
    assert perfect.source_key.startswith("gold:milestone:perfect_day:")
    assert _balance(db_session, user.id) == _settled(db_session, user.id) > 0

    # Shadow: none of it reaches the learner's client…
    for body in bodies:
        assert not [name for name in walk_keys(body) if "gold" in name.lower()]
    # …nor the conversation the models are sent: no grade joins the turns.
    respond = (
        db_session.query(DailyJourneyStep)
        .filter(DailyJourneyStep.journey_id == uuid.UUID(final["id"]), DailyJourneyStep.kind == "respond")
        .one()
    )
    for turn in respond.private_task["turns"]:
        assert set(turn) <= TURN_KEYS, sorted(set(turn) - TURN_KEYS)


def test_mode_off_writes_nothing(
    journey_client: TestClient, journey_enabled: None, db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "off")
    email = f"gold-off-{uuid.uuid4().hex[:8]}@example.com"
    headers = login(journey_client, email)
    final, _bodies = _walk_the_day(journey_client, headers, db_session)
    assert final["status"] == "completed"
    user = _learner(db_session, email)
    assert _entries(db_session, user.id) == []
    assert db_session.get(GoldBalance, user.id) is None


def test_a_failing_ledger_never_costs_the_answer(
    journey_client: TestClient, journey_enabled: None, db_session: Session, monkeypatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("ledger down")

    for name in ("_open_day", "_perfect_day", "_reconcile_milestones"):
        monkeypatch.setattr(gold_ledger, name, broken)
    email = f"gold-down-{uuid.uuid4().hex[:8]}@example.com"
    headers = login(journey_client, email)
    final, _bodies = _walk_the_day(journey_client, headers, db_session)
    assert final["status"] == "completed"
    assert final["recap"]["objective_outcome"] == "met"
    user = _learner(db_session, email)
    assert _entries(db_session, user.id) == []
    steps = db_session.query(DailyJourneyStep).filter(DailyJourneyStep.journey_id == uuid.UUID(final["id"])).all()
    assert {step.status for step in steps if step.kind in {"recall", "respond"}} == {"completed"}


# ---------------------------------------------------------------------------
# Recall items
# ---------------------------------------------------------------------------


def test_a_retry_pays_the_repair_on_the_learners_own_help(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, first, retry, again) = _journey("scene", "recall", "recall", "recall")
    word = _word(41)
    _pay_recall(db_session, user, journey, first, _recall(word, outcome=TaskOutcome.NOT_YET, evidence=EvidenceKind.NOT_YET))
    assert _entries(db_session, user.id) == []

    # The answer was shown after the miss: the record says «solution», the gold
    # reads the help the learner asked for (none).
    shown = _recall(word, evidence=EvidenceKind.PRODUCED_SUPPORTED, assistance=AssistanceLevel.SOLUTION)
    _pay_recall(db_session, user, journey, retry, shown, retry=True)
    [entry] = _entries(db_session, user.id)
    assert (entry.amount, entry.breakdown["category"], entry.evidence["retry"], entry.evidence["copy"]) == (
        1, "repair", True, False,
    )

    # A repair under a hint pays half of one feuille: nothing.
    hinted = _recall(_word(42), evidence=EvidenceKind.PRODUCED_SUPPORTED, assistance=AssistanceLevel.SOLUTION)
    _pay_recall(db_session, user, journey, again, hinted, retry=True, assistance="hint")
    assert len(_entries(db_session, user.id)) == 1


def test_a_delayed_recall_doubles_only_an_unaided_warmup_with_an_old_contact(db_session: Session) -> None:
    user = _user(db_session)
    journey, (old, recent, unknown, hinted, _scene, after) = _journey(
        "recall", "recall", "recall", "recall", "scene", "recall"
    )
    two_days = NOW - timedelta(days=2)
    contacts = {
        "vocabulary:51": two_days,
        "vocabulary:52": NOW - timedelta(hours=3),
        "vocabulary:54": two_days,
        "vocabulary:55": two_days,
    }
    _pay_recall(db_session, user, journey, old, _recall(_word(51)), contacts=contacts)
    _pay_recall(db_session, user, journey, recent, _recall(_word(52)), contacts=contacts)
    _pay_recall(db_session, user, journey, unknown, _recall(_word(53)), contacts=contacts)
    _pay_recall(db_session, user, journey, hinted, _recall(_word(54)), contacts=contacts, assistance="hint")
    _pay_recall(db_session, user, journey, after, _recall(_word(55)), contacts=contacts)
    paid = {entry.target["id"]: entry for entry in _entries(db_session, user.id)}
    assert {target: entry.amount for target, entry in paid.items()} == {
        "51": 4,  # a warm-up two days after the last contact: rappel différé
        "52": 2,  # three hours: not delayed
        "53": 2,  # no known contact: a first meeting, never a delayed recall
        "54": 1,  # aided: half, and never doubled
        "55": 2,  # after the scene: the word was just read there
    }
    assert paid["51"].evidence["delayed_recall"] is True and paid["51"].evidence["warmup"] is True
    assert paid["51"].evidence["previous_contact_at"] == two_days.isoformat()
    assert "rappel différé ×2" in paid["51"].breakdown["reason_fr"]
    assert paid["55"].evidence["warmup"] is False


def test_contacts_are_read_from_the_learners_records(db_session: Session) -> None:
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    seen = NOW - timedelta(days=3)
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, last_review=seen))
    db_session.flush()

    contacts = gold_ledger.snapshot_contacts(db_session, user=user, evaluation=_recall(_rule(concept.id), _word(999999)))
    assert contacts == {f"grammar:{concept.id}": seen, "vocabulary:999999": None}
    missed = _recall(_rule(concept.id), outcome=TaskOutcome.NOT_YET, evidence=EvidenceKind.NOT_YET)
    assert gold_ledger.snapshot_contacts(db_session, user=user, evaluation=missed) == {}


def test_a_copied_sentence_pays_nothing_and_an_accent_slip_pays_half(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, copied, slipped) = _journey("scene", "recall", "recall")
    _pay_recall(
        db_session, user, journey, copied, _recall(_word(61), evidence=EvidenceKind.PRODUCED_SUPPORTED), fmt="sentence"
    )
    assert _entries(db_session, user.id) == [], "a displayed sentence typed back is not production (WP-130 B)"

    _pay_recall(db_session, user, journey, slipped, _recall(_word(62), slip_kind="accent"))
    [entry] = _entries(db_session, user.id)
    assert entry.amount == 1 and entry.evidence["accent_slip"] is True
    assert {"rule": "R3", "name": "accent", "factor": "1/2"} in entry.breakdown["factors"]


def test_an_item_without_targets_pays_as_itself_once(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, who_said) = _journey("scene", "recall")
    for _ in range(2):  # a replayed request finds its entry
        _pay_recall(db_session, user, journey, who_said, _recall(), fmt="who_said")
    [entry] = _entries(db_session, user.id)
    assert (entry.amount, entry.target, entry.source_key) == (1, None, f"gold:journey:{journey.id}:{who_said.id}:unit")
    assert _balance(db_session, user.id) == 1


def test_the_best_of_the_day_counts_across_the_journey_and_la_forge(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, picked, picked_again) = _journey("scene", "recall", "recall")
    rule = _rule(4242)
    recognised = _recall(rule, evidence=EvidenceKind.RECOGNIZED)
    _pay_recall(db_session, user, journey, picked, recognised, fmt="choice")
    gold_ledger.record_forge_item(
        db_session, user=user, attempt=_forge_attempt(4242), rung=int(Rung.TRANSFORM), verdict=_forge_verdict(),
        mode="seance", reprise=False, below_level=False, level_before=3, contact_before=None,
        now=NOW + timedelta(minutes=1),
    )
    _pay_recall(db_session, user, journey, picked_again, recognised, fmt="choice", now=NOW + timedelta(minutes=2))
    paid = [(entry.source_kind, entry.amount, entry.breakdown["best_before"]) for entry in _entries(db_session, user.id)]
    assert paid == [("journey_target", 1, 0), ("forge_item", 1, 1)], (
        "the transform tops the morning's recognition up by one; the second recognition adds nothing"
    )


def test_the_plafond_pays_at_most_120_a_day(db_session: Session) -> None:
    user = _user(db_session)
    journey, steps = _journey("scene", *(["respond"] * 32))
    for minute, step in enumerate(steps[1:]):
        _pay_reply(db_session, user, journey, step, _reply(), now=NOW + timedelta(minutes=minute))
    entries = _entries(db_session, user.id)
    assert len(entries) == 32, "a reply past the plafond is still written: the day's earned gold stays true"
    assert all(entry.breakdown["earned"] == 5 for entry in entries)
    assert [entry.amount for entry in entries[:18]] == [5] * 18
    assert [entry.amount for entry in entries[-2:]] == [0, 0]
    assert "plafond du jour" in entries[20].breakdown["reason_fr"]
    assert sum(entry.amount for entry in entries) == core.DAY_CAP == 120
    assert _balance(db_session, user.id) == 120


def test_a_new_timezone_moves_the_gold_day_only_after_a_week(db_session: Session) -> None:
    user = _user(db_session)
    user.timezone = "Europe/Paris"
    db_session.flush()
    journey, (_scene, *items) = _journey("scene", "recall", "recall", "recall")
    late = datetime(2026, 11, 2, 22, 30, tzinfo=UTC)  # 23:30 in Paris
    _pay_recall(db_session, user, journey, items[0], _recall(_word(71)), now=late)
    user.timezone = "America/New_York"
    db_session.flush()
    _pay_recall(db_session, user, journey, items[1], _recall(_word(72)), now=late + timedelta(hours=1))
    _pay_recall(db_session, user, journey, items[2], _recall(_word(73)), now=late + timedelta(days=8, hours=1))
    days = [(entry.local_date.isoformat(), entry.evidence["tz"]) for entry in _entries(db_session, user.id)]
    assert days == [
        ("2026-11-02", "Europe/Paris"),
        # 00:30 in Paris, 18:30 the day before in New York: a zone claimed an hour
        # ago does not reopen a day whose plafond is spent.
        ("2026-11-03", "Europe/Paris"),
        ("2026-11-10", "America/New_York"),  # claimed for a week: it is the learner's day now
    ]


# ---------------------------------------------------------------------------
# Reply turns and «Joli !»
# ---------------------------------------------------------------------------


def test_a_free_turn_pays_nothing_and_a_repair_after_a_miss_pays_one(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, respond) = _journey("scene", "respond")
    task = SimpleNamespace(max_turns=1, repair_allowed=True)
    # The greeting nudge cost no exchange.
    _pay_reply(db_session, user, journey, respond, _reply(needs_repair=True, turn_consumed=False), task=task)
    # The planned exchange, missed.
    _pay_reply(
        db_session, user, journey, respond, _reply(TaskOutcome.NOT_YET, needs_repair=True), task=task,
        turn_position=1, turn_index=0, consumed_before=0,
    )
    assert _entries(db_session, user.id) == []
    # The repair slot, answered: a slip turned right.
    _pay_reply(
        db_session, user, journey, respond, _reply(), task=task,
        turn_position=2, turn_index=1, consumed_before=1, previous_outcome="not_yet",
    )
    [entry] = _entries(db_session, user.id)
    assert (entry.amount, entry.breakdown["category"], entry.evidence["repair"]) == (1, "repair", True)


def test_reply_turns_pay_per_exchange_up_to_what_the_scene_takes(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, respond) = _journey("scene", "respond")
    task = SimpleNamespace(max_turns=1, repair_allowed=True)  # 1 + the repair + 2 for a question = 4
    turns = [
        (TaskOutcome.PARTIALLY_MET, None),  # half of a reply
        (TaskOutcome.MET, "partially_met"),  # the repair slot after it
        (TaskOutcome.MET, "met"),  # the character asked something: the answer is a reply
        (TaskOutcome.MET, "met"),
        (TaskOutcome.MET, "met"),  # past what the scene can take
    ]
    for position, (outcome, previous) in enumerate(turns):
        _pay_reply(
            db_session, user, journey, respond, _reply(outcome), task=task,
            turn_position=position, previous_outcome=previous, now=NOW + timedelta(minutes=position),
        )
    paid = [(entry.amount, entry.breakdown["category"]) for entry in _entries(db_session, user.id)]
    assert paid == [(2, "free"), (1, "repair"), (5, "free"), (5, "free")]


def test_joli_pays_two_once_a_day(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, corrected, first, second) = _journey("scene", "respond", "respond", "respond")
    used = [{"concept_id": 7, "outcome": "correct", "span": "ne … pas"}]
    erratum = Correction(span_fr="je mange pas", corrected_fr="je ne mange pas", note_native="ne … pas")
    _pay_reply(db_session, user, journey, corrected, _reply(concept_evidence=used, correction=erratum))
    _pay_reply(db_session, user, journey, first, _reply(concept_evidence=used), now=NOW + timedelta(minutes=1))
    _pay_reply(db_session, user, journey, second, _reply(concept_evidence=used), now=NOW + timedelta(minutes=2))
    entries = _entries(db_session, user.id)
    assert [entry.amount for entry in entries if entry.entry_kind == gold_ledger.ENTRY_EARN] == [5, 5, 5]
    [joli] = [entry for entry in entries if entry.entry_kind == gold_ledger.ENTRY_BONUS]
    assert (joli.amount, joli.state, joli.source_key) == (2, "settled", "gold:bonus:joli:2026-11-03")
    assert joli.evidence["step_id"] == str(first.id)
    assert _balance(db_session, user.id) == 17


def test_a_reply_lifts_the_targets_it_shows(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, respond, recall) = _journey("scene", "respond", "recall")
    word = _word(81)
    _pay_reply(db_session, user, journey, respond, _reply(targets=(word,)))
    _pay_recall(db_session, user, journey, recall, _recall(word), now=NOW + timedelta(minutes=1))
    [entry] = _entries(db_session, user.id)
    assert (entry.source_kind, entry.evidence["lifts"]) == ("journey_reply", ["vocabulary:81"])


# ---------------------------------------------------------------------------
# La Forge and its relecture
# ---------------------------------------------------------------------------


def _forge_entries(db: Session, user: User) -> list[GoldLedgerEntry]:
    return _entries(db, user.id, source_kind=gold_ledger.SOURCE_FORGE_ITEM)


def test_a_provisional_forge_sentence_is_pending_until_its_relecture_settles_it(
    db_session: Session, monkeypatch
) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService(ACCEPTED))
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.amount, entry.breakdown["category"]) == ("pending", 3, "guided")
    assert _balance(db_session, user.id) == 0, "pending gold is no part of the livret"

    service.run_ai_review_for_attempt(attempt.id)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.amount, entry.evidence["settled_by"]) == ("settled", 3, "relecture")
    assert _balance(db_session, user.id) == 3


def test_a_relecture_that_reads_a_miss_pulps_the_pending_gold(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService(MODEL_SAYS_WRONG))
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    service.run_ai_review_for_attempt(attempt.id)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.void_reason) == ("void", "not_yet")
    assert _balance(db_session, user.id) == 0


def test_an_unread_answer_is_pulped_and_a_review_that_reads_it_revives_it(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)

    class _Down:
        def generate_error_detection(self, messages, **kwargs):
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("down")

    service = AtelierCorrectionService(db_session, llm_service=_Down())
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    service.run_ai_review_for_attempt(attempt.id)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.void_reason) == ("void", "unread")

    retry = AtelierCorrectionService(db_session, llm_service=_FakeLLMService(ACCEPTED))
    db_session.refresh(attempt)
    retry.mark_ai_review_pending(attempt)
    retry.run_ai_review_for_attempt(attempt.id)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.amount, entry.void_reason, entry.voided_at) == ("settled", 3, None, None)
    assert _balance(db_session, user.id) == 3


def _pulped_unread(db: Session, user: User, concept_id: int) -> SimpleNamespace:
    """A provisional guided sentence (pending 3) whose relecture nobody could read."""

    attempt = _forge_attempt(concept_id, round_name="sentence")
    gold_ledger.record_forge_item(
        db, user=user, attempt=attempt, rung=int(Rung.PRODUCE), verdict=_forge_verdict(checked=False, local="correct"),
        mode="seance", reprise=False, below_level=False, level_before=4, contact_before=None, now=NOW,
    )
    gold_ledger.settle_forge_item(
        db, user=user, attempt=attempt, history_entry={"rung": int(Rung.PRODUCE)},
        verdict=_forge_verdict(), unread=True, now=NOW + timedelta(minutes=1),
    )
    return attempt


def _read_at_last(db: Session, user: User, attempt: SimpleNamespace, *, outcome: str = "correct") -> GoldLedgerEntry:
    gold_ledger.settle_forge_item(
        db, user=user, attempt=attempt, history_entry={"rung": int(Rung.PRODUCE)},
        verdict=_forge_verdict(outcome), unread=False, now=NOW + timedelta(hours=1),
    )
    [entry] = [row for row in _forge_entries(db, user) if row.source_key == f"gold:forge:{attempt.id}"]
    return entry


@pytest.mark.parametrize(
    ("meanwhile", "revived"),
    [(Rung.PRODUCE, ("void", 3, "already_paid")), (Rung.TRANSFORM, ("settled", 1, None))],
    ids=["meanwhile-the-same-form", "meanwhile-a-weaker-form"],
)
def test_a_revived_answer_is_priced_against_the_day_as_it_stands(
    db_session: Session, meanwhile: Rung, revived: tuple[str, int, str | None]
) -> None:
    user = _user(db_session)
    pulped = _pulped_unread(db_session, user, 4444)
    gold_ledger.record_forge_item(  # the same rule again, while the first answer lies pulped
        db_session, user=user, attempt=_forge_attempt(4444), rung=int(meanwhile), verdict=_forge_verdict(),
        mode="seance", reprise=False, below_level=False, level_before=4, contact_before=None,
        now=NOW + timedelta(minutes=2),
    )
    entry = _read_at_last(db_session, user, pulped)
    assert (entry.state, entry.amount, entry.void_reason) == revived
    assert (entry.evidence["outcome"], entry.evidence["checked"]) == ("correct", True)
    assert _settled(db_session, user.id) == 3 == _balance(db_session, user.id), (
        "R1: the rule's best of the day (guided, 3) is paid once, whichever answer pays it"
    )


def test_a_revival_after_the_plafond_pays_what_the_plafond_leaves(db_session: Session) -> None:
    user = _user(db_session)
    pulped = _pulped_unread(db_session, user, 4545)
    journey, steps = _journey("scene", *(["respond"] * 30))
    for minute, step in enumerate(steps[1:]):  # 150 earned: the plafond is spent
        _pay_reply(db_session, user, journey, step, _reply(), now=NOW + timedelta(minutes=2 + minute))
    entry = _read_at_last(db_session, user, pulped)
    assert (entry.state, entry.amount, entry.breakdown["earned"]) == ("settled", 0, 3)
    assert entry.breakdown["day_earned_before"] == 150
    assert _settled(db_session, user.id) == core.DAY_CAP == _balance(db_session, user.id)


def test_a_partial_verdict_the_day_already_paid_pulps_the_pending_gold(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, recall) = _journey("scene", "recall")
    _pay_recall(db_session, user, journey, recall, _recall(_rule(4646), evidence=EvidenceKind.RECOGNIZED), fmt="choice")
    attempt = _forge_attempt(4646, round_name="sentence")
    gold_ledger.record_forge_item(
        db_session, user=user, attempt=attempt, rung=int(Rung.PRODUCE),
        verdict=_forge_verdict(checked=False, local="correct"), mode="seance", reprise=False, below_level=False,
        level_before=4, contact_before=None, now=NOW + timedelta(minutes=1),
    )
    entry = _read_at_last(db_session, user, attempt, outcome="partial")
    assert (entry.state, entry.void_reason, entry.evidence["outcome"]) == ("void", "already_paid", "partial"), (
        "half a guided sentence is worth 1, no more than the morning's recognition already paid the rule"
    )
    assert _settled(db_session, user.id) == 1 == _balance(db_session, user.id)


@pytest.mark.parametrize(("seen_days_ago", "amount", "rules"), [(None, 1, ["R5"]), (2, 2, ["R4", "R5"])])
def test_a_forge_warmup_posed_below_the_level_pays_half(
    db_session: Session, seen_days_ago: int | None, amount: int, rules: list[str]
) -> None:
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    seen = None if seen_days_ago is None else datetime.now(UTC) - timedelta(days=seen_days_ago)
    db_session.add(
        UserGrammarProgress(
            user_id=user.id, concept_id=concept.id, forge_rung=int(Rung.PRODUCE), reps=3, stability=10,
            last_review=seen,
        )
    )
    db_session.flush()
    session, state = _forge_day(db_session, user, concept.id)
    slot = state.next_slot()
    assert slot.rung == Rung.TRANSFORM, "a due rule's first item is posed one step easier"
    state.pending = {"concept_id": concept.id, "rung": slot.rung, "round": "transform"}
    _store_state(session, state)
    attempt = AtelierAttempt(
        atelier_session_id=session.id, user_id=user.id, concept_id=concept.id,
        round="transform", mode="rewrite", exercise_id=f"forge:{concept.id}:transform:w",
        prompt_payload={"items": [{"id": "w"}]}, answer_payload={"answers": {"w": "Je ne mange pas."}},
        correction_payload={"assessment_status": "checked", "checked": True},
        verdict="correct", score_0_4=4.0,
    )
    db_session.add(attempt)
    db_session.flush()
    ForgeService(db_session).observe_attempt(user=user, session=session, attempt=attempt)
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.amount, entry.evidence["below_level"]) == ("settled", amount, True)
    assert [factor["rule"] for factor in entry.breakdown["factors"]] == rules


def test_a_late_verdict_on_an_answer_with_no_entry_mints_it_on_the_answers_day(db_session: Session) -> None:
    user = _user(db_session)
    yesterday = NOW - timedelta(days=1)
    attempt = _forge_attempt(4343, round_name="sentence", created_at=yesterday)
    gold_ledger.settle_forge_item(
        db_session, user=user, attempt=attempt, history_entry={"rung": int(Rung.PRODUCE)},
        verdict=_forge_verdict(), unread=False, now=NOW,
    )
    gold_ledger.settle_forge_item(  # a replayed relecture
        db_session, user=user, attempt=attempt, history_entry={"rung": int(Rung.PRODUCE)},
        verdict=_forge_verdict(), unread=False, now=NOW,
    )
    [entry] = _forge_entries(db_session, user)
    assert (entry.state, entry.amount, entry.local_date.isoformat()) == ("settled", 3, "2026-11-02")


# ---------------------------------------------------------------------------
# Courrier letters
# ---------------------------------------------------------------------------


def _letter_attempt(verdict: str, at: datetime, *, mode: str = "writing") -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), verdict=verdict, created_at=at, mode=mode, answer_payload={})


def test_a_letter_pays_on_its_first_written_attempt(db_session: Session) -> None:
    user = _user(db_session)
    accepted, partial, revised, from_the_day = (SimpleNamespace(id=uuid.uuid4()) for _ in range(4))
    for _ in range(2):  # a replay writes nothing twice
        gold_ledger.record_letter(db_session, user=user, mission=accepted, attempts=[_letter_attempt("accepted", NOW)], now=NOW)
    gold_ledger.record_letter(db_session, user=user, mission=partial, attempts=[_letter_attempt("partial", NOW)], now=NOW)
    gold_ledger.record_letter(
        db_session, user=user, mission=revised, now=NOW,
        attempts=[_letter_attempt("accepted", NOW + timedelta(minutes=5)), _letter_attempt("needs_revision", NOW)],
    )
    gold_ledger.record_letter(
        db_session, user=user, mission=from_the_day, now=NOW, attempts=[_letter_attempt("accepted", NOW, mode="journey")]
    )
    paid = {entry.evidence["mission_id"]: entry.amount for entry in _entries(db_session, user.id)}
    assert paid == {str(accepted.id): 8, str(partial.id): 4}, (
        "accepted pays a letter, partial half; a rewrite after «needs revision» and a letter "
        "answered from the day (paid as its reply turns) pay nothing here"
    )


def test_completing_a_letter_writes_its_gold(db_session: Session, monkeypatch) -> None:
    from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
    from app.services import missions as missions_module
    from app.services.missions import MissionScheduler

    monkeypatch.setattr(missions_module, "_safe_llm", lambda: None)
    user = _user(db_session)
    mission = RealWorldMission(
        user_id=user.id, status="in_progress", cadence="ad_hoc", mission_type="message", title="Lettre",
        brief="Réponds à la lettre.", selected_concept_ids=[], target_errata_ids=[], target_vocabulary_ids=[],
        source_snapshot={}, objectives=[], prompt_payload={}, recap_payload={},
    )
    db_session.add(mission)
    db_session.flush()
    db_session.add(
        RealWorldMissionAttempt(
            mission_id=mission.id, user_id=user.id, mode="writing",
            answer_payload={"text": "Chère Inès, merci pour ta lettre."}, correction_payload={},
            verdict="accepted", score_0_4=4.0,
        )
    )
    db_session.commit()
    db_session.refresh(mission)
    MissionScheduler(db_session).complete(user=user, mission=mission)
    [entry] = _entries(db_session, user.id)
    assert (entry.source_kind, entry.amount, entry.state) == ("letter", 8, "settled")


@pytest.mark.skipif(not os.environ.get("GOLD_PG_URL"), reason="set GOLD_PG_URL to a migrated throwaway PostgreSQL database")
def test_a_writer_gives_up_on_a_locked_learner_before_the_deadlock_detector() -> None:  # pragma: no cover - opt-in
    """Outside the journey a writer reaches the learner lock with its answer's rows
    already written. Finding the learner locked, it waits less than PostgreSQL's
    ``deadlock_timeout`` and gives up: no entry, a usable session, and the caller's own
    ``lock_timeout`` untouched. Once the lock is free it writes as usual.

    ``GOLD_PG_URL=postgresql+psycopg2://… pytest tests/test_gold_ledger.py -k deadlock``
    against a database at ``alembic upgrade head``.
    """

    from sqlalchemy import create_engine, text

    from app.db.savepoint import session_is_usable

    engine = create_engine(os.environ["GOLD_PG_URL"])
    user_id = uuid.uuid4()
    with Session(engine) as setup:
        setup.add(User(id=user_id, email=f"gold-pg-{user_id.hex[:8]}@example.com", hashed_password="x", target_language="fr"))
        setup.commit()
    holder = engine.connect()
    try:
        held = holder.begin()
        holder.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": str(user_id)})
        with Session(engine) as db:
            user = db.get(User, user_id)
            started = time.monotonic()
            gold_ledger.record_letter(
                db, user=user, mission=SimpleNamespace(id=uuid.uuid4()),
                attempts=[_letter_attempt("accepted", NOW)], now=NOW,
            )
            waited = time.monotonic() - started
            assert waited < 0.9, f"waited {waited:.2f}s for the learner: the deadlock detector runs at 1 s"
            assert session_is_usable(db)
            assert db.execute(text("SELECT current_setting('lock_timeout')")).scalar() == "0"
            assert db.query(GoldLedgerEntry).filter(GoldLedgerEntry.user_id == user_id).count() == 0
            held.rollback()

            gold_ledger.record_letter(
                db, user=user, mission=SimpleNamespace(id=uuid.uuid4()),
                attempts=[_letter_attempt("accepted", NOW)], now=NOW,
            )
            assert db.query(GoldLedgerEntry).filter(GoldLedgerEntry.user_id == user_id).count() == 1
            assert db.execute(text("SELECT current_setting('lock_timeout')")).scalar() == "0"
            db.rollback()
    finally:
        holder.close()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
        engine.dispose()


@pytest.mark.skipif(not os.environ.get("GOLD_PG_URL"), reason="set GOLD_PG_URL to a migrated throwaway PostgreSQL database")
def test_a_journey_answer_waiting_on_a_writers_row_is_never_the_deadlock_victim() -> None:  # pragma: no cover
    """The cycle itself: a journey answer holds the learner and waits for a row that a
    Forge relecture has just written; the relecture's gold writer then asks for the
    learner. The writer gives up, the journey answer commits."""

    import threading

    from sqlalchemy import create_engine, text

    engine = create_engine(os.environ["GOLD_PG_URL"])
    user_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS gold_pg_rows (id INTEGER PRIMARY KEY, v INTEGER)"))
        conn.execute(text("INSERT INTO gold_pg_rows VALUES (1, 0) ON CONFLICT (id) DO UPDATE SET v = 0"))
    with Session(engine) as setup:
        setup.add(User(id=user_id, email=f"gold-pg-{user_id.hex[:8]}@example.com", hashed_password="x", target_language="fr"))
        setup.commit()
    journey = engine.connect()
    outcome: dict[str, str] = {}
    try:
        pid = journey.execute(text("SELECT pg_backend_pid()")).scalar()
        journey.commit()
        with Session(engine) as writer:
            writer.execute(text("UPDATE gold_pg_rows SET v = 1 WHERE id = 1"))  # the relecture's own row
            writer.flush()
            began = journey.begin()
            journey.execute(text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": str(user_id)})

            def journey_answer() -> None:
                try:
                    journey.execute(text("UPDATE gold_pg_rows SET v = 2 WHERE id = 1"))
                    began.commit()
                    outcome["journey"] = "committed"
                except Exception as exc:  # the deadlock this test is about
                    outcome["journey"] = type(getattr(exc, "orig", exc)).__name__
                    began.rollback()

            waiting = threading.Thread(target=journey_answer)
            waiting.start()
            with engine.connect() as probe:
                for _ in range(100):
                    event = probe.execute(
                        text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
                    ).scalar()
                    probe.commit()
                    if event == "Lock":
                        break
                    time.sleep(0.01)
            gold_ledger.record_letter(
                writer, user=writer.get(User, user_id), mission=SimpleNamespace(id=uuid.uuid4()),
                attempts=[_letter_attempt("accepted", NOW)], now=NOW,
            )
            writer.commit()
            waiting.join(timeout=10)
        assert outcome == {"journey": "committed"}
    finally:
        journey.close()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
            conn.execute(text("DROP TABLE IF EXISTS gold_pg_rows"))
        engine.dispose()


# ---------------------------------------------------------------------------
# The critic's corrections
# ---------------------------------------------------------------------------


def test_a_withdrawn_success_keeps_settled_gold_and_an_injection_pulps_it(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, recall, respond) = _journey("scene", "recall", "respond")
    _pay_recall(db_session, user, journey, recall, _recall(_word(31), _word(32)))
    _pay_reply(db_session, user, journey, respond, _reply(), now=NOW + timedelta(minutes=1))
    # A pending entry under the step (none of today's writers leaves one, but the rule holds).
    db_session.add(
        GoldLedgerEntry(
            user_id=user.id, amount=2, entry_kind="earn", state="pending", source_kind="journey_target",
            source_key=f"gold:journey:{journey.id}:{recall.id}:grammar:77", target={"kind": "grammar", "id": "77"},
            evidence={"outcome": "met"}, breakdown={"earned": 2, "value": 2}, rule_version=core.RULE_VERSION,
            local_date=NOW.date(), week_id=core.week_id(NOW), created_at=NOW,
        )
    )
    db_session.flush()
    assert _balance(db_session, user.id) == 9

    gold_ledger.note_released_grading_corrected(
        db_session, user=user, journey_id=journey.id, step_id=recall.id, outcome=TaskOutcome.MET,
        withdrawn_target_ids=["31", "77"], reason="incompatible_demonstrated_targets", now=NOW,
    )
    entries = {entry.source_key: entry for entry in _entries(db_session, user.id)}
    prefix = f"gold:journey:{journey.id}:{recall.id}"
    withdrawn, kept, pending = entries[f"{prefix}:vocabulary:31"], entries[f"{prefix}:vocabulary:32"], entries[f"{prefix}:grammar:77"]
    assert withdrawn.state == "settled" and withdrawn.evidence["withdrawn"]["reason"] == "incompatible_demonstrated_targets"
    assert "withdrawn" not in kept.evidence and "critic" not in kept.evidence
    assert (pending.state, pending.void_reason) == ("void", "withdrawn")
    assert _balance(db_session, user.id) == 9, "settled gold stays settled when the grader erred"

    reply_key = gold_ledger.reply_source_key(journey.id, respond.id, 0)
    gold_ledger.note_released_grading_corrected(
        db_session, user=user, journey_id=journey.id, step_id=respond.id, outcome=TaskOutcome.PARTIALLY_MET,
        withdrawn_target_ids=[], reason="false_successful_grading", now=NOW,
    )
    reply = {entry.source_key: entry for entry in _entries(db_session, user.id)}[reply_key]
    assert reply.state == "settled" and reply.evidence["critic"]["outcome"] == "partially_met"

    gold_ledger.note_released_grading_corrected(
        db_session, user=user, journey_id=journey.id, step_id=respond.id, outcome=TaskOutcome.NOT_YET,
        withdrawn_target_ids=[], reason="false_successful_grading,prompt_injection", now=NOW,
    )
    reply = {entry.source_key: entry for entry in _entries(db_session, user.id)}[reply_key]
    assert (reply.state, reply.void_reason) == ("void", "injection")
    assert _balance(db_session, user.id) == 4


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def test_milestones_are_paid_once_from_the_records_that_decide_them(db_session: Session, monkeypatch) -> None:
    user = _user(db_session)
    journey, (_scene, recall) = _journey("scene", "recall")
    _pay_recall(db_session, user, journey, recall, _recall(_word(91)), now=NOW)  # the learner's first entry
    held, tested_out, before = (
        _concept(db_session, external_id) for external_id in ("FR_A2_NEG_001", "FR_B1_COND_001", "FR_B1_TENSE_001")
    )
    soon = NOW + timedelta(hours=1)
    db_session.add_all(
        [
            UserGrammarProgress(user_id=user.id, concept_id=held.id, held_at=soon),
            UserGrammarProgress(user_id=user.id, concept_id=tested_out.id, held_at=soon, tested_out_at=soon),
            UserGrammarProgress(user_id=user.id, concept_id=before.id, held_at=NOW - timedelta(days=3)),
            UserLevelCheckpoint(user_id=user.id, band="A2", status="passed", passed_at=NOW + timedelta(hours=2)),
            UserLevelCheckpoint(user_id=user.id, band="A1", status="passed", passed_at=NOW - timedelta(days=30)),
        ]
    )
    db_session.flush()
    monkeypatch.setattr(
        journey_capabilities,
        "capability_confirmed_at",
        lambda db, *, user: {
            CapabilityKey.ORDER_AT_CAFE: NOW + timedelta(hours=3),
            CapabilityKey.ARRANGE_MEETING: NOW - timedelta(days=9),
        },
    )

    gold_ledger.record_rule_held(db_session, user=user, now=soon)
    milestones = [entry for entry in _entries(db_session, user.id) if entry.entry_kind == gold_ledger.ENTRY_MILESTONE]
    assert [entry.source_key for entry in milestones] == [f"gold:milestone:rule_held:{held.id}"], (
        "a rule held through practice pays at once; a test-out and a rule held before the ledger began do not"
    )

    for _ in range(2):
        gold_ledger.reconcile_milestones(db_session, user=user, now=NOW + timedelta(hours=4))
    milestones = sorted(
        (entry.breakdown["milestone"], entry.amount)
        for entry in _entries(db_session, user.id)
        if entry.entry_kind == gold_ledger.ENTRY_MILESTONE
    )
    assert milestones == [("capability_confirmed", 10), ("epreuve_passed", 30), ("rule_held", 25)]
    assert _balance(db_session, user.id) == 2 + 10 + 30 + 25


# ---------------------------------------------------------------------------
# The nightly job, the report and the owner's endpoint
# ---------------------------------------------------------------------------


def test_the_nightly_job_reconciles_recomputes_and_keeps_the_report(db_session: Session) -> None:
    user = _user(db_session)
    journey, (_scene, recall, respond) = _journey("scene", "recall", "respond")
    _pay_recall(db_session, user, journey, recall, _recall(_word(95)), now=NOW)
    _pay_reply(db_session, user, journey, respond, _reply(), now=NOW + timedelta(minutes=1))
    concept = _concept(db_session, "FR_A2_NEG_001")
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, held_at=NOW + timedelta(hours=2)))
    db_session.get(GoldBalance, user.id).balance = 999  # a drifted cache
    db_session.commit()

    night = NOW + timedelta(hours=18)
    summary = run_nightly(db_session, now=night)
    assert (summary["reconciled"], summary["failed"]) == (1, 0)
    assert _balance(db_session, user.id) == 2 + 5 + 25
    run_nightly(db_session, now=night)
    milestones = [entry for entry in _entries(db_session, user.id) if entry.entry_kind == gold_ledger.ENTRY_MILESTONE]
    assert len(milestones) == 1
    reports = db_session.query(PilotEvent).filter(PilotEvent.event_type == REPORT_EVENT).all()
    assert len(reports) == 2
    assert reports[0].user_id is None
    assert reports[0].payload["report"] == "gold_shadow" and reports[0].payload["learners"] >= 1


def test_the_nightly_job_skips_when_the_mode_is_off(db_session: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_GOLD_MODE", "off")
    assert run_nightly(db_session, now=NOW) == {"skipped": "ATELIER_GOLD_MODE=off"}
    assert db_session.query(PilotEvent).filter(PilotEvent.event_type == REPORT_EVENT).count() == 0


def test_the_report_reads_production_the_plafond_and_the_rhythm_median(db_session: Session) -> None:
    user = _user(db_session)
    user.daily_goal_minutes = 10  # Régulier
    db_session.flush()
    journey, steps = _journey("scene", *(["respond"] * 20), "recall", "recall")
    for minute, step in enumerate(steps[1:21]):  # day 1: 100 earned, 95 paid
        _pay_reply(db_session, user, journey, step, _reply(), now=NOW + timedelta(minutes=minute))
    day_two = NOW + timedelta(days=1)
    for index, step in enumerate(steps[21:]):  # day 2: two recognitions
        _pay_recall(
            db_session, user, journey, step, _recall(_word(100 + index), evidence=EvidenceKind.RECOGNIZED),
            fmt="choice", now=day_two + timedelta(minutes=index),
        )
    report = build_gold_report(db_session, days=14, now=day_two + timedelta(hours=1))

    regulier = report["gold_by_rhythm"]["regulier"]
    assert (regulier["learners"], regulier["days"], regulier["median"]) == (1, 2, 48.5)
    assert regulier["journee_pleine_share"] == 0.5
    assert report["production_share"] == round(95 / 97, 3)
    assert report["plafond"] == {"touched_day_share": 0.5, "capped_day_share": 0.0, "touched_days": 1, "capped_days": 0}
    assert report["recognition_only_day_share"] == 0.5
    assert report["journees_pleines"] == {"learner_weeks": 1, "mean_per_week": 1, "weeks_with_five": 0}
    checks = {check["metric"]: check["ok"] for check in report["checks"]}
    assert checks == {"production_share": True, "plafond_day_share": False, "stale_pending": True}
    page = report_markdown(report)
    assert "| regulier | 1 | 2 | 48.5 |" in page


def test_a_finished_day_that_earned_nothing_counts_at_zero(db_session: Session) -> None:
    user = _user(db_session)
    user.daily_goal_minutes = 10  # Régulier
    journey, (_scene, recall) = _journey("scene", "recall")
    _pay_recall(db_session, user, journey, recall, _recall(_word(97)), now=NOW)  # Tuesday: 2
    for offset, kind in ((-3, STREAK_DAY_PRACTISED), (0, STREAK_DAY_PRACTISED), (1, STREAK_DAY_PRACTISED),
                         (2, STREAK_DAY_RELACHE)):
        db_session.add(StreakDay(user_id=user.id, local_date=(NOW + timedelta(days=offset)).date(), kind=kind))
    never_paid = _user(db_session)  # practised, but nothing on the ledger at all
    db_session.add(StreakDay(user_id=never_paid.id, local_date=NOW.date(), kind=STREAK_DAY_PRACTISED))
    db_session.flush()

    report = build_gold_report(db_session, days=14, now=NOW + timedelta(days=3))
    regulier = report["gold_by_rhythm"]["regulier"]
    assert (report["learners"], report["learner_days"]) == (1, 2), (
        "Tuesday (2) and Wednesday (finished, 0); not Saturday, before the ledger started for this "
        "learner, not the relâche, and not a learner the ledger never recorded"
    )
    assert (regulier["days"], regulier["median"], regulier["journee_pleine_share"]) == (2, 1, 0.0)
    assert report["journees_pleines"] == {"learner_weeks": 1, "mean_per_week": 0, "weeks_with_five": 0}


def test_the_report_names_stale_pending_and_pulped_entries(db_session: Session) -> None:
    user = _user(db_session)
    waiting, missed = _forge_attempt(4401, round_name="sentence"), _forge_attempt(4402, round_name="sentence")
    for attempt in (waiting, missed):
        gold_ledger.record_forge_item(
            db_session, user=user, attempt=attempt, rung=int(Rung.PRODUCE),
            verdict=_forge_verdict("incorrect", checked=False, local="correct"), mode="seance", reprise=False,
            below_level=False, level_before=4, contact_before=None, now=NOW,
        )
    gold_ledger.settle_forge_item(
        db_session, user=user, attempt=missed, history_entry={"rung": int(Rung.PRODUCE)},
        verdict=_forge_verdict("incorrect"), unread=False, now=NOW + timedelta(minutes=5),
    )
    report = build_gold_report(db_session, now=NOW + timedelta(hours=2))
    health = report["ledger_health"]
    assert (health["stale_pending"], health["void_by_reason"]) == (1, {"not_yet": 1})
    assert health["oldest_pending_at"] == NOW.replace(tzinfo=UTC).isoformat()
    assert {"metric": "stale_pending", "value": 1, "target": "0", "ok": False} in report["checks"]


def test_the_pilot_gold_report_is_for_the_owner_only(client: TestClient, db_session: Session) -> None:
    email = f"gold-owner-{uuid.uuid4().hex[:8]}@example.com"
    headers = login(client, email)
    assert client.get("/api/v1/analytics/pilot-gold", headers=headers).status_code == 403
    owner = _learner(db_session, email)
    owner.role = "admin"
    db_session.commit()
    response = client.get("/api/v1/analytics/pilot-gold", params={"days": 7}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["report"], body["window_days"], body["rule_version"]) == ("gold_shadow", 7, core.RULE_VERSION)


def test_a_mistyped_mode_is_refused_at_startup() -> None:
    from pydantic import ValidationError

    from app.config import Settings

    assert Settings(ATELIER_GOLD_MODE=" Shadow ").ATELIER_GOLD_MODE == "shadow"
    with pytest.raises(ValidationError):
        Settings(ATELIER_GOLD_MODE="loud")
