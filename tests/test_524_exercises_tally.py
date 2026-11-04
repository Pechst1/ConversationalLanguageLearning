"""#524 — the Done screen's «Exercises» counts every exercise answered today.

Explore walk 4 Nov: day 2 had 8 recall drills in the scene and 2 La Forge items;
Fertig said «2 Übungen». The tally read La Forge's ``AtelierAttempt`` rows only,
because the scene's recall answers are stored as journey steps, not attempts.
The day with more practice showed fewer exercises. ``daily_session.exercises_today``
is the one place that counts, and it counts both.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.user import User
from app.services import daily_session


def _learner(client: TestClient, db: Session) -> User:
    email = f"t524-{uuid.uuid4().hex[:8]}@example.com"
    password = "t524-secure-pass"
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "target_language": "fr", "native_language": "en"},
    )
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    user = db.get(User, UUID(str(decode_token(token)["sub"])))
    user.timezone = "UTC"
    db.commit()
    return user


def _journey(db: Session, user: User, *, on: datetime, steps: list[tuple[str, str, str | None]]) -> DailyJourney:
    journey = DailyJourney(user_id=user.id, local_date=on.date(), timezone="UTC", status="completed")
    db.add(journey)
    db.flush()
    for ordinal, (kind, status, evidence_ref) in enumerate(steps):
        db.add(
            DailyJourneyStep(
                journey_id=journey.id,
                ordinal=ordinal,
                kind=kind,
                status=status,
                evidence_ref=evidence_ref,
                completed_at=on if status == "completed" else None,
            )
        )
    db.flush()
    return journey


def _forge_items(db: Session, user: User, *, count: int, at: datetime) -> None:
    session = AtelierSession(
        user_id=user.id, selected_concept_ids=[], quote_payload={}, status="completed", recap_payload={}
    )
    db.add(session)
    db.flush()
    for index in range(count):
        db.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                round="recognize",
                mode="fill",
                exercise_id=f"forge:{index}",
                created_at=at,
            )
        )
    db.flush()


def test_524_the_tally_counts_recall_drills_and_forge_items(client: TestClient, db_session: Session) -> None:
    user = _learner(client, db_session)
    now = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = now - timedelta(days=1)

    # Today: the scene's 3 answered recall drills (a rule card and a drill left
    # unanswered or skipped are no exercises), then 2 La Forge items.
    _journey(
        db_session,
        user,
        on=now,
        steps=[
            ("rule", "completed", None),
            ("recall", "completed", "session_learning_moment:a"),
            ("recall", "completed", "session_learning_moment:b"),
            ("recall", "completed", "session_learning_moment:c"),
            ("recall", "skipped", None),
            ("recall", "pending", None),
            ("respond", "completed", "session_learning_moment:d"),
        ],
    )
    _forge_items(db_session, user, count=2, at=now)
    # Yesterday's practice is not today's.
    _journey(db_session, user, on=yesterday, steps=[("recall", "completed", "session_learning_moment:old")])
    _forge_items(db_session, user, count=4, at=yesterday)
    db_session.commit()

    counted = daily_session.exercises_today(db_session, user, now=now)
    assert counted == 5, f"{counted} exercises counted after 3 recall drills and 2 La Forge items"

    view = daily_session.build_session(
        db_session,
        user,
        journey=None,
        scene_done=True,
        scene_seconds=480,
        reviews_due=0,
        forge_href="/atelier?mode=forge&from=day",
        forge_blocks_today=1,
        now=now,
    )
    assert view["tally"]["exercises"] == 5, (
        f"the Done screen says {view['tally']['exercises']} Exercises after 3 recall drills and 2 La Forge items"
    )
