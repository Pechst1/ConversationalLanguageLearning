"""The gold gate: a prompt or model change on a gold surface is caught, and a fall blocks it.

No model, no network. The fingerprint must move when a prompt or a model moves and stay
put otherwise; the paired comparison must block a fall, pass a hold, credit a rise and
refuse a run that scored too few items on both sides.
"""

from __future__ import annotations

import json

import pytest

from tests.gold_transcripts import gate as G
from tests.gold_transcripts import runner as R


def _run(surface: str, scores: dict[str, float | None]) -> dict:
    rows = [
        {"id": item, "status": "not_run"} if score is None else {"id": item, "status": "scored", "score": score}
        for item, score in scores.items()
    ]
    return {"items": {surface: rows}}


def _ids(n: int) -> list[str]:
    return [f"i{k:02d}" for k in range(n)]


def test_same_scores_hold():
    base = _run("forge", dict.fromkeys(_ids(20), 0.9))
    row = G.compare(base, base, "forge")
    assert row["verdict"] == "held" and row["diff"] == 0 and row["paired"] == 20


def test_a_fall_beyond_the_tolerance_blocks():
    ids = _ids(20)
    base = _run("scene", dict.fromkeys(ids, 1.0))
    # Two items of twenty lose everything: ten points down.
    head = _run("scene", {i: (0.0 if k < 2 else 1.0) for k, i in enumerate(ids)})
    row = G.compare(base, head, "scene")
    assert row["verdict"] == "fell"
    assert row["diff"] == pytest.approx(-10.0)
    assert row["worse"][:2] == ["i00 -100", "i01 -100"]


def test_a_small_wobble_holds_and_a_clear_gain_rises():
    ids = _ids(25)
    base = _run("courrier", dict.fromkeys(ids, 0.8))
    wobble = _run("courrier", {i: (0.6 if k < 3 else 0.8) for k, i in enumerate(ids)})  # -2.4 points
    assert G.compare(base, wobble, "courrier")["verdict"] == "held"
    gain = _run("courrier", {i: (1.0 if k < 10 else 0.8) for k, i in enumerate(ids)})  # +8 points
    assert G.compare(base, gain, "courrier")["verdict"] == "rose"


def test_items_scored_on_one_side_only_are_left_out_and_too_few_is_incomplete():
    ids = _ids(20)
    base = _run("correction", dict.fromkeys(ids, 1.0))
    # The head's cap ran out after 15 items: those 15 pair, 75 % < 90 %.
    head = _run("correction", {i: (1.0 if k < 15 else None) for k, i in enumerate(ids)})
    row = G.compare(base, head, "correction")
    assert row["paired"] == 15 and row["verdict"] == "incomplete"
    assert G.compare(base, _run("correction", {}), "correction")["verdict"] == "incomplete"


def test_stale_names_every_reason():
    current = {s: {"fingerprint": f"fp-{s}", "calls": 1} for s in ("scene", "forge", "courrier", "correction")}
    gate = {"surfaces": {
        "scene": {"fingerprint": "fp-scene", "verdict": "held"},
        "forge": {"fingerprint": "old", "verdict": "rose"},
        "courrier": {"fingerprint": "fp-courrier", "verdict": "fell"},
    }}
    assert G.stale(current, gate) == {
        "forge": "its prompts or models changed since it last passed",
        "courrier": "its last gate verdict is «fell»",
        "correction": "never gated",
    }


def test_the_committed_gate_covers_every_weekly_surface_with_a_passing_verdict():
    gate = G.load_gate()
    for surface in ("scene", "forge", "courrier", "correction"):
        entry = gate["surfaces"][surface]
        assert entry["verdict"] in G.PASSING
        assert len(entry["fingerprint"]) == 16
    if gate.get("calibration"):
        # The tolerance sits above the noise the same-code run measured.
        assert max(abs(d) for d in gate["calibration"]["diffs"].values()) <= G.TOLERANCE


def test_a_base_that_mostly_fell_back_judges_nothing():
    ids = _ids(20)
    dead = {"items": {"scene": [{"id": i, "status": "scored", "score": 0.0, "failure": "expired key"} for i in ids]}}
    assert G.compare(dead, dead, "scene")["verdict"] == "incomplete"
    # A head that falls back where the base answered is a fall, not an outage.
    assert G.compare(_run("scene", dict.fromkeys(ids, 1.0)), dead, "scene")["verdict"] == "fell"


@pytest.fixture(scope="module")
def correction_fingerprint():
    return G.fingerprints(["correction"])["correction"]


def test_the_fingerprint_is_stable(correction_fingerprint):
    assert correction_fingerprint["calls"] == 26
    assert G.fingerprints(["correction"])["correction"] == correction_fingerprint


def test_a_prompt_change_moves_the_fingerprint(monkeypatch, correction_fingerprint):
    from app.services import missions

    monkeypatch.setattr(missions, "MISSION_FRAGMENT_MAX_WORDS", missions.MISSION_FRAGMENT_MAX_WORDS + 1)
    assert G.fingerprints(["correction"])["correction"]["fingerprint"] != correction_fingerprint["fingerprint"]


def test_a_model_change_in_render_yaml_moves_the_fingerprint(monkeypatch, correction_fingerprint):
    real = R.render_values

    def other_model(*args, **kwargs):
        values = dict(real(*args, **kwargs))
        values["ATELIER_CORRECTION_LLM_MODEL"] = "gpt-4o-mini"
        return values

    monkeypatch.setattr(R, "render_values", other_model)
    assert G.fingerprints(["correction"])["correction"]["fingerprint"] != correction_fingerprint["fingerprint"]


def test_render_says_blocked_and_lists_the_items_that_moved():
    ids = _ids(20)
    rows = {"scene": G.compare(_run("scene", dict.fromkeys(ids, 1.0)),
                               _run("scene", {i: (0.0 if k < 2 else 1.0) for k, i in enumerate(ids)}), "scene")}
    text = G.render(rows, base_ref="origin/main abc", head_ref="def", spent=0.5)
    assert text.startswith("### Gold gate: blocked")
    assert "| scene | 100.0 | 90.0 | -10.0 | 20/20 | fell |" in text
    assert "i00 -100" in text
    json.dumps(rows)  # gate.json keeps these rows


def test_a_run_where_the_model_never_answered_is_kept_out_of_the_trend():
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location("gold_cli", Path(__file__).parents[1] / "scripts" / "gold_transcripts.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    dead = {"surfaces": {"scene": {"items": 28, "failed_outright": 28}, "forge": {"items": 28, "failed_outright": 20}}}
    assert cli._dead_run(dead) == "scene 28/28 fell back, forge 20/28 fell back"
    # One surface answering is a real (bad) score, not an outage.
    alive = {"surfaces": {"scene": {"items": 28, "failed_outright": 28}, "forge": {"items": 28, "failed_outright": 2}}}
    assert cli._dead_run(alive) is None
