"""WP-S2 · La Forge's item bank: variety without waiting.

Acceptance (docs/implementation/atelier-v2/WORK-PACKAGES-2026-09-24-seance.md, WP-S2):

* every A1–A2 unit yields ≥ 200 distinct valid items per rung type it
  supports — the payloads pass the séance's own validators, each item's
  answer passes the unit's detector, and no prompt shows its own answer;
* a 10-session simulation for one learner never reuses a sentence within
  7 days (and the rule card's example is never an exercise);
* the séance start calls no LLM (the bank renders in-process);
* v1 and v2 catalogues both work;
* vetted LLM sets are shared by (unit, band) across learners.
"""
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models.atelier import AtelierExerciseSet, AtelierServedItem, AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services import item_bank as ib
from app.services.atelier import (
    ATELIER_GENERATOR_VERSION,
    AtelierExerciseGenerator,
    AtelierPoolService,
    AtelierScheduler,
    _latest_valid_shared_llm_exercise_set,
    item_bank_exercise_set,
    session_exercise_set,
    shared_pool_sets,
)
from app.services.grammar_catalog import FrenchCoreGrammarCatalog, load_v1_to_v2_mapping

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENT = {"concept_id": 1, "external_id": "X", "label": "X", "target_count": 1}
MIN_ITEMS = 200


def _a1_a2_units() -> list[str]:
    with (ROOT / "templates" / "french_core_grammar_v2.tsv").open(encoding="utf-8") as handle:
        return [row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in {"A1", "A2"}]


# --------------------------------------------------------------------------- #
# Coverage: every A1–A2 unit, ≥ 200 distinct valid items per rung
# --------------------------------------------------------------------------- #


def test_every_a1_a2_unit_has_templates() -> None:
    units = _a1_a2_units()
    assert len(units) >= 60
    missing = [unit for unit in units if unit not in ib.template_units()]
    assert not missing, missing


def test_every_v1_a1_a2_concept_is_served_through_the_mapping() -> None:
    with (ROOT / "templates" / "french_core_grammar_v1.tsv").open(encoding="utf-8") as handle:
        v1 = [row["external_id"] for row in csv.DictReader(handle, delimiter="\t") if row["cefr_level"] in {"A1", "A2"}]
    mapping = load_v1_to_v2_mapping()
    unserved = [external_id for external_id in v1 if not ib.units_for_external_id(external_id)]
    # A v1 concept is unserved only when every v2 unit replacing it is above A2.
    for external_id in unserved:
        levels = {ib.unit_row(unit).get("level") for unit in mapping.get(external_id, [])}
        assert levels and levels <= {"B1", "B2"}, (external_id, levels)
    assert len(unserved) <= 2


def _chunks(values: list, size: int = 3) -> list[list]:
    return [values[index:index + size] for index in range(0, len(values) - size + 1, size)]


@pytest.mark.parametrize("unit", _a1_a2_units())
def test_unit_yields_200_distinct_valid_items_per_rung(unit: str) -> None:
    bank = ib.default_bank()
    detector = ib.unit_detector(unit)
    items = bank.generate(unit, MIN_ITEMS + 40, seed=f"acceptance:{unit}", detector=detector)
    assert len(items) >= MIN_ITEMS, f"{unit}: only {len(items)} distinct sentences"

    by_rung: dict[str, list[dict]] = {rung: [] for rung in ib.RUNG_TYPES}
    for index, item in enumerate(items):
        # The answer key: the rule-carrying span sits in the sentence, the
        # sentence is an accepted answer, and every trap differs from it.
        assert item.target and item.target in item.sentence, item
        assert item.sentence in item.accepted
        assert all(ib.normalize(trap) != ib.normalize(item.target) for trap in item.traps)
        if detector is not None:
            assert detector(item.sentence), (unit, item.sentence)
        for rung in ib.RUNG_TYPES:
            payload_item = ib.rung_item(rung, item, index=index, requirement=REQUIREMENT)
            if payload_item is None:
                continue
            assert not ib.spoils(rung, payload_item), (unit, rung, payload_item)
            by_rung[rung].append(payload_item)

    # The séance's own payload validator, three items per mode at a time.
    produce = ib.produce_block(items[0], items[1], requirement=REQUIREMENT)
    chunks = {rung: _chunks(values) for rung, values in by_rung.items()}
    rounds = max(len(values) for values in chunks.values())
    for index in range(rounds):
        def pick(rung: str, index: int = index) -> list:
            values = chunks[rung]
            return values[index] if index < len(values) else values[0]

        output = pick("production")
        for classify in (pick("classify"), pick("pair")):
            payload = {
                "recognize": {
                    "fill": {"items": pick("fill")},
                    "word_bank": {"items": pick("word_bank")},
                    "classify": {"items": classify},
                },
                "transform": {"items": pick("transform")},
                "produce": produce,
                "output_ladder": {
                    name: {"items": [output[slot]]} for slot, name in enumerate(("sentence", "speak", "conversation"))
                },
            }
            errors = AtelierExerciseGenerator._payload_validation_errors(payload)
            assert not errors, (unit, errors[:3])

    def distinct(rung: str) -> int:
        keys = {"prompt", "choices", "labels", "source", "tokens", "meaning_cue", "example_answer"}
        return len(
            {json.dumps({k: v for k, v in entry.items() if k in keys}, ensure_ascii=False, sort_keys=True) for entry in by_rung[rung]}
        )

    short = {rung: distinct(rung) for rung in ib.RUNG_TYPES if distinct(rung) < MIN_ITEMS}
    assert not short, f"{unit}: fewer than {MIN_ITEMS} distinct valid items for {short}"


def test_items_never_show_their_answer() -> None:
    item = ib.default_bank().generate("FR2_A11_LE_LA", 1, seed="spoil")[0]
    fill = ib.rung_item("fill", item)
    assert "___" in fill["prompt"]
    assert not ib.contains_phrase(fill["prompt"].replace("___", " "), fill["correct_answer"])
    repair = ib.rung_item("transform", item)
    assert ib.normalize(repair["source"]) != ib.normalize(repair["expected_answer"])
    assert repair["expected_answer"] not in repair["instruction"]


def test_gloss_units_carry_the_meaning_in_every_prompt() -> None:
    item = ib.default_bank().generate("FR2_A12_CONNECTORS", 1, seed="gloss")[0]
    assert item.gloss
    assert item.en in ib.rung_item("fill", item)["prompt"]
    assert item.en in ib.rung_item("transform", item)["instruction"]


# --------------------------------------------------------------------------- #
# Séance integration
# --------------------------------------------------------------------------- #


def _user(db_session, *, cefr: str = "A1.1") -> User:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test", target_language="fr", cefr_estimate=cefr)
    db_session.add(user)
    db_session.commit()
    return user


def _session(db_session, user: User, concepts: list[GrammarConcept]) -> AtelierSession:
    session = AtelierSession(
        user_id=user.id,
        selected_concept_ids=[concept.id for concept in concepts],
        quote_payload={},
        status="in_progress",
        recap_payload={},
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session


def _v1(db_session, external_id: str) -> GrammarConcept:
    AtelierScheduler(db_session).ensure_catalog()
    return db_session.query(GrammarConcept).filter(GrammarConcept.external_id == external_id).one()


@pytest.fixture()
def no_llm(monkeypatch):
    calls: list[str] = []

    def refuse(self, concept, **kwargs):  # noqa: ANN001
        calls.append(str(concept.external_id))
        raise AssertionError("La Forge must not call an LLM at séance start")

    monkeypatch.setattr(AtelierExerciseGenerator, "_generate_with_llm", refuse)
    return calls


def test_seance_set_comes_from_the_bank_without_an_llm(db_session, no_llm) -> None:
    concept = _v1(db_session, "FR_A1_NOUN_001")
    user = _user(db_session)
    session = _session(db_session, user, [concept])

    exercise_set = session_exercise_set(db_session, user=user, session=session, concept=concept, fast_path=True)

    assert exercise_set.source == "template"
    assert no_llm == []
    assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)
    forge = exercise_set.payload["forge"]
    assert set(forge["units"]) == {"FR2_A11_UN_UNE", "FR2_A11_ADJ_AGREEMENT"}
    assert len(forge["fingerprints"]) == ib.ITEMS_PER_SET
    served = db_session.query(AtelierServedItem).filter(AtelierServedItem.user_id == user.id).count()
    assert served == ib.ITEMS_PER_SET
    # Answer keys ride along for local grading (WP-S1).
    fill = exercise_set.payload["recognize"]["fill"]["items"][0]
    assert fill["target_span"] == fill["correct_answer"]
    assert fill["accepted_answers"]
    repair = exercise_set.payload["transform"]["items"][0]
    assert repair["expected_answer"] in repair["accepted_answers"]
    # The stored set is what grading reads back.
    again = session_exercise_set(db_session, user=user, session=session, concept=concept)
    assert again.id == exercise_set.id


def test_seance_start_api_serves_bank_sets_and_calls_no_llm(client: TestClient, db_session, no_llm) -> None:
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "forge-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "forge-secure"}).json()["access_token"]
    AtelierScheduler(db_session).ensure_catalog()

    response = client.post("/api/v1/atelier/sessions", json={}, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 201, response.text
    body = response.json()
    sources = {item["source"] for item in body["exercise_sets"]}
    assert "template" in sources
    assert no_llm == []
    for exercise_set in body["exercise_sets"]:
        if exercise_set["source"] == "template":
            assert exercise_set["payload"]["forge"]["source"] == "item_bank"


def test_rule_card_example_is_never_an_exercise(db_session) -> None:
    concept = _v1(db_session, "FR_A1_ART_001")
    user = _user(db_session)
    session = _session(db_session, user, [concept])
    exercise_set = item_bank_exercise_set(db_session, user=user, session=session, concept=concept)
    assert exercise_set is not None
    panel = exercise_set.payload["rule_panel"]
    card = {ib.fingerprint(sentence) for sentence in [*panel.get("examples", []), exercise_set.payload["xray"]["sentence"]]}
    assert not card & set(exercise_set.payload["forge"]["fingerprints"])


def test_ten_sessions_never_reuse_a_sentence_within_seven_days(db_session, no_llm) -> None:
    """One learner, ten séances on ten days, the same two concepts every time."""

    concepts = [_v1(db_session, "FR_A1_NOUN_001"), _v1(db_session, "FR_A1_NEG_001")]
    user = _user(db_session)
    served_on: dict[str, list[int]] = {}
    session_days: list[tuple[object, int]] = []
    for day in range(10):
        session = _session(db_session, user, concepts)
        session_days.append((session.id, day))
        for concept in concepts:
            exercise_set = item_bank_exercise_set(db_session, user=user, session=session, concept=concept)
            assert exercise_set is not None, (day, concept.external_id)
            for value in exercise_set.payload["forge"]["fingerprints"]:
                served_on.setdefault(value, []).append(day)
        # Move the clock one day: a row served on day d is now (day + 1 - d) days old.
        now = datetime.now(UTC)
        for session_id, served_day in session_days:
            db_session.query(AtelierServedItem).filter(AtelierServedItem.atelier_session_id == session_id).update(
                {AtelierServedItem.served_at: now - timedelta(days=day + 1 - served_day)}, synchronize_session=False
            )
        db_session.commit()
    repeats = {value: days for value, days in served_on.items() if len(days) > 1}
    too_soon = {value: days for value, days in repeats.items() if min(b - a for a, b in zip(days, days[1:], strict=False)) < 7}
    assert not too_soon, too_soon
    assert len(served_on) > 10 * ib.ITEMS_PER_SET
    assert no_llm == []


def test_v2_catalogue_concepts_are_served_by_their_own_templates(db_session, monkeypatch, no_llm) -> None:
    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    try:
        concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_A21_PC_ETRE").one()
        user = _user(db_session, cefr="A2.1")
        session = _session(db_session, user, [concept])
        exercise_set = session_exercise_set(db_session, user=user, session=session, concept=concept, fast_path=True)
        assert exercise_set.source == "template"
        assert exercise_set.payload["forge"]["units"] == ["FR2_A21_PC_ETRE"]
        assert AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)
        detector = ib.unit_detector("FR2_A21_PC_ETRE")
        for item in exercise_set.payload["transform"]["items"]:
            assert detector(item["expected_answer"])
    finally:
        FrenchCoreGrammarCatalog(db_session, "v1").ensure_catalog()


def test_concepts_without_templates_keep_the_old_path(db_session, monkeypatch) -> None:
    concept = _v1(db_session, "FR_B1_COND_001")
    user = _user(db_session)
    session = _session(db_session, user, [concept])
    assert item_bank_exercise_set(db_session, user=user, session=session, concept=concept) is None
    exercise_set = session_exercise_set(db_session, user=user, session=session, concept=concept, fast_path=True)
    assert exercise_set.source != "template"


def test_bank_can_be_switched_off(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "ATELIER_ITEM_BANK_ENABLED", False)
    concept = _v1(db_session, "FR_A1_ART_002")
    user = _user(db_session)
    session = _session(db_session, user, [concept])
    assert item_bank_exercise_set(db_session, user=user, session=session, concept=concept) is None


# --------------------------------------------------------------------------- #
# Shared LLM pools by (unit, band)
# --------------------------------------------------------------------------- #


def _pool_payload(db_session, concept: GrammarConcept) -> dict:
    generator = AtelierExerciseGenerator(db_session)
    payload = generator._fallback_payload(concept)
    for index, name in enumerate(("sentence", "speak", "conversation")):
        item = payload["output_ladder"][name]["items"][0]
        item["example_answer"] = f"Au Mistral, Margaux demande une table numéro {index} pour {concept.id}."
    payload["produce"]["source_fragment"] = f"Romy écrit un message au Mistral pour {concept.id}."
    return payload


def test_pool_service_generates_shared_sets_per_band(db_session, monkeypatch) -> None:
    concept = _v1(db_session, "FR_A1_ART_002")
    db_session.query(AtelierExerciseSet).filter(AtelierExerciseSet.concept_id == concept.id).delete()
    db_session.commit()
    counter = {"n": 0}

    def fake_generate(self, target, **kwargs):  # noqa: ANN001
        counter["n"] += 1
        assert kwargs.get("user") is None and kwargs.get("session_id") is None
        payload = _pool_payload(db_session, target)
        payload["produce"]["source_fragment"] += f" ({counter['n']})"
        return payload, "fake-model", "Gated in test."

    monkeypatch.setattr(AtelierExerciseGenerator, "_generate_with_llm", fake_generate)
    report = AtelierPoolService(db_session).pregenerate(concepts=[concept], bands=("A1", "A2"), per_band=2)

    assert report["created"] == 4
    pool = db_session.query(AtelierExerciseSet).filter(AtelierExerciseSet.concept_id == concept.id).all()
    assert {item.source for item in pool} == {"llm"}
    assert sorted(item.pool_band for item in pool) == ["A1", "A1", "A2", "A2"]
    # The shared fast path now finds them — the band's own set first.
    assert _latest_valid_shared_llm_exercise_set(db_session, concept, band="A2").pool_band == "A2"
    assert [item.pool_band for item in shared_pool_sets(db_session, concept, band="A1")][:2] == ["A1", "A1"]
    # Idempotent: a full pool plans nothing.
    again = AtelierPoolService(db_session).pregenerate(concepts=[concept], bands=("A1", "A2"), per_band=2, dry_run=True)
    assert again["planned"] == 0


def test_bank_uses_the_shared_pool_for_production_prompts_across_learners(db_session, no_llm) -> None:
    concept = _v1(db_session, "FR_A1_ART_002")
    db_session.query(AtelierExerciseSet).filter(AtelierExerciseSet.concept_id == concept.id).delete()
    db_session.commit()
    pool_set = AtelierExerciseSet(
        concept_id=concept.id,
        generator_version=ATELIER_GENERATOR_VERSION,
        model="fake-model",
        source="llm",
        content_hash=f"pool-{uuid4()}",
        payload=_pool_payload(db_session, concept),
        validation_notes="shared pool",
        pool_band="A1",
    )
    private = AtelierExerciseSet(
        concept_id=concept.id,
        generator_version=ATELIER_GENERATOR_VERSION,
        model="fake-model",
        source="llm_user",
        content_hash=f"private-{uuid4()}",
        payload=_pool_payload(db_session, concept),
        validation_notes="personalised",
    )
    db_session.add_all([pool_set, private])
    db_session.commit()

    first, second = _user(db_session), _user(db_session)
    sets = []
    for learner in (first, second):
        session = _session(db_session, learner, [concept])
        exercise_set = item_bank_exercise_set(db_session, user=learner, session=session, concept=concept)
        sets.append(exercise_set)
        assert exercise_set.payload["forge"]["pool_set_id"] == str(pool_set.id)
        assert exercise_set.payload["output_ladder"] == pool_set.payload["output_ladder"]
        db_session.refresh(session)
        assert session.quote_payload["pool_set_ids"][str(concept.id)] == str(pool_set.id)
    # Shared across learners, never the personalised set.
    assert sets[0].payload["forge"]["pool_set_id"] == sets[1].payload["forge"]["pool_set_id"]
    # The same learner does not get the pool's prompts again inside 7 days.
    session = _session(db_session, first, [concept])
    third = item_bank_exercise_set(db_session, user=first, session=session, concept=concept)
    assert third.payload["forge"]["pool_set_id"] is None
    assert no_llm == []
