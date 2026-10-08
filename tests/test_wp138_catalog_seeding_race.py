"""WP-138 — the grammar catalogue survives a concurrent first seeding.

The 2026-10-07 browser walk: five learners opened «Aujourd'hui» at once on a
fresh database, every ``GET /atelier/today`` upserted the catalogue, and all but
one died on ``ix_grammar_concepts_external_id`` (500 → «Offline» on day 1). The
loser now rolls back and runs again over the winner's rows.
"""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.atelier_assets import AtelierAssetService
from app.services.grammar_catalog import FrenchCoreGrammarCatalog


def _lose_the_race_once(monkeypatch, cls, name: str) -> list[int]:
    real = getattr(cls, name)
    calls: list[int] = []

    def flaky(self, *args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise IntegrityError("INSERT", {}, Exception("duplicate key value violates unique constraint"))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(cls, name, flaky)
    return calls


def test_a_lost_catalogue_race_is_retried_over_the_winners_rows(db_session: Session, monkeypatch) -> None:
    calls = _lose_the_race_once(monkeypatch, FrenchCoreGrammarCatalog, "_ensure_catalog")
    concepts = FrenchCoreGrammarCatalog(db_session).ensure_catalog(archive_legacy=True)
    assert len(calls) == 2
    assert concepts and all(concept.id for concept in concepts)


def test_a_lost_blueprint_race_is_retried(db_session: Session, monkeypatch) -> None:
    FrenchCoreGrammarCatalog(db_session).ensure_catalog(archive_legacy=True)
    calls = _lose_the_race_once(monkeypatch, AtelierAssetService, "_ensure_assets_for_catalog")
    AtelierAssetService(db_session).ensure_assets_for_catalog("fr")
    assert len(calls) == 2


def test_eight_concurrent_first_requests_seed_one_catalogue_on_real_postgres() -> None:
    """The race itself, on PostgreSQL: a throwaway database next to ``WP138_PG_URL``,
    migrated, then eight sessions seed the catalogue at the same instant."""

    import os
    import subprocess
    import sys
    import threading
    import uuid
    from pathlib import Path

    import pytest
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import sessionmaker

    base = os.environ.get("WP138_PG_URL", "").strip()
    if not base:
        pytest.skip("set WP138_PG_URL to a PostgreSQL server this test may create a database on")
    name = f"wp138_race_{uuid.uuid4().hex[:8]}"
    admin = create_engine(make_url(base).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    engine = create_engine(url, pool_size=10)
    try:
        root = Path(__file__).resolve().parent.parent
        subprocess.run(  # noqa: S603 - this interpreter running alembic on its own throwaway database
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=root, env={**os.environ, "DATABASE_URL": url}, check=True, capture_output=True,
        )
        from app.services.atelier import AtelierScheduler

        Session = sessionmaker(bind=engine)
        errors: list[str] = []
        barrier = threading.Barrier(8)

        def first_request() -> None:
            db = Session()
            try:
                barrier.wait()
                AtelierScheduler(db).ensure_catalog()
            except Exception as exc:  # noqa: BLE001 - collected and asserted below
                errors.append(repr(exc)[:300])
            finally:
                db.close()

        threads = [threading.Thread(target=first_request) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
