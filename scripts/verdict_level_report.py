#!/usr/bin/env python3
"""Package V stage 1: what a re-judge of old rows would change, per learner. Reads only.

The verdict stack ships with ``VERDICT_LEGACY_ROWS=as_counted``: a row stored before the
cut-over (the ``verdict_cutover`` row the migration writes) keeps what it counted for, so
the deploy moves no level, gold or token. This report is for the owner's decision (package
V, owner decision 1): if old rows were read the new way instead (``rejudge``), what would
move for each learner?

Per learner, for rows stored before the cut-over:

* ``level``: attempts in the last 14 days that feed the level average (Forge, Courrier,
  Feuilleton), as counted and as re-judged, and the two averages;
* ``letters``: finished Courrier letters whose gold or token a re-judge would hold back
  (an unread message, a rules-only first attempt), and the gold those letters were paid.
  Gold already paid is never taken back by ``rejudge``: that would be the ledger's
  supersede (package V stage 2). This only says how much was paid on such letters.

Nothing is written: the session is rolled back and never committed.

Usage::

    .venv/bin/python scripts/verdict_level_report.py
    .venv/bin/python scripts/verdict_level_report.py --email a@b.c --json
    .venv/bin/python scripts/verdict_level_report.py --all-rows   # no cut-over row yet: read every row
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models.atelier import AtelierAttempt  # noqa: E402
from app.db.models.gold import GoldLedgerEntry  # noqa: E402
from app.db.models.graphic_novel import GraphicNovelAttempt  # noqa: E402
from app.db.models.mission import RealWorldMission, RealWorldMissionAttempt, RealWorldMissionTurn  # noqa: E402
from app.db.models.user import User  # noqa: E402
from app.services import verdicts  # noqa: E402
from app.services.missions import unanswered_user_turns, unchecked_messages  # noqa: E402
from app.services.verdict_cutover import AS_COUNTED, Cutover, cutover  # noqa: E402

LEVEL_READS = (
    ("forge", AtelierAttempt, lambda row: verdicts.from_forge(row.correction_payload, verdict=row.verdict)),
    ("courrier", RealWorldMissionAttempt, lambda row: verdicts.from_courrier(row.correction_payload, verdict=row.verdict)),
    ("feuilleton", GraphicNovelAttempt, lambda row: verdicts.from_feuilleton(row.correction_payload, verdict=row.verdict)),
)


def _average(scores: list[float]) -> float | None:
    return round(sum(scores) / len(scores), 3) if scores else None


def report(db: Session, *, user_ids: set[Any] | None = None, all_rows: bool = False, now: datetime | None = None) -> list[dict[str, Any]]:
    """One entry per learner with a legacy row a re-judge would read differently."""

    now = now or datetime.now(UTC)
    cut = Cutover(now, AS_COUNTED) if all_rows else cutover(db)
    if cut.at is None:
        return []
    start_14 = now - timedelta(days=14)
    out: dict[Any, dict[str, Any]] = defaultdict(
        lambda: {"level": {}, "letters": {"held_back": 0, "gold_paid_on_them": 0, "mission_ids": []}}
    )

    for surface, model, read in LEVEL_READS:
        query = select(model).where(model.created_at < cut.at)
        if user_ids:
            query = query.where(model.user_id.in_(user_ids))
        for row in db.scalars(query):
            if not cut.keeps(row):
                continue
            entry = out[row.user_id]["level"].setdefault(
                surface, {"rows": 0, "rejudged_not_counting": 0, "scores_14d": [], "rejudged_scores_14d": []}
            )
            entry["rows"] += 1
            counts = read(row).counts
            if not counts:
                entry["rejudged_not_counting"] += 1
            created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
            if created >= start_14:
                entry["scores_14d"].append(float(row.score_0_4 or 0.0))
                if counts:
                    entry["rejudged_scores_14d"].append(float(row.score_0_4 or 0.0))

    letters = select(RealWorldMission).where(RealWorldMission.status == "completed")
    if user_ids:
        letters = letters.where(RealWorldMission.user_id.in_(user_ids))
    for mission in db.scalars(letters):
        attempts = list(
            db.scalars(select(RealWorldMissionAttempt).where(RealWorldMissionAttempt.mission_id == mission.id))
        )
        turns = list(db.scalars(select(RealWorldMissionTurn).where(RealWorldMissionTurn.mission_id == mission.id)))
        rows = [*attempts, *turns]
        if not rows or not all(cut.keeps(row) for row in rows):
            continue
        if not (unchecked_messages(attempts, turns) or unanswered_user_turns(turns)):
            continue
        paid = db.scalars(
            select(GoldLedgerEntry).where(GoldLedgerEntry.source_key == f"gold:letter:{mission.id}")
        ).all()
        letter = out[mission.user_id]["letters"]
        letter["held_back"] += 1
        letter["gold_paid_on_them"] += sum(int(entry.amount or 0) for entry in paid)
        letter["mission_ids"].append(str(mission.id))

    results = []
    for user_id, entry in out.items():
        moved = any(level["rejudged_not_counting"] for level in entry["level"].values()) or entry["letters"]["held_back"]
        if not moved:
            continue
        counted = [score for level in entry["level"].values() for score in level["scores_14d"]]
        rejudged = [score for level in entry["level"].values() for score in level["rejudged_scores_14d"]]
        user = db.get(User, user_id)
        results.append(
            {
                "user_id": str(user_id),
                "email": getattr(user, "email", None),
                "level": {
                    surface: {"rows": level["rows"], "rejudged_not_counting": level["rejudged_not_counting"]}
                    for surface, level in entry["level"].items()
                },
                "average_14d": {"as_counted": _average(counted), "rejudged": _average(rejudged)},
                "attempts_14d": {"as_counted": len(counted), "rejudged": len(rejudged)},
                "letters": entry["letters"],
            }
        )
    return sorted(results, key=lambda item: item["email"] or item["user_id"])


def _print(results: list[dict[str, Any]], cut_at: Any) -> None:
    print(f"Cut-over: {cut_at}. Learners a re-judge of old rows would move: {len(results)}")
    for item in results:
        avg = item["average_14d"]
        print(f"\n{item['email'] or item['user_id']}")
        for surface, level in item["level"].items():
            print(f"  {surface:<11} {level['rows']:>4} old rows, {level['rejudged_not_counting']:>4} would stop counting")
        print(
            f"  14-day average {avg['as_counted']} over {item['attempts_14d']['as_counted']} attempts"
            f" -> {avg['rejudged']} over {item['attempts_14d']['rejudged']}"
        )
        letters = item["letters"]
        if letters["held_back"]:
            print(f"  letters a re-judge would hold back: {letters['held_back']} (gold paid on them: {letters['gold_paid_on_them']})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", action="append", default=[], help="only this learner (repeatable)")
    parser.add_argument("--all-rows", action="store_true", help="treat every stored row as old (before the migration ran)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        user_ids = None
        if args.email:
            user_ids = set(db.scalars(select(User.id).where(User.email.in_(args.email))))
        results = report(db, user_ids=user_ids, all_rows=args.all_rows)
        cut_at = "every row (--all-rows)" if args.all_rows else cutover(db).at
        if args.json:
            print(json.dumps({"cutover": str(cut_at), "learners": results}, indent=2, ensure_ascii=False))
        else:
            _print(results, cut_at)
    finally:
        db.rollback()
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
