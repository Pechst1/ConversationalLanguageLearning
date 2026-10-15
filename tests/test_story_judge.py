"""Story-quality plan, Phase 1, «Maßstab»: the judge (``app/services/season/story_judge.py``).

No network: every call goes to a fake client that answers the way the judge would.

1. A real live-read transcript reads as its generated pages, each with yesterday's summary,
   and the readability baseline's ``days``/``classify`` view of it is kept.
2. The rubric's scores aggregate to medians and counts, the lowest lines and the plan's gate.
3. «new» is not asked of a page with no previous page.
4. The pairwise order is seeded, and the judge's A/B maps back to old and new.
5. The spend cap stops the run before a call could pass it, and says what it skipped.
6. The benchmark reads the authored tentpole pages at B1, in French.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from app.services.llm_service import LLMResult, estimate_text_cost_usd
from app.services.season.story_judge import (
    QUESTIONS,
    Judge,
    SpendCapReached,
    benchmark_pages,
    call_ceiling_usd,
    classify,
    days,
    gate,
    generated_pages,
    load_transcript,
    markdown,
    pairwise_plan,
    pairwise_report,
    questions_for,
    rubric_messages,
    rubric_report,
)

EVIDENCE = Path(__file__).resolve().parents[1] / "docs/implementation/atelier-v2/evidence"
OLD_B1 = EVIDENCE / "loss-rate-2026-10-07/run2-b1/B1.1.md"
NEW_B1 = EVIDENCE / "wp149-confirmation/b1/B1.1.md"
#: A transcript that opens on a generated day: there is no page before it.
FIRST_DAY_ONLY = EVIDENCE / "loss-rate-2026-10-07/topup/live-b1/B1.1.md"


class FakeJudge:
    """``generate_chat_completion`` as LLMService has it; ``answer(user)`` writes the JSON."""

    def __init__(self, answer, *, cost: float = 0.01) -> None:
        self.answer = answer
        self.cost = cost
        self.calls: list[dict[str, Any]] = []

    def generate_chat_completion(self, messages, **kwargs: Any) -> LLMResult:
        self.calls.append({"messages": list(messages), **kwargs})
        content = json.dumps(self.answer(messages[-1]["content"]), ensure_ascii=False)
        return LLMResult(
            "openai", kwargs.get("model") or "fake", content, 900, 300, 1200, self.cost, {}
        )


def asked(user: str) -> list[str]:
    return re.search(r"^Questions: (.*)$", user, re.M).group(1).split(", ")


def scored(scores: dict[str, Any]):
    """An answer giving each asked question its score from ``scores``."""

    def answer(user: str) -> dict[str, Any]:
        return {
            key: {"score": scores[key], "reason": f"{key}: why", "line": f"{key} line"}
            for key in asked(user)
        }

    return answer


ALL_FOURS = dict.fromkeys(QUESTIONS, 4)


# ---------------------------------------------------------------------------
# 1. A real transcript
# ---------------------------------------------------------------------------


def test_a_real_transcript_reads_as_its_generated_pages_with_yesterday_for_new():
    pages = load_transcript(OLD_B1)

    # Day 32 re-read T4 B after a lost day: no page of its own, so not a page here.
    assert [(page.key, page.day) for page in pages] == [
        ("t4.a", 25),
        ("t4.b", 26),
        ("g4.1", 27),
        ("g4.2", 28),
        ("g4.3", 29),
        ("g4.4", 30),
        ("g4.5", 31),
    ]
    generated = generated_pages(pages)
    assert [page.key for page in generated] == ["g4.1", "g4.2", "g4.3", "g4.4", "g4.5"]
    assert {page.level for page in pages} == {"B1"}, "read from «niveau B1.1» in the header"

    first = generated[0]
    assert first.title == "Le choix de Lila"
    text = first.text
    assert text.startswith("Caption: Le lendemain de la dispute. Vous êtes chez Marin et Lila.")
    assert "Lila Bonnet [se tourne vers toi]: «Tu as vu ce que le quartier a dit hier." in text
    assert (
        "Task line: Donne ton avis sur l'avenir de l'appartement (garder/partager/vendre)" in text
    )
    assert "Learner (scripted): «Je ne sais pas encore. Mais je ne pars pas demain.»" in text
    assert text.rstrip().endswith("attendant que tu reviennes avec une réponse claire.")
    assert "Checklist" not in text and "petit moment" not in text, (
        "the director's notes are not on the page"
    )

    # Yesterday of the first generated day is the authored T4 B; of the second, g4.1.
    assert first.previous_summary.startswith("«La photographie» · opens: Gus climbs down")
    assert "Romy Tremblay: «Tu veux que j'oublie ?»" in first.previous_summary
    assert generated[1].previous_summary.startswith(
        "«Le choix de Lila» · opens: Le lendemain de la dispute. Vous êtes chez Marin et Lila."
    )
    assert "Lila Bonnet: «Tu as vu ce que le quartier a dit hier." in generated[1].previous_summary


def test_the_baseline_view_of_a_day_is_kept():
    text = OLD_B1.read_text(encoding="utf-8")
    assert len(list(days(text))) == 5
    page, replies, task = classify(next(days(text)))
    assert task.startswith("Donne ton avis sur l'avenir de l'appartement")
    assert page[0][0] == "caption" and page[0][1].startswith("Le lendemain de la dispute.")
    assert page[1:3] == [
        ("caption", "Le matin après la dispute. Lila a dormi peu. La clé est sur la table."),
        ("line", "Cette soupe refroidit si personne ne la prend, hein ?"),
    ]
    assert len(page) == 10
    assert replies[0] == (
        "line",
        "Ah, bon. Ça me rassure d'entendre que tu restes — un peu. Merci.",
    )
    assert replies[-1][0] == "caption" and replies[-1][1].startswith(
        "Lila sourit et se détend un peu"
    )


# ---------------------------------------------------------------------------
# 2. Aggregation and the gate
# ---------------------------------------------------------------------------


def test_rubric_scores_aggregate_to_medians_counts_lowest_lines_and_the_gate():
    pages = generated_pages(load_transcript(OLD_B1))[:3]
    answers = iter(
        [
            {
                "natural": 4,
                "clear_question": 5,
                "something_happens": 2,
                "new": 3,
                "voices": 4,
                "level": 5,
            },
            {
                "natural": 5,
                "clear_question": 4,
                "something_happens": 3,
                "new": 1,
                "voices": 3,
                "level": 4,
            },
            # A score off the scale counts in no median.
            {
                "natural": 3,
                "clear_question": 4,
                "something_happens": 2,
                "new": 2,
                "voices": "7",
                "level": 4,
            },
        ]
    )
    fake = FakeJudge(lambda user: scored(next(answers))(user))

    report = rubric_report(pages, Judge(client=fake, model="gpt-5.5"), sources=[str(OLD_B1)])

    summary = report["summary"]
    assert {key: (row["median"], row["count"]) for key, row in summary.items()} == {
        "natural": (4, 3),
        "clear_question": (4, 3),
        "something_happens": (2, 3),
        "new": (2, 3),
        "voices": (3.5, 2),
        "level": (4, 3),
    }
    assert report["pages"][2]["scores"]["voices"] == {
        "score": None,
        "reason": "voices: why",
        "line": "voices line",
        "error": "score '7' is not 1-5",
    }
    lowest = report["lowest"]
    assert (lowest[0]["question"], lowest[0]["score"], lowest[0]["page"]) == (
        "new",
        1,
        "run2-b1/B1.1.md g4.2",
    )
    assert [row["score"] for row in lowest] == sorted(row["score"] for row in lowest)
    assert lowest[1] == {
        "question": "something_happens",
        "score": 2,
        "page": "run2-b1/B1.1.md g4.1",
        "line": "something_happens line",
        "reason": "something_happens: why",
    }
    verdict = report["gate"]
    assert verdict["verdict"] == "fail"
    assert [(row["measured"], row["ok"]) for row in verdict["criteria"]] == [
        (4, True),
        (4, True),
        ("something_happens 2", False),
    ]
    assert report["calls"] == 3 and report["spent_usd"] == pytest.approx(0.03)

    summary_md = markdown(report)
    assert "| natural | 4 | 3 | 4 5 3 |" in summary_md
    assert "| voices | 3.5 | 2 | 4 3 |" in summary_md
    assert "- new 1 · run2-b1/B1.1.md g4.2 — «new line» — new: why" in summary_md
    assert "**Gate** (plan, Phase 1): fail" in summary_md
    assert "- no question median below 3: something_happens 2 — fail" in summary_md


def test_the_gate_passes_at_four_and_three_and_needs_two_wins_in_three():
    table = {
        "natural": {"median": 4},
        "clear_question": {"median": 4.5},
        "something_happens": {"median": 3},
        "voices": {"median": 3},
        "level": {"median": 5},
    }
    assert gate(table)["verdict"] == "pass"
    assert gate({**table, "clear_question": {"median": 3.5}})["verdict"] == "fail"
    assert gate({**table, "voices": {"median": 2.5}})["verdict"] == "fail"
    assert gate({})["verdict"] == "incomplete", "nothing scored is not a pass"
    assert gate(wins=2, compared=3)["verdict"] == "pass"
    assert gate(wins=1, compared=3)["verdict"] == "fail"
    assert gate(wins=3, compared=5)["verdict"] == "fail", "3 of 5 is under 2 of 3"
    assert gate(wins=0, compared=0)["verdict"] == "incomplete"


# ---------------------------------------------------------------------------
# 3. «new» needs a previous page
# ---------------------------------------------------------------------------


def test_new_is_not_asked_without_a_previous_page():
    alone = load_transcript(FIRST_DAY_ONLY)
    assert [(page.key, page.previous_summary) for page in alone] == [("g4.6", None)]
    second = generated_pages(load_transcript(OLD_B1))[1]
    fake = FakeJudge(scored(ALL_FOURS))

    report = rubric_report([alone[0], second], Judge(client=fake, model="gpt-5.5"))

    first_user, second_user = (call["messages"][-1]["content"] for call in fake.calls)
    assert asked(first_user) == [key for key in QUESTIONS if key != "new"]
    assert "Previous day" not in first_user
    assert "- new:" not in fake.calls[0]["system_prompt"]
    assert set(report["pages"][0]["scores"]) == set(QUESTIONS) - {"new"}
    assert report["pages"][0]["previous"] is None
    assert asked(second_user) == list(QUESTIONS)
    assert "Previous day: «Le choix de Lila» · opens:" in second_user
    assert report["summary"]["new"]["count"] == 1
    # The benchmark is the rubric minus «new», whatever page came before.
    assert "new" not in questions_for(second, include_new=False)


# ---------------------------------------------------------------------------
# 4. Pairwise
# ---------------------------------------------------------------------------


def test_the_pairwise_order_is_seeded_and_the_verdict_maps_back_to_old_and_new():
    old, new = load_transcript(OLD_B1), load_transcript(NEW_B1)
    plan, unmatched = pairwise_plan(old, new)
    assert unmatched == []
    assert [(key, new_first) for key, _, _, new_first in plan] == [
        ("g4.1", True),
        ("g4.2", False),
        ("g4.3", True),
        ("g4.4", True),
        ("g4.5", True),
    ]
    assert [row[3] for row in pairwise_plan(old, new)[0]] == [row[3] for row in plan], (
        "same seed, same order"
    )
    orders = {
        tuple(row[3] for row in pairwise_plan(old, new, seed=seed)[0]) for seed in ("a", "b", "c")
    }
    assert len(orders) > 1, "another seed, another order"

    new_titles = {page.title for page in generated_pages(new)}

    def prefers_new(user: str) -> dict[str, str]:
        title_a = re.search(r"^Page A «(.*)»:$", user, re.M).group(1)
        return {"better": "A" if title_a in new_titles else "B", "reason": "Clearer question."}

    fake = FakeJudge(prefers_new)
    report = pairwise_report([(old, new)], Judge(client=fake, model="gpt-5.5"))
    assert [row["new_shown_as"] for row in report["comparisons"]] == ["A", "B", "A", "A", "A"]
    assert [row["winner"] for row in report["comparisons"]] == ["new"] * 5
    assert (report["wins_new"], report["compared"], report["gate"]["verdict"]) == (5, 5, "pass")
    first_user = fake.calls[0]["messages"][-1]["content"]
    assert "Story position: g4.1" in first_user and "Page A «La dispute sur le toit»:" in first_user

    # A judge that always says «A» hands new exactly the positions where new was shown first.
    always_a = pairwise_report(
        [(old, new)],
        Judge(client=FakeJudge(lambda user: {"better": "A", "reason": "."}), model="m"),
    )
    assert always_a["wins_new"] == 4 and always_a["gate"]["verdict"] == "pass"
    assert "| run2-b1/B1.1.md g4.2 ↔ b1/B1.1.md g4.2 | B | A | old | . |" in markdown(always_a)


# ---------------------------------------------------------------------------
# 5. The spend cap
# ---------------------------------------------------------------------------


def test_the_cap_stops_before_a_call_could_pass_it_and_says_what_it_skipped():
    pages = generated_pages(load_transcript(OLD_B1))
    fake = FakeJudge(scored(ALL_FOURS), cost=0.2)
    judge = Judge(client=fake, model="gpt-5.5", cap_usd=0.5)

    report = rubric_report(pages, judge)

    # 0.2 + 0.2 spent; a third call could cost as much as the dearest so far: 0.6 > 0.5.
    assert len(fake.calls) == 2 and report["calls"] == 2
    assert report["spent_usd"] == pytest.approx(0.4) and report["spent_usd"] <= report["cap_usd"]
    assert [row["page"] for row in report["skipped"]] == [page.label for page in pages[2:]]
    assert report["skipped"][0]["reason"].startswith("spend cap: US$0.4000 spent")
    assert report["stopped"] == report["skipped"][0]["reason"]
    with pytest.raises(SpendCapReached, match="spend cap"):
        judge.ask("system", "user")  # once stopped, every later call is refused
    assert len(fake.calls) == 2
    assert "**Skipped**" in markdown(report)

    # Before the first call: its ceiling alone (the prompt and the whole completion budget at
    # llm_service's conservative rate for unpriced gpt-5.5) is over a cap this small.
    ceiling = call_ceiling_usd("gpt-5.5", "", "", 4000)
    assert (
        ceiling
        == estimate_text_cost_usd("gpt-5.5", 32, 4000)
        > estimate_text_cost_usd("gpt-5-mini", 32, 4000)
    )
    nothing = FakeJudge(scored({}))
    tiny = rubric_report(pages, Judge(client=nothing, model="gpt-5.5", cap_usd=ceiling))
    assert nothing.calls == [] and tiny["spent_usd"] == 0 and len(tiny["skipped"]) == 5
    assert tiny["gate"]["verdict"] == "incomplete"


def test_each_call_is_one_attempt_on_one_provider_asking_for_json():
    page = generated_pages(load_transcript(OLD_B1))[0]
    messages = rubric_messages(page, questions_for(page))
    fake = FakeJudge(scored(ALL_FOURS))
    answer, cost, error = Judge(client=fake, model="gpt-5.5").ask(*messages)
    assert (answer["natural"]["score"], cost, error) == (4, 0.01, None)
    call = fake.calls[0]
    assert call["model"] == "gpt-5.5" and call["response_format"] == {"type": "json_object"}
    assert call["max_provider_attempts"] == 1 and call["disable_retries"] is True
    assert call["reasoning_effort"] == "low"
    assert "strict JSON" in call["system_prompt"] and call["messages"][0]["role"] == "user"
    # gpt-4o rejects a reasoning effort: none is sent.
    Judge(client=fake, model="gpt-4o").ask(*messages)
    assert "reasoning_effort" not in fake.calls[1]

    # A provider error is kept on the page and the run goes on.
    class Down:
        def generate_chat_completion(self, messages, **kwargs):
            raise RuntimeError("provider down")

    report = rubric_report([page], Judge(client=Down(), model="gpt-5.5"))
    assert report["pages"][0]["error"] == "RuntimeError: provider down"
    assert (report["calls"], report["failed_calls"], report["spent_usd"]) == (0, 1, 0)
    # It may still have been billed (an empty gpt-5 answer is), so the cap counts it at its
    # ceiling: a cap with room for one and a half calls lets no second call through.
    ceiling = call_ceiling_usd("gpt-5.5", *messages, 4000)
    assert report["failed_calls_up_to_usd"] == pytest.approx(ceiling)
    twice = rubric_report(
        [page, page], Judge(client=Down(), model="gpt-5.5", cap_usd=1.5 * ceiling)
    )
    assert (twice["failed_calls"], len(twice["skipped"])) == (1, 1)
    assert "(+ up to US$" in twice["skipped"][0]["reason"]


# ---------------------------------------------------------------------------
# 6. The benchmark
# ---------------------------------------------------------------------------


def test_the_benchmark_reads_each_tentpole_page_at_b1_in_french():
    pages = benchmark_pages("B1")
    assert [page.key for page in pages] == [f"t{n}.a" for n in range(1, 9)]
    t1 = pages[0]
    assert (t1.title, t1.level, t1.source) == (
        "Le mauvais accueil",
        "B1",
        "app/data/season/s1/t1.json",
    )
    text = t1.text
    # The B1 line where the bible wrote one (levels.py, page.py), not the A2 line.
    assert "Caption: Paris, un 11 novembre sous la pluie." in text
    assert "Augustin « Gus » de Roncourt: «Alors, dites-moi. Qui êtes-vous, exactement ?»" in text
    # From B1 the task line is French, as the app serves it.
    assert "Task line: Dis qui tu es et pourquoi tu es là." in text
    assert re.search(r"^Learner \(scripted\): «.+»$", text, re.M), "the bible's own example answer"
    assert text.rstrip().endswith("Caption: Deux clés, une seule porte. À suivre…")
    for note in ("la scène lit", "non posé", "Cette réplique"):
        assert all(note not in page.text for page in pages), (
            "the harness's notes never reach the judge"
        )
    t4 = pages[3].text
    assert "Question with cards: «Le feu : en bas, ou en haut ? Montre.»" in t4

    # Below B1 the line is the A2 one and the task is in the learner's own language.
    a2 = benchmark_pages("A2")[0].text
    assert "Caption: Paris. Le 11 novembre. Il pleut." in a2
    assert "Task line: Say who you are and why you are here." in a2

    fake = FakeJudge(scored(dict.fromkeys(QUESTIONS, 5)))
    report = rubric_report(
        pages[:2], Judge(client=fake, model="gpt-5.5"), mode="benchmark", include_new=False
    )
    assert report["mode"] == "benchmark" and "new" not in report["summary"]
    assert all("new" not in asked(call["messages"][-1]["content"]) for call in fake.calls)
    assert report["gate"]["verdict"] == "pass"


# ---------------------------------------------------------------------------
# The CLI
# ---------------------------------------------------------------------------


def test_the_cli_writes_the_report_and_its_summary_and_a_dry_run_calls_nothing(
    tmp_path, monkeypatch, capsys
):
    from scripts import story_judge as cli

    monkeypatch.setattr(cli, "_client", lambda: pytest.fail("a dry run builds no client"))
    assert cli.main(["benchmark", "--dry-run", "--model", "gpt-5.5"]) == 0
    printed = capsys.readouterr().out
    assert "## s1/t1.json t1.a (this call costs at most US$0.06" in printed
    assert "Task line: Dis qui tu es et pourquoi tu es là." in printed
    assert printed.rstrip().endswith(
        "8 calls planned to gpt-5.5, cap US$0.60. Dry run: no client, no call."
    )

    fake = FakeJudge(scored(ALL_FOURS))
    out = tmp_path / "b1.json"
    assert (
        cli.main(["rubric", str(OLD_B1), "--model", "gpt-5.5", "--out", str(out)], client=fake) == 0
    )
    report = json.loads(out.read_text(encoding="utf-8"))
    assert (report["mode"], len(report["pages"]), len(fake.calls)) == ("rubric", 5, 5)
    assert (tmp_path / "b1.md").read_text(encoding="utf-8").startswith("# Story judge · rubric")
    with pytest.raises(SystemExit):
        cli.main(["pairwise", str(OLD_B1)])  # transcripts come in pairs
