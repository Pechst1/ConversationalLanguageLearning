"""WP-87: the paid review script walks the lanes production runs, and reports
per-lane latency — checked here with the fake provider, never a paid call."""

from __future__ import annotations

import json
import sys

from app.config import settings
from app.services import living_story as engine
from tests.test_wp87_lanes import LaneProvider


def test_review_script_plays_the_turn_in_lanes_and_reports_their_latency(monkeypatch, tmp_path):
    from scripts import review_living_story as review

    fake = LaneProvider()
    fake.delays = dict.fromkeys(fake.delays, 0.0)
    monkeypatch.setattr(engine, "_client", lambda: fake)
    monkeypatch.setattr(engine, "DUAL_DRAFTS_ENABLED", False)
    for name in ("ATELIER_LLM_ENABLED", "ATELIER_STORY_MAX_ATTEMPTS", "ATELIER_STORY_TURN_LANES_ENABLED"):
        monkeypatch.setattr(settings, name, getattr(settings, name))
    output = tmp_path / "review.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["review", "--live", "--days", "1", "--max-requests", "12", "--lanes", "--output", str(output)],
    )
    review.main()
    report = json.loads(output.read_text())
    assert report["lanes"] is True
    schemas = [request["schema"] for request in report["requests"]]
    assert {"TutorVerdict", "VoiceReply"} <= set(schemas), schemas
    latency = report["lane_latency"]
    assert {"TutorVerdict", "VoiceReply"} <= set(latency)
    if report["scenes"]:
        assert "reply_phase_seconds" in report["scenes"][0]
