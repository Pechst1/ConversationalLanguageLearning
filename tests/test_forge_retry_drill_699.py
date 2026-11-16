"""#699 — «Try the line again» keeps the way the item was posed.

11 Nov explore walk (``a2-en``, La Forge 2/12, «Type it · Complete: …»): the
learner missed a typed gap, tapped «Try the line again», typed the right form
and pressed Check. Under «Well done!» came the item's two choice cards, one of
them a wrong form («Elles ont envoyer»), although the learner was never asked
to choose.

The page reads how an item was posed from the forge's item while it is served,
then from the answer's own record (``correction.forge.drill``). A retry is a
resubmission: the forge does not count it again, and it wrote no record on it,
so the page found no drill and drew the item the classic way, with its options.
"""
from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.services.forge import _store_state, forge_state_of
from tests.test_atelier import _prime_core_exercise_sets, _token
from tests.test_wp_s3_forge import _answer_for, _item, _submit, _wrong_for


def test_a_retried_typed_gap_is_still_typed(client: TestClient, db_session: Session) -> None:
    headers = {"Authorization": f"Bearer {_token(client)}"}
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    assert nxt["round"] == "recognize", nxt

    # The forge poses this gap typed (its options are kept for the classic way).
    session = db_session.get(AtelierSession, UUID(data["session_id"]))
    state = forge_state_of(session)
    state.pending = {**(state.pending or {}), "drill": "typed"}
    _store_state(session, state)
    flag_modified(session, "quote_payload")
    db_session.commit()

    item = _item(data, nxt)
    first = _submit(client, headers, data["session_id"], nxt, _wrong_for(item, nxt["round"], nxt["mode"]))
    assert first.status_code == 200, first.text
    assert first.json()["correction"]["forge"]["drill"] == "typed"

    # «Try the line again»: the same item, resubmitted, right this time.
    again = client.post(
        f"/api/v1/atelier/sessions/{data['session_id']}/attempts",
        headers=headers,
        json={
            "concept_id": nxt["concept_id"], "round": nxt["round"], "mode": nxt["mode"],
            "exercise_id": f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}",
            "answer_payload": _answer_for(item, nxt["round"], nxt["mode"]), "resubmit": True,
        },
    )
    assert again.status_code == 200, again.text
    body = again.json()
    assert body["forge"]["answered"] == 1, "a retry is not counted twice"
    forge = (body["correction"] or {}).get("forge") or {}
    assert forge.get("drill") == "typed", (
        "the retried answer carries no record of how its item was posed, so the page draws the typed gap "
        f"with its choice cards under «Well done!» (correction.forge = {forge!r})"
    )
    # Nothing on the retry claims a climb or a count the first answer did not make.
    assert not forge.get("counted") and "new_rung" not in forge and not forge.get("run")
