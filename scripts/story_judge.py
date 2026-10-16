#!/usr/bin/env python
"""Score story pages the way a reader reads them (story-quality plan, Phase 1, «Maßstab»: the judge).

    venv/bin/python scripts/story_judge.py rubric RUN/B1.1.md [RUN/A1.1.md …]
    venv/bin/python scripts/story_judge.py pairwise OLD/B1.1.md NEW/B1.1.md [OLD NEW …]
    venv/bin/python scripts/story_judge.py benchmark [--level B1] [--day a]

Each page (or pair) is one paid call to the judge model: ``OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL``
(gpt-5.5 in production) unless ``--model`` names another. ``--cap-usd`` is checked before every
call; the run stops before a call that could pass it and lists what it skipped. ``--dry-run``
prints what the judge would read and what each call could cost, with no client and no call.
Writes ``--out`` (JSON) and a Markdown summary beside it, and prints the summary. The logic is
``app/services/season/story_judge.py``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.services.season import story_judge as sj  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--model", help="judge model (default: OPENAI_GRAPHIC_NOVEL_PREMIUM_SCRIPT_MODEL)"
    )
    common.add_argument(
        "--cap-usd",
        type=float,
        default=sj.DEFAULT_CAP_USD,
        help="hard spend cap (default %(default)s)",
    )
    common.add_argument(
        "--reasoning-effort",
        default=sj.DEFAULT_REASONING_EFFORT,
        choices=("minimal", "low", "medium", "high"),
        help="sent to gpt-5 models only (default %(default)s)",
    )
    common.add_argument(
        "--max-tokens", type=int, default=sj.DEFAULT_MAX_TOKENS, help="completion ceiling per call"
    )
    common.add_argument("--out", type=Path, help="JSON report; the Markdown summary goes beside it")
    common.add_argument(
        "--dry-run", action="store_true", help="print what the judge would read; no call"
    )

    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    modes = parser.add_subparsers(dest="mode", required=True)
    rubric = modes.add_parser(
        "rubric", parents=[common], help="score every generated page of the transcripts"
    )
    rubric.add_argument("transcripts", nargs="+", type=Path, metavar="TRANSCRIPT")
    rubric.add_argument("--level", help="override the level in the transcripts' header")
    pairwise = modes.add_parser(
        "pairwise", parents=[common], help="old against new, position by position"
    )
    pairwise.add_argument(
        "transcripts", nargs="+", type=Path, metavar="OLD NEW", help="one or more pairs"
    )
    pairwise.add_argument("--level", help="override the level in the transcripts' header")
    pairwise.add_argument(
        "--seed", default=sj.DEFAULT_SEED, help="seeds the A/B order (default %(default)s)"
    )
    benchmark = modes.add_parser(
        "benchmark", parents=[common], help="the authored tentpole pages, rubric minus «new»"
    )
    benchmark.add_argument(
        "--level", default="B1", help="the level the pages are read at (default %(default)s)"
    )
    benchmark.add_argument(
        "--day", default="a", choices=("a", "b"), help="which tentpole day (default %(default)s)"
    )
    benchmark.add_argument("--season", default="s1")
    return parser


def _planned_calls(args: argparse.Namespace, loaded: Any) -> list[tuple[str, str, str]]:
    """``(label, system, user)`` for every call the run would make, in order."""

    calls: list[tuple[str, str, str]] = []
    if args.mode == "pairwise":
        for old_pages, new_pages in loaded:
            for key, old, new, new_first in sj.pairwise_plan(old_pages, new_pages, seed=args.seed)[
                0
            ]:
                first, second = (new, old) if new_first else (old, new)
                system, user = sj.pairwise_messages(first, second, key=key, level=new.level)
                shown = "A" if new_first else "B"
                calls.append((f"{old.label} ↔ {new.label} (new shown as {shown})", system, user))
        return calls
    for page in loaded:
        questions = sj.questions_for(page, include_new=args.mode == "rubric")
        calls.append((page.label, *sj.rubric_messages(page, questions)))
    return calls


def _dry_run(calls: list[tuple[str, str, str]], *, model: str, max_tokens: int, cap: float) -> None:
    shown = None
    for label, system, user in calls:
        if system != shown:
            print(f"## System prompt\n\n{system}\n")
            shown = system
        ceiling = sj.call_ceiling_usd(model, system, user, max_tokens)
        print(f"## {label} (this call costs at most US${ceiling:.4f})\n\n{user}\n")
    print(f"{len(calls)} calls planned to {model}, cap US${cap:.2f}. Dry run: no client, no call.")


def _client() -> Any:
    from app.services.llm_service import LLMService

    return LLMService()


def main(argv: list[str] | None = None, *, client: Any = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.cap_usd <= 0:
        parser.error("--cap-usd must be above 0")
    if args.mode == "pairwise" and len(args.transcripts) % 2:
        parser.error("pairwise takes transcripts in pairs: OLD NEW [OLD NEW …]")
    paths = (
        list(zip(args.transcripts[::2], args.transcripts[1::2], strict=True))
        if args.mode == "pairwise"
        else []
    )
    try:
        if args.mode == "pairwise":
            loaded: Any = [
                (
                    sj.load_transcript(old, level=args.level),
                    sj.load_transcript(new, level=args.level),
                )
                for old, new in paths
            ]
        elif args.mode == "rubric":
            loaded = [
                page
                for path in args.transcripts
                for page in sj.generated_pages(sj.load_transcript(path, level=args.level))
            ]
        else:
            loaded = sj.benchmark_pages(args.level, season_id=args.season, day=args.day)
    except (OSError, ValueError) as exc:
        print(f"story_judge: {exc}", file=sys.stderr)
        return 2
    model = args.model or sj.default_model()
    if args.dry_run:
        _dry_run(
            _planned_calls(args, loaded), model=model, max_tokens=args.max_tokens, cap=args.cap_usd
        )
        return 0

    try:
        judge = sj.Judge(
            client=client if client is not None else _client(),
            model=model,
            cap_usd=args.cap_usd,
            reasoning_effort=args.reasoning_effort,
            max_tokens=args.max_tokens,
        )
    except ValueError as exc:  # LLMService with no provider configured
        print(f"story_judge: no judge model available ({exc})", file=sys.stderr)
        return 2
    if args.mode == "pairwise":
        sources = [(str(old), str(new)) for old, new in paths]
        report = sj.pairwise_report(loaded, judge, seed=args.seed, sources=sources)
    elif args.mode == "rubric":
        report = sj.rubric_report(loaded, judge, sources=[str(path) for path in args.transcripts])
    else:
        sources = sorted({page.source for page in loaded})
        report = sj.rubric_report(
            loaded, judge, mode="benchmark", include_new=False, sources=sources
        )

    out = args.out or Path(f"story_judge_{args.mode}.json")
    json_path, md_path = out.with_suffix(".json"), out.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = sj.markdown(report)
    md_path.write_text(summary, encoding="utf-8")
    print(summary)
    print(f"Wrote {json_path} and {md_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
