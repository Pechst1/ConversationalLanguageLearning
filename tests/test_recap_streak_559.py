"""#559 — the recap prints the streak Home prints.

Live walks 6 and 7 Nov: La Forge's end sheet said «26 days in a row» (then «27»)
while Home's chip said 25 (26). The number was derived twice: the recap read the
stored column (``grammar_streak_days``) before and after the write, the chip reads
:func:`app.services.streak.read_streak`. Home also holds today's count back until
the day is done (``homeDayChip``); the recap now goes through the same client
function (``recapStreak``, ``web-frontend/lib/day-session.ts``).

The server half: the recap's «was» is the checked streak, never the stale stored
count of a chain that already broke («12 → 1»).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from app.db.models.atelier import AtelierSession
from app.db.models.user import User
from app.services.atelier import AtelierSRSService
from app.services.streak import local_today, read_streak, record_practice_day


def _user(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"recap-559-{uuid.uuid4().hex[:10]}@example.com",
        hashed_password="x",
        native_language="en",
        target_language="fr",
        timezone="Europe/Paris",
    )
    db_session.add(user)
    db_session.commit()
    return user


def _complete(db_session, user: User) -> dict:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[])
    db_session.add(session)
    db_session.commit()
    return AtelierSRSService(db_session).complete_session(session=session, user=user)


def test_recap_was_is_the_checked_streak_not_the_stale_count(db_session) -> None:
    user = _user(db_session)
    today = local_today(user)
    # A chain of 12 that stopped five days ago: the stored column still says 12.
    user.grammar_streak_days = 12
    user.grammar_last_review_date = today - timedelta(days=5)
    db_session.commit()
    assert read_streak(user).days == 0  # what Home prints this morning

    recap = _complete(db_session, user)

    assert recap["streak_before"] == 0, "the chain was already broken: «12 → 1» is not what Home showed"
    assert recap["streak_after"] == read_streak(user).days == 1


def test_recap_after_is_the_number_every_other_screen_reads(db_session) -> None:
    user = _user(db_session)
    today = local_today(user)
    for back in range(25, 0, -1):
        record_practice_day(db_session, user, on_date=today - timedelta(days=back))
    db_session.commit()
    assert read_streak(user).days == 25

    recap = _complete(db_session, user)

    assert recap["streak_before"] == 25
    assert recap["streak_after"] == read_streak(user).days == 26
