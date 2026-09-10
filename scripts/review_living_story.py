"""Opt-in live prose review using synthetic context, with no database connection.

Run from the repository root with: python -m scripts.review_living_story --live
--output /tmp/atelier-story-review.json. Without --live no provider is constructed.
This is a quality sample, not a substitute for the API/transaction integration tests.
"""

from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--attempts",
        type=int,
        default=1,
        choices=(1, 2, 3),
        help="Draft/turn attempts per stage (production uses ATELIER_STORY_MAX_ATTEMPTS=2).",
    )
    parser.add_argument(
        "--max-requests", type=int, default=12, help="Hard cap on paid requests for this run."
    )
    parser.add_argument(
        "--level",
        default="A1",
        choices=("A1", "A2", "B1"),
        help=(
            "CEFR band to review. Register and the cast projection both depend on it, so a "
            "single band says nothing about the others."
        ),
    )
    parser.add_argument(
        "--days", type=int, default=3, help="Synthetic days to walk (scene + reply each)."
    )
    parser.add_argument(
        "--output", type=Path, default=Path("var/reviews/atelier-story-review.json")
    )
    args = parser.parse_args()
    if not args.live:
        print(
            "No requests made. --live runs at most --max-requests (default 12) model requests "
            "for three synthetic scenes and replies. No application database is used."
        )
        return

    from app.config import settings
    from app.db import models  # noqa: F401 — register model relationships for the event sink
    from app.services import living_story as engine
    from app.services.serial import SerialThreadService

    report = {
        "version": engine.VERSION,
        "synthetic_only": True,
        "level": args.level,
        "attempts": args.attempts,
        "requests": [],
        "scenes": [],
    }

    class EventSink:
        def add(self, event):
            pass  # This review never persists telemetry to the application database.

    real_client = engine._client
    calls = 0
    max_requests = args.max_requests

    class BoundedClient:
        def generate_chat_completion(self, *args, **kwargs):
            nonlocal calls
            if calls >= max_requests:
                raise engine.StoryUnavailable("review_request_limit")
            calls += 1
            started = time.monotonic()
            result = real_client().generate_chat_completion(*args, **kwargs)
            report["requests"].append(
                {
                    "model": result.model,
                    "provider": result.provider,
                    "tokens": result.total_tokens,
                    "estimated_cost_usd": result.cost,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                }
            )
            return result

    settings.ATELIER_LLM_ENABLED = True  # This process only; no persisted flags change.
    settings.ATELIER_STORY_MAX_ATTEMPTS = args.attempts
    engine._client = lambda: BoundedClient()
    world = SerialThreadService._load_world_bible()
    context = {
        "thread_id": "synthetic-review",
        "revision": "synthetic",
        "control_language": "en",
        "level": args.level,
        # Below B1 the cast projection carries no coarse vocabulary (WP-17 register).
        "level_register": (
            "no coarse or vulgar vocabulary"
            if args.level in {"A1", "A2"}
            else "mild colloquial register allowed, never coarse"
        ),
        "world": {
            "logline": world.get("logline"),
            "cast": engine._cast_for_level(
                [
                    {
                        k: c.get(k)
                        for k in (
                            "id",
                            "name",
                            "role",
                            "personality",
                            "wants",
                            "speech_pattern",
                            "register_with_user",
                            "gender",
                        )
                    }
                    for c in world["cast"]
                ],
                args.level,
            ),
            "locations": engine._locations(world),
        },
        "story_so_far": [],
        "relationships": {},
        "chapter": None,
        "resolved_chapter_questions": [],
        "variety": {},
        "events": [],
        "commitments": [],
        "recent_situations": [],
        "legacy_beat": None,
    }
    try:
        for day in range(args.days):
            scene, _ = engine._approved(
                engine.DIRECTOR,
                context,
                engine.SceneDraft,
                lambda value: engine._validate_scene(value, context),
                db=EventSink(),
                user=SimpleNamespace(id=uuid4()),
            )
            text = (
                scene.suggested_response_fr
                if day != 1
                else "Non, je ne peux pas vous aider aujourd'hui. Je préfère rentrer chez moi."
            )
            payload = {
                "story": deepcopy(context),
                "scene": scene.model_dump(mode="json"),
                "rubric": scene.objective_semantics,
                "learner_text": text,
                "history": [],
                "turns_left": 2,
                "targets": [],
                "assistance": "suggestion" if day != 1 else "none",
            }
            # Match the production actor's knowledge boundary.
            payload["story"]["events"] = [
                e for e in context["events"] if scene.character_id in e["witnesses"]
            ]
            payload["story"]["story_so_far"] = [e["summary_fr"] for e in payload["story"]["events"]]
            payload["story"]["recent_situations"] = []
            payload["story"]["commitments"] = [
                c for c in context["commitments"] if scene.character_id in c["witnesses"]
            ]
            result, _ = engine._approved(
                engine.ACTOR,
                payload,
                engine.SemanticTurn,
                lambda value, source=payload: engine._validate_turn(value, source),
                db=EventSink(),
                user=SimpleNamespace(id=uuid4()),
            )
            report["scenes"].append(
                {
                    "day": day + 1,
                    "scene": scene.model_dump(mode="json"),
                    "learner_text": text,
                    "turn": result.model_dump(mode="json"),
                }
            )
            event_id = f"synthetic:{day}"
            witnesses = sorted(
                {
                    scene.character_id,
                    *[line.character_id for panel in scene.panels for line in panel.dialogue],
                }
            )
            context["events"].append(
                {
                    "id": event_id,
                    "summary_fr": result.callback_fr or result.resolution_fr,
                    "witnesses": witnesses,
                }
            )
            context["story_so_far"].append(result.callback_fr)
            context["recent_situations"].append(
                {
                    "novelty_key": scene.novelty_key,
                    "premise_fr": scene.premise_fr,
                    "objective_native": scene.objective_native,
                    "character_id": scene.character_id,
                    "location_id": scene.location_id,
                }
            )
            if result.chapter_resolved:
                context["resolved_chapter_questions"].append(scene.chapter.dramatic_question)
            context["chapter"] = {**scene.chapter.model_dump(), "resolved": result.chapter_resolved}
            context["variety"] = engine._variety(
                context["recent_situations"],
                context["world"]["cast"],
                context["world"]["locations"],
            )
            for i, commitment in enumerate(result.commitments):
                context["commitments"].append(
                    {
                        "id": f"{event_id}:{i}",
                        **commitment.model_dump(),
                        "status": "open",
                        "witnesses": witnesses,
                    }
                )
            print(
                f"Synthetic scene {day + 1}: accepted; {calls}/{args.max_requests} requests used.",
                flush=True,
            )
        report["status"] = "sample_ready_for_human_review"
    except engine.StoryUnavailable as exc:
        report["status"] = "rejected_or_unavailable"
        report["reason"] = str(exc)
    finally:
        report["attempted_requests"] = calls
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{report['status']}: {args.output}")


if __name__ == "__main__":
    main()
