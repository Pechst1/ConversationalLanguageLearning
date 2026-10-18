"""The own-words bonus belongs to free use, not to a correction (#216).

La Forge climbs a ladder per rule: tell right from wrong (unterscheiden),
build from tiles (bauen), rewrite or correct a given sentence (umformen), then
write a sentence of your own (bilden) and use it freely. The bonus token reads
«In your own words … you used today's form in a sentence of your own»; it is
true only on the last two rungs. Live walk 2026-10-18: correcting one word of
the app's own sentence («Tu est italien, Marin ?») earned it.

Root cause: ``DRAFTING_ROUNDS`` listed the rounds that are *typed* and
*graded by a model or key* instead of the rounds where the learner *composes*.
``transform`` sat in it because it is harder than a tile build, and the bonus
copy then told the learner something false about it.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierAttempt, AtelierSession
from app.db.models.user import User
from app.services.atelier_rewards import AtelierRewardService


def _user(db_session: Session) -> User:
    user = User(
        id=uuid4(),
        email=f"own-words-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="de",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _flawless_attempt(db_session: Session, user: User, *, round_name: str, mode: str) -> AtelierAttempt:
    session = AtelierSession(user_id=user.id, selected_concept_ids=[], quote_payload={})
    db_session.add(session)
    db_session.flush()
    items = [{"id": f"{mode}-{index}"} for index in range(3)]
    attempt = AtelierAttempt(
        atelier_session_id=session.id,
        user_id=user.id,
        concept_id=None,
        round=round_name,
        mode=mode,
        exercise_id=f"{round_name}-{mode}-{uuid4().hex[:6]}",
        prompt_payload={"items": items} if round_name == "recognize" else {},
        answer_payload={},
        correction_payload=(
            {"corrected_answer": {item["id"]: "x" for item in items}}
            if round_name == "recognize"
            else {"assessment_status": "checked"}
        ),
        verdict="correct",
        score_0_4=4.0,
    )
    db_session.add(attempt)
    db_session.flush()
    return attempt


def _efforts(db_session: Session, *, round_name: str, mode: str) -> list[str]:
    user = _user(db_session)
    attempt = _flawless_attempt(db_session, user, round_name=round_name, mode=mode)
    minted = AtelierRewardService(db_session).mint_logo_token_for_attempt(attempt, first_submission=True)
    return [item["metadata"]["effort"] for item in minted]


@pytest.mark.parametrize(
    ("round_name", "mode"),
    [
        ("recognize", "classify"),  # unterscheiden
        ("recognize", "word_bank"),  # bauen
        ("transform", "rewrite"),  # umformen: correct the one error in a given sentence
    ],
)
def test_no_own_words_bonus_below_free_use(db_session: Session, round_name: str, mode: str) -> None:
    assert "drafting" not in _efforts(db_session, round_name=round_name, mode=mode), (
        f"{round_name}/{mode} is not the learner composing a sentence: no «In your own words» bonus"
    )


@pytest.mark.parametrize(
    ("round_name", "mode"),
    [("sentence", "sentence"), ("conversation", "conversation")],
)
def test_own_words_bonus_on_bilden_and_free_use(db_session: Session, round_name: str, mode: str) -> None:
    assert _efforts(db_session, round_name=round_name, mode=mode) == ["drafting"]
