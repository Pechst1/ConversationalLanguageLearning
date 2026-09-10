#!/usr/bin/env python3
"""Print one day of pilot activity, spend, and failures.

The daily-journey section (WP-11) is part of the same report: start/completion/
early-stop counts, step drop-off, help use, the measured active-duration
distribution, provider waiting, retry and fallback rates, and cost coverage.
Every rate carries its denominator, and a day with too few journeys prints an
explicit insufficient-data line instead of a precise-looking number.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func

from app.db.models.pilot_event import PilotEvent
from app.db.session import SessionLocal
from app.services.pilot_events import PilotEventService, format_daily_digest

#: WP-16 §5. The Séance correction is the most-used paid endpoint in the app and
#: had no cost telemetry until this package, so the weekly guardrail did not
#: cover it (STATUS 2026-09-07 §WP-15). One row per real checker call, written
#: at the call site in `AtelierCorrectionService`.
CORRECTION_EVENT_TYPE = "atelier_correction"


def format_correction_line(db, day: date, user_id: str | None = None) -> str:
    """One digest line for the day's Séance corrections.

    Prints the denominators — calls and tokens — beside the money, so a day
    whose cost looks small because the provider reported none is still visible
    as a day with real traffic.
    """

    # `--user-id` arrives as a string; the column is a real UUID type.
    normalized_user_id = UUID(str(user_id)) if user_id else None
    query = db.query(
        func.count(PilotEvent.id),
        func.coalesce(func.sum(PilotEvent.cost_usd), 0.0),
    ).filter(
        PilotEvent.event_type == CORRECTION_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        query = query.filter(PilotEvent.user_id == normalized_user_id)
    calls, cost = query.one()
    calls = int(calls or 0)
    if not calls:
        return "Séance corrections: none"

    token_rows = db.query(PilotEvent.payload).filter(
        PilotEvent.event_type == CORRECTION_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        token_rows = token_rows.filter(PilotEvent.user_id == normalized_user_id)
    tokens = 0
    truncated = 0
    models: set[str] = set()
    for (payload,) in token_rows:
        payload = payload or {}
        tokens += int(payload.get("total_tokens") or 0)
        truncated += 1 if payload.get("answer_truncated") else 0
        if payload.get("model"):
            models.add(str(payload["model"]))
    model_note = ", ".join(sorted(models)) or "model unreported"
    line = (
        f"Séance corrections: {calls} calls · {tokens} tokens · "
        f"${float(cost or 0.0):.4f} · {model_note}"
    )
    if truncated:
        line += f" · {truncated} answer(s) truncated at the request bound"
    return line


def format_transcription_line(db, day: date, user_id: str | None = None) -> str:
    """One digest line for the day's transcriptions, declared as an estimate.

    WP-27 made speaking the journey's default output, so this endpoint is on
    the learner's main path. Whisper reports neither duration nor usage, so the
    money here is modelled from upload size — the line says "estimated" out
    loud, because a modelled cost printed as a bill is worse than no line.
    """

    from app.services.transcription_cost import TRANSCRIPTION_EVENT_TYPE

    normalized_user_id = UUID(str(user_id)) if user_id else None
    rows = db.query(PilotEvent.payload, PilotEvent.cost_usd).filter(
        PilotEvent.event_type == TRANSCRIPTION_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        rows = rows.filter(PilotEvent.user_id == normalized_user_id)
    calls = 0
    cost = 0.0
    seconds = 0.0
    surfaces: dict[str, int] = {}
    for payload, row_cost in rows:
        payload = payload or {}
        calls += 1
        cost += float(row_cost or 0.0)
        seconds += float(payload.get("estimated_seconds") or 0.0)
        surface = str(payload.get("surface") or "unknown")
        surfaces[surface] = surfaces.get(surface, 0) + 1
    if not calls:
        return "Transcriptions: none"
    where = ", ".join(f"{name} {count}" for name, count in sorted(surfaces.items()))
    return (
        f"Transcriptions: {calls} calls · ~{seconds / 60.0:.1f} min audio · "
        f"~${cost:.4f} (estimated from upload size, not a provider bill) · {where}"
    )


#: WP-25. One row per placement grading call. A placement is at most six paid
#: calls and happens at most once per learner, so it will never dominate the
#: bill — but a cost nobody prints is a cost nobody notices, and the first-week
#: spend per learner is exactly what the pilot is trying to learn.
PLACEMENT_EVENT_TYPE = "placement_grading"


def format_placement_line(db, day: date, user_id: str | None = None) -> str:
    """One digest line for the day's placement gradings.

    Same shape and same rule as the correction line: calls and tokens beside the
    money, so a day whose cost reads zero because the provider reported none is
    still visible as a day with real traffic. ``learners`` is printed because
    cost per placed learner, not cost per call, is the number that decides
    whether an honest placement is affordable at cohort scale.
    """

    normalized_user_id = UUID(str(user_id)) if user_id else None
    rows = db.query(PilotEvent.payload, PilotEvent.cost_usd, PilotEvent.user_id).filter(
        PilotEvent.event_type == PLACEMENT_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        rows = rows.filter(PilotEvent.user_id == normalized_user_id)
    calls = 0
    tokens = 0
    cost = 0.0
    learners: set[str] = set()
    models: set[str] = set()
    for payload, row_cost, row_user in rows:
        payload = payload or {}
        calls += 1
        tokens += int(payload.get("total_tokens") or 0)
        cost += float(row_cost or 0.0)
        if row_user is not None:
            learners.add(str(row_user))
        if payload.get("model"):
            models.add(str(payload["model"]))
    if not calls:
        return "Placements: none"
    model_note = ", ".join(sorted(models)) or "model unreported"
    per_learner = f" · ${cost / len(learners):.4f}/learner" if learners else ""
    return (
        f"Placements: {calls} gradings · {len(learners)} learner(s) · "
        f"{tokens} tokens · ${cost:.4f}{per_learner} · {model_note}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--user-id")
    parser.add_argument(
        "--latency-only",
        action="store_true",
        help="Print only the WP-26 latency section and the release gate.",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help=(
            "Exit non-zero unless the WP-26 release gate passes. "
            "insufficient_data is not a pass."
        ),
    )
    parser.add_argument(
        "--journey-only",
        action="store_true",
        help="Print only the daily-journey section (WP-11 release metrics).",
    )
    args = parser.parse_args()

    # WP-26 §3: latency is a release metric, so it can be read on its own and
    # can fail a build.
    from app.services.journey_latency import (
        evaluate_gate,
        format_latency_lines,
        latency_rollup,
    )

    if args.latency_only or args.gate:
        with SessionLocal() as db:
            rollup = latency_rollup(db, args.day, user_id=args.user_id)
        print("\n".join(format_latency_lines(rollup)))
        if args.gate:
            verdict = evaluate_gate(rollup)
            raise SystemExit(0 if verdict["status"] == "pass" else 1)
        return

    with SessionLocal() as db:
        report = PilotEventService(db).daily_rollup(args.day, user_id=args.user_id)
    if args.journey_only:
        from app.services.journey_events import format_journey_digest

        print("\n".join(format_journey_digest(report["journey"])))
        return
    print(format_daily_digest(report))
    # WP-16 §5: the Séance correction line item.
    with SessionLocal() as db:
        print(format_correction_line(db, args.day, args.user_id))
    # WP-27: the transcription line item, declared as an estimate.
    with SessionLocal() as db:
        print(format_transcription_line(db, args.day, args.user_id))
    # WP-26: p50/p95 per waited-on phase, the prefetch hit rate, and the gate.
    with SessionLocal() as db:
        print("\n".join(format_latency_lines(latency_rollup(db, args.day, user_id=args.user_id))))
        # WP-25: the placement line item.
        print(format_placement_line(db, args.day, args.user_id))
        # WP-29: known-word coverage of the day's generated scenes, as the
        # generator measured them. Says so explicitly when it did not, because an
        # unmeasured scene is not a scene at 100 %.
        from app.services.lexical_coverage import format_coverage_line

        # The hook is applied (WP-29 §5, in living_story `_validate_scene`), so
        # an unmeasured scene now means a scene generated before it landed or one
        # too short to measure — not a missing hook. Rewritten here rather than in
        # `format_coverage_line`, which another package owns.
        print(
            format_coverage_line(db, args.day, args.user_id).replace(
                "(WP-29 hook not applied in living_story.py)",
                "(generated before the coverage hook, or too short to measure)",
            )
        )


if __name__ == "__main__":
    main()
