"""S1.1 — count the day brief's shadow disagreements over a test run.

A pytest plugin, loaded by name. It switches ``DAY_BRIEF_ENABLED`` on for the run,
collects every ``day_brief_disagreement`` warning and prints, per chooser, how many
times it disagreed with the brief and on how many distinct days (journeys)::

    TZ=UTC pytest -q -p no:cacheprovider -p tests.day_brief_shadow -m walk tests/test_learner_walk.py

``DAY_BRIEF_SHADOW_REPORT=path.json`` also writes the counts (and the first few
examples per chooser) as JSON. The counts are the evidence for stage S1.2.
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict

import pytest

SHADOW_EVENT = "day_brief_disagreement"  # = app.services.day_brief.SHADOW_EVENT

_EVENTS: list[dict] = []
_BUILT: list[int] = [0]


class _Collector(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "event_name", None) == SHADOW_EVENT:
            _EVENTS.append(
                {
                    "chooser": record.chooser,
                    "field": record.brief_field,
                    "chooser_value": record.chooser_value,
                    "brief_value": record.brief_value,
                    "journey_id": record.journey_id,
                }
            )


_HANDLER = _Collector(level=logging.WARNING)


@pytest.hookimpl(trylast=True)
def pytest_configure(config) -> None:  # noqa: ARG001 - pytest hook signature
    # Imported here: the app's settings need the environment tests/conftest.py sets.
    from app.config import settings
    from app.services import day_brief

    assert day_brief.SHADOW_EVENT == SHADOW_EVENT
    settings.DAY_BRIEF_ENABLED = True
    real_store = day_brief.store

    def counting_store(journey, brief):
        _BUILT[0] += 1
        return real_store(journey, brief)

    day_brief.store = counting_store
    if os.environ.get("DAY_BRIEF_SHADOW_READS") == "1":
        _also_read_home_and_open_the_forge()
    target = logging.getLogger(day_brief.__name__)
    target.disabled = False
    target.setLevel(logging.WARNING)
    target.addHandler(_HANDLER)


def _also_read_home_and_open_the_forge() -> None:
    """``DAY_BRIEF_SHADOW_READS=1``: the backend walk never reads Home and never opens
    La Forge (it advances the forge step). After each day this reads Home and starts
    the séance its «Forge today's rule» entry links to, so the read-time choosers run
    too. It changes the walk (one open séance a day), so it is a separate measurement."""

    from tests import learner_walk

    real_play_day = learner_walk.play_day

    def play_day(client, db, headers, **kwargs):
        transcript = real_play_day(client, db, headers, **kwargs)
        home = client.get("/api/v1/daily-journeys/today", headers=headers)
        forge = ((home.json() or {}).get("forge") or {}) if home.status_code == 200 else {}
        body = {"origin": "after_day", "budget_seconds": 300}
        if forge.get("concept_id") is not None:
            body["preferred_concept_id"] = forge["concept_id"]
        client.post("/api/v1/atelier/sessions", headers=headers, json=body)
        return transcript

    learner_walk.play_day = play_day


def summary() -> dict:
    events: dict[str, int] = defaultdict(int)
    days: dict[str, set[str]] = defaultdict(set)
    examples: dict[str, list[dict]] = defaultdict(list)
    for event in _EVENTS:
        events[event["chooser"]] += 1
        days[event["chooser"]].add(event["journey_id"])
        if len(examples[event["chooser"]]) < 5:
            examples[event["chooser"]].append(event)
    return {
        "briefs_built": _BUILT[0],
        "choosers": {
            chooser: {"events": events[chooser], "days": len(days[chooser]), "examples": examples[chooser]}
            for chooser in sorted(events)
        },
    }


def pytest_terminal_summary(terminalreporter) -> None:
    report = summary()
    terminalreporter.write_sep("-", "day brief shadow disagreements (S1.1)")
    terminalreporter.write_line(f"briefs built: {report['briefs_built']}")
    if not report["choosers"]:
        terminalreporter.write_line("no disagreement")
    for chooser, row in report["choosers"].items():
        terminalreporter.write_line(f"{chooser}: {row['events']} events on {row['days']} days")
    path = os.environ.get("DAY_BRIEF_SHADOW_REPORT")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
