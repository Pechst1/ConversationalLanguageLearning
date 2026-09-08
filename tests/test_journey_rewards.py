"""WP-09 — the daily-journey completion keepsake.

The keepsake rides the **existing** source-unique collectible path: it is an
ordinary logo token from a new source, exactly like the mission token, so no
collection, kind, or workshop threshold changes. What these tests hold down is
the honesty of the reward: only a real completion earns one, an HTTP retry
never mints a second, and minting stays inside the caller's transaction.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.atelier import AtelierCollectible
from app.db.models.daily_journey import DailyJourney
from app.db.models.user import User
from app.services.atelier_rewards import (
    COLLECTIBLE_KINDS,
    DAILY_JOURNEY_SOURCE_KIND,
    LOGO_TOKEN,
    PLATE_SEMAINE,
    WORKSHOP_RULES,
    AtelierRewardService,
)
from app.services.journey_capabilities import (
    KEEPSAKE_EFFECT,
    journey_keepsake,
    mint_journey_keepsake,
)
from app.services.journey_contracts import JOURNEY_CONTENT_VERSION, effect_source_key


def _user(db_session: Session) -> User:
    user = User(
        id=uuid4(),
        email=f"keepsake-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _journey(db_session: Session, user: User, *, local_date: date | None = None) -> DailyJourney:
    journey = DailyJourney(
        user_id=user.id,
        local_date=local_date or date(2026, 9, 5),
        timezone="Europe/Paris",
        content_version=JOURNEY_CONTENT_VERSION,
        level_band="A1",
        status="completed",
        scenario_snapshot={
            "scenario_key": "order_at_cafe",
            "title_fr": "Un café au Mistral",
            "location_name": "Le Mistral",
            "character_name": "Margaux",
        },
    )
    db_session.add(journey)
    db_session.flush()
    return journey


def _rows(db_session: Session, journey: DailyJourney) -> list[AtelierCollectible]:
    return (
        db_session.query(AtelierCollectible)
        .filter(
            AtelierCollectible.source_ref
            == effect_source_key(journey_id=journey.id, effect=KEEPSAKE_EFFECT)
        )
        .all()
    )


# --------------------------------------------------------------------------
# 1. Who earns one
# --------------------------------------------------------------------------

def test_a_completed_journey_mints_one_keepsake(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)

    result = mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )

    assert result.minted is True
    assert result.already_minted is False
    (row,) = _rows(db_session, journey)
    assert result.collectible_ids == [str(row.id)]
    assert row.user_id == user.id
    assert row.kind == LOGO_TOKEN, "an existing kind, not a new collection"
    assert row.source_kind == DAILY_JOURNEY_SOURCE_KIND
    assert row.source_ref == f"journey:{journey.id}:keepsake"
    assert row.metadata_payload["scenario_key"] == "order_at_cafe"
    assert row.metadata_payload["scenario_title_fr"] == "Un café au Mistral"
    assert row.metadata_payload["date"] == "2026-09-05"


def test_an_early_exit_earns_no_keepsake(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)

    result = mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="early",
    )

    assert result.minted is False
    assert result.already_minted is False
    assert result.collectible_ids == []
    assert _rows(db_session, journey) == []


def test_any_non_completion_earns_no_keepsake(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)

    for completion_kind in ("", "failed", "unavailable", "ended_early", "COMPLETE"):
        result = mint_journey_keepsake(
            db_session,
            user=user,
            journey_id=journey.id,
            scenario_key="order_at_cafe",
            completion_kind=completion_kind,
        )
        assert result.minted is False, completion_kind

    assert _rows(db_session, journey) == []


def test_a_keepsake_is_never_minted_for_someone_elses_journey(db_session: Session) -> None:
    owner = _user(db_session)
    stranger = _user(db_session)
    journey = _journey(db_session, owner)

    result = mint_journey_keepsake(
        db_session,
        user=stranger,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )

    assert result.minted is False
    assert result.collectible_ids == []
    assert _rows(db_session, journey) == []


# --------------------------------------------------------------------------
# 2. Retry
# --------------------------------------------------------------------------

def test_a_retried_finish_returns_the_same_keepsake_and_never_mints_twice(
    db_session: Session,
) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)

    first = mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )
    replays = [
        mint_journey_keepsake(
            db_session,
            user=user,
            journey_id=journey.id,
            scenario_key="order_at_cafe",
            completion_kind="complete",
        )
        for _ in range(3)
    ]

    assert first.minted is True
    assert [item.minted for item in replays] == [False, False, False]
    assert [item.already_minted for item in replays] == [True, True, True]
    assert all(item.collectible_ids == first.collectible_ids for item in replays)
    assert len(_rows(db_session, journey)) == 1


def test_two_journeys_earn_two_keepsakes(db_session: Session) -> None:
    user = _user(db_session)
    monday = _journey(db_session, user, local_date=date(2026, 9, 7))
    tuesday = _journey(db_session, user, local_date=date(2026, 9, 8))

    for journey in (monday, tuesday):
        mint_journey_keepsake(
            db_session,
            user=user,
            journey_id=journey.id,
            scenario_key="order_at_cafe",
            completion_kind="complete",
        )

    assert len(_rows(db_session, monday)) == 1
    assert len(_rows(db_session, tuesday)) == 1
    assert journey_keepsake(db_session, user=user, journey_id=monday.id) is not None
    assert journey_keepsake(db_session, user=user, journey_id=tuesday.id) is not None


# --------------------------------------------------------------------------
# 3. Transaction boundary
# --------------------------------------------------------------------------

def test_minting_never_commits_the_callers_transaction(db_session: Session) -> None:
    """CONTRACTS §1/§6: the daily-journey state machine owns the commit."""

    user = _user(db_session)
    journey = _journey(db_session, user)
    source_ref = effect_source_key(journey_id=journey.id, effect=KEEPSAKE_EFFECT)

    result = mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )
    assert result.minted is True

    db_session.rollback()

    assert (
        db_session.query(AtelierCollectible)
        .filter(AtelierCollectible.source_ref == source_ref)
        .count()
        == 0
    ), "a rolled-back journey must not leave a keepsake behind"


def test_the_existing_committing_reward_paths_still_commit(db_session: Session) -> None:
    """Regression for the added ``commit`` switch on the shared mint helper."""

    user = _user(db_session)
    db_session.commit()
    service = AtelierRewardService(db_session)
    source_ref = f"legacy-effort-{uuid4().hex}"

    minted = service.mint_conversation_effort_token(
        user_id=user.id,
        source_kind="conversation",
        source_ref=source_ref,
        recovery=False,
        word_count=12,
        error_count=0,
    )
    assert len(minted) == 1

    db_session.rollback()

    assert (
        db_session.query(AtelierCollectible)
        .filter(AtelierCollectible.source_ref == source_ref)
        .count()
        == 1
    ), "the pre-existing path still owns its own commit"


# --------------------------------------------------------------------------
# 4. Existing collections and thresholds are untouched
# --------------------------------------------------------------------------

def test_collections_and_thresholds_are_unchanged(db_session: Session) -> None:
    assert COLLECTIBLE_KINDS == (
        "logo_token",
        "gilt_seal",
        "story_seal",
        "plate_semaine",
        "plate_chapter",
        "colophon",
    )
    assert WORKSHOP_RULES[PLATE_SEMAINE]["required"] == 7
    assert WORKSHOP_RULES[PLATE_SEMAINE]["member_kind"] == LOGO_TOKEN
    assert WORKSHOP_RULES["plate_chapter"]["required"] == 3
    assert WORKSHOP_RULES["colophon"]["required"] == 4


def test_the_keepsake_joins_the_existing_workshop_economy(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)
    service = AtelierRewardService(db_session)
    before = service.workshop_progress(user_id=user.id)

    mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )
    after = service.workshop_progress(user_id=user.id)

    assert before[PLATE_SEMAINE]["available"] == 0
    assert after[PLATE_SEMAINE]["available"] == 1
    assert after[PLATE_SEMAINE]["required"] == 7, "the threshold is untouched"
    assert after["plate_chapter"] == before["plate_chapter"]
    assert after["colophon"] == before["colophon"]


def test_the_keepsake_appears_in_the_existing_almanac(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)
    mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )

    almanac = AtelierRewardService(db_session).almanac(user_id=user.id)
    tokens = almanac["collectibles"][LOGO_TOKEN]

    assert sorted(almanac["collectibles"]) == sorted(COLLECTIBLE_KINDS), (
        "the almanac still groups exactly the existing kinds"
    )
    assert len(tokens) == 1
    assert tokens[0]["source_kind"] == DAILY_JOURNEY_SOURCE_KIND
    assert tokens[0]["metadata"]["source"] == "daily_journey"
    assert almanac["totals"] == {LOGO_TOKEN: 1}


def test_minted_at_is_populated_once_the_caller_commits(db_session: Session) -> None:
    user = _user(db_session)
    journey = _journey(db_session, user)
    mint_journey_keepsake(
        db_session,
        user=user,
        journey_id=journey.id,
        scenario_key="order_at_cafe",
        completion_kind="complete",
    )

    db_session.commit()
    (row,) = _rows(db_session, journey)

    assert isinstance(row.minted_at, datetime)
    assert row.minted_at.replace(tzinfo=UTC) <= datetime.now(UTC)
