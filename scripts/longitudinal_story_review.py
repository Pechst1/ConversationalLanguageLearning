"""WP-14F — bounded fourteen-day live prose review of the living-story engine.

Fully synthetic: no application database, no learner record, no persisted
telemetry.  It builds the same context dictionary ``living_story.story_context``
would build, runs the real director/actor/critic calls for one simulated day
after another, and then carries each accepted scene forward by mirroring
``living_story.settle_resolution``'s bookkeeping (events, commitments, chapter,
story_so_far, recent_situations, relationships).

Learner behaviour is scripted per day — accept, refuse, propose something new,
make a grammar mistake, answer off topic, skip a day — so the review can see how
the story reacts to more than a compliant learner.

Run from the repository root, e.g.::

    venv/bin/python scripts/longitudinal_story_review.py                # nothing happens
    venv/bin/python scripts/longitudinal_story_review.py --level A1 --live --attempts 2

Without ``--live`` no provider is constructed and no request is made.  ``--max-requests``
is a hard cap on paid calls (draft + review + turn + review is four per day).
This is a prose-quality sample for human review, never a substitute for
``tests/test_living_story_longitudinal.py``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

# One scripted learner behaviour per simulated day. "skip" advances the date
# without generating anything, which is what a missed day really looks like.
BEHAVIOUR_BY_DAY = [
    "accept",
    "propose",
    "accept",
    "refuse",
    "grammar_mistake",
    "skip",
    "accept",
    "off_topic",
    "accept",
    "propose",
    "refuse",
    "grammar_mistake",
    "accept",
    "accept",
]

SCRIPTED_TEXT = {
    # A refusal is a legitimate communicative act, not a failure to answer.
    "refuse": "Non, désolé, je ne peux pas aujourd'hui. Je dois travailler ce soir.",
    # Real A1/A2 errors: article contraction, agreement, and a wrong auxiliary.
    "grammar_mistake": "Je suis d'accord, je vais à le marché demain et j'ai allé hier aussi.",
    # Comprehensible French, but not an answer to the question asked.
    "off_topic": "J'aime beaucoup les chiens. Mon frère a deux chats à Lyon.",
    "propose": "En fait, j'ai une autre idée : je peux organiser un petit repas chez moi samedi.",
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Actually call the provider.")
    parser.add_argument("--level", default="A1", choices=("A1", "A2", "B1", "B2"))
    parser.add_argument(
        "--address",
        default="neutral",
        choices=("neutral", "feminine", "masculine"),
        help="The learner's stored address preference, as the engine reads it.",
    )
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument(
        "--attempts", type=int, default=2, choices=(1, 2, 3), help="ATELIER_STORY_MAX_ATTEMPTS."
    )
    parser.add_argument(
        "--max-requests", type=int, default=60, help="Hard cap on paid requests for this run."
    )
    parser.add_argument(
        "--no-critic",
        action="store_true",
        help=(
            "Skip the independent review call (living_story.CRITIC_ENABLED = False) for "
            "this process only. Use it for the A/B that decides whether the critic earns "
            "its ~25%% of each scene's cost; the deterministic guards still run."
        ),
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def learner_text(behaviour: str, scene) -> tuple[str, str]:
    """The learner's line for this day, and the assistance the app recorded."""
    if behaviour == "accept":
        # The app's own suggestion: exactly what a supported learner would send.
        return scene.suggested_response_fr, "suggestion"
    return SCRIPTED_TEXT[behaviour], "none"


def actor_payload(context: dict, scene, text: str, assistance: str) -> dict:
    """Mirror of ``living_story._turn_payload``'s knowledge boundary."""
    story = deepcopy(context)
    story["events"] = [e for e in context["events"] if scene.character_id in e["witnesses"]]
    story["story_so_far"] = [e["summary_fr"] for e in story["events"]]
    story["commitments"] = [
        c for c in context["commitments"] if scene.character_id in c["witnesses"]
    ]
    story["legacy_beat"] = None
    story["recent_situations"] = []
    story["chapter"] = {
        key: value
        for key, value in (context.get("chapter") or {}).items()
        if key != "possible_developments"
    }
    story["world"]["cast"] = [
        member
        if member["id"] == scene.character_id
        else {key: member.get(key) for key in ("id", "name", "role")}
        for member in context["world"]["cast"]
    ]
    story["relationships"] = {
        scene.character_id: context["relationships"].get(scene.character_id, {})
    }
    return {
        "story": story,
        "scene": scene.model_dump(mode="json"),
        "rubric": scene.objective_semantics,
        "history": [],
        "learner_text": text,
        "turns_left": 1,
        "targets": [],
        "assistance": assistance,
    }


def open_chapter(context: dict, scene) -> dict:
    """Mirror of ``living_story.bind_journey``'s chapter identity and rotation rules."""
    chapter = context.get("chapter") or {}
    if not chapter or chapter.get("resolved") or chapter.get("exhausted"):
        if chapter.get("dramatic_question"):
            context["resolved_chapter_questions"] = [
                *[
                    question
                    for question in context.get("resolved_chapter_questions") or []
                    if question != chapter["dramatic_question"]
                ],
                chapter["dramatic_question"],
            ][-12:]
        chapter = {
            **scene.chapter.model_dump(),
            "id": str(uuid4()),
            "scene_count": 0,
            "resolved_commitments": 0,
            "resolved": False,
        }
    chapter.pop("exhausted", None)
    context["chapter"] = chapter
    context["recent_situations"] = [
        *context["recent_situations"],
        {
            "id": f"story_{uuid4().hex}",
            "novelty_key": scene.novelty_key,
            "premise_fr": scene.premise_fr,
            "objective_native": scene.objective_native,
            "character_id": scene.character_id,
            "location_id": scene.location_id,
            "causal_reason": scene.causal_reason,
        },
    ][-14:]
    return chapter


def settle(engine, context: dict, scene, turn, event_id: str, when: date) -> dict:
    """Mirror of ``living_story.settle_resolution``'s durable bookkeeping."""
    witnesses = sorted(
        {scene.character_id, *[line.character_id for p in scene.panels for line in p.dialogue]}
    )
    event = {
        "id": event_id,
        "scene_id": f"synthetic:{event_id}",
        "witnesses": witnesses,
        "summary_fr": turn.callback_fr or turn.resolution_fr,
        "source_quotes": turn.evidence_quotes,
        "outcome": turn.outcome,
        "at": when.isoformat(),
    }
    context["events"] = [*context["events"], event][-engine.MAX_HISTORY :]
    commitments = [dict(c) for c in context["commitments"]]
    for existing in commitments:
        if existing["id"] in turn.resolved_commitment_ids:
            existing.update(status="resolved", resolved_by=event_id)
    for index, commitment in enumerate(turn.commitments):
        if any(
            c["status"] == "open" and c["text_fr"].casefold() == commitment.text_fr.casefold()
            for c in commitments
        ):
            continue
        commitments.append(
            {
                "id": f"{event_id}:commitment:{index}",
                "text_fr": commitment.text_fr,
                "source_quote": commitment.source_quote,
                "source_event_id": event_id,
                "witnesses": witnesses,
                "status": "open",
            }
        )
    context["commitments"] = [c for c in commitments if c["status"] == "open"] + [
        c for c in commitments if c["status"] != "open"
    ][-20:]
    chapter = dict(context["chapter"])
    chapter["scene_count"] = int(chapter.get("scene_count", 0)) + 1
    chapter["resolved_commitments"] = int(chapter.get("resolved_commitments", 0)) + len(
        [c for c in commitments if c.get("resolved_by") == event_id]
    )
    if turn.chapter_resolved and turn.outcome == "met":
        chapter.update(resolved=True, resolved_by=event_id)
    context["chapter"] = chapter
    context["story_so_far"] = [*context["story_so_far"], event["summary_fr"]][-40:]
    # Relationship closeness/callbacks as SerialThreadService keeps them. The tu
    # register switch depends on durable thread state and is not simulated here.
    relationships = dict(context["relationships"])
    entry = dict(relationships.get(scene.character_id) or {})
    entry["closeness"] = max(0, min(5, int(entry.get("closeness") or 0)))
    entry["register"] = str(entry.get("register") or "vous")
    if turn.outcome == "met":
        entry["closeness"] = min(5, entry["closeness"] + 1)
    if turn.summary_native:
        entry["last_summary"] = turn.summary_native
    if turn.callback_fr:
        callbacks = [c for c in entry.get("callbacks", []) if c]
        if turn.callback_fr not in callbacks:
            callbacks.append(turn.callback_fr)
        entry["callbacks"] = callbacks[-5:]
    relationships[scene.character_id] = entry
    context["relationships"] = relationships
    return event


def main():
    args = parse_args()
    output = args.output or Path(f"var/reviews/atelier-longitudinal-{args.level}.json")
    if not args.live:
        print(
            f"No requests made. --live simulates {args.days} days for a {args.level} learner "
            f"using at most --max-requests ({args.max_requests}) model requests "
            f"({'draft + review + turn + review' if not args.no_critic else 'draft + turn'} "
            "per day). No application database is used."
        )
        return

    from app.config import settings
    from app.db import models  # noqa: F401 — register model relationships for the event sink
    from app.services import living_story as engine
    from app.services.serial import SerialThreadService

    report = {
        "version": engine.VERSION,
        "level": args.level,
        "critic": not args.no_critic,
        "address": args.address,
        "attempts": args.attempts,
        "synthetic_only": True,
        "requests": [],
        "days": [],
    }

    class EventSink:
        def add(self, event):  # This review never writes telemetry to any database.
            pass

    real_client = engine._client
    state = {"calls": 0, "day": 0, "stage": None}

    class BoundedClient:
        def generate_chat_completion(self, messages, **kwargs):
            if state["calls"] >= args.max_requests:
                raise engine.StoryUnavailable("review_request_limit")
            state["calls"] += 1
            stage = json.loads(messages[0]["content"])["output_schema"]["title"]
            started = time.monotonic()
            try:
                result = real_client().generate_chat_completion(messages, **kwargs)
            except Exception as exc:  # recorded, then handled by the engine's own retry
                report["requests"].append(
                    {
                        "day": state["day"],
                        "stage": f"{state['stage']}/{stage}",
                        "error": f"{type(exc).__name__}: {exc}"[:200],
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                    }
                )
                raise
            report["requests"].append(
                {
                    "day": state["day"],
                    "stage": f"{state['stage']}/{stage}",
                    "model": result.model,
                    "provider": result.provider,
                    "tokens": result.total_tokens,
                    "estimated_cost_usd": result.cost,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    # The raw proposal, so a rejected day still leaves reviewable
                    # evidence of what the model actually wrote.
                    "content": (result.content or "")[:3000],
                }
            )
            return result

    settings.ATELIER_LLM_ENABLED = True  # This process only; no persisted flag changes.
    settings.ATELIER_STORY_MAX_ATTEMPTS = args.attempts
    engine.CRITIC_ENABLED = not args.no_critic
    engine._client = lambda: BoundedClient()

    world = SerialThreadService._load_world_bible()
    context = {
        "thread_id": "synthetic-longitudinal",
        "revision": "synthetic",
        "control_language": "en",
        "learner": {
            "address": args.address,
            "grammatical_gender_note": engine.ADDRESS_NOTES[args.address],
        },
        "level": args.level,
        "level_register": (
            "no coarse or vulgar vocabulary"
            if args.level in engine.CLEAN_REGISTER_LEVELS
            else "the cast's own register"
        ),
        "world": {
            "logline": world.get("logline"),
            # Same projection and same level register filter as ``story_context``.
            "cast": engine._cast_for_level(
                [
                    {
                        key: member.get(key)
                        for key in (
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
                    for member in world["cast"]
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

    sink, user = EventSink(), SimpleNamespace(id=uuid4())
    today = date(2026, 3, 10)
    stopped = None
    for index in range(args.days):
        day_number = index + 1
        when = today + timedelta(days=index)
        behaviour = BEHAVIOUR_BY_DAY[index % len(BEHAVIOUR_BY_DAY)]
        state["day"] = day_number
        if behaviour == "skip":
            report["days"].append(
                {"day": day_number, "date": when.isoformat(), "behaviour": "skip", "status": "skipped"}
            )
            print(f"Day {day_number} ({when}): skipped, no request.", flush=True)
            continue
        before = state["calls"]
        started = time.monotonic()
        # Same derived director inputs as ``living_story.story_context``.
        context["variety"] = engine._variety(
            [{k: v for k, v in item.items() if k != "id"} for item in context["recent_situations"]],
            context["world"]["cast"],
            context["world"]["locations"],
        )
        context["chapter"] = engine.chapter_state(
            {"chapter": context.get("chapter")} if context.get("chapter") else {}
        )
        try:
            state["stage"] = "director"
            scene, _ = engine._approved(
                engine.DIRECTOR,
                context,
                engine.SceneDraft,
                lambda value: engine._validate_scene(value, context),
                db=sink,
                user=user,
            )
        except engine.StoryUnavailable as exc:
            report["days"].append(
                {
                    "day": day_number,
                    "date": when.isoformat(),
                    "behaviour": behaviour,
                    "status": "scene_unavailable",
                    "reason": str(exc),
                    "requests": state["calls"] - before,
                }
            )
            print(f"Day {day_number} ({when}): no scene — {exc}", flush=True)
            if str(exc) == "review_request_limit":
                stopped = "review_request_limit"
                break
            continue
        chapter = open_chapter(context, scene)
        text, assistance = learner_text(behaviour, scene)
        payload = actor_payload(context, scene, text, assistance)
        try:
            state["stage"] = "actor"
            turn, _ = engine._approved(
                engine.ACTOR,
                payload,
                engine.SemanticTurn,
                lambda value, source=payload: engine._validate_turn(value, source),
                db=sink,
                user=user,
            )
        except engine.StoryUnavailable as exc:
            report["days"].append(
                {
                    "day": day_number,
                    "date": when.isoformat(),
                    "behaviour": behaviour,
                    "status": "turn_unavailable",
                    "reason": str(exc),
                    "scene": scene.model_dump(mode="json"),
                    "learner_text": text,
                    "requests": state["calls"] - before,
                }
            )
            print(f"Day {day_number} ({when}): scene ok, no turn — {exc}", flush=True)
            if str(exc) == "review_request_limit":
                stopped = "review_request_limit"
                break
            continue
        event = settle(engine, context, scene, turn, f"day:{day_number}", when)
        report["days"].append(
            {
                "day": day_number,
                "date": when.isoformat(),
                "behaviour": behaviour,
                "status": "accepted",
                "assistance": assistance,
                "chapter": {k: chapter[k] for k in ("id", "title_fr", "dramatic_question")},
                "chapter_resolved": bool(context["chapter"].get("resolved")),
                "scene": scene.model_dump(mode="json"),
                "learner_text": text,
                "turn": turn.model_dump(mode="json"),
                "event": event,
                "open_commitments": [
                    c for c in context["commitments"] if c["status"] == "open"
                ],
                "requests": state["calls"] - before,
                "elapsed_seconds": round(time.monotonic() - started, 2),
            }
        )
        print(
            f"Day {day_number} ({when}, {behaviour}): {turn.outcome}; "
            f"{state['calls']}/{args.max_requests} requests used.",
            flush=True,
        )

    accepted = [d for d in report["days"] if d["status"] == "accepted"]
    latencies = [r["elapsed_seconds"] for r in report["requests"] if "error" not in r]
    report["summary"] = {
        "days_simulated": len(report["days"]),
        "days_accepted": len(accepted),
        "days_skipped": len([d for d in report["days"] if d["status"] == "skipped"]),
        "days_failed": len(
            [d for d in report["days"] if d["status"] in ("scene_unavailable", "turn_unavailable")]
        ),
        "requests": state["calls"],
        "request_errors": len([r for r in report["requests"] if "error" in r]),
        "estimated_cost_usd": round(
            sum(r.get("estimated_cost_usd") or 0.0 for r in report["requests"]), 4
        ),
        "tokens": sum(r.get("tokens") or 0 for r in report["requests"]),
        "models": sorted({r["model"] for r in report["requests"] if r.get("model")}),
        "median_request_seconds": round(statistics.median(latencies), 2) if latencies else None,
        "max_request_seconds": max(latencies) if latencies else None,
        "stopped_early": stopped,
        "outcomes": {
            outcome: len([d for d in accepted if d["turn"]["outcome"] == outcome])
            for outcome in ("met", "partially_met", "not_yet")
        },
        "distinct_premises": len({d["scene"]["premise_fr"] for d in accepted}),
        "distinct_locations": sorted({d["scene"]["location_id"] for d in accepted}),
        "distinct_characters": sorted({d["scene"]["character_id"] for d in accepted}),
        "chapters": len({d["chapter"]["id"] for d in accepted}),
        "open_commitments_at_end": [c["text_fr"] for c in context["commitments"] if c["status"] == "open"],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
