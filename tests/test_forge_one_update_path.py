# ruff: noqa: F811
"""#281 / #146: a rule's level, its stored level and its review date follow one path.

Live walk 22 Oct: «Item 2 read Level 5 before I answered; after a wrong answer it
read Level 6», and the recap showed every rule at «Level 6». The level the learner
sees (the séance's staircase, ``correction.forge.new_rung``), the level stored
(``UserGrammarProgress.forge_rung``) and the review date (``next_review``) each had
their own writer: a free sentence stepped the staircase at once on the *local*
reading, and the model's reading that followed (or its failure) only wrote
evidence, "the staircase has moved on". So a miss that the local check mistook
for a hit stayed a level up everywhere, and an answer nobody could read (status
«unavailable») still climbed.

The fix is one settle step: whenever the real verdict arrives (or is known never to
arrive) the staircase, the stored level, the shown level and the schedule are
recomputed together from that verdict.
"""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.forge import Rung
from app.db.models.grammar import UserGrammarProgress
from app.services.atelier import AtelierCorrectionService
from app.services.forge import ForgeService, _store_state, forge_state_of
from tests.test_atelier import _FakeLLMService
from tests.test_forge_integration import _forge_session, _right, _wrong


def _progress(db: Session, user, concept) -> UserGrammarProgress | None:
    return (
        db.query(UserGrammarProgress)
        .filter(UserGrammarProgress.user_id == user.id, UserGrammarProgress.concept_id == concept.id)
        .one_or_none()
    )


def _seated(db: Session, rung: Rung, monkeypatch, *, relecture: bool = True):
    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: relecture)
    user, concept, session, _shared = _forge_session(db)
    forge = ForgeService(db)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(rung)
    _store_state(session, state)
    db.commit()
    return user, concept, session, forge


def _levels(db: Session, user, concept, session, attempt) -> tuple[int, int | None, int]:
    """(the séance's level, the stored level, the level the learner is shown)."""

    db.refresh(session)
    db.refresh(attempt)
    state = forge_state_of(session)
    progress = _progress(db, user, concept)
    return (
        state.track(concept.id).rung,
        progress.forge_rung if progress else None,
        int(attempt.correction_payload["forge"]["new_rung"]),
    )


def _sentence(service, session, user, concept, forge, text: str):
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence", nxt["round"]
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": text},
    )
    return attempt


# A sentence that the rule's local detector reads as using the rule (see
# test_forge_integration), but that the model, reading it, marks wrong.
USES_THE_FORM = "Je ne bois pas de café le soir."
MODEL_SAYS_WRONG = {
    "verdict": "incorrect",
    "score_0_4": 1,
    "errata": [
        {
            "span": "de café",
            "learner_text": "de café",
            "corrected_target": "du café",
            "task_error_type": "grammar",
            "why_wrong": "x",
        }
    ],
}


def test_a_miss_the_local_check_took_for_a_hit_lowers_the_level_everywhere(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)
    service = AtelierCorrectionService(db_session, llm_service=_FakeLLMService(MODEL_SAYS_WRONG))
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    assert attempt.correction_payload["assessment_status"] == "provisional"
    assert attempt.correction_payload["local_check"]["detector"] == "hit"
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    # Provisionally the sentence uses the rule: the séance keeps moving.
    assert _levels(db_session, user, concept, session, attempt) == (Rung.FREE_USE, Rung.FREE_USE, Rung.FREE_USE)

    service.run_ai_review_for_attempt(attempt.id)

    assert _levels(db_session, user, concept, session, attempt) == (Rung.TRANSFORM, Rung.TRANSFORM, Rung.TRANSFORM), (
        "the model read it as a miss: the level the learner sees, the level stored and the séance's "
        "level must all be one below the rung it was posed at"
    )
    # The review date follows the same miss: the rule comes back soon.
    progress = _progress(db_session, user, concept)
    assert progress is not None and progress.next_review is not None
    assert forge.view(user=user, session=session)["rules"][0]["rung"] == Rung.TRANSFORM


def test_an_answer_nobody_could_read_never_climbs(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)

    class _Down:
        def generate_error_detection(self, messages, **kwargs):
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("down")

    service = AtelierCorrectionService(db_session, llm_service=_Down())
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    assert _levels(db_session, user, concept, session, attempt)[0] == Rung.FREE_USE

    service.run_ai_review_for_attempt(attempt.id)

    assert _levels(db_session, user, concept, session, attempt) == (Rung.PRODUCE, Rung.PRODUCE, Rung.PRODUCE), (
        "«Antwort gespeichert, noch nicht geprüft» is unavailable: it never counts, so it never climbs"
    )


def test_an_answer_that_is_unavailable_from_the_start_does_not_climb(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch, relecture=False)
    service = AtelierCorrectionService(db_session)
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    assert attempt.correction_payload["assessment_status"] == "unavailable"
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    assert _levels(db_session, user, concept, session, attempt) == (Rung.PRODUCE, Rung.PRODUCE, Rung.PRODUCE)


def test_a_hit_the_model_confirms_keeps_the_level_it_gave(db_session: Session, monkeypatch) -> None:
    user, concept, session, forge = _seated(db_session, Rung.PRODUCE, monkeypatch)
    service = AtelierCorrectionService(
        db_session, llm_service=_FakeLLMService({"verdict": "accepted", "score_0_4": 4, "errata": []})
    )
    attempt = _sentence(service, session, user, concept, forge, USES_THE_FORM)
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    service.run_ai_review_for_attempt(attempt.id)
    assert _levels(db_session, user, concept, session, attempt) == (Rung.FREE_USE, Rung.FREE_USE, Rung.FREE_USE)


def test_right_wrong_wrong_on_one_rule_moves_all_three_levels_together(db_session: Session, monkeypatch) -> None:
    """The issue's «Done when»: the shown level, the stored level and the review date
    follow the same sequence, and the recap reads the stored value."""

    user, concept, session, forge = _seated(db_session, Rung.BUILD, monkeypatch)
    service = AtelierCorrectionService(db_session)
    seen: list[tuple[int, int | None, int]] = []
    due: list[Any] = []
    for answer_right in (True, False, False):
        nxt = forge.next_item(user=user, session=session)
        round_name, mode = nxt["round"], nxt["mode"]
        mode = "rewrite" if round_name == "transform" else mode
        item = nxt["item"]
        answer = _right(item, round_name, mode) if answer_right else _wrong(item, round_name, mode)
        attempt = service.submit_attempt(
            session=session,
            user=user,
            concept=concept,
            round_name=round_name,
            mode=mode,
            exercise_id=f"forge:{concept.id}:{round_name}:{nxt['item_id']}",
            answer_payload=answer,
        )
        forge.observe_attempt(user=user, session=session, attempt=attempt)
        seen.append(_levels(db_session, user, concept, session, attempt))
        due.append(_progress(db_session, user, concept).next_review)
    assert seen == [
        (Rung.TRANSFORM, Rung.TRANSFORM, Rung.TRANSFORM),
        (Rung.BUILD, Rung.BUILD, Rung.BUILD),
        (Rung.DISCRIMINATE, Rung.DISCRIMINATE, Rung.DISCRIMINATE),
    ]
    # A miss brings the rule back no later than the right answer had set it.
    assert due[1] <= due[0] and due[2] <= due[1]
    # The recap reads the stored value.
    from app.services.atelier import AtelierSRSService

    recap = AtelierSRSService(db_session).complete_session(session=session, user=user)
    [rule] = recap["forge"]["rules"]
    assert rule["rung"] == _progress(db_session, user, concept).forge_rung == Rung.DISCRIMINATE
    assert rule["next_due"] == _progress(db_session, user, concept).next_review.isoformat()


@pytest.mark.parametrize("status", ["unavailable"])
def test_verdict_from_attempt_never_reads_a_local_hit_of_an_unavailable_answer(status: str) -> None:
    from app.db.models.atelier import AtelierAttempt
    from app.services.forge import verdict_from_attempt

    attempt = AtelierAttempt(
        round="sentence",
        mode="sentence",
        verdict="needs_review",
        correction_payload={"assessment_status": status, "local_check": {"detector": "hit"}},
        answer_payload={"text": "x"},
    )
    verdict = verdict_from_attempt(attempt)
    assert verdict.checked is False and verdict.local is None
    attempt.correction_payload = {"assessment_status": "provisional", "local_check": {"detector": "hit"}}
    assert verdict_from_attempt(attempt).local == "correct"
