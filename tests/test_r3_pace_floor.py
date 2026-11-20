"""Round 3 (walk 2, 17 Nov 2026) — Home's minutes stay true after day 1.

The second walk's players answered a deck card every 1.6–2.4 s and a La Forge
item every ~10 s (median gap, read from the walk databases). PR 909 used those
paces as they were, so Home said «Grammatik 2 Min.» and «Wörter 1 Min.» against
about 9 and 6 real minutes, and «30 mots · 1 min» on day 6. A measured pace now
needs 20 items over two days, is the median, is clamped to [½, 3×] the default,
and a step is never quoted below a minute per 6 cards or per 2 La Forge items.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.progress import ReviewLog, UserVocabularyProgress
from app.db.models.user import User
from app.db.models.vocabulary import VocabularyWord
from app.services.daily_session import SessionInputs, session_view

NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


def _inputs(**overrides) -> SessionInputs:
    values = {
        "pace": "normal",
        "scene_done": False,
        "scene_seconds": 480,
        "quota": 15,
        "introduced": 0,
        "reviews_due": 15,
        "words_marked_done": False,
        "forge_seconds": 300,
        "forge_blocks_today": 0,
        "forge_href": "/atelier?concept=1",
        "exercises_today": 0,
        "forge_max_items": 8,
        "deck": (15, 15),
    }
    values.update(overrides)
    return SessionInputs(**values)


def _minutes(view: dict, kind: str) -> int:
    return next(step["minutes"] for step in view["steps"] if step["kind"] == kind)


def _learner(db: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"r3-pace-{uuid.uuid4().hex}@example.com",
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


def _forge(db: Session, user: User, *, days_back: int, gaps: list[float]) -> None:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], status="completed", quote_payload={}, recap_payload={})
    db.add(session)
    db.flush()
    clock = NOW - timedelta(days=days_back)
    for index, gap in enumerate([0.0, *gaps]):
        clock += timedelta(seconds=gap)
        db.add(
            AtelierAttempt(
                atelier_session_id=session.id,
                user_id=user.id,
                round="forge",
                mode="fill",
                exercise_id=f"r3-pace:{days_back}:{index}",
                prompt_payload={},
                answer_payload={},
                correction_payload={},
                verdict="correct",
                score_0_4=4.0,
                created_at=clock,
            )
        )
    db.flush()


def _deck(db: Session, user: User, *, days_back: int, cards: int, seconds_per_card: float) -> None:
    clock = NOW - timedelta(days=days_back, hours=2)
    for _index in range(cards):
        word = VocabularyWord(
            word=f"r3mot{uuid.uuid4().hex[:8]}",
            normalized_word=f"r3mot{uuid.uuid4().hex[:8]}",
            language="fr",
            english_translation="x",
            frequency_rank=100,
        )
        db.add(word)
        db.flush()
        progress = UserVocabularyProgress(user_id=user.id, word_id=word.id, reps=1, state="learning")
        db.add(progress)
        db.flush()
        db.add(ReviewLog(progress_id=progress.id, rating=2, source="drill", format="flashcard", review_date=clock))
        clock += timedelta(seconds=seconds_per_card)
    db.flush()


def test_the_walk_s_two_seconds_a_card_still_quotes_the_floor(db_session: Session) -> None:
    """The walk's own paces (cards at 2 s, La Forge at 10 s, five days of them)."""

    from app.services.day_pace import day_pace

    user = _learner(db_session)
    for back in range(1, 6):
        _deck(db_session, user, days_back=back, cards=17, seconds_per_card=2.0)
        _forge(db_session, user, days_back=back, gaps=[10.0] * 7)
    pace = day_pace(db_session, user, now=NOW)
    assert {"forge", "words"} <= pace.measured
    view = session_view(_inputs(deck=(15, 15), pace_per_step=pace))
    # 15 new at the 10 s floor + 15 reviews at 5 s = 225 s, but never under a
    # minute per 6 cards: 30 cards are at least 5 minutes, not «1 min».
    assert _minutes(view, "words") >= 5
    # Eight items at the 24 s floor, never under a minute per two: 4 minutes, not «2».
    assert _minutes(view, "grammar") >= 4
    # Seventeen cards (the A1 walk's days 2–4) are at least 3 minutes, not «1».
    assert _minutes(session_view(_inputs(deck=(15, 2), pace_per_step=pace)), "words") >= 3


def test_a_plausible_human_pace_is_quoted_within_a_fifth(db_session: Session) -> None:
    from app.services.day_pace import day_pace

    user = _learner(db_session)
    for back in (1, 2, 3):
        _deck(db_session, user, days_back=back, cards=16, seconds_per_card=14.0)
        _forge(db_session, user, days_back=back, gaps=[55.0] * 7)
    pace = day_pace(db_session, user, now=NOW)
    assert {"forge", "words"} <= pace.measured
    view = session_view(_inputs(deck=(15, 15), pace_per_step=pace))
    real_words = 30 * 14.0
    real_grammar = 8 * 55.0
    assert abs(_minutes(view, "words") * 60 - real_words) <= 0.2 * real_words
    assert abs(_minutes(view, "grammar") * 60 - real_grammar) <= 0.2 * real_grammar


def test_one_day_of_evidence_is_not_a_pace(db_session: Session) -> None:
    from app.services.day_pace import DEFAULT_FORGE_SECONDS_PER_ITEM, day_pace

    user = _learner(db_session)
    _deck(db_session, user, days_back=1, cards=40, seconds_per_card=2.0)
    _forge(db_session, user, days_back=1, gaps=[10.0] * 30)
    pace = day_pace(db_session, user, now=NOW)
    assert "words" not in pace.measured and "forge" not in pace.measured
    assert pace.forge_seconds_per_item == DEFAULT_FORGE_SECONDS_PER_ITEM


def test_the_pace_is_the_median_not_the_mean(db_session: Session) -> None:
    """A few slow items (a card read twice, a long verdict) do not drag the quote."""

    from app.services.day_pace import day_pace

    user = _learner(db_session)
    for back in (1, 2):
        _forge(db_session, user, days_back=back, gaps=[40.0] * 10 + [170.0] * 4)
    pace = day_pace(db_session, user, now=NOW)
    assert pace.forge_seconds_per_item == 40.0


def test_home_s_day_figure_is_the_sum_of_its_steps() -> None:
    view = session_view(_inputs())
    shown = [step["minutes"] for step in view["steps"] if step["state"] != "done"]
    assert view["minutes_left"] == sum(shown)
