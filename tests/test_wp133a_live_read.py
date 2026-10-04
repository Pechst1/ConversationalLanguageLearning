"""WP-133a: the early capped baseline read of generated days (owner-approved, US$3 in all).

A thin wrapper over the owner's season report (``tests/test_season_one.py::
test_write_the_first_days_for_the_owner``). It adds what the report does not keep:
- for each lost day, the guard reason (from the authored-fallback marker's log line);
- for each draft the director wrote, whether it carried today's rule
  (``grammar_plan.introduce``): how often the cast says it, and whether the question invites it.

Run one band at a time, with a hard cap per band (the report's own ``_live_model`` guard):

    WP133A_OUT=<dir> SEASON_REPORT=<dir>/A1.md SEASON_REPORT_LIVE=1 SEASON_REPORT_MAX_USD=1.0 \
    SEASON_REPORT_DAYS=10 SEASON_REPORT_BAND=A1.1 python -m pytest tests/test_wp133a_live_read.py -q -s

Skipped unless ``WP133A_OUT`` is set: never part of the suite.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from app.services import living_story as engine
from tests import test_season_one as season_suite

assembled_client = season_suite.assembled_client
clock = season_suite.clock
journey_enabled = season_suite.journey_enabled
season_on = season_suite.season_on


@pytest.mark.skipif(not os.environ.get("WP133A_OUT"), reason="paid read; set WP133A_OUT=<dir> with the owner's approval")
def test_wp133a_live_read(assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch, caplog):  # noqa: F811
    # Without SEASON_REPORT_LIVE this is a free plumbing run on the fake director.
    assert not os.environ.get("SEASON_REPORT_LIVE") or os.environ.get("SEASON_REPORT_MAX_USD"), "a live read needs its cap"
    # Production's catalogue (config default v2), not the suite's pinned v1: the read
    # measures whether the director weaves the rule a real learner meets today.
    from app.config import settings
    from app.services.grammar_catalog import FrenchCoreGrammarCatalog

    monkeypatch.setattr(settings, "ATELIER_GRAMMAR_CATALOG_VERSION", "v2")
    # tests/conftest.py turns the practice day off for most modules; production runs it,
    # and without it the plan never carries an ``introduce`` to weave.
    monkeypatch.setattr(settings, "ATELIER_JOURNEY_PRACTICE_DAY_ENABLED", True)
    FrenchCoreGrammarCatalog(db_session, "v2").ensure_catalog()
    weaves: list[dict] = []
    real_gap = engine.grammar_weave_gap

    def recorded_gap(draft, context):
        unit = (context.get(engine.GRAMMAR_PLAN_KEY) or {}).get("introduce") or {}
        gap = real_gap(draft, context)
        weaves.append(
            {
                "unit": unit.get("id") or unit.get("concept_id") or unit.get("title_fr"),
                "title": draft.title_fr if hasattr(draft, "title_fr") else None,
                "uses": engine.grammar_uses(draft, unit) if unit else None,
                "invited": engine.grammar_invited(draft, unit) if unit else None,
                "countable": bool(unit.get("detectors")),
                "complies": gap is None,
            }
        )
        return gap

    monkeypatch.setattr(engine, "grammar_weave_gap", recorded_gap)
    caplog.set_level(logging.WARNING)
    try:
        season_suite.test_write_the_first_days_for_the_owner(
            assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
        )
        outcome = "complete"
    except season_suite.SpendCapReached as exc:
        outcome = f"stopped: {exc}"
    failures = [
        record.getMessage()
        for record in caplog.records
        if "story engine failed" in record.getMessage() or "critic" in record.getMessage().lower()
    ]
    out = Path(os.environ["WP133A_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    band = os.environ.get("SEASON_REPORT_BAND", "A2.1")
    (out / f"{band}.json").write_text(
        json.dumps({"band": band, "outcome": outcome, "weaves": weaves, "failures": failures}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
