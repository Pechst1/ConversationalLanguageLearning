"""#828 (child of #542): a typed La Forge gap miss said «Du hast „est“ gewählt» (chose).

Explore walk 16 Nov 2026 (``a1-de-fresh``, La Forge 2/6, «Eintippen · Ergänze den
Satz»): the learner typed «est» and read «Du hast „est“ gewählt; hier ist „es“ nötig.
Hier braucht es die Form «es» von «être», nicht «est».» The verb came from the
feedback path (the recognize round's «chose» line), not from how the forge posed the
item; and the second sentence said the swap again. Seen again 17 Nov in English
(«You chose “tu as porter”; Most verbs …»).

The forge knows how it posed each item (``state.pending["drill"]`` while it is served,
the history entry once answered, #699); the grader reads it there.
"""
from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.atelier import AtelierSession
from app.db.models.grammar import GrammarConcept
from app.db.models.user import User
from app.services.forge import _store_state, forge_state_of
from tests.test_atelier import _prime_core_exercise_sets, _token
from tests.test_wp_s3_forge import _item, _submit

WROTE = {"en": "You wrote “zzz”", "de": "Du hast „zzz“ geschrieben", "fr": "Tu as écrit « zzz »"}
CHOSE = {"en": "You chose “zzz”", "de": "Du hast „zzz“ gewählt", "fr": "Tu as choisi « zzz »"}


def _seance(client: TestClient, db_session: Session, language: str, drill: str):
    token = _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.query(User).order_by(User.created_at.desc()).first()
    user.native_language = language
    user.cefr_estimate = "A1"
    db_session.commit()
    _prime_core_exercise_sets(db_session)
    neg = db_session.query(GrammarConcept).filter(GrammarConcept.external_id == "FR_A2_NEG_001").one()
    data = client.post("/api/v1/atelier/sessions", headers=headers, json={"preferred_concept_id": neg.id}).json()
    nxt = data["forge"]["next"]
    assert nxt["round"] == "recognize", nxt
    session = db_session.get(AtelierSession, UUID(data["session_id"]))
    state = forge_state_of(session)
    state.pending = {**(state.pending or {}), "drill": drill}
    _store_state(session, state)
    flag_modified(session, "quote_payload")
    db_session.commit()
    return headers, data, nxt


def _why(response) -> str:
    assert response.status_code == 200, response.text
    errata = (response.json()["correction"] or {}).get("errata") or []
    assert errata, response.json()["correction"]
    return " ".join(str(erratum.get("why_wrong") or "") for erratum in errata)


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_typed_gap_says_wrote(client: TestClient, db_session: Session, language: str) -> None:
    headers, data, nxt = _seance(client, db_session, language, "typed")
    item = _item(data, nxt)
    first = _submit(client, headers, data["session_id"], nxt, {"answers": {item["id"]: "zzz"}})
    why = _why(first)
    assert WROTE[language] in why and CHOSE[language] not in why, (
        f"a typed gap miss calls the typed answer «chosen» ({language}): {why!r}"
    )
    # 17 Nov: the hint shown before the solution kept «; » before a new sentence.
    assert not re.search(r"; [A-ZÀ-Ý]", why), f"a capital after a semicolon: {why!r}"

    # «Try the line again», wrong again: the retry was posed typed too (#699).
    again = client.post(
        f"/api/v1/atelier/sessions/{data['session_id']}/attempts",
        headers=headers,
        json={
            "concept_id": nxt["concept_id"], "round": nxt["round"], "mode": nxt["mode"],
            "exercise_id": f"forge:{nxt['concept_id']}:{nxt['round']}:{nxt['item_id']}",
            "answer_payload": {"answers": {item["id"]: "zzz"}}, "resubmit": True,
        },
    )
    why = _why(again)
    assert WROTE[language] in why and CHOSE[language] not in why, (
        f"a retried typed gap miss calls the typed answer «chosen» ({language}): {why!r}"
    )


@pytest.mark.parametrize("language", ["en", "de", "fr"])
def test_choice_gap_says_chose(client: TestClient, db_session: Session, language: str) -> None:
    headers, data, nxt = _seance(client, db_session, language, "choice")
    item = _item(data, nxt)
    why = _why(_submit(client, headers, data["session_id"], nxt, {"answers": {item["id"]: "zzz"}}))
    assert CHOSE[language] in why and WROTE[language] not in why, why


@pytest.mark.parametrize(
    ("language", "needs"),
    [("en", "this item needs"), ("de", "nötig"), ("fr", "il faut")],
)
def test_named_slip_says_it_once(db_session: Session, language: str, needs: str) -> None:
    """«est» for «es»: one sentence names what was typed, the next says why; the
    «… needs “es”» clause would say the swap a second time."""

    from app.services.atelier import AtelierCorrectionService

    concept = GrammarConcept(external_id="FR2_A11_ETRE", name="Être", level="A1", category="Verbs")
    item = {
        "id": "gap", "prompt": "___ -tu au Mistral, Marin ?", "choices": ["Es", "Est", "Suis"],
        "correct_answer": "es", "lesson_external_id": "FR2_A11_ETRE",
    }
    service = AtelierCorrectionService(db_session)
    service.explanation_language = language
    service._posed = "typed"
    erratum = service._recognize_erratum(concept, "fill", item, "est", "es")
    why = erratum["why_wrong"]
    assert needs not in why, f"the swap is said twice: {why!r}"
    assert why.count("«es»") + why.count("« es »") + why.count("„es“") + why.count("“es”") == 1, why
