"""Tests for the visible CEFR progress engine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.models.grammar import UserGrammarProgress
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt
from app.db.models.progress import UserVocabularyProgress
from app.db.models.user import User
from app.services.cefr_progress import CEFRProgressService


def _user(db_session, *, email: str = "cefr@example.com", estimate: str = "A1.1") -> User:
    user = User(
        id=uuid4(),
        email=email,
        hashed_password="x",
        native_language="en",
        target_language="fr",
        proficiency_level="A2",
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
    now = datetime.now(timezone.utc)
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
