"""WP-69 — the API does not serve a schema it was not written for.

On 2026-09-22 the dev database was one migration behind the code (WP-64's
column missing) and the API booted anyway. Nothing failed until a learner's
first scene reached the missing column, 40 seconds into «Envoi…». The lesson
for production is that *a server that boots against a schema it cannot serve
fails later, in front of a learner*. This module moves that failure to the
deploy:

* at startup the database's ``alembic_version`` is compared with the migration
  head(s) shipped in this image. ``APP_ENV=production`` refuses to start while
  the database is **behind** (the deploy fails, the old instance keeps
  serving); every other environment logs it loudly and carries on;
* ``/ready`` answers 503 while the database is behind, so a load balancer never
  routes a learner to an instance that would 500 on the first new column.

A database that is *ahead* of this image (a revision the image does not know —
an old image during a rollback, or mid-deploy after the new image migrated) is
logged but not refused: blocking a rollback would turn a bad deploy into an
outage.

A database with no ``alembic_version`` table at all is refused in production
(never migrated) and skipped on SQLite, which is what the test suite runs on:
its tables come from ``Base.metadata.create_all``, not from migrations.

The deploy itself migrates first: ``docker/entrypoint.sh`` runs
``alembic upgrade head`` under ``set -euo pipefail`` before ``exec uvicorn``
whenever ``RUN_MIGRATIONS=1`` (the API service in ``render.yaml``).
"""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = ROOT / "alembic"
VERSION_TABLE = "alembic_version"

CURRENT = "current"
BEHIND = "behind"
AHEAD_OR_UNKNOWN = "ahead_or_unknown"
UNVERSIONED = "unversioned"
UNCHECKED = "unchecked"


@dataclass(frozen=True)
class SchemaStatus:
    state: str
    database: tuple[str, ...] = ()
    heads: tuple[str, ...] = ()
    detail: str = ""

    @property
    def is_behind(self) -> bool:
        return self.state in (BEHIND, UNVERSIONED)

    def message(self) -> str:
        return (
            f"database schema is {self.state}: database at {list(self.database) or 'no revision'}, "
            f"code expects {list(self.heads)}. {self.detail}".strip()
        )


@lru_cache(maxsize=1)
def _script_directory() -> Any:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return ScriptDirectory.from_config(config)


def script_heads() -> tuple[str, ...]:
    """The migration head(s) this image ships. Read from disk once."""

    return tuple(sorted(_script_directory().get_heads()))


def _known(revision: str) -> bool:
    try:
        return _script_directory().get_revision(revision) is not None
    except Exception:  # alembic raises for a revision it has never heard of
        return False


def check_schema(connection: Any, *, heads: tuple[str, ...] | None = None) -> SchemaStatus:
    """Compare ``connection``'s alembic revision with the heads.

    ``connection`` is a SQLAlchemy ``Connection`` or ``Session``. Never raises:
    a check that cannot run is ``unchecked``, and the caller decides.
    """

    try:
        expected = heads if heads is not None else script_heads()
    except Exception as exc:  # pragma: no cover - a broken image
        logger.exception("schema guard: could not read the migration heads")
        return SchemaStatus(UNCHECKED, detail=f"heads unreadable: {exc}")

    try:
        bind = connection.connection() if isinstance(connection, Session) else connection
        dialect = bind.dialect.name
        has_table = sa_inspect(bind).has_table(VERSION_TABLE)
    except Exception as exc:
        logger.warning("schema guard: could not inspect the database: %s", exc)
        return SchemaStatus(UNCHECKED, heads=expected, detail=str(exc))

    if not has_table:
        if dialect == "sqlite":
            # The test suite's schema comes from create_all, not migrations.
            return SchemaStatus(UNCHECKED, heads=expected, detail="sqlite without alembic_version")
        return SchemaStatus(
            UNVERSIONED,
            heads=expected,
            detail="The alembic_version table is missing: run `alembic upgrade head`.",
        )

    try:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).all()
    except Exception as exc:
        logger.warning("schema guard: could not read alembic_version: %s", exc)
        return SchemaStatus(UNCHECKED, heads=expected, detail=str(exc))

    database = tuple(sorted(str(row[0]) for row in rows if row and row[0]))
    if not database:
        return SchemaStatus(
            UNVERSIONED,
            heads=expected,
            detail="alembic_version is empty: run `alembic upgrade head`.",
        )
    if set(database) == set(expected):
        return SchemaStatus(CURRENT, database=database, heads=expected)
    if all(_known(revision) for revision in database):
        return SchemaStatus(
            BEHIND,
            database=database,
            heads=expected,
            detail="Run `alembic upgrade head` before serving this image.",
        )
    return SchemaStatus(
        AHEAD_OR_UNKNOWN,
        database=database,
        heads=expected,
        detail="The database carries a revision this image does not know (a newer deploy, or a rollback).",
    )


def enforce_at_startup(status: SchemaStatus, *, app_env: str) -> None:
    """Refuse to start production behind the schema; shout everywhere else."""

    production = app_env.strip().lower() == "production"
    if status.is_behind:
        if production:
            raise RuntimeError(
                "Refusing to start: " + status.message()
                + " (WP-69: the API never serves a schema it cannot serve.)"
            )
        logger.error("SCHEMA BEHIND — %s Requests touching new columns will fail.", status.message())
        return
    if status.state == AHEAD_OR_UNKNOWN:
        logger.error("Schema mismatch — %s", status.message())
    elif status.state == UNCHECKED and status.detail and "sqlite" not in status.detail:
        logger.warning("Schema guard could not check the database: %s", status.detail)


async def run_startup_guard(app: Any, *, app_env: str) -> SchemaStatus:
    """Check the schema through the session the app's requests will use.

    The session comes from ``get_db`` — or from its override, so a test app
    wired to SQLite is checked against SQLite and never against whatever
    ``DATABASE_URL`` the machine running the suite happens to have. A database
    that cannot be reached at startup is not refused here: ``/ready`` reports
    it, and the platform keeps the old instance.
    """

    from app.api.deps import get_db

    provider = getattr(app, "dependency_overrides", {}).get(get_db, get_db)
    status = SchemaStatus(UNCHECKED)
    try:
        if inspect.isasyncgenfunction(provider):
            agen = provider()
            db = await agen.__anext__()
            try:
                status = check_schema(db)
            finally:
                await agen.aclose()
        else:
            gen = provider()
            db = next(gen)
            try:
                status = check_schema(db)
            finally:
                gen.close()
    except Exception as exc:
        logger.warning("schema guard: no session at startup: %s", exc)
        status = SchemaStatus(UNCHECKED, detail=str(exc))
    enforce_at_startup(status, app_env=app_env)
    return status


__all__ = [
    "AHEAD_OR_UNKNOWN",
    "BEHIND",
    "CURRENT",
    "SchemaStatus",
    "UNCHECKED",
    "UNVERSIONED",
    "check_schema",
    "enforce_at_startup",
    "run_startup_guard",
    "script_heads",
]
