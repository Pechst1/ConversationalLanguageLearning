"""Beta: «Something here looks wrong» under a verdict, from the tap to a finding.

The tap is stored as a `looks_wrong` report; the loop script files one public issue per
report that names its shape, never the learner's or the correction's words.
"""
from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_users import register_and_login

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "loop" / "learner_reports.py"
_SPEC = importlib.util.spec_from_file_location("learner_reports", _PATH)
assert _SPEC and _SPEC.loader
learner_reports = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(learner_reports)

SHOWN = {
    "surface": "journey",
    "step_kind": "recall",
    "outcome": "not_yet",
    "correction": {
        "kind": "grammar",
        "span_fr": "je suis allé hier chez ma sœur Camille",
        "corrected_fr": "je suis allée hier chez ma sœur Camille",
        "notes_native": ["Accord du participe avec être."],
    },
    "slip_note_native": None,
    "journey_id": "j-1",
    "step_id": "s-1",
}


def _report(**overrides):
    report = {
        "id": "0b9c8d7e-1111-2222-3333-444455556666",
        "category": "looks_wrong",
        "message": "Ich bin ein Mann, das war richtig",
        "route": "/atelier",
        "screen": "journey",
        "context_payload": SHOWN,
        "created_at": datetime.now(UTC).isoformat(),
    }
    report.update(overrides)
    return report


def test_the_tap_is_stored_as_a_looks_wrong_report(client: TestClient) -> None:
    token = register_and_login(client, "looks-wrong@example.com", "verysecure")
    response = client.post(
        "/api/v1/feedback/reports",
        json={"category": "looks_wrong", "route": "/atelier", "screen": "journey", "context_payload": SHOWN},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "looks_wrong"
    assert body["context_payload"]["correction"]["corrected_fr"].startswith("je suis allée")


def test_the_public_issue_names_the_report_never_the_words() -> None:
    issue = learner_reports.issue_for(_report())
    text = issue["title"] + issue["body"]
    assert "recall" in text and "not_yet" in text and "grammar" in text
    assert "learner-report:0b9c8d7e-1111-2222-3333-444455556666" in issue["body"]
    # Neither the learner's answer, the correction, its note nor the learner's own note.
    for private in ("Camille", "allée", "Accord du participe", "Ich bin ein Mann"):
        assert private not in text
    assert issue["labels"] == ["walk-finding", "source:learner", "queue:owner"]


def test_a_report_is_filed_once_and_only_when_recent() -> None:
    now = datetime.now(UTC)
    old = _report(id="old", created_at=(now - timedelta(days=9)).isoformat())
    filed = _report(id="filed")
    fresh = _report(id="fresh")
    todo = learner_reports.new_reports([old, filed, fresh], {"filed"}, since=now - timedelta(days=2))
    assert [r["id"] for r in todo] == ["fresh"]
