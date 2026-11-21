#!/usr/bin/env python
"""Score the story surfaces every week on fixed learner inputs (gold transcripts).

    python scripts/gold_transcripts.py plan                       # what a run would send and cost; no key, no call
    python scripts/gold_transcripts.py run --max-usd 1.5          # paid: production prompts + models, judged
    python scripts/gold_transcripts.py run --max-usd 1.5 --post   # … and post score + trend on the digest issue (#121)
    python scripts/gold_transcripts.py run --surface scene --limit 3 --max-usd 0.2   # a quick look
    python scripts/gold_transcripts.py run --label haiku-live --set STORY_LIVE_MODEL=claude-haiku-5-5 --max-usd 1
                                                                   # same inputs, another model (a comparison run)
    python scripts/gold_transcripts.py run --surface page --label writer-sonnet --set STORY_WRITER_MODEL=claude-sonnet-5-5 --max-usd 1.5
                                                                   # the night writer's pages (not in the weekly run)
    python scripts/gold_transcripts.py run --surface day --max-usd 2 --post
                                                                   # a whole day of acts, one day of the set a week (its own run)
    python scripts/gold_transcripts.py rejudge var/gold/<date>-production.json --judge-model claude-sonnet-5-5 --max-usd 1
                                                                   # the same answers, another judge (calibrate a judge change)
    python scripts/gold_transcripts.py trend                       # the history kept in the digest comments
    python scripts/gold_transcripts.py check                       # free, in PR CI: did prompts or models change ungated?
    python scripts/gold_transcripts.py gate --max-usd 1.5          # paid: base vs this checkout on the changed surfaces;
                                                                   # a surface that holds or rises is written to gate.json

The inputs live in ``tests/gold_transcripts/sets/`` (20–30 per surface, taken from the live
walks), the criteria in ``tests/gold_transcripts/criteria.py``. A run drives the same code
production runs (the scene's reply lanes, La Forge's second check, the Courrier's reply and
its correction) with the settings ``render.yaml`` declares for the API service, then asks a
judge model the fixed criteria. Every call goes through a meter that refuses the call that
could pass ``--max-usd`` (at most US$2). Never run from PR CI: the nightly routine runs it.

The gate (``tests/gold_transcripts/gate.py``): ``check`` is free and runs in PR CI; it
fails when what the weekly surfaces send a model (prompts, models, parameters) differs
from what last passed ``gate``. ``gate`` is paid and is run by whoever made the change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, date, datetime
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
from tests.gold_transcripts.criteria import (  # noqa: E402
    CRITERIA,
    DAY_SURFACE,
    WEEKLY_SURFACES,
    run_version,
)

API_KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")
OUT = REPO / "var" / "gold"


def _sets(args: argparse.Namespace) -> list[str]:
    return list(dict.fromkeys(args.surface)) if args.surface else list(WEEKLY_SURFACES)


def _when(args: argparse.Namespace) -> date:
    """The run's date: which day of the set a weekly day run writes (``runner.week_day``)."""

    return date.fromisoformat(args.date) if args.date else datetime.now(UTC).date()


def _day_items(args: argparse.Namespace) -> list[dict]:
    """The days a day run writes: the ones named, else the week's day."""

    items = S.load_items(DAY_SURFACE, args.id)
    return (items if args.id else R.week_day(items, _when(args)))[: args.limit or None]


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


def _plan_day(args: argparse.Namespace, per_judge: float) -> tuple[int, float, float]:
    """A day of acts priced from what the night writer measured (``runner.NIGHT_WRITER_USD``):
    a refused call stops the day at its first, so recording it would price one call."""

    from app.config import settings

    writer = str(settings.STORY_WRITER_MODEL or "")
    measured = R.NIGHT_WRITER_USD.get(writer)
    items = _day_items(args)
    app_cost = judge_cost = 0.0
    for item in items:
        roles = S.day_roles(item)
        acts = 1 + len(roles)
        judge_cost += per_judge * acts
        if measured is None:
            print(f"{DAY_SURFACE:10s} {item['id']}: «Le fil» + {', '.join(roles) or 'no later act'} · writer {writer} not measured")
            continue
        typical = measured["page"] + measured["act"] * len(roles)
        dearest = measured["page"] + measured["act_dearest"] * len(roles)
        app_cost += dearest
        print(
            f"{DAY_SURFACE:10s} {item['id']}: «Le fil» + {', '.join(roles) or 'no later act'} · writer {writer} "
            f"measured about US${typical:.2f}, at most US${dearest:.2f} · judge worst case US${per_judge * acts:.3f}"
        )
    return len(items), app_cost, judge_cost


def cmd_plan(args: argparse.Namespace) -> int:
    applied = R.apply_profile(_overrides(args.set))
    try:
        total_items = 0
        app_cost = 0.0
        from app.services.llm_service import text_price_for

        rates, _ = text_price_for(args.judge_model)
        # The judge reads ~3k characters and writes ≤1k tokens, once per item (per act).
        per_judge = (3500 / 3 + 600) / 1000 * rates["prompt"] + 1000 / 1000 * rates["completion"]
        judge_cost = 0.0
        for surface in _sets(args):
            if surface == DAY_SURFACE:
                count, app, judge = _plan_day(args, per_judge)
                total_items += count
                app_cost += app
                judge_cost += judge
                continue
            items = S.load_items(surface, args.id)[: args.limit or None]
            recorder = _Recorder()
            for item in items:
                try:
                    S.SURFACES[surface](item, recorder)
                except Exception:  # noqa: BLE001, S110 - a refused call may surface as anything
                    pass
            judge_cost += per_judge * len(items)
            app_cost += sum(recorder.estimates)
            total_items += len(items)
            print(
                f"{surface:10s} {len(items):3d} items · first-attempt app calls {len(recorder.estimates):3d} "
                f"(worst case US${sum(recorder.estimates):.3f}) · judge worst case US${per_judge * len(items):.3f}"
            )
        print(f"criteria {run_version(_sets(args))} · {total_items} items · judge {args.judge_model}")
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
    when = _when(args)
    day = when.isoformat()
    try:
        meter = R.Meter(inner=LLMService(), cap_usd=args.max_usd)
        result = R.run(
            _sets(args), client=meter, judge_model=args.judge_model, limit=args.limit, ids=args.id,
            progress=(lambda line: print(line, flush=True)) if args.verbose else None, when=when,
        )
        result.update(
            date=day, label=args.label, cap_usd=args.max_usd, spent_usd=round(meter.spent_usd, 4),
            calls=meter.calls, models=R.models_in_use(),
            settings_overrides=_overrides(args.set), call_log=meter.log,
        )
    finally:
        R.restore_profile(applied)
    OUT.mkdir(parents=True, exist_ok=True)
    name = args.label if _sets(args) != [DAY_SURFACE] else f"{args.label}-day"
    out = Path(args.out) if args.out else OUT / f"{day}-{name}.json"
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
    dead = _dead_run(result)
    if dead:
        print(f"\nthe model did not answer: {dead}. Most likely an expired or missing key, or an outage.")
    if args.post:
        why = _not_posted(args) or (dead and "most answers fell back, so the scores would only say the model was unreachable")
        print(f"not posted: {why}." if why else "posted: " + R.post_comment(report))
    return 1 if dead else 0


def _dead_run(result: dict) -> str | None:
    """Why a run measured nothing: every surface run fell back on more than half its items
    (on 14 Nov an expired key scored every surface 0). Such a run is kept out of the trend."""

    surfaces = result.get("surfaces") or {}
    counts = {s: (v.get("failed_outright") or 0, v.get("items") or 0) for s, v in surfaces.items()}
    if counts and all(total and failed > total / 2 for failed, total in counts.values()):
        return ", ".join(f"{s} {failed}/{total} fell back" for s, (failed, total) in counts.items())
    return None


def _not_posted(args: argparse.Namespace) -> str | None:
    """Why a run's report stays off the digest issue; ``None`` when it is posted. The
    weekly run and the week's day of acts (``--surface day`` alone) are the production
    scores; anything narrower is a look."""

    if args.label != "production" and not args.post_comparison:
        return "a comparison run (--label) posts only with --post-comparison"
    if args.limit or args.id or (args.surface and _sets(args) != [DAY_SURFACE]):
        return "a partial run (--limit/--id/--surface) is not a production score"
    return None


def cmd_rejudge(args: argparse.Namespace) -> int:
    """Score a saved run's answers with another judge and compare the two judges."""

    source = Path(args.results)
    before = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {}
    try:
        R.judge_for(list(before.get("items") or {}), args.judge_model)
    except ValueError as exc:
        print(f"rejudge refuses: {exc}.")
        return 2
    refused = _refuse_paid(args, "rejudge")
    if refused is not None:
        return refused
    if not before:
        print(f"rejudge refuses: no results at {source}.")
        return 2
    from app.services.llm_service import LLMService
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
    # A day run's entry has the day score alone, under the day's own criteria version.
    for entry in history[-args.nights:]:
        cells = "  ".join(
            f"{entry['scores'].get(s):>10.0f}" if entry["scores"].get(s) is not None else f"{'–':>10s}" for s in surfaces
        )
        print(f"{entry['date']}  {entry['label']:<12s} {entry['criteria']:<13s} {cells}   ${entry.get('spent', 0):.2f}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Free: fail when a surface's prompts or models differ from what last passed the gate."""

    from tests.gold_transcripts import gate as G

    current = G.fingerprints()
    gate = G.load_gate()
    todo = G.stale(current, gate)
    for surface, now in current.items():
        mark = "STALE " if surface in todo else "gated "
        print(f"{mark}{surface:10s} {now['fingerprint']}  {now['calls']:3d} calls"
              + (f"  ({todo[surface]})" if surface in todo else ""))
    if not todo:
        print("gold gate: every surface's prompts and models passed the gate.")
        return 0
    print(
        f"\ngold gate: {', '.join(todo)} changed what a model is asked or which model answers. Before this can merge,\n"
        "run the paired gold run and commit the gate.json it writes (needs OPENAI_API_KEY and ANTHROPIC_API_KEY):\n"
        "    python scripts/gold_transcripts.py gate --max-usd 1.5\n"
        "A surface that falls by more than "
        f"{G.TOLERANCE:g} points stays blocked. See tests/gold_transcripts/README.md, «The gate»."
    )
    return 1


def _git(*argv: str, cwd: Path = REPO) -> str:
    return subprocess.run(["git", *argv], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603, S607


def _run_side(root: Path, label: str, surfaces: list[str], cap: float, out: Path, log: Path) -> subprocess.Popen:
    argv = [sys.executable, str(root / "scripts" / "gold_transcripts.py"), "run", "--label", label,
            "--max-usd", f"{cap:.2f}", "--out", str(out)]
    for surface in surfaces:
        argv += ["--surface", surface]
    env = dict(os.environ, GOLD_GATE_SIDE=label)
    return subprocess.Popen(argv, cwd=root, stdout=log.open("w"), stderr=subprocess.STDOUT, env=env)  # noqa: S603


def cmd_gate(args: argparse.Namespace) -> int:
    """Paid: the changed surfaces, base against this checkout, paired item by item."""

    from tests.gold_transcripts import gate as G

    current = G.fingerprints()
    gate = G.load_gate()
    if args.baseline:
        # Bootstrapping only: a surface the gate has never seen takes today's fingerprint as
        # its starting point, without a run. A surface already in gate.json is never reset.
        entries = gate.setdefault("surfaces", {})
        added = [s for s in current if s not in entries]
        for surface in added:
            entries[surface] = {**current[surface], "verdict": "baseline", "date": _when(args).isoformat(),
                                "base_ref": _git("rev-parse", "--short=9", "HEAD")}
        G.save_gate(gate)
        print(f"gold gate: baseline for {', '.join(added) or 'no surface (all already gated)'}.")
        return 0
    refused = _refuse_paid(args, "gate")
    if refused is not None:
        return refused
    if args.surface:
        surfaces = list(dict.fromkeys(args.surface))
    elif args.all:
        surfaces = list(WEEKLY_SURFACES)
    else:
        surfaces = list(G.stale(current, gate))
    if not surfaces:
        print("gold gate: nothing to run, every surface is gated.")
        return 0
    base_sha = _git("merge-base", "HEAD", args.base)
    head_sha = _git("rev-parse", "HEAD")
    dirty = bool(_git("status", "--porcelain", "--untracked-files=no"))
    head_ref = head_sha[:9] + (" + uncommitted changes" if dirty else "")
    print(f"gold gate: {', '.join(surfaces)} · base {args.base} ({base_sha[:9]}) · head {head_ref} · cap US${args.max_usd:.2f}")
    work = Path(tempfile.mkdtemp(prefix="gold-gate-"))
    base_root = work / "base"
    _git("worktree", "add", "--detach", str(base_root), base_sha)
    try:
        # Both sides are asked the same questions: this checkout's inputs and criteria.
        here = REPO / "tests" / "gold_transcripts"
        there = base_root / "tests" / "gold_transcripts"
        shutil.rmtree(there / "sets")
        shutil.copytree(here / "sets", there / "sets")
        shutil.copy2(here / "criteria.py", there / "criteria.py")
        half = args.max_usd / 2
        sides = {
            "base": (_run_side(base_root, "gate-base", surfaces, half, work / "base.json", work / "base.log")),
            "head": (_run_side(REPO, "gate-head", surfaces, half, work / "head.json", work / "head.log")),
        }
        failed = []
        for name, proc in sides.items():
            if proc.wait() != 0 or not (work / f"{name}.json").exists():
                failed.append(name)
        if failed:
            for name in failed:
                print(f"--- {name} run failed; its last lines:")
                print("\n".join((work / f"{name}.log").read_text(encoding="utf-8").splitlines()[-15:]))
            return 1
        base = json.loads((work / "base.json").read_text(encoding="utf-8"))
        head = json.loads((work / "head.json").read_text(encoding="utf-8"))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(base_root)], cwd=REPO, check=False)  # noqa: S603, S607
    spent = float(base.get("spent_usd") or 0) + float(head.get("spent_usd") or 0)
    rows = {surface: G.compare(base, head, surface) for surface in surfaces}
    report = G.render(rows, base_ref=f"{args.base} {base_sha[:9]}", head_ref=head_ref, spent=spent)
    print(report)
    day = _when(args).isoformat()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, result in (("base", base), ("head", head)):
        (OUT / f"{day}-gate-{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    (OUT / f"{day}-gate.md").write_text(report + "\n", encoding="utf-8")
    entries = gate.setdefault("surfaces", {})
    for surface, row in rows.items():
        if row["verdict"] not in G.PASSING:
            continue
        entries[surface] = {
            "fingerprint": current[surface]["fingerprint"], "calls": current[surface]["calls"],
            "verdict": row["verdict"], "base": row["base"], "head": row["head"], "diff": row["diff"],
            "paired": row["paired"], "date": day, "base_ref": base_sha[:9],
            "criteria": head.get("criteria_version"), "judge": head.get("judge_model"),
        }
    if args.calibrate:
        gate["calibration"] = {
            "date": day, "ref": base_sha[:9], "judge": head.get("judge_model"), "spent_usd": round(spent, 2),
            "diffs": {surface: row["diff"] for surface, row in rows.items()},
        }
    G.save_gate(gate)
    blocked = [s for s, row in rows.items() if row["verdict"] not in G.PASSING]
    print(f"\nreport: {OUT / (day + '-gate.md')} · gate.json updated for "
          f"{', '.join(s for s in rows if s not in blocked) or 'no surface'}")
    if blocked:
        print("blocked: " + ", ".join(f"{s} ({rows[s]['verdict']})" for s in blocked))
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--surface", action="append", choices=list(S.SURFACES), help="only this surface (repeatable)")
        p.add_argument("--limit", type=int, default=None, help="only the first N items of each surface")
        p.add_argument("--set", action="append", metavar="KEY=VALUE", help="an app setting on top of render.yaml (repeatable)")
        p.add_argument("--judge-model", default=None, help=f"default {R.DEFAULT_JUDGE}; {R.PAGE_JUDGE} when pages are scored")
        p.add_argument("--id", action="append", help="only this item (repeatable)")
        p.add_argument("--date", default=None, help="the run's date (default: today, UTC); picks the week's day of acts")
    run = sub.choices["run"]
    run.add_argument("--max-usd", type=float, default=None, help=f"spending cap (required, at most {R.HARD_CAP_USD})")
    run.add_argument("--label", default="production", help="the run's name in the history; anything but «production» is a comparison")
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
    sub.add_parser("check", help="free: fail when prompts or models changed since they last passed the gate")
    gate = sub.add_parser("gate", help="paid: base against this checkout on the changed surfaces, paired")
    gate.add_argument("--max-usd", type=float, default=None, help=f"spending cap for both sides (required, at most {R.HARD_CAP_USD})")
    gate.add_argument("--base", default="origin/main", help="the base to compare with (its merge-base with HEAD)")
    gate.add_argument("--surface", action="append", choices=list(WEEKLY_SURFACES), help="gate this surface even if unchanged")
    gate.add_argument("--all", action="store_true", help="gate every weekly surface")
    gate.add_argument("--calibrate", action="store_true", help="record the paired differences as the noise calibration")
    gate.add_argument("--baseline", action="store_true",
                      help="free, bootstrapping only: accept today's fingerprint for surfaces never gated")
    gate.add_argument("--date", default=None, help=argparse.SUPPRESS)
    gate.add_argument("--allow-ci", action="store_true", help=argparse.SUPPRESS)
    trend = sub.add_parser("trend")
    trend.add_argument("--runs", "--nights", dest="nights", type=int, default=14)
    args = parser.parse_args(argv)

    logger.remove()  # the engine logs every refusal; the report says what matters
    if args.command in ("plan", "run"):
        if DAY_SURFACE in _sets(args) and _sets(args) != [DAY_SURFACE]:
            print(f"{args.command} refuses: the day of acts runs on its own (--surface {DAY_SURFACE}), with its own cap and comment.")
            return 2
        try:
            args.judge_model = R.judge_for(_sets(args), args.judge_model)
        except ValueError as exc:
            print(f"{args.command} refuses: {exc}.")
            return 2
    commands = {"plan": cmd_plan, "run": cmd_run, "rejudge": cmd_rejudge, "trend": cmd_trend,
                "check": cmd_check, "gate": cmd_gate}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
