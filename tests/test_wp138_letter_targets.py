"""WP-138 — letter grading keeps communication, target practice and errors apart.

Status plan 2026-10-06, item 3. WP-125A made an unused *suggested word* neutral.
The provider also sees the letter's grammar targets and repair targets, and could
still turn one it did not find into an erratum, a missing target or a lower
verdict. An unused target is "not practised": no erratum, no negative evidence,
and no downgrade of a letter that did its job without a real mistake.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.services.missions as missions_module
from app.core.security import decode_token
from app.db.models.error import UserError
from app.db.models.user import User
from app.services import story_correspondence as courrier
from app.services.learner_copy import learner_text
from app.services.missions import MissionCorrectionService
from app.services.news_service import NewsService

LETTER = "Bonjour, je viens voir le problème demain matin et je vous écris ensuite."

OBJECTIVES = [
    {"id": "real_world_task", "required": True, "kind": "communication", "label": "Répondre"},
    {"id": "concept_12", "required": False, "kind": "grammar", "concept_id": 12, "external_id": "FR_SUBJ",
     "label": "Placer une fois : le subjonctif"},
    {"id": "erratum_abc", "required": False, "kind": "grammar", "error_id": "abc", "label": "Réparer : une erreur"},
]


def _service() -> MissionCorrectionService:
    return MissionCorrectionService(db=None, llm_service=object())  # type: ignore[arg-type]


def _absence_correction(*, verdict: str = "partial", required_met: bool = True, extra_errata=()) -> dict:
    return {
        "verdict": verdict,
        "score_0_4": 2,
        "corrected_answer": LETTER,
        "objective_progress": [
            {"id": "real_world_task", "label": "Répondre", "met": required_met, "note": "ok"},
            {"id": "concept_12", "label": "subjonctif", "met": False, "note": "You did not use the subjunctive."},
            {"id": "erratum_abc", "label": "Réparer", "met": False, "note": "Missing."},
        ],
        "concept_hits": [],
        "missing_targets": [
            {"external_id": "FR_SUBJ", "label": "subjonctif", "detected_count": 0, "target_count": 1, "missing_count": 1}
        ],
        "errata": [
            {
                "display_label": "Subjonctif manquant",
                "learner_text": "",
                "corrected_target": "il faut que je vienne",
                "why_wrong": "You did not use the subjunctive.",
                "repair_hint": "Use il faut que.",
                "severity": 2,
                "recurring": False,
                "task_error_type": "grammar_missing_target",
                "external_id": "FR_SUBJ",
            },
            *extra_errata,
        ],
        "vocabulary_links": [],
    }


def test_an_unused_grammar_target_is_not_an_error_and_does_not_downgrade():
    mission = SimpleNamespace(objectives=OBJECTIVES)
    result = _service()._separate_target_practice(correction=_absence_correction(), mission=mission, language="en")

    assert result["verdict"] == "accepted"
    assert result["score_0_4"] >= 3
    assert result["errata"] == []
    assert result["missing_targets"] == []
    assert result["unused_targets"] == [{"external_id": "FR_SUBJ", "label": "subjonctif", "kind": "grammar"}]
    rows = {row["id"]: row for row in result["objective_progress"]}
    for row_id in ("concept_12", "erratum_abc"):
        assert rows[row_id]["met"] is False
        assert rows[row_id]["observed"] is False
        assert rows[row_id]["note"] == learner_text("mission.target_unpractised", "en")


def test_a_real_language_error_still_lowers_the_verdict():
    real = {
        "display_label": "Accord",
        "learner_text": "la problème",
        "corrected_target": "le problème",
        "why_wrong": "x",
        "repair_hint": "y",
        "severity": 1,
        "recurring": False,
        "task_error_type": "agreement",
        "external_id": "FR_AGREE",
    }
    mission = SimpleNamespace(objectives=OBJECTIVES)
    result = _service()._separate_target_practice(
        correction=_absence_correction(extra_errata=[real]), mission=mission
    )
    assert result["verdict"] == "partial"
    assert result["errata"] == [real]


def test_an_unhandled_communicative_requirement_still_decides():
    mission = SimpleNamespace(objectives=OBJECTIVES)
    result = _service()._separate_target_practice(
        correction=_absence_correction(verdict="needs_revision", required_met=False), mission=mission
    )
    assert result["verdict"] == "needs_revision"
    assert result["errata"] == []


def test_journey_answer_marks_an_unused_grammar_target_not_practised():
    rows = courrier.objective_progress_from_journey(objectives=OBJECTIVES, outcome="met", language="de")
    by_id = {row["id"]: row for row in rows}
    assert by_id["real_world_task"]["met"] is True
    for row_id in ("concept_12", "erratum_abc"):
        assert by_id[row_id]["observed"] is False
        assert by_id[row_id]["note"] == learner_text("mission.target_unpractised", "de")
    progress = {row["id"]: row for row in rows}
    assert courrier.outcome_from_objectives(objectives=OBJECTIVES, progress_by_id=progress) == "kept"


async def _no_news(self, interests=None, limit=3, prefer_paris=True):  # noqa: ARG001
    return {"mode": "none", "digest": "", "items": [], "fetched_at": None, "source_policy": "test"}


def test_a_submitted_letter_without_its_grammar_target_is_accepted_and_files_no_erratum(
    client: TestClient, db_session, monkeypatch
):
    monkeypatch.setattr(NewsService, "fetch_france_context", _no_news)

    def _llm_correction(self, *, user, mission, text, mode):  # noqa: ARG001
        correction = _absence_correction()
        correction["objective_progress"] = [
            {"id": item["id"], "label": item.get("label") or "", "met": bool(item.get("required")), "note": "ok"}
            for item in mission.objectives or []
        ]
        correction["_fallback_used"] = False
        correction["_model"] = "stub"
        return correction

    monkeypatch.setattr(missions_module.MissionCorrectionService, "_llm_correction", _llm_correction)
    email = f"{uuid4()}@example.com"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "wp138-secure", "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "wp138-secure"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    user = db_session.get(User, UUID(str(decode_token(token)["sub"])))
    created = client.post(
        "/api/v1/missions/",
        json={"mission_type": "message", "cadence": "ad_hoc", "use_news": False},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    mission_id = created.json()["mission"]["id"]

    submit = client.post(
        f"/api/v1/missions/{mission_id}/submit", json={"text": LETTER, "mode": "writing"}, headers=headers
    )
    assert submit.status_code == 200, submit.text
    correction = submit.json()["correction"]
    assert correction["verdict"] == "accepted"
    assert correction["errata"] == []
    assert correction["missing_targets"] == []
    assert any(item.get("external_id") == "FR_SUBJ" for item in correction["unused_targets"])
    db_session.expire_all()
    assert db_session.query(UserError).filter(UserError.user_id == user.id).count() == 0
