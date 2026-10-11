"""WP-S8 — measure and prove La Forge's speed.

WORK-PACKAGES-2026-09-24-seance §3 WP-S8:

* per-rule metrics from real rows: items-to-proficient (forge rung ≥ 4),
  items-to-held, days-to-held, lapse rate after held, test-out pass rate;
* per séance: active minutes, completion, abandon (the new
  ``forge_abandoned`` event: park, explicit exit, a stale séance found on a
  later start), latency p50/p95 per rung;
* the owner-only dashboard API ``/analytics/pilot-forge`` (7 / 30 days, per band);
* the Dossier's measured line (hidden under three held rules);
* the simulation report script and its numbers in the doc.
"""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services.forge_metrics import (
    FORGE_ABANDONED_EVENT,
    active_seconds,
    forge_dashboard,
    latency_metrics,
    learner_rule_speed,
    record_forge_abandoned,
    rule_metrics,
    seance_metrics,
    sweep_stale_forge_seances,
)
from tests.test_atelier import _prime_core_exercise_sets, _token
from tests.test_wp_s3_forge import _answer_for, _item, _submit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def _forge_quote(*, finished: bool = False, mode: str = "seance", answered: int = 0) -> dict:
    return {
        "forge": {
            "mode": mode,
            "length": 12,
            "tracks": [{"concept_id": 1, "role": "today", "rung": 2}],
            "history": [{"concept_id": 1} for _ in range(answered)],
            "finished": finished,
            "budget_seconds": 360,
            "origin": "after_day",
        }
    }


def _attempt(user_id, concept_id, at, *, session_id=None, verdict="correct", new_rung=None, round_name="recognize",
             mode="fill", status="checked") -> AtelierAttempt:
    correction = {"assessment_status": status}
    if new_rung is not None:
        correction["forge"] = {"new_rung": new_rung}
    return AtelierAttempt(
        id=uuid4(),
        atelier_session_id=session_id or uuid4(),
        user_id=user_id,
        concept_id=concept_id,
        round=round_name,
        mode=mode,
        exercise_id=f"x:{uuid4()}",
        verdict=verdict,
        correction_payload=correction,
        answer_payload={},
        created_at=at,
    )


# ---------------------------------------------------------------------------
# Per-rule metrics (pure, from fixture rows)
# ---------------------------------------------------------------------------


def test_rule_metrics_items_and_days_to_proficient_and_held():
    user = uuid4()
    introduced = NOW - timedelta(days=20)
    held_at = NOW - timedelta(days=2)
    progress = UserGrammarProgress(user_id=user, concept_id=7, introduced_at=introduced, held_at=held_at)
    test_out_session = AtelierSession(id=uuid4(), user_id=user, status="test_out_done")
    attempts = [
        # A test-out answer at rung 5 never counts as reaching proficient.
        _attempt(user, 7, introduced + timedelta(hours=1), session_id=test_out_session.id, new_rung=5),
        _attempt(user, 7, introduced + timedelta(days=1), new_rung=1),
        _attempt(user, 7, introduced + timedelta(days=2), new_rung=2),
        _attempt(user, 7, introduced + timedelta(days=3), new_rung=3),
        _attempt(user, 7, introduced + timedelta(days=4), new_rung=4),  # proficient: the 5th answer
        _attempt(user, 7, introduced + timedelta(days=10), new_rung=5),
        _attempt(user, 7, held_at - timedelta(minutes=1), new_rung=5),  # 7 answers up to held
        _attempt(user, 7, held_at + timedelta(days=1), verdict="incorrect"),  # a later day, wrong: lapse
    ]
    metrics = rule_metrics(
        [progress], attempts, [test_out_session], since=NOW - timedelta(days=30), until=NOW
    )
    assert metrics["items_to_proficient"] == {"n": 1, "median": 5.0, "p90": 5.0}
    assert metrics["items_to_held"]["n"] == 1 and metrics["items_to_held"]["median"] == 7.0
    assert metrics["days_to_held"]["median"] == 18.0
    assert metrics["lapse_after_held"] == {"returned": 1, "lapsed": 1, "rate": 1.0}


def test_rule_metrics_windows_and_test_outs():
    user = uuid4()
    # Held by a test-out: not in the speed cohort, counted in the pass rate.
    tested = UserGrammarProgress(
        user_id=user, concept_id=1, introduced_at=NOW - timedelta(days=1), held_at=NOW - timedelta(days=1),
        tested_out_at=NOW - timedelta(days=1),
    )
    # Held before the 7-day window: out of the cohort there, in the 30-day one.
    early = UserGrammarProgress(
        user_id=user, concept_id=2, introduced_at=NOW - timedelta(days=40), held_at=NOW - timedelta(days=20),
    )
    sessions = [
        AtelierSession(id=uuid4(), user_id=user, status="test_out_done", completed_at=NOW - timedelta(days=1),
                       recap_payload={"test_out": {"passed": True}}),
        AtelierSession(id=uuid4(), user_id=user, status="test_out_done", completed_at=NOW - timedelta(days=2),
                       recap_payload={"test_out": {"passed": False}}),
        AtelierSession(id=uuid4(), user_id=user, status="test_out", completed_at=None, recap_payload={}),
    ]
    # A correct answer on a later day: returned, not lapsed.
    attempts = [_attempt(user, 2, NOW - timedelta(days=3))]
    week = rule_metrics([tested, early], attempts, sessions, since=NOW - timedelta(days=7), until=NOW)
    assert week["items_to_held"]["n"] == 0 and week["days_to_held"]["median"] is None
    assert week["test_out"] == {"finished": 2, "passed": 1, "pass_rate": 0.5}
    assert week["lapse_after_held"] == {"returned": 1, "lapsed": 0, "rate": 0.0}
    month = rule_metrics([tested, early], attempts, sessions, since=NOW - timedelta(days=30), until=NOW)
    assert month["days_to_held"] == {"n": 1, "median": 20.0, "p90": 20.0}


def test_an_unchecked_answer_is_no_lapse():
    user = uuid4()
    held = UserGrammarProgress(user_id=user, concept_id=3, introduced_at=NOW - timedelta(days=30),
                               held_at=NOW - timedelta(days=5))
    attempts = [
        _attempt(user, 3, NOW - timedelta(days=3), verdict="incorrect", round_name="sentence", mode="sentence",
                 status="provisional"),
    ]
    metrics = rule_metrics([held], attempts, [], since=NOW - timedelta(days=30), until=NOW)
    assert metrics["lapse_after_held"] == {"returned": 0, "lapsed": 0, "rate": None}


# ---------------------------------------------------------------------------
# Per-séance metrics and latency
# ---------------------------------------------------------------------------


def test_active_seconds_caps_idle_gaps():
    start = NOW - timedelta(hours=2)
    session = AtelierSession(id=uuid4(), user_id=uuid4(), status="completed", started_at=start,
                             completed_at=start + timedelta(hours=1), quote_payload=_forge_quote())
    attempts = [
        _attempt(session.user_id, 1, start + timedelta(seconds=30), session_id=session.id),
        _attempt(session.user_id, 1, start + timedelta(seconds=60), session_id=session.id),
        # Lunch: a 40-minute gap counts as the 180 s ceiling.
        _attempt(session.user_id, 1, start + timedelta(minutes=41), session_id=session.id),
    ]
    # 30 + 30 + 180 + (completion 19 min later → 180)
    assert active_seconds(session, attempts) == 420


def test_seance_metrics_completion_abandon_and_open():
    user = uuid4()
    completed = AtelierSession(id=uuid4(), user_id=user, status="completed", started_at=NOW - timedelta(hours=3),
                               completed_at=NOW - timedelta(hours=3) + timedelta(minutes=6),
                               quote_payload=_forge_quote(answered=10))
    parked = AtelierSession(id=uuid4(), user_id=user, status="parked", started_at=NOW - timedelta(hours=2),
                            quote_payload=_forge_quote(answered=2))
    open_now = AtelierSession(id=uuid4(), user_id=user, status="in_progress", started_at=NOW - timedelta(minutes=5),
                              quote_payload=_forge_quote())
    left = AtelierSession(id=uuid4(), user_id=user, status="in_progress", started_at=NOW - timedelta(days=3),
                          quote_payload=_forge_quote())
    legacy = AtelierSession(id=uuid4(), user_id=user, status="completed", started_at=NOW - timedelta(hours=1),
                            quote_payload={})
    rows = {
        str(completed.id): [
            _attempt(user, 1, completed.started_at + timedelta(seconds=25 * i), session_id=completed.id)
            for i in range(1, 11)
        ]
    }
    metrics = seance_metrics([completed, parked, open_now, left, legacy], rows, {str(parked.id)}, now=NOW)
    assert metrics["started"] == 4  # the legacy séance is not a forge séance
    assert metrics["completed"] == 1 and metrics["completion_rate"] == 0.25
    assert metrics["abandoned"] == 2 and metrics["abandon_rate"] == 0.5
    assert metrics["still_open"] == 1 and metrics["never_returned"] == 1
    assert metrics["active_minutes"]["median"] == 6.0
    assert metrics["items"]["median"] == 10.0
    empty = seance_metrics([], {}, set(), now=NOW)
    assert empty["completion_rate"] is None and empty["active_minutes"]["median"] is None  # n/a, never 0


def test_latency_metrics_group_by_rung_with_percentiles():
    events = [
        PilotEvent(event_type="forge_verdict", payload={"rung": "recognize", "mode": "fill", "local_ms": float(ms)})
        for ms in range(1, 101)
    ]
    events.append(PilotEvent(event_type="forge_verdict", payload={
        "rung": "conversation", "mode": "conversation", "local_ms": 40.0, "async_llm_ms": 2200.0,
        "verdict_changed": True,
    }))
    report = latency_metrics(events)
    by_rung = {row["rung"]: row for row in report["by_rung"]}
    assert [row["rung"] for row in report["by_rung"]] == ["recognise", "free_use"]
    assert by_rung["recognise"]["n"] == 100
    assert by_rung["recognise"]["local_p50_ms"] == 51.0 and by_rung["recognise"]["local_p95_ms"] == 95.0
    assert by_rung["free_use"]["async_p95_ms"] == 2200.0 and by_rung["free_use"]["verdict_changed"] == 1


# ---------------------------------------------------------------------------
# The abandon event
# ---------------------------------------------------------------------------


def _user(db_session, **extra) -> User:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="x", target_language="fr", **extra)
    db_session.add(user)
    db_session.commit()
    return user


def _abandon_events(db_session, session_id) -> list[PilotEvent]:
    return (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == FORGE_ABANDONED_EVENT, PilotEvent.entity_id == str(session_id))
        .all()
    )


def test_record_forge_abandoned_once_and_never_for_finished_or_legacy(db_session):
    user = _user(db_session)
    seance = AtelierSession(user_id=user.id, status="in_progress", quote_payload=_forge_quote(answered=3),
                            recap_payload={})
    finished = AtelierSession(user_id=user.id, status="in_progress", quote_payload=_forge_quote(finished=True),
                              recap_payload={})
    legacy = AtelierSession(user_id=user.id, status="in_progress", quote_payload={}, recap_payload={})
    test_out = AtelierSession(user_id=user.id, status="test_out", quote_payload=_forge_quote(mode="test_out"),
                              recap_payload={})
    db_session.add_all([seance, finished, legacy, test_out])
    db_session.commit()
    first = record_forge_abandoned(db_session, seance, reason="exit")
    db_session.commit()
    assert first is not None and first.payload["answered"] == 3 and first.payload["reason"] == "exit"
    assert record_forge_abandoned(db_session, seance, reason="parked") is None
    for other in (finished, legacy, test_out):
        assert record_forge_abandoned(db_session, other, reason="exit") is None
    db_session.commit()
    assert len(_abandon_events(db_session, seance.id)) == 1


def test_a_stale_forge_seance_is_swept_as_expired(db_session):
    user = _user(db_session)
    stale = AtelierSession(user_id=user.id, status="in_progress", quote_payload=_forge_quote(),
                           recap_payload={}, started_at=datetime.now(UTC) - timedelta(days=2))
    fresh = AtelierSession(user_id=user.id, status="in_progress", quote_payload=_forge_quote(),
                           recap_payload={}, started_at=datetime.now(UTC) - timedelta(minutes=10))
    db_session.add_all([stale, fresh])
    db_session.commit()
    assert sweep_stale_forge_seances(db_session, user_id=user.id) == 1
    db_session.commit()
    events = _abandon_events(db_session, stale.id)
    assert len(events) == 1 and events[0].payload["reason"] == "expired"
    assert _abandon_events(db_session, fresh.id) == []
    assert sweep_stale_forge_seances(db_session, user_id=user.id) == 0


def test_parking_a_forge_seance_and_the_exit_endpoint_write_forge_abandoned(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    other = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_COND_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    answered = _submit(client, headers, data["session_id"], nxt, _answer_for(_item(data, nxt), nxt["round"], nxt["mode"]))
    assert answered.status_code == 200

    # The explicit exit: one event, the séance stays open.
    for _ in range(2):
        exited = client.post(f"/api/v1/atelier/sessions/{data['session_id']}/exit", headers=headers)
        assert exited.status_code == 204
    events = _abandon_events(db_session, data["session_id"])
    assert [e.payload["reason"] for e in events] == ["exit"]
    assert events[0].payload["answered"] == 1
    assert db_session.get(AtelierSession, UUID(data["session_id"])).status == "in_progress"

    # Another rule parks the séance; it already has its event, so none is added.
    second = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": other.id})
    assert second.status_code == 201
    assert len(_abandon_events(db_session, data["session_id"])) == 1

    # Parking a séance with no event yet writes «parked».
    third = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id})
    assert third.status_code == 201
    parked = _abandon_events(db_session, second.json()["session_id"])
    assert [e.payload["reason"] for e in parked] == ["parked"]

    # A completed séance writes nothing on exit.
    third_id = third.json()["session_id"]
    nxt = third.json()["forge"]["next"]
    _submit(client, headers, third_id, nxt, _answer_for(_item(third.json(), nxt), nxt["round"], nxt["mode"]))
    assert client.post(f"/api/v1/atelier/sessions/{third_id}/complete", headers=headers).status_code == 200
    assert client.post(f"/api/v1/atelier/sessions/{third_id}/exit", headers=headers).status_code == 204
    assert _abandon_events(db_session, third_id) == []


# ---------------------------------------------------------------------------
# The dashboard
# ---------------------------------------------------------------------------


def _seed_pilot(db_session, concept_id: int) -> tuple[User, User]:
    now = datetime.now(UTC)
    a1 = _user(db_session, cefr_estimate="A1.2")
    a2 = _user(db_session, cefr_estimate="A2.1")
    for user, days in ((a1, 16), (a2, 20)):
        db_session.add(UserGrammarProgress(
            user_id=user.id, concept_id=concept_id, introduced_at=now - timedelta(days=days + 3),
            held_at=now - timedelta(days=3), forge_rung=5,
        ))
        session = AtelierSession(user_id=user.id, status="completed", started_at=now - timedelta(days=1),
                                 completed_at=now - timedelta(days=1) + timedelta(minutes=5),
                                 quote_payload=_forge_quote(answered=4), recap_payload={})
        db_session.add(session)
        db_session.flush()
        for index in range(4):
            db_session.add(_attempt(user.id, concept_id, now - timedelta(days=5) + timedelta(minutes=index),
                                    session_id=session.id, new_rung=index + 2))
        db_session.add(PilotEvent(user_id=user.id, event_type="forge_verdict",
                                  payload={"rung": "transform", "mode": "rewrite", "local_ms": 4.0},
                                  occurred_at=now - timedelta(days=1)))
    left = AtelierSession(user_id=a1.id, status="parked", started_at=now - timedelta(hours=5),
                          quote_payload=_forge_quote(answered=1), recap_payload={})
    db_session.add(left)
    db_session.commit()
    record_forge_abandoned(db_session, left, reason="parked")
    db_session.commit()
    return a1, a2


def test_forge_dashboard_windows_and_bands(db_session):
    concept = GrammarConcept(name="Négation", external_id="FR_S8_TEST", level="A1")
    db_session.add(concept)
    db_session.commit()
    a1, a2 = _seed_pilot(db_session, concept.id)
    report = forge_dashboard(db_session, user_ids=[a1.id, a2.id])
    assert [w["days"] for w in report["windows"]] == [7, 30]
    week = report["windows"][0]
    overall = week["overall"]
    assert overall["learners"] == 2
    assert overall["rules"]["days_to_held"]["n"] == 2 and overall["rules"]["days_to_held"]["median"] == 18.0
    assert overall["rules"]["items_to_proficient"]["median"] == 3.0  # rungs 2, 3, 4 → the 3rd answer
    assert overall["rules"]["items_to_held"]["median"] == 4.0
    assert overall["seances"]["started"] == 3 and overall["seances"]["completed"] == 2
    assert overall["seances"]["abandoned"] == 1 and overall["seances"]["abandon_reasons"] == {"parked": 1}
    assert overall["latency"]["by_rung"][0]["rung"] == "transform"
    bands = {section["band"]: section for section in week["by_band"]}
    assert set(bands) == {"A1", "A2"}
    assert bands["A1"]["rules"]["days_to_held"]["median"] == 16.0
    assert bands["A2"]["rules"]["days_to_held"]["median"] == 20.0
    assert bands["A2"]["seances"]["abandoned"] == 0


def _register(client: TestClient) -> tuple[str, str]:
    email = f"{uuid4()}@example.com"
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "forge-secure", "target_language": "fr", "native_language": "en",
    })
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "forge-secure"}).json()["access_token"]
    return email, token


def test_pilot_forge_api_is_admin_only(client: TestClient, db_session):
    email, token = _register(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/v1/analytics/pilot-forge", headers=headers).status_code == 403
    user = db_session.query(User).filter(User.email == email).one()
    user.role = "admin"
    db_session.commit()
    response = client.get("/api/v1/analytics/pilot-forge", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert [w["days"] for w in body["windows"]] == [7, 30]
    overall = body["windows"][0]["overall"]
    assert set(overall) == {"learners", "rules", "seances", "latency"}
    assert {"started", "completion_rate", "abandon_rate", "active_minutes"} <= set(overall["seances"])
    assert {"items_to_proficient", "items_to_held", "days_to_held", "lapse_after_held", "test_out"} <= set(
        overall["rules"]
    )


# ---------------------------------------------------------------------------
# The Dossier's measured line
# ---------------------------------------------------------------------------


def test_learner_rule_speed_hidden_under_three_and_median_over_practice(db_session):
    user = _user(db_session)
    now = datetime.now(UTC)
    for concept_id, days in ((1, 14), (2, 20)):
        db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept_id,
                                           introduced_at=now - timedelta(days=days + 1),
                                           held_at=now - timedelta(days=1)))
    db_session.commit()
    two = learner_rule_speed(db_session, user_id=user.id)
    assert two["held"] == 2 and two["show"] is False
    db_session.add(UserGrammarProgress(user_id=user.id, concept_id=3, introduced_at=now, held_at=now,
                                       tested_out_at=now))
    db_session.commit()
    three = learner_rule_speed(db_session, user_id=user.id)
    assert three["show"] is True and three["held"] == 3 and three["held_by_practice"] == 2
    assert three["median_days_to_held"] == 17  # the test-out's zero days are left out


def test_the_dossier_level_carries_the_rule_speed(client: TestClient, db_session):
    token = _token(client)
    response = client.get("/api/v1/dossier/state", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    speed = response.json()["dossier"]["level"]["rules_speed"]
    assert speed == {"held": 0, "held_by_practice": 0, "median_days_to_held": None, "show": False, "minimum": 3}


# ---------------------------------------------------------------------------
# The simulation report
# ---------------------------------------------------------------------------


def test_the_simulation_report_runs_and_its_numbers_are_in_the_doc():
    spec = importlib.util.spec_from_file_location("forge_speed_report", ROOT / "scripts/forge_speed_report.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    block = module.report()
    assert block.startswith(module.BEGIN) and block.rstrip().endswith(module.END)
    doc = module.DOC.read_text(encoding="utf-8")
    assert module.BEGIN in doc and module.END in doc
    # Deterministic simulation: the committed table is today's output.
    committed = doc.split(module.BEGIN, 1)[1].split(module.END, 1)[0]
    strip = lambda text: [line for line in text.splitlines() if line.startswith("|")]  # noqa: E731
    assert strip(committed) == strip(block)
    for rhythm in ("Léger", "Régulier", "Soutenu", "Intensif"):
        assert f"| {rhythm} | 85 % | **Forge**" in block
