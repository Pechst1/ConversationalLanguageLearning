"""Restore a real dump and prove broken restores fail without leaving a database."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy.engine import make_url

from scripts.verify_restored_database import expected_heads

PG_URL = os.environ.get("PRODUCTION_READINESS_PG_URL")
ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not PG_URL, reason="set PRODUCTION_READINESS_PG_URL to a disposable migrated CI database")


@pytest.fixture()
def restore_env():
    url = make_url(PG_URL)
    if not (url.database or "").startswith(("atelier_ci_", "atelier_readiness_")):
        pytest.fail("restore checks require a disposable CI database name")
    return {
        **os.environ,
        "PGHOST": url.host or "localhost",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "postgres",
        "PGPASSWORD": url.password or "",
        "RESTORE_PYTHON": sys.executable,
    }, url


def _drill_databases(env):
    with psycopg2.connect(host=env["PGHOST"], port=env["PGPORT"], user=env["PGUSER"], password=env["PGPASSWORD"], dbname="postgres") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT datname FROM pg_database WHERE datname LIKE 'wp73_drill_%'")
            return set(cursor.fetchall())


def _restore(dump, env):
    before = _drill_databases(env)
    result = subprocess.run(  # noqa: S603 - trusted local fixture and repository script
        ["/bin/bash", str(ROOT / "scripts/restore_drill.sh"), str(dump)],
        env=env, capture_output=True, text=True, check=False,
    )
    assert _drill_databases(env) == before, "restore drill leaked its disposable database"
    return result


def test_current_schema_dump_restores_and_is_verified(restore_env, tmp_path):
    env, url = restore_env
    dump = tmp_path / "recovery.dump"
    subprocess.run(  # noqa: S603 - trusted disposable database and generated fixture path
        [shutil.which("pg_dump"), "-Fc", "--file", str(dump), "--dbname", url.database], env=env, check=True,
    )
    result = _restore(dump, env)
    assert result.returncode == 0, result.stderr
    assert "Restore verified:" in result.stdout
    assert "users:" in result.stdout and "dropped wp73_drill_" in result.stdout


@pytest.mark.parametrize("broken", ["outdated-head", "missing-columns", "invalid-dump"])
def test_broken_restores_fail_and_are_cleaned_up(restore_env, tmp_path, broken):
    env, _ = restore_env
    dump = tmp_path / "broken.sql"
    if broken == "invalid-dump":
        dump.write_text("THIS IS NOT VALID SQL;")
    else:
        head = "outdated" if broken == "outdated-head" else sorted(expected_heads())[0]
        dump.write_text(f"CREATE TABLE alembic_version(version_num text); INSERT INTO alembic_version VALUES ('{head}'); CREATE TABLE users(id uuid);")  # noqa: S608 - trusted migration identifier in a generated fixture
    result = _restore(dump, env)
    assert result.returncode != 0
    if broken == "outdated-head":
        assert "schema mismatch" in result.stderr
    elif broken == "missing-columns":
        assert "missing" in result.stderr
