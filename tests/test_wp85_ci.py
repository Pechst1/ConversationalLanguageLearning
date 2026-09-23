"""WP-85: CI runs every suite, and a new suite cannot be left out of it.

Before WP-85 each node suite had to be added to `package.json` *and* listed in
`ci.yml` by hand; a dozen were in neither list's intersection and never ran in
CI. `npm test` now globs every suite, and these tests pin the glob against the
files on disk.
"""
from __future__ import annotations

import fnmatch
import json
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web-frontend"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _test_globs() -> list[str]:
    script = json.loads((WEB / "package.json").read_text(encoding="utf-8"))["scripts"]["test"]
    argv = shlex.split(script)
    assert argv[:2] == ["node", "--test"], script
    return argv[2:]


def _matches(path: str, pattern: str) -> bool:
    # `node --test` globs: `**/` may match zero directories.
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.replace("**/", ""))


def test_npm_test_covers_every_node_suite_on_disk() -> None:
    globs = _test_globs()
    suites = [
        path.relative_to(WEB).as_posix()
        for folder in ("lib", "components", "scripts")
        for path in (WEB / folder).rglob("*.test.*")
        if path.suffix in {".js", ".mjs"} and "node_modules" not in path.parts
    ]
    assert len(suites) > 30
    missed = [suite for suite in suites if not any(_matches(suite, g) for g in globs)]
    assert missed == [], f"node suites npm test would skip: {missed}"


def test_the_workflow_parses_and_every_job_can_fail_the_run() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert {"backend", "postgres", "frontend", "docker"} <= set(jobs)
    for name, job in jobs.items():
        assert "continue-on-error" not in job, name
        for step in job["steps"]:
            assert not step.get("continue-on-error"), (name, step.get("name"))


def test_ci_runs_the_suites_and_the_type_check() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "npm test" in text
    assert "npx tsc --noEmit -p ." in text
    assert "ruff check ." in text
    # The backend run prints its count: a single -q, and pyproject adds none.
    assert "pytest -q -n auto --dist loadfile" in text
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'addopts = "-ra"' in pyproject


def test_the_postgres_job_runs_the_row_lock_drivers_on_a_throwaway_database() -> None:
    job = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["postgres"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    for command in (
        "alembic downgrade base",
        "scripts/verify_story_engine_pg.py",
        "scripts/verify_journey_drain.py",
        "test_best_effort_on_real_postgres",
        "test_every_query_executes_against_a_real_database",
    ):
        assert command in runs, command
    # The drivers refuse the owner's database name; CI must not use it.
    assert "language_learning" not in job["env"]["DATABASE_URL"]
