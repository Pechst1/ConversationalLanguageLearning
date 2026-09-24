"""WP-S3 — La Forge: staircase, composition, item-level evidence, test-out.

WORK-PACKAGES-2026-09-24-seance §2 / WP-S3 «Done when»:
* median items-to-held per rule at 85 % accuracy under 60 (and today's ladder
  measured with the same simulation);
* no séance has 3 brand-new rules (the forge: at most one);
* the evidence written matches the items answered (with caps);
plus test-out pass → held, fail → placed on the right rung; composition shares
within ±10 %; never two items of one rule back to back.
"""
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core import forge as core
from app.core.forge import ForgeState, ForgeUnit, Role, Rung, Verdict
from app.core.srs.memory import EvidenceFormat
from app.core.srs.simulation import simulate_items_to_held
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.services.concept_life import concept_stage
from app.services.forge import (
    ForgeService,
    PayloadItemProvider,
    PickedUnit,
    SelectTodayComposer,
    forge_state_of,
    verdict_from_attempt,
)
from tests.test_atelier import _prime_core_exercise_sets, _token, _user

PARTIAL = Verdict(core.OUTCOME_PARTIAL)


def _units(today: int = 1, due: tuple[int, ...] = (2, 3), contrast: tuple[int, ...] = (4,)) -> list[ForgeUnit]:
    return [
        ForgeUnit(today, Role.TODAY.value, 0),
        *(ForgeUnit(cid, Role.DUE.value, 2) for cid in due),
        *(ForgeUnit(cid, Role.CONTRAST.value, 1) for cid in contrast),
    ]


def _run(state: ForgeState, answer) -> list[core.Slot]:
    slots = []
    while (slot := state.next_slot()) is not None:
        slots.append(slot)
        state.record(concept_id=slot.concept_id, rung=slot.rung, verdict=answer(slot), fingerprint=f"{slot.position}")
    return slots


# ---------------------------------------------------------------------------
# The staircase and the reprise
# ---------------------------------------------------------------------------


def test_staircase_moves_up_on_correct_down_on_error_and_holds_otherwise():
    assert core.step_rung(Rung.BUILD, Verdict.right()) == Rung.TRANSFORM
    assert core.step_rung(Rung.BUILD, Verdict.wrong()) == Rung.DISCRIMINATE
    assert core.step_rung(Rung.BUILD, PARTIAL) == Rung.BUILD
    assert core.step_rung(Rung.BUILD, Verdict(core.OUTCOME_INCORRECT, checked=False)) == Rung.BUILD
    assert core.step_rung(Rung.RECOGNISE, Verdict.wrong()) == Rung.RECOGNISE
    assert core.step_rung(Rung.FREE_USE, Verdict.right()) == Rung.FREE_USE
    assert [core.rung_name(r) for r in Rung] == [
        "recognise", "discriminate", "build", "transform", "produce", "free_use",
    ]


def test_rung_evidence_uses_the_wp_l3_formats():
    assert core.evidence_for(Rung.DISCRIMINATE, Verdict.right()).format is EvidenceFormat.RECOGNISE
    assert core.evidence_for(Rung.BUILD, Verdict.right()).format is EvidenceFormat.GUIDED
    guided_production = core.evidence_for(Rung.PRODUCE, Verdict.right())
    assert guided_production.format is EvidenceFormat.PRODUCE and guided_production.assisted
    free_use = core.evidence_for(Rung.FREE_USE, Verdict.right())
    assert free_use.format is EvidenceFormat.PRODUCE and not free_use.assisted
    assert core.evidence_for(Rung.TRANSFORM, PARTIAL).assisted
    assert core.evidence_for(Rung.TRANSFORM, Verdict(core.OUTCOME_CORRECT, checked=False)) is None


def test_an_error_books_a_reprise_three_to_five_items_later():
    state = ForgeState.seance(_units(), length=20)
    first = state.next_slot()
    assert first.role == Role.TODAY.value
    state.record(concept_id=first.concept_id, rung=first.rung, verdict=Verdict.wrong(), fingerprint="a")
    track = state.track(first.concept_id)
    booked = track.reprise_at
    assert booked is not None and 3 <= booked - first.position <= 5
    slots = _run(state, lambda _slot: PARTIAL)
    back = next(slot for slot in slots if slot.concept_id == first.concept_id)
    assert back.reprise and back.position == booked
    assert track.reprise_at is None  # answered: the reprise is spent
    assert back.position - first.position in {3, 4, 5}


def test_a_rule_clean_at_the_top_retires_from_the_seance():
    state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, 5), ForgeUnit(2, Role.DUE.value, 0)], length=12)
    slots = _run(state, lambda _slot: Verdict.right())
    assert [slot.concept_id for slot in slots].count(1) == 1  # free use right once: forged for today
    assert state.track(1).topped


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def test_composition_shares_are_40_40_20_within_ten_points():
    state = ForgeState.seance(_units(), length=20)
    _run(state, lambda _slot: PARTIAL)  # no top-out, no reprise: the pure mix
    shares = core.role_shares(state.history)
    assert abs(shares[Role.TODAY.value] - 0.4) <= 0.10
    assert abs(shares[Role.DUE.value] - 0.4) <= 0.10
    assert abs(shares[Role.CONTRAST.value] - 0.2) <= 0.10


def test_shares_renormalise_when_a_role_is_missing():
    state = ForgeState.seance(_units(contrast=()), length=10)
    _run(state, lambda _slot: PARTIAL)
    shares = core.role_shares(state.history)
    assert abs(shares[Role.TODAY.value] - 0.5) <= 0.10
    assert abs(shares[Role.DUE.value] - 0.5) <= 0.10


@pytest.mark.parametrize("seed", range(40))
def test_never_two_items_of_one_rule_back_to_back(seed):
    rng = random.Random(seed)
    due = tuple(range(2, 2 + rng.randint(0, 3)))
    contrast = (9,) if rng.random() < 0.6 else ()
    state = ForgeState.seance(_units(due=due, contrast=contrast), length=rng.randint(6, 24))
    choices = [Verdict.right(), Verdict.wrong(), PARTIAL, Verdict(core.OUTCOME_CORRECT, checked=False)]
    slots = _run(state, lambda _slot: rng.choice(choices))
    if len(state.tracks) > 1:
        assert core.distinct_rule_runs([slot.concept_id for slot in slots]) == 0


def test_no_seance_seats_more_than_one_brand_new_rule():
    units = [
        ForgeUnit(1, Role.TODAY.value, 0, is_new=True),
        ForgeUnit(2, Role.DUE.value, 0, is_new=True),
        ForgeUnit(3, Role.CONTRAST.value, 0, is_new=True),
        ForgeUnit(4, Role.DUE.value, 2),
    ]
    state = ForgeState.seance(units, length=12)
    assert [track.concept_id for track in state.tracks] == [1, 4]


def test_length_comes_from_the_rhythm_budget_and_the_learners_pace():
    assert core.seance_length(360, 25) == 14
    assert core.seance_length(360, 45) == 8
    assert core.seance_length(600, 25) == 24
    assert core.seance_length(240, 60) == core.MIN_SEANCE_ITEMS


# ---------------------------------------------------------------------------
# Evidence with caps
# ---------------------------------------------------------------------------


def test_evidence_written_matches_checked_items_with_first_success_per_rung_caps():
    state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, 2), ForgeUnit(2, Role.DUE.value, 2)], length=12)
    decisions = []
    rng = random.Random(3)
    while (slot := state.next_slot()) is not None:
        verdict = rng.choice([Verdict.right(), Verdict.wrong(), Verdict(core.OUTCOME_CORRECT, checked=False)])
        decisions.append((slot, verdict, state.record(concept_id=slot.concept_id, rung=slot.rung, verdict=verdict)))
    checked = [d for _s, v, d in decisions if v.checked]
    assert state.evidence_written == len(checked) == sum(1 for _s, _v, d in decisions if d.counted)
    assert all(not d.counted for _s, v, d in decisions if not v.checked)
    for cid in (1, 2):
        scheduled_successes = [d.rung for s, v, d in decisions if s.concept_id == cid and d.schedule and v.correct]
        assert len(scheduled_successes) == len(set(scheduled_successes))  # one per rung
        scheduled_failures = [d for s, v, d in decisions if s.concept_id == cid and d.schedule and v.checked and not v.correct]
        assert len(scheduled_failures) <= 1
        weights = [d.weight_scale for s, v, d in decisions if s.concept_id == cid and d.schedule and v.correct]
        assert weights == [core.MASSED_WEIGHT_DECAY**k for k in range(len(weights))]


def test_a_second_success_on_the_same_rung_folds():
    state = ForgeState.seance([ForgeUnit(1, Role.TODAY.value, 2)], length=6)
    first = state.record(concept_id=1, rung=2, verdict=Verdict.right())
    again = state.record(concept_id=1, rung=2, verdict=Verdict.right())
    assert first.schedule and first.counted
    assert again.counted and not again.schedule


# ---------------------------------------------------------------------------
# Test-out
# ---------------------------------------------------------------------------


def test_test_out_passes_on_four_of_five_with_the_production_right():
    result = core.evaluate_test_out([(0, True), (1, False), (2, True), (3, True), (5, True)])
    assert result.passed and result.placement_rung == Rung.FREE_USE


def test_test_out_fails_without_the_production_and_places_on_produce():
    result = core.evaluate_test_out([(0, True), (1, True), (2, True), (3, True), (5, False)])
    assert not result.passed and result.placement_rung == Rung.PRODUCE


def test_test_out_failure_places_the_rule_at_its_lowest_failed_rung():
    result = core.evaluate_test_out([(0, True), (1, True), (2, False), (3, False), (5, True)])
    assert not result.passed and result.placement_rung == Rung.BUILD
    result = core.evaluate_test_out([(0, False), (1, True), (2, True), (3, True), (5, False)])
    assert result.placement_rung == Rung.RECOGNISE


def test_test_out_state_runs_five_mixed_items_including_production():
    state = ForgeState.test_out(7)
    slots = _run(state, lambda _slot: Verdict.right())
    assert [slot.rung for slot in slots] == [int(r) for r in core.TEST_OUT_RUNGS]
    assert Rung.FREE_USE in [slot.rung for slot in slots]
    assert state.finished and state.result["passed"]


# ---------------------------------------------------------------------------
# The simulation: the forge against today's ladder
# ---------------------------------------------------------------------------


def test_simulation_median_items_to_held_under_sixty_at_85_percent():
    forge = simulate_items_to_held(0.85, engine="forge")
    ladder = simulate_items_to_held(0.85, engine="ladder")
    assert forge.rules_judged >= 20
    assert forge.median_items_to_held < 60
    assert forge.held_share >= 0.9
    # Today's ladder, same learner: one evidence per concept at the end, at the
    # strongest format (production), so the séance alone never gives «Tenue»
    # its spaced item — its rules are not held by the séance.
    assert ladder.median_items_to_held > forge.median_items_to_held
    # Evidence written == items answered (every forge item is checked here).
    assert forge.evidence_written == forge.items_answered
    assert ladder.evidence_written < ladder.items_answered / 5
    # Never more than one brand-new rule in a forge séance.
    assert forge.max_new_rules_per_seance <= 1


def test_simulation_with_the_journey_rappel_holds_rules_faster_in_days():
    forge = simulate_items_to_held(0.85, engine="forge", rappel=True)
    ladder = simulate_items_to_held(0.85, engine="ladder", rappel=True, ladder_padding=False)
    assert forge.median_items_to_held < 60
    assert forge.median_days_to_held < ladder.median_days_to_held


# ---------------------------------------------------------------------------
# The service and the API
# ---------------------------------------------------------------------------


def _answer_for(item: dict, round_name: str, mode: str) -> dict:
    if round_name == "recognize":
        if mode == "word_bank":
            return {"answers": {item["id"]: list(item.get("answer_tokens") or [])}}
        return {"answers": {item["id"]: item.get("correct_answer") or item.get("correct_label")}}
    if round_name == "transform":
        return {"answers": {item["id"]: item.get("expected_answer")}}
    return {"text": str(item.get("example") or item.get("model_answer") or "Je ne bois pas de café.")}


def _wrong_for(item: dict, round_name: str, mode: str) -> dict:
    if round_name == "recognize":
        if mode == "word_bank":
            return {"answers": {item["id"]: ["zzz"]}}
        return {"answers": {item["id"]: "zzz"}}
    if round_name == "transform":
        return {"answers": {item["id"]: "zzz"}}
    return {"text": "zzz"}


def _item(session_payload: dict, nxt: dict) -> dict:
    exercise_set = next(s for s in session_payload["exercise_sets"] if s["concept_id"] == nxt["concept_id"])
    payload = exercise_set["payload"]
    if nxt["round"] == "recognize":
        items = payload["recognize"][nxt["mode"]]["items"]
    elif nxt["round"] == "transform":
        items = payload["transform"]["items"]
    else:
        items = payload["output_ladder"][nxt["round"]]["items"]
    return items[nxt["item_index"]]


def _submit(client: TestClient, headers, session_id: str, nxt: dict, answer: dict):
    mode = "rewrite" if nxt["round"] == "transform" else nxt["mode"]
    exercise_id = f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}"
    return client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": nxt["concept_id"],
            "round": nxt["round"],
            "mode": mode,
            "exercise_id": exercise_id,
            "answer_payload": answer,
        },
    )


def test_a_forge_seance_writes_one_evidence_per_answered_item_and_none_at_the_end(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id})
    assert started.status_code == 201
    data = started.json()
    forge = data["forge"]
    assert forge["mode"] == "seance" and forge["length"] >= core.MIN_SEANCE_ITEMS
    nxt = forge["next"]
    answered = 0
    for _ in range(4):
        item = _item(data, nxt)
        answer = _answer_for(item, nxt["round"], nxt["mode"]) if answered % 2 == 0 else _wrong_for(item, nxt["round"], nxt["mode"])
        response = _submit(client, headers, data["session_id"], nxt, answer)
        assert response.status_code == 200, response.text
        answered += 1
        body = response.json()
        assert body["forge"]["answered"] == answered
        assert body["correction"]["forge"]["counted"] is True
        nxt = body["forge"]["next"]
        if nxt is None:
            break
    session = db_session.get(AtelierSession, UUID(data["session_id"]))
    db_session.refresh(session)
    state = forge_state_of(session)
    assert state.evidence_written == answered
    assert state.history[0]["correct"] is True and state.history[0]["schedule"] is True
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.concept_id == neg.id, UserGrammarProgress.user_id == session.user_id)
        .one()
    )
    db_session.refresh(progress)
    reps_before = progress.reps
    assert reps_before == sum(1 for entry in state.history if entry["schedule"])
    assert progress.forge_rung is not None

    done = client.post(f"/api/v1/atelier/sessions/{data['session_id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["recap"]["forge"]["evidence_written"] == answered
    db_session.refresh(progress)
    assert progress.reps == reps_before  # no end-of-session double count


def test_resubmitting_an_item_does_not_count_twice(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    item = _item(data, nxt)
    first = _submit(client, headers, data["session_id"], nxt, _wrong_for(item, nxt["round"], nxt["mode"]))
    assert first.json()["forge"]["answered"] == 1
    mode = "rewrite" if nxt["round"] == "transform" else nxt["mode"]
    again = client.post(
        f"/api/v1/atelier/sessions/{data['session_id']}/attempts",
        headers=headers,
        json={
            "concept_id": nxt["concept_id"], "round": nxt["round"], "mode": mode,
            "exercise_id": f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}",
            "answer_payload": _answer_for(item, nxt["round"], nxt["mode"]), "resubmit": True,
        },
    )
    assert again.status_code == 200
    assert again.json()["forge"]["answered"] == 1


def test_forge_state_endpoint_reports_rung_stage_and_next_due(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    _submit(client, headers, data["session_id"], nxt, _answer_for(_item(data, nxt), nxt["round"], nxt["mode"]))
    state = client.get(f"/api/v1/atelier/forge/state?concept_id={neg.id}", headers=headers)
    assert state.status_code == 200
    rule = state.json()["rules"][0]
    assert rule["concept_id"] == neg.id
    assert rule["rung_name"] in {"discriminate", "build"}
    assert rule["stage"] == "practising" and rule["next_due"]


def test_test_out_fail_through_the_api_places_the_rule_on_the_failed_rung(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    tense = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_TENSE_001").one()
    started = client.post("/api/v1/atelier/forge/test-out", headers=headers, json={"concept_id": tense.id})
    assert started.status_code == 201, started.text
    data = started.json()
    assert data["status"] == "test_out"
    assert data["forge"]["mode"] == "test_out" and data["forge"]["length"] == 5
    # Test-outs never hijack the day's séance.
    assert client.get("/api/v1/atelier/sessions/active", headers=headers).json()["session"] is None
    nxt = data["forge"]["next"]
    rungs = []
    body = {}
    while nxt is not None:
        rungs.append(nxt["rung"])
        item = _item(data, nxt)
        # Right on recognise, wrong from discriminate on.
        answer = _answer_for(item, nxt["round"], nxt["mode"]) if nxt["rung"] == 0 else _wrong_for(item, nxt["round"], nxt["mode"])
        body = _submit(client, headers, data["session_id"], nxt, answer).json()
        nxt = body["forge"]["next"]
    assert rungs == [0, 1, 2, 3, 5]
    result = body["forge"]["result"]
    assert result["passed"] is False and result["placement_rung"] == Rung.DISCRIMINATE
    progress = db_session.query(UserGrammarProgress).filter(UserGrammarProgress.concept_id == tense.id).one()
    db_session.refresh(progress)
    assert progress.forge_rung == Rung.DISCRIMINATE
    assert progress.tested_out_at is None and progress.held_at is None
    session = db_session.get(AtelierSession, UUID(data["session_id"]))
    db_session.refresh(session)
    assert session.status == "test_out_done"


def test_test_out_pass_holds_the_rule_at_once(db_session):
    """Driven through the service with checked verdicts (WP-S1 grades production)."""

    _prime_core_exercise_sets(db_session)
    user = _user(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    service = ForgeService(db_session)
    session = service.start_test_out(user=user, concept_id=concept.id)
    answered = 0
    while (nxt := service.next_item(user=user, session=session)) is not None:
        attempt = AtelierAttempt(
            atelier_session_id=session.id,
            user_id=user.id,
            concept_id=concept.id,
            round=nxt["round"],
            mode="rewrite" if nxt["round"] == "transform" else nxt["mode"],
            exercise_id=f"to:{nxt['item_id']}",
            prompt_payload={"items": [{"id": nxt["item_id"]}]},
            answer_payload={"answers": {nxt["item_id"]: "x"}} if nxt["round"] in {"recognize", "transform"} else {"text": "x"},
            correction_payload={"checked": True},
            verdict="incorrect" if answered == 1 else "correct",  # one miss, production right
            score_0_4=4.0,
        )
        db_session.add(attempt)
        db_session.flush()
        service.observe_attempt(user=user, session=session, attempt=attempt)
        answered += 1
    assert answered == 5
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.concept_id == concept.id, UserGrammarProgress.user_id == user.id)
        .one()
    )
    assert progress.tested_out_at is not None and progress.held_at is not None
    assert concept_stage(progress) == "held"
    assert progress.forge_rung == Rung.FREE_USE
    assert forge_state_of(session).evidence_written == 5


def test_unchecked_answers_never_count(db_session):
    attempt = AtelierAttempt(
        round="sentence", mode="sentence", verdict="accepted", score_0_4=3.0,
        correction_payload={"correction_debug": {"fallback_used": True}}, answer_payload={"text": "x"},
    )
    assert verdict_from_attempt(attempt).checked is False
    attempt.correction_payload = {"checked": True}
    assert verdict_from_attempt(attempt).checked is True and verdict_from_attempt(attempt).correct
    attempt.round, attempt.correction_payload = "recognize", {"assessment_status": "unavailable"}
    assert verdict_from_attempt(attempt).checked is False


def test_default_composer_seats_the_journeys_rule_of_the_day_and_its_contrast_partner(db_session):
    _prime_core_exercise_sets(db_session)
    user = _user(db_session)
    concepts = db_session.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).order_by(GrammarConcept.id).limit(3).all()
    today, partner, other = concepts
    now = datetime.now(UTC)
    refs = dict(today.source_refs or {})
    refs["contrast_partners"] = [partner.external_id]
    today.source_refs = refs
    db_session.add_all([
        UserGrammarProgress(user_id=user.id, concept_id=today.id, score=0, reps=1, state="neu", introduced_at=now),
        UserGrammarProgress(user_id=user.id, concept_id=partner.id, score=6, reps=3, state="neu",
                            introduced_at=now - timedelta(days=20), next_review=now + timedelta(days=5)),
    ])
    db_session.commit()

    class _Sel:
        def __init__(self, concept, role):
            self.concept, self.role = concept, role

    picked = SelectTodayComposer(db_session, selections=[_Sel(other, "new")]).pick(user, now=now)
    roles = {unit.concept_id: unit.role for unit in picked}
    assert roles[today.id] == Role.TODAY.value
    assert roles[partner.id] == Role.CONTRAST.value
    assert picked[0] == PickedUnit(today.id, Role.TODAY.value)


def test_payload_item_provider_never_serves_an_excluded_item_and_falls_back_downwards():
    payload = {
        "recognize": {"fill": {"items": [{"id": "f1"}, {"id": "f2"}]}, "classify": {"items": []}, "word_bank": {"items": [{"id": "w1"}]}},
        "transform": {"items": [{"id": "t1"}]},
        "output_ladder": {"sentence": {"items": [{"id": "s1"}]}, "conversation": {"items": [{"id": "c1"}]}},
    }
    provider = PayloadItemProvider({1: payload})
    item = provider.item_for(concept_id=1, rung=Rung.RECOGNISE, exclude=set())
    assert item.item_id == "f1"
    item2 = provider.item_for(concept_id=1, rung=Rung.RECOGNISE, exclude={item.fingerprint})
    assert item2.item_id == "f2"
    # No classify item: discriminate falls back to recognise, never up.
    fallback = provider.item_for(concept_id=1, rung=Rung.DISCRIMINATE, exclude=set())
    assert fallback.rung == Rung.RECOGNISE
    assert provider.item_for(concept_id=1, rung=Rung.FREE_USE, exclude=set()).round == "conversation"
    assert provider.item_for(concept_id=2, rung=0, exclude=set()) is None


def test_test_out_is_available_for_any_rule_from_day_one(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    cond = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_B1_COND_001").one()
    response = client.post("/api/v1/atelier/forge/test-out", headers=headers, json={"concept_id": cond.id})
    assert response.status_code == 201
    missing = client.post("/api/v1/atelier/forge/test-out", headers=headers, json={"concept_id": 999999})
    assert missing.status_code == 404
