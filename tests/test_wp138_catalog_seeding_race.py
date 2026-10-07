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
