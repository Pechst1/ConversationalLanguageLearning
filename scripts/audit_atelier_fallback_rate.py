#!/usr/bin/env python
"""Measure how often live Atelier exercise generation would need deterministic fallback."""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.db.models.atelier import AtelierExerciseSet, AtelierGenerationEvent
from app.db.models.grammar import GrammarConcept
from app.db.session import SessionLocal
from app.services.atelier import ATELIER_GENERATOR_VERSION, AtelierExerciseGenerator, AtelierScheduler


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit live Atelier fallback trigger rate")
    parser.add_argument("--cycles", type=int, default=3, help="How many repeated live-generation cycles to run")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of active concepts per cycle")
    parser.add_argument("--external-id", action="append", dest="external_ids", help="Only audit this concept")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to pause between attempts")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON report path")
    parser.add_argument(
        "--history-only",
        action="store_true",
        help="Do not call the LLM; summarize local exercise-set and generation-event fallback history",
    )
    parser.add_argument(
        "--reset-backoff",
        action="store_true",
        help="Reset provider backoff before each attempt to sample each request independently",
    )
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


def _valid_cached_llm(db, concept: GrammarConcept) -> bool:
    cached = (
        db.query(AtelierExerciseSet)
        .filter(
            AtelierExerciseSet.concept_id == concept.id,
            AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
            AtelierExerciseSet.source == "llm",
        )
        .order_by(AtelierExerciseSet.created_at.desc())
        .first()
    )
    return bool(cached and AtelierExerciseGenerator.validate_payload(cached.payload, concept=concept))


def _pending_generation_events(db) -> list[AtelierGenerationEvent]:
    return [event for event in db.new if isinstance(event, AtelierGenerationEvent)]


def _event_reasons(events: list[AtelierGenerationEvent]) -> list[str]:
    reasons: list[str] = []
    for event in events:
        payload = event.payload or {}
        if event.event_type == "structural_guard" and not event.passed:
            errors = payload.get("errors") if isinstance(payload, dict) else []
            reasons.extend(str(error) for error in (errors or [])[:4])
        if event.event_type == "ai_critique" and not event.passed:
            verdicts = payload.get("verdicts") if isinstance(payload, dict) else []
            for verdict in (verdicts or [])[:8]:
                if isinstance(verdict, dict) and not verdict.get("passes"):
                    reasons.append(str(verdict.get("reason") or "AI critique failed"))
    return reasons


def _reason_bucket(result: tuple[dict[str, Any], str, str] | None, events: list[AtelierGenerationEvent]) -> str:
    if result:
        if any(not event.passed for event in events):
            return "repaired_after_failed_attempt"
        return "live_generation_ok"
    failed_types = {event.event_type for event in events if not event.passed}
    if "ai_critique" in failed_types:
        return "ai_critique_failed"
    if "structural_guard" in failed_types:
        return "structural_guard_failed"
    if AtelierExerciseGenerator._llm_backoff_remaining_seconds() > 0:
        return "provider_backoff_or_unavailable"
    if not settings.ATELIER_LLM_ENABLED:
        return "atelier_llm_disabled"
    if not (settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY):
        return "missing_llm_key"
    return "generation_returned_none"


def _attempt(db, concept_id: int, *, cycle: int, reset_backoff: bool) -> dict[str, Any]:
    if reset_backoff:
        AtelierExerciseGenerator._llm_backoff_until = 0.0
        AtelierExerciseGenerator._llm_backoff_reason = None
    concept = db.get(GrammarConcept, concept_id)
    if not concept:
        raise RuntimeError(f"Concept {concept_id} disappeared during audit")

    cache_cover = _valid_cached_llm(db, concept)
    generator = AtelierExerciseGenerator(db)
    started = time.perf_counter()
    result = generator._generate_with_llm(concept)
    latency_ms = int((time.perf_counter() - started) * 1000)
    events = _pending_generation_events(db)
    reasons = _event_reasons(events)
    row = {
        "cycle": cycle,
        "concept_id": concept.id,
        "external_id": concept.external_id,
        "concept_name": concept.name,
        "live_generation_ok": result is not None,
        "fallback_triggered": result is None,
        "cache_would_cover": bool(cache_cover and result is None),
        "deterministic_fallback_needed": bool(result is None and not cache_cover),
        "reason_bucket": _reason_bucket(result, events),
        "model": result[1] if result else None,
        "latency_ms": latency_ms,
        "event_counts": dict(Counter(event.event_type for event in events)),
        "failed_event_counts": dict(Counter(event.event_type for event in events if not event.passed)),
        "reasons": reasons[:8],
        "backoff_remaining_seconds": round(AtelierExerciseGenerator._llm_backoff_remaining_seconds(), 1),
        "backoff_reason": AtelierExerciseGenerator._llm_backoff_reason,
    }
    db.rollback()
    return row


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    fallback = sum(1 for row in rows if row["fallback_triggered"])
    deterministic = sum(1 for row in rows if row["deterministic_fallback_needed"])
    cache_cover = sum(1 for row in rows if row["cache_would_cover"])
    repaired = sum(1 for row in rows if row["reason_bucket"] == "repaired_after_failed_attempt")
    buckets = Counter(str(row["reason_bucket"]) for row in rows)
    by_concept: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["external_id"])
        entry = by_concept.setdefault(
            key,
            {
                "name": row["concept_name"],
                "attempts": 0,
                "fallback_triggered": 0,
                "deterministic_fallback_needed": 0,
                "cache_would_cover": 0,
                "reason_buckets": Counter(),
            },
        )
        entry["attempts"] += 1
        entry["fallback_triggered"] += int(row["fallback_triggered"])
        entry["deterministic_fallback_needed"] += int(row["deterministic_fallback_needed"])
        entry["cache_would_cover"] += int(row["cache_would_cover"])
        entry["reason_buckets"][row["reason_bucket"]] += 1
    for entry in by_concept.values():
        entry["reason_buckets"] = dict(entry["reason_buckets"])
    return {
        "attempts": total,
        "live_generation_ok": total - fallback,
        "fallback_triggered": fallback,
        "fallback_trigger_rate": round(fallback / total, 4) if total else 0.0,
        "deterministic_fallback_needed": deterministic,
        "deterministic_fallback_rate": round(deterministic / total, 4) if total else 0.0,
        "cache_would_cover": cache_cover,
        "repaired_after_failed_attempt": repaired,
        "reason_buckets": dict(buckets),
        "by_concept": by_concept,
    }


def _history_report(db, args: argparse.Namespace) -> dict[str, Any]:
    concept_query = _concept_query(db, args.external_ids)
    if args.limit:
        concept_query = concept_query.limit(args.limit)
    concepts = concept_query.all()
    concept_ids = [concept.id for concept in concepts]
    active_count = db.query(GrammarConcept).filter(GrammarConcept.active.is_(True)).count()

    set_query = db.query(AtelierExerciseSet).filter(
        AtelierExerciseSet.generator_version == ATELIER_GENERATOR_VERSION,
    )
    event_query = db.query(AtelierGenerationEvent).filter(
        AtelierGenerationEvent.generator_version == ATELIER_GENERATOR_VERSION,
    )
    if concept_ids:
        set_query = set_query.filter(AtelierExerciseSet.concept_id.in_(concept_ids))
        event_query = event_query.filter(AtelierGenerationEvent.concept_id.in_(concept_ids))
    sets = set_query.order_by(AtelierExerciseSet.created_at.asc()).all()
    events = event_query.order_by(AtelierGenerationEvent.created_at.desc()).all()

    validity = Counter()
    invalid_sets: list[dict[str, Any]] = []
    latest_by_concept: dict[int, AtelierExerciseSet] = {}
    for exercise_set in sets:
        concept = exercise_set.concept
        valid = AtelierExerciseGenerator.validate_payload(exercise_set.payload, concept=concept)
        validity[f"{exercise_set.source}:{'valid' if valid else 'invalid'}"] += 1
        if not valid:
            invalid_sets.append(
                {
                    "external_id": concept.external_id if concept else None,
                    "source": exercise_set.source,
                    "exercise_set_id": str(exercise_set.id),
                    "created_at": exercise_set.created_at.isoformat() if exercise_set.created_at else None,
                }
            )
        latest_by_concept[exercise_set.concept_id] = exercise_set

    latest_counts = Counter(exercise_set.source for exercise_set in latest_by_concept.values())
    failed_events = [event for event in events if not event.passed]
    failed_samples: list[dict[str, Any]] = []
    reason_counter = Counter()
    for event in failed_events:
        reasons = _event_reasons([event])
        for reason in reasons:
            reason_counter[reason] += 1
        if len(failed_samples) < 25:
            failed_samples.append(
                {
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                    "event_type": event.event_type,
                    "model": event.model,
                    "external_id": event.concept.external_id if event.concept else None,
                    "reasons": reasons[:4],
                }
            )

    total_sets = len(sets)
    source_counts = Counter(exercise_set.source for exercise_set in sets)
    fallback_sets = source_counts.get("fallback", 0)
    latest_total = len(latest_by_concept)
    latest_fallback = latest_counts.get("fallback", 0)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": ATELIER_GENERATOR_VERSION,
        "history_only": True,
        "summary": {
            "active_concepts": active_count,
            "selected_concepts": len(concepts),
            "exercise_sets_current_version": total_sets,
            "source_counts": dict(source_counts),
            "fallback_set_rate": round(fallback_sets / total_sets, 4) if total_sets else 0.0,
            "latest_concepts_with_sets": latest_total,
            "latest_source_counts": dict(latest_counts),
            "latest_fallback_rate": round(latest_fallback / latest_total, 4) if latest_total else 0.0,
            "source_validity": dict(validity),
            "generation_events_current_version": len(events),
            "event_type_passed": {
                f"{event_type}:{passed}": count
                for (event_type, passed), count in Counter((event.event_type, event.passed) for event in events).items()
            },
            "failed_generation_events": len(failed_events),
            "failure_reason_counts": dict(reason_counter.most_common(20)),
        },
        "invalid_sets": invalid_sets[:50],
        "failed_event_samples": failed_samples,
    }


def main() -> int:
    args = _parse_args()
    db = SessionLocal()
    rows: list[dict[str, Any]] = []
    try:
        AtelierScheduler(db).ensure_catalog()
        if args.history_only:
            report = _history_report(db, args)
            print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"Wrote {args.output}")
            return 0

        query = _concept_query(db, args.external_ids)
        query = query.limit(args.limit or 3)
        concept_ids = [concept.id for concept in query.all()]
        print(
            "Atelier fallback audit "
            f"cycles={args.cycles} concepts={len(concept_ids)} "
            f"llm_enabled={settings.ATELIER_LLM_ENABLED} "
            f"critique_enabled={settings.ATELIER_EXERCISE_CRITIQUE_ENABLED} "
            f"exercise_model={settings.ATELIER_EXERCISE_LLM_MODEL} "
            f"critique_model={settings.ATELIER_CRITIQUE_LLM_MODEL}"
        )
        for cycle in range(1, args.cycles + 1):
            for concept_id in concept_ids:
                row = _attempt(db, concept_id, cycle=cycle, reset_backoff=args.reset_backoff)
                rows.append(row)
                print(
                    f"cycle={row['cycle']} {row['external_id']:<18} "
                    f"live_ok={str(row['live_generation_ok']).lower():<5} "
                    f"fallback_triggered={str(row['fallback_triggered']).lower():<5} "
                    f"cache_cover={str(row['cache_would_cover']).lower():<5} "
                    f"deterministic_needed={str(row['deterministic_fallback_needed']).lower():<5} "
                    f"bucket={row['reason_bucket']} latency_ms={row['latency_ms']}"
                )
                if row["reasons"]:
                    print(f"  reasons: {' | '.join(row['reasons'][:3])}")
                if args.sleep:
                    time.sleep(args.sleep)
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator_version": ATELIER_GENERATOR_VERSION,
            "settings": {
                "atelier_llm_enabled": settings.ATELIER_LLM_ENABLED,
                "critique_enabled": settings.ATELIER_EXERCISE_CRITIQUE_ENABLED,
                "exercise_model": settings.ATELIER_EXERCISE_LLM_MODEL,
                "critique_model": settings.ATELIER_CRITIQUE_LLM_MODEL,
                "reset_backoff": args.reset_backoff,
            },
            "summary": _summary(rows),
            "rows": rows,
        }
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Wrote {args.output}")
        return 1 if report["summary"]["deterministic_fallback_needed"] else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
