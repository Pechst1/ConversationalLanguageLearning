"""Backfill Feuilleton panel image data URIs into configured image storage."""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO

from app.config import settings
from app.db.models.graphic_novel import GraphicNovelPanel
from app.db.session import SessionLocal
from app.services.graphic_novel_image_storage import GraphicNovelImageStorage, is_data_uri
from sqlalchemy import select, update


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite GraphicNovelPanel image data URIs to configured storage URLs."
    )
    parser.add_argument("--dry-run", action="store_true", help="Report candidate rows without changing the database.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of candidate panels to process.")
    parser.add_argument(
        "--storage",
        choices=("local", "s3"),
        default=None,
        help="Override GRAPHIC_NOVEL_IMAGE_STORAGE for this run.",
    )
    parser.add_argument(
        "--backup-jsonl",
        type=Path,
        default=None,
        help="Path for a JSONL backup of original image_url/image_payload.url values before rewrite.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not write a JSONL backup when applying changes.",
    )
    return parser.parse_args()


def _default_backup_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("var") / "graphic-novel-image-backfills" / f"{stamp}.jsonl"


def _open_backup(args: argparse.Namespace) -> TextIO | None:
    if args.dry_run or args.no_backup:
        return None
    path = args.backup_jsonl or _default_backup_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")


def _write_backup(handle: TextIO | None, panel: Mapping[str, Any], payload: dict) -> None:
    if handle is None:
        return
    handle.write(
        json.dumps(
            {
                "panel_id": str(panel["id"]),
                "scene_id": str(panel["scene_id"]),
                "panel_index": panel["panel_index"],
                "image_url": panel["image_url"],
                "image_payload_url": payload.get("url"),
            },
            ensure_ascii=False,
        )
        + "\n"
    )


async def _run() -> int:
    args = _parse_args()
    if args.storage:
        setattr(settings, "GRAPHIC_NOVEL_IMAGE_STORAGE", args.storage)
    if settings.GRAPHIC_NOVEL_IMAGE_STORAGE == "data_uri" and not args.dry_run:
        raise SystemExit(
            "Refusing to apply with GRAPHIC_NOVEL_IMAGE_STORAGE=data_uri. "
            "Set GRAPHIC_NOVEL_IMAGE_STORAGE=local|s3 or pass --storage."
        )

    db = SessionLocal()
    backup = _open_backup(args)
    storage = GraphicNovelImageStorage()
    scanned = 0
    migrated = 0
    skipped = 0
    try:
        panels = GraphicNovelPanel.__table__
        query = (
            select(
                panels.c.id,
                panels.c.scene_id,
                panels.c.panel_index,
                panels.c.image_url,
                panels.c.image_payload,
            )
            .where(panels.c.image_url.like("data:%"))
            .order_by(panels.c.scene_id, panels.c.panel_index)
        )
        if args.limit:
            query = query.limit(args.limit)
        for row in db.execute(query):
            panel = row._mapping
            scanned += 1
            payload = dict(panel["image_payload"] or {})
            source_url = panel["image_url"] or payload.get("url")
            if not is_data_uri(source_url):
                skipped += 1
                continue
            payload["url"] = source_url
            if args.dry_run:
                print(f"DRY-RUN panel={panel['id']} scene={panel['scene_id']} index={panel['panel_index']}")
                migrated += 1
                continue

            stored = await storage.persist_payload(
                payload,
                scene_id=panel["scene_id"],
                panel_index=panel["panel_index"],
                image_role="panel",
            )
            stored_url = stored.get("url")
            if not isinstance(stored_url, str) or is_data_uri(stored_url):
                skipped += 1
                continue
            _write_backup(backup, panel, payload)
            db.execute(
                update(panels)
                .where(panels.c.id == panel["id"])
                .values(image_url=stored_url, image_payload=stored)
            )
            migrated += 1
            if migrated % 50 == 0:
                db.commit()
        if not args.dry_run:
            db.commit()
    finally:
        if backup is not None:
            backup.close()
        db.close()

    action = "would migrate" if args.dry_run else "migrated"
    print(f"Scanned {scanned} data-URI panel(s); {action} {migrated}; skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
