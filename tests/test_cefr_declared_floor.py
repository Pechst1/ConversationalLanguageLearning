"""P2 (pilot 2026-11-17) · a declared level is never lowered automatically.

The walk's learner declared B1 and was stored A1.1 after her 40th checked
answer, with no message: the interface switched to her mother tongue, the next
rule was «avoir» at Forge level 1 and scenes shrank. The measured level was
«one band above the highest closed épreuve», which for a learner who has closed
none is A1.1. The stored level now never goes below the learner's floor (a
settled placement, else the declaration); the lower measurement is kept in the
payload for the pilot's ops view and changes nothing the learner sees. Only a
placement — a test the learner chose to take — may move it down.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.cefr import UserCEFRProgressHistory
from app.db.models.error import UserError
from app.db.models.placement import PlacementSession
from app.db.models.user import User
from app.services.cefr_progress import (
    CEFR_PROGRESS_VERSION,
    DECLARED_LEVEL_EVIDENCE_ATTEMPTS,
    CEFRProgressService,
)
from app.services.chrome_language import user_chrome_language

#: Every caller that recomputes with ``persist=True`` outside a placement.
PERSISTING_SOURCES = ("atelier_session_complete", "mission_complete", "feuilleton_complete", "lazy", "api")


def _declared_b1(db_session) -> User:
    """The walk's learner: declared B1, already shown B1.1 by earlier recomputes."""

    user = User(
        id=uuid4(),
        email=f"p2-floor-{uuid4().hex[:8]}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="B1",
        cefr_estimate="B1.1",
        cefr_estimate_payload={
            "version": CEFR_PROGRESS_VERSION,
            "estimate": "B1.1",
            "estimate_source": "declared",
            "release_floor": None,
        },
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _half_wrong_attempts(db_session, user: User, count: int = DECLARED_LEVEL_EVIDENCE_ATTEMPTS + 4) -> None:
    """``count`` checked Forge answers in the last 14 days, about half of them wrong."""

    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed")
    db_session.add(session)
    db_session.flush()
    now = datetime.now(UTC)
    for index in range(count):
        wrong = index % 2 == 0
        db_session.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                concept_id=None,
                round="recognize",
                mode="fill",
                exercise_id=f"p2-{index}",
                verdict="incorrect" if wrong else "correct",
                score_0_4=1 if wrong else 3,
                created_at=now - timedelta(days=1 + index % 10),
            )
        )
        if wrong:
            db_session.add(
                UserError(
                    user_id=user.id,
                    error_category="grammar",
                    created_at=now - timedelta(days=1 + index % 10),
                )
            )
    db_session.commit()


def _low_history(db_session, user: User, level: str = "A1.1") -> None:
    """Three earlier recomputes that already measured low: the smoothing has run out."""

    for _ in range(3):
        db_session.add(
            UserCEFRProgressHistory(
                user_id=user.id,
                estimate_level="B1.1",
                source="test",
                signal_snapshot={},
                payload={"computed_level": level},
            )
        )
    db_session.commit()


def _placement(db_session, user: User, level: str) -> None:
    db_session.add(
        PlacementSession(
            user_id=user.id,
            status="complete",
            current_band=level,
            turns=[],
            estimate={"graded_turns": 5},
            estimate_level=level,
            confidence=0.8,
            completed_at=datetime.now(UTC),
        )
    )
    db_session.commit()


@pytest.mark.parametrize("source", PERSISTING_SOURCES)
def test_a_declared_b1_is_not_lowered_by_measurement(db_session, source):
    user = _declared_b1(db_session)
    chrome_before = user_chrome_language(user)
    _half_wrong_attempts(db_session, user)
    _low_history(db_session, user)

    payload = CEFRProgressService(db_session).recompute(user, source=source)
    db_session.refresh(user)

    assert user.cefr_estimate == "B1.1"
    assert payload["estimate"] == "B1.1"
    assert user_chrome_language(user) == chrome_before
    # The measurement is not lost: it is recorded for the pilot's ops view.
    below = payload["measured_below_floor"]
    assert below["level"] == "A1.1"
    assert below["floor"] == "B1.1"
    assert below["floor_source"] == "declared"
    assert below["attempts"] >= DECLARED_LEVEL_EVIDENCE_ATTEMPTS
    assert below["errors"] > 0
    history = (
        db_session.query(UserCEFRProgressHistory)
        .filter_by(user_id=user.id, source=source)
        .one()
    )
    assert history.estimate_level == "B1.1"


def test_a_learner_already_lowered_is_restored_to_the_floor(db_session):
    """The walk's learner was stored A1.1 before this rule: the next recompute puts B1.1 back."""

    user = _declared_b1(db_session)
    _half_wrong_attempts(db_session, user)
    user.cefr_estimate = "A1.1"
    user.cefr_estimate_payload = {**user.cefr_estimate_payload, "estimate": "A1.1", "estimate_source": "measured"}
    db_session.commit()

    CEFRProgressService(db_session).recompute(user, source="atelier_session_complete")
    db_session.refresh(user)

    assert user.cefr_estimate == "B1.1"


def test_a_placement_below_the_declaration_still_lowers_it(db_session):
    user = _declared_b1(db_session)
    _half_wrong_attempts(db_session, user)
    _placement(db_session, user, "A2.1")

    CEFRProgressService(db_session).recompute(user, source="placement")
    db_session.refresh(user)
    assert user.cefr_estimate == "A2.1"

    # …and the placed level is now the floor the later recomputes keep.
    _low_history(db_session, user)
    payload = CEFRProgressService(db_session).recompute(user, source="atelier_session_complete")
    db_session.refresh(user)
    assert user.cefr_estimate == "A2.1"
    assert payload["measured_below_floor"]["floor_source"] == "placement"


def test_an_upward_measurement_still_raises_the_level(db_session):
    from app.services import level_checkpoint as checkpoints

    user = _declared_b1(db_session)
    _half_wrong_attempts(db_session, user)
    # The learner passed the B1.1 épreuve: the evidence puts her in B1.2.
    checkpoints.credit_band(db_session, user.id, "B1.1", source=checkpoints.SOURCE_RELEASE, now=datetime.now(UTC))
    db_session.commit()

    payload = CEFRProgressService(db_session).recompute(user, source="atelier_session_complete")
    db_session.refresh(user)

    assert user.cefr_estimate == "B1.2"
    assert payload["estimate_source"] == "measured"
    assert payload["measured_below_floor"] is None
