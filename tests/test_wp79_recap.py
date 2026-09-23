"""WP-79 — the end of the day, as a reward (backend half).

A finished day's recap carries, read and never invented: the steps done, the
words practised, the character's mood from the living story's ledger (only
when *this* day moved it), the keepsake that was minted, «La suite demain» in
WP-80's source order, and a level move shown exactly once.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.db.models.serial import SerialThread
from app.schemas.daily_journey import JourneyRecap
from app.services import achievement_recap
from app.services.achievement_recap import forward_line, recap_mood, recap_teaser, recap_words
from app.services.daily_journey import DailyJourneyService
from app.services.daily_journey_adapters import build_default_adapters
from tests.test_daily_journey_state import (  # noqa: F401 - fixture
    create_request,
    drive_to_finish,
    enabled,
    freeze,
    make_user,
)


def _service(db: Session) -> DailyJourneyService:
    return DailyJourneyService(db, build_default_adapters())


# ---------------------------------------------------------------------------
# One finished day, end to end
# ---------------------------------------------------------------------------


def test_a_finished_day_carries_every_reward_fact(db_session: Session, enabled: None) -> None:  # noqa: F811 - pytest fixture
    user = make_user(db_session, "wp79-day@example.com")
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    final = drive_to_finish(service, user, created, finish_kind="complete")

    recap = final.recap
    assert recap is not None and final.status == "completed"
    # The streak rides on the snapshot, already counting today (WP-80).
    assert final.streak is not None and final.streak.days == 1 and final.streak.today_done
    assert recap.steps_done == sum(1 for step in final.steps if step.status == "completed") > 0
    # The keepsake WP-09 minted is finally described, for the vignette.
    assert recap.collectible_ids and recap.keepsake is not None
    assert recap.keepsake.collectible_id == recap.collectible_ids[0]
    assert recap.keepsake.title_fr == created.scenario.title_fr
    assert recap.keepsake.local_date == final.local_date
    # «La suite demain»: always a line, and the source is named.
    assert recap.teaser is not None and recap.teaser.text_fr
    assert recap.teaser.source in {"engine", "resolution", "authored"}
    if recap.teaser.source == "authored":
        assert recap.teaser_fr is None, "an authored line is never passed off as the engine's"
    # The level is stored so the next recap can compare; nothing moved yet.
    assert recap.level == (user.cefr_estimate or "A1.1")
    assert recap.level_up is None
    # Persisted recaps read back through the strict model.
    JourneyRecap.model_validate(final.recap.model_dump(mode="json"))


def test_an_early_stop_mints_no_keepsake(db_session: Session, enabled: None) -> None:  # noqa: F811 - pytest fixture
    user = make_user(db_session, "wp79-early@example.com")
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    final = drive_to_finish(service, user, created, finish_kind="early")
    assert final.recap is not None
    assert final.recap.keepsake is None


def test_a_recap_written_before_wp79_still_reads() -> None:
    legacy = {
        "completion_kind": "complete",
        "objective_outcome": "met",
        "practiced_targets": [],
        "capability_evidence": [],
        "next_focus": None,
        "collectible_ids": [],
        "story_outcome": None,
        "active_seconds": None,
    }
    recap = JourneyRecap.model_validate(legacy)
    assert recap.words == [] and recap.teaser is None and recap.level_up is None


# ---------------------------------------------------------------------------
# The level move: shown once, and only on measured evidence
# ---------------------------------------------------------------------------


def test_the_level_move_appears_once(
    db_session: Session, enabled: None, monkeypatch: pytest.MonkeyPatch  # noqa: F811 - pytest fixture
) -> None:
    user = make_user(db_session, "wp79-level@example.com")
    service = _service(db_session)

    freeze(monkeypatch, datetime(2026, 9, 1, 9, 0, tzinfo=UTC))
    first, _ = service.create_journey(user, create_request())
    day1 = drive_to_finish(service, user, first, finish_kind="complete")
    assert day1.recap.level == "A1.1" and day1.recap.level_up is None

    # The CEFR engine moves the band between the two days, on measured evidence.
    user.cefr_estimate = "A1.2"
    user.cefr_estimate_payload = {
        "estimate": "A1.2",
        "estimate_source": "measured",
        "signals": {"mastered_vocabulary": 312, "mastered_grammar": 21},
    }
    db_session.commit()

    freeze(monkeypatch, datetime(2026, 9, 2, 9, 0, tzinfo=UTC))
    second, _ = service.create_journey(user, create_request())
    day2 = drive_to_finish(service, user, second, finish_kind="complete")
    move = day2.recap.level_up
    assert move is not None
    assert (move.from_level, move.to_level) == ("A1.1", "A1.2")
    assert (move.mastered_vocabulary, move.mastered_grammar) == (312, 21)

    freeze(monkeypatch, datetime(2026, 9, 3, 9, 0, tzinfo=UTC))
    third, _ = service.create_journey(user, create_request())
    day3 = drive_to_finish(service, user, third, finish_kind="complete")
    assert day3.recap.level == "A1.2"
    assert day3.recap.level_up is None, "a level move is a moment, not a banner"


def test_a_declared_level_is_not_a_level_up(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = make_user(db_session, "wp79-declared@example.com")
    user.cefr_estimate = "A2.1"
    user.cefr_estimate_payload = {"estimate": "A2.1", "estimate_source": "declared"}
    db_session.commit()
    journey = SimpleNamespace(id=uuid.uuid4(), user_id=user.id)
    monkeypatch.setattr(achievement_recap, "_previous_recap_level", lambda *a, **k: "A1.1")
    level, move = achievement_recap.recap_level(db_session, user, journey)
    assert level == "A2.1" and move is None


# ---------------------------------------------------------------------------
# The face: the mood ledger, and only today's move
# ---------------------------------------------------------------------------


def _journey(**scenario) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        scenario_snapshot={"character_id": "lila_bonnet", "character_name": "Lila", **scenario},
        steps=[],
        local_date=date(2026, 9, 22),
    )


def test_the_mood_shift_is_claimed_only_for_todays_exchange() -> None:
    journey = _journey()
    today = f"journey:{journey.id}:story"
    live = {"moods": {"lila_bonnet": {"mood": 1, "trust": 3, "last_shift": "warmer", "last_event_id": today}}}
    assert recap_mood(journey, live) == {
        "character_id": "lila_bonnet",
        "character_name": "Lila",
        "mood": 1,
        "shift": "warmer",
    }
    live["moods"]["lila_bonnet"]["last_event_id"] = "journey:someday:story"
    assert recap_mood(journey, live)["shift"] is None
    assert recap_mood(journey, {}) is None


def test_the_mood_is_read_from_the_story_state_on_finish(
    db_session: Session, enabled: None  # noqa: F811 - pytest fixture
) -> None:
    user = make_user(db_session, "wp79-mood@example.com")
    service = _service(db_session)
    created, _ = service.create_journey(user, create_request())
    character = created.scenario.character_id
    db_session.add(
        SerialThread(
            user_id=user.id,
            status="active",
            state={
                "living_story": {
                    "moods": {
                        character: {
                            "mood": 2,
                            "trust": 4,
                            "last_shift": "warmer",
                            "last_event_id": f"journey:{created.id}:story",
                        }
                    }
                }
            },
        )
    )
    db_session.commit()
    final = drive_to_finish(service, user, created, finish_kind="complete")
    mood = final.recap.mood
    assert mood is not None
    assert (mood.character_id, mood.mood, mood.shift) == (character, 2, "warmer")


# ---------------------------------------------------------------------------
# «La suite demain» — WP-80's order: engine, resolution, authored
# ---------------------------------------------------------------------------


def _resolution(line: str) -> SimpleNamespace:
    return SimpleNamespace(kind="resolution", public_prompt={"character_line_fr": line})


def test_the_teaser_prefers_the_engine_then_the_resolution_then_an_authored_line() -> None:
    user = SimpleNamespace(cefr_estimate="A1.1")
    journey = _journey()
    journey.steps = [_resolution("Merci pour tout. Je vous raconte la suite demain !")]

    engine = recap_teaser(
        user,
        journey,
        {"next_teaser": {"text_fr": "Lila a reçu une lettre étrange.", "character_id": "lila_bonnet"}},
    )
    assert engine == {
        "text_fr": "Lila a reçu une lettre étrange.",
        "character_id": "lila_bonnet",
        "character_name": "Lila",
        "source": "engine",
    }

    stale = recap_teaser(
        user,
        journey,
        {"next_teaser": {"text_fr": "Hier.", "source_event_id": "journey:other:story"}},
    )
    assert stale["source"] == "resolution"
    assert stale["text_fr"] == "Je vous raconte la suite demain !"

    journey.steps = [_resolution("Voilà votre café.")]
    authored = recap_teaser(user, journey, {})
    assert authored["source"] == "authored"
    assert authored["character_name"] == "Lila"
    from app.services.serial_notifications import MORNING_LINES

    assert authored["text_fr"] == MORNING_LINES["lila_bonnet"]["A"]


def test_a_forward_line_needs_an_explicit_marker() -> None:
    assert forward_line("Bonne journée. À demain au Mistral !") == "À demain au Mistral !"
    assert forward_line("Merci, c'était parfait.") is None
    assert forward_line("") is None


def test_words_are_the_practised_vocabulary_minus_not_yet() -> None:
    def item(kind: str, ident: str, evidence: str):
        return SimpleNamespace(
            target=SimpleNamespace(kind=kind, id=ident, label_fr=f"fr-{ident}", label_native=None),
            evidence_kind=evidence,
        )

    words = recap_words(
        [
            item("vocabulary", "1", "produced_independent"),
            item("vocabulary", "1", "recognized"),
            item("vocabulary", "2", "not_yet"),
            item("grammar", "g", "produced_supported"),
            item("vocabulary", "3", "recognized"),
        ]
    )
    assert [w["id"] for w in words] == ["1", "3"]


def test_words_kept_today_join_the_recap(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    kept_words = pytest.importorskip("app.services.kept_words")
    row = SimpleNamespace(word_id=7, word="addition", surface="l'addition", gloss="the bill")
    monkeypatch.setattr(kept_words, "kept_words_for", lambda *a, **k: [row])
    journey = SimpleNamespace(started_at=datetime(2026, 9, 22, tzinfo=UTC))
    words = achievement_recap.kept_today(db_session, SimpleNamespace(id=uuid.uuid4()), journey, set())
    assert words == [
        {"id": "7", "label_fr": "l'addition", "label_native": "the bill", "evidence_kind": "unscored"}
    ]
    assert achievement_recap.kept_today(db_session, SimpleNamespace(id=uuid.uuid4()), journey, {"7"}) == []
