"""WP-166: the paid check of the varied first day and the invented gap days.

Skipped unless ``WP166_OUT`` is set: never part of the suite. Two parts, each with a
hard cap (``tests/test_season_one.py::_live_model``):

* openings — ``WP166_PART=openings``: three day-1 openings written by the real model
  for three learners (A1 German, B1 English, C1 German), with the guards' verdict;
* gap days — ``WP166_PART=days``: the owner's season report (``SEASON_REPORT_*``),
  real model everywhere, through the WP-133a wrapper (refusals and spend recorded).

    WP166_OUT=<dir> WP166_PART=openings SEASON_REPORT_MAX_USD=0.10 python -m pytest tests/test_wp166_paid_check.py -q -s
    WP166_OUT=<dir> WP166_PART=days WP133A_OUT=<dir>/a1 SEASON_REPORT=<dir>/a1/A1.1.md SEASON_REPORT_LIVE=1 \
      SEASON_REPORT_MAX_USD=0.20 SEASON_REPORT_DAYS=4 SEASON_REPORT_BAND=A1.1 python -m pytest tests/test_wp166_paid_check.py -q -s
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.services.season import opening
from app.services.season.format import load_season
from app.services.season.page import resolve_day
from tests import test_season_one as season_suite
from tests import test_wp133a_live_read as live_read

assembled_client = season_suite.assembled_client
clock = season_suite.clock
journey_enabled = season_suite.journey_enabled
season_on = season_suite.season_on

PAID = pytest.mark.skipif(not os.environ.get("WP166_OUT"), reason="paid check; set WP166_OUT=<dir> with the owner's approval")
LEARNERS = (("A1", "de"), ("B1", "en"), ("C1", "de"))


@PAID
@pytest.mark.skipif(os.environ.get("WP166_PART") != "openings", reason="WP166_PART=openings")
def test_three_learners_three_openings(monkeypatch):
    spend = season_suite._live_model(monkeypatch)
    out = Path(os.environ["WP166_OUT"])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for band, language in LEARNERS:
        page = resolve_day(load_season("s1"), "t1", "a", flags={}, band=band, language=language)
        written, usage = opening.write_opening(page, band=band, language=language, budget=60)
        rows.append({"band": band, "language": language, "opening": written, "usage": usage})
        if written:
            served = opening.apply_opening(page, written)
            rows[-1]["panels"] = [m for m in served["movements"] if m.get("id") in opening.OPENING_PANELS]
    (out / "openings.json").write_text(json.dumps({"spend": spend, "openings": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# Day 1: three openings (real model)", ""]
    for row in rows:
        lines.append(f"## {row['band']} · {row['language']}")
        written = row["opening"]
        if not written:
            lines += ["*Not written: the authored opening is served.*", ""]
            continue
        lines.append(f"*{written['hour']} · {written['weather']} · {written['learner_doing']}*")
        lines.append(f"*Spark: {written['spark']}*")
        for panel in row["panels"]:
            lines.append(f"**{panel['id']}** ({panel['location_id']}) — *{panel['visual']}*")
            for line in panel["lines"]:
                who = "caption" if line["kind"] == "caption" else line["name"]
                native = f" ({line['text_native']})" if line.get("text_native") else ""
                lines.append(f"- {who}: «{line['text_fr']}»{native}")
        lines.append("")
    (out / "openings.md").write_text("\n".join(lines), encoding="utf-8")


@PAID
@pytest.mark.skipif(os.environ.get("WP166_PART") != "days", reason="WP166_PART=days")
def test_gap_days_written_by_the_real_model(assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch, caplog):  # noqa: F811
    # Registration's background task would open the app's own database: day 1 writes
    # its opening inline instead (the path a learner without a background row takes).
    monkeypatch.setattr(opening, "prepare_in_background", lambda user_id: None)
    live_read.test_wp133a_live_read(assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch, caplog)
