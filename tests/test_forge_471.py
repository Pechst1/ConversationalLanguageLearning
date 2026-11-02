"""#471: an answer nobody read never keeps the level it climbed on.

Walk 2 Nov 2026 (La Forge «Je suis, tu es», fake stack): «Sag auf Französisch:
„Ich bin klug.“», answer «je suis intelligente», «Antwort gespeichert, noch nicht
geprüft», and the level chip went Stufe 5 -> 6 and stayed there. The end sheet
read Stufe 6 of 6 after one day.

Why the code allowed it: the local «uses the rule» reading steps the level on
provisionally, and the settle step takes that step back when the model never
reads the answer. But settle (and ``level_read``) took *any* later answer that was
read as the owner of the level, so the provisional step stayed. A read answer owns
the level only when it could move it: an item posed below the level (a warm-up, a
minimal pair, a due rule's entry item) never lifts or lowers it, so it owns nothing.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core import forge as core
from app.core.forge import Rung


def _level_is(actual: object, expected: object, what: str) -> None:
    """One-line failure text, so the red/green proof can read what failed."""

    if int(actual) != int(expected):  # type: ignore[call-overload]
        raise AssertionError(f"{what}: level {int(actual)} instead of {int(expected)}")


def _climbed_on_an_unread_sentence() -> tuple[core.ForgeState, dict]:
    state = core.ForgeState.seance([core.ForgeUnit(1, core.Role.TODAY.value, int(Rung.PRODUCE))], length=8)
    state.record(
        concept_id=1,
        rung=int(Rung.PRODUCE),
        verdict=core.Verdict(core.OUTCOME_CORRECT, checked=False, local=core.OUTCOME_CORRECT),
    )
    first = state.history[-1]
    assert state.track(1).rung == Rung.FREE_USE, "provisionally the sentence uses the rule: the séance moves on"
    return state, first


def test_warm_up_keeps_no_climb() -> None:
    state, first = _climbed_on_an_unread_sentence()
    # The next item is a keyed one posed below the level (a warm-up): read, right, moves nothing.
    state.record(concept_id=1, rung=int(Rung.RECOGNISE), verdict=core.Verdict(core.OUTCOME_CORRECT, checked=True))
    assert state.track(1).rung == Rung.FREE_USE

    # While the sentence is still unread the end sheet already shows the level without its climb.
    _level_is(state.level_read(1), Rung.PRODUCE, "end sheet level")

    # Nobody ever reads the sentence: the climb goes back.
    _level_is(state.settle(first, core.Verdict(core.OUTCOME_INCORRECT, checked=False)), Rung.PRODUCE, "settled")
    _level_is(state.track(1).rung, Rung.PRODUCE, "rule level")
    assert state.track(1).topped is False


def test_answer_at_level_owns_it() -> None:
    """The counterpart (the existing #281 rule): a read right answer at the new level tops the rule."""

    state, first = _climbed_on_an_unread_sentence()
    state.record(concept_id=1, rung=int(Rung.FREE_USE), verdict=core.Verdict(core.OUTCOME_CORRECT, checked=True))
    assert state.level_read(1) == Rung.FREE_USE
    assert state.settle(first, core.Verdict(core.OUTCOME_INCORRECT, checked=False)) == Rung.FREE_USE
    assert state.track(1).topped is True


def test_stored_level_unchanged(db_session: Session, monkeypatch) -> None:
    """Through the services: the sentence is unread (the relecture fails), a keyed warm-up
    is read after it. The rule's stored level (what the next day opens on, and what the
    mastery-test offer reads) is where it was before the sentence."""

    from app.db.models.grammar import UserGrammarProgress
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of
    from tests.test_forge_check_failure import ANSWER, _ModelDown
    from tests.test_forge_integration import _forge_session

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
    sentence = service.submit_attempt(
        session=session, user=user, concept=concept, round_name="sentence", mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}", answer_payload={"text": ANSWER},
    )
    view = forge.observe_attempt(user=user, session=session, attempt=sentence)
    assert view["rules"][0]["rung"] == int(Rung.FREE_USE), "while the model reads it the séance keeps moving"

    # A keyed item posed below the level, answered right and read, before the relecture lands.
    state = forge_state_of(session)
    state.record(concept_id=concept.id, rung=int(Rung.RECOGNISE), verdict=core.Verdict(core.OUTCOME_CORRECT, checked=True))
    _store_state(session, state)
    db_session.commit()

    failed = service.run_ai_review_for_attempt(sentence.id)
    assert failed.correction_payload["assessment_status"] == "unavailable"

    db_session.expire_all()
    progress = (
        db_session.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one()
    )
    _level_is(forge_state_of(session).track(concept.id).rung, Rung.PRODUCE, "seance level")
    _level_is(progress.forge_rung, Rung.PRODUCE, "stored level")
    _level_is(failed.correction_payload["forge"]["new_rung"], Rung.PRODUCE, "shown level")
