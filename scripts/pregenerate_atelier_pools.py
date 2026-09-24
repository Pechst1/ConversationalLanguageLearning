#!/usr/bin/env python
"""WP-S2 (La Forge): batch pre-generation of the shared LLM pools, run offline.

The séance serves its recognition, repair and build items from the item bank
(``app/data/grammar_templates``) and takes its situations and production
prompts from a *shared pool*: vetted LLM sets generated without a learner, one
pool per (concept, learner band). This job fills every pool up to
``ATELIER_POOL_SETS_PER_BAND`` sets, through the same structural guard and AI
critic as every generated set; the quality flywheel retires pool sets on
reports or a high wrong rate and regenerates them in the same band.

    python scripts/pregenerate_atelier_pools.py --dry-run
    python scripts/pregenerate_atelier_pools.py --band A1 --band A2 --per-band 3 --max-new 40
    python scripts/pregenerate_atelier_pools.py --external-id FR2_A11_ETRE
"""
from __future__ import annotations

import argparse
import json
import time

from app.db.models.grammar import GrammarConcept
from app.db.session import SessionLocal
from app.services.atelier import AtelierPoolService, AtelierScheduler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-generate La Forge's shared LLM pools")
    parser.add_argument("--external-id", action="append", dest="external_ids", help="Only this concept (repeatable)")
    parser.add_argument("--band", action="append", dest="bands", help="Learner band (repeatable; default A1 and A2)")
    parser.add_argument("--per-band", type=int, default=None, help="Pool size per (concept, band)")
    parser.add_argument("--max-new", type=int, default=None, help="Stop after creating this many sets")
    parser.add_argument("--dry-run", action="store_true", help="Report what is missing without generating")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    db = SessionLocal()
    started = time.monotonic()
    try:
        AtelierScheduler(db).ensure_catalog()
        query = db.query(GrammarConcept).filter(GrammarConcept.active.is_(True))
        if args.external_ids:
            query = query.filter(GrammarConcept.external_id.in_(args.external_ids))
        concepts = query.order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc()).all()
        report = AtelierPoolService(db).pregenerate(
            concepts=concepts,
            bands=tuple(args.bands or ("A1", "A2")),
            per_band=args.per_band,
            max_new=args.max_new,
            dry_run=args.dry_run,
        )
    finally:
        db.close()
    report["seconds"] = round(time.monotonic() - started, 1)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report.get("failed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
