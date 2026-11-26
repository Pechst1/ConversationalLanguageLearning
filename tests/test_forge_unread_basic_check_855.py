"""#855 (walks 17 and 18 Nov): an unread La Forge sentence listed its basic-check fixes as «J ai →».

The solution gate (#767) blanks every fix's replacement while a second chance is
open. An answer nobody read, and nobody can be asked to read again (no model:
the screen offers only «Skip without a check», never «Check again»), gets no
second chance: the basic check's fixes are the only help it has, and both sides
are served. An unread answer that CAN be checked again (a timeout, a provider
error) keeps its solution: the re-check may open the chance (attempt 1 of #855
served it anyway, review of #861).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services import solution_gate
from tests.test_forge_instant_feedback import _start, no_model  # noqa: F401 - fixture

UNREAD = "J ai cuisine pour Lila la semaine derniere."


def _post_unread(client: TestClient, db_session) -> tuple[dict, dict, dict]:
    headers, session_id, concept, _payload = _start(client, db_session)
    response = client.post(
        f"/api/v1/atelier/sessions/{session_id}/attempts",
        headers=headers,
        json={
            "concept_id": concept["id"],
            "round": "sentence",
            "mode": "sentence",
            "exercise_id": f"{concept['external_id']}:sentence",
            "answer_payload": {"text": UNREAD},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    read = client.get(f"/api/v1/atelier/attempts/{body['attempt_id']}", headers=headers).json()
    return headers, body, read


def test_an_unread_sentence_with_no_model_keeps_both_sides_of_its_basic_check(client: TestClient, db_session, no_model):  # noqa: F811
    _headers, body, read = _post_unread(client, db_session)
    for served in (body["check"], read["check"]):
        assert served["outcome"] == "not_checked", served
        assert served["retryable"] is False, "with no model nobody can be asked again"
        assert served["edits"], "the basic check found the fixes"
        spans = {edit["span"]: edit["replacement"] for edit in served["edits"]}
        assert all(spans.values()), f"an unread answer with no chance to come served fixes with nothing after «→»: {spans}"
    for correction in (body["correction"], read["correction"]):
        assert correction["solution"]["state"] == "shown", "the payload says the solution is on it"
        assert [erratum["corrected_target"] for erratum in correction["errata"]] == ["J'ai", "cuisiné", "dernière"]


def test_asking_again_after_a_whole_unread_answer_never_reopens_a_chance(client: TestClient, db_session, no_model):  # noqa: F811
    # Once the fixes were shown, a later read (a model configured since) shows the solution:
    # the learner is never asked to repair words they have already been given.
    from uuid import UUID

    from app.db.models.atelier import AtelierAttempt
    from app.services.atelier import AtelierCorrectionService

    _headers, body, _read = _post_unread(client, db_session)
    attempt = db_session.query(AtelierAttempt).filter(AtelierAttempt.id == UUID(body["attempt_id"])).one()
    service = AtelierCorrectionService(db_session)
    service._can_schedule_ai_review = lambda: True  # type: ignore[method-assign]
    attempt, _scheduled = service.mark_ai_review_pending(attempt)
    stored = attempt.correction_payload
    assert stored["solution"]["state"] == "shown", stored["solution"]
    after = dict(stored, assessment_status="checked", verdict="incorrect", ai_review={"status": "complete"}, correction_debug={"model": "m"})
    assert solution_gate.is_withheld(after, "incorrect") is False


def _sentence(status: str, **extra) -> dict:
    """A free sentence's stored correction, posed with a second chance (``withheld``)."""

    correction = {
        "assessment_status": status,
        "verdict": "needs_review" if status == "unavailable" else "incorrect",
        "corrected_answer": "J'ai cuisiné pour Lila la semaine dernière.",
        "errata": [{"learner_text": "derniere", "corrected_target": "dernière", "why_wrong": "Accent."}],
        **extra,
    }
    return solution_gate.mark(correction, chance=True, language="en")


def test_an_unread_answer_that_can_be_checked_again_keeps_its_solution_for_the_chance():
    # A timeout: the unread screen offers «Check again», and a miss read then opens the
    # second chance. Nothing is given away before it.
    for error in ("timeout", "provider down"):
        failed = _sentence("unavailable", ai_review={"status": "failed", "error": error})
        assert solution_gate.is_withheld(failed, "needs_review") is True, error
        assert solution_gate.learner_view(failed, verdict="needs_review")["corrected_answer"] == ""
        check = {"edits": [{"span": "derniere", "replacement": "dernière", "note": "Accent."}], "corrected": None}
        assert solution_gate.withhold_check(check, failed, "needs_review")["edits"][0]["replacement"] == ""
        after = dict(failed, assessment_status="checked", verdict="incorrect", ai_review={"status": "complete"}, correction_debug={"model": "m"})
        assert solution_gate.is_withheld(after, "incorrect") is True


def test_a_check_still_running_or_read_keeps_the_solution_for_its_chance():
    pending = _sentence("provisional", ai_review={"status": "pending"})
    assert solution_gate.is_withheld(pending, "incorrect") is True
    read = _sentence("checked", correction_debug={"model": "fake"})
    assert solution_gate.is_withheld(read, "incorrect") is True


def test_an_unread_answer_nobody_can_check_again_is_served_whole():
    no_model_failed = _sentence("unavailable", ai_review={"status": "failed", "error": "no_model"})
    assert solution_gate.is_withheld(no_model_failed, "needs_review") is False
    assert solution_gate.learner_view(no_model_failed, verdict="needs_review")["corrected_answer"].startswith("J'ai")
    check = {"edits": [{"span": "derniere", "replacement": "dernière", "note": "Accent."}], "corrected": None}
    assert solution_gate.withhold_check(check, no_model_failed, "needs_review")["edits"][0]["replacement"] == "dernière"
