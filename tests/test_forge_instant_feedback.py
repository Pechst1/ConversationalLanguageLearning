"""WP-S1 (La Forge): grade locally, never block on the model.

* keyed rungs (recognise, word bank, classify, transform) come back from the
  answer key in well under 300 ms, with no model on the request path;
* free production returns a provisional local verdict at once, the model's
  verdict lands asynchronously and amends the evidence exactly once;
* the word bank has no second check;
* every submit is logged with its rung and latency (WP-S8).
"""
from __future__ import annotations

import time
from statistics import quantiles
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import atelier as atelier_endpoints
from app.config import settings
from app.db.models.atelier import AtelierSession
from app.db.models.grammar import UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.services.atelier import FORGE_VERDICT_EVENT, AtelierCorrectionService, AtelierSRSService
from app.services.forge_grading import (
    describe_diff,
    production_local_check,
    same_answer,
    token_diff,
)
from tests.test_atelier import (
    _attach_primed_exercise_set,
    _concept,
    _FakeLLMService,
    _prime_core_exercise_sets,
    _token,
    _user,
)

# -- the local grader ---------------------------------------------------------


def test_comparison_folds_typography_but_reports_accents():
    assert same_answer("s’il vous plaît", "S'il vous plaît.") == (True, False)
    assert same_answer("  Je  ne bois pas de café !", "je ne bois pas de café") == (True, False)
    assert same_answer("Je ne bois pas de cafe", "Je ne bois pas de café.") == (True, True)
    assert same_answer("Je bois du café", "Je ne bois pas de café.") == (False, False)


def test_token_diff_names_the_ending_the_missing_word_and_the_order():
    assert token_diff("Une petit table blanche", "Une petite table blanche") == [
        {"kind": "ending", "learner": "petit", "target": "petite"}
    ]
    assert token_diff("Je bois pas de café", "Je ne bois pas de café") == [
        {"kind": "missing", "learner": "", "target": "ne"}
    ]
    assert token_diff("table petite une", "une petite table")[0]["kind"] == "order"
    assert token_diff("je suis allé a la gare", "Je suis allé à la gare.") == [
        {"kind": "accent", "learner": "a", "target": "à"}
    ]
    # Elisions stay whole tokens; «aujourd'hui» is one word.
    assert token_diff("J’ai vu l’homme aujourd'hui", "J'ai vu l'homme aujourd'hui") == []
    why = describe_diff(token_diff("Une petit table", "Une petite table"), "en")
    assert "«petit»" in why and "«petite»" in why and "ending" in why


def test_production_local_check_uses_the_units_detector(db_session):
    concept = _concept(db_session, "FR_B1_COND_001")
    hit = production_local_check(concept, "Si tu viens demain, je te montrerai la ville.", "Si je finis tôt, je t'appellerai.")
    miss = production_local_check(concept, "Je viens demain avec mon frère.")
    assert hit["detector"] == "hit" and hit["source"] == "detector"
    assert 0.0 <= hit["model_similarity"] <= 1.0
    assert miss["detector"] == "miss"


# -- keyed rungs: p95 < 300 ms, no model on the request path ------------------


@pytest.fixture()
def no_model(monkeypatch):
    """No provider configured: nothing may even be queued, let alone awaited."""

    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    monkeypatch.setattr(settings, "ATELIER_BACKGROUND_PREGENERATION_ENABLED", False)
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)

    def refuse(*_args, **_kwargs):  # pragma: no cover - reached only on a regression
        raise AssertionError("the séance called a model on the request path")

    monkeypatch.setattr(AtelierCorrectionService, "_llm_correction", refuse)


def _start(client: TestClient, db_session) -> tuple[dict, str, dict, dict]:
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={})
    assert started.status_code == 201
    data = started.json()
    concept = data["concepts"][0]
    exercise_set = next(item for item in data["exercise_sets"] if item["concept_id"] == concept["id"])
    return headers, data["session_id"], concept, exercise_set["payload"]


def test_keyed_rungs_answer_from_the_key_under_300ms(client: TestClient, db_session, no_model):
    headers, session_id, concept, payload = _start(client, db_session)
    recognize = payload["recognize"]
    transform_items = payload["transform"]["items"]

    def answers(mode: str, right: bool) -> dict:
        if mode == "fill":
            return {item["id"]: item["correct_answer"] if right else "zzz" for item in recognize["fill"]["items"]}
        if mode == "classify":
            return {item["id"]: item["correct_label"] if right else "zzz" for item in recognize["classify"]["items"]}
        if mode == "word_bank":
            return {
                item["id"]: list(item["answer_tokens"]) if right else list(reversed(item["answer_tokens"]))
                for item in recognize["word_bank"]["items"]
            }
        return {item["id"]: item["expected_answer"] if right else item.get("source") or "zzz" for item in transform_items}

    timings: dict[str, list[float]] = {"recognize": [], "transform": []}
    server_ms: list[float] = []
    for index in range(40):
        mode = ("fill", "classify", "word_bank", "transform")[index % 4]
        round_name = "transform" if mode == "transform" else "recognize"
        body = {
            "concept_id": concept["id"],
            "round": round_name,
            "mode": "rewrite" if mode == "transform" else mode,
            "exercise_id": f"{concept['external_id']}:{mode}",
            "answer_payload": {"answers": answers(mode, right=index % 3 != 0)},
            "resubmit": True,
        }
        started = time.perf_counter()
        response = client.post(f"/api/v1/atelier/sessions/{session_id}/attempts", headers=headers, json=body)
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert response.status_code == 200, response.text
        correction = response.json()["correction"]
        assert correction["assessment_status"] == "checked"
        assert response.json()["ai_review"]["status"] in {"not_applicable", "failed"}
        if index >= 4:  # the first lap warms the catalogue caches
            timings[round_name].append(elapsed_ms)
            server_ms.append(float(correction["latency"]["local_ms"]))

    for round_name, values in timings.items():
        p95 = quantiles(values, n=20)[-1]
        print(f"forge {round_name}: p50 {quantiles(values, n=2)[0]:.1f} ms, p95 {p95:.1f} ms")
        assert p95 < 300, f"{round_name} p95 {p95:.1f} ms"
    assert quantiles(server_ms, n=20)[-1] < 300

    events = db_session.query(PilotEvent).filter(PilotEvent.event_type == FORGE_VERDICT_EVENT).all()
    assert len(events) == 40
    assert {event.payload["rung"] for event in events} == {"recognize", "transform"}
    assert all(event.payload["local_ms"] >= 0 for event in events)


def test_word_bank_has_no_second_check(db_session, monkeypatch):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    fake_llm = _FakeLLMService({"verdict": "incorrect", "score_0_4": 0, "errata": []})
    service = AtelierCorrectionService(db_session, llm_service=fake_llm)

    wrong_order = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="recognize",
        mode="word_bank",
        exercise_id="FR_B1_COND_001:word_bank:si-bank-1",
        answer_payload={"answers": {"si-bank-1": ["elle", "Si", "appelle", ",", "je", "répondrai"]}},
    )

    assert wrong_order.verdict != "correct"
    assert wrong_order.correction_payload["errata"]
    assert wrong_order.correction_payload["ai_review"]["status"] == "not_applicable"
    assert service.should_auto_start_ai_review(wrong_order) is False
    assert fake_llm.calls == []


# -- free production: instant local verdict, asynchronous model verdict --------


def test_free_production_returns_locally_and_queues_the_model(client: TestClient, db_session, monkeypatch):
    fake_llm = _FakeLLMService({"verdict": "partial", "score_0_4": 2, "errata": [
        {
            "display_label": "Accord",
            "learner_text": "je t'appellerai",
            "corrected_target": "je vous appellerai",
            "why_wrong": "You switch register.",
            "repair_hint": "You keep vous.",
            "severity": 2,
            "recurring": True,
            "task_error_type": "register",
        }
    ]})
    monkeypatch.setattr(AtelierCorrectionService, "_get_llm_service", lambda self: fake_llm)
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    monkeypatch.setattr(settings, "ATELIER_BACKGROUND_PREGENERATION_ENABLED", False)
    queued: list = []
    monkeypatch.setattr(atelier_endpoints, "run_atelier_ai_review", lambda attempt_id: queued.append(attempt_id))
    headers, session_id, concept, payload = _start(client, db_session)
    example = payload["output_ladder"]["sentence"]["items"][0]["example_answer"]

    started = time.perf_counter()
    response = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "sentence",
            "mode": "sentence",
            "exercise_id": f"{concept['external_id']}:sentence",
            "answer_payload": {"text": example},
        },
    )
    elapsed_ms = (time.perf_counter() - started) * 1000

    assert response.status_code == 200, response.text
    body = response.json()
    # The model was not called while the learner waited: the response carries
    # the local verdict and the relecture is queued for after it.
    assert fake_llm.calls == []
    assert queued == [UUID(body["attempt_id"])]
    assert elapsed_ms < 500
    assert body["correction"]["assessment_status"] == "provisional"
    assert body["correction"]["local_check"]["detector"] in {"hit", "miss", "unknown"}
    assert body["correction"]["local_check"]["model_similarity"] == 1.0
    assert body["ai_review"]["status"] == "pending"

    # The relecture lands: it amends the stored correction and the latency row.
    landed = AtelierCorrectionService(db_session, llm_service=fake_llm).run_ai_review_for_attempt(body["attempt_id"])
    assert fake_llm.calls and fake_llm.calls[0]["method"] == "generate_error_detection"
    assert landed.verdict == "partial"
    assert landed.correction_payload["assessment_status"] == "checked"
    second = landed.correction_payload["second_check"]
    assert second["status"] == "complete"
    assert second["verdict_changed"] is (body["verdict"] in {"correct", "accepted"})
    event = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == FORGE_VERDICT_EVENT, PilotEvent.entity_id == body["attempt_id"])
        .one()
    )
    db_session.refresh(event)
    assert event.payload["rung"] == "sentence"
    assert event.payload["local_ms"] >= 0
    assert event.payload["async_llm_ms"] is not None
    assert event.payload["verdict_changed"] is second["verdict_changed"]

    read = client.get(f"/api/v1/atelier/attempts/{body['attempt_id']}", headers=headers)
    assert read.json()["correction"]["second_check"]["status"] == "complete"


def _sentence_session(db_session, monkeypatch):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    user = _user(db_session)
    concept = _concept(db_session, "FR_B1_COND_001")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id])
    db_session.add(session)
    db_session.commit()
    _attach_primed_exercise_set(db_session, session, concept)
    return user, concept, session


def _progress(db_session, user, concept) -> UserGrammarProgress | None:
    db_session.expire_all()
    return (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one_or_none()
    )


def test_a_verdict_landing_after_the_seance_closed_counts_exactly_once(db_session, monkeypatch):
    user, concept, session = _sentence_session(db_session, monkeypatch)
    fake_llm = _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})
    service = AtelierCorrectionService(db_session, llm_service=fake_llm)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )
    assert attempt.correction_payload["evidence_hold"] is True

    # The séance closes before the model has answered: the provisional verdict
    # is not evidence yet.
    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    assert recap["pending_checks"] == 1
    assert recap["strengthened"] == 0
    assert _progress(db_session, user, concept) is None

    landed = service.run_ai_review_for_attempt(attempt.id)
    assert landed.correction_payload["evidence_applied"]["mode"] == "late"
    progress = _progress(db_session, user, concept)
    assert progress is not None and progress.reps == 1

    # A second landing (a manual retry) finds the stamp and writes nothing.
    assert service._apply_deferred_evidence(landed, user=user, session=session) is False
    landed.correction_payload = {**landed.correction_payload, "ai_review": {"status": "pending", "auto_started": False}}
    db_session.add(landed)
    db_session.commit()
    service.run_ai_review_for_attempt(attempt.id)
    assert _progress(db_session, user, concept).reps == 1


def test_a_verdict_landing_before_the_seance_closed_counts_in_the_session(db_session, monkeypatch):
    user, concept, session = _sentence_session(db_session, monkeypatch)
    fake_llm = _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})
    service = AtelierCorrectionService(db_session, llm_service=fake_llm)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )
    service.run_ai_review_for_attempt(attempt.id)

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)

    assert recap["pending_checks"] == 0
    assert recap["strengthened"] == 1
    assert _progress(db_session, user, concept).reps == 1
    db_session.refresh(attempt)
    assert not attempt.correction_payload.get("evidence_deferred")


def test_an_unchecked_answer_never_counts(db_session, monkeypatch):
    user, concept, session = _sentence_session(db_session, monkeypatch)

    class _Down:
        calls: list = []

        def generate_error_detection(self, messages, **kwargs):
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("down")

    service = AtelierCorrectionService(db_session, llm_service=_Down())
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id="FR_B1_COND_001:sentence",
        answer_payload={"text": "Si je finis tôt, je t'appellerai."},
    )
    AtelierSRSService(db_session).complete_session(session=session, user=user)
    failed = service.run_ai_review_for_attempt(attempt.id)

    assert failed.correction_payload["assessment_status"] == "unavailable"
    assert failed.verdict == "needs_review"
    assert failed.correction_payload["second_check"]["status"] == "failed"
    assert "evidence_applied" not in failed.correction_payload
    assert _progress(db_session, user, concept) is None
