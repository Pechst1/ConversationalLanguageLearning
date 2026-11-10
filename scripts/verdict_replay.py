#!/usr/bin/env python3
"""Package V stage 2: replay stored answers through two judges and print every flip.

A judge change (a rule, a reader, the variant gate, a model id) used to have no measured
effect: the 1990 spellings were «corrected» for weeks before a review saw it. This script
runs the same answers through two judges and lists what changed.

Sources of answers:

* ``tests/verdict_corpus/replay_cases.jsonl``: frozen answers, each a surface, the
  learner's text and what the surface stored (the model's answer included, so no call is
  made). Built by ``build-corpus`` from the walk and issue sentences, the negative corpus,
  the valid-variant list and one case per reader branch.
* ``--ledger``: the live records of ``verdict_records`` (each holds the reading it was
  judged from), judged again by today's judge.

Judges: today's code, and a base: ``--base-ref REF`` runs the same cases through the
code at a git revision (``git archive`` into a temporary folder, a subprocess), or
``--base-file`` reads a frozen run (``tests/verdict_corpus/replay_base.jsonl``, written by
``--write-base``).

A flip is printed for every case whose outcome, ``counts`` or edits differ. The run fails
(exit 1) on a **right → wrong** flip (the base said right, today's judge says anything
else) or on **any edit between two accepted spellings** in today's output.

Usage::

    python scripts/verdict_replay.py build-corpus
    python scripts/verdict_replay.py --base-ref origin/main --write-base
    python scripts/verdict_replay.py                        # today vs the frozen base
    python scripts/verdict_replay.py --ledger               # live records vs today's judge
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "verdict_corpus"
CASES = CORPUS / "replay_cases.jsonl"
BASE = CORPUS / "replay_base.jsonl"

# A base run (``_run`` in a subprocess) must import the archived ``app``, not this tree's.
if os.environ.get("VERDICT_REPLAY_BASE") != "1" and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: The reader each surface's case goes through, and the arguments it takes besides ``text``.
SURFACES = ("recall", "scene", "forge", "courrier", "feuilleton", "voice", "rehearsal", "placement", "journal")


# ---------------------------------------------------------------------------
# Running one judge
# ---------------------------------------------------------------------------


def _call(case: dict[str, Any]) -> dict[str, Any]:
    """Today's verdict for one case, through the surface's public reader."""

    from app.services import verdicts
    from app.services.journey_contracts import Correction, TaskOutcome

    surface, args = case["surface"], dict(case.get("args") or {})
    text = case.get("text") or ""
    reader = getattr(verdicts, f"from_{surface}")
    if surface in {"recall", "scene"}:
        args["outcome"] = TaskOutcome(args["outcome"])
        if args.get("correction"):
            args["correction"] = Correction(**args["correction"])
        return reader(text=text, **args).to_dict()
    if surface in {"rehearsal"}:
        return reader(args.get("debrief")).to_dict()
    if surface == "placement":
        return reader(args.get("grading"), failure=args.get("failure")).to_dict()
    if surface == "voice":
        return reader(text=text, **args).to_dict()
    return reader(args.get("correction"), text=text, **{k: v for k, v in args.items() if k != "correction"}).to_dict()


def run_today(cases: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {case["id"]: _call(case) for case in cases}


def run_ref(ref: str, cases_path: Path = CASES) -> dict[str, dict[str, Any]]:
    """The same cases through the code at ``ref``: its ``app/`` and this file, in a subprocess."""

    with tempfile.TemporaryDirectory(prefix="verdict-replay-") as tmp:
        archive = subprocess.run(  # noqa: S603 - a git revision the person running this named
            ["git", "archive", ref, "app"], cwd=ROOT, check=True, capture_output=True  # noqa: S607
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        env = {**os.environ, "PYTHONPATH": tmp, "VERDICT_REPLAY_BASE": "1", "SECRET_KEY": os.environ.get("SECRET_KEY", "verdict-replay")}
        out = subprocess.run(  # noqa: S603 - this script, run by the same interpreter
            [sys.executable, str(Path(__file__).resolve()), "_run", "--cases", str(cases_path)],
            cwd=tmp, env=env, check=True, capture_output=True, text=True,
        ).stdout
    return json.loads(out)


# ---------------------------------------------------------------------------
# Comparing two judges
# ---------------------------------------------------------------------------


def _edits(verdict: dict[str, Any]) -> list[tuple[str, str]]:
    return [(edit["span"], edit["replacement"]) for edit in verdict.get("edits") or []]


def compare(base: dict[str, dict[str, Any]], today: dict[str, dict[str, Any]], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from app.services.spelling_variants import is_variant_edit

    flips, right_to_wrong, variant_edits = [], [], []
    for case_id, now in today.items():
        before = base.get(case_id)
        if before is not None and (
            before["outcome"] != now["outcome"] or before["counts"] != now["counts"] or _edits(before) != _edits(now)
        ):
            flip = {
                "id": case_id,
                "surface": cases.get(case_id, {}).get("surface"),
                "outcome": [before["outcome"], now["outcome"]],
                "counts": [before["counts"], now["counts"]],
                "edits": [_edits(before), _edits(now)],
            }
            flips.append(flip)
            if before["outcome"] == "right" and now["outcome"] != "right":
                right_to_wrong.append(flip)
        for span, replacement in _edits(now):
            if is_variant_edit(span, replacement):
                variant_edits.append({"id": case_id, "edit": [span, replacement]})
    return {
        "cases": len(today),
        "compared": sum(1 for case_id in today if case_id in base),
        "flips": flips,
        "right_to_wrong": right_to_wrong,
        "variant_edits": variant_edits,
    }


def _print(result: dict[str, Any], label: str) -> None:
    print(f"{label}: {result['cases']} cases, {result['compared']} compared, {len(result['flips'])} flips")
    for flip in result["flips"]:
        print(f"  {flip['id']} ({flip['surface']}): outcome {flip['outcome'][0]} -> {flip['outcome'][1]}, "
              f"counts {flip['counts'][0]} -> {flip['counts'][1]}, edits {flip['edits'][0]} -> {flip['edits'][1]}")
    print(f"right -> wrong: {len(result['right_to_wrong'])}; edits of a valid variant: {len(result['variant_edits'])}")
    for item in result["variant_edits"]:
        print(f"  variant edit in {item['id']}: {item['edit'][0]} -> {item['edit'][1]}")


def load_cases(path: Path = CASES) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_base(path: Path = BASE) -> dict[str, dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {row["id"]: row["verdict"] for row in rows}


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


def replay_ledger(limit: int | None = None) -> dict[str, Any]:
    """Every live record judged again by today's judge, against what it stored."""

    from sqlalchemy import select

    from app.db.models.verdict_record import VerdictRecord
    from app.db.session import SessionLocal
    from app.services.judge import Reading, Task, judge

    db = SessionLocal()
    try:
        query = select(VerdictRecord).where(VerdictRecord.superseded_by_id.is_(None)).order_by(VerdictRecord.created_at)
        if limit:
            query = query.limit(limit)
        base, today, cases = {}, {}, {}
        for record in db.scalars(query):
            reading = Reading.from_dict((record.verdict or {}).get("reading") or {})
            key = f"{record.subject_type}:{record.subject_id}"
            base[key] = (record.verdict or {}).get("shown") or {}
            today[key] = judge(Task(record.surface), record.answer_text, reading=reading).to_dict()
            cases[key] = {"surface": record.surface}
        return compare(base, today, cases)
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# Building the corpus
# ---------------------------------------------------------------------------


def _walk_sentences() -> list[str]:
    source = (ROOT / "tests" / "test_correction_walk_rules.py").read_text(encoding="utf-8")
    seen: dict[str, None] = {}
    for match in re.finditer(r'pytest\.param\(\s*"((?:[^"\\]|\\.)+)"', source):
        seen.setdefault(match.group(1), None)
    return list(seen)


def _negative_sentences() -> list[str]:
    from tests.test_correction_negative_corpus import CORPUS as NEGATIVE

    return [sentence for sentences in NEGATIVE.values() for sentence in sentences]


def _variant_pairs() -> list[tuple[str, str, str]]:
    rows = []
    for raw in (CORPUS / "valid_variants.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            first, second, sentence = (part.strip() for part in line.split("|"))
            rows.append((first, second, sentence))
    return rows


def _erratum(span: str, replacement: str, why: str = "") -> dict[str, Any]:
    return {"learner_text": span, "corrected_target": replacement, "why_wrong": why or f"« {replacement} ».", "severity": 1}


def build_corpus() -> list[dict[str, Any]]:
    from app.services import correction_contract as cc

    cases: list[dict[str, Any]] = []

    def add(case_id: str, surface: str, text: str, **args: Any) -> None:
        cases.append({"id": case_id, "surface": surface, "text": text, "args": args})

    # Correct French a model accepted: it must stay right, with no edit.
    for index, sentence in enumerate(_negative_sentences()):
        add(f"negative-{index}", "courrier", sentence,
            correction={"verdict": "accepted", "score_0_4": 4, "errata": [], "correction_debug": {"model": "m"}})
    # The walk and issue sentences: the rule pass's errata, read by a model (partly) and with
    # the model down (rules only, not checked).
    for index, sentence in enumerate(_walk_sentences()):
        errata = [
            _erratum(item["learner_text"], item["corrected_target"], item.get("why_wrong") or "")
            for item in cc.deterministic_errata(sentence)
        ]
        add(f"walk-{index}-read", "courrier", sentence,
            correction={"verdict": "partial" if errata else "accepted", "score_0_4": 3, "errata": errata,
                        "correction_debug": {"model": "m"}})
        add(f"walk-{index}-down", "courrier", sentence,
            correction={"verdict": "unassessed", "errata": errata, "correction_debug": {"fallback_used": True, "failure": "timeout"}})
        add(f"walk-{index}-journal", "journal", sentence,
            correction={"checker": "model", "verdict": "partial" if errata else "accepted", "errata": errata})
    # A model that «corrected» one right spelling into the other, both ways.
    for first, second, sentence in _variant_pairs():
        for wrong, right in ((first, second), (second, first)):
            text = sentence.replace("{}", wrong)
            add(f"variant-{wrong}->{right}", "courrier", text,
                correction={"verdict": "partial", "score_0_4": 3, "errata": [_erratum(wrong, right)],
                            "correction_debug": {"model": "m"}})
    # One case per reader branch.
    line = "Je cherche la colis."
    slip = [_erratum("la colis", "le colis")]
    add("forge-key", "forge", line, correction={"local_status": "right", "verdict": "correct"})
    add("forge-model", "forge", line, correction={"verdict": "partial", "errata": slip, "correction_debug": {"model": "m"}})
    add("forge-provisional", "forge", line, correction={"assessment_status": "provisional", "verdict": "partial"})
    add("forge-unavailable", "forge", line,
        correction={"assessment_status": "unavailable", "verdict": "needs_review", "errata": slip,
                    "ai_review": {"status": "failed", "error": "timeout"}})
    add("forge-old-fallback", "forge", line,
        correction={"verdict": "partial", "corrected_answer": "x", "correction_debug": {"fallback_used": True}})
    add("forge-key-word", "forge", line, correction={"verdict": "correct", "errata": []})
    add("feuilleton-model", "feuilleton", line, correction={"verdict": "partial", "errata": slip, "correction_debug": {"model": "m"}})
    add("feuilleton-branch", "feuilleton", line, correction={"verdict": "accepted"})
    add("feuilleton-down", "feuilleton", line, correction={"verdict": "unassessed", "correction_debug": {"fallback_used": True, "failure": "timeout"}})
    add("courrier-journey", "courrier", line, correction={"journey_outcome": "met"})
    add("courrier-journey-down", "courrier", line, correction={"journey_outcome": "partially_met", "journey_check_failure": "TimeoutError"})
    add("courrier-no-model", "courrier", line, correction={"verdict": "unassessed", "correction_debug": {"fallback_used": True, "failure": "no_model"}})
    add("journal-model", "journal", line, correction={"checker": "model", "errata": slip})
    add("journal-old-checked", "journal", line, correction={"assessment_status": "checked"})
    add("journal-down", "journal", line, correction={"checker": "deterministic", "failure_reason": "timeout", "retryable": True, "errata": slip})
    add("recall-met", "recall", "le colis", outcome="met")
    add("recall-miss", "recall", "la colis", outcome="not_yet",
        correction={"span_fr": "la colis", "corrected_fr": "le colis", "note_native": "masc."})
    add("recall-unscored", "recall", "la colis", outcome="unscored")
    add("scene-authored", "scene", line, outcome="met")
    add("scene-model", "scene", line, outcome="partially_met", failure_reason="reply_source:model")
    add("scene-down", "scene", line, outcome="partially_met", check_failure="TimeoutError: read timed out")
    add("voice-read", "voice", line, errors=[{"span": "la colis", "correction": "le colis", "message": "masc."}], read=True)
    add("voice-clean", "voice", "Je cherche le colis.", errors=[], read=True)
    add("voice-down", "voice", line, errors=[], read=False, failure="timeout")
    add("rehearsal-read", "rehearsal", line,
        debrief={"free_line": line, "correction_available": True, "fixes": slip})
    add("rehearsal-right", "rehearsal", "Je cherche le colis.",
        debrief={"free_line": "Je cherche le colis.", "correction_available": True, "already_correct": True})
    add("rehearsal-down", "rehearsal", line, debrief={"free_line": line, "correction_available": False, "correction_failure": "timeout"})
    add("placement-read", "placement", line, grading={"score_0_4": 3})
    add("placement-down", "placement", line, grading=None, failure="TimeoutError")
    return cases


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", nargs="?", default="replay", choices=["replay", "build-corpus", "_run"])
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--base-ref", help="judge the cases with the code at this git revision")
    parser.add_argument("--base-file", type=Path, default=BASE)
    parser.add_argument("--write-base", action="store_true", help="store the base run in --base-file")
    parser.add_argument("--ledger", action="store_true", help="replay the live verdict records instead")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    os.environ.setdefault("SECRET_KEY", "verdict-replay")

    if args.command == "_run":
        print(json.dumps(run_today(load_cases(args.cases)), ensure_ascii=False))
        return 0
    if args.command == "build-corpus":
        cases = build_corpus()
        _write_jsonl(args.cases, cases)
        print(f"{len(cases)} cases -> {args.cases}")
        return 0
    if args.ledger:
        result = replay_ledger(args.limit)
        label = "ledger"
    else:
        cases = load_cases(args.cases)
        base = run_ref(args.base_ref, args.cases) if args.base_ref else load_base(args.base_file)
        if args.write_base:
            _write_jsonl(args.base_file, ({"id": case_id, "verdict": verdict} for case_id, verdict in sorted(base.items())))
            print(f"{len(base)} base verdicts -> {args.base_file}")
        result = compare(base, run_today(cases), {case["id"]: case for case in cases})
        label = f"corpus vs {args.base_ref or args.base_file.name}"
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print(result, label)
    return 1 if result["right_to_wrong"] or result["variant_edits"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
