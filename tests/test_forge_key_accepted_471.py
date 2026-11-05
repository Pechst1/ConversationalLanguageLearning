"""#471, walk of 2 and 3 Nov: «Antwort gespeichert, noch nicht geprüft» on an answer the key accepts.

«Sag auf Französisch: „Ich bin klug.“» answered «je suis intelligente» is in the item's
accept-list, yet the card said «Ich konnte diese Antwort nicht prüfen». The model was
down, and the relecture's failure demoted every free answer to «unavailable», the
key's verdict included. The key alone decides an accepted answer (#401: whether a model
is configured only decides what happens to every OTHER sentence), so a model that fails
to read it changes nothing; and the answers nobody could read (not in the list) never
move the level, the stored level, the end sheet or the mastery-test offer.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.forge import Rung
from app.db.models.grammar import UserGrammarProgress
from tests.test_forge_check_failure import ANSWER, _ModelDown
from tests.test_forge_integration import _forge_session


def _sentence_turn(db_session: Session, monkeypatch, answer):
    """A séance with the rule at PRODUCE; one sentence answered while the model is down."""

    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: True)
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    service = AtelierCorrectionService(db_session, llm_service=_ModelDown())

    def turn(text: str | None = None):
        nxt = forge.next_item(user=user, session=session)
        assert nxt["round"] in {"sentence", "conversation"}, nxt["round"]
        attempt = service.submit_attempt(
            session=session, user=user, concept=concept, round_name=nxt["round"], mode=nxt["mode"],
            exercise_id=f"forge:{concept.id}:{nxt['round']}:{nxt['item_id']}",
            answer_payload={"text": text if text is not None else answer(nxt)},
        )
        forge.observe_attempt(user=user, session=session, attempt=attempt)
        return attempt

    return user, concept, session, forge, service, turn


def _key_answer(nxt) -> str:
    return str(nxt["item"]["example_answer"] if "item" in nxt else nxt["items"][0]["example_answer"])


def test_an_answer_the_key_accepts_stays_checked_when_the_model_cannot_read_it(db_session: Session, monkeypatch) -> None:
    from app.services.forge import forge_state_of

    user, concept, session, forge, service, turn = _sentence_turn(db_session, monkeypatch, _key_answer)
    attempt = turn()
    assert attempt.correction_payload["local_status"] == "right"

    failed = service.run_ai_review_for_attempt(attempt.id)

    payload = failed.correction_payload
    assert (payload["assessment_status"], failed.verdict) == ("checked", "correct"), "the key's verdict stands"
    assert payload["second_check"]["status"] == "failed"
    db_session.expire_all()
    entry = forge_state_of(session).history[-1]
    assert entry["checked"] and entry["counted"], "a key-accepted answer is evidence without the model"
    assert forge_state_of(session).track(concept.id).rung == int(Rung.FREE_USE)


def test_unread_sentences_move_nothing_the_learner_is_shown_or_offered(db_session: Session, monkeypatch) -> None:
    """The walk: sentences the key does not list, the model down, one after the other."""

    from app.services.atelier import AtelierSRSService
    from app.services.forge import forge_state_of

    user, concept, session, forge, service, turn = _sentence_turn(db_session, monkeypatch, _key_answer)
    # Each sentence is answered while the model is still reading the one before.
    attempts = [turn(ANSWER)]
    for _ in range(2):
        if forge.next_item(user=user, session=session) is None:
            break
        attempts.append(turn(ANSWER))
    assert len(attempts) >= 2, "the walk answers several sentences"
    for attempt in attempts:
        assert service.run_ai_review_for_attempt(attempt.id).correction_payload["assessment_status"] == "unavailable"

    db_session.expire_all()
    state = forge_state_of(session)
    assert state.track(concept.id).rung == int(Rung.PRODUCE), "the level chip"
    assert state.level_read(concept.id) == int(Rung.PRODUCE), "the end sheet's level"
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    assert progress.forge_rung == int(Rung.PRODUCE), "the stored level the next day, and the test offer, read"
    assert not any(entry.get("checked") for entry in state.history)
    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    rule = recap["forge"]["rules"][0]
    assert rule["rung"] == int(Rung.PRODUCE)
    assert [line["fr"] for line in rule["proof"]] == [], "an unchecked sentence is not listed as practised"
