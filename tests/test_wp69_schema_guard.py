"""WP-69 — the API refuses a schema it cannot serve.

The dev database was one migration behind on 2026-09-22 and the API booted
anyway; the first learner request to reach the missing column was the one that
failed. These tests pin the guard: production refuses to start behind the head,
other environments shout, ``/ready`` answers 503, and the SQLite test databases
(no ``alembic_version``: their schema comes from ``create_all``) are skipped.

Every database here is a private SQLite engine, never the suite's shared one:
an ``alembic_version`` table left in the shared engine would turn every other
test's ``/ready`` red.
"""
from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.db import schema_guard
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def _engine(revision: str | None) -> object:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    if revision is not None:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
            if revision:
                conn.execute(text("INSERT INTO alembic_version VALUES (:rev)"), {"rev": revision})
    return engine


def _previous_revision(head: str) -> str:
    return schema_guard._script_directory().get_revision(head).down_revision


def test_the_heads_are_the_migration_files_this_image_ships() -> None:
    heads = schema_guard.script_heads()
    assert len(heads) == 1, f"more than one alembic head: {heads}"
    assert any(path.name.startswith(heads[0]) for path in (ROOT / "alembic" / "versions").glob("*.py"))


def test_a_current_database_is_current() -> None:
    head = schema_guard.script_heads()[0]
    with _engine(head).connect() as conn:
        status = schema_guard.check_schema(conn)
    assert status.state == schema_guard.CURRENT
    assert not status.is_behind


def test_a_database_one_migration_behind_is_behind() -> None:
    head = schema_guard.script_heads()[0]
    with _engine(_previous_revision(head)).connect() as conn:
        status = schema_guard.check_schema(conn)
    assert status.state == schema_guard.BEHIND
    assert status.is_behind
    assert head in status.message()


def test_an_unknown_revision_is_reported_but_never_blocks_a_rollback() -> None:
    with _engine("ffffffffffff").connect() as conn:
        status = schema_guard.check_schema(conn)
    assert status.state == schema_guard.AHEAD_OR_UNKNOWN
    assert not status.is_behind
    schema_guard.enforce_at_startup(status, app_env="production")  # does not raise


def test_an_empty_version_table_is_unversioned() -> None:
    with _engine("").connect() as conn:
        status = schema_guard.check_schema(conn)
    assert status.state == schema_guard.UNVERSIONED
    assert status.is_behind


def test_sqlite_without_a_version_table_is_skipped() -> None:
    """The suite's own databases come from create_all and carry no revision."""

    with _engine(None).connect() as conn:
        status = schema_guard.check_schema(conn)
    assert status.state == schema_guard.UNCHECKED
    schema_guard.enforce_at_startup(status, app_env="production")  # does not raise


def test_production_refuses_to_start_behind_the_head() -> None:
    head = schema_guard.script_heads()[0]
    with _engine(_previous_revision(head)).connect() as conn:
        status = schema_guard.check_schema(conn)
    with pytest.raises(RuntimeError, match="Refusing to start"):
        schema_guard.enforce_at_startup(status, app_env="production")


def test_other_environments_only_log(caplog: pytest.LogCaptureFixture) -> None:
    head = schema_guard.script_heads()[0]
    with _engine(_previous_revision(head)).connect() as conn:
        status = schema_guard.check_schema(conn)
    with caplog.at_level("ERROR", logger="app.db.schema_guard"):
        schema_guard.enforce_at_startup(status, app_env="development")
    assert any("SCHEMA BEHIND" in record.getMessage() for record in caplog.records)


def _app_on(engine: object) -> object:
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override
    return app


def test_the_startup_guard_uses_the_apps_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    head = schema_guard.script_heads()[0]
    app = _app_on(_engine(_previous_revision(head)))
    with pytest.raises(RuntimeError, match="Refusing to start"):
        asyncio.run(schema_guard.run_startup_guard(app, app_env="production"))
    status = asyncio.run(schema_guard.run_startup_guard(app, app_env="development"))
    assert status.state == schema_guard.BEHIND


def test_ready_answers_503_while_the_database_is_behind() -> None:
    head = schema_guard.script_heads()[0]
    app = _app_on(_engine(_previous_revision(head)))
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database schema behind"}


def test_ready_is_ready_on_the_head() -> None:
    head = schema_guard.script_heads()[0]
    app = _app_on(_engine(head))
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_the_deploy_migrates_before_it_serves() -> None:
    """``docker/entrypoint.sh`` fails the deploy if the migration fails."""

    script = (ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    migrate = script.index("alembic upgrade head")
    serve = script.index("exec uvicorn")
    assert migrate < serve
    assert 'RUN_MIGRATIONS:-1}" = "1"' in script
