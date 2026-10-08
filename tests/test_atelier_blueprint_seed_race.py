"""WP-153: five first requests to /atelier/today on a fresh database each seeded the
Atelier concept blueprints, and the second insert hit uq_atelier_concept_blueprint_version
(concept_id, language, asset_version) → a 500 (four times on day 1 of the 8 October walk).
Opt-in: needs a throwaway PostgreSQL database."""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.atelier import AtelierConceptBlueprint, AtelierLanguagePack
from app.db.models.grammar import GrammarConcept
from app.services.atelier_assets import BLUEPRINT_SEED_LOCK_KEY, AtelierAssetService
from app.services.grammar_catalog import FrenchCoreGrammarCatalog

pytestmark = pytest.mark.skipif(
    not os.environ.get("WP69_PG_URL"), reason="set WP69_PG_URL to a throwaway PostgreSQL database"
)


@pytest.fixture()
def engine() -> Iterator[Engine]:  # pragma: no cover - opt-in
    # Its own schema: the shared CI database already holds blueprints, and the race
    # only exists while they are missing.
    schema = f"bp_race_{uuid.uuid4().hex[:8]}"
    admin = create_engine(os.environ["WP69_PG_URL"])
    with admin.begin() as conn:
        conn.exec_driver_sql(f"CREATE SCHEMA {schema}")
    engine = create_engine(os.environ["WP69_PG_URL"], connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        FrenchCoreGrammarCatalog(db).ensure_catalog()
        db.commit()
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        admin.dispose()


def _active_concepts(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(GrammarConcept)
        .where(GrammarConcept.language == "fr", GrammarConcept.active.is_(True), GrammarConcept.external_id.isnot(None))
    )


def test_concurrent_first_requests_seed_each_blueprint_once(engine: Engine) -> None:  # pragma: no cover - opt-in
    errors: list[BaseException] = []
    start = threading.Barrier(5)

    def seed() -> None:
        try:
            with Session(engine) as db:
                start.wait()
                AtelierAssetService(db).ensure_assets_for_catalog("fr")
                db.commit()
        except BaseException as exc:  # noqa: BLE001 - collected for the assertion
            errors.append(exc)

    threads = [threading.Thread(target=seed) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(AtelierLanguagePack)) == 1
        assert db.scalar(select(func.count()).select_from(AtelierConceptBlueprint)) == _active_concepts(db)


def test_seeded_blueprints_never_wait_for_the_seed_lock(engine: Engine) -> None:  # pragma: no cover - opt-in
    """Same rule as the catalogue (3575306): once every blueprint exists, a request must
    not touch the lock, even while another transaction holds it."""
    with Session(engine) as db:
        AtelierAssetService(db).ensure_assets_for_catalog("fr")
        db.commit()
    with Session(engine) as holder, Session(engine) as db:
        holder.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": BLUEPRINT_SEED_LOCK_KEY})
        db.execute(text("SET statement_timeout = 2000"))
        AtelierAssetService(db).ensure_assets_for_catalog("fr")  # raises QueryCanceled if it waits
        concept = db.scalars(select(GrammarConcept).where(GrammarConcept.active.is_(True)).limit(1)).one()
        assert AtelierAssetService(db).approved_blueprint_payload(concept)["blueprint_status"] == "approved"
        holder.rollback()
