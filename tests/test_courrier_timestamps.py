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
