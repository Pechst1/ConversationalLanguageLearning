#!/usr/bin/env python3
"""Red-thread design, slice 5: the pool of shared pages, for the owner.

``list`` and ``show`` only read. ``retire`` takes a page out of the pool for every
learner who has not read it yet (the row stays); the next learner on that day gets
a newly written page.

Usage::

    .venv/bin/python scripts/story_pool.py list [--day g3:les_canapes] [--all]
    .venv/bin/python scripts/story_pool.py show <page id>
    .venv/bin/python scripts/story_pool.py retire <page id> --reason "weak ending"
"""
from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from app.db.models.story_pool import StoryPoolPage
from app.db.session import SessionLocal
from app.services.season import page_pool


def _page_text(draft: dict) -> str:
    lines = [f"# {draft.get('title_fr')}", str(draft.get("premise_fr") or ""), ""]
    for panel in draft.get("panels") or []:
        if panel.get("narration_fr"):
            lines.append(str(panel["narration_fr"]))
        for line in panel.get("dialogue") or []:
            lines.append(f"  {line.get('character_id')}: {line.get('text_fr')}")
    lines += ["", f"→ {draft.get('opening_line_fr')}", f"({draft.get('objective_native')})"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--day", help="<gap>:<premise>, e.g. g3:les_canapes")
    listing.add_argument("--all", action="store_true", help="include retired pages")
    commands.add_parser("show").add_argument("page")
    retiring = commands.add_parser("retire")
    retiring.add_argument("page")
    retiring.add_argument("--reason", default="")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.command == "list":
            query = select(StoryPoolPage).order_by(StoryPoolPage.day_key, StoryPoolPage.band, StoryPoolPage.created_at)
            if args.day:
                query = query.where(StoryPoolPage.day_key == args.day)
            if not args.all:
                query = query.where(StoryPoolPage.retired_at.is_(None))
            for row in db.scalars(query):
                state = f"retired ({row.retired_reason or '-'})" if row.retired_at else "live"
                print(
                    f"{row.id}  {row.day_key:<28} {row.band:<3} {row.language:<3} served {row.served:>4}  "
                    f"${row.cost_usd:.2f}  {state}  «{(row.draft or {}).get('title_fr')}»"
                )
        elif args.command == "show":
            row = db.get(StoryPoolPage, uuid.UUID(args.page))
            print(_page_text(row.draft) if row else "no such page")
        else:
            done = page_pool.retire(db, uuid.UUID(args.page), reason=args.reason)
            db.commit()
            print("retired" if done else "no such live page")
    finally:
        db.close()


if __name__ == "__main__":
    main()
