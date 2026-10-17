"""Prove a fix: its tests fail on the code before it and pass with it.

Run from the root of a checkout (or worktree) at the PR's head:

    python scripts/loop/red_green.py [--base origin/main] [--json]

It splits the files the branch changed since its merge base into tests and the rest,
then runs the changed tests twice:

- **green**: on the branch as it is. Every test must pass.
- **red**: with every non-test change put back to the merge base (added files removed,
  deleted files restored), the tests unchanged. At least one test must fail.

The checkout is restored afterwards. Exit 0 only when green passes and red fails by a
real assertion. A red that fails only at import or collection (the test imports a name
the fix adds) is reported as `weak`: it proves the name is new, not that the bug is gone,
so the verifier must read the test. Walk assertions (web-frontend/e2e) need the whole
stack and are listed but not run.

Night shift 17 Oct: a PR that "fixed" #197 only loosened the walk driver and had no test
that failed before it. The fixer had been told to reproduce first; this makes it a check
a verifier runs instead of a sentence in a prompt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

PY_TEST = re.compile(r"(^|/)tests?/(.*/)?test_[^/]+\.py$")
NODE_TEST = re.compile(r"^web-frontend/.+\.test\.(js|mjs)$")
WALK = re.compile(r"^web-frontend/e2e/")
NOT_CODE = re.compile(r"\.(md|png|jpe?g|svg|txt)$")
# A failure for one of these reasons only shows that a name the fix adds is missing on main.
MISSING_NAME = re.compile(r"^(ImportError|ModuleNotFoundError|NameError|AttributeError: module)\b")
PYTEST_FAILED_LINE = re.compile(r"^FAILED \S+(?: - (.*))?$", re.MULTILINE)


@dataclass
class Run:
    command: str
    code: int
    tail: str
    # Whether at least one test failed on an assertion about behaviour, read from the full output.
    asserted: bool = False


@dataclass
class Verdict:
    base: str
    tests: list[str] = field(default_factory=list)
    walk_only: list[str] = field(default_factory=list)
    reverted: list[str] = field(default_factory=list)
    green: list[Run] = field(default_factory=list)
    red: list[Run] = field(default_factory=list)
    result: str = ""  # proven | weak | no-test | green-fails | red-passes
    reason: str = ""


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def changed_files(base: str) -> list[tuple[str, str]]:
    """(status, path) for every file the branch changed since its merge base with `base`."""
    out = git("diff", "--name-status", "--no-renames", f"{base}...HEAD")
    return [(line.split("\t", 1)[0][0], line.split("\t", 1)[1]) for line in out.splitlines() if line]


def run_tests(tests: list[str]) -> list[Run]:
    runs: list[Run] = []
    py = [t for t in tests if t.endswith(".py")]
    node = [t for t in tests if NODE_TEST.search(t)]
    if py:
        argv = [sys.executable, "-m", "pytest", "-q", "-rf", "-p", "no:randomly", "-p", "no:cacheprovider", *py]
        runs.append(_run(argv, cwd="."))
    if node:
        if not Path("web-frontend/node_modules").is_dir():
            raise SystemExit("web-frontend/node_modules is missing: run scripts/loop/setup_env.sh in this checkout first")
        argv = ["node", "--test", *[t.removeprefix("web-frontend/") for t in node]]
        runs.append(_run(argv, cwd="web-frontend"))
    return runs


def _run(argv: list[str], cwd: str) -> Run:
    # A fresh bytecode cache per run: a reverted file of the same size within the same second
    # would otherwise be imported from the fixed version's .pyc, and red would pass.
    with tempfile.TemporaryDirectory() as pycache:
        env = {**os.environ, "PYTHONPYCACHEPREFIX": pycache}
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd, env=env, check=False)  # noqa: S603 - fixed argv, no shell
    output = (proc.stdout + proc.stderr).strip()
    tail = "\n".join(output.splitlines()[-25:])
    return Run(" ".join(argv), proc.returncode, tail, asserted=proc.returncode != 0 and asserted(argv, output))


def asserted(argv: list[str], output: str) -> bool:
    """A real red: some test ran and failed on what it asserts, not on a missing import or name.

    A name the fix adds, imported inside a test, fails that test with ImportError, and pytest still
    counts it as `1 failed`; a node test reading a missing export fails with a TypeError. Neither
    proves the bug is caught (Codex review on #207)."""
    if argv[1:3] == ["-m", "pytest"]:
        return any(reason and not MISSING_NAME.match(reason) for reason in PYTEST_FAILED_LINE.findall(output))
    return "ERR_ASSERTION" in output


def revert_to_base(merge_base: str, sources: list[tuple[str, str]]) -> None:
    for status, path in sources:
        if status == "A":
            Path(path).unlink(missing_ok=True)
        else:
            git("checkout", merge_base, "--", path)


def restore_head(sources: list[tuple[str, str]]) -> None:
    for status, path in sources:
        if status == "D":
            Path(path).unlink(missing_ok=True)
        else:
            git("checkout", "HEAD", "--", path)


def prove(base: str) -> Verdict:
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise SystemExit("commit or stash your changes first: red_green restores files from git")
    merge_base = git("merge-base", base, "HEAD").strip()
    verdict = Verdict(base=f"{base} ({merge_base[:8]})")
    files = changed_files(base)
    tests = [p for s, p in files if s != "D" and (PY_TEST.search(p) or NODE_TEST.search(p))]
    verdict.walk_only = [p for s, p in files if s != "D" and WALK.search(p) and not NODE_TEST.search(p)]
    sources = [(s, p) for s, p in files
               if p not in tests and not NOT_CODE.search(p) and not WALK.search(p)]
    verdict.tests, verdict.reverted = tests, [p for _, p in sources]
    if not tests:
        verdict.result = "no-test"
        verdict.reason = "the branch changes no pytest or node test file" + (
            " (walk assertions only: they need the full stack, see web-frontend/e2e)" if verdict.walk_only else "")
        return verdict

    verdict.green = run_tests(tests)
    if any(r.code != 0 for r in verdict.green):
        verdict.result, verdict.reason = "green-fails", "the changed tests fail on the branch itself"
        return verdict
    if not sources:
        verdict.result, verdict.reason = "red-passes", "only tests changed: nothing to revert, so nothing is proven"
        return verdict
    try:
        revert_to_base(merge_base, sources)
        verdict.red = run_tests(tests)
    finally:
        restore_head(sources)

    failing = [r for r in verdict.red if r.code != 0]
    if not failing:
        verdict.result = "red-passes"
        verdict.reason = "the tests also pass without the fix: they do not test the bug"
    elif any(r.asserted for r in failing):
        verdict.result, verdict.reason = "proven", "fails without the fix, passes with it"
    else:
        verdict.result = "weak"
        verdict.reason = ("fails without the fix only at import/collection (a new name is missing); "
                          "read the test to see whether it would catch the bug itself")
    return verdict


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    verdict = prove(args.base)
    if args.json:
        print(json.dumps(asdict(verdict), indent=1, ensure_ascii=False))
    else:
        print(f"red/green vs {verdict.base}: {verdict.result.upper()} - {verdict.reason}")
        print("tests: " + (", ".join(verdict.tests) or "none"))
        if verdict.walk_only:
            print("walk assertions (not run here): " + ", ".join(verdict.walk_only))
        for label, runs in (("green (with the fix)", verdict.green), ("red (without the fix)", verdict.red)):
            for run in runs:
                print(f"\n--- {label}: exit {run.code}: {run.command}\n{run.tail}")
    return 0 if verdict.result == "proven" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
