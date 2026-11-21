"""Owner, 13 Nov 2026: no solution before a retry — for every typed answer too.

Walk of 19 Nov (B1, La Forge «Tape la forme», Niveau 3): «On ___ demain matin ?», typed
«en lui parle» → at once «Tu as choisi « en lui parle » ; il faut « lui en parle » ici.»
and «Recopie la correction». Other typed gaps of the same walk («un lampe»,
«qu'elle a perdu») got a hint and «Réessayer» first.

What decided it (walk databases, ``atelier_attempts``): a typed fill is the fill item
of the classic way posed without its options, and the stored item keeps them. The
solution gate (``second_chance_for``) counted those options: two stored (the miss
of a pick between two names the other one) → solution at once; three → withheld.
The learner never saw either. And the deterministic line said «choisi» of a line
that was typed.

Guard: every drill whose answer is typed or written gets its retry on a first miss,
whatever the stored item holds; a real pick between two keeps the designed exception;
a typed miss says «écrit» / «wrote» / «geschrieben».
"""
from __future__ import annotations

import json
import unicodedata
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.services import forge_drills as drills
from app.services import solution_gate
from app.services.atelier import AtelierCorrectionService
from app.services.forge import _store_state, forge_state_of

# The walk's item, as stored (atelier_walk_1795093725477_595898, attempt a7595afb).
WALK_ITEM = {
    "id": "fr2-b11-double-pronouns-fill-be41cd25eb",
    "prompt": "Le vide-grenier ? Le propriétaire ne sait encore rien. On ___ demain matin ?",
    "choices": ["lui en parle", "en lui parle"],
    "correct_answer": "lui en parle",
    "accepted_answers": ["lui en parle"],
    "lesson_external_id": "FR2_B11_DOUBLE_PRONOUNS",
}
WALK_PROMPT = {"round": "recognize", "mode": "fill", "items": [WALK_ITEM]}
WALK_ANSWER = {"answers": {WALK_ITEM["id"]: "en lui parle"}}

#: La Forge's drills whose answer the learner types or writes (``forge_drills``).
TYPED_OR_WRITTEN = (drills.DRILL_TYPED, drills.DRILL_SPOT, drills.DRILL_MINE, drills.DRILL_REWRITE, drills.DRILL_WRITE, drills.DRILL_SCENE)


def _chance(**kwargs) -> bool:
    base = {
        "round_name": "recognize",
        "exercise_id": f"forge:82:recognize:{WALK_ITEM['id']}",
        "prompt_payload": WALK_PROMPT,
        "answer_payload": WALK_ANSWER,
        "first_submission": True,
        "retest": False,
        "rule_check": False,
    }
    return solution_gate.second_chance_for(**{**base, **kwargs})


def test_the_walks_typed_gap_gets_its_retry():
    assert _chance(drill=drills.DRILL_TYPED), "a typed gap whose stored item keeps two options showed its solution at once"


@pytest.mark.parametrize("drill", TYPED_OR_WRITTEN)
def test_every_typed_or_written_drill_gets_a_retry_whatever_the_item_stores(drill):
    round_name, _mode = drills.DRILL_POOL[drill]
    assert _chance(round_name=round_name, drill=drill), drill
    # The retry itself is the chance: its miss shows the solution (unchanged).
    assert not _chance(round_name=round_name, drill=drill, first_submission=False)


def test_a_typed_answer_that_is_none_of_the_options_gets_a_retry_without_a_drill():
    assert _chance(answer_payload={"answers": {WALK_ITEM["id"]: "lui en parlons"}})


def test_a_pick_between_two_keeps_the_designed_exception():
    assert not _chance(drill=drills.DRILL_CHOICE)
    assert not _chance()


@pytest.mark.parametrize(
    ("language", "written", "chosen"),
    [("fr", "Tu as écrit « en lui parle »", "Tu as choisi"), ("en", "You wrote “en lui parle”", "You chose"), ("de", "Du hast „en lui parle“ geschrieben", "gewählt")],
)
def test_a_typed_miss_says_written_not_chosen(db_session, language, written, chosen):
    concept = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR2_B11_DOUBLE_PRONOUNS").one_or_none()
    if concept is None:
        concept = GrammarConcept(
            external_id="FR2_B11_DOUBLE_PRONOUNS", language="fr", name="Deux pronoms ensemble : je le lui donne", level="B1",
            category="Pronouns", subskill="double_pronouns", core_rule="me/te/nous/vous > le/la/les > lui/leur > y > en",
            main_traps="lui le", anchor_examples="Je le lui donne.", exercise_tags=["pronouns"],
        )
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    service._posed_drill = drills.DRILL_TYPED
    erratum = service._recognize_erratum(concept, "fill", dict(WALK_ITEM), "en lui parle", "lui en parle")
    assert erratum["why_wrong"].startswith(written), erratum["why_wrong"]
    assert chosen not in erratum["why_wrong"]
    # Picked among the options, the same miss was chosen.
    service._posed_drill = drills.DRILL_CHOICE
    picked = service._recognize_erratum(concept, "fill", dict(WALK_ITEM), "en lui parle", "lui en parle")
    assert chosen in picked["why_wrong"], picked["why_wrong"]


def _fold(text: str) -> str:
    return unicodedata.normalize("NFC", text).replace("’", "'").lower()


def test_a_typed_gap_with_two_stored_options_is_served_without_its_solution(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    """End to end through La Forge: the walk's case on a séance of the test bank."""

    from tests.test_atelier import _prime_core_exercise_sets, _token
    from tests.test_wp_s3_forge import _item

    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    assert nxt["round"] == "recognize" and nxt["mode"] == "fill", nxt

    session = db_session.get(AtelierSession, UUID(data["session_id"]))
    state = forge_state_of(session)
    state.pending = {**(state.pending or {}), "drill": drills.DRILL_TYPED}
    _store_state(session, state)
    flag_modified(session, "quote_payload")
    db_session.commit()

    item = _item(data, nxt)
    key = str(item.get("correct_answer"))
    wrong = "zzz ne pas"
    original = AtelierCorrectionService._prompt_payload

    def two_options(self, *args, **kwargs):
        # As in the walk: the stored fill keeps two options (the key and the miss).
        payload = original(self, *args, **kwargs)
        for stored in payload.get("items") or []:
            if stored.get("id") == item["id"]:
                stored["choices"] = [key, wrong]
        return payload

    monkeypatch.setattr(AtelierCorrectionService, "_prompt_payload", two_options)
    response = client.post(
        f"/api/v1/atelier/sessions/{data['session_id']}/attempts",
        headers=headers,
        json={
            "concept_id": nxt["concept_id"], "round": "recognize", "mode": "fill",
            "exercise_id": f"forge:{nxt['concept_id']}:recognize:{nxt['item_id']}",
            "answer_payload": {"answers": {item["id"]: wrong}},
        },
    )
    assert response.status_code == 200, response.text
    correction = response.json()["correction"]
    assert correction["verdict"] != "correct"
    assert correction["solution"]["state"] == "withheld", (
        f"a typed miss showed its solution before the retry (solution = {correction['solution']!r})"
    )
    assert correction["corrected_answer"] in ({}, "")
    served = _fold(json.dumps(correction["errata"], ensure_ascii=False))
    assert _fold(f"« {key} »") not in served and _fold(f"“{key}”") not in served and _fold(f"„{key}“") not in served
