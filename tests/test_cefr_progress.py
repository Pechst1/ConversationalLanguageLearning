"""Tests for the visible CEFR progress engine."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.db.models.grammar import UserGrammarProgress
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.services.cefr_progress import DECLARED_LEVEL_EVIDENCE_ATTEMPTS, CEFRProgressService


def _user(
    db_session,
    *,
    email: str = "cefr@example.com",
    estimate: str = "A1.1",
    proficiency_level: str = "A1",
) -> User:
    # The declared level is a floor on the estimate until the app has seen enough
    # work to argue (see test_declared_level_*), so tests about measurement keep
    # it at the bottom of the scale on purpose.
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level=proficiency_level,
        cefr_estimate=estimate,
        cefr_target_level="A2.1",
        daily_goal_minutes=20,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_cefr_recompute_does_not_regress_from_single_weak_day(db_session):
    user = _user(db_session, email="cefr-smooth@example.com", estimate="A1.2")

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["computed_estimate"] == "A1.1"
    assert payload["estimate"] == "A1.2"
    assert payload["target"] == "A2.1"


def test_cefr_recompute_exposes_threshold_breakdown_and_forecast(db_session):
    user = _user(db_session, email="cefr-forecast@example.com", estimate="A1.1")
    now = datetime.now(UTC)
    for index in range(300):
        db_session.add(
            UserVocabularyProgress(
                user_id=user.id,
                word_id=index + 1,
                state="mastered",
                proficiency_score=95,
                mastered_date=now - timedelta(days=index % 10),
                updated_at=now - timedelta(days=index % 10),
            )
        )
    for index in range(20):
        db_session.add(
            UserGrammarProgress(
                user_id=user.id,
                concept_id=index + 1,
                state="gemeistert",
                score=8.5,
                updated_at=now - timedelta(days=index % 10),
            )
        )
    mission = RealWorldMission(
        user_id=user.id,
        status="completed",
        cadence="ad_hoc",
        mission_type="message",
        title="Forecast fixture",
        brief="Reply clearly.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={},
        recap_payload={},
    )
    db_session.add(mission)
    db_session.flush()
    for day in range(7):
        db_session.add(
            RealWorldMissionAttempt(
                mission_id=mission.id,
                user_id=user.id,
                mode="chat",
                answer_payload={"text": "D'accord."},
                correction_payload={},
                verdict="passed",
                score_0_4=3.1,
                created_at=now - timedelta(days=day),
            )
        )
    db_session.commit()

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["estimate"] == "A1.2"
    assert payload["breakdown"]["vocabulary"]["current"] == 300
    assert payload["breakdown"]["grammar"]["current"] == 20
    assert payload["forecast"]["status"] == "available"
    assert payload["forecast"]["target"] == "A2.1"
    assert payload["today_delta"]["attempts"] >= 1


def test_declared_level_holds_until_the_app_has_seen_enough_work(db_session):
    """A self-declared B1 must not be told they are A1.1 on day one.

    With an empty database the threshold walk can only return A1.1, which says
    nothing about the learner and everything about the app never having met them.
    """
    user = _user(db_session, email="cefr-declared@example.com", proficiency_level="B1")

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["computed_estimate"] == "A1.1"
    assert payload["estimate"] == "B1.1"
    assert payload["estimate_source"] == "declared"
    assert payload["declared_level"] == "B1.1"
    # The counters only measure in-app evidence, so they must not be presented
    # as a verified measure of a level the app has not tested.
    assert payload["breakdown"]["status"] == "unverified"


def test_declared_level_never_lowers_a_measured_estimate(db_session):
    """The declaration is a floor, not a cap."""
    user = _user(db_session, email="cefr-floor@example.com", estimate="A2.2", proficiency_level="A1")

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["estimate"] == "A2.2"
    assert payload["estimate_source"] == "measured"


def test_measurement_overrides_the_declaration_once_evidence_exists(db_session):
    """After enough real attempts the app is entitled to disagree, downwards."""
    from app.db.models.atelier import AtelierAttempt, AtelierSession

    user = _user(db_session, email="cefr-evidence@example.com", proficiency_level="B1")
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed")
    db_session.add(session)
    db_session.flush()
    now = datetime.now(UTC)
    for index in range(DECLARED_LEVEL_EVIDENCE_ATTEMPTS + 2):
        db_session.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                concept_id=None,
                round="recognize",
                mode="fill",
                exercise_id=f"evidence-{index}",
                verdict="incorrect",
                score_0_4=1,
                created_at=now - timedelta(days=1),
            )
        )
    db_session.commit()

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["estimate_source"] == "measured"
    assert payload["estimate"] == "A1.1"
    assert payload["breakdown"]["status"] == "measured"


def test_unknown_declaration_is_ignored(db_session):
    user = _user(db_session, email="cefr-unknown@example.com", proficiency_level="")

    payload = CEFRProgressService(db_session).recompute(user, source="test")

    assert payload["declared_level"] is None
    assert payload["estimate_source"] == "measured"
