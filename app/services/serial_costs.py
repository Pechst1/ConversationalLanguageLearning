"""Cost observability for Serial Feuilleton generation."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.graphic_novel import GraphicNovelScene


def _float_or(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_or(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _utc_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def serial_generation_cost_event(scene: GraphicNovelScene) -> dict[str, Any]:
    """Return the structured cost payload persisted for one serial generation."""
    script = scene.script_payload if isinstance(scene.script_payload, dict) else {}
    cost = script.get("estimated_cost") if isinstance(script.get("estimated_cost"), dict) else {}
    panel_count = _int_or(cost.get("panel_count"), _int_or(script.get("panel_count"), len(scene.panels or [])))
    image_count = _int_or(cost.get("image_units"), panel_count)
    story_usd = _float_or(cost.get("story_generation_usd"))
    image_usd = _float_or(cost.get("image_generation_usd"))
    total_usd = _float_or(cost.get("total_estimated_usd"), story_usd + image_usd)
    return {
        "scene_id": str(scene.id),
        "serial_thread_id": str(scene.serial_thread_id) if scene.serial_thread_id else None,
        "user_id": str(scene.user_id),
        "episode_index": scene.episode_index,
        "story_usd": round(story_usd, 6),
        "image_usd": round(image_usd, 6),
        "total_usd": round(total_usd, 6),
        "image_count": image_count,
        "panel_count": panel_count,
        "image_quality": cost.get("image_quality") or scene.image_quality,
        "render_mode": cost.get("render_mode") or script.get("render_mode"),
        "currency": cost.get("currency") or "USD",
        "basis": cost.get("basis") or "",
    }


class SerialGenerationCostService:
    """Aggregate persisted serial generation estimates by learner and ISO week."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def weekly_rollup(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        user_id: UUID | str | None = None,
    ) -> list[dict[str, Any]]:
        """Return weekly learner spend from serial scene cost metadata.

        Date filters are inclusive start and exclusive end.
        """
        query = self.db.query(GraphicNovelScene).filter(GraphicNovelScene.serial_thread_id.isnot(None))
        if start_date:
            query = query.filter(GraphicNovelScene.created_at >= _utc_start(start_date))
        if end_date:
            query = query.filter(GraphicNovelScene.created_at < _utc_start(end_date))
        if user_id:
            query = query.filter(GraphicNovelScene.user_id == UUID(str(user_id)))

        buckets: dict[tuple[str, int, int], dict[str, Any]] = {}
        for scene in query.order_by(GraphicNovelScene.created_at.asc()).all():
            created_at = scene.created_at or datetime.now(timezone.utc)
            created_day = created_at.date()
            iso = created_day.isocalendar()
            event = serial_generation_cost_event(scene)
            key = (event["user_id"], iso.year, iso.week)
            row = buckets.setdefault(
                key,
                {
                    "user_id": event["user_id"],
                    "user_email": getattr(scene.user, "email", None),
                    "iso_year": iso.year,
                    "iso_week": iso.week,
                    "week_start": _week_start(created_day).isoformat(),
                    "scene_count": 0,
                    "episode_count": 0,
                    "episodes": set(),
                    "story_usd": 0.0,
                    "image_usd": 0.0,
                    "total_usd": 0.0,
                    "image_count": 0,
                    "image_quality_breakdown": {},
                },
            )
            row["scene_count"] += 1
            if event["episode_index"] is not None:
                row["episodes"].add(int(event["episode_index"]))
            row["story_usd"] += event["story_usd"]
            row["image_usd"] += event["image_usd"]
            row["total_usd"] += event["total_usd"]
            row["image_count"] += event["image_count"]
            quality = str(event.get("image_quality") or "unknown")
            row["image_quality_breakdown"][quality] = row["image_quality_breakdown"].get(quality, 0) + 1

        rows: list[dict[str, Any]] = []
        for row in buckets.values():
            episodes = sorted(row["episodes"])
            row["episodes"] = episodes
            row["episode_count"] = len(episodes)
            row["story_usd"] = round(row["story_usd"], 6)
            row["image_usd"] = round(row["image_usd"], 6)
            row["total_usd"] = round(row["total_usd"], 6)
            rows.append(row)
        return sorted(rows, key=lambda item: (item["week_start"], item["user_email"] or item["user_id"]))


def format_rollup_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No serial generation cost rows found."
    headers = ["week", "learner", "scenes", "episodes", "story_usd", "image_usd", "total_usd", "images", "quality"]
    table_rows: list[list[str]] = []
    for row in rows:
        quality = ", ".join(f"{key}:{value}" for key, value in sorted((row.get("image_quality_breakdown") or {}).items()))
        table_rows.append(
            [
                str(row.get("week_start") or ""),
                str(row.get("user_email") or row.get("user_id") or ""),
                str(row.get("scene_count") or 0),
                str(row.get("episode_count") or 0),
                f"{float(row.get('story_usd') or 0.0):.6f}",
                f"{float(row.get('image_usd') or 0.0):.6f}",
                f"{float(row.get('total_usd') or 0.0):.6f}",
                str(row.get("image_count") or 0),
                quality,
            ]
        )
    widths = [len(header) for header in headers]
    for row in table_rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row, strict=True)]
    lines = ["  ".join(value.ljust(width) for value, width in zip(headers, widths, strict=True))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend("  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)) for row in table_rows)
    return "\n".join(lines)


__all__ = ["SerialGenerationCostService", "format_rollup_table", "serial_generation_cost_event"]
