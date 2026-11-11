#!/usr/bin/env python
"""Which story prompts changed, and does the pipeline still hold (E-7 · Loop v2).

    python scripts/prompt_regression.py                  # check every golden case; exit 1 on a change
    python scripts/prompt_regression.py --case page-a1-clean-plusieurs-semaines
    python scripts/prompt_regression.py --update         # accept the changed prompts (rewrite snapshots)
    python scripts/prompt_regression.py --stamp          # keep the recorded answers for today's prompts
    python scripts/prompt_regression.py --live --max-usd 0.10 --case <id>   # record real answers (paid)

The golden cases live in ``tests/prompt_regression/cases``; the harness and the format
are documented in ``tests/prompt_regression/harness.py``. A check renders every case's
prompts with the current code, compares them with the committed snapshot (printing a
unified diff for each change), and replays the recorded answers through the guards.
No database, no network, no model call — except ``--live``, which refuses to run
without an API key and an explicit spending cap.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# What tests/conftest.py pins: no provider is reachable from a check, whatever .env says.
os.environ.setdefault("SECRET_KEY", "prompt-regression")
os.environ["ATELIER_LLM_ENABLED"] = "false"

from loguru import logger  # noqa: E402

from tests.prompt_regression import harness  # noqa: E402

#: The provider keys ``--live`` accepts (``app.services.llm_service``).
API_KEY_ENVS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")


def _live(cases: list[harness.Case], *, named: bool, max_usd: float | None, model: str | None) -> int:
    """Record what the real model answers to the named turn and authored cases, up to the cap.

    Owner decision ED-3 caps a run at US$1. Only the cases you name are recorded: a golden
    case built from a real failure keeps its answers, or it stops being that failure.
    """

    if not any(os.environ.get(name) for name in API_KEY_ENVS):
        print(
            f"--live refuses to run: no API key in the environment ({' or '.join(API_KEY_ENVS)})."
        )
        return 2
    if max_usd is None or max_usd <= 0:
        print(
            "--live refuses to run without an explicit spending cap: --max-usd 0.10 (owner cap: US$1 per run)."
        )
        return 2
    if max_usd > 1.0:
        print("--live refuses a cap above US$1 per run (owner decision ED-3); ask the owner first.")
        return 2
    if not named:
        print("--live records only the cases you name: --case <id> (repeatable).")
        return 2
    if any(case.lane not in ("turn", "authored") for case in cases):
        print("--live records turn and authored cases only.")
        return 2

    from app.services.llm_service import LLMService

    recorder = harness.Recorder(
        LLMService(), model=model, cap_usd=max_usd, stamp=f"live {datetime.now(UTC).date().isoformat()}"
    )
    print(f"--live: {len(cases)} case(s), model {model or 'provider default'}, capped at US${max_usd:.2f}")
    failed = 0
    for case in cases:
        observed = harness.record_case(case, recorder)
        if observed.get("failure"):
            failed += 1
            print(f"{case.id}: not recorded ({observed['failure']})")
            continue
        print(f"{case.id}: {observed['reply_fr']}")
        if observed["voice_refusals"]:
            print(f"    refused first: {observed['voice_refusals']}")
    print(f"spent US${recorder.spent:.4f} of US${max_usd:.2f}; {failed} case(s) not recorded.")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--case", action="append", help="only this golden case (repeatable)")
    parser.add_argument(
        "--update", action="store_true", help="accept the changed prompts: rewrite their snapshots"
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="mark the recorded answers as answering today's prompts",
    )
    parser.add_argument(
        "--live", action="store_true", help="record the real model's answers to the named cases (paid)"
    )
    parser.add_argument(
        "--max-usd", type=float, default=None, help="spending cap for --live (required with it)"
    )
    parser.add_argument(
        "--model", default=None, help="the model --live records with (production's STORY_LIVE_MODEL)"
    )
    parser.add_argument(
        "--no-diff", action="store_true", help="list the changed cases without their diffs"
    )
    args = parser.parse_args(argv)

    logger.remove()  # the engine logs every refusal; the report below says what matters
    cases = harness.load_cases(args.case)
    if args.case and len(cases) != len(set(args.case)):
        known = {case.id for case in harness.load_cases()}
        print(f"unknown case(s): {sorted(set(args.case) - known)}")
        return 2
    if args.live:
        return _live(cases, named=bool(args.case), max_usd=args.max_usd, model=args.model)
    results = [harness.run_case(case) for case in cases]

    changed, broken, stale = [], [], []
    for result in results:
        problem = harness.snapshot_diff(result)
        if problem:
            changed.append(result.case.id)
            if args.update:
                harness.write_snapshot(result)
            elif not args.no_diff:
                print(problem, end="\n\n")
        if args.stamp and harness.stamp_answers(result):
            print(f"stamped: {result.case.id}")
        for line in harness.check(result):
            broken.append(f"{result.case.id}: {line}")
        stale += [f"{result.case.id}: {call}" for call in harness.stale_answers(result)]

    print(
        f"{len(results)} golden case(s), {sum(len(r.calls) for r in results)} prompt(s) rendered."
    )
    if changed:
        verb = "accepted (snapshots rewritten)" if args.update else "changed vs snapshot"
        print(f"prompts {verb}: {len(changed)}")
        for case_id in changed:
            print(f"  {case_id}")
    else:
        print("prompts: unchanged.")
    if stale and not args.stamp:
        print(
            f"answers recorded against an older prompt (replayed as they are; --live refreshes, --stamp keeps): {len(stale)}"
        )
        for line in stale:
            print(f"  {line}")
    if broken:
        print(f"replay problems: {len(broken)}")
        for line in broken:
            print(f"  {line}")
    else:
        print("replay: every case holds its expectations.")
    return 1 if broken or (changed and not args.update) else 0


if __name__ == "__main__":
    sys.exit(main())
