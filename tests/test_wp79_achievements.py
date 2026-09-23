"""WP-79 — every achievement that is listed can be earned by a test learner.

Before WP-79, 19 of 20 could not: their fields were never written. This walks
one learner through the real writers — a finished journey, the practice
streak, an answered letter, a kept Lexique, a closed chapter — and checks the
whole catalogue unlocks, each from its own row, and that nothing unlocks early.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models.achievement import Achievement
from app.db.models.daily_journey import DailyJourney
from app.db.models.mission import RealWorldMission
from app.db.models.progress import UserVocabularyProgress
from app.db.models.serial import SerialThread
from app.db.models.vocabulary import VocabularyWord
from app.services.achievement import CATALOGUE, CATALOGUE_KEYS, AchievementService
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from app.services.streak import record_practice_day
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    drive_to_finish,
    enabled,
    make_user,
)


def _unlock(db: Session, user) -> set[str]:
    return {row.achievement_key for row in AchievementService(db).check_and_unlock(user=user)}


def _completed_days(db: Session, user, count: int, first: date) -> None:
    for offset in range(count):
        db.add(
            DailyJourney(
                user_id=user.id,
                local_date=first + timedelta(days=offset),
                status="completed",
                scenario_snapshot={},
            )
        )
    db.commit()


def test_every_listed_achievement_is_reachable(db_session: Session, enabled: None) -> None:  # noqa: F811 - pytest fixture
    user = make_user(db_session, "wp79-reach@example.com")
    service = AchievementService(db_session)
    assert _unlock(db_session, user) == set(), "a new learner has earned nothing"

    # first_scene — one real finished day, through the journey state machine.
    journeys = DailyJourneyService(db_session, build_default_adapters())
    created, _ = journeys.create_journey(user, create_request())
    finished = drive_to_finish(journeys, user, created, finish_kind="complete")
    db_session.commit()
    assert _unlock(db_session, user) == {"first_scene"}

    # scenes_10 — nine more completed days.
    _completed_days(db_session, user, 9, date(2026, 1, 1))
    assert _unlock(db_session, user) == {"scenes_10"}

    # session_streak_3 / 7 / 30 — the practice streak WP-80 records. The
    # finished journey already counted today, so tomorrow makes two.
    start = finished.local_date + timedelta(days=1)
    for offset in range(29):
        record_practice_day(db_session, user, on_date=start + timedelta(days=offset))
        if offset == 0:
            db_session.commit()
            assert _unlock(db_session, user) == set(), "two days is not three"
    db_session.commit()
    assert _unlock(db_session, user) == {"session_streak_3", "session_streak_7", "session_streak_30"}

    # first_letter — an answered Courrier letter.
    db_session.add(
        RealWorldMission(
            user_id=user.id, status="completed", title="Une lettre", brief="Répondre à Marin."
        )
    )
    db_session.commit()
    assert _unlock(db_session, user) == {"first_letter"}

    # words_kept_50 — fifty words in the learner's own Lexique; 49 is not 50.
    for i in range(50):
        word = VocabularyWord(
            language="fr",
            word=f"reach{i}",
            normalized_word=f"reach{i}",
            english_translation=f"r{i}",
            frequency_rank=i + 1,
        )
        db_session.add(word)
        db_session.flush()
        db_session.add(UserVocabularyProgress(user_id=user.id, word_id=word.id, state="new"))
        if i == 48:
            db_session.commit()
            assert _unlock(db_session, user) == set()
    db_session.commit()
    assert _unlock(db_session, user) == {"words_kept_50"}

    # first_chapter — the living story closed a chapter (its chronicle row).
    db_session.add(
        SerialThread(
            user_id=user.id,
            status="active",
            state={"living_story": {"chronicle": [{"chapter": 1, "summary_fr": "Le radiateur."}]}},
        )
    )
    db_session.commit()
    assert _unlock(db_session, user) == {"first_chapter"}

    earned = {item.achievement_key for item in service.get_user_achievements(user.id) if item.completed}
    assert earned == set(CATALOGUE_KEYS), "every listed achievement was reached"


def test_the_catalogue_is_small_honest_and_seeded_idempotently(db_session: Session) -> None:
    service = AchievementService(db_session)
    service.ensure_catalogue()
    service.ensure_catalogue()
    rows = db_session.query(Achievement).filter(Achievement.achievement_key.in_(CATALOGUE_KEYS)).all()
    assert sorted(row.achievement_key for row in rows) == sorted(CATALOGUE_KEYS), "one row each"
    assert [row.achievement_key for row in service.list_all_achievements()] == [i.key for i in CATALOGUE]
    assert len(CATALOGUE) <= 10
    for item in CATALOGUE:
        assert item.measure in {"scenes", "streak", "letters", "words", "chapters"}
        assert item.xp_reward == 0
    # The retired, unreachable ones are gone from the catalogue.
    for retired in ("xp_bronze", "accuracy_perfectionist", "review_champion", "vocabulary_learner"):
        assert retired not in CATALOGUE_KEYS


def test_the_seed_script_uses_the_same_catalogue() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "seed_achievements.py"
    spec = importlib.util.spec_from_file_location("seed_achievements_wp79", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert [item.key for item in module.get_default_achievements()] == [item.key for item in CATALOGUE]


def test_an_unknown_learner_id_reads_no_progress(db_session: Session) -> None:
    items = AchievementService(db_session).get_user_achievements(uuid.uuid4(), include_locked=True)
    assert all(item.current_progress == 0 and not item.completed for item in items)
