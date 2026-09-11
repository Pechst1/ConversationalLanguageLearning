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
from datetime import UTC, date, timedelta
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


# --------------------------------------------------------------------------
# WP-37 — the lines the 2026-09-10 packages wrote helpers for and could not call.
#
# Each package left a digest hook owed because this file was outside its lease
# (WP-30 §7, WP-31 §7.3, WP-32 §9.3, WP-34, WP-33). Every one of them prints
# something honest on an empty window: "nothing to report" is a result, and a
# rate with no denominator is not.
# --------------------------------------------------------------------------

#: `rehearsal_digest_line` and `intake_digest_line` count rows across the whole
#: cohort — neither takes a learner filter. Saying so is cheaper than a reader
#: assuming `--user-id` narrowed them.
_COHORT_NOTE = " · cohort-wide, not filtered by --user-id"


def format_rehearsal_line(db, day: date, user_id: str | None = None) -> str:
    """WP-31 §7.3. Did the real thing actually happen?

    The rehearsal score is deliberately not in it: what WP-31 claims is that a
    learner who rehearsed carried the situation out, and that is the only number
    the line prints. A window with no debriefs says so instead of printing 0 %.
    """

    from app.services.rehearsal import rehearsal_digest_line

    line = rehearsal_digest_line(db, since=day, until=day)
    return f"{line}{_COHORT_NOTE if user_id else ''}"


def format_intake_line(db, day: date, user_id: str | None = None) -> str:
    """WP-34. How many documents were brought in, how many were read, what it cost."""

    from datetime import datetime, time

    from app.services.intake import intake_digest_line

    start = datetime.combine(day, time.min, tzinfo=UTC)
    line = intake_digest_line(db, since=start, until=start + timedelta(days=1))
    return f"{line}{_COHORT_NOTE if user_id else ''}"


def format_episode_audio_line(db, day: date, user_id: str | None = None) -> str:
    """WP-32 §9.3, first half: spend per listening learner and the cache-hit rate.

    The cache-hit rate is the number that decides whether listening-first is
    affordable, so it is printed beside the money rather than derived later. A
    run served entirely from cache writes no row at all (a zero-cost row reads
    as a free call), so the rate here is over the lines of the runs that *did*
    synthesize — which is the only population this event type can speak for, and
    the line says so. The money is an estimate and repeats that out loud: the
    speech endpoint returns audio and no usage block.
    """

    from app.services.episode_audio import EPISODE_AUDIO_EVENT_TYPE

    normalized_user_id = UUID(str(user_id)) if user_id else None
    rows = db.query(PilotEvent.payload, PilotEvent.cost_usd, PilotEvent.user_id).filter(
        PilotEvent.event_type == EPISODE_AUDIO_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        rows = rows.filter(PilotEvent.user_id == normalized_user_id)
    runs = 0
    failed = 0
    synthesized = 0
    cached = 0
    cost = 0.0
    learners: set[str] = set()
    models: set[str] = set()
    for payload, row_cost, row_user in rows:
        payload = payload or {}
        runs += 1
        failed += 1 if str(payload.get("status")) == "failed" else 0
        synthesized += int(payload.get("lines") or 0)
        cached += int(payload.get("cached_lines") or 0)
        cost += float(row_cost or 0.0)
        if row_user is not None:
            learners.add(str(row_user))
        if payload.get("model"):
            models.add(str(payload["model"]))
    if not runs:
        return "Radio episodes (synthesis): none"
    served = synthesized + cached
    hit = f"{round(100 * cached / served)}%" if served else "no lines"
    per_learner = f" · ~${cost / len(learners):.4f}/listening learner" if learners else ""
    model_note = ", ".join(sorted(models)) or "model unreported"
    line = (
        f"Radio episodes (synthesis): {runs} paying run(s) · {len(learners)} learner(s) · "
        f"{synthesized} lines synthesized, {cached} from cache ({hit} of the lines these "
        f"runs served) · ~${cost:.4f} (estimated from characters, not a provider bill)"
        f"{per_learner} · {model_note}"
    )
    if failed:
        line += f" · {failed} run(s) failed and served no clips"
    return line


def format_episode_prediction_line(db, day: date, user_id: str | None = None) -> str:
    """WP-32 §9.3, second half: what the predict → verify stage concluded.

    Counts, never an accuracy rate. The prediction is a two-way choice, so a
    coin flip scores 50 % and a percentage here would read as a comprehension
    score it cannot be (WP-32 §10). `unresolved` is a real answer — a scene the
    stored lines settle neither way — and is printed as its own count, because
    the fraction landing there is the first thing the pilot must read.
    """

    from app.services.episode_audio import PREDICTION_EVENT_TYPE, PREDICTION_VERDICTS

    normalized_user_id = UUID(str(user_id)) if user_id else None
    rows = db.query(PilotEvent.payload).filter(
        PilotEvent.event_type == PREDICTION_EVENT_TYPE,
        func.date(PilotEvent.occurred_at) == day,
    )
    if normalized_user_id:
        rows = rows.filter(PilotEvent.user_id == normalized_user_id)
    counts = dict.fromkeys(PREDICTION_VERDICTS, 0)
    total = 0
    for (payload,) in rows:
        payload = payload or {}
        verdict = str(payload.get("verdict") or "unresolved")
        counts[verdict] = counts.get(verdict, 0) + 1
        total += 1
    if not total:
        return "Radio episodes (prediction): none"
    parts = ", ".join(f"{name}:{counts.get(name, 0)}" for name in PREDICTION_VERDICTS)
    return (
        f"Radio episodes (prediction, n={total}): {parts} — counts, not an accuracy "
        "rate: the guess is a two-way choice"
    )


def format_journal_lines(db, day: date, user_id: str | None = None) -> list[str]:
    """WP-30 §7: the journal's cost, and the one number the package exists for.

    The `+7d` follow-up signal is the journal's own — about a *scene*, not a
    sitting — and is deliberately never folded into `build_capability_summary`;
    two rubrics is the CONTRACTS §8 failure. So the two numbers are printed side
    by side and named apart.
    """

    from app.services.journal import JOURNAL_EVENT_TYPE, JOURNAL_FOLLOWUP_EVENT_TYPE

    normalized_user_id = UUID(str(user_id)) if user_id else None

    def _rows(event_type: str):
        query = db.query(PilotEvent.payload, PilotEvent.cost_usd).filter(
            PilotEvent.event_type == event_type,
            func.date(PilotEvent.occurred_at) == day,
        )
        if normalized_user_id:
            query = query.filter(PilotEvent.user_id == normalized_user_id)
        return list(query)

    corrections = _rows(JOURNAL_EVENT_TYPE)
    if corrections:
        tokens = sum(int((payload or {}).get("total_tokens") or 0) for payload, _ in corrections)
        cost = sum(float(row_cost or 0.0) for _, row_cost in corrections)
        models = sorted(
            {str((payload or {}).get("model")) for payload, _ in corrections if (payload or {}).get("model")}
        )
        first = (
            f"Journal corrections: {len(corrections)} calls · {tokens} tokens · "
            f"${cost:.4f} · {', '.join(models) or 'model unreported'}"
        )
    else:
        first = "Journal corrections: none"

    follow = _rows(JOURNAL_FOLLOWUP_EVENT_TYPE)
    if not follow:
        second = "Journal follow-ups (+7d): none answered — nothing to report"
    else:
        recalled = sum(
            1 for payload, _ in follow if str((payload or {}).get("signal")) == "used_again_later"
        )
        second = (
            f"Journal follow-ups (+7d): {recalled}/{len(follow)} still recalled a stored fact "
            "(the journal's own signal about a scene, not journey evidence)"
        )
    return [first, second]


def format_register_line(report: dict, user_id: str | None = None) -> str:
    """WP-33's dimension, read off the rollup the journey section already built.

    `_capability_rollup` calls `build_capability_summary`, which since WP-37
    carries `register` — so this costs no extra query and, by construction,
    cannot disagree with the capability line above it. It is a **stock**: each
    active learner's standing as of now, not something earned on the day.
    """

    section = (report or {}).get("journey") or {}
    capabilities = section.get("capabilities") or {}
    measured = int(capabilities.get("learners_measured") or 0)
    counts = (capabilities.get("by_capability") or {}).get("register")
    if not measured or not counts:
        return "Register (WP-33): no learner resolved on this day — nothing to report"
    states = ", ".join(f"{name}:{count}" for name, count in sorted(counts.items()))
    unknown = int(counts.get("unknown", 0)) + int(counts.get("not_tried", 0))
    return (
        f"Register (WP-33, n={measured} learners, standing not same-day): {states} · "
        f"{unknown} learner(s) with nothing to evaluate, reported as such and never as a pass"
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
        # WP-37: the five hooks the 2026-09-10 packages left owed here. Each one
        # says "none" / "nothing to report" on an empty day rather than a zero
        # that reads like a measurement.
        print(format_rehearsal_line(db, args.day, args.user_id))  # WP-31 §7.3
        print(format_intake_line(db, args.day, args.user_id))  # WP-34
        print(format_episode_audio_line(db, args.day, args.user_id))  # WP-32 §9.3
        print(format_episode_prediction_line(db, args.day, args.user_id))  # WP-32 §9.3
        for line in format_journal_lines(db, args.day, args.user_id):  # WP-30 §7
            print(line)
    # WP-33: read off the rollup above — no extra query, and it cannot disagree
    # with the capability line the journey section prints.
    print(format_register_line(report, args.user_id))


if __name__ == "__main__":
    main()
