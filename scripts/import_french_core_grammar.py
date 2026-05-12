"""Import the curated French core grammar catalog and report asset status.

Usage:
    .venv/bin/python scripts/import_french_core_grammar.py
    .venv/bin/python scripts/import_french_core_grammar.py --backfill-blueprints
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.models.atelier import AtelierConceptBlueprint
from app.db.models.grammar import GrammarConcept, GrammarConceptArchive, GrammarConceptLocalization
from app.db.session import SessionLocal
from app.services.atelier_assets import AtelierAssetService
from app.services.grammar_catalog import FRENCH_CORE_CATALOG_VERSION, FrenchCoreGrammarCatalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Install the focused French grammar notebook catalog")
    parser.add_argument("--backfill-blueprints", action="store_true", help="Generate/validate approved Atelier blueprints")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        concepts = FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=True)
        service = AtelierAssetService(db)
        invalid: list[tuple[str, str, list[str]]] = []
        if args.backfill_blueprints:
            for concept in concepts:
                blueprint = service.ensure_concept_blueprint(concept)
                quality = service.blueprint_quality(blueprint.payload)
                if not quality["valid"]:
                    invalid.append((concept.external_id or str(concept.id), concept.name, quality["issues"]))

        active_count = (
            db.query(GrammarConcept)
            .filter(
                GrammarConcept.language == "fr",
                GrammarConcept.active.is_(True),
                GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_VERSION,
            )
            .count()
        )
        archived_count = db.query(GrammarConceptArchive).count()
        localized_count = db.query(GrammarConceptLocalization).filter(GrammarConceptLocalization.locale == "de").count()
        blueprint_count = (
            db.query(AtelierConceptBlueprint)
            .join(GrammarConcept, GrammarConcept.id == AtelierConceptBlueprint.concept_id)
            .filter(
                GrammarConcept.catalog_version == FRENCH_CORE_CATALOG_VERSION,
                AtelierConceptBlueprint.review_status == "approved",
            )
            .count()
        )

        print(f"Catalog version: {FRENCH_CORE_CATALOG_VERSION}")
        print(f"Active French concepts: {active_count}")
        print(f"Archived legacy concepts: {archived_count}")
        print(f"German localizations: {localized_count}")
        print(f"Approved blueprints: {blueprint_count}")
        if invalid:
            print("Invalid blueprints:")
            for external_id, title, issues in invalid[:30]:
                print(f"- {external_id} {title}: {'; '.join(issues)}")
        elif args.backfill_blueprints:
            print("All generated blueprints passed the quality gate.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
