"""Tests for the WP-18 rollout tooling.

Two scripts are covered: ``scripts/rollout_health.py`` (the runbook's health and
cost queries) and ``scripts/verify_journey_drain.py`` (the drain driver). The
safety guards are the point — both refuse the owner's live database, and the
drain driver refuses the two ports that belong to other processes.

Set ``WP18_HEALTH_DATABASE_URL`` to a throwaway PostgreSQL URL to additionally
execute every health query against real SQL; without it those checks skip
instead of pretending the SQL was validated.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Registered before execution: a @dataclass resolves its own module by name.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


health = _load("rollout_health")
drain = _load("verify_journey_drain")


# ---------------------------------------------------------------------------
# rollout_health: the database guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/language_learning",
        "postgresql://127.0.0.1:5432/language_learning",
        "postgresql:///language_learning",
        "postgresql://user:pw@localhost/language_learning",
    ],
)
def test_the_owners_local_database_is_always_refused(url):
    with pytest.raises(SystemExit) as excinfo:
        health.guard_database_url(url)
    assert "language_learning" in str(excinfo.value)
    # Even the explicit production opt-in cannot unlock a local one.
    with pytest.raises(SystemExit):
        health.guard_database_url(url, allow_production_name=True)


def test_the_remote_pilot_database_needs_an_explicit_opt_in():
    url = "postgresql://user:pw@dpg-abc.frankfurt-postgres.render.com/language_learning"
    with pytest.raises(SystemExit) as excinfo:
        health.guard_database_url(url)
    assert "--allow-production-name" in str(excinfo.value)
    assert health.guard_database_url(url, allow_production_name=True) == url


def test_a_throwaway_database_passes_the_guard():
    url = "postgresql://localhost/atelier_wp18_1788800504"
    assert health.guard_database_url(url) == url


def test_an_empty_database_url_is_refused():
    with pytest.raises(SystemExit):
        health.guard_database_url("")


# ---------------------------------------------------------------------------
# rollout_health: the query set the runbook documents
# ---------------------------------------------------------------------------


def test_every_documented_query_is_present_and_bounded():
    keys = [query.key for query in health.QUERIES]
    assert keys == [
        "journeys",
        "states",
        "conflicts",
        "engine_cost",
        "engine_ledger",
        "correction_cost",
        "weekly_guardrail",
    ]
    assert len(set(keys)) == len(keys)
    for query in health.QUERIES:
        assert ":since" in query.sql, f"{query.key} is unbounded in time"
        assert ":email" in query.sql, f"{query.key} cannot be narrowed to one learner"
        # Read-only by construction: no write verb anywhere in the statement.
        lowered = query.sql.lower()
        for verb in ("insert ", "update ", "delete ", "drop ", "alter ", "truncate "):
            assert verb not in lowered, f"{query.key} contains {verb.strip()}"


def test_the_queries_that_carry_the_money_read_the_guardrail_source():
    # The weekly guardrail reads scene estimated_cost; the runbook says so and
    # the queries must read the same place, or the runbook is fiction.
    assert "estimated_cost" in health.ENGINE_COST.sql
    assert "estimated_cost" in health.WEEKLY_GUARDRAIL.sql
    assert ":guardrail" in health.WEEKLY_GUARDRAIL.sql
    assert "atelier_correction" in health.CORRECTION_COST.sql
    assert "journey_story_generation_failed" in health.ENGINE_LEDGER.sql
    assert "journey_resume_conflict" in health.JOURNEY_CONFLICTS.sql


def test_render_table_prints_a_header_a_rule_and_every_row():
    output = health.render_table("## Title", ["day", "created"], [(date(2026, 9, 7), 3), (None, 0)])
    lines = output.splitlines()
    assert lines[0] == "## Title"
    assert lines[1].startswith("day")
    assert set(lines[2]) <= {"-", "+", " "}
    assert lines[3].startswith("2026-09-07")
    # A NULL prints as an empty cell, never as the string "None".
    assert lines[4].endswith("| 0") and "None" not in lines[4]


def test_render_table_says_no_rows_rather_than_printing_an_empty_table():
    assert health.render_table("## Title", ["a"], []) == "## Title\n  (no rows)"


@pytest.mark.skipif(
    not os.environ.get("WP18_HEALTH_DATABASE_URL"),
    reason="set WP18_HEALTH_DATABASE_URL to a throwaway PostgreSQL database",
)
def test_every_query_executes_against_a_real_database():
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["WP18_HEALTH_DATABASE_URL"])
    try:
        for query in health.QUERIES:
            columns, rows = health.run_query(
                engine,
                query,
                {"since": date(2020, 1, 1), "email": None, "guardrail": 2.0},
            )
            assert columns, f"{query.key} returned no columns"
            for row in rows:
                assert len(row) == len(columns)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# verify_journey_drain
# ---------------------------------------------------------------------------


def test_the_drain_driver_refuses_the_owners_database():
    with pytest.raises(SystemExit) as excinfo:
        drain.Db("postgresql://localhost/language_learning")
    assert "language_learning" in str(excinfo.value)


@pytest.mark.parametrize("port", [8000, 8010])
def test_the_drain_driver_refuses_reserved_ports(port):
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(SCRIPTS / "verify_journey_drain.py"),
            "--database-url",
            "postgresql://localhost/atelier_wp18_test",
            "--port",
            str(port),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "Refusing port" in (result.stdout + result.stderr)


def test_the_drain_driver_refuses_the_owners_database_from_the_command_line():
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [
            sys.executable,
            str(SCRIPTS / "verify_journey_drain.py"),
            "--database-url",
            "postgresql://localhost/language_learning",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "language_learning" in (result.stdout + result.stderr)


def test_free_port_never_returns_a_reserved_port():
    port = drain.free_port("127.0.0.1")
    assert 8021 <= port <= 8059
    assert port not in (8000, 8010)


def test_the_report_table_marks_failures_and_the_exit_code_follows_them():
    report = drain.Report()
    report.record("1 · flag on", "create journey", True, "201")
    report.record("2 · drained", "create refused", False, "200")
    table = report.table()
    assert "PASS" in table and "FAIL" in table
    assert len(report.failed) == 1
    assert report.failed[0][1] == "create refused"


def test_detail_of_reads_the_structured_journey_error_body():
    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            if self._payload is None:
                raise ValueError("no json")
            return self._payload

    body = {"detail": {"code": "journey_disabled", "message": "The daily journey is not enabled."}}
    assert drain.detail_of(Response(body))["code"] == "journey_disabled"
    assert drain.detail_of(Response({"detail": "plain string"})) == {}
    assert drain.detail_of(Response(None)) == {}
