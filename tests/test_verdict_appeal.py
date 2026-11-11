"""Package V stage 5: the appeal. «I think this is right», re-judged by the stronger model.

Before, a wrong verdict could only be found by a walk (#174): the learner who knew their
answer was right had no way to say so. Now, under a «not yet» or «partly» drill verdict:

* upheld: a ledger record supersedes the drill's, the step's result is amended, the memo
  gains the answer (the next learner who writes it is right with no call), and a script
  exports the case to ``tests/verdict_corpus/candidates/``;
* refused: one sentence of reason, in the learner's language;
* three per learner and day; a model that could not be asked costs nothing.

Driven through the real journey routes.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models.answer_memo import AnswerMemo
from app.db.models.daily_journey import DailyJourneyStep
from app.db.models.user import User
from app.db.models.verdict_appeal import VerdictAppeal
from app.services import answer_memo, verdict_appeal, verdict_ledger
from app.services.llm_service import LLMProviderError
from tests.test_daily_journey_api import (
    create_journey,
    journey_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    key,
    login,
    step_of,
)

#: Right French that the drill's key does not list.
OUTSIDE_THE_KEY = "le paquet"


class _AppealModel:
    """The stronger model: rules as told, and remembers what it was asked."""

    def __init__(self, *, upheld: bool = True, reason: str = "« le paquet » dit la même chose.") -> None:
        self.upheld = upheld
        self.reason = reason
        self.asked: list[dict[str, Any]] = []

    def generate_chat_completion(self, messages, **kwargs):
        payload = json.loads(messages[0]["content"])
        assert payload["output_schema"]["title"] == "AppealRuling"
        assert kwargs["system_prompt"] == verdict_appeal.APPEAL_SYSTEM_PROMPT
        self.asked.append(payload["data"])
        return SimpleNamespace(
            content=json.dumps({"upheld": self.upheld, "reason_native": self.reason}),
            model="appeal-model",
        )


@pytest.fixture()
def model(monkeypatch) -> _AppealModel:
    fake = _AppealModel()
    monkeypatch.setattr(verdict_appeal, "_client", lambda: fake)
    monkeypatch.setattr(answer_memo, "dispatcher", lambda _memo_id: None)
    return fake


def _missed_drill(client, db_session, headers) -> tuple[str, str]:
    """A day up to its first drill, made a typed one, answered outside its key."""

    journey = create_journey(client, headers)
    scene = step_of(journey, "scene")
    state = client.post(
        f"/api/v1/daily-journeys/{journey['id']}/advance",
        headers=headers,
        json={"mutation_id": key(), "expected_revision": journey["revision"], "current_step_id": scene["id"]},
    ).json()
    recall = step_of(state, "recall")
    step = db_session.get(DailyJourneyStep, uuid.UUID(recall["id"]))
    private = dict(step.private_task)
    task = dict(private["recall_task"])
    task.update(
        {
            "task_type": "translate", "prompt_fr": None, "correct_option_id": None, "correct_tile_order": [],
            "accepted_answers": ["le colis"], "solution_fr": "le colis", "options": [],
        }
    )
    private["recall_task"] = task
    step.private_task = private
    db_session.commit()
    attempt = client.post(
        f"/api/v1/daily-journeys/{journey['id']}/steps/{recall['id']}/attempts",
        headers=headers,
        json={"mutation_id": key(), "expected_revision": state["revision"], "input": {"mode": "text", "text": OUTSIDE_THE_KEY}},
    )
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["check"]["outcome"] == "not_yet"
    return journey["id"], recall["id"]


def _appeal(client, headers, journey_id, step_id):
    return client.post(f"/api/v1/daily-journeys/{journey_id}/steps/{step_id}/appeal", headers=headers)


def test_an_upheld_appeal_supersedes_the_verdict_and_the_memo_gains_the_answer(
    journey_client, journey_enabled, db_session, model  # noqa: F811
):
    headers = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    journey_id, step_id = _missed_drill(journey_client, db_session, headers)

    reply = _appeal(journey_client, headers, journey_id, step_id)

    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["state"] == "upheld"
    assert (body["check"]["outcome"], body["check"]["checked_by"], body["check"]["counts"]) == ("right", "model", True)
    assert body["reason"] == "« le paquet » dit la même chose."
    assert body["remaining_today"] == 2
    # What the model was asked: the exercise, the answer, and the learner's language.
    asked = model.asked[0]
    assert asked["learner_answer"] == OUTSIDE_THE_KEY
    assert asked["reason_language"] == "en"
    assert "le colis" in asked["exercise"]["expected_fr"]

    # The ledger: the drill's verdict, superseded by the appeal's.
    live = verdict_ledger.live_record(db_session, "journey_step", step_id)
    assert live.counts is True and live.supersedes_id is not None
    first = db_session.get(type(live), live.supersedes_id)
    assert first.counts is True and first.verdict["shown"]["outcome"] == "not_yet"
    # The step's result says so, and what it was.
    result = db_session.get(DailyJourneyStep, uuid.UUID(step_id)).private_task["result"]
    assert result["outcome"] == "met"
    assert result["appeal"]["was"] == "not_yet"
    # The memo gained the answer, confirmed: the next learner is right with no call.
    memo = db_session.scalars(select(AnswerMemo).where(AnswerMemo.surface == "recall")).one()
    assert (memo.state, memo.outcome, memo.answer_norm) == ("confirmed", "right", OUTSIDE_THE_KEY)

    other = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    journey = create_journey(journey_client, other)
    # (the same item, the same answer, another learner: the drill reads the memo)
    from app.services.journey_learning import _memo_settles_recall

    step = db_session.get(DailyJourneyStep, uuid.UUID(step_id))
    from app.services.daily_journey import _recall_task_from_json

    assert _memo_settles_recall(db_session, _recall_task_from_json(step.private_task["recall_task"]), "Le paquet")
    assert journey["id"] != journey_id


def test_a_refused_appeal_says_why_in_one_sentence_and_changes_nothing(
    journey_client, journey_enabled, db_session, model  # noqa: F811
):
    model.upheld, model.reason = False, "Ici, il faut « le colis » : « paquet » n'est pas le mot de la leçon."
    headers = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    journey_id, step_id = _missed_drill(journey_client, db_session, headers)

    body = _appeal(journey_client, headers, journey_id, step_id).json()

    assert body["state"] == "refused"
    assert body["check"]["outcome"] == "not_yet"
    assert body["reason"] == model.reason
    assert verdict_ledger.live_record(db_session, "journey_step", step_id) is None
    assert db_session.get(DailyJourneyStep, uuid.UUID(step_id)).private_task["result"]["outcome"] == "not_yet"
    assert db_session.scalars(select(AnswerMemo)).first() is None

    # Asking again returns the same ruling and asks no one.
    again = _appeal(journey_client, headers, journey_id, step_id).json()
    assert (again["state"], again["reason"]) == ("refused", model.reason)
    assert len(model.asked) == 1


def test_three_appeals_a_day_and_an_unread_one_costs_nothing(
    journey_client, journey_enabled, db_session, model, monkeypatch  # noqa: F811
):
    headers = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    journey_id, step_id = _missed_drill(journey_client, db_session, headers)
    user = db_session.scalars(select(User).order_by(User.created_at.desc())).first()

    def down(*_a, **_k):
        raise LLMProviderError("appeal model down")

    monkeypatch.setattr(model, "generate_chat_completion", down)
    unread = _appeal(journey_client, headers, journey_id, step_id).json()
    assert (unread["state"], unread["check"]["outcome"], unread["remaining_today"]) == ("unread", "not_yet", 3)

    for _ in range(3):
        db_session.add(
            VerdictAppeal(
                user_id=user.id, surface="recall", subject_type="journey_step", subject_id=str(uuid.uuid4()),
                state="refused", created_at=datetime.now(UTC),
            )
        )
    db_session.commit()
    limited = _appeal(journey_client, headers, journey_id, step_id)
    assert limited.status_code == 429
    assert limited.json()["detail"] == "appeal_daily_limit"


def test_only_the_learners_own_not_yet_can_be_appealed(journey_client, journey_enabled, db_session, model):  # noqa: F811
    headers = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    journey_id, step_id = _missed_drill(journey_client, db_session, headers)
    stranger = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    assert _appeal(journey_client, stranger, journey_id, step_id).status_code == 404

    assert _appeal(journey_client, headers, journey_id, step_id).json()["state"] == "upheld"
    # Now right: nothing left to appeal, and the upheld ruling is what comes back.
    assert _appeal(journey_client, headers, journey_id, step_id).json()["state"] == "upheld"
    assert len(model.asked) == 1


def test_the_export_script_writes_upheld_cases_for_the_corpus(
    journey_client, journey_enabled, db_session, model, tmp_path  # noqa: F811
):
    from scripts import verdict_appeal_export

    headers = login(journey_client, f"appeal-{uuid.uuid4().hex[:8]}@example.com")
    _missed_drill_ids = _missed_drill(journey_client, db_session, headers)
    _appeal(journey_client, headers, *_missed_drill_ids)

    written = verdict_appeal_export.export(db_session, out_dir=tmp_path)

    assert len(written) == 1
    lines = written[0].read_text(encoding="utf-8").splitlines()
    case = json.loads(lines[0])
    assert case["surface"] == "recall" and case["text"] == OUTSIDE_THE_KEY
    assert case["expected"] == "right" and case["was"] == "not_yet"
    assert "le colis" in case["item"]["expected_fr"]
    # Exported once: a second run writes nothing.
    assert verdict_appeal_export.export(db_session, out_dir=tmp_path) == []
