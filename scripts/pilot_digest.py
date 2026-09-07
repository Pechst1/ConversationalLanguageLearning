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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--user-id")
    parser.add_argument(
        "--journey-only",
        action="store_true",
        help="Print only the daily-journey section (WP-11 release metrics).",
    )
    args = parser.parse_args()
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


if __name__ == "__main__":
    main()
