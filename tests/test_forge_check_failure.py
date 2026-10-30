"""#334: a La Forge free-text answer the model never read changes nothing.

Live walk 25 Oct 2026: all five free-text items ended «The second check
stopped», yet the level had already gone up (5 -> 6) and the recap printed
lines under the rules that the learner never wrote. An answer nobody checked
is neither progress nor the learner's work.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from tests.test_forge_integration import _forge_session

ANSWER = "Je ne bois pas de café le soir."


class _ModelDown:
    """The model client forced to fail (timeout / provider error)."""

    calls: list = []

    def generate_error_detection(self, messages, **kwargs):
        from app.services.llm_service import LLMProviderError

        raise LLMProviderError("down")


def _free_text_answer(db_session: Session, monkeypatch):
    """A forge séance with the rule at PRODUCE; one free-text answer, its relecture queued."""

    from app.core.forge import Rung
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
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    service = AtelierCorrectionService(db_session, llm_service=_ModelDown())
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": ANSWER},
    )
    assert attempt.correction_payload["assessment_status"] == "provisional"
    assert attempt.correction_payload["local_check"]["detector"] == "hit"
    view = forge.observe_attempt(user=user, session=session, attempt=attempt)
    return user, session, forge, service, attempt, view


def test_a_failed_second_check_leaves_the_level_where_it_was(db_session: Session, monkeypatch) -> None:
    from app.core.forge import Rung
    from app.services.forge import forge_state_of

    user, session, forge, service, attempt, view = _free_text_answer(db_session, monkeypatch)
    assert view["rules"][0]["rung"] == int(Rung.FREE_USE), "while the model reads it, the séance keeps moving"

    failed = service.run_ai_review_for_attempt(attempt.id)

    assert failed.correction_payload["assessment_status"] == "unavailable"
    assert failed.correction_payload["second_check"]["status"] == "failed"
    db_session.expire_all()
    view = forge.view(user=user, session=session)
    assert view["rules"][0]["rung"] == int(Rung.PRODUCE), "an unread answer does not raise the level"
    assert failed.correction_payload["forge"]["new_rung"] == int(Rung.PRODUCE), "the screen reads the level from here"
    assert forge_state_of(session).tracks[0].rung == int(Rung.PRODUCE)


def test_the_recap_never_prints_the_model_answer_as_an_unchecked_sentence(db_session: Session, monkeypatch) -> None:
    from app.services.atelier import AtelierSRSService

    user, session, _forge, service, attempt, _view = _free_text_answer(db_session, monkeypatch)
    example = str(attempt.prompt_payload["items"][0].get("example_answer") or "")
    assert example, "the item carries a model answer, which is not the learner's work"

    # Skipped while the second check is still running ...
    pending = AtelierSRSService(db_session)._forge_proof_line(attempt)
    assert pending is None, f"a provisional answer is not proof of anything: {pending!r}"

    # ... and after it stopped.
    failed = service.run_ai_review_for_attempt(attempt.id)
    assert failed.correction_payload["assessment_status"] == "unavailable"
    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    proofs = [line["fr"] for rule in recap["forge"]["rules"] for line in rule["proof"]]
    assert example not in proofs
    assert proofs == []


def test_an_answer_nobody_can_read_never_moves_the_level_in_the_first_place(db_session: Session, monkeypatch) -> None:
    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of

    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    attempt = AtelierCorrectionService(db_session, llm_service=_ModelDown()).submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": ANSWER},
    )
    assert attempt.correction_payload["assessment_status"] == "unavailable"

    view = forge.observe_attempt(user=user, session=session, attempt=attempt)

    assert view["rules"][0]["rung"] == int(Rung.PRODUCE)
