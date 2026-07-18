"""Focused regressions for the L'Epreuve learning-moment contract."""
from __future__ import annotations

from uuid import uuid4

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierCorrectionService


def test_typed_micro_repair_persists_and_queues_one_unrewarded_retest(db_session) -> None:
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test", target_language="fr")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=None,
        round="produce",
        mode="integrated_writing",
        exercise_id="integrated-writing",
        prompt_payload={"prompt": "Write one sentence."},
        answer_payload={"text": "Je vais demain."},
        correction_payload={
            "errata": [
                {
                    "learner_text": "Je vais demain.",
                    "corrected_target": "J'irai demain.",
                    "why_wrong": "Use futur simple for the result.",
                }
            ]
        },
        verdict="needs_repair",
        score_0_4=1,
    )
    db_session.add(attempt)
    db_session.commit()

    updated = AtelierCorrectionService(db_session).record_micro_repair(
        attempt=attempt,
        text="J'irai demain.",
        erratum_index=0,
    )

    assert updated.correction_payload["micro_repairs"]["0"]["status"] == "ok"
    assert updated.correction_payload["retest"]["status"] == "queued"
    assert updated.correction_payload["retest"]["source_attempt_id"] == str(attempt.id)
    assert db_session.query(AtelierAttempt).filter(AtelierAttempt.atelier_session_id == session.id).count() == 1


def test_epeuve_surface_uses_persisted_learning_moments() -> None:
    source = ("web-frontend/pages/atelier.tsx")
    contents = open(source, encoding="utf-8").read()

    for marker in (
        "repairAtelierAttempt",
        "repairRetestFromAttempt",
        "EpConfidence",
        "EpRepair",
        "EpProvenance",
        "EpLock",
        "EpGalley",
        "EpFix",
        "EpRecapHead",
        "EpProof",
        "EpSeal",
        "EpPhrase",
        "retest_source_attempt_id",
    ):
        assert marker in contents
