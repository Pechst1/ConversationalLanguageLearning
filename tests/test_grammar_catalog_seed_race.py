"""E-2 follow-up: two first requests on a fresh database must not both seed the
grammar catalogue (UniqueViolation on ix_grammar_concepts_external_id → a 500 on
/atelier/today). Opt-in: needs a throwaway PostgreSQL database."""

from __future__ import annotations

import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.grammar import GrammarConcept
from app.services.grammar_catalog import FrenchCoreGrammarCatalog


@pytest.mark.skipif(not os.environ.get("WP69_PG_URL"), reason="set WP69_PG_URL to a throwaway PostgreSQL database")
def test_two_first_requests_seed_the_catalogue_once() -> None:  # pragma: no cover - opt-in
    # Its own schema: the shared CI database already holds rows that reference
    # grammar_concepts, and the race only exists on an empty catalogue.
    schema = f"seed_race_{uuid.uuid4().hex[:8]}"
    admin = create_engine(os.environ["WP69_PG_URL"])
    with admin.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
    engine = create_engine(os.environ["WP69_PG_URL"], connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    try:
        errors: list[BaseException] = []
        start = threading.Barrier(2)

        def seed() -> None:
            try:
                with Session(engine) as db:
                    start.wait()
                    FrenchCoreGrammarCatalog(db).ensure_catalog()
                    db.commit()
            except BaseException as exc:  # noqa: BLE001 - collected for the assertion
                errors.append(exc)

        threads = [threading.Thread(target=seed) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []
        with Session(engine) as db:
            rows = FrenchCoreGrammarCatalog(db).rows()
            stored = db.scalar(select(func.count()).select_from(GrammarConcept).where(GrammarConcept.active.is_(True)))
        assert stored == len(rows)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")


@pytest.mark.skipif(not os.environ.get("WP69_PG_URL"), reason="set WP69_PG_URL to a throwaway PostgreSQL database")
def test_a_complete_catalogue_never_waits_for_the_seed_lock() -> None:  # pragma: no cover - opt-in
    """The 7-day walk of 2026-10-08 lost day 3: every call took the advisory lock, so the
    five lives' day generations queued behind each other. Once the catalogue is complete,
    ensure_catalog must not touch the lock, even while another transaction holds it."""
    from sqlalchemy import text

    from app.services.grammar_catalog import CATALOG_SEED_LOCK_KEY

    schema = f"seed_lock_{uuid.uuid4().hex[:8]}"
    admin = create_engine(os.environ["WP69_PG_URL"])
    with admin.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
    engine = create_engine(os.environ["WP69_PG_URL"], connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            FrenchCoreGrammarCatalog(db).ensure_catalog()
            db.commit()
        with Session(engine) as holder, Session(engine) as db:
            holder.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CATALOG_SEED_LOCK_KEY})
            db.execute(text("SET LOCAL statement_timeout = 2000"))
            concepts = FrenchCoreGrammarCatalog(db).ensure_catalog()  # raises QueryCanceled if it waits
            assert len(concepts) == len(FrenchCoreGrammarCatalog(db).rows())
            holder.rollback()
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
