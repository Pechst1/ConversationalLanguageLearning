# ruff: noqa: F811 - the journey fixtures are imported by name and requested as arguments
"""La Forge, integrated (WP-S1 × S2 × S3 × S4): one engine, end to end.

A Soutenu day folds a forge step into its Scène movement (S4). The step's
link starts a forge séance (S3) seated from the one picker's plan, with the
fold's budget. The rule's items come from the séance's exercise set and, once
a rung has no unused item left, from the item bank (S2): generated, appended
to this session's set, graded by their key on the request path (S1), never a
sentence twice. Completing the block hands the learner back to the day's
step and recomputes the level.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierServedItem, AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.schemas.daily_journey import ForgePrompt
from app.services.forge import forge_state_of
from app.services.grammar_catalog import FrenchCoreGrammarCatalog
from app.services.item_bank import units_for_external_id
from tests.test_journey_end_to_end import (
    Driver,
    assembled_client,  # noqa: F401 - fixture
    journey_enabled,  # noqa: F401 - fixture
    learner_id,
    register,
)


def _right(item: dict[str, Any], round_name: str, mode: str) -> dict[str, Any]:
    if round_name == "recognize":
        if mode == "word_bank":
            return {"answers": {item["id"]: list(item.get("answer_tokens") or [])}}
        return {"answers": {item["id"]: item.get("correct_answer") or item.get("correct_label")}}
    if round_name == "transform":
        return {"answers": {item["id"]: item.get("expected_answer")}}
    return {"text": str(item.get("example_answer") or "")}


def _wrong(item: dict[str, Any], round_name: str, mode: str) -> dict[str, Any]:
    if round_name in {"recognize", "transform"}:
        return {"answers": {item["id"]: ["zzz"] if mode == "word_bank" else "zzz"}}
    return {"text": "zzz"}


def _walk_to_the_forge_step(driver: Driver) -> dict[str, Any]:
    for _ in range(80):
        step = driver.current()
        if step is None or step["kind"] == "forge":
            break
        if step["kind"] == "recall":
            driver.attempt(driver.recall_answer(step, correct=True))
            if driver.journey.get("current_step_id") == step["id"]:
                driver.advance()
        else:
            driver.advance()
    step = driver.current()
    assert step is not None and step["kind"] == "forge"
    return step


def test_soutenu_day_forge_step_runs_a_bank_topped_seance_and_returns_to_the_day(
    assembled_client: TestClient, journey_enabled: None, db_session: Session
) -> None:
    FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()
    email = f"forge-e2e-{uuid.uuid4().hex[:8]}@example.com"
    headers = register(assembled_client, email)
    user = db_session.get(User, learner_id(db_session, email))
    user.daily_goal_minutes = 20  # Soutenu: the forge is folded into the day
    db_session.commit()
    driver = Driver(assembled_client, headers, db=db_session)
    journey = driver.create()
    forge_steps = [step for step in journey["steps"] if step["kind"] == "forge"]
    assert len(forge_steps) == 1
    step = _walk_to_the_forge_step(driver)
    prompt = ForgePrompt.model_validate(step["prompt"])
    assert prompt.href.startswith("/atelier?mode=forge") and f"step={step['id']}" in prompt.href
    concept = db_session.get(GrammarConcept, prompt.concept_id)
    assert units_for_external_id(concept.external_id), "today's rule has bank templates"

    # The step's link: a forge séance for today's rule, the fold's budget.
    started = assembled_client.post(
        "/api/v1/atelier/sessions",
        headers=headers,
        json={
            "preferred_concept_id": prompt.concept_id,
            "origin": "journey",
            "budget_seconds": prompt.budget_seconds,
            "journey_step_id": step["id"],
        },
    )
    assert started.status_code == 201, started.text
    data = started.json()
    session_id = data["session_id"]
    plan = data["quote"]["forge"]
    assert plan["origin"] == "journey" and plan["journey_step_id"] == step["id"]
    assert plan["units"][0] == {"concept_id": prompt.concept_id, "role": "today", "reason": plan["units"][0]["reason"]}
    assert plan["budget_seconds"] == prompt.budget_seconds
    forge = data["forge"]
    assert forge["mode"] == "seance" and forge["rules"][0]["concept_id"] == prompt.concept_id
    initial_set = next(s for s in data["exercise_sets"] if s["concept_id"] == prompt.concept_id)["payload"]
    initial_ids = {
        str(item["id"])
        for container in (
            *(initial_set["recognize"][mode]["items"] for mode in ("fill", "classify", "word_bank")),
            initial_set["transform"]["items"],
            *(initial_set["output_ladder"][key]["items"] for key in ("sentence", "speak", "conversation")),
        )
        for item in container
    }

    # Miss until the rule has sunk to recognise and spent its three fill
    # items: the next recognise item is a bank top-up. Then answer right.
    served_ids: list[str] = []
    topped_up: list[dict[str, Any]] = []
    nxt = forge["next"]
    answered = 0
    while nxt is not None and answered < 40:
        item = nxt["item"]
        assert item["id"] == nxt["item_id"]
        served_ids.append(str(item["id"]))
        if str(item["id"]) not in initial_ids:
            topped_up.append({"item": item, "round": nxt["round"], "mode": nxt["mode"]})
        miss = not topped_up
        answer = (_wrong if miss else _right)(item, nxt["round"], nxt["mode"])
        response = assembled_client.post(
            f"/api/v1/atelier/sessions/{session_id}/attempts",
            headers=headers,
            json={
                "concept_id": nxt["concept_id"],
                "round": nxt["round"],
                "mode": "rewrite" if nxt["round"] == "transform" else nxt["mode"],
                "exercise_id": f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}",
                "answer_payload": answer,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        if str(item["id"]) not in initial_ids and nxt["round"] in {"recognize", "transform"}:
            # A top-up is graded by its own key, on the request path.
            assert body["correction"]["assessment_status"] == "checked"
            assert body["verdict"] == "correct", body["correction"]
            assert body["correction"]["forge"]["counted"] is True
        answered += 1
        nxt = body["forge"]["next"]

    assert topped_up, "the séance went beyond the initial set"
    assert len(served_ids) == len(set(served_ids)), "no item twice"
    assert answered > 3

    # The top-ups live in this session's own set, where the submit path found them.
    fresh = assembled_client.get(f"/api/v1/atelier/sessions/{session_id}", headers=headers).json()
    payload = next(s for s in fresh["exercise_sets"] if s["concept_id"] == prompt.concept_id)["payload"]
    appended = payload["forge"]["appended"]
    assert {entry["id"] for entry in appended} >= {entry["item"]["id"] for entry in topped_up}
    sentences = db_session.query(AtelierServedItem.fingerprint).filter(
        AtelierServedItem.atelier_session_id == uuid.UUID(session_id)
    ).all()
    fingerprints = [row[0] for row in sentences]
    assert len(fingerprints) == len(set(fingerprints)), "no sentence twice"
    assert {entry["fingerprint"] for entry in appended} <= set(fingerprints)

    # One evidence per checked item.
    session = db_session.get(AtelierSession, uuid.UUID(session_id))
    db_session.refresh(session)
    state = forge_state_of(session)
    assert state.position == answered
    assert state.evidence_written == sum(1 for entry in state.history if entry["checked"])

    # Complete: the level is recomputed and the day's step reads «Back to the scene».
    user = db_session.get(User, user.id)
    user.cefr_estimate_payload = None
    db_session.commit()
    done = assembled_client.post(f"/api/v1/atelier/sessions/{session_id}/complete", headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["recap"]["forge"]["journey_step_id"] == step["id"]
    db_session.expire_all()
    assert (db_session.get(User, user.id).cefr_estimate_payload or {}).get("coverage"), "the level was recomputed"

    driver.journey = driver.today()["journey"]
    back = next(item for item in driver.journey["steps"] if item["kind"] == "forge")
    assert back["prompt"]["forged"] is True
    driver.advance()
    assert driver.current() is None or driver.current()["kind"] != "forge"


# ---------------------------------------------------------------------------
# The bank top-up, the relecture and the test-out, service by service
# ---------------------------------------------------------------------------


def _forge_session(db_session: Session, external_id: str = "FR_A2_NEG_001"):
    from tests.test_atelier import _attach_primed_exercise_set, _concept, _user

    user = _user(db_session)
    concept = _concept(db_session, external_id)
    session = AtelierSession(user_id=user.id, selected_concept_ids=[concept.id], status="in_progress", quote_payload={})
    db_session.add(session)
    db_session.commit()
    shared = _attach_primed_exercise_set(db_session, session, concept)
    return user, concept, session, shared


def test_a_top_up_copies_a_shared_set_on_write_and_never_repeats_a_sentence(db_session: Session) -> None:
    from app.core.forge import Rung
    from app.services.atelier import AtelierExerciseGenerator, served_fingerprints
    from app.services.forge import FORGE_SESSION_SET_SOURCE, BankItemProvider, fingerprint_for
    from app.services.grammar_units import examples as unit_examples
    from app.services.item_bank import fingerprint as bank_fingerprint

    user, concept, session, shared = _forge_session(db_session)
    shared_payload = json.loads(json.dumps(shared.payload))
    before = served_fingerprints(db_session, user)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    assert provider.sets[concept.id].id == shared.id, "the shared set is served until a top-up"
    initial = len(provider.payloads.payloads[concept.id]["recognize"]["fill"]["items"])

    exclude: set[str] = set()
    posed: list[str] = []
    for _ in range(12):
        item = provider.item_for(concept_id=concept.id, rung=Rung.RECOGNISE, exclude=exclude)
        assert item is not None and item.rung == Rung.RECOGNISE
        exclude.add(fingerprint_for(concept.id, item.round, item.mode, item.item_id))
        posed.append(item.item_id)
    assert len(posed) == len(set(posed))

    db_session.expire_all()
    session = db_session.get(AtelierSession, session.id)
    owned_id = session.quote_payload["exercise_set_ids"][str(concept.id)]
    assert owned_id != str(shared.id), "copy-on-write: the shared set is never written"
    db_session.refresh(shared)
    assert shared.payload == shared_payload
    owned = provider.sets[concept.id]
    db_session.refresh(owned)
    assert str(owned.id) == owned_id and owned.source == FORGE_SESSION_SET_SOURCE
    assert owned.payload["forge"]["owner_session_id"] == str(session.id)
    assert AtelierExerciseGenerator.validate_payload(owned.payload, concept=concept), "the set keeps its shape"

    appended = owned.payload["forge"]["appended"]
    fingerprints = [entry["fingerprint"] for entry in appended]
    assert len(appended) == 12 - initial and len(set(fingerprints)) == len(fingerprints)
    assert not set(fingerprints) & before, "nothing served in the last seven days"
    assert not set(fingerprints) & {bank_fingerprint(example) for example in unit_examples(concept)}
    assert set(fingerprints) <= served_fingerprints(db_session, user), "each top-up is recorded as served"


def test_a_topped_up_item_is_graded_by_its_key_through_the_submit_path(db_session: Session) -> None:
    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import BankItemProvider, fingerprint_for

    user, concept, session, _shared = _forge_session(db_session)
    provider = BankItemProvider.for_session(db_session, user=user, session=session)
    exclude = {
        fingerprint_for(concept.id, "transform", "rewrite", str(item["id"]))
        for item in provider.payloads.payloads[concept.id]["transform"]["items"]
    }
    item = provider.item_for(concept_id=concept.id, rung=Rung.TRANSFORM, exclude=exclude)
    assert item is not None and item.round == "transform"
    db_session.refresh(session)
    attempt = AtelierCorrectionService(db_session).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="transform",
        mode="rewrite",
        exercise_id=f"forge:{concept.id}:transform:{item.item_id}",
        answer_payload={"answers": {item.item_id: item.payload["expected_answer"]}},
    )
    assert attempt.prompt_payload["items"][0]["id"] == item.item_id
    assert attempt.verdict == "correct" and attempt.correction_payload["assessment_status"] == "checked"


def test_a_provisional_production_moves_the_staircase_and_counts_once_when_the_relecture_lands(
    db_session: Session, monkeypatch
) -> None:
    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state
    from tests.test_atelier import _FakeLLMService

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    fake_llm = _FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})
    service = AtelierCorrectionService(db_session, llm_service=fake_llm)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": "Je ne bois pas de café le soir."},
    )
    assert attempt.correction_payload["assessment_status"] == "provisional"
    assert attempt.correction_payload["local_check"]["detector"] == "hit"
    view = forge.observe_attempt(user=user, session=session, attempt=attempt)
    entry = forge_state_of(session).history[-1]
    assert entry["checked"] is False and entry["counted"] is False
    assert view["rules"][0]["rung"] == int(Rung.FREE_USE), "the local check keeps the séance moving"

    landed = service.run_ai_review_for_attempt(attempt.id)
    assert landed.correction_payload["evidence_applied"]["mode"] == "forge"
    db_session.refresh(session)
    entry = forge_state_of(session).history[-1]
    assert entry["amended"] is True and entry["counted"] is True
    written = forge_state_of(session).evidence_written

    # A second landing (a manual retry) changes nothing.
    landed.correction_payload = {**landed.correction_payload, "ai_review": {"status": "pending", "auto_started": True}}
    db_session.add(landed)
    db_session.commit()
    service.run_ai_review_for_attempt(attempt.id)
    db_session.refresh(session)
    assert forge_state_of(session).evidence_written == written


def test_a_test_out_passes_on_local_grading_without_a_model(db_session: Session, monkeypatch) -> None:
    from app.config import settings
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService
    from tests.test_atelier import _concept, _user

    monkeypatch.setattr(settings, "ATELIER_CORRECTION_LLM_ENABLED", False)
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    user = _user(db_session)
    concept = _concept(db_session, "FR_A2_NEG_001")
    forge = ForgeService(db_session)
    session = forge.start_test_out(user=user, concept_id=concept.id)
    service = AtelierCorrectionService(db_session)
    answered = 0
    while (nxt := forge.next_item(user=user, session=session)) is not None:
        free = nxt["round"] not in {"recognize", "transform"}
        answer = {"text": "Je ne mange pas de viande le soir."} if free else _right(nxt["item"], nxt["round"], nxt["mode"])
        attempt = service.submit_attempt(
            session=session,
            user=user,
            concept=concept,
            round_name=nxt["round"],
            mode="rewrite" if nxt["round"] == "transform" else nxt["mode"],
            exercise_id=f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}",
            answer_payload=answer,
        )
        if free:
            assert attempt.correction_payload["graded_by"] == "local_test_out"
            assert attempt.correction_payload["ai_review"]["status"] == "not_applicable"
        forge.observe_attempt(user=user, session=session, attempt=attempt)
        answered += 1
    assert answered == 5
    result = forge_state_of(session).result
    assert result["passed"] is True and result["production_correct"] is True
