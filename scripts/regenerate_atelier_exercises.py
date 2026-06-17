#!/usr/bin/env python
"""Prewarm current-version Atelier exercise sets for active grammar concepts."""
from __future__ import annotations

import argparse
import time
from typing import Any

from app.db.models.atelier import AtelierGenerationEvent
from app.db.models.grammar import GrammarConcept
from app.db.session import SessionLocal
from app.services.atelier import (
    ATELIER_GENERATOR_VERSION,
    AtelierExerciseGenerator,
    AtelierScheduler,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate Atelier exercise cache")
    parser.add_argument("--external-id", action="append", dest="external_ids", help="Only regenerate this concept")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of concepts to process")
    return parser.parse_args()


def _concept_query(db, external_ids: list[str] | None):
    query = db.query(GrammarConcept).filter(
        GrammarConcept.active.is_(True),
        GrammarConcept.external_id.isnot(None),
        GrammarConcept.external_id != "",
    )
    if external_ids:
        query = query.filter(GrammarConcept.external_id.in_(external_ids))
    return query.order_by(GrammarConcept.difficulty_order.asc(), GrammarConcept.id.asc())


def _event_summary(db, concept: GrammarConcept) -> dict[str, Any]:
    events = (
        db.query(AtelierGenerationEvent)
        .filter(
            AtelierGenerationEvent.concept_id == concept.id,
            AtelierGenerationEvent.generator_version == ATELIER_GENERATOR_VERSION,
        )
        .order_by(AtelierGenerationEvent.created_at.desc())
        .limit(12)
        .all()
    )
    structural_failures = [
        event for event in events
        if event.event_type == "structural_guard" and not event.passed
    ]
    critique_failures = [
        event for event in events
        if event.event_type == "ai_critique" and not event.passed
    ]
    token_cost = 0
    for event in events:
        payload = event.payload or {}
        usage = payload.get("usage") if isinstance(payload, dict) else {}
        if isinstance(usage, dict):
            token_cost += int(usage.get("total_tokens") or 0)
    return {
        "structural_failures": len(structural_failures),
        "critique_failures": len(critique_failures),
        "token_cost": token_cost,
    }


def main() -> int:
    args = _parse_args()
    db = SessionLocal()
    failures: list[dict[str, Any]] = []
    successes = 0
    try:
        AtelierScheduler(db).ensure_catalog()
        query = _concept_query(db, args.external_ids)
        if args.limit:
            query = query.limit(args.limit)
        concepts = query.all()
        generator = AtelierExerciseGenerator(db)
        print(f"Regenerating {len(concepts)} Atelier exercise set(s) for {ATELIER_GENERATOR_VERSION}.")
        for concept in concepts:
            label = concept.external_id or str(concept.id)
            started = time.perf_counter()
            try:
                exercise_set = generator.get_or_create(concept)
                latency_ms = int((time.perf_counter() - started) * 1000)
                event_summary = _event_summary(db, concept)
                successes += 1
                print(
                    f"ok   {label:<18} set={exercise_set.id} "
                    f"source={exercise_set.source} model={exercise_set.model or '-'} "
                    f"fallback={str(exercise_set.source == 'fallback').lower()} "
                    f"structural_failures={event_summary['structural_failures']} "
                    f"critique_failures={event_summary['critique_failures']} "
                    f"latency_ms={latency_ms} tokens={event_summary['token_cost'] or '-'}"
                )
            except Exception as exc:  # pragma: no cover - CLI safety net
                failures.append({"external_id": label, "error": str(exc)})
                print(f"fail {label:<18} {exc}")
        print(f"Done: {successes} ok, {len(failures)} failed.")
        return 1 if failures else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
