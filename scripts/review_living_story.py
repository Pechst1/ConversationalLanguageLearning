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


def _p(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))], 2)


def lane_latency(report: dict) -> dict:
    """WP-87: seconds per schema (lane) and for the reply phase the learner waits on."""

    per_schema: dict[str, list[float]] = {}
    for request in report.get("requests") or []:
        if request.get("content") and request.get("elapsed_seconds") is not None:
            per_schema.setdefault(str(request.get("schema")), []).append(request["elapsed_seconds"])
    summary = {
        schema: {"n": len(values), "p50": _p(values, 0.5), "p90": _p(values, 0.9), "max": max(values)}
        for schema, values in sorted(per_schema.items())
    }
    for key in ("reply_phase_seconds", "story_lane_seconds"):
        values = [scene[key] for scene in report.get("scenes") or [] if scene.get(key) is not None]
        if values:
            summary[key] = {"n": len(values), "p50": _p(values, 0.5), "max": max(values)}
    return summary


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
        choices=("A1", "A2", "B1", "B2", "C1"),
        help=(
            "CEFR band to review. Register and the cast projection both depend on it, so a "
            "single band says nothing about the others."
        ),
    )
    parser.add_argument(
        "--days", type=int, default=3, help="Synthetic days to walk (scene + reply each)."
    )
    parser.add_argument(
        "--seed",
        default="synthetic-review",
        help="Per-learner dice (WP-59): the arc order and the complication cards this life is dealt.",
    )
    parser.add_argument(
        "--lanes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "WP-87: play each turn as production does with ATELIER_STORY_TURN_LANES_ENABLED "
            "(tutor ‖ voice, then story + critic). Default: the setting's value."
        ),
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
    from app.services import story_lanes as lanes
    from app.services.serial import SerialThreadService

    use_lanes = settings.ATELIER_STORY_TURN_LANES_ENABLED if args.lanes is None else args.lanes

    report = {
        "version": engine.VERSION,
        "synthetic_only": True,
        "level": args.level,
        "attempts": args.attempts,
        "lanes": use_lanes,
        "requests": [],
        "scenes": [],
    }

    class EventSink:
        def add(self, event):
            pass  # This review never persists telemetry to the application database.

    real_client = engine._client
    calls = 0
    max_requests = args.max_requests

    import threading

    counter_lock = threading.Lock()

    class BoundedClient:
        def generate_chat_completion(self, *args, **kwargs):
            nonlocal calls
            # WP-59 draws two drafts on two threads: the counter is locked, and a
            # call the provider refused is still a request the report shows.
            with counter_lock:
                if calls >= max_requests:
                    raise engine.StoryUnavailable("review_request_limit")
                calls += 1
            started = time.monotonic()
            # WP-87: which lane (schema) this request served, for per-lane latency.
            try:
                messages = args[0] if args else kwargs.get("messages")
                schema = json.loads(messages[0]["content"])["output_schema"]["title"]
            except Exception:  # noqa: BLE001 - a label, never a reason to fail
                schema = None
            try:
                result = real_client().generate_chat_completion(*args, **kwargs)
            except Exception as exc:
                report["requests"].append(
                    {
                        "schema": schema,
                        "error": f"{type(exc).__name__}: {exc}"[:300],
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                        "content": None,
                    }
                )
                raise
            report["requests"].append(
                {
                    "schema": schema,
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
    # WP-63: the season rollover swaps the world bible, and it is the production
    # writer that does it — so this review holds the world on a stand-in "thread"
    # exactly as the database row holds it, and calls that writer rather than a
    # second implementation of it.
    thread = SimpleNamespace(id=args.seed, world_bible=world)
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
            **engine._season_projection(world, {}, seed=args.seed, chapter_index=0),
        },
        "story_so_far": [],
        "relationships": {},
        "moods": {},
        "chapter": None,
        "resolved_chapter_questions": [],
        "variety": {},
        "events": [],
        "commitments": [],
        "recent_situations": [],
        # WP-62 long memory, as production projects it. The ledgers themselves live in
        # `live` below; `context` only ever carries their compact projections.
        "day_index": 0,
        "chronicle": [],
        "consequences": [],
        "plants_due": [],
        "callback": None,
        "secrets": engine.secrets_projection(
            [c["id"] for c in engine._cast_projection(world) if c.get("id")], {}, seed=args.seed
        ),
        "legacy_beat": None,
    }
    arc_progress: dict = {}
    # The same shape `state["living_story"]` has in the database, so the review walks
    # the real writers rather than a second implementation of them.
    live: dict = {
        "chronicle": [],
        "consequences": [],
        "planted": [],
        "secrets": {},
        # WP-63 — l'horizon de saison.
        "threads": {},
        "agendas": {},
        "arc_progress": {},
        "season_index": 1,
        "season_stage": "running",
        "season_chapters": 0,
        "escalated_problems": {},
        "events": [],
    }
    cast_ids = [c["id"] for c in engine._cast_projection(world) if c.get("id")]
    context["agendas"] = engine.agendas_projection(world, {})
    context["season"] = {
        "number": 1,
        "phase": "running",
        "completion": 0.0,
        "chapters": 0,
        "finale": None,
        "interlude": None,
    }
    context["chapter_shape"] = {
        "shape": engine.DEFAULT_SHAPE,
        "beats": list(engine.CHAPTER_SHAPES[engine.DEFAULT_SHAPE]),
        "note": engine.shape_note(engine.DEFAULT_SHAPE),
        "letter_beat": None,
    }
    context["escalated_problems"] = []
    try:
        for day in range(args.days):
            scene, _ = engine._approved(
                engine.DIRECTOR,
                context,
                engine.SceneDraft,
                lambda value: engine._validate_scene(value, context),
                db=EventSink(),
                user=SimpleNamespace(id=uuid4()),
                candidates=engine.dual_draft_candidates(context),
                choose=lambda value: engine._scene_score(value, context),
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
            payload["story"]["moods"] = {scene.character_id: context["moods"].get(scene.character_id, {})}
            payload["story"]["commitments"] = [
                c for c in context["commitments"] if scene.character_id in c["witnesses"]
            ]
            lane_timing: dict = {}
            try:
                if use_lanes:
                    # WP-87, as production runs it: tutor ‖ voice on the request, then
                    # the story lane (ending + critic) off the critical path.
                    payload["turn_plan"] = {"closing_turn": True, "clarify_form_fr": None}
                    reply_started = time.monotonic()
                    reply = lanes.run_reply_lanes(payload)
                    lane_timing["reply_phase_seconds"] = round(time.monotonic() - reply_started, 2)
                    lane_timing["lane_seconds"] = dict(reply.seconds)
                    story = lanes.run_story_lane(payload, reply.tutor, reply.voice)
                    lane_timing["story_lane_seconds"] = story.seconds
                    lane_timing["released_issues"] = story.released_issues
                    if story.turn is None:
                        raise engine.StoryUnavailable(story.reason or "story_lane_failed", hint=story.hint)
                    result = story.turn
                else:
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
                    **lane_timing,
                    "objective_language": engine.objective_language(scene.objective_native),
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
                # WP-63: the hand this chapter is dealt, and the finale/interlude
                # overrides, exactly as `bind_journey` deals them.
                phase = engine.season_phase(live)
                shape = engine.planned_shape(live, seed=args.seed)
                extra: dict = {}
                if phase == "finale":
                    shape, extra = "ensemble", {"finale": True, "side_story": False}
                elif phase == "interlude":
                    beat = engine.interlude_beat(args.seed, engine.chapters_total(live))
                    shape, extra = engine.DEFAULT_SHAPE, {"interlude": True, "interlude_beat_id": beat["id"]}
                current = engine.open_chapter(scene, shape=shape, **extra)
                live["chapters_total"] = engine.chapters_total(live) + 1
                live["season_chapters"] = int(live.get("season_chapters") or 0) + 1
            current = engine.chapter_after_scene(current, scene, result, event_id)
            # Production stamps every situation with its chapter; three guards and the
            # `already_asked` projection read it. Paid A2 re-run 2026-09-21: without it
            # the review never exercised them and lost day 7 to its own chapter.
            context["recent_situations"][-1]["chapter_title_fr"] = current.get("title_fr")
            moods_before = context["moods"]
            context["moods"] = engine.moods_after_turn(moods_before, scene.character_id, result, event_id)
            # WP-62: the same four writers production runs, in the same order.
            for index, commitment in enumerate(result.commitments):
                context["commitments"].append(
                    {
                        "id": f"{event_id}:{index}",
                        **commitment.model_dump(),
                        "status": "open",
                        "witnesses": witnesses,
                        "day": day + 1,
                    }
                )
            live["consequences"] = engine.consequences_after_turn(
                live["consequences"],
                character_id=scene.character_id,
                chapter=current,
                turn=result,
                event_id=event_id,
                day=day + 1,
                moods_before=moods_before,
                moods_after=context["moods"],
                commitments=context["commitments"],
            )
            if scene.callback_ref:
                live["consequences"] = engine.mark_consequence_referenced(
                    live["consequences"], scene.callback_ref, day + 1
                )
            live["chronicle"] = engine.chronicle_after_chapter(
                live["chronicle"],
                chapter=current,
                draft=scene,
                turn=result,
                event_id=event_id,
                day=day + 1,
            )
            live["planted"] = engine.plants_after_scene(
                live["planted"],
                draft=scene,
                chapter=current,
                event_id=event_id,
                day=day + 1,
                chapter_index=len(context["resolved_chapter_questions"]) + 1,
            )
            live["secrets"] = engine.secrets_after_turn(
                live["secrets"],
                scene.character_id,
                scene.secret_shift,
                result.secret_shift,
                allowed_reveal=engine.secrets_projection(cast_ids, live["secrets"], seed=args.seed)["next"],
            )
            if current.get("resolved"):
                context["resolved_chapter_questions"].append(current["dramatic_question"])
            # WP-63: the arc moves only on an honest stage claim, and only when the
            # authored gates allow it; the season's long questions move from the same
            # accepted draft; the cast's private week ticks between chapters.
            world_arcs = list(world.get("season_arcs") or [])
            flags = {
                **(live.get("world_flags") or {}),
                **engine.arc_flags(world_arcs, arc_progress),
            }
            arc_progress = engine.arc_progress_after_scene(
                arc_progress, current, world_arcs, event_id, day=day + 1, flags=flags
            )
            live["arc_progress"] = arc_progress
            live["threads"] = engine.threads_after_scene(
                live["threads"],
                draft=scene,
                known_keys=[row["key"] for row in engine.season_threads(world)],
                closing=engine.chapter_closing(current),
                day=day + 1,
                event_id=event_id,
            )
            live["events"] = list(context["events"])
            if engine.chapter_closing(current):
                live["agendas"], meanwhile = engine.agenda_tick(
                    world,
                    live["agendas"],
                    seed=args.seed,
                    chapter_index=engine.chapters_total(live),
                    day=day + 1,
                )
                if meanwhile and meanwhile["id"] not in {e["id"] for e in context["events"]}:
                    context["events"].append(meanwhile)
                    live["events"] = list(context["events"])
                if current.get("finale"):
                    live["threads"] = engine.close_open_threads(
                        live["threads"], [row["key"] for row in engine.season_threads(world)], day=day + 1
                    )
                live["season_stage"] = engine.season_stage_after_chapter(
                    live, chapter=current, world_arcs=world_arcs, arc_progress=arc_progress
                )
                if current.get("interlude"):
                    if engine.roll_over_season(EventSink(), thread, live, day=day + 1):
                        world = thread.world_bible
                        arc_progress = {}
                        cast_ids = [c["id"] for c in engine._cast_projection(world) if c.get("id")]
                        context["world"]["cast"] = engine._cast_for_level(
                            engine._cast_projection(world), args.level
                        )
                        context["world"]["logline"] = world.get("logline")
                        print(f"Season {live['season_index']} begins.", flush=True)
            context["world"].update(
                engine._season_projection(
                    world,
                    arc_progress,
                    seed=args.seed,
                    chapter_index=len(context["resolved_chapter_questions"]) + 1,
                    flags=engine.arc_flags(world_arcs, arc_progress),
                    day=day + 1,
                    threads=engine.threads_projection(world, live),
                )
            )
            context["chapter"] = engine.chapter_state(
                {"chapter": current, "recent_situations": context["recent_situations"]}
            )
            context["variety"] = engine._variety(
                context["recent_situations"],
                context["world"]["cast"],
                context["world"]["locations"],
            )
            chapter_index = len(context["resolved_chapter_questions"]) + 1
            live["chapter"] = context["chapter"]
            live["resolved_chapter_questions"] = context["resolved_chapter_questions"]
            context["day_index"] = day + 1
            context["chronicle"] = engine.chronicle_for_prompt(live["chronicle"])
            context["consequences"] = engine.top_consequences(live["consequences"], day=day + 1)
            context["plants_due"] = engine.plants_due(live["planted"], chapter_index=chapter_index)
            context["callback"] = engine.callback_candidate(
                live, seed=args.seed, beat=engine.required_beats(context["chapter"])[0]
            )
            context["secrets"] = engine.secrets_projection(cast_ids, live["secrets"], seed=args.seed)
            # WP-63 projections, as `story_context` builds them.
            live["chapter"] = context["chapter"]
            phase = engine.season_phase(live)
            shape = (context["chapter"] or {}).get("shape") or engine.planned_shape(
                live, seed=args.seed
            )
            context["agendas"] = engine.agendas_projection(world, live["agendas"])
            context["chapter_shape"] = {
                "shape": shape,
                "beats": list(engine.CHAPTER_SHAPES.get(shape, engine.CHAPTER_BEATS)),
                "note": engine.shape_note(shape, context["chapter"]),
                "letter_beat": engine.LETTER_BEAT if shape == "letter" else None,
            }
            context["season"] = {
                "number": int(live.get("season_index") or 1),
                "phase": phase,
                "completion": engine.season_completion(
                    list(world.get("season_arcs") or []), arc_progress
                ),
                "chapters": int(live.get("season_chapters") or 0),
                "finale": engine.finale_context(live, world=world, day=day + 1)
                if phase == "finale"
                else None,
                "interlude": engine.interlude_beat(args.seed, engine.chapters_total(live))
                if phase == "interlude"
                else None,
            }
            context["escalated_problems"] = sorted(live.get("escalated_problems") or {})
            print(
                f"Synthetic scene {day + 1}: accepted; {calls}/{args.max_requests} requests used.",
                flush=True,
            )
        report["status"] = "sample_ready_for_human_review"
    except engine.StoryUnavailable as exc:
        report["status"] = "rejected_or_unavailable"
        report["reason"] = str(exc)
        # The token alone never said why a day was lost (paid run 2026-09-21): keep the
        # guard's own sentence — every refusal of the last scene is folded into it.
        report["reason_feedback"] = str(getattr(exc, "feedback", "") or "")
    finally:
        report["attempted_requests"] = calls
        report["lane_latency"] = lane_latency(report)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{report['status']}: {args.output}")


if __name__ == "__main__":
    main()
