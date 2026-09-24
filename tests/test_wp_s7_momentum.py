"""WP-S7 — momentum and fun, inside the design language.

* the combo counts checked right answers only (S1 semantics) and resets on a
  checked error; the séance recap carries the best run and a pilot event;
* the grammar map endpoint draws every rule in one of four stages;
* Éclair: unlocked by two introduced contrasting rules, graded by the stored
  keys, evidence at the discriminate rung with the forge's caps, best score per
  pair kept;
* the Seal's rings: rules held on the journey's local day; a rare token for a
  passed test-out; pilot events for test-out starts and passes.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.core import forge as core
from app.core.forge import Rung
from app.core.srs.memory import EvidenceFormat
from app.db.models.atelier import AtelierAttempt, AtelierCollectible
from app.db.models.grammar import GrammarConcept, UserGrammarProgress
from app.db.models.pilot_event import PilotEvent
from app.db.models.user import User
from app.services.eclair import (
    ECLAIR_DONE_STATUS,
    EclairUnavailable,
    eclair_pairs,
    finish_round,
    grade_answers,
    pair_key,
    parse_pair_key,
    round_for_user,
    start_round,
)
from app.services.forge import ForgeService
from app.services.grammar_map import map_stage
from app.services.seals import mastery_today_for
from tests.test_atelier import _prime_core_exercise_sets, _token, _user
from tests.test_wp_s3_forge import _answer_for, _item, _submit, _wrong_for


def _entry(position: int, outcome: str, checked: bool = True) -> dict:
    return {"position": position, "outcome": outcome, "checked": checked}


# ---------------------------------------------------------------------------
# The combo
# ---------------------------------------------------------------------------


def test_combo_counts_checked_right_answers_and_ignores_unchecked_ones():
    right, wrong = core.OUTCOME_CORRECT, core.OUTCOME_INCORRECT
    history = [
        _entry(0, right),
        _entry(1, right, checked=False),  # unchecked: neither extends nor breaks
        _entry(2, right),
        _entry(3, wrong, checked=False),  # a provisional miss never resets
        _entry(4, right),
    ]
    assert core.combo_runs(history) == (3, 3)


def test_combo_resets_only_on_a_checked_error_and_keeps_the_best():
    right, wrong, partial = core.OUTCOME_CORRECT, core.OUTCOME_INCORRECT, core.OUTCOME_PARTIAL
    history = [_entry(0, right), _entry(1, right), _entry(2, right), _entry(3, wrong), _entry(4, right)]
    assert core.combo_runs(history) == (1, 3)
    assert core.combo_runs([_entry(0, right), _entry(1, partial)]) == (0, 1)
    assert core.combo_runs([]) == (0, 0)
    # Order is the answer order, whatever order the ledger was stored in.
    assert core.combo_runs(list(reversed(history))) == (1, 3)


def test_a_seance_view_carries_the_combo_and_the_recap_its_best_run(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    forge = data["forge"]
    assert forge["combo"] == {"run": 0, "best": 0}
    assert forge["features"] == {"combo": True, "eclair": True, "grammar_map": True, "mastery_rewards": True}
    nxt = forge["next"]
    runs = []
    for index in range(3):
        item = _item(data, nxt)
        answer = _wrong_for(item, nxt["round"], nxt["mode"]) if index == 2 else _answer_for(item, nxt["round"], nxt["mode"])
        body = _submit(client, headers, data["session_id"], nxt, answer).json()
        runs.append(body["forge"]["combo"]["run"])
        nxt = body["forge"]["next"]
        if nxt is None:
            break
    assert runs[:2] == [1, 2]
    if len(runs) == 3:
        assert runs[2] == 0
    done = client.post(f"/api/v1/atelier/sessions/{data['session_id']}/complete", headers=headers)
    assert done.status_code == 200
    assert done.json()["recap"]["forge"]["best_combo"] == 2
    event = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == "forge_combo", PilotEvent.entity_id == data["session_id"])
        .one()
    )
    assert event.payload["best"] == 2


# ---------------------------------------------------------------------------
# The grammar map
# ---------------------------------------------------------------------------


def test_map_stage_draws_four_states():
    now = datetime.now(UTC)
    assert map_stage(None) == "ghost"
    assert map_stage(SimpleNamespace(held_at=None, introduced_at=None, reps=0, forge_rung=None,
                                     free_use_first_at=None, free_use_last_at=None, spaced_success_at=None,
                                     stability=0.0)) == "ghost"
    introduced = SimpleNamespace(held_at=None, introduced_at=now, reps=1, forge_rung=2, free_use_first_at=None,
                                 free_use_last_at=None, spaced_success_at=None, stability=0.0)
    assert map_stage(introduced) == "introduced"
    introduced.forge_rung = int(Rung.PRODUCE)
    assert map_stage(introduced) == "proficient"
    introduced.held_at = now
    assert map_stage(introduced) == "held"


def test_map_endpoint_returns_every_rule_with_its_stage(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    user = db_session.get(User, UUID(client.get("/api/v1/users/me", headers=headers).json()["id"]))
    concepts = (
        db_session.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).order_by(GrammarConcept.id).limit(3).all()
    )
    now = datetime.now(UTC)
    introduced, proficient, held = concepts
    db_session.add_all([
        UserGrammarProgress(user_id=user.id, concept_id=introduced.id, reps=1, introduced_at=now, forge_rung=1),
        UserGrammarProgress(user_id=user.id, concept_id=proficient.id, reps=4, introduced_at=now, forge_rung=4),
        UserGrammarProgress(user_id=user.id, concept_id=held.id, reps=6, introduced_at=now, forge_rung=5,
                            held_at=now, tested_out_at=now),
    ])
    db_session.commit()

    response = client.get("/api/v1/atelier/forge/map", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    rules = {rule["concept_id"]: rule for band in body["bands"] for rule in band["rules"]}
    assert rules[introduced.id]["stage"] == "introduced"
    assert rules[proficient.id]["stage"] == "proficient"
    assert rules[held.id]["stage"] == "held" and rules[held.id]["tested_out"] is True
    assert {rule["stage"] for rule in rules.values()} == {"ghost", "introduced", "proficient", "held"}
    assert body["counts"]["held"] == 1 and body["total"] == len(rules)
    assert all(band["band"][:2] in {"A1", "A2", "B1", "B2", "C1", "C2"} for band in body["bands"])
    assert body["features"]["grammar_map"] is True

    opened = client.post("/api/v1/atelier/forge/map/opened", headers=headers)
    assert opened.status_code == 204
    assert db_session.query(PilotEvent).filter(
        PilotEvent.event_type == "grammar_map_opened", PilotEvent.user_id == user.id
    ).count() == 1


def test_map_endpoint_is_off_behind_its_flag(client: TestClient, monkeypatch):
    token = _token(client)
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_MAP_ENABLED", False)
    response = client.get("/api/v1/atelier/forge/map", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Éclair
# ---------------------------------------------------------------------------


@contextmanager
def _contrasting_pair(db_session):
    """FR_A1_ART_001 (le/la) and FR_A1_ART_002 (un/une) as contrast partners."""

    _prime_core_exercise_sets(db_session)
    first = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A1_ART_001").one()
    second = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A1_ART_002").one()
    before = dict(first.source_refs or {})
    first.source_refs = {**before, "contrast_partners": [second.external_id]}
    db_session.add(first)
    db_session.commit()
    try:
        yield first, second
    finally:
        first.source_refs = before
        db_session.add(first)
        db_session.commit()


def _introduce(db_session, user, *concepts):
    now = datetime.now(UTC) - timedelta(days=3)
    for concept in concepts:
        db_session.add(UserGrammarProgress(user_id=user.id, concept_id=concept.id, reps=1, introduced_at=now,
                                           next_review=now + timedelta(days=1)))
    db_session.commit()


def test_pair_keys_are_order_free():
    assert pair_key(9, 4) == "4-9" == pair_key(4, 9)
    assert parse_pair_key("9-4") == (4, 9)
    assert parse_pair_key("4-4") is None and parse_pair_key("x") is None


def test_eclair_unlocks_only_with_two_introduced_contrasting_rules(db_session):
    with _contrasting_pair(db_session) as (first, second):
        user = _user(db_session)
        assert eclair_pairs(db_session, user) == []
        _introduce(db_session, user, first)
        assert eclair_pairs(db_session, user) == []  # one rule is not a pair
        with pytest.raises(EclairUnavailable):
            start_round(db_session, user=user)
        _introduce(db_session, user, second)
        pairs = eclair_pairs(db_session, user)
        assert [row["pair"] for row in pairs] == [pair_key(first.id, second.id)]
        assert pairs[0]["best"] == 0 and pairs[0]["plays"] == 0


def test_eclair_round_grades_by_key_writes_capped_discriminate_evidence_and_keeps_the_best(db_session):
    with _contrasting_pair(db_session) as (first, second):
        user = _user(db_session)
        _introduce(db_session, user, first, second)
        started = start_round(db_session, user=user, concept_id=first.id)
        assert started["seconds"] == 60
        items = started["items"]
        assert len(items) >= 10
        assert {item["concept_id"] for item in items} == {first.id, second.id}
        assert all(len(item["labels"]) == 2 and item["correct_answer"] in item["labels"] for item in items)
        # Never three of one rule in a row.
        ids = [item["concept_id"] for item in items]
        assert not any(ids[i] == ids[i + 1] == ids[i + 2] for i in range(len(ids) - 2))

        reps_before = {
            row.concept_id: row.reps
            for row in db_session.query(UserGrammarProgress).filter(UserGrammarProgress.user_id == user.id)
        }
        # Eight answers: six right, two wrong (one per rule), plus junk.
        answers = []
        wrong_done: set[int] = set()
        for item in items[:8]:
            if item["concept_id"] not in wrong_done and len(answers) >= 2:
                wrong_done.add(item["concept_id"])
                other = next(label for label in item["labels"] if label != item["correct_answer"])
                answers.append({"id": item["id"], "answer": other})
            else:
                answers.append({"id": item["id"], "answer": item["correct_answer"]})
        answers.append({"id": "not-an-item", "answer": "x"})
        answers.append({"id": items[0]["id"], "answer": "again"})  # a second answer is ignored

        session = round_for_user(db_session, user=user, eclair_id=UUID(started["eclair_id"]))
        result = finish_round(db_session, user=user, session=session, answers=answers, elapsed_ms=60_000)
        assert result["answered"] == 8
        assert result["score"] == 8 - len(wrong_done) == 6
        assert result["best"] == 6 and result["new_best"] is True
        assert result["evidence_written"] == 8
        # The forge's caps: per rule, the first success and the first failure move the schedule.
        assert result["schedule_moves"] == 4
        db_session.refresh(session)
        assert session.status == ECLAIR_DONE_STATUS
        ledger = session.recap_payload["evidence"]
        assert {entry["format"] for entry in ledger} == {EvidenceFormat.RECOGNISE.value}
        assert all(entry["rung"] == Rung.DISCRIMINATE for entry in ledger)
        for concept in (first, second):
            row = (
                db_session.query(UserGrammarProgress)
                .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
                .one()
            )
            db_session.refresh(row)
            assert row.reps - reps_before[concept.id] == 2  # one success + one failure moved it
            assert row.forge_rung is None  # an Éclair never moves the staircase

        # A second round of the same pair today: graded, kept as a play, but it folds.
        again = start_round(db_session, user=user, pair=started["pair"])
        second_session = round_for_user(db_session, user=user, eclair_id=UUID(again["eclair_id"]))
        low = finish_round(
            db_session, user=user, session=second_session,
            answers=[{"id": item["id"], "answer": item["correct_answer"]} for item in again["items"][:3]],
        )
        assert low["score"] == 3 and low["best"] == 6 and low["new_best"] is False
        assert low["schedule_moves"] == 0 and low["evidence_written"] == 3
        pairs = eclair_pairs(db_session, user)
        assert pairs[0]["best"] == 6 and pairs[0]["plays"] == 2
        # Filing twice changes nothing.
        assert finish_round(db_session, user=user, session=second_session, answers=[])["score"] == 3
        events = db_session.query(PilotEvent).filter(
            PilotEvent.user_id == user.id, PilotEvent.event_type.in_(["eclair_started", "eclair_finished"])
        ).all()
        assert sorted(event.event_type for event in events) == ["eclair_finished"] * 2 + ["eclair_started"] * 2


def test_eclair_api_refuses_a_locked_pair_and_files_a_round(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    locked = client.post("/api/v1/atelier/forge/eclair", headers=headers, json={"pair": "1-2"})
    assert locked.status_code == 409
    with _contrasting_pair(db_session) as (first, second):
        user = db_session.get(User, UUID(client.get("/api/v1/users/me", headers=headers).json()["id"]))
        _introduce(db_session, user, first, second)
        body = client.get("/api/v1/atelier/forge/map", headers=headers).json()
        assert body["eclair"]["unlocked"] is True
        started = client.post("/api/v1/atelier/forge/eclair", headers=headers, json={"pair": pair_key(first.id, second.id)})
        assert started.status_code == 201, started.text
        data = started.json()
        filed = client.post(
            f"/api/v1/atelier/forge/eclair/{data['eclair_id']}/finish",
            headers=headers,
            json={"answers": [{"id": item["id"], "answer": item["correct_answer"]} for item in data["items"][:5]],
                  "elapsed_ms": 60000},
        )
        assert filed.status_code == 200, filed.text
        assert filed.json()["score"] == 5
        # Éclair rounds never read as the day's séance.
        assert client.get("/api/v1/atelier/sessions/active", headers=headers).json()["session"] is None


def test_eclair_is_off_behind_its_flag(db_session, monkeypatch):
    with _contrasting_pair(db_session) as (first, second):
        user = _user(db_session)
        _introduce(db_session, user, first, second)
        monkeypatch.setattr(settings, "ATELIER_ECLAIR_ENABLED", False)
        with pytest.raises(EclairUnavailable):
            start_round(db_session, user=user)


def test_grade_answers_folds_typography():
    items = [{"id": "a", "concept_id": 1, "correct_answer": "J’aime le café."}]
    assert grade_answers(items, [{"id": "a", "answer": "J'aime le café"}])[0]["correct"] is True


# ---------------------------------------------------------------------------
# Rewards tied to mastery
# ---------------------------------------------------------------------------


def _journey(user_id, day, tz="Europe/Berlin"):
    return SimpleNamespace(user_id=user_id, local_date=day, timezone=tz)


def test_the_seal_gets_a_ring_for_each_rule_held_on_the_journeys_local_day(db_session):
    _prime_core_exercise_sets(db_session)
    user = _user(db_session)
    concepts = db_session.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).order_by(GrammarConcept.id).limit(4).all()
    # 23:30 in Berlin on 24 Sept is 21:30 UTC: still the 24th locally.
    evening = datetime(2026, 9, 24, 21, 30, tzinfo=UTC)
    yesterday = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
    after_midnight = datetime(2026, 9, 24, 22, 30, tzinfo=UTC)  # 00:30 on the 25th in Berlin
    db_session.add_all([
        UserGrammarProgress(user_id=user.id, concept_id=concepts[0].id, reps=5, held_at=evening),
        UserGrammarProgress(user_id=user.id, concept_id=concepts[1].id, reps=5, held_at=evening, tested_out_at=evening),
        UserGrammarProgress(user_id=user.id, concept_id=concepts[2].id, reps=5, held_at=yesterday),
        UserGrammarProgress(user_id=user.id, concept_id=concepts[3].id, reps=5, held_at=after_midnight),
    ])
    db_session.commit()
    from datetime import date

    today = mastery_today_for(db_session, _journey(user.id, date(2026, 9, 24)))
    assert today == {
        "held_concept_ids": sorted([concepts[0].id, concepts[1].id]),
        "tested_out_concept_ids": [concepts[1].id],
    }
    assert mastery_today_for(db_session, _journey(user.id, date(2026, 9, 25)))["held_concept_ids"] == [concepts[3].id]


def test_the_seal_rings_are_off_behind_the_rewards_flag(db_session, monkeypatch):
    from datetime import date

    monkeypatch.setattr(settings, "ATELIER_MASTERY_REWARDS_ENABLED", False)
    assert mastery_today_for(db_session, _journey(_user(db_session).id, date(2026, 9, 24))) is None


def _pass_test_out(db_session, user, concept):
    service = ForgeService(db_session)
    session = service.start_test_out(user=user, concept_id=concept.id)
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
            verdict="correct",
            score_0_4=4.0,
        )
        db_session.add(attempt)
        db_session.flush()
        service.observe_attempt(user=user, session=session, attempt=attempt)
    db_session.refresh(session)
    return session


def test_a_passed_test_out_mints_one_rare_token_and_writes_pilot_events(db_session):
    _prime_core_exercise_sets(db_session)
    user = _user(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    session = _pass_test_out(db_session, user, concept)
    result = session.recap_payload["test_out"]
    assert result["passed"] is True
    assert result["token"]["rare"] is True and result["token"]["concept_id"] == concept.id
    tokens = db_session.query(AtelierCollectible).filter(
        AtelierCollectible.user_id == user.id, AtelierCollectible.source_kind == "test_out"
    ).all()
    assert len(tokens) == 1 and tokens[0].kind == "logo_token" and tokens[0].metadata_payload["rare"] is True
    # A second pass of the same rule mints nothing new.
    again = _pass_test_out(db_session, user, concept)
    assert "token" not in again.recap_payload["test_out"]
    assert db_session.query(AtelierCollectible).filter(
        AtelierCollectible.user_id == user.id, AtelierCollectible.source_kind == "test_out"
    ).count() == 1
    kinds = [
        (event.event_type, (event.payload or {}).get("passed"))
        for event in db_session.query(PilotEvent)
        .filter(PilotEvent.user_id == user.id, PilotEvent.event_type.like("forge_test_out_%"))
        .order_by(PilotEvent.occurred_at)
    ]
    assert kinds.count(("forge_test_out_started", None)) == 2
    assert kinds.count(("forge_test_out_finished", True)) == 2


def test_no_rare_token_with_the_rewards_flag_off(db_session, monkeypatch):
    _prime_core_exercise_sets(db_session)
    monkeypatch.setattr(settings, "ATELIER_MASTERY_REWARDS_ENABLED", False)
    user = _user(db_session)
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    session = _pass_test_out(db_session, user, concept)
    assert session.recap_payload["test_out"]["passed"] is True
    assert "token" not in session.recap_payload["test_out"]
