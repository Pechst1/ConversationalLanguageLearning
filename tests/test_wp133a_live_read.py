"""WP-133a: the early capped baseline read of generated days (owner-approved, US$3 in all).

A thin wrapper over the owner's season report (``tests/test_season_one.py::
test_write_the_first_days_for_the_owner``). It adds what the report does not keep:
- for each lost day, the guard reason (from the authored-fallback marker's log line);
- for each draft the director wrote, whether it carried today's rule
  (``grammar_plan.introduce``): how often the cast says it, and whether the question invites it;
- (LOSS-RATE 2026-10-06) every refused proposal: ``refusals`` (reason, hint, what the draft
  claimed, the season day; for a schema failure the finish reason and an output excerpt)
  and ``refusal_reasons`` (a tally), so a read can confirm why generated days are lost.

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
    # LOSS-RATE 2026-10-06: every refused proposal (a guard, the schema, the critic),
    # with the guard's reason, the hint the retry got, what the draft claimed (beat,
    # chapter question, voices, objective) and — for a schema failure — the provider's
    # finish reason and an excerpt of the model's own output. Never a key, never the
    # prompt. ``position`` is the season day the director was writing for.
    refusals: list[dict] = []
    where: dict = {}
    real_context = engine.story_context

    def located_context(*args, **kwargs):
        context = real_context(*args, **kwargs)
        where["position"] = ((context.get("season_script") or {}).get("position") or {}).get("key")
        return context

    monkeypatch.setattr(engine, "story_context", located_context)
    monkeypatch.setattr(
        engine, "REFUSAL_OBSERVERS", [lambda record: refusals.append({"position": where.get("position"), **record})]
    )
    # Free dry runs only: WP133A_DRY_FAIL="3,4" loses those season days on the fake
    # director, so the recovery (reprise, bridge) path is read before money is spent.
    dry_fail = {int(day) for day in os.environ.get("WP133A_DRY_FAIL", "").split(",") if day.strip()}
    if dry_fail and not os.environ.get("SEASON_REPORT_LIVE"):
        plain = season_on._season_draft
        calls = {"day": 0}

        def failing(context):
            day = int((((context.get("season_script") or {}).get("brief") or {}).get("season") or {}).get("day") or 0)
            if day in dry_fail:
                raise engine.StoryUnavailable("dry_run_forced")
            return plain(context)

        monkeypatch.setattr(season_on, "_season_draft", failing)
        del calls
    out = Path(os.environ["WP133A_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    band = os.environ.get("SEASON_REPORT_BAND", "A2.1")
    os.environ.setdefault("SEASON_REPORT_SPEND", str(out / f"{band}.spend.json"))
    caplog.set_level(logging.WARNING)
    try:
        season_suite.test_write_the_first_days_for_the_owner(
            assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
        )
        outcome = "complete"
    except season_suite.SpendCapReached as exc:
        outcome = f"stopped: {exc}"
    except Exception as exc:  # noqa: BLE001 - a paid run keeps what it learned
        outcome = f"crashed: {type(exc).__name__}: {exc}"
    failures = [
        record.getMessage()
        for record in caplog.records
        if any(
            mark in record.getMessage()
            for mark in ("story engine failed", "season day lost", "re-reads", "recovery", "attempt refused", "shape repaired")
        )
        or "critic" in record.getMessage().lower()
    ]
    spent = Path(os.environ["SEASON_REPORT_SPEND"])
    spend = json.loads(spent.read_text(encoding="utf-8")) if spent.is_file() else None
    (out / f"{band}.json").write_text(
        json.dumps(
            {
                "band": band,
                "outcome": outcome,
                "spend": spend,
                "weaves": weaves,
                "failures": failures,
                "refusals": refusals,
                "refusal_reasons": _tally(row["reason"] for row in refusals),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


def _tally(reasons) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reason in reasons:
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))
