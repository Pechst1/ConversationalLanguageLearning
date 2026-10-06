#!/usr/bin/env python3
"""WP-29 — known-word coverage over a learner's recent generated scenes.

Answers one question the app could not answer before: *are the scenes we
generate actually readable by the learner we generated them for?* Comprehension
with support needs about 95 % known-word coverage (Laufer & Ravenhorst-Kalovski
2010); until this package nothing measured it, and the band label on the prompt
was the whole quality control.

Two honest labels the report insists on:

``stored``
    The generator measured this scene at generation time and the number in the
    row is what the learner was actually served.

``recomputed``
    The WP-29 hook is not in ``living_story.py`` yet (it is leased to WP-28), so
    coverage is recomputed here from the stored panels **against today's
    known-word set** — not the one the learner had that day. A learner who has
    since learned fifty words will read better here than they did then. Useful
    for a distribution, not evidence about a particular day.

Usage::

    .venv/bin/python scripts/coverage_report.py --user-id <uuid>
    .venv/bin/python scripts/coverage_report.py --email a@b.c --limit 30 --json
"""
from __future__ import annotations

import argparse
import json
from uuid import UUID

from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.lexical_coverage import (
    ACCIDENTAL_UNKNOWN_BUDGET,
    SUPPORTED_COVERAGE_FLOOR,
    UNASSISTED_COVERAGE_FLOOR,
    accidental_budget,
    coverage_distribution,
    default_resolver,
    known_word_set,
    load_lexicon,
    recent_scene_coverage,
)


def resolve_user(db, *, user_id: str | None, email: str | None) -> User:
    query = db.query(User)
    if user_id:
        return query.filter(User.id == UUID(str(user_id))).one()
    if email:
        return query.filter(User.email == email).one()
    raise SystemExit("Pass --user-id or --email: coverage is per learner, never global.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id")
    parser.add_argument("--email")
    parser.add_argument("--limit", type=int, default=14, help="Scenes to look back over.")
    parser.add_argument(
        "--stored-only",
        action="store_true",
        help="Report only scenes the generator measured; never recompute.",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = parser.parse_args()

    with SessionLocal() as db:
        user = resolve_user(db, user_id=args.user_id, email=args.email)
        known = known_word_set(db, user=user)
        rows = recent_scene_coverage(
            db,
            user=user,
            limit=args.limit,
            recompute=not args.stored_only,
            resolver=default_resolver(),
        )

    stats = coverage_distribution(rows)
    if args.json:
        print(
            json.dumps(
                {
                    "user_id": str(user.id),
                    "known": known.as_dict(),
                    "lexicon": load_lexicon().version,
                    "distribution": stats,
                    "scenes": [row.as_dict() for row in rows],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"Learner {user.id} · band {known.band} (estimate {known.estimate_level}, "
          f"source {known.estimate_source})")
    print(f"Known-word set: {len(known.lemmas)} lemmas "
          f"({known.nailed_count} nailed by FSRS, {known.core_count} core-list assumed) · "
          f"lexicon {load_lexicon().version}")
    print(f"Accidental-unknown budget at {known.band}: "
          f"{accidental_budget(known.band)} (all bands: {ACCIDENTAL_UNKNOWN_BUDGET})")
    print("")

    if stats.get("status") == "insufficient_data":
        # A distribution over zero scenes is not "0 % coverage"; it is no data.
        print("No scenes with measurable text. Nothing to report — this is not a zero.")
        return

    print(f"{'created':<12} {'cov':>7} {'acc':>4} {'tgt':>4}  origin      title")
    for row in rows:
        created = row.created_at.date().isoformat() if row.created_at else "unknown"
        print(
            f"{created:<12} {row.coverage * 100:6.1f}% {row.accidental_count:>4} "
            f"{row.target_count:>4}  {row.origin:<11} {row.title[:40]}"
        )
        if row.accidental:
            print(f"{'':<12} accidental: {', '.join(row.accidental)}")
    print("")
    print(
        f"{stats['scenes']} scene(s) · median {stats['median'] * 100:.1f}% · "
        f"min {stats['min'] * 100:.1f}% · max {stats['max'] * 100:.1f}%"
    )
    print(
        f"At the {SUPPORTED_COVERAGE_FLOOR * 100:.0f}% supported floor: "
        f"{stats['at_supported_floor']}/{stats['scenes']} · "
        f"at the {UNASSISTED_COVERAGE_FLOOR * 100:.0f}% unassisted floor: "
        f"{stats['at_unassisted_floor']}/{stats['scenes']}"
    )
    print(f"Measured at generation: {stats['stored']} · recomputed here: {stats['recomputed']}")
    if stats["recomputed"]:
        print(
            "Recomputed rows use today's known-word set, not the learner's set on the day. "
            "They become 'stored' once the WP-29 hook lands in living_story.py."
        )


if __name__ == "__main__":
    main()
