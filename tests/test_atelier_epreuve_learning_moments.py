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


def test_retest_is_scheduled_in_drills_not_attempt_rows(db_session) -> None:
    """The client compares `due_after_completed` against its completed-drill
    count, so counting raw attempt rows here booked the retest past the end of
    the ladder as soon as the learner had retried anything -- it then sat queued
    forever while still padding the denominator, which reported a finished
    edition as "close en avance"."""
    user = User(id=uuid4(), email=f"{uuid4()}@example.com", hashed_password="test", target_language="fr")
    db_session.add(user)
    db_session.flush()
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.flush()

    def _attempt(exercise_id: str, correction: dict | None = None) -> AtelierAttempt:
        attempt = AtelierAttempt(
            atelier_session_id=session.id,
            user_id=user.id,
            concept_id=None,
            round="produce",
            mode="integrated_writing",
            exercise_id=exercise_id,
            prompt_payload={"prompt": "Write one sentence."},
            answer_payload={"text": "Je vais demain."},
            correction_payload=correction or {},
            verdict="needs_repair",
            score_0_4=1,
        )
        db_session.add(attempt)
        return attempt

    # One drill, submitted four times ("Réessayer"): still one drill.
    for _ in range(3):
        _attempt("integrated-writing")
    repaired = _attempt(
        "integrated-writing",
        {
            "errata": [
                {
                    "learner_text": "Je vais demain.",
                    "corrected_target": "J'irai demain.",
                    "why_wrong": "Use futur simple for the result.",
                }
            ]
        },
    )
    db_session.commit()

    updated = AtelierCorrectionService(db_session).record_micro_repair(
        attempt=repaired, text="J'irai demain.", erratum_index=0
    )
    assert updated.correction_payload["retest"]["due_after_completed"] == 3


def test_locked_rung_keeps_the_drills_the_learner_already_classed() -> None:
    source = open("web-frontend/pages/atelier.tsx", encoding="utf-8").read()
    # `keepLockedItem` is what separates "retired because unreached" from
    # "already banked"; without it the composing stick ran backwards.
    assert "const keepLockedItem = (key: string) => Boolean(submitted[key]);" in source
    assert "if (modeIsLocked && !keepLockedItem(key)) return;" in source
    assert "if (transformIsLocked && !keepLockedItem(key)) return;" in source
    # And the retest threshold is clamped to the end of the ladder.
    assert "Math.min(retest.dueAfterCompleted, totalDrills(session, adaptiveLocks, submitted))" in source
