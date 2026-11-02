"""Gold transcripts (the nightly scored run) hold together without a model.

The paid run is ``scripts/gold_transcripts.py run`` from the nightly routine, never CI.
These tests check, with a fake model client and no network: the gold sets are well formed
and sized, every item drives its surface's production code to an answer, the spending
meter refuses the call that would pass the cap, the judge's answer is read strictly, and
the report's hidden history marker reads back into the trend. A day of acts (Phase 2
«Folge in Akten») is written as the night writes it and judged act by act.
"""

from __future__ import annotations

import json
import os
from datetime import date
from types import SimpleNamespace

import pytest

from tests.gold_transcripts import runner as R
from tests.gold_transcripts import surfaces as S
from tests.gold_transcripts.criteria import (
    CRITERIA,
    CRITERIA_VERSION,
    DAY_SURFACE,
    WEEKLY_SURFACES,
    criteria_version,
    judged,
)


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
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids)), "item ids are unique"
    if surface == DAY_SURFACE:
        # One day for each band the acts are measured on, each on a page of the page set:
        # a weekly run writes one, in turn (``runner.week_day``).
        assert sorted(item["level"] for item in items) == ["A1", "A2", "B1"]
        pages = {item["id"]: item for item in S.load_items("page")}
        for item in items:
            page = pages[item["page"]]
            assert (page["level"], page["season_day"]) == (item["level"], item["season_day"]), item["id"]
            assert item["learner_text"].strip() and item["segment_day"] in item["page"], item["id"]
        return
    assert 20 <= len(items) <= 30, f"{surface}: {len(items)} items, the plan asks 20–30"
    for item in items:
        assert item["learner_text"].strip(), item["id"]
        if surface == "page":
            context = json.loads((S.PAGES / f"{item['id']}.json").read_text(encoding="utf-8"))
            position = context["season_script"]["position"]
            assert (position["season_day"], position["kind"]) == (item["season_day"], "gap"), item["id"]
            assert context["level"] == item["level"], item["id"]
            continue
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


@pytest.mark.parametrize("surface", list(WEEKLY_SURFACES))
def test_every_item_reaches_an_answer(surface):
    model = FakeModel()
    for item in S.load_items(surface):
        output = S.SURFACES[surface](item, model)
        assert not output.get("failure"), f"{item['id']}: {output}"
        verdicts = S.checks(surface, item, output)
        assert set(verdicts) == {c.id for c in CRITERIA[surface] if c.by == "check"}
    assert model.calls, "the surface called the model"


class PageWriter:
    """story_split's fake writer (tests/test_story_split.py) plus a story judge that rates
    every question 4, except «level» 2."""

    def __init__(self):
        from tests.test_story_split import SplitProvider

        self.writer = SplitProvider()
        self.judged: list[str] = []
        self.readings: list[tuple[str, str]] = []

    def generate_chat_completion(self, messages, **kwargs):
        system = kwargs.get("system_prompt") or ""
        if system.startswith(("You judge one day", "You judge one act")):
            asked = messages[-1]["content"].split("Questions: ", 1)[1].split("\n", 1)[0].split(", ")
            self.judged.append(kwargs.get("model"))
            self.readings.append((system, messages[-1]["content"]))
            return _result({q: {"score": 2 if q == "level" else 4, "reason": "fake", "line": ""} for q in asked})
        return self.writer.generate_chat_completion(messages, **kwargs)


class DayWriter(PageWriter):
    """The page writer that also plans and writes a later act (the night's fake,
    tests/test_story_acts_night.py), its critic letting every act through."""

    def __init__(self):
        super().__init__()
        from tests.test_story_acts_night import ActProvider

        self.writer = ActProvider()
        self.writer.critic_refusals_left = 0


def test_the_page_surface_writes_each_day_and_is_rated_on_the_story_judge_questions(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)
    for item in S.load_items("page"):
        output = S.run_page(item, PageWriter().writer)
        assert not output["failure"], (item["id"], output)
        assert output["seconds"] < S.PAGE_BUDGET_SECONDS and output["page_lines"], item["id"]
        assert any("«" in line for line in output["page_lines"]), "the dialogue is on the page"
    client = PageWriter()
    result = R.run(["page"], client=client, judge_model="gpt-6.1-sol", limit=3)
    summary = result["surfaces"]["page"]
    assert client.judged == ["gpt-6.1-sol"] * 3
    assert summary["lost"] == 0 and summary["seconds_median"] is not None
    assert summary["ratings"]["level"]["mean"] == 2 and summary["criteria"]["natural"] == "3/3"
    # Four questions at 4/5 and one at 2/5: (4 × 0.75 + 0.25) / 5 = 65.
    assert summary["score"] == 65.0
    report = R.render_report({**result, "date": "2026-11-01", "label": "writer-test", "cap_usd": 1.0}, [])
    assert "0 of 3 days lost" in report and "level 2.0" in report


def test_a_lost_day_scores_zero_and_is_not_judged(monkeypatch):
    from app.config import settings
    from app.services import living_story as engine

    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)

    def lost(*args, **kwargs):
        raise engine.StoryUnavailable("timeout")

    monkeypatch.setattr(engine, "_approved", lost)
    client = PageWriter()
    result = R.run(["page"], client=client, limit=2)
    assert client.judged == []
    assert result["surfaces"]["page"]["lost"] == 2 and result["surfaces"]["page"]["score"] == 0.0


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
    result = R.run(["forge", "correction"], client=meter, judge_model=R.PAGE_JUDGE, limit=10)
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
    assert "first run" in first
    history = R.parse_history(["unrelated digest comment", first])
    assert len(history) == 1
    assert history[0]["date"] == "2026-11-01" and history[0]["criteria"] == CRITERIA_VERSION
    assert history[0]["scores"] == {"courrier": 70.0} and history[0]["spent"] == 0.4
    second = R.render_report(_night("2026-11-02", 78.0), history)
    assert "| +8 |" in second and "70 → 78" in second
    # A comparison run does not count against the production trend.
    other = R.render_report(_night("2026-11-02", 50.0, label="haiku-live"), history)
    assert "first run" in other and "haiku-live" in other


class StrictJudge(FakeModel):
    """Fails every `takes_up`: a second judge that disagrees on one criterion."""

    def generate_chat_completion(self, messages, **kwargs):
        if kwargs.get("system_prompt") == R.JUDGE_SYSTEM:
            payload = json.loads(messages[-1]["content"])
            self.calls.append(("judge", kwargs.get("model")))
            return _result({"criteria": [
                {"id": c["id"], "verdict": "fail" if c["id"] == "takes_up" else "pass", "reason": "strict"}
                for c in payload["criteria"]
            ]})
        return super().generate_chat_completion(messages, **kwargs)


def test_rejudge_scores_the_same_answers_with_another_judge():
    before = R.run(["courrier"], client=FakeModel(), limit=3)
    before["items"]["courrier"][2].update(failure="stock line", score=0.0)  # a fallback stays a fallback
    judge = StrictJudge()
    after = R.rejudge(before, judge_client=judge, judge_model="claude-sonnet-5-5")
    assert [model for kind, model in judge.calls] == ["claude-sonnet-5-5"] * 2, "only judged answers, no app call"
    assert after["judge_model"] == "claude-sonnet-5-5" and after["rejudged_from"] == R.DEFAULT_JUDGE
    rows = after["items"]["courrier"]
    assert rows[0]["output"] == before["items"]["courrier"][0]["output"]
    assert rows[0]["verdicts"]["served"][0] == "pass", "the deterministic check is kept"
    assert rows[0]["verdicts"]["takes_up"][0] == "fail" and rows[2]["score"] == 0.0
    agreement = R.judge_agreement(before, after)["courrier"]
    judged_count = len(judged("courrier"))
    assert agreement["verdicts"] == 2 * judged_count
    assert agreement["agreement"] == round((judged_count - 1) / judged_count, 3)
    assert agreement["flips"][0].endswith("takes_up: pass→fail")


def test_a_judge_change_restarts_the_trend():
    first = R.render_report(_night("2026-11-01", 70.0), [])
    history = R.parse_history([first])
    assert history[0]["judge"] == R.DEFAULT_JUDGE
    # Entries written before the judge was recorded count as the first judge's.
    legacy = [{k: v for k, v in history[0].items() if k != "judge"}]
    first_judge = {**_night("2026-11-02", 78.0), "judge_model": R.FIRST_JUDGE}
    assert "| +8 |" in R.render_report(first_judge, legacy)
    report = R.render_report(_night("2026-11-02", 78.0), legacy)
    assert "first run" in report and "The judge changed" in report


def test_no_claude_judge_grades_the_claude_night_writer(monkeypatch, tmp_path, capsys):
    assert R.judge_for(["scene", "forge"]) == R.DEFAULT_JUDGE
    assert R.judge_for(["page"]) == R.PAGE_JUDGE and not R.PAGE_JUDGE.startswith("claude")
    with pytest.raises(ValueError):
        R.judge_for(["page"], "claude-opus-5-5")
    from scripts import gold_transcripts as cli

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert cli.main(["plan", "--surface", "page", "--judge-model", "claude-sonnet-5-5"]) == 2
    saved = tmp_path / "pages.json"
    saved.write_text(json.dumps({"judge_model": R.PAGE_JUDGE, "items": {"page": []}}), encoding="utf-8")
    assert cli.main(["rejudge", str(saved), "--judge-model", "claude-sonnet-5-5", "--max-usd", "1"]) == 2
    assert "Claude model" in capsys.readouterr().out


def test_an_unrated_page_question_earns_nothing():
    verdicts = {"served": ("pass", ""), "natural": ("pass", "5/5 fine")}
    verdicts.update({c.id: ("fail", "judge: no verdict") for c in judged("page") if c.id != "natural"})
    assert R.item_score(verdicts, "page") == 1 / len(judged("page"))


def test_cli_maps_the_environment_anthropic_key(monkeypatch):
    import importlib

    from scripts import gold_transcripts as cli

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # registered, so the test's own value is undone
    monkeypatch.setenv("ATELIER_ANTHROPIC_API_KEY", "sk-ant-test")
    importlib.reload(cli)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-test"


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


def test_profile_never_makes_the_process_a_production_server():
    """CI shares worker processes: a failed or applied profile must not leak APP_ENV,
    SMTP or spend settings into the next test file."""

    from app.config import settings

    snapshot = settings.model_dump()
    applied = R.apply_profile()
    try:
        assert "APP_ENV" not in applied and "SMTP_PORT" not in applied
        assert "USER_DAILY_SPEND_CAP_USD" not in applied
        assert settings.APP_ENV == snapshot["APP_ENV"]
    finally:
        R.restore_profile(applied)
    assert settings.model_dump() == snapshot
    with pytest.raises(ValueError):
        R.apply_profile({"NOT_A_SETTING": "x"})
    with pytest.raises(ValueError):
        R.apply_profile({"MISSION_CHAT_TIMEOUT_SECONDS": "not a number"})
    assert settings.model_dump() == snapshot


def test_cli_refuses_without_a_cap_above_the_cap_and_in_ci(monkeypatch, capsys):
    from scripts import gold_transcripts as cli

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("CI", raising=False)
    assert cli.main(["run"]) == 2
    assert cli.main(["run", "--max-usd", "5"]) == 2
    monkeypatch.setenv("CI", "true")
    assert cli.main(["run", "--max-usd", "1"]) == 2
    assert "CI" in capsys.readouterr().out
    assert cli.main(["rejudge", "x.json", "--judge-model", "claude-sonnet-5-5", "--max-usd", "1"]) == 2


# ---------------------------------------------------------------------------
# A day of acts (Phase 2 «Folge in Akten»)
# ---------------------------------------------------------------------------


@pytest.fixture
def plan_then_write(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "STORY_PLAN_THEN_WRITE", True)


def test_a_day_is_its_page_then_each_act_an_intensif_learner_plays(plan_then_write):
    played = {"A1": ["fil", "soir"], "A2": ["fil", "soir"], "B1": ["fil", "cote", "soir"]}
    for item in S.load_items(DAY_SURFACE):
        output = S.run_day(item, DayWriter().writer)
        assert not output["failure"], (item["id"], output)
        acts = output["acts"]
        assert [act["role"] for act in acts] == played[item["level"]], "in play order"
        first, *later = acts
        for act in acts:
            assert not act["failure"] and act["page_lines"] and act["seconds"] < S.PAGE_BUDGET_SECONDS, item["id"]
        for act in later:
            # The act moves on from the day's first act (a bottle chapter keeps its room).
            assert act["lead"] != first["lead"], item["id"]
        verdicts = S.checks(DAY_SURFACE, item, output)
        assert verdicts == {f"{role}.served": ("pass", "") for role in played[item["level"]]}


def test_a_day_is_judged_act_by_act_and_a_later_act_against_the_first(plan_then_write):
    client = DayWriter()
    result = R.run([DAY_SURFACE], client=client, judge_model=R.PAGE_JUDGE, ids=["d-b1-g4.4"])

    assert result["criteria_version"] == criteria_version([DAY_SURFACE]) != CRITERIA_VERSION
    assert client.judged == [R.PAGE_JUDGE] * 3, "one reading an act"
    first, cote, soir = client.readings
    assert first[0].startswith("You judge one act of a day") and "Act: «Le fil»" in first[1]
    assert "Questions: natural, clear_question, something_happens, voices, level\n" in first[1]
    for system, user in (cote, soir):
        assert "Questions: natural, clear_question, something_happens, voices, level, new\n" in user
        assert "The day's first act: " in user and "Previous day" not in user
        assert "compared with the day's first act" in system
    summary = result["surfaces"][DAY_SURFACE]
    assert summary["days"] == ["d-b1-g4.4"]
    acts = summary["acts"]
    assert list(acts) == ["fil", "cote", "soir"]
    assert all(act["written"] == 1 and not act["dropped"] for act in acts.values())
    assert "new" in acts["soir"]["ratings"] and "new" not in acts["fil"]["ratings"]
    assert acts["soir"]["gate"] == "fail", "«level» at 2 fails the gate on the act alone"
    assert acts["soir"]["vs_first"] == 0.0
    # «Le fil»: four of five at 4/5 and «level» at 2/5 = 65; a later act asks six: 66.7.
    assert summary["score"] == round(100 * (0.65 + 2 * (5 * 0.75 + 0.25) / 6) / 3, 1)
    assert summary["criteria"]["soir.served"] == "1/1" and summary["criteria"]["cote.new"] == "1/1"

    report = R.render_report({**result, "date": "2026-11-08", "label": "production", "cap_usd": 2.0}, [])
    assert "| A day of acts |" in report and "A day of acts (`d-b1-g4.4`)" in report
    assert "| Le soir | yes | " in report and "| À côté | yes | " in report
    entry = R.parse_history([report])[0]
    assert entry["scores"] == {DAY_SURFACE: summary["score"]} and entry["days"] == ["d-b1-g4.4"]
    assert entry["criteria"] == criteria_version([DAY_SURFACE])


@pytest.fixture
def le_soir_dropped(plan_then_write, monkeypatch):
    """The act critic refuses «Le soir» on its first reading, so the night drops it."""

    from app.services import living_story as engine

    drafted = engine.draft_later_act

    def critic_refuses_le_soir(act_context, **kwargs):
        if not kwargs["reviews"] and act_context["act"]["role"] == "soir":
            raise engine.StoryUnavailable("story_critic_refused", hint="the act repeats the first")
        return drafted(act_context, **kwargs)

    monkeypatch.setattr(engine, "draft_later_act", critic_refuses_le_soir)


def test_a_dropped_act_scores_zero_and_the_night_writes_none_after_it(le_soir_dropped):
    client = DayWriter()
    result = R.run([DAY_SURFACE], client=client, ids=["d-b1-g4.4"])

    [row] = result["items"][DAY_SURFACE]
    roles = {act["role"]: act for act in row["output"]["acts"]}
    assert roles["soir"]["failure"] == "dropped: story_critic_refused"
    assert "dropped" in roles["cote"]["not_run"], "«À côté» is never played without «Le soir»"
    assert client.judged == [R.PAGE_JUDGE], "only «Le fil» was written"
    assert set(row["verdicts"]) == {"fil.served", "soir.served", *(f"fil.{c.id}" for c in judged("page"))}
    assert R.act_scores(row["verdicts"])["soir"] == 0.0 and row["score"] == pytest.approx(0.65 / 2)
    acts = result["surfaces"][DAY_SURFACE]["acts"]
    assert (acts["soir"]["dropped"], acts["cote"]["not_run"]) == (1, 1)
    lines = "\n".join(R.day_lines(result["surfaces"][DAY_SURFACE]))
    assert "| Le soir | dropped 1: dropped: story_critic_refused |" in lines
    assert "| À côté | not written: the act before it was dropped" in lines


def test_rejudging_a_day_keeps_its_dropped_act_at_zero(le_soir_dropped):
    before = R.run([DAY_SURFACE], client=DayWriter(), ids=["d-b1-g4.4"])
    judge = DayWriter()
    after = R.rejudge(before, judge_client=judge, judge_model=R.PAGE_JUDGE)

    [was], [row] = before["items"][DAY_SURFACE], after["items"][DAY_SURFACE]
    assert judge.judged == [R.PAGE_JUDGE], "only «Le fil» is read again"
    assert row["verdicts"]["soir.served"] == was["verdicts"]["soir.served"] and row["verdicts"]["fil.served"][0] == "pass"
    # The same ratings from another reading leave the day as it was, the dropped act at 0.
    assert row["score"] == was["score"] == pytest.approx(0.65 / 2)
    assert after["surfaces"][DAY_SURFACE]["score"] == before["surfaces"][DAY_SURFACE]["score"]


class LowJudge:
    """A second story judge that rates every question 2/5."""

    def __init__(self):
        self.judged: list[str] = []

    def generate_chat_completion(self, messages, **kwargs):
        asked = messages[-1]["content"].split("Questions: ", 1)[1].split("\n", 1)[0].split(", ")
        self.judged.append(kwargs.get("model"))
        return _result({q: {"score": 2, "reason": "low", "line": ""} for q in asked})


def test_two_judges_of_a_day_are_compared_act_by_act(plan_then_write):
    before = R.run([DAY_SURFACE], client=DayWriter(), ids=["d-b1-g4.4"])
    # «Le fil» is asked the page's questions; «À côté» and «Le soir» also «new».
    asked = len(judged("page")) + 2 * len(judged(DAY_SURFACE))

    again = R.rejudge(before, judge_client=DayWriter(), judge_model=R.PAGE_JUDGE)
    same = R.judge_agreement(before, again)[DAY_SURFACE]
    assert (same["verdicts"], same["agreement"], same["flips"]) == (asked, 1.0, [])

    low = LowJudge()
    report = R.judge_agreement(before, R.rejudge(before, judge_client=low, judge_model=R.PAGE_JUDGE))[DAY_SURFACE]
    assert low.judged == [R.PAGE_JUDGE] * 3
    # Both rate «level» 2/5 on every act; every other rating falls from 4 to 2.
    assert report["verdicts"] == asked and report["agreement"] == round(3 / asked, 3)
    assert report["flips"][0] == "d-b1-g4.4 fil.natural: pass→fail"
    assert "d-b1-g4.4 soir.new: pass→fail" in report["flips"] and len(report["flips"]) == asked - 3


def test_acts_the_run_s_cap_cannot_hold_are_not_written_and_not_scored(plan_then_write):
    client = DayWriter()
    client.writer.cap_usd = 0.5  # under one act at its dearest and the judge's readings
    client.writer.spent_usd = 0.0
    output = S.run_day(S.load_items(DAY_SURFACE, ["d-a2-g2.5"])[0], client.writer)

    first, soir = output["acts"]
    assert not first["failure"] and soir == {"role": "soir", "failure": None, "not_run": soir["not_run"]}
    assert "spending cap" in soir["not_run"]
    assert S.checks(DAY_SURFACE, {}, output) == {"fil.served": ("pass", "")}


def test_the_weekly_day_run_writes_one_day_of_the_set_in_turn():
    items = S.load_items(DAY_SURFACE)
    weeks = [R.week_day(items, date.fromisocalendar(2026, week, 7))[0]["id"] for week in (45, 46, 47, 48)]
    assert sorted(weeks[:3]) == sorted(item["id"] for item in items) and weeks[3] == weeks[0]
    result = R.run([DAY_SURFACE], client=DayWriter(), when=date(2026, 11, 8), limit=1)
    assert result["surfaces"][DAY_SURFACE]["items"] == 1


def test_the_day_keeps_its_own_criteria_and_never_moves_the_weekly_trend():
    assert R.run_version(list(WEEKLY_SURFACES)) == CRITERIA_VERSION == criteria_version()
    assert R.run_version([DAY_SURFACE]) == criteria_version([DAY_SURFACE]) != CRITERIA_VERSION
    assert R.judge_for([DAY_SURFACE]) == R.PAGE_JUDGE
    with pytest.raises(ValueError, match="Claude model"):
        R.judge_for([DAY_SURFACE], "claude-sonnet-5-5")
    weekly = R.parse_history([R.render_report(_night("2026-11-08", 70.0), [])])
    day = {
        "date": "2026-11-08", "label": "production", "criteria": criteria_version([DAY_SURFACE]),
        "judge": R.PAGE_JUDGE, "scores": {DAY_SURFACE: 60.0}, "spent": 1.4, "days": ["d-a1-g1.3"],
    }
    report = R.render_report(_night("2026-11-15", 72.0), [*weekly, day])
    assert "| +2 |" in report and "The criteria changed" not in report


def test_the_day_runs_on_its_own_and_posts_as_the_week_s_day(monkeypatch, capsys):
    from scripts import gold_transcripts as cli

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert cli.main(["plan", "--surface", DAY_SURFACE, "--surface", "scene"]) == 2
    assert "runs on its own" in capsys.readouterr().out

    def args(*argv):
        parsed = SimpleNamespace(label="production", post_comparison=False, limit=None, id=None, surface=None)
        for key, value in zip(argv[::2], argv[1::2], strict=True):
            setattr(parsed, key, value)
        return parsed

    assert cli._not_posted(args()) is None
    assert cli._not_posted(args("surface", [DAY_SURFACE])) is None
    assert "partial" in cli._not_posted(args("surface", [DAY_SURFACE], "id", ["d-b1-g4.4"]))
    assert "partial" in cli._not_posted(args("surface", ["scene"]))
    assert "comparison" in cli._not_posted(args("surface", [DAY_SURFACE], "label", "acts-first"))

