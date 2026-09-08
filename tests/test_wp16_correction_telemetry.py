"""WP-16 §5 — the Séance correction has a bound and a cost row.

Two gaps WP-15 recorded and could not close inside its own files:

* the learner answer went to the paid checker with no length cap at all, so
  request size was learner-controlled;
* the correction call kept no usage metadata, so
  ``PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD`` did not cover the most-used paid
  endpoint in the app and ``pilot_digest`` had nothing to print.

Both are closed by narrow additive edits at the correction call site.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.db.models.pilot_event import PilotEvent
from app.services.atelier import (
    ATELIER_LLM_ANSWER_MAX_CHARS,
    AtelierCorrectionService,
)

# --------------------------------------------------------------------------
# 1. The answer bound
# --------------------------------------------------------------------------

def test_a_real_answer_is_never_cut():
    """The cap is generous: a long integrated-writing answer passes whole."""

    text = "Une phrase correcte. " * 60 + "Mais je exercer mon français."
    assert len(text) < ATELIER_LLM_ANSWER_MAX_CHARS
    block = AtelierCorrectionService._compact_llm_answer({"text": text})
    assert block["text"] == text
    assert "truncated" not in block


def test_an_unbounded_answer_is_cut_to_the_cap_and_declared():
    text = "a" * (ATELIER_LLM_ANSWER_MAX_CHARS * 3)
    block = AtelierCorrectionService._compact_llm_answer({"text": text})
    assert len(block["text"]) == ATELIER_LLM_ANSWER_MAX_CHARS
    assert block["truncated"] is True


def test_keyed_answers_share_one_budget():
    answers = {f"item-{index}": "b" * 1500 for index in range(5)}
    block = AtelierCorrectionService._compact_llm_answer({"answers": answers})
    total = sum(len(value) for value in block["answers"].values())
    assert total == ATELIER_LLM_ANSWER_MAX_CHARS
    assert block["truncated"] is True


def test_the_truncation_reaches_the_service_flag(db_session):
    service = AtelierCorrectionService(db_session)
    assert service._answer_truncated is False
    service._llm_answer_block({"text": "court"})
    assert service._answer_truncated is False
    service._llm_answer_block({"text": "c" * (ATELIER_LLM_ANSWER_MAX_CHARS + 1)})
    assert service._answer_truncated is True


# --------------------------------------------------------------------------
# 2. The cost row
# --------------------------------------------------------------------------

def _result(**overrides):
    base = {
        "provider": "openai",
        "model": "gpt-5-mini",
        "content": "{}",
        "prompt_tokens": 1200,
        "completion_tokens": 340,
        "total_tokens": 1540,
        "cost": 0.00231,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_a_correction_call_writes_one_priced_pilot_event(db_session):
    service = AtelierCorrectionService(db_session)
    user_id = uuid4()
    session_id = uuid4()
    service._cost_user_id = user_id
    service._cost_session_id = session_id

    service._record_correction_cost(_result())
    db_session.flush()

    rows = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == "atelier_correction", PilotEvent.user_id == user_id)
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.cost_usd == pytest.approx(0.00231)
    assert row.entity_type == "atelier_session"
    assert row.entity_id == str(session_id)
    assert row.payload["model"] == "gpt-5-mini"
    assert row.payload["total_tokens"] == 1540
    assert row.payload["answer_truncated"] is False


def test_a_provider_that_reports_no_cost_still_makes_the_call_visible(db_session):
    service = AtelierCorrectionService(db_session)
    user_id = uuid4()
    service._cost_user_id = user_id
    service._cost_session_id = uuid4()

    service._record_correction_cost(_result(cost=None))
    db_session.flush()

    row = (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == "atelier_correction", PilotEvent.user_id == user_id)
        .one()
    )
    assert row.cost_usd == 0.0
    assert row.payload["prompt_tokens"] == 1200


def test_telemetry_never_breaks_a_correction(db_session):
    """A broken cost row must not cost the learner their check."""

    service = AtelierCorrectionService(db_session)
    service._cost_user_id = "not-a-uuid"
    service._cost_session_id = None
    service._record_correction_cost(_result())  # must not raise


# --------------------------------------------------------------------------
# 3. The digest line item
# --------------------------------------------------------------------------

def test_the_digest_prints_calls_tokens_and_money(db_session):
    import sys
    from datetime import UTC, date, datetime
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from pilot_digest import format_correction_line

    user_id = uuid4()
    day = date.today()
    service = AtelierCorrectionService(db_session)
    service._cost_user_id = user_id
    service._cost_session_id = uuid4()
    service._record_correction_cost(_result())
    service._answer_truncated = True
    service._record_correction_cost(_result(cost=0.001))
    for row in (
        db_session.query(PilotEvent)
        .filter(PilotEvent.event_type == "atelier_correction", PilotEvent.user_id == user_id)
        .all()
    ):
        row.occurred_at = datetime.now(UTC)
    db_session.flush()

    line = format_correction_line(db_session, day, str(user_id))
    assert line.startswith("Séance corrections: 2 calls")
    assert "3080 tokens" in line
    assert "$0.0033" in line
    assert "gpt-5-mini" in line
    assert "1 answer(s) truncated" in line


def test_the_digest_says_none_on_a_day_with_no_corrections(db_session):
    import sys
    from datetime import date, timedelta
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from pilot_digest import format_correction_line

    assert format_correction_line(
        db_session, date.today() - timedelta(days=400), str(uuid4())
    ) == "Séance corrections: none"
