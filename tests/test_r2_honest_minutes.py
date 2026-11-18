"""R2 (7) — Home's minutes are the learner's real ones.

Walk 2026-11-17: Home quoted «Grammatik 4» for La Forge's 8 items, which the A1
learner played in 6–7 minutes (25 s an item quoted, ~48 s played); a B1 day quoted
«8 min · + mots ≈ 5 min» took about 25. The quote now reads each step at the
learner's measured pace (the scene from the journey step timestamps, La Forge
from ``measured_seconds_per_drill``, the deck from the seconds between answers)
and otherwise at defaults calibrated to the walk.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.daily_session import SessionInputs, session_view

NOW = datetime(2026, 11, 18, 9, 0, tzinfo=UTC)


def _inputs(**overrides) -> SessionInputs:
    values = {
        "pace": "normal",
        "scene_done": False,
        "scene_seconds": 480,
        "quota": 15,
        "introduced": 0,
        "reviews_due": 5,
        "words_marked_done": False,
        "forge_seconds": 300,
        "forge_blocks_today": 0,
        "forge_href": "/atelier?concept=1",
        "exercises_today": 0,
        "forge_max_items": 8,
        "deck": (15, 5),
    }
    values.update(overrides)
    return SessionInputs(**values)


def _minutes_of(view: dict, kind: str) -> int:
    return next(step["minutes"] for step in view["steps"] if step["kind"] == kind)


def test_a_new_learner_s_forge_quote_is_the_walk_s_pace() -> None:
    """Eight items at the calibrated 48 s: «7 Min.», not the «4» the walk saw become 6–7."""

    view = session_view(_inputs())
    assert _minutes_of(view, "grammar") == 7
    # 15 new cards at 20 s and 5 reviews at 10 s.
    assert _minutes_of(view, "words") == 6
    assert _minutes_of(view, "scene") == 8


def _learner(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"r2-pace-{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
        timezone="UTC",
        daily_pace="normal",
    )
    db.add(user)
    db.flush()
    return user


def _played_day(db: Session, user: User, day: date, *, estimated: list[int], played: list[int]) -> None:
    """An ended day whose core steps were estimated and played as given (seconds)."""

    journey = DailyJourney(
        id=uuid.uuid4(),
        user_id=user.id,
        local_date=day,
        timezone="UTC",
        status="completed",
        budget_seconds=600,
        plan_selection={},
        created_at=datetime.combine(day, datetime.min.time(), tzinfo=UTC),
    )
    db.add(journey)
    db.flush()
    clock = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=8)
    for ordinal, (estimate, seconds) in enumerate(zip(estimated, played, strict=True)):
        db.add(
            DailyJourneyStep(
                journey_id=journey.id,
                ordinal=ordinal,
                kind=("scene", "respond", "resolution")[ordinal % 3],
                status="completed",
                estimated_seconds=estimate,
                started_at=clock,
                completed_at=clock + timedelta(seconds=seconds),
            )
        )
        clock += timedelta(seconds=seconds)
    # A folded La Forge block is an extension: never part of the scene's pace.
    db.add(
        DailyJourneyStep(
            journey_id=journey.id,
            ordinal=len(estimated),
            kind="forge",
            status="completed",
            estimated_seconds=60,
            started_at=clock,
            completed_at=clock + timedelta(seconds=900),
        )
    )
    db.flush()


def _forge_seance(db: Session, user: User, *, items: int, seconds_per_item: int, days_back: int = 1) -> None:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed", quote_payload={}, recap_payload={})
    db.add(session)
    db.flush()
    start = NOW - timedelta(days=days_back)
    for index in range(items):
        db.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                round="forge",
                mode="cloze",
                exercise_id=f"r2-pace:{index}",
                prompt_payload={},
                answer_payload={},
                correction_payload={},
                verdict="correct",
                score_0_4=4.0,
                created_at=start + timedelta(seconds=index * seconds_per_item),
            )
        )
    db.flush()


def _deck_answers(db: Session, user: User, *, cards: int, seconds_per_card: int, days_back: int = 1) -> None:
    start = NOW - timedelta(days=days_back, hours=2)
    for index in range(cards):
        word = VocabularyWord(
            word=f"r2mot{uuid.uuid4().hex[:6]}",
            normalized_word=f"r2mot{index}{uuid.uuid4().hex[:6]}",
            language="fr",
            english_translation="x",
            frequency_rank=100,
        )
        db.add(word)
        db.flush()
        progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, reps=1, state="learning")
        db.add(progress)
        db.flush()
        db.add(
            ReviewLog(
                progress_id=progress.id,
                rating=3,
                source="drill",
                format="flashcard",
                review_date=start + timedelta(seconds=index * seconds_per_card),
            )
        )
    db.flush()


def test_a_measured_learner_is_quoted_within_a_fifth_of_their_own_steps(db_session: Session) -> None:
    from app.services.day_pace import day_pace

    user = _learner(db_session)
    # Three ended days: scenes estimated 600 s, played 900 s (1.5×).
    for back in (1, 2, 3):
        _played_day(db_session, user, NOW.date() - timedelta(days=back), estimated=[200, 200, 200], played=[300, 300, 300])
    # La Forge: an item every 55 s. The deck: a card every 16 s. Round 3: over two days.
    for back in (1, 2):
        _forge_seance(db_session, user, items=12, seconds_per_item=55, days_back=back)
        _deck_answers(db_session, user, cards=12, seconds_per_card=16, days_back=back)

    pace = day_pace(db_session, user, now=NOW)
    assert pace.measured == frozenset({"scene", "forge", "words"})

    scene_estimate, items, new, reviews = 600, 8, 15, 5
    measured = scene_estimate * 1.5 + items * 55 + (new + reviews) * 16
    view = session_view(_inputs(scene_seconds=scene_estimate, deck=(new, reviews), pace_per_step=pace))
    quoted = view["minutes_left"] * 60
    assert abs(quoted - measured) <= 0.2 * measured, (quoted, measured)
    # The day itself is the same size: eight items, twenty cards.
    assert next(step for step in view["steps"] if step["kind"] == "grammar")["count"] == items
    assert next(step for step in view["steps"] if step["kind"] == "words")["count"] == new + reviews


def test_an_unmeasured_learner_gets_the_defaults(db_session: Session) -> None:
    from app.services.day_pace import DEFAULT_PACE, day_pace

    user = _learner(db_session)
    pace = day_pace(db_session, user, now=NOW)
    assert pace == DEFAULT_PACE
    assert pace.measured == frozenset()
