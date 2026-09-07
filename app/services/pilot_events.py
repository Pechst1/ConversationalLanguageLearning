"""Trusted instrumentation and one-day pilot reporting."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models.atelier import AtelierGenerationEvent
from app.db.models.graphic_novel import GraphicNovelScene
from app.db.models.pilot_event import PilotEvent
from app.db.models.serial import SerialEpisode, SerialThread
from app.services.serial_costs import serial_generation_cost_event

#: Events that mean "something went wrong", counted in the ``failures`` total.
#: The two journey entries are infrastructure failures (WP-11), never learner
#: mistakes.
_FAILURE_EVENT_TYPES = frozenset(
    {
        "client_crash",
        "generation_fallback",
        "episode_delayed",
        "journey_generation_fallback",
        "journey_provider_failed",
    }
)


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    local_tz = ZoneInfo("Europe/Berlin")
    start_local = datetime.combine(day, time.min, tzinfo=local_tz)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=local_tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


class PilotEventService:
    """Write slim events and produce the answer to “what happened yesterday?”."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None,
        entity_type: str | None = None,
        entity_id: str | UUID | int | None = None,
        payload: dict[str, Any] | None = None,
        cost_usd: float = 0.0,
        occurred_at: datetime | None = None,
    ) -> PilotEvent:
        event = PilotEvent(
            user_id=user_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            payload=payload or {},
            cost_usd=max(0.0, float(cost_usd or 0.0)),
        )
        if occurred_at is not None:
            # WP-11: the column's ``func.now()`` default is the *transaction*
            # clock in PostgreSQL, so every row written inside one transaction
            # would share an instant. Duration measurement needs the real one.
            event.occurred_at = occurred_at
        self.db.add(event)
        return event

    def daily_rollup(
        self,
        day: date,
        *,
        user_id: UUID | str | None = None,
    ) -> dict[str, Any]:
        start, end = _day_bounds(day)
        event_query = self.db.query(PilotEvent).filter(
            PilotEvent.occurred_at >= start,
            PilotEvent.occurred_at < end,
        )
        scene_query = (
            self.db.query(GraphicNovelScene)
            .options(joinedload(GraphicNovelScene.panels), joinedload(GraphicNovelScene.user))
            .filter(
                GraphicNovelScene.serial_thread_id.isnot(None),
                GraphicNovelScene.created_at >= start,
                GraphicNovelScene.created_at < end,
            )
        )
        if user_id:
            normalized_user_id = UUID(str(user_id))
            event_query = event_query.filter(PilotEvent.user_id == normalized_user_id)
            scene_query = scene_query.filter(GraphicNovelScene.user_id == normalized_user_id)

        events = event_query.order_by(PilotEvent.occurred_at).all()
        scenes = scene_query.order_by(GraphicNovelScene.created_at).all()
        users: dict[str, dict[str, Any]] = {}

        def bucket(uid: str, email: str | None = None) -> dict[str, Any]:
            return users.setdefault(
                uid,
                {
                    "user_id": uid,
                    "user_email": email,
                    "events": Counter(),
                    "event_count": 0,
                    "serial_scenes": 0,
                    "story_usd": 0.0,
                    "image_usd": 0.0,
                    "audio_usd": 0.0,
                    "other_llm_usd": 0.0,
                    "total_usd": 0.0,
                    "failures": 0,
                },
            )

        for event in events:
            uid = str(event.user_id or "system")
            row = bucket(uid, getattr(event.user, "email", None) if event.user else None)
            row["events"][event.event_type] += 1
            row["event_count"] += 1
            row["other_llm_usd"] += float(event.cost_usd or 0.0)
            row["total_usd"] += float(event.cost_usd or 0.0)
            if event.event_type in _FAILURE_EVENT_TYPES:
                row["failures"] += 1

        for scene in scenes:
            cost = serial_generation_cost_event(scene)
            uid = str(scene.user_id)
            row = bucket(uid, getattr(scene.user, "email", None))
            row["serial_scenes"] += 1
            for field in ("story_usd", "image_usd", "audio_usd", "total_usd"):
                row[field] += float(cost[field] or 0.0)

        fallback_rows = (
            self.db.query(AtelierGenerationEvent.user_id, func.count(AtelierGenerationEvent.id))
            .filter(
                AtelierGenerationEvent.created_at >= start,
                AtelierGenerationEvent.created_at < end,
                AtelierGenerationEvent.source == "fallback",
            )
        )
        delayed_rows = (
            self.db.query(SerialThread.user_id, func.count(SerialEpisode.id))
            .join(SerialThread, SerialThread.id == SerialEpisode.thread_id)
            .filter(
                SerialEpisode.created_at >= start,
                SerialEpisode.created_at < end,
                SerialEpisode.status == "delayed",
            )
        )
        if user_id:
            normalized_user_id = UUID(str(user_id))
            fallback_rows = fallback_rows.filter(AtelierGenerationEvent.user_id == normalized_user_id)
            delayed_rows = delayed_rows.filter(SerialThread.user_id == normalized_user_id)
        for uid, count in fallback_rows.group_by(AtelierGenerationEvent.user_id).all():
            bucket(str(uid or "system"))["failures"] += int(count)
        for uid, count in delayed_rows.group_by(SerialThread.user_id).all():
            bucket(str(uid or "system"))["failures"] += int(count)

        rows: list[dict[str, Any]] = []
        for row in users.values():
            row["events"] = dict(sorted(row["events"].items()))
            for field in ("story_usd", "image_usd", "audio_usd", "other_llm_usd", "total_usd"):
                row[field] = round(float(row[field]), 6)
            rows.append(row)
        rows.sort(key=lambda value: (value["user_email"] or value["user_id"]))
        # WP-11: additive section. Existing keys keep their exact meaning, so
        # every non-journey pilot report continues to read the same numbers.
        from app.services.journey_events import journey_daily_rollup

        journey_section = journey_daily_rollup(self.db, day, user_id=user_id)
        return {
            "day": day.isoformat(),
            "currency": "USD",
            "users": rows,
            "journey": journey_section,
            "totals": {
                "learners": len([row for row in rows if row["user_id"] != "system"]),
                "events": sum(row["event_count"] for row in rows),
                "failures": sum(row["failures"] for row in rows),
                "cost_usd": round(sum(row["total_usd"] for row in rows), 6),
            },
        }


def format_daily_digest(report: dict[str, Any]) -> str:
    """Format a rollup for terminal/email use without optional dependencies."""
    lines = [
        f"Pilot digest · {report['day']}",
        f"Learners {report['totals']['learners']} · events {report['totals']['events']} · "
        f"failures {report['totals']['failures']} · cost ${report['totals']['cost_usd']:.4f}",
    ]
    for row in report["users"]:
        activity = ", ".join(f"{name}:{count}" for name, count in row["events"].items()) or "no events"
        lines.append(
            f"- {row['user_email'] or row['user_id']}: ${row['total_usd']:.4f}; "
            f"failures {row['failures']}; {activity}"
        )
    journey_section = report.get("journey")
    if journey_section:
        from app.services.journey_events import format_journey_digest

        lines.extend(format_journey_digest(journey_section))
    return "\n".join(lines)


__all__ = ["PilotEventService", "format_daily_digest"]
