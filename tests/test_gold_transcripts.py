"""Gold transcripts (the nightly scored run) hold together without a model.

The paid run is ``scripts/gold_transcripts.py run`` from the nightly routine, never CI.
These tests check, with a fake model client and no network: the gold sets are well formed
and sized, every item drives its surface's production code to an answer, the spending
meter refuses the call that would pass the cap, the judge's answer is read strictly, and
the report's hidden history marker reads back into the trend.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tests.gold_transcripts import runner as R
from tests.gold_transcripts import surfaces as S
from tests.gold_transcripts.criteria import CRITERIA, CRITERIA_VERSION, judged


def _result(content, model="fake", cost=0.0):
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return SimpleNamespace(
        content=text, model=model, provider="fake", total_tokens=0, cost=cost,
        prompt_tokens=0, completion_tokens=0, raw_response={},
    )


class FakeModel:
    """Answers every call the four surfaces make with a valid, plain answer."""

    def __init__(self, cost: float = 0.0):
        self.calls: list[tuple[str, str | None]] = []
        self.cost = cost

    def generate_chat_completion(self, messages, **kwargs):
        user = messages[-1]["content"]
        try:
            schema = (json.loads(user).get("output_schema") or {}).get("title")
        except (json.JSONDecodeError, AttributeError):
            schema = None
        self.calls.append((schema or "chat", kwargs.get("model")))
        if schema == "TutorVerdict":
            # Quote the learner's own first words, as a grade must.
            data = json.loads(user)["data"]
            quote = " ".join(str(data.get("learner_text") or "").split()[:3])
            return _result({
                "outcome": "met", "evidence_quotes": [quote], "correction_span_fr": None,
                "correction_fr": None, "correction_note_native": None, "demonstrated_target_ids": [],
            }, cost=self.cost)
        if schema == "VoiceReply":
            return _result({
                "reply_fr": "D'accord. Je comprends.", "understood_intent": "answered",
                "needs_clarification": False, "feeling_shift": "steady", "acts": [],
            }, cost=self.cost)
        if kwargs.get("system_prompt") == R.JUDGE_SYSTEM:
            payload = json.loads(user)
            return _result({"criteria": [{"id": c["id"], "verdict": "pass", "reason": "ok"} for c in payload["criteria"]]}, cost=self.cost)
        return _result("D'accord, à bientôt.", cost=self.cost)

    def generate_error_detection(self, messages, **kwargs):
        self.calls.append(("error", kwargs.get("model")))
        payload = json.loads(messages[-1]["content"])
        text = payload.get("learner_text") or (payload.get("answer") or {}).get("text") or ""
        return _result({
            "verdict": "correct", "score_0_4": 4, "corrected_answer": text, "concept_hits": [],
            "missing_targets": [], "errata": [], "lexical_gaps": [], "notes_native": [],
        }, cost=self.cost)


# ---------------------------------------------------------------------------
# The sets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface", list(S.SURFACES))
def test_set_is_sized_and_well_formed(surface):
    items = S.load_items(surface)
    assert 20 <= len(items) <= 30, f"{surface}: {len(items)} items, the plan asks 20–30"
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids)), "item ids are unique"
    for item in items:
        assert item["learner_text"].strip(), item["id"]
        assert "live walk" in item["source"] or "eval" in item["source"] or "prompt rule" in item["source"], item["id"]
        assert isinstance(item.get("truth"), dict), item["id"]
        if surface == "scene":
            assert item["character_id"] in S._world_cast(), item["id"]
            assert {"opening_line_fr", "objective_native"} <= set(item["scene"]), item["id"]
        if surface in {"forge", "correction"}:
            assert isinstance(item["truth"].get("correct"), bool), item["id"]
            assert item["truth"]["correct"] == (not item["truth"].get("errors")), item["id"]
        if surface == "forge":
            assert item["concept"] in S._units(), item["id"]
        if surface in {"courrier", "correction"}:
            assert item["correspondent"]["register"] in {"tu", "vous"}, item["id"]


def test_every_criterion_is_named_once():
    for surface, criteria in CRITERIA.items():
        ids = [c.id for c in criteria]
        assert len(ids) == len(set(ids)), surface
        assert all(c.by in {"check", "judge"} for c in criteria)
        assert judged(surface), surface
    assert len(CRITERIA_VERSION) == 12


# ---------------------------------------------------------------------------
# The surfaces run on their production code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface", list(S.SURFACES))
def test_every_item_reaches_an_answer(surface):
    model = FakeModel()
    for item in S.load_items(surface):
        output = S.SURFACES[surface](item, model)
        assert not output.get("failure"), f"{item['id']}: {output}"
        verdicts = S.checks(surface, item, output)
        assert set(verdicts) == {c.id for c in CRITERIA[surface] if c.by == "check"}
    assert model.calls, "the surface called the model"


def test_scene_payload_carries_the_item():
    item = S.load_items("scene", ["s06-three-days-notary"])[0]
    payload = S.scene_payload(item)
    assert payload["learner_text"] == item["learner_text"]
    assert payload["history"] == item["history"]
    assert payload["story"]["world"]["cast"][0]["id"] == "lila_bonnet"
    assert payload["scene"]["opening_line_fr"] == "Tu restes combien de temps ?"
    # The bible's register sentence becomes the word the engine compares against.
    for item in S.load_items("scene"):
        member = S.scene_payload(item)["story"]["world"]["cast"][0]
        assert member["register_with_user"] in {"tu", "vous"}, item["id"]
    camille = S.load_items("scene", ["s18-no-dinner-cat"])[0]
    assert S.scene_payload(camille)["story"]["world"]["cast"][0]["register_with_user"] == "vous"


def test_forge_check_fails_a_wrong_verdict():
    item = S.load_items("forge", ["f01-nous-preferons"])[0]
    verdicts = S.checks("forge", item, {"failure": None, "passes": False})
    assert verdicts["verdict_right"][0] == "fail"


def test_correction_checks_spans_and_clean_sentences():
    item = S.load_items("correction", ["k10-je-suis-fatigue-ok"])[0]
    output = {"failure": None, "errata": [{"learner_text": "suis", "corrected_target": "est"}]}
    verdicts = S.checks("correction", item, output)
    assert verdicts["verdict_right"][0] == "fail"
    assert verdicts["spans_real"][0] == "pass"
    output = {"failure": None, "errata": [{"learner_text": "ils sont", "corrected_target": "ils est"}]}
    assert S.checks("correction", item, output)["spans_real"][0] == "fail"


def test_courrier_stock_line_is_a_failure():
    item = S.load_items("courrier")[0]

    class Stock(FakeModel):
        def generate_chat_completion(self, messages, **kwargs):
            from app.services.llm_service import LLMProviderError

            raise LLMProviderError("timeout")

    output = S.run_courrier(item, Stock())
    assert output["failure"], output


# ---------------------------------------------------------------------------
# Meter, judge, run
# ---------------------------------------------------------------------------


def test_meter_refuses_the_call_that_would_pass_the_cap():
    from app.services.llm_service import LLMProviderError

    meter = R.Meter(inner=FakeModel(cost=0.01), cap_usd=0.02)
    messages = [{"role": "user", "content": "x"}]
    meter.generate_chat_completion(messages, model="gpt-6-luna", max_tokens=10)
    meter.generate_chat_completion(messages, model="gpt-6-luna", max_tokens=10)
    with pytest.raises(LLMProviderError, match="gold budget"):
        meter.generate_chat_completion(messages, model="gpt-6-luna", max_tokens=10)
    assert meter.exhausted
    assert meter.spent_usd == pytest.approx(0.02)
    assert meter.calls == 2


def test_meter_reserves_parallel_calls_and_prices_claude_at_its_floor():
    import threading

    from app.services.llm_service import ANTHROPIC_MIN_MAX_TOKENS, LLMProviderError

    gate = threading.Event()

    class Slow(FakeModel):
        def generate_chat_completion(self, messages, **kwargs):
            gate.wait(5)
            return _result("ok", cost=0.0)

    messages = [{"role": "user", "content": "x"}]
    meter = R.Meter(inner=Slow(), cap_usd=0.01)
    one_call = meter.worst_case("chat", messages, {"model": "gpt-6-luna", "max_tokens": 10})
    meter.cap_usd = one_call * 1.5  # room for one call in flight, not two
    errors: list[Exception] = []

    def call():
        try:
            meter.generate_chat_completion(messages, model="gpt-6-luna", max_tokens=10)
        except LLMProviderError as exc:
            errors.append(exc)

    first = threading.Thread(target=call)
    first.start()
    for _ in range(500):  # until the first call is admitted and in flight
        if meter.reserved_usd > 0:
            break
        threading.Event().wait(0.01)
    call()  # nothing is spent yet: only the reservation can refuse it
    gate.set()
    first.join()
    assert len(errors) == 1 and meter.calls == 1 and meter.reserved_usd == pytest.approx(0.0)
    claude = meter.worst_case("chat", messages, {"model": "claude-sonnet-5-5", "max_tokens": 1000})
    floor = meter.worst_case("chat", messages, {"model": "claude-sonnet-5-5", "max_tokens": ANTHROPIC_MIN_MAX_TOKENS})
    assert claude == floor


def test_parse_verdicts_never_passes_a_missing_verdict():
    content = json.dumps({"criteria": [{"id": "takes_up", "verdict": "pass", "reason": "ok"}, {"id": "no_reask", "verdict": "maybe"}]})
    verdicts = R.parse_verdicts("scene", content)
    assert verdicts["takes_up"] == ("pass", "ok")
    assert verdicts["no_reask"][0] == "fail"
    assert all(v == "fail" for v, _ in R.parse_verdicts("scene", "not json").values())


def test_run_scores_and_stops_at_the_cap():
    model = FakeModel(cost=0.004)
    meter = R.Meter(inner=model, cap_usd=0.05)
    result = R.run(["forge", "correction"], client=meter, limit=10)
    rows = result["items"]["forge"] + result["items"]["correction"]
    scored = [r for r in rows if r["status"] == "scored"]
    skipped = [r for r in rows if r["status"] == "not_run"]
    assert scored and skipped, "some items ran, the rest stopped at the cap"
    assert meter.spent_usd <= 0.05
    assert all("cap" in r["reason"] for r in skipped)
    summary = result["surfaces"]["correction"]
    assert summary["items"] == 10 and summary["scored"] + summary["not_run"] == 10


def test_judge_answers_feed_the_score():
    result = R.run(["courrier"], client=FakeModel(), limit=3)
    summary = result["surfaces"]["courrier"]
    assert summary["score"] == 100.0
    assert summary["criteria"]["takes_up"] == "3/3"


# ---------------------------------------------------------------------------
# Report and history
# ---------------------------------------------------------------------------


def _night(date, score, label="production"):
    result = R.run(["courrier"], client=FakeModel(), limit=2)
    result["surfaces"]["courrier"]["score"] = score
    result.update(date=date, label=label, cap_usd=1.5, spent_usd=0.4, models={"STORY_LIVE_MODEL": "gpt-6-luna"})
    return result


def test_report_marker_reads_back_as_history_and_trend():
    first = R.render_report(_night("2026-11-01", 70.0), [])
    assert "first night" in first
    history = R.parse_history(["unrelated digest comment", first])
    assert len(history) == 1
    assert history[0]["date"] == "2026-11-01" and history[0]["criteria"] == CRITERIA_VERSION
    assert history[0]["scores"] == {"courrier": 70.0} and history[0]["spent"] == 0.4
    second = R.render_report(_night("2026-11-02", 78.0), history)
    assert "| +8 |" in second and "70 → 78" in second
    # A comparison run does not count against the production trend.
    other = R.render_report(_night("2026-11-02", 50.0, label="haiku-live"), history)
    assert "first night" in other and "haiku-live" in other


def test_profile_applies_render_values_and_restores():
    from app.config import settings

    before = settings.STORY_LIVE_MODEL
    applied = R.apply_profile({"OPENAI_MISSION_FAST_MODEL": "gpt-6-luna"})
    try:
        assert settings.STORY_LIVE_MODEL == R.render_values()["STORY_LIVE_MODEL"]
        assert settings.OPENAI_MISSION_FAST_MODEL == "gpt-6-luna"
        assert settings.ATELIER_LLM_ENABLED is True
    finally:
        R.restore_profile(applied)
    assert settings.STORY_LIVE_MODEL == before
    with pytest.raises(ValueError):
        R.apply_profile({"NOT_A_SETTING": "x"})


def test_cli_refuses_without_a_cap_above_the_cap_and_in_ci(monkeypatch, capsys):
    from scripts import gold_transcripts as cli

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["run"]) == 2
    assert cli.main(["run", "--max-usd", "5"]) == 2
    monkeypatch.setenv("CI", "true")
    assert cli.main(["run", "--max-usd", "1"]) == 2
    assert "CI" in capsys.readouterr().out
