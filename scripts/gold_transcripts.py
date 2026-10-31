#!/usr/bin/env python
"""Score the story surfaces every week on fixed learner inputs (gold transcripts).

    python scripts/gold_transcripts.py plan                       # what a run would send and cost; no key, no call
    python scripts/gold_transcripts.py run --max-usd 1.5          # paid: production prompts + models, judged
    python scripts/gold_transcripts.py run --max-usd 1.5 --post   # … and post score + trend on the digest issue (#121)
    python scripts/gold_transcripts.py run --surface scene --limit 3 --max-usd 0.2   # a quick look
    python scripts/gold_transcripts.py run --label haiku-live --set STORY_LIVE_MODEL=claude-haiku-5-5 --max-usd 1
                                                                   # same inputs, another model (a comparison run)
    python scripts/gold_transcripts.py rejudge var/gold/<date>-production.json --judge-model claude-sonnet-5-5 --max-usd 1
                                                                   # the same answers, another judge (calibrate a judge change)
    python scripts/gold_transcripts.py trend                       # the history kept in the digest comments

The inputs live in ``tests/gold_transcripts/sets/`` (20–30 per surface, taken from the live
walks), the criteria in ``tests/gold_transcripts/criteria.py``. A run drives the same code
production runs (the scene's reply lanes, La Forge's second check, the Courrier's reply and
its correction) with the settings ``render.yaml`` declares for the API service, then asks a
judge model the fixed criteria. Every call goes through a meter that refuses the call that
could pass ``--max-usd`` (at most US$2). Never run from PR CI: the weekly routine runs it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("SECRET_KEY", "gold-transcripts")
# The cloud environment keeps the Anthropic key under its own name; the app reads ANTHROPIC_API_KEY.
if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ATELIER_ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = os.environ["ATELIER_ANTHROPIC_API_KEY"]

from loguru import logger  # noqa: E402

from tests.gold_transcripts import runner as R  # noqa: E402
from tests.gold_transcripts import surfaces as S  # noqa: E402
from tests.gold_transcripts.criteria import CRITERIA, CRITERIA_VERSION  # noqa: E402

API_KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
OUT = REPO / "var" / "gold"


def _sets(args: argparse.Namespace) -> list[str]:
    return args.surface or list(S.SURFACES)


def _overrides(pairs: list[str] | None) -> dict[str, str]:
    out = {}
    for pair in pairs or []:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set wants KEY=VALUE, got {pair!r}")
        out[key.strip()] = value.strip()
    return out


class _Recorder:
    """A client that answers nothing: it records the worst-case price of every call
    the app would make and refuses it, so ``plan`` costs nothing."""

    def __init__(self) -> None:
        self.meter = R.Meter(inner=None, cap_usd=float("inf"))
        self.estimates: list[float] = []

    def _refuse(self, kind, messages, kwargs):
        from app.services.llm_service import LLMProviderError

        self.estimates.append(self.meter.worst_case(kind, messages, kwargs))
        raise LLMProviderError("plan: not sent")

    def generate_chat_completion(self, messages, **kwargs):
        return self._refuse("chat", messages, kwargs)

    def generate_error_detection(self, messages, **kwargs):
        return self._refuse("error", messages, kwargs)


def cmd_plan(args: argparse.Namespace) -> int:
    applied = R.apply_profile(_overrides(args.set))
    try:
        total_items = 0
        app_cost = 0.0
        from app.services.llm_service import text_price_for

        rates, _ = text_price_for(args.judge_model)
        judge_cost = 0.0
        for surface in _sets(args):
            items = S.load_items(surface)[: args.limit or None]
            recorder = _Recorder()
            for item in items:
                try:
                    S.SURFACES[surface](item, recorder)
                except Exception:  # noqa: BLE001, S110 - a refused call may surface as anything
                    pass
            # The judge reads ~3k characters and writes ≤1k tokens, once per item.
            per_judge = (3500 / 3 + 600) / 1000 * rates["prompt"] + 1000 / 1000 * rates["completion"]
            judge_cost += per_judge * len(items)
            app_cost += sum(recorder.estimates)
            total_items += len(items)
            print(
                f"{surface:10s} {len(items):3d} items · first-attempt app calls {len(recorder.estimates):3d} "
                f"(worst case US${sum(recorder.estimates):.3f}) · judge worst case US${per_judge * len(items):.3f}"
            )
        print(f"criteria {CRITERIA_VERSION} · {total_items} items · judge {args.judge_model}")
        print(f"worst case ≈ US${app_cost + judge_cost:.2f} (retries not counted; the meter caps the real run)")
        print("models: " + json.dumps(R.models_in_use(), ensure_ascii=False))
    finally:
        R.restore_profile(applied)
    return 0


def _refuse_paid(args: argparse.Namespace, command: str = "run") -> int | None:
    if not any(os.environ.get(name) for name in API_KEY_ENVS):
        print(f"{command} refuses: no API key in the environment ({' or '.join(API_KEY_ENVS)}).")
        return 2
    if args.max_usd is None or args.max_usd <= 0:
        print(f"{command} refuses without an explicit cap: --max-usd {R.DEFAULT_CAP_USD} (owner rule: about US$1–2 a run).")
        return 2
    if args.max_usd > R.HARD_CAP_USD:
        print(f"{command} refuses a cap above US${R.HARD_CAP_USD:.2f} a run; ask the owner first.")
        return 2
    if os.environ.get("CI") and not args.allow_ci:
        print(f"{command} refuses inside CI: gold transcripts are paid and run from the weekly routine only.")
        return 2
    return None


def cmd_run(args: argparse.Namespace) -> int:
    refused = _refuse_paid(args)
    if refused is not None:
        return refused
    from app.services.llm_service import LLMService

    applied = R.apply_profile(_overrides(args.set))
    date = args.date or datetime.now(UTC).strftime("%Y-%m-%d")
    try:
        meter = R.Meter(inner=LLMService(), cap_usd=args.max_usd)
        result = R.run(
            _sets(args), client=meter, judge_model=args.judge_model, limit=args.limit, ids=args.id,
            progress=(lambda line: print(line, flush=True)) if args.verbose else None,
        )
        result.update(
            date=date, label=args.label, cap_usd=args.max_usd, spent_usd=round(meter.spent_usd, 4),
            calls=meter.calls, models=R.models_in_use(),
            settings_overrides=_overrides(args.set), call_log=meter.log,
        )
    finally:
        R.restore_profile(applied)
    OUT.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else OUT / f"{date}-{args.label}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    history: list[dict] = []
    try:
        history = R.parse_history(R.issue_comment_bodies())
    except Exception as exc:  # noqa: BLE001 - the report still prints without its trend
        print(f"(trend unavailable: {exc})")
    report = R.render_report(result, history)
    (out.with_suffix(".md")).write_text(report + "\n", encoding="utf-8")
    print(report)
    print(f"\nfull results: {out}")
    if args.post:
        if args.label != "production" and not args.post_comparison:
            print("not posted: a comparison run (--label) posts only with --post-comparison.")
        elif args.limit or args.id or args.surface:
            print("not posted: a partial run (--limit/--id/--surface) is not a production score.")
        else:
            print("posted: " + R.post_comment(report))
    return 0


def cmd_rejudge(args: argparse.Namespace) -> int:
    """Score a saved run's answers with another judge and compare the two judges."""

    refused = _refuse_paid(args, "rejudge")
    if refused is not None:
        return refused
    from app.services.llm_service import LLMService

    source = Path(args.results)
    before = json.loads(source.read_text(encoding="utf-8"))
    applied = R.apply_profile()
    try:
        meter = R.Meter(inner=LLMService(), cap_usd=args.max_usd)
        meter.role = "judge"
        after = R.rejudge(
            before, judge_client=meter, judge_model=args.judge_model,
            progress=(lambda line: print(line, flush=True)) if args.verbose else None,
        )
        after.update(spent_usd=round(meter.spent_usd, 4), cap_usd=args.max_usd, call_log=meter.log)
    finally:
        R.restore_profile(applied)
    out = source.with_name(f"{source.stem}-judge-{args.judge_model}.json")
    out.write_text(json.dumps(after, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(f"judge {before.get('judge_model')} → {args.judge_model} on the answers of {source.name}")
    print(f"{'surface':12s} {'old':>5s} {'new':>5s}  verdicts agree")
    for surface, row in R.judge_agreement(before, after).items():
        old = "–" if row["score_a"] is None else f"{row['score_a']:.0f}"
        new = "–" if row["score_b"] is None else f"{row['score_b']:.0f}"
        agree = "–" if row["agreement"] is None else f"{100 * row['agreement']:.0f}% of {row['verdicts']}"
        print(f"{surface:12s} {old:>5s} {new:>5s}  {agree}")
        for flip in row["flips"][: args.show_flips]:
            print(f"    {flip}")
    print(f"spent US${meter.spent_usd:.3f} · full results: {out}")
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    history = R.parse_history(R.issue_comment_bodies())
    if not history:
        print("no gold scores on the digest issue yet.")
        return 0
    surfaces = list(CRITERIA)
    print("date        label        criteria      " + "  ".join(f"{s:>10s}" for s in surfaces) + "   spent")
    for entry in history[-args.nights:]:
        cells = "  ".join(
            f"{entry['scores'].get(s):>10.0f}" if entry["scores"].get(s) is not None else f"{'–':>10s}" for s in surfaces
        )
        print(f"{entry['date']}  {entry['label']:<12s} {entry['criteria']:<13s} {cells}   ${entry.get('spent', 0):.2f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--surface", action="append", choices=list(S.SURFACES), help="only this surface (repeatable)")
        p.add_argument("--limit", type=int, default=None, help="only the first N items of each surface")
        p.add_argument("--set", action="append", metavar="KEY=VALUE", help="an app setting on top of render.yaml (repeatable)")
        p.add_argument("--judge-model", default=R.DEFAULT_JUDGE)
    run = sub.choices["run"]
    run.add_argument("--max-usd", type=float, default=None, help=f"spending cap (required, at most {R.HARD_CAP_USD})")
    run.add_argument("--id", action="append", help="only this item (repeatable)")
    run.add_argument("--label", default="production", help="the run's name in the history; anything but «production» is a comparison")
    run.add_argument("--date", default=None, help="the run's date (default: today, UTC)")
    run.add_argument("--out", default=None, help="where the full results JSON goes (default var/gold/<date>-<label>.json)")
    run.add_argument("--post", action="store_true", help=f"post the report on issue #{R.DIGEST_ISSUE}")
    run.add_argument("--post-comparison", action="store_true", help="allow --post for a comparison run")
    run.add_argument("--allow-ci", action="store_true", help=argparse.SUPPRESS)
    run.add_argument("--verbose", "-v", action="store_true")
    rejudge = sub.add_parser("rejudge", help="score a saved run's answers with another judge")
    rejudge.add_argument("results", help="a results JSON written by run (var/gold/<date>-<label>.json)")
    rejudge.add_argument("--judge-model", required=True)
    rejudge.add_argument("--max-usd", type=float, default=None, help=f"spending cap (required, at most {R.HARD_CAP_USD})")
    rejudge.add_argument("--show-flips", type=int, default=8, help="verdicts that changed, shown per surface")
    rejudge.add_argument("--allow-ci", action="store_true", help=argparse.SUPPRESS)
    rejudge.add_argument("--verbose", "-v", action="store_true")
    trend = sub.add_parser("trend")
    trend.add_argument("--runs", "--nights", dest="nights", type=int, default=14)
    args = parser.parse_args(argv)

    logger.remove()  # the engine logs every refusal; the report says what matters
    return {"plan": cmd_plan, "run": cmd_run, "rejudge": cmd_rejudge, "trend": cmd_trend}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
