"""#724, live walk of 12 Nov 2026: La Forge's free-sentence check ended «Answer saved, not
checked yet. It doesn't count yet.», «Run again» changed nothing and only «Skip without a
check» was left.

«J'ai trente-deux an.» answers «Quel âge as-tu?». With the model down the check fell back to
nothing: every other surface that reads a learner's sentence (the Courrier, the Journal, the
scene) runs the model-free pass of :mod:`app.services.correction_contract` when the model
does not answer, La Forge did not. And with no model to ask at all, «Run again» was offered
for a call that could never be made.

What the learner sees is the check the server sends (``_attempt_response``:
:func:`app.services.verdicts.from_forge` over the stored correction), so these tests read it
the same way.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.services.llm_service import LLMResult
from tests.test_forge_integration import _forge_session

ANSWER = "J'ai trente-deux an."
FIXED = "J'ai trente-deux ans."


class _Model:
    """The model client: it fails ``failures`` times, then reads the sentence."""

    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    def generate_error_detection(self, messages, **kwargs):
        from app.services.llm_service import LLMProviderError

        self.calls += 1
        if self.calls <= self.failures:
            raise LLMProviderError("down")
        content = {
            "verdict": "partial",
            "score_0_4": 2,
            "corrected_answer": FIXED,
            "concept_hits": [],
            "missing_targets": [],
            "errata": [
                {
                    "display_label": "Plural",
                    "learner_text": "an",
                    "corrected_target": "ans",
                    "why_wrong": "After a number above one, «an» takes an s: «trente-deux ans».",
                    "repair_hint": "trente-deux ans",
                    "severity": 2,
                    "recurring": False,
                    "task_error_type": "number_agreement",
                }
            ],
        }
        return LLMResult(
            provider="openai",
            model="gpt-4o",
            content=json.dumps(content),
            prompt_tokens=10,
            completion_tokens=10,
            total_tokens=20,
            cost=0.0,
            raw_response={},
        )


def _answered(db_session: Session, monkeypatch, model, *, model_configured: bool = True):
    """A forge séance with the rule at PRODUCE and «J'ai trente-deux an.» submitted."""

    from app.core.forge import Rung
    from app.services.atelier import AtelierCorrectionService
    from app.services.forge import ForgeService, _store_state, forge_state_of

    monkeypatch.setattr(AtelierCorrectionService, "_can_schedule_ai_review", lambda self: model_configured)
    user, concept, session, _shared = _forge_session(db_session)
    forge = ForgeService(db_session)
    forge.attach(user=user, session=session, keep_concepts=True)
    state = forge_state_of(session)
    state.tracks[0].rung = int(Rung.PRODUCE)
    _store_state(session, state)
    db_session.commit()
    nxt = forge.next_item(user=user, session=session)
    assert nxt["round"] == "sentence"
    service = AtelierCorrectionService(db_session, llm_service=model)
    attempt = service.submit_attempt(
        session=session,
        user=user,
        concept=concept,
        round_name="sentence",
        mode="sentence",
        exercise_id=f"forge:{concept.id}:sentence:{nxt['item_id']}",
        answer_payload={"text": ANSWER},
    )
    forge.observe_attempt(user=user, session=session, attempt=attempt)
    return service, attempt


def _check(attempt) -> dict:
    """The check the screen reads, as ``_attempt_response`` builds it."""

    from app.services import verdicts

    return verdicts.from_forge(attempt.correction_payload, text=ANSWER, verdict=attempt.verdict).to_dict()


def _run_again(service, attempt):
    """«Run again»: the endpoint marks the check pending, then the job runs it."""

    attempt, enqueued = service.mark_ai_review_pending(attempt, auto_started=False)
    assert enqueued, "«Run again» sends the check again"
    return service.run_ai_review_for_attempt(attempt.id)


def _edits(check: dict) -> list[tuple[str, str]]:
    return [(edit["span"], edit["replacement"]) for edit in check["edits"]]


def test_run_again_sends_the_check_again_and_the_reading_that_lands_is_shown(db_session: Session, monkeypatch) -> None:
    model = _Model(failures=2)
    service, attempt = _answered(db_session, monkeypatch, model)

    first = service.run_ai_review_for_attempt(attempt.id)
    assert _check(first)["retryable"] is True, "a failed call offers «Run again»"
    second = _run_again(service, first)
    assert _check(second)["retryable"] is True
    third = _run_again(service, second)

    assert model.calls == 3, "each «Run again» asked the model again"
    check = _check(third)
    assert check["checked_by"] == "model" and check["outcome"] in {"partly", "not_yet"}, check
    assert ("an", "ans") in _edits(check), "the reading that landed names «an» → «ans»"


def test_a_check_the_model_never_answers_falls_back_to_the_rules(db_session: Session, monkeypatch) -> None:
    model = _Model(failures=99)
    service, attempt = _answered(db_session, monkeypatch, model)

    failed = service.run_ai_review_for_attempt(attempt.id)
    failed = _run_again(service, failed)

    check = _check(failed)
    assert check["counts"] is False, "an answer the model never read moves nothing (#334)"
    assert ("an", "ans") in _edits(check), (
        f"the model-free pass every other surface runs names the slip; the screen got {check['edits']!r} "
        "and so said «Answer saved, not checked yet»"
    )
    assert check["retryable"] is True


def test_with_no_model_to_ask_the_check_says_so_and_offers_no_dead_retry(db_session: Session, monkeypatch) -> None:
    model = _Model(failures=0)
    service, attempt = _answered(db_session, monkeypatch, model, model_configured=False)

    check = _check(attempt)
    assert model.calls == 0
    assert check["counts"] is False
    assert ("an", "ans") in _edits(check), "the rules still read the sentence"
    assert (check["failure"], check["retryable"]) == ("no_model", False), (
        f"«Run again» can never reach a model that is not there: {check['failure']!r}, retryable={check['retryable']!r}"
    )
    again, enqueued = service.mark_ai_review_pending(attempt, auto_started=False)
    assert not enqueued
    assert _check(again)["retryable"] is False
