"""#316: the Courrier's message times must leave the server marked as UTC."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

from app.api.v1.endpoints.missions import _attempt_read, _turn_read
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn
from app.services.missions import serialize_mission

# What a naive column (SQLite, or any DateTime without a zone) hands back.
NAIVE = datetime(2026, 10, 24, 2, 6, 0)


def _mission() -> RealWorldMission:
    mission = RealWorldMission(
        id=uuid4(),
        user_id=uuid4(),
        cadence="ad_hoc",
        mission_type="message",
        title="Service client",
        brief="Ask for the address.",
        selected_concept_ids=[],
        target_errata_ids=[],
        target_vocabulary_ids=[],
        source_snapshot={},
        objectives=[],
        prompt_payload={},
        recap_payload={},
        status="in_progress",
    )
    mission.created_at = NAIVE
    mission.started_at = NAIVE
    return mission


def _stamps() -> dict[str, str | None]:
    turn = RealWorldMissionTurn(id=uuid4(), turn_index=1, role="user", mode="chat", text="Bonjour")
    turn.created_at = NAIVE
    attempt = RealWorldMissionAttempt(id=uuid4(), mode="writing", verdict="ok")
    attempt.created_at = NAIVE
    mission = _mission()
    mission.turns = [turn]
    mission.attempts = [attempt]
    payload = serialize_mission(mission)
    return {
        "endpoint turn": _turn_read(turn)["created_at"],
        "endpoint attempt": _attempt_read(attempt)["created_at"],
        "mission created_at": payload["created_at"],
        "mission started_at": payload["started_at"],
        "mission turn": payload["turns"][0]["created_at"],
        "mission attempt": payload["attempts"][0]["created_at"],
    }


def test_courrier_stamps_say_they_are_utc():
    """A naive stamp printed as «2026-10-24T02:06:00» is read by the browser as
    its own clock, so a Berlin learner saw «02 h 06» at 04:06."""
    for where, stamp in _stamps().items():
        parsed = datetime.fromisoformat(stamp)
        assert parsed.utcoffset() == timedelta(0), f"{where}: {stamp!r} carries no UTC marker"
        assert parsed == datetime(2026, 10, 24, 2, 6, tzinfo=UTC), where


def test_utc_iso_keeps_an_aware_stamp_and_marks_a_naive_one():
    from app.utils.timestamps import utc_iso

    assert utc_iso(None) is None
    assert utc_iso(NAIVE) == "2026-10-24T02:06:00+00:00"
    berlin = datetime(2026, 10, 24, 4, 6, tzinfo=timezone(timedelta(hours=2)))
    assert utc_iso(berlin) == "2026-10-24T02:06:00+00:00"


# ---------------------------------------------------------------------------
# #397: the thread reads in the order of its stored times, and a turn is stamped
# when it is written.
# ---------------------------------------------------------------------------


def _turn(index: int, role: str, at: datetime) -> RealWorldMissionTurn:
    turn = RealWorldMissionTurn(id=uuid4(), turn_index=index, role=role, mode="chat", text=f"t{index}")
    turn.created_at = at
    return turn


def test_the_thread_is_listed_by_stored_time_newest_last():
    """#397: the page printed 02 h 58, 02 h 57, 03 h 11, 03 h 02, 02 h 57 down the thread:
    it sorted by the turn counter and ignored the stored time it prints."""
    base = datetime(2026, 10, 31, 2, 57, 0)
    mission = _mission()
    mission.turns = [
        _turn(1, "assistant", base + timedelta(minutes=1)),
        _turn(2, "user", base),
        _turn(3, "assistant", base + timedelta(minutes=14)),
        _turn(4, "user", base + timedelta(minutes=5)),
        _turn(5, "assistant", base),
    ]
    attempt_late = RealWorldMissionAttempt(id=uuid4(), mode="writing", verdict="ok")
    attempt_late.created_at = base + timedelta(minutes=9)
    attempt_early = RealWorldMissionAttempt(id=uuid4(), mode="writing", verdict="ok")
    attempt_early.created_at = base
    mission.attempts = [attempt_late, attempt_early]

    payload = serialize_mission(mission)

    stamps = [datetime.fromisoformat(turn["created_at"]) for turn in payload["turns"]]
    assert stamps == sorted(stamps), [turn["created_at"] for turn in payload["turns"]]
    # Equal times (a second-resolution column) keep the turn counter's order.
    assert [turn["turn_index"] for turn in payload["turns"]][:2] == [2, 5]
    attempt_stamps = [datetime.fromisoformat(item["created_at"]) for item in payload["attempts"]]
    assert attempt_stamps == sorted(attempt_stamps)


def test_a_turn_is_stamped_when_it_is_written(db_session):
    """#397: a stamp the database sets is the time its transaction began, so a reply
    written after a slow correction was stamped before it. The writer stamps it."""
    from app.db.models.user import User

    user = User(
        id=uuid4(),
        email=f"stamp-{uuid4().hex}@example.com",
        hashed_password="test",
        native_language="en",
        target_language="fr",
        proficiency_level="A1",
    )
    db_session.add(user)
    mission = _mission()
    mission.user_id = user.id
    mission.created_at = None
    mission.started_at = None
    db_session.add(mission)
    db_session.commit()

    stamps = []
    for index in (1, 2, 3):
        turn = RealWorldMissionTurn(
            mission_id=mission.id, user_id=user.id, turn_index=index, role="user", mode="chat", text=f"t{index}"
        )
        db_session.add(turn)
        db_session.commit()
        db_session.refresh(turn)
        stamps.append(turn.created_at)

    assert stamps[0] < stamps[1] < stamps[2], stamps
