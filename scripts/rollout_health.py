#!/usr/bin/env python
"""Run the WP-18 rollout health queries against an explicit database.

These are exactly the queries printed in
``docs/implementation/atelier-v2/ROLLOUT.md`` §Health and §Cost, kept in code so
the runbook and the tool cannot drift. Read-only: every statement is a SELECT.

    .venv/bin/python scripts/rollout_health.py \\
        --database-url postgresql://user:pass@host/db --since 2026-09-07

``--since`` (default: seven days ago) bounds every query. ``--user`` narrows to
one learner by email. ``--json`` prints machine-readable rows instead of tables.

Safety: the owner's local database is called ``language_learning`` and so is the
Render pilot database. The script refuses that name outright; pass
``--allow-production-name`` to run it against the *remote* pilot database on
purpose. A local ``language_learning`` is refused even then.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

LOCAL_HOSTS = {"", "localhost", "127.0.0.1", "::1", "0.0.0.0"}  # noqa: S104 - comparison, not a bind


@dataclass(frozen=True)
class Query:
    key: str
    title: str
    sql: str


#: Journeys created and completed per learner-local day, with the honest
#: denominators beside them. ``local_date`` is the learner's own calendar day.
JOURNEY_VOLUME = Query(
    "journeys",
    "Journeys per learner-local day",
    """
    SELECT j.local_date AS day,
           count(*) AS created,
           count(*) FILTER (WHERE j.status = 'completed') AS completed,
           count(*) FILTER (WHERE j.status = 'ended_early') AS ended_early,
           count(*) FILTER (WHERE j.status IN ('preparing', 'active', 'paused')) AS still_open,
           count(DISTINCT j.user_id) AS learners
      FROM daily_journeys j
      JOIN users u ON u.id = j.user_id
     WHERE j.local_date >= :since
       AND (:email IS NULL OR u.email = :email)
     GROUP BY j.local_date
     ORDER BY j.local_date
    """,
)

#: Anything a learner would experience as "nothing to do today": a journey stuck
#: in preparing, or one that gave up with an unavailable reason.
JOURNEY_STATES = Query(
    "states",
    "Journey states and unavailable reasons",
    """
    SELECT j.status,
           coalesce(j.unavailable_reason, '-') AS unavailable_reason,
           j.unavailable_retry_allowed AS retry_allowed,
           count(*) AS journeys,
           max(j.generation_attempts) AS max_generation_attempts
      FROM daily_journeys j
      JOIN users u ON u.id = j.user_id
     WHERE j.local_date >= :since
       AND (:email IS NULL OR u.email = :email)
     GROUP BY 1, 2, 3
     ORDER BY journeys DESC
    """,
)

#: 409s. Every conflict the service answers emits ``journey_resume_conflict``
#: (version conflict or step-not-active); the denominator is the accepted
#: mutations on the same day, so the rate means "conflicts per accepted move".
JOURNEY_CONFLICTS = Query(
    "conflicts",
    "409 conflict rate per day",
    """
    WITH events AS (
        SELECT date(e.occurred_at) AS day,
               e.event_type,
               coalesce(e.payload->>'conflict_kind', '-') AS conflict_kind
          FROM pilot_events e
          LEFT JOIN users u ON u.id = e.user_id
         WHERE e.occurred_at >= :since
           AND (:email IS NULL OR u.email = :email)
    )
    SELECT day,
           count(*) FILTER (WHERE event_type = 'journey_resume_conflict') AS conflicts,
           count(*) FILTER (WHERE event_type = 'journey_resume_conflict'
                              AND conflict_kind = 'version_conflict') AS version_conflicts,
           count(*) FILTER (WHERE event_type = 'journey_resume_conflict'
                              AND conflict_kind = 'step_not_active') AS step_not_active,
           count(*) FILTER (WHERE event_type IN ('journey_started', 'journey_step_completed',
                                                 'journey_completed', 'journey_ended_early')
                           ) AS accepted_mutations
      FROM events
     GROUP BY day
     ORDER BY day
    """,
)

#: Engine spend per learner-day, read from the same place the weekly guardrail
#: reads it: ``graphic_novel_scenes.script_payload->'estimated_cost'``. Engine
#: scenes are the ones whose cost basis names the living-story prompt revision.
ENGINE_COST = Query(
    "engine_cost",
    "Engine cost per learner-day (scene estimated_cost)",
    """
    SELECT date(s.created_at) AS day,
           u.email,
           count(*) AS scenes,
           round(sum((s.script_payload->'estimated_cost'->>'story_generation_usd')::numeric), 6)
               AS story_usd,
           round(sum((s.script_payload->'estimated_cost'->>'total_estimated_usd')::numeric), 6)
               AS total_usd
      FROM graphic_novel_scenes s
      JOIN users u ON u.id = s.user_id
     WHERE s.created_at >= :since
       AND s.script_payload->'estimated_cost'->>'basis' LIKE 'living-story-%'
       AND (:email IS NULL OR u.email = :email)
     GROUP BY 1, 2
     ORDER BY 1, 2
    """,
)

#: The event ledger behind the same money, including the spend of generations
#: that never produced a scene — those exist only here.
ENGINE_LEDGER = Query(
    "engine_ledger",
    "Engine cost ledger rows (pilot_events)",
    """
    SELECT date(e.occurred_at) AS day,
           e.event_type,
           count(*) AS rows_written,
           round(sum(e.cost_usd)::numeric, 6) AS cost_usd
      FROM pilot_events e
      LEFT JOIN users u ON u.id = e.user_id
     WHERE e.occurred_at >= :since
       AND e.event_type IN ('journey_story_scene_cost', 'journey_story_turn_cost',
                            'journey_story_generation_failed')
       AND (:email IS NULL OR u.email = :email)
     GROUP BY 1, 2
     ORDER BY 1, 2
    """,
)

#: Séance correction spend (the most-used paid endpoint). One row per real
#: checker call, written at the call site; the digest prints the same numbers.
CORRECTION_COST = Query(
    "correction_cost",
    "Séance correction cost per day",
    """
    SELECT date(e.occurred_at) AS day,
           count(*) AS calls,
           sum(coalesce((e.payload->>'total_tokens')::int, 0)) AS tokens,
           round(sum(e.cost_usd)::numeric, 6) AS cost_usd
      FROM pilot_events e
      LEFT JOIN users u ON u.id = e.user_id
     WHERE e.occurred_at >= :since
       AND e.event_type = 'atelier_correction'
       AND (:email IS NULL OR u.email = :email)
     GROUP BY 1
     ORDER BY 1
    """,
)

#: The weekly guardrail itself: learner spend per ISO week from the scene
#: estimates, which is what PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD compares to.
WEEKLY_GUARDRAIL = Query(
    "weekly_guardrail",
    "Weekly spend per learner against the guardrail",
    """
    SELECT extract(isoyear FROM s.created_at)::int AS iso_year,
           extract(week FROM s.created_at)::int AS iso_week,
           u.email,
           count(*) AS scenes,
           round(sum((s.script_payload->'estimated_cost'->>'total_estimated_usd')::numeric), 4)
               AS week_usd,
           (sum((s.script_payload->'estimated_cost'->>'total_estimated_usd')::numeric)
                > :guardrail) AS over_guardrail
      FROM graphic_novel_scenes s
      JOIN users u ON u.id = s.user_id
     WHERE s.created_at >= :since
       AND s.serial_thread_id IS NOT NULL
       AND (:email IS NULL OR u.email = :email)
     GROUP BY 1, 2, 3
     ORDER BY 1, 2, 5 DESC
    """,
)

QUERIES: tuple[Query, ...] = (
    JOURNEY_VOLUME,
    JOURNEY_STATES,
    JOURNEY_CONFLICTS,
    ENGINE_COST,
    ENGINE_LEDGER,
    CORRECTION_COST,
    WEEKLY_GUARDRAIL,
)


class UnsafeDatabase(SystemExit):
    """Raised as a SystemExit so the CLI exits non-zero with the reason."""


def guard_database_url(url: str, *, allow_production_name: bool = False) -> str:
    """Refuse the owner's database; allow the remote pilot one only on purpose."""

    if not url:
        raise UnsafeDatabase("--database-url is required.")
    host = (urlparse(url).hostname or "").lower()
    name = urlparse(url).path.lstrip("/").split("?")[0].lower()
    if "language_learning" not in url:
        return url
    if host in LOCAL_HOSTS or name != "language_learning":
        raise UnsafeDatabase(
            "Refusing the owner's local language_learning database. Point this at "
            "the pilot database, or at a throwaway copy."
        )
    if not allow_production_name:
        raise UnsafeDatabase(
            "This URL names a 'language_learning' database on a remote host — the "
            "Render pilot database. Re-run with --allow-production-name if that is "
            "what you mean."
        )
    return url


def run_query(engine, query: Query, params: dict[str, Any]) -> tuple[list[str], list[tuple]]:
    with engine.connect() as conn:
        result = conn.execute(text(query.sql), params)
        return list(result.keys()), [tuple(row) for row in result]


def render_table(title: str, columns: list[str], rows: list[tuple]) -> str:
    if not rows:
        return f"{title}\n  (no rows)"
    cells = [[("" if value is None else str(value)) for value in row] for row in rows]
    widths = [max(len(columns[i]), *(len(row[i]) for row in cells)) for i in range(len(columns))]
    head = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns)).rstrip()
    rule = "-+-".join("-" * width for width in widths)
    body = [" | ".join(row[i].ljust(widths[i]) for i in range(len(columns))).rstrip() for row in cells]
    return "\n".join([title, head, rule, *body])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=7),
        help="Inclusive lower bound (YYYY-MM-DD). Default: seven days ago.",
    )
    parser.add_argument("--user", help="Narrow every query to one learner email.")
    parser.add_argument(
        "--guardrail",
        type=float,
        default=2.0,
        help="PILOT_SERIAL_WEEKLY_COST_GUARDRAIL_USD, for the weekly column.",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=[q.key for q in QUERIES],
        help="Run only these queries (repeatable).",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON rows instead of tables.")
    parser.add_argument(
        "--allow-production-name",
        action="store_true",
        help="Permit a remote database literally named language_learning (the Render pilot).",
    )
    args = parser.parse_args(argv)

    url = guard_database_url(args.database_url, allow_production_name=args.allow_production_name)
    params = {"since": args.since, "email": args.user, "guardrail": args.guardrail}
    selected = [q for q in QUERIES if not args.only or q.key in args.only]

    engine = create_engine(url)
    payload: dict[str, Any] = {"since": args.since.isoformat(), "user": args.user, "sections": {}}
    try:
        for query in selected:
            columns, rows = run_query(engine, query, params)
            if args.json:
                payload["sections"][query.key] = [dict(zip(columns, row, strict=True)) for row in rows]
            else:
                print(render_table(f"\n## {query.title}", columns, rows))
    finally:
        engine.dispose()

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
