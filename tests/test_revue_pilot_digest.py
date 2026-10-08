"""WP-119 §10c: the pilot digest's «Le Papier» line reads the close's ledger rows."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.services.pilot_events import PilotEventService
from app.services.revue.encounter import REVUE_COST_EVENT_TYPE

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pilot_digest import REVUE_EVENT_TYPE, format_revue_line  # noqa: E402


def _row(db, user_id, *, turns, guests, cost, provider="openai", at):
    PilotEventService(db).record(
        REVUE_EVENT_TYPE,
        user_id=user_id,
        entity_type="revue_session",
        entity_id=uuid4(),
        payload={"week": "2026-W40", "dossier_id": "d", "turns": turns, "guests": guests,
                 "provider": provider, "grader": "revue-rubric-v1"},
        cost_usd=cost,
        occurred_at=at,
    )


def test_the_digest_reads_the_event_type_the_close_writes():
    assert REVUE_EVENT_TYPE == REVUE_COST_EVENT_TYPE


def test_the_revue_line_prints_sessions_turns_guests_and_cost(db_session):
    user_id = uuid4()
    stamp = datetime.now(UTC)
    _row(db_session, user_id, turns=6, guests=1, cost=0.012, at=stamp)
    _row(db_session, user_id, turns=4, guests=0, cost=0.008, provider="fake", at=stamp)
    _row(db_session, user_id, turns=9, guests=1, cost=0.5, at=stamp - timedelta(days=3))  # another day
    db_session.flush()

    line = format_revue_line(db_session, stamp.date(), str(user_id))
    assert line == (
        "Le Papier (revue): 2 session(s) closed · 10 turns · 1 guest(s) · "
        "$0.0200 · $0.0100/session · fake, openai"
    )


def test_the_revue_line_says_none_on_an_empty_day(db_session):
    day = (datetime.now(UTC) - timedelta(days=400)).date()
    assert format_revue_line(db_session, day, str(uuid4())) == "Le Papier (revue): none"
