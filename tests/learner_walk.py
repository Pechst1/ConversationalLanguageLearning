"""EXERCISE-QA 2026-10-03 — «la promenade de l'apprenant»: a deterministic learner walk.

Plays whole days through the real HTTP surface (the assembled router, the real
planner, the real season 1 and its level overlays, the real graders) for a set of
personas and answer qualities, and writes each day as a JSON transcript **in the
order the learner reads it**: every step's public prompt, what the learner
answered, and every word the app said back.

Nothing here judges a model: the story engine runs on the season suite's scripted
provider (``tests/test_season_one.SeasonProvider``), conftest neutralises every
key, and the clock is the journey service's controllable one. The transcripts are
the evidence; :mod:`tests.walk_checks` reads them.

Used by ``tests/test_learner_walk.py`` (fast: day 1 of every persona × quality)
and by the long walk (``-m walk``: days 1, 2, 7, 14 and 30 of every persona).
``WALK_TRANSCRIPTS=<dir>`` writes the JSON files for a human read.
"""
from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourneyStep
from tests import test_journey_end_to_end as support

PASSWORD = "securepass123"


@dataclass(frozen=True)
class Persona:
    key: str
    native: str
    cefr: str
    description: str


PERSONAS: tuple[Persona, ...] = (
    Persona("a1-de-fresh", "de", "A1.1", "fresh A1 beginner, German native"),
    Persona("a2-de-placed", "de", "A2.1", "placed A2, German native"),
    Persona("b1-en", "en", "B1.1", "B1, English native"),
    Persona("b2-en", "en", "B2.1", "B2, English native"),
    Persona("c1-de", "de", "C1.1", "C1, German native"),
)
QUALITIES: tuple[str, ...] = ("good", "average", "poor")
WALK_DAYS: tuple[int, ...] = (1, 2, 7, 14, 30)


def weave_grammar(draft: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """What a compliant director does with ``grammar_plan.introduce``: one cast line
    that uses the unit (its first authored example, markup removed). The fake
    director of the season suite ignores the plan, so without this the walk never
    meets a Règle step on a generated day."""

    import re as _re

    plan = context.get("grammar_plan") or {}
    introduce = plan.get("introduce") or {}
    examples = [str(example) for example in introduce.get("examples") or [] if example]
    if not examples:
        return draft
    example = examples[0]
    if isinstance(example, dict):  # pragma: no cover - examples are strings today
        example = str(example.get("fr") or "")
    line = " ".join(_re.sub(r"[\[\]{}]", "", example).split())
    panels = list(draft.get("panels") or [])
    if not line or not panels:
        return draft
    speaker = str(draft.get("character_id") or "")
    panels[2] = {**panels[2], "dialogue": [{"character_id": speaker, "text_fr": line, "text_native": ""}]}
    return {**draft, "panels": panels}


def register(client: TestClient, persona: Persona) -> tuple[dict[str, str], str]:
    email = f"walk-{persona.key}-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "target_language": "fr",
            "native_language": persona.native,
            "cefr_estimate": persona.cefr,
        },
    )
    assert response.status_code in (200, 201), response.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, email


# ---------------------------------------------------------------------------
# Answers: good / average / poor
# ---------------------------------------------------------------------------


def _smart_quotes(text: str) -> str:
    """What an iPhone types: U+2019 apostrophes, capitalised first letter."""

    out = text.replace("'", "’")
    return out[:1].upper() + out[1:]


def _accent_slip(text: str) -> str:
    """Drop the first accent that is not grammar (a learner on a German keyboard)."""

    for accented, plain in (("è", "e"), ("ê", "e"), ("ç", "c"), ("î", "i"), ("ô", "o"), ("û", "u")):
        if accented in text:
            return text.replace(accented, plain, 1)
    return text


@dataclass
class Answerer:
    """Decides the answer to one step for one quality, deterministically."""

    quality: str
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def recall(self, driver: support.Driver, step: dict[str, Any]) -> tuple[dict[str, Any], str]:
        task = driver.recall_key(step) or {}
        task_type = str(task.get("task_type") or "")
        if self.quality == "good":
            return driver.recall_answer(step, correct=True), "right"
        if self.quality == "poor":
            return driver.recall_answer(step, correct=False), "wrong"
        # average: typed answers come in with phone typography or an accent slip,
        # and one pick in three is wrong.
        if task_type in {"short_answer", "transform", "dictation"}:
            accepted = list(task.get("accepted_answers") or [])
            if accepted:
                variant = _accent_slip(_smart_quotes(accepted[0]))
                return {"mode": "text", "text": variant}, "right-with-slip"
        if self.rng.random() < 0.34:
            return driver.recall_answer(step, correct=False), "wrong"
        return driver.recall_answer(step, correct=True), "right"

    def reply(self, step: dict[str, Any], examples: list[str], native: str) -> str:
        if self.quality == "good" and examples:
            return examples[0]
        if self.quality == "average":
            base = examples[0] if examples else "Je suis d'accord, je reste."
            # A clumsy but meaningful reply: lower case, no accents, phone quotes.
            return _smart_quotes(base.lower().replace("é", "e").replace("è", "e"))
        return "Ich weiß nicht." if native == "de" else "I don't know."


# ---------------------------------------------------------------------------
# One day, recorded
# ---------------------------------------------------------------------------


def _public_step(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": step.get("id"),
        "kind": step.get("kind"),
        "prompt": step.get("prompt") or {},
    }


def _season_turns(db: Session, journey_id: str) -> list[dict[str, Any]]:
    """Today's season turns from the pinned brief (``[]`` on a generated day)."""

    from tests.test_season_one import _pinned_brief

    brief = _pinned_brief(db, journey_id)
    return list((((brief.get("story_context") or {}).get("season")) or {}).get("turns") or [])


#: Plausible learner replies for a generated (gap) day, where no authored examples exist.
GAP_REPLIES = (
    "Je reste encore un peu. Je veux comprendre qui elle était.",
    "Un café crème, s'il te plaît.",
    "Merci. Oui, j'ai froid, mais ça va mieux.",
    "Je ne sais pas encore. Mais je ne pars pas demain.",
    "D'accord, je t'aide. On commence quand ?",
)


def play_day(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    *,
    persona: Persona,
    quality: str,
    day: int,
    provider: Any | None = None,
) -> dict[str, Any]:
    """Play one whole day and return its transcript (reading order)."""

    driver = support.Driver(client, headers, db=db)
    answerer = Answerer(quality, random.Random(f"{persona.key}-{quality}-{day}"))
    journey = driver.create()
    transcript: dict[str, Any] = {
        "persona": persona.key,
        "native": persona.native,
        "cefr": persona.cefr,
        "quality": quality,
        "day": day,
        "journey_id": journey.get("id"),
        "status": journey.get("status"),
        "day_shape": journey.get("day_shape"),
        "control_language": journey.get("control_language"),
        "events": [],
    }
    events: list[dict[str, Any]] = transcript["events"]
    if journey.get("status") != "active":
        transcript["error"] = f"journey not active: {journey.get('status')}"
        return transcript
    turns = _season_turns(db, journey["id"])
    reply_index = 0
    asked_in_french = False
    for _ in range(160):
        step = driver.current()
        if step is None:
            break
        kind = step["kind"]
        event: dict[str, Any] = {"step": _public_step(step)}
        events.append(event)
        if kind in ("scene", "resolution", "rule", "desk", "forge", "read"):
            driver.advance()
            continue
        if kind == "recall":
            payload, intent = answerer.recall(driver, step)
            key = driver.recall_key(step) or {}
            event["answer"] = {"input": payload, "intent": intent}
            event["key"] = {
                "task_type": key.get("task_type"),
                "accepted_answers": key.get("accepted_answers"),
                "solution_fr": key.get("solution_fr"),
                "target": key.get("target"),
            }
            response = driver.attempt(payload)
            event["status_code"] = response.status_code
            if response.status_code == 200:
                body = response.json()
                event["result"] = _result(body, step["id"])
            if driver.journey.get("current_step_id") == step["id"]:
                driver.advance()
            continue
        # respond: one or more exchanges
        turn = turns[reply_index] if reply_index < len(turns) else {}
        replies = [reply for reply in turn.get("replies") or [] if reply.get("examples")]
        pick = replies[(day + reply_index) % len(replies)] if replies else None
        turn_examples = list(pick["examples"]) if pick else [GAP_REPLIES[(day + reply_index) % len(GAP_REPLIES)]]
        text = answerer.reply(step, turn_examples, persona.native)
        if asked_in_french:
            # QA-CLOSE: the scene asked for French; the poor learner tries, clumsily.
            text, asked_in_french = "je sais pas", False
        if provider is not None and pick is not None:
            provider.routes[text] = str(pick.get("id") or "")
        event["answer"] = {"input": {"mode": "text", "text": text}, "intent": quality}
        response = driver.attempt({"mode": "text", "text": text})
        event["status_code"] = response.status_code
        if response.status_code != 200:
            break
        body = response.json()
        event["result"] = _result(body, step["id"])
        if "en français ?" in str(body.get("character_reply_fr") or ""):
            asked_in_french = True
        else:
            reply_index += 1
        if body.get("next_turn"):
            continue
        if driver.journey.get("current_step_id") == step["id"]:
            driver.advance()
    finish = driver.finish("complete")
    transcript["finish_status"] = finish.status_code
    final = driver.journey
    resolution = next((s for s in final.get("steps") or [] if s.get("kind") == "resolution"), None)
    transcript["resolution"] = (resolution or {}).get("prompt")
    transcript["private_leaks"] = sorted(set(driver.private_leaks))
    return transcript


def _result(body: dict[str, Any], step_id: str) -> dict[str, Any]:
    step = next((s for s in (body.get("journey") or {}).get("steps") or [] if s.get("id") == step_id), {})
    return {
        "task_outcome": body.get("task_outcome"),
        "correction": body.get("correction"),
        "character_reply_fr": body.get("character_reply_fr"),
        "character_lines": body.get("character_lines"),
        "reply_source": body.get("reply_source"),
        "next_turn": (body.get("next_turn") or {}).get("prompt"),
        "pending": body.get("pending"),
        "step_after": {"status": step.get("status"), "prompt": step.get("prompt"), "feedback": step.get("feedback")},
    }


def private_task(db: Session, step_id: str) -> dict[str, Any]:
    row = db.get(DailyJourneyStep, uuid.UUID(step_id))
    return dict(getattr(row, "private_task", None) or {}) if row is not None else {}


def write_transcripts(transcripts: list[dict[str, Any]], name: str) -> Path | None:
    target = os.environ.get("WALK_TRANSCRIPTS")
    if not target:
        return None
    folder = Path(target)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.json"
    path.write_text(json.dumps(transcripts, ensure_ascii=False, indent=1), encoding="utf-8")
    return path
