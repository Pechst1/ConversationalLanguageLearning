"""E-2 follow-up: two first requests on a fresh database must not both seed the
grammar catalogue (UniqueViolation on ix_grammar_concepts_external_id → a 500 on
/atelier/today). Opt-in: needs a throwaway PostgreSQL database."""

from __future__ import annotations

import os
import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.grammar import GrammarConcept
from app.services.grammar_catalog import FrenchCoreGrammarCatalog


@pytest.mark.skipif(not os.environ.get("WP69_PG_URL"), reason="set WP69_PG_URL to a throwaway PostgreSQL database")
def test_two_first_requests_seed_the_catalogue_once() -> None:  # pragma: no cover - opt-in
    engine = create_engine(os.environ["WP69_PG_URL"])
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DELETE FROM grammar_concept_localizations")
        conn.exec_driver_sql("DELETE FROM grammar_concepts")
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
