"""#855 (walk 17 Nov): an unread La Forge sentence listed its basic-check fixes as «J ai →».

The solution gate (#767) blanks every fix's replacement while a second chance is
open. An answer nobody read gets no second chance: its screen offers only
«Skip without a check», so the basic check's fixes are the only help it has, and
both sides are served.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.services import solution_gate
from tests.test_forge_instant_feedback import _start, no_model  # noqa: F401 - fixture

UNREAD = "J ai cuisine pour Lila la semaine derniere."


def test_an_unread_sentence_keeps_both_sides_of_its_basic_check(client: TestClient, db_session, no_model):  # noqa: F811
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
    for served in (body["check"], read["check"]):
        assert served["outcome"] == "not_checked", served
        assert served["edits"], "the basic check found the fixes"
        spans = {edit["span"]: edit["replacement"] for edit in served["edits"]}
        assert all(spans.values()), f"an unread answer's basic check served fixes with nothing after «→»: {spans}"


def _sentence(status: str, **extra) -> dict:
    """A free sentence's stored correction, posed with a second chance (``withheld``)."""

    correction = {
        "assessment_status": status,
        "verdict": "incorrect",
        "corrected_answer": "J'ai cuisiné pour Lila la semaine dernière.",
        "errata": [{"learner_text": "derniere", "corrected_target": "dernière", "why_wrong": "Accent."}],
        **extra,
    }
    return solution_gate.mark(correction, chance=True, language="en")


def test_a_check_still_running_keeps_the_solution_for_its_chance():
    # Read later, the miss gets its second chance: nothing is given away before it.
    pending = _sentence("provisional", ai_review={"status": "pending"})
    assert solution_gate.is_withheld(pending, "incorrect") is True
    read = _sentence("checked", correction_debug={"model": "fake"})
    assert solution_gate.is_withheld(read, "incorrect") is True


def test_a_check_that_failed_after_the_answer_was_posed_withholds_nothing():
    # The relecture fails after the answer was marked «withheld» on its way in: the screen is
    # the unread one, with no second chance, so its basic check is served whole.
    failed = _sentence("unavailable", ai_review={"status": "failed", "error": "provider down"})
    assert solution_gate.is_withheld(failed, "needs_review") is False
    check = {"edits": [{"span": "derniere", "replacement": "dernière", "note": "Accent."}], "corrected": None}
    assert solution_gate.withhold_check(check, failed, "needs_review")["edits"][0]["replacement"] == "dernière"
