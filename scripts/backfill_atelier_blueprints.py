"""Backfill quality-gated Atelier concept blueprints.

Dry-run by default:
    .venv/bin/python scripts/backfill_atelier_blueprints.py --language fr

Apply changes:
    .venv/bin/python scripts/backfill_atelier_blueprints.py --language fr --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db.models.grammar import GrammarConcept
from app.db.session import SessionLocal
from app.services.atelier_assets import AtelierAssetService
from app.services.grammar_catalog import FrenchCoreGrammarCatalog


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Atelier concept blueprints")
    parser.add_argument("--language", default="fr")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true", help="Write approved blueprints to the database")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.language == "fr":
            FrenchCoreGrammarCatalog(db).ensure_catalog(archive_legacy=True)
        query = (
            db.query(GrammarConcept)
            .filter(GrammarConcept.language == args.language, GrammarConcept.active.is_(True))
            .order_by(GrammarConcept.level, GrammarConcept.difficulty_order, GrammarConcept.id)
        )
        if args.limit:
            query = query.limit(args.limit)
        concepts = query.all()
        service = AtelierAssetService(db)

        generated = 0
        failed: list[tuple[int, str, list[str]]] = []
        signatures: dict[str, int] = {}
        for concept in concepts:
            try:
                if args.apply:
                    blueprint = service.ensure_concept_blueprint(concept)
                    payload = blueprint.payload
                else:
                    payload = service.generate_concept_blueprint_payload(concept)
                quality = service.blueprint_quality(payload)
                signature = quality.get("motif_signature")
                if signature:
                    signatures[signature] = signatures.get(signature, 0) + 1
                if quality["valid"]:
                    generated += 1
                else:
                    failed.append((concept.id, concept.name, quality["issues"]))
            except Exception as exc:  # pragma: no cover - command line reporting
                failed.append((concept.id, concept.name, [str(exc)]))

        duplicates = [signature for signature, count in signatures.items() if count > 1]
        print(f"Concepts scanned: {len(concepts)}")
        print(f"Valid blueprints: {generated}")
        print(f"Duplicate motif signatures: {len(duplicates)}")
        if failed:
            print("Failures:")
            for concept_id, name, issues in failed[:20]:
                print(f"- {concept_id} {name}: {'; '.join(issues)}")
        if args.apply:
            db.commit()
            print("Applied blueprint backfill.")
        else:
            print("Dry run only; pass --apply to write.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
