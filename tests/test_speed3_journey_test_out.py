"""SPEED-3 — «Je connais déjà — vérifier»: the Règle step's short test-out.

The journey's rule step offers a three-item «Épreuve de la règle» (the forge
test-out's item generation and grading, ``short=True``) without leaving the
day:

1. a pass holds the unit at once, as the forge test-out does;
2. a fail places the unit on the failed rung and every answer is evidence —
   the learner then reads the card as usual;
3. a unit tested out spends no slot of the weekly intake quota.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from app.core import forge as core
from app.core.forge import Rung
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.services import concept_life
from app.services.concept_life import concept_stage
from app.services.forge import forge_state_of
from tests.test_atelier import _prime_core_exercise_sets, _token
from tests.test_wp_s3_forge import _answer_for, _item, _submit, _wrong_for


def _right(item: dict, nxt: dict) -> dict:
    if nxt["round"] in {"conversation", "sentence"}:
        return {"text": str(item.get("example_answer") or item.get("model_answer") or "Je ne bois pas de café.")}
    return _answer_for(item, nxt["round"], nxt["mode"])


def _start(client: TestClient, headers: dict, concept_id: int) -> dict:
    started = client.post(
        "/api/v1/atelier/forge/test-out",
        headers=headers,
        json={"concept_id": concept_id, "short": True, "source": "journey"},
    )
    assert started.status_code == 201, started.text
    return started.json()


def _play(client: TestClient, headers: dict, data: dict, *, wrong_at: set[int]) -> tuple[list[int], dict]:
    nxt = data["forge"]["next"]
    rungs: list[int] = []
    body: dict = {}
    while nxt is not None:
        item = nxt.get("item") or _item(data, nxt)
        answer = _wrong_for(item, nxt["round"], nxt["mode"]) if len(rungs) in wrong_at else _right(item, nxt)
        rungs.append(nxt["rung"])
        response = _submit(client, headers, data["session_id"], nxt, answer)
        assert response.status_code == 200, response.text
        body = response.json()
        nxt = body["forge"]["next"]
    return rungs, body


def _progress(db_session, session_id: str, concept_id: int) -> tuple[AtelierSession, UserGrammarProgress]:
    session = db_session.get(AtelierSession, UUID(session_id))
    db_session.refresh(session)
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.concept_id == concept_id, UserGrammarProgress.user_id == session.user_id)
        .one()
    )
    db_session.refresh(progress)
    return session, progress


def test_the_journey_check_is_three_items_and_a_pass_holds_the_unit(client: TestClient, db_session):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = _start(client, headers, neg.id)
    assert data["status"] == "test_out"
    assert data["forge"]["mode"] == "test_out" and data["forge"]["length"] == 3
    assert data["forge"]["next"]["item"], "the item travels with the forge view: the journey renders it"

    rungs, body = _play(client, headers, data, wrong_at=set())
    assert rungs == [int(r) for r in core.TEST_OUT_SHORT_RUNGS] == [Rung.DISCRIMINATE, Rung.TRANSFORM, Rung.FREE_USE]
    result = body["forge"]["result"]
    assert result["passed"] is True and result["total"] == 3

    session, progress = _progress(db_session, data["session_id"], neg.id)
    assert session.status == "test_out_done"
    assert (session.quote_payload or {}).get("test_out_source") == "journey"
    assert progress.tested_out_at is not None and progress.held_at is not None
    assert concept_stage(progress) == "held"
    assert progress.forge_rung == core.TOP_RUNG


def test_a_failed_journey_check_places_the_unit_and_its_answers_are_evidence(client: TestClient, db_session):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = _start(client, headers, neg.id)

    rungs, body = _play(client, headers, data, wrong_at={0})
    assert len(rungs) == 3
    result = body["forge"]["result"]
    assert result["passed"] is False and result["placement_rung"] == Rung.DISCRIMINATE

    session, progress = _progress(db_session, data["session_id"], neg.id)
    assert progress.tested_out_at is None and progress.held_at is None
    # The unit is met (the learner now reads its card); it starts on the rung it failed.
    assert progress.introduced_at is not None
    assert progress.forge_rung == Rung.DISCRIMINATE
    assert forge_state_of(session).evidence_written >= 1


def test_the_full_epreuve_is_unchanged(client: TestClient, db_session):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    started = client.post("/api/v1/atelier/forge/test-out", headers=headers, json={"concept_id": neg.id})
    assert started.status_code == 201
    assert started.json()["forge"]["length"] == len(core.TEST_OUT_RUNGS) == 5


def test_a_tested_out_unit_spends_no_slot_of_the_weekly_quota(client: TestClient, db_session):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = _start(client, headers, neg.id)
    _play(client, headers, data, wrong_at=set())
    session, progress = _progress(db_session, data["session_id"], neg.id)
    assert progress.tested_out_at is not None
    user = session.user
    now = datetime.now(UTC) + timedelta(hours=1)
    # Nothing else was introduced: the day may still introduce a unit, as if
    # the known one had never taken a slot.
    assert concept_life.introductions_in_window(db_session, user, now=now) == []
    assert concept_life.introduction_due(db_session, user, now=now)
