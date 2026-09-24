"""WP-S6 — La Forge, beauty and clarity: the payload side.

* the séance recap carries each rule's progress (the rung reached, the stage
  before and after, the next review, two proof lines) instead of a tally;
* the item bank's cues (the minimal-pair ask, the glossed repair, the
  production situation) offer a learner-language version next to the English
  one the séance already carries — the French sentences never move.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.models.grammar import GrammarConcept
from app.services import item_bank as ib
from tests.test_atelier import _prime_core_exercise_sets, _token
from tests.test_wp_s3_forge import _answer_for, _item, _submit

STAGES = {"new", "introduced", "practising", "held"}


def test_the_recap_draws_each_rules_progress(client: TestClient, db_session):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    started = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id})
    assert started.status_code == 201
    data = started.json()
    nxt = data["forge"]["next"]
    for _ in range(3):
        item = _item(data, nxt)
        response = _submit(client, headers, data["session_id"], nxt, _answer_for(item, nxt["round"], nxt["mode"]))
        assert response.status_code == 200, response.text
        nxt = response.json()["forge"]["next"]
        if nxt is None:
            break

    done = client.post(f"/api/v1/atelier/sessions/{data['session_id']}/complete", headers=headers)
    assert done.status_code == 200
    rules = done.json()["recap"]["forge"]["rules"]
    assert rules and rules[0]["concept_id"] == neg.id
    rule = rules[0]
    assert rule["rung_name"] in {"recognise", "discriminate", "build", "transform", "produce", "free_use"}
    assert rule["stage_before"] in STAGES and rule["stage"] in STAGES
    # Three right answers moved the rule: it is practised now, whatever it was.
    assert rule["stage"] in {"practising", "held"}
    assert rule["next_due"]
    assert 1 <= len(rule["proof"]) <= 2
    for line in rule["proof"]:
        assert len(line["fr"].split()) >= 2  # a whole line, never a lone article
        assert line["fixed"] is False


def test_bank_cues_offer_the_learner_language_and_keep_the_english_prompt():
    bank = ib.default_bank()
    item = bank.generate("FR2_A11_LE_LA", 1, seed="wp-s6")[0]

    pair = ib.pair_item(item)
    assert pair is not None
    assert pair["prompt_l10n"]["en"] == pair["prompt"]
    assert pair["prompt_l10n"]["de"].startswith("Welcher Satz bedeutet")
    assert pair["prompt_l10n"]["fr"].startswith("Quelle phrase veut dire")

    output = ib.output_item(item, round_name="sentence", requirement={"label": "X", "target_count": 1})
    assert output["prompt_l10n"]["en"] == output["prompt"]
    # The situation moves with the ask: no English scene inside a German cue.
    scene = ib._scene_for(item)
    assert scene not in output["prompt_l10n"]["de"]
    assert "Sag auf Französisch" in output["prompt_l10n"]["de"]
    assert "Dites en français" in output["prompt_l10n"]["fr"]

    gloss = bank.generate("FR2_A12_CONNECTORS", 1, seed="wp-s6")[0]
    repair = ib.transform_item(gloss)
    if repair is not None:
        assert repair["instruction_l10n"]["en"] == repair["instruction"]
        assert repair["instruction_l10n"]["de"].startswith("Korrigiere den Satz")

    produce = ib.produce_block(item, item, requirement={"label": "X", "target_count": 1})
    assert produce["prompt_l10n"]["en"] == produce["prompt"]
    assert "Nachricht auf Französisch" in produce["prompt_l10n"]["de"]
