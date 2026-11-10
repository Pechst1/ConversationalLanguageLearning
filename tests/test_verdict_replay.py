"""Package V stage 2: a judge change is replayed before it ships.

``tests/verdict_corpus/replay_cases.jsonl`` holds 604 frozen answers (walk and issue
sentences, the negative corpus, both ways of every valid-variant pair, one case per reader
branch). ``replay_base.jsonl`` is what the judge on main (``cbaedd4a``) said about each.
Today's judge may change a verdict, but never turn a right answer into anything else, and
never edit one accepted spelling into another.

Refresh the base on purpose only: ``python scripts/verdict_replay.py --base-ref origin/main --write-base``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verdict_replay.py"


@pytest.fixture(scope="module")
def replay():
    spec = importlib.util.spec_from_file_location("verdict_replay", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_no_right_answer_turns_wrong_and_no_valid_variant_is_edited(replay):
    cases = replay.load_cases()
    base = replay.load_base()
    result = replay.compare(base, replay.run_today(cases), {case["id"]: case for case in cases})

    assert result["compared"] == len(cases) > 500
    assert result["right_to_wrong"] == []
    assert result["variant_edits"] == []


def test_every_valid_variant_pair_is_in_the_replay_and_left_alone(replay):
    """A pair added to ``valid_variants.txt`` is judged too, frozen corpus or not."""

    fresh = [case for case in replay.build_corpus() if case["id"].startswith("variant-")]
    assert len(fresh) == 2 * len(replay._variant_pairs())
    edited = {
        case["id"]: verdict["edits"]
        for case, verdict in zip(fresh, (replay._call(case) for case in fresh), strict=True)
        if verdict["edits"]
    }
    assert edited == {}


def test_the_replay_names_a_right_answer_that_turns_wrong(replay):
    right = {"outcome": "right", "counts": True, "edits": []}
    wrong = {"outcome": "wrong", "counts": True, "edits": [{"span": "ognon", "replacement": "oignon"}]}
    result = replay.compare({"a": right}, {"a": wrong}, {"a": {"surface": "courrier"}})

    assert [flip["id"] for flip in result["right_to_wrong"]] == ["a"]
    assert result["variant_edits"] == [{"id": "a", "edit": ["ognon", "oignon"]}]
