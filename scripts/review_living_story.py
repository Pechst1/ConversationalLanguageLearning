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
                    # The content is the whole point of a prose review: without it a
                    # rejected day records a verdict with nothing to judge it against,
                    # and the run has to be paid for twice to see what was said.
                    "content": result.content,
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
            "cast": engine._cast_for_level(engine._cast_projection(world), args.level),
            "locations": engine._locations(world),
            **engine._season_projection(world, {}),
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
    arc_progress: dict = {}
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
                # A refusal that fits any scene (a romantic walk as much as a favour):
                # the earlier "vous aider" wording was itself off-scene and made the
                # critic reject the turn for the wrong reason (live run 2026-09-19d).
                else "Non, pas aujourd'hui, désolé. Je préfère rentrer chez moi."
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
            try:
                result, _ = engine._approved(
                    engine.ACTOR,
                    payload,
                    engine.SemanticTurn,
                    lambda value, source=payload: engine._validate_turn(value, source),
                    db=EventSink(),
                    user=SimpleNamespace(id=uuid4()),
                )
                reply_source = "model"
            except engine.StoryUnavailable as exc:
                # What production does (WP-58): an honest authored ending, never a
                # dead day. Recorded as such so the reviewer can count them.
                character = next(
                    (c for c in context["world"]["cast"] if c["id"] == scene.character_id), {}
                )
                result = engine.fallback_turn(
                    character_name=character.get("name"),
                    learner_text=text,
                    language=context["control_language"],
                    reason=str(exc),
                )
                reply_source = f"authored:{exc}"
            report["scenes"].append(
                {
                    "day": day + 1,
                    "chapter_before": context["chapter"],
                    "scene": scene.model_dump(mode="json"),
                    "learner_text": text,
                    "reply_source": reply_source,
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
                    "beat": scene.beat,
                    "problem_key": scene.problem_key,
                }
            )
            # The same chapter bookkeeping production runs (WP-58): open on setup,
            # advance per scene, close on the resolution beat, retire the question.
            current = context["chapter"]
            if not current or current.get("resolved") or current.get("exhausted"):
                current = engine.open_chapter(scene)
            current = engine.chapter_after_scene(current, scene, result, event_id)
            if current.get("resolved"):
                context["resolved_chapter_questions"].append(current["dramatic_question"])
            arc_progress = engine.arc_progress_after_scene(
                arc_progress, current, world.get("season_arcs") or [], event_id
            )
            context["world"].update(engine._season_projection(world, arc_progress))
            context["chapter"] = engine.chapter_state({"chapter": current})
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
