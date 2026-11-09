"""The capped paid path of the prompt regression (owner decision ED-3), with no network: a
stub stands in for the provider, so the cap and the bookkeeping are tested for free."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import prompt_regression as script
from tests.prompt_regression import harness


class _Stub:
    """Answers like the provider, at a set price per call."""

    def __init__(self, cost: float = 0.01):
        self.cost = cost
        self.models: list[str | None] = []

    def generate_chat_completion(self, messages, *, system_prompt=None, model=None, **kwargs):
        self.models.append(model)
        schema = json.loads(messages[-1]["content"])["output_schema"]["title"]
        content = (
            {"outcome": "met", "evidence_quotes": ["Non"], "demonstrated_target_ids": []}
            if schema == "TutorVerdict"
            else {
                "reply_fr": "Parce qu'il m'a élevée.",
                "understood_intent": "L'apprenant refuse.",
                "needs_clarification": False,
                "learner_intent": "no",
            }
        )
        return SimpleNamespace(content=json.dumps(content), model="stub-model", provider="stub", total_tokens=0, cost=self.cost)


@pytest.fixture
def case(tmp_path: Path) -> harness.Case:
    source = harness.load_cases(["turn-a2-camille-says-no"])[0]
    raw = json.loads(json.dumps(source.raw))
    path = tmp_path / "case.json"
    path.write_text(json.dumps(raw, ensure_ascii=False))
    return harness.Case(
        id=source.id, lane=source.lane, level=source.level, source=source.source, input=source.input,
        answers={}, expect={}, path=path, raw=raw,
    )


def test_a_recording_replays_against_the_digest_of_the_prompt_it_answered(case):
    stub = _Stub()
    recorder = harness.Recorder(stub, model="production-model", cap_usd=1.0, stamp="live test")
    observed = harness.record_case(case, recorder)

    assert observed["reply_fr"] == "Parce qu'il m'a élevée."
    assert stub.models == ["production-model", "production-model"], "the named model answers"
    recorded = json.loads(case.path.read_text())["answers"]
    assert recorded["VoiceReply"][0]["origin"] == "live test stub-model"
    assert recorder.spent == pytest.approx(0.02)

    replayed = harness.run_case(
        harness.Case(
            id=case.id, lane=case.lane, level=case.level, source=case.source, input=case.input,
            answers=recorded, expect={}, path=case.path, raw=case.raw,
        )
    )
    assert harness.stale_answers(replayed) == []
    assert replayed.observed["reply_fr"] == "Parce qu'il m'a élevée."


def test_the_cap_stops_the_run_and_leaves_no_half_recorded_case(case):
    stub = _Stub()
    before = case.path.read_text()
    recorder = harness.Recorder(stub, model=None, cap_usd=0.5, spent=0.5)
    observed = harness.record_case(case, recorder)
    assert observed["failure"]
    assert stub.models == [], "nothing is called past the cap"
    assert case.path.read_text() == before


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"named": True, "max_usd": None, "model": None}, "spending cap"),
        ({"named": True, "max_usd": 1.5, "model": None}, "above US$1"),
        ({"named": False, "max_usd": 0.5, "model": None}, "only the cases you name"),
    ],
)
def test_live_refuses_before_any_call(monkeypatch, capsys, kwargs, reason):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    assert script._live([], **kwargs) == 2
    assert reason in capsys.readouterr().out


def test_live_refuses_without_a_key(monkeypatch, capsys):
    for name in script.API_KEY_ENVS:
        monkeypatch.delenv(name, raising=False)
    assert script._live([], named=True, max_usd=0.5, model=None) == 2
    assert "no API key" in capsys.readouterr().out


def test_live_never_records_over_a_page_case(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "not-a-real-key")
    page = next(case for case in harness.load_cases() if case.lane == "page")
    assert script._live([page], named=True, max_usd=0.5, model=None) == 2
    assert "authored cases only" in capsys.readouterr().out
