#!/usr/bin/env python
"""Which story prompts changed, and does the pipeline still hold (E-7 · Loop v2).

    python scripts/prompt_regression.py                  # check every golden case; exit 1 on a change
    python scripts/prompt_regression.py --case page-a1-clean-plusieurs-semaines
    python scripts/prompt_regression.py --update         # accept the changed prompts (rewrite snapshots)
    python scripts/prompt_regression.py --stamp          # keep the recorded answers for today's prompts
    python scripts/prompt_regression.py --live --max-usd 0.10   # refresh stale answers (stub, see below)

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


def _live(results: list[harness.Result], max_usd: float | None) -> int:
    """Refresh the recorded answers whose prompt changed — guard, plan, then stop.

    Stub (owner decision ED-3 caps a run at US$1): it checks the key and the cap,
    and lists the calls a refresh would pay for. The paid path itself — one real
    call per stale answer through ``LLMService``, a running total that stops at the
    cap, the answers written back with their new ``prompt_digest`` and a cache under
    ``var/prompt-cache/`` — is not built yet.
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
    stale = [(result.case.id, call) for result in results for call in harness.stale_answers(result)]
    if not stale:
        print("--live: every recorded answer answers today's prompt; nothing to pay for (US$0).")
        return 0
    print(f"--live would refresh {len(stale)} answer(s), capped at US${max_usd:.2f}:")
    for case_id, call in stale:
        print(f"  {case_id}: {call}")
    print("--live is a stub: the paid refresh is not implemented yet. Nothing was called or spent.")
    return 2


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
        "--live", action="store_true", help="refresh the answers of changed prompts (paid; stub)"
    )
    parser.add_argument(
        "--max-usd", type=float, default=None, help="spending cap for --live (required with it)"
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
    results = [harness.run_case(case) for case in cases]
    if args.live:
        return _live(results, args.max_usd)

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
