"""#401: without the correction model, a free-text answer equal to the item's own
answer is right on the spot; any other sentence still waits for the relecture.

Walk 31 Oct (fake stack, no model): «Hier, elle a écrit un message à Romy.», the
item's own answer word for word, ended «I could not check this answer». The key
already says it is right; only a sentence the key does not cover needs the model.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from tests.test_forge_integration import _forge_session


class _NoCall:
    def generate_error_detection(self, messages, **kwargs):  # pragma: no cover - regression only
        raise AssertionError("no model is configured: nothing may call it")


def _submit_free_text(db_session: Session, monkeypatch, *, text_for):
    """A forge séance at PRODUCE with no model; ``text_for(prompt)`` is what the learner writes."""

    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService, _accepted_answers
    from app.services.forge import ForgeService, _store_state, forge_state_of

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: False)
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    service = AtelierCorrectionService(db_session, llm_service=_NoCall())
    exercise_id = f"forge:{concept.id}:sentence:{nxt['item_id']}"
    # The item's own answers, read from the very payload the séance grades against.
    accepted = _accepted_answers(
        service._prompt_payload(concept, "sentence", "sentence", exercise_id, user=user, session=session)
    )
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=exercise_id,
        answer_payload={"text": text_for(accepted)},
    )
    return user, session, forge, attempt


def test_the_items_own_answer_is_right_without_the_model(db_session: Session, monkeypatch) -> None:
    def typed(accepted: list[str]) -> str:
        assert accepted, "the item carries an accepted answer"
        # Case, final punctuation and apostrophe style do not matter.
        return accepted[0].rstrip(".!? ").lower().replace("'", "’")

    user, session, forge, attempt = _submit_free_text(db_session, monkeypatch, text_for=typed)
    correction = attempt.correction_payload

    assert correction["assessment_status"] != "unavailable", "the key covers this sentence: no model needed"
    assert correction["verdict"] == "correct"
    assert float(correction["score_0_4"]) == 4.0
    assert (correction.get("ai_review") or {}).get("status") == "not_applicable", "nothing is left to run again"

    # The right answer counts: the level moves, the answer is no «unchecked» line.
    from app.core.forge import Rung

    view = forge.observe_attempt(user=user, session=session, attempt=attempt)
    assert view["rules"][0]["rung"] == int(Rung.FREE_USE)


def test_a_sentence_the_key_does_not_cover_still_waits_for_the_relecture(db_session: Session, monkeypatch) -> None:
    _user, _session, _forge, attempt = _submit_free_text(
        db_session, monkeypatch, text_for=lambda _accepted: "Je ne bois pas de café le soir."
    )
    correction = attempt.correction_payload

    assert correction["assessment_status"] == "unavailable"
    assert correction["verdict"] == "needs_review"
