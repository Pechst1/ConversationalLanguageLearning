#!/usr/bin/env python
"""The season-end walk's API (2026-11-09): production's story settings on a throwaway database.

One uvicorn worker, lanes on, two drafts, the critic, the season writer on: the values
come from ``render.yaml``'s ``atelier-api`` block, not from a second list that can drift.
Art, speech and La Revue are off (they bypass the story engine and only cost money).
The test clock is on, so this can never start in production.

    DATABASE_URL=postgresql://localhost/atelier_walk_XXXX SEASON_END_OUT=<dir> \
    SEASON_END_MODE=fake            venv/bin/python scripts/season_end_walk_server.py --port 8021
    SEASON_END_MODE=live SEASON_END_MAX_USD=6 ...

**The cap is hard.** Before every call the guard adds the worst case of that call (its
prompt plus its whole ``max_tokens``, at the model's price) to the money already spent,
to the calls in flight, and to the worst case of any call that failed after it left
(a timed-out call may still be billed). Over the cap, the call is refused and never
leaves the process. The ledger is on disk after every call and survives a restart.

**Nothing else can bill.** Outbound HTTP is refused unless it is a chat completion on
OpenAI or a message on Anthropic (fake mode: refused altogether), so an image, a voice or
a transcription cannot leave whatever a flag says. The keys come from the shared
checkout's ``.env`` and are never printed.

**Failure injection** (``POST /__walk/control``, both modes), for the writer and the
story lane: ``writer_delay_s``, ``critic_delay_s``, ``lane_delay_s`` honour the call's own
``request_timeout`` exactly as a slow provider would; ``writer_mode`` is ``ok``,
``timeout``, ``refuse`` (fake only: the critic says no) or ``garbage`` (fake only).

Logs in ``SEASON_END_OUT``: ``calls.jsonl`` (every model call), ``requests.jsonl`` (every
HTTP request with its duration), ``locks.jsonl`` (what Postgres held while the writer
ran), ``writer/`` (what the writer and its critic answered) and ``spend.json``.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(1, str(REPO / "scripts"))

MODE = os.environ.get("SEASON_END_MODE", "fake")
OUT = Path(os.environ.get("SEASON_END_OUT") or "").resolve() if os.environ.get("SEASON_END_OUT") else None
CAP = float(os.environ.get("SEASON_END_MAX_USD", "0"))
WRITER_SCHEMAS = {"SeasonDraft", "SeasonReview"}
# Slow story lane = these, the ones the lane job waits on before its settle.
LANE_SCHEMAS = {"StoryTurn", "TurnReview"}

CONTROL: dict[str, Any] = {
    "writer_delay_s": 0,
    "critic_delay_s": 0,
    "lane_delay_s": 0,
    "writer_mode": "ok",
}
#: What this walk changes from production's manifest, and why.
OVERRIDES = {
    "APP_ENV": "development",  # the test clock refuses to exist in production
    "ATELIER_TEST_CLOCK_ENABLED": "true",
    "LOG_FORMAT": "text",
    "REGISTRATION_OPEN": "true",
    "RUN_MIGRATIONS": "0",
    "BOOTSTRAP_REFERENCE_DATA": "0",
    "SENTRY_ENVIRONMENT": "walk",
    "RATE_LIMIT_TRUSTED_PROXY_HOPS": "0",
    "SCHEMA_GUARD_ENABLED": "true",
    # They bypass the story engine and only cost money here.
    "ATELIER_PANEL_ART_ENABLED": "false",
    "GRAPHIC_NOVEL_IMAGE_GENERATION_ENABLED": "false",
    "ATELIER_EPISODE_AUDIO_ENABLED": "false",
    "FEUILLETON_AUDIO_ENABLED": "false",
    "ATELIER_SPOKEN_REPLY_ENABLED": "false",
    "SERIAL_PHONE_CALL_MISSIONS_ENABLED": "false",
    "REVUE_ENABLED": "false",
    "REVUE_RADIO_ENABLED": "false",
    "REVUE_CORRECTEUR_ENABLED": "false",
    "REVUE_COMPTOIR_ENABLED": "false",
    "REVUE_PLATE_GENERATION_ENABLED": "false",
    "ATELIER_POOL_BACKGROUND_TOPUP_ENABLED": "false",
    # Weeks of a life are played in an hour of real time; this guard reads the real day.
    # The walk's own cap replaces it. The per-learner caps stay at production's values.
    "SERVICE_DAILY_SPEND_CAP_USD": "1000",
    # A person answering a day at a time never trips it; a rehearsal that plays a day in
    # seconds does. GET polls are not limited in production either.
    "RATE_LIMIT_ENABLED": "false",
    # No broker: nothing may queue into the owner's Redis.
    "CELERY_TASK_ALWAYS_EAGER": "true",
    "CELERY_BROKER_URL": "memory://",
    "CELERY_RESULT_BACKEND": "cache+memory://",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def jsonl(name: str, row: dict) -> None:
    if OUT is None:
        return
    with (OUT / name).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": now_iso(), **row}, ensure_ascii=False, default=str) + "\n")


def production_environment() -> None:
    """``render.yaml``'s plain values, then this walk's overrides. Secrets are not in it."""

    import yaml

    manifest = yaml.safe_load((REPO / "render.yaml").read_text(encoding="utf-8"))
    api = next(row for row in manifest["services"] if row.get("name") == "atelier-api")
    cors = os.environ.get("BACKEND_CORS_ORIGINS")
    for row in api.get("envVars") or []:
        if "value" in row:
            os.environ[str(row["key"])] = str(row["value"])
    os.environ.update(OVERRIDES)
    if cors:
        os.environ["BACKEND_CORS_ORIGINS"] = cors
    # The walk harness's one-minute token is a stress test of its own; this walk measures
    # a wait, so the token lives as long as production's.
    os.environ.pop("ACCESS_TOKEN_EXPIRE_MINUTES", None)


def guard_database() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    name = urlparse(url.replace("+psycopg2", "")).path.lstrip("/")
    if not name.startswith(("atelier_walk_", "atelier_season_end")):
        sys.exit(f"Refusing database {name!r}: this server runs on a throwaway atelier_walk_* database only.")
    return name


def shared_env_keys() -> None:
    """The owner's keys from the shared checkout's ``.env``: never printed, never copied."""

    from dotenv import dotenv_values

    common = subprocess.run(  # noqa: S603 - fixed git argv, no shell
        ["git", "-C", str(REPO), "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607 - git from PATH (dev script)
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    values = dotenv_values(Path(common).parent / ".env")
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        if values.get(key):
            os.environ[key] = str(values[key])
        else:
            os.environ.pop(key, None)
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("No OPENAI_API_KEY in the shared checkout's .env.")


# ---------------------------------------------------------------------------
# Outbound allowlist
# ---------------------------------------------------------------------------


def allowed(url: str) -> bool:
    parsed = urlparse(str(url))
    host = parsed.hostname or ""
    if host in {"127.0.0.1", "localhost", "::1", "testserver"}:
        return True
    if MODE != "live":
        return False
    if host == "api.openai.com":
        return parsed.path.endswith(("/chat/completions", "/responses"))
    if host == "api.anthropic.com":
        return parsed.path.endswith("/messages")
    return False


def install_allowlist() -> None:
    import httpx
    import requests

    def refuse(url: Any) -> None:
        jsonl("refused_outbound.jsonl", {"url": str(url).split("?")[0]})
        raise RuntimeError(f"season-end walk: outbound request refused: {str(url).split('?')[0]}")

    plain_send = httpx.Client.send

    def send(self, request, **kwargs):
        if not allowed(str(request.url)):
            refuse(request.url)
        return plain_send(self, request, **kwargs)

    httpx.Client.send = send
    plain_async = httpx.AsyncClient.send

    async def async_send(self, request, **kwargs):
        if not allowed(str(request.url)):
            refuse(request.url)
        return await plain_async(self, request, **kwargs)

    httpx.AsyncClient.send = async_send
    plain_requests = requests.Session.send

    def requests_send(self, request, **kwargs):
        if not allowed(str(request.url)):
            refuse(request.url)
        return plain_requests(self, request, **kwargs)

    requests.Session.send = requests_send


# ---------------------------------------------------------------------------
# The ledger, and what every model call goes through
# ---------------------------------------------------------------------------


class SpendCapReached(RuntimeError):
    pass


class Ledger:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = {"usd": 0.0, "calls": 0, "cap": CAP, "failed_worst_usd": 0.0, "refused_calls": 0, "by_model": {}}
        self.in_flight = 0.0
        self.path = OUT / "spend.json" if OUT else None
        if self.path and self.path.is_file():
            self.state.update(json.loads(self.path.read_text(encoding="utf-8")))
            self.state["cap"] = CAP

    def worst_case(self, model: str, prompt_chars: int, max_tokens: int) -> float:
        from app.services.llm_service import text_price_for

        # An unpriced model is costed at the dearest we know: the cap errs on the safe side.
        rates, _known = text_price_for(model)
        # About three characters a token for this French-and-JSON prompt: an overestimate.
        return (prompt_chars / 3 / 1000) * rates["prompt"] + (max_tokens / 1000) * rates["completion"]

    def reserve(self, worst: float) -> None:
        with self.lock:
            committed = self.state["usd"] + self.state["failed_worst_usd"] + self.in_flight
            if committed + worst > CAP:
                self.state["refused_calls"] += 1
                self._save()
                raise SpendCapReached(f"spend cap US${CAP}: {committed:.3f} committed, this call could add {worst:.3f}")
            self.in_flight += worst

    def settle(self, worst: float, *, model: str, cost: float | None) -> None:
        with self.lock:
            self.in_flight = max(0.0, self.in_flight - worst)
            self.state["calls"] += 1
            row = self.state["by_model"].setdefault(model, {"calls": 0, "usd": 0.0})
            row["calls"] += 1
            if cost is None:
                # It left the process and did not come back: it may still be billed.
                self.state["failed_worst_usd"] += worst
            else:
                self.state["usd"] += cost
                row["usd"] += cost
            self._save()

    def _save(self) -> None:
        if self.path:
            self.path.write_text(json.dumps(self.state, indent=1), encoding="utf-8")


LEDGER: Ledger | None = None
WRITER_INFLIGHT = threading.Event()


def schema_of(messages: list[dict]) -> str | None:
    try:
        return str(json.loads(messages[0]["content"])["output_schema"]["title"])
    except Exception:  # noqa: BLE001 - not every LLM call is a story call
        return None


def inject(schema: str | None, kwargs: dict) -> None:
    """A slow or failing provider, on the schema's own ``request_timeout``."""

    if schema == "SeasonDraft" and CONTROL["writer_mode"] == "timeout":
        window = float(kwargs.get("request_timeout") or 60)
        time.sleep(min(window, float(CONTROL["writer_delay_s"] or 0)))
        raise TimeoutError("season-end walk: writer forced to time out")
    delay = 0.0
    if schema == "SeasonDraft":
        delay = float(CONTROL["writer_delay_s"] or 0)
    elif schema == "SeasonReview":
        delay = float(CONTROL["critic_delay_s"] or 0)
    elif schema in LANE_SCHEMAS:
        delay = float(CONTROL["lane_delay_s"] or 0)
    if not delay:
        return
    window = kwargs.get("request_timeout")
    if window is not None and delay > float(window):
        time.sleep(float(window))
        raise TimeoutError(f"season-end walk: {schema} ran past its {window} s window")
    time.sleep(delay)


def keep_writer_output(schema: str | None, content: Any) -> None:
    if schema in WRITER_SCHEMAS and OUT is not None:
        folder = OUT / "writer"
        folder.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        (folder / f"{stamp}-{schema}.json").write_text(str(content or ""), encoding="utf-8")


def observed(schema: str | None, kwargs: dict, call) -> Any:
    """Run ``call``, with the writer's lock sampler on, and log what happened."""

    from app.services import living_story as engine

    started = time.monotonic()
    if schema in WRITER_SCHEMAS:
        WRITER_INFLIGHT.set()
    try:
        result = call()
    except Exception as exc:
        jsonl("calls.jsonl", {
            "schema": schema, "model": kwargs.get("model"), "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "seconds": round(time.monotonic() - started, 3), "thread": threading.current_thread().name,
            "ahead": engine._AHEAD_OF_TIME.get(), "request_timeout": kwargs.get("request_timeout"),
        })
        raise
    finally:
        if schema in WRITER_SCHEMAS:
            WRITER_INFLIGHT.clear()
    jsonl("calls.jsonl", {
        "schema": schema, "model": getattr(result, "model", None), "provider": getattr(result, "provider", None),
        "tokens": getattr(result, "total_tokens", None), "cost": getattr(result, "cost", None),
        "seconds": round(time.monotonic() - started, 3), "thread": threading.current_thread().name,
        "ahead": engine._AHEAD_OF_TIME.get(), "request_timeout": kwargs.get("request_timeout"),
        "reasoning_effort": kwargs.get("reasoning_effort"), "max_tokens": kwargs.get("max_tokens"),
    })
    keep_writer_output(schema, getattr(result, "content", None))
    return result


def install_live_guard() -> None:
    from app.services import llm_service

    original = llm_service.LLMService.generate_chat_completion

    def guarded(self, messages, *args, **kwargs):
        schema = schema_of(messages)
        if schema == "SeasonReview" and CONTROL.get("critic_json_word"):
            # Walk only, never the product: OpenAI refuses a json_object call whose messages
            # never say "json", which is what SEASON_CRITIC does. With this on, the walk can
            # read what a learner would get once that is fixed.
            kwargs["system_prompt"] = f"{kwargs.get('system_prompt') or ''}\nAnswer in JSON."
        model = str(kwargs.get("model") or os.environ.get("OPENAI_MODEL") or "unknown")
        prompt_chars = sum(len(str(row.get("content") or "")) for row in messages) + len(str(kwargs.get("system_prompt") or ""))
        worst = LEDGER.worst_case(model, prompt_chars, int(kwargs.get("max_tokens") or 4000))
        LEDGER.reserve(worst)
        cost: float | None = None

        def call():
            inject(schema, kwargs)
            return original(self, messages, *args, **kwargs)

        try:
            result = observed(schema, kwargs, call)
            cost = float(getattr(result, "cost", 0.0) or 0.0)
            return result
        except Exception as exc:
            # A request the provider refused outright (400, 401) did no work and is not billed;
            # anything else may have left and stays at its worst case.
            if "error 400" in str(exc) or "error 401" in str(exc):
                cost = 0.0
            raise
        finally:
            LEDGER.settle(worst, model=model, cost=cost)

    llm_service.LLMService.generate_chat_completion = guarded


def fake_writer_answer(schema: str, source: dict) -> dict:
    if schema == "SeasonDraft":
        refs = [row["id"] for row in source["material"]]
        cast = [row["id"] for row in (source.get("world") or {}).get("cast") or []][:3] or ["user"]
        return {
            "title_fr": "La saison écrite (fake)",
            "logline": "Plumbing only: the written season of the fake provider.",
            "logline_fr": "Une saison de plomberie, sans vrai modèle.",
            "your_arc": "Plumbing only; never read this for quality.",
            "first_episode_seed": "Plumbing only: a morning at the usual table.",
            "arcs": [
                {
                    "id": f"fake_arc_{index}",
                    "title_fr": f"Arc {index}",
                    "characters": [cast[index % len(cast)], "user"],
                    "grounded_in": refs[index % len(refs)],
                    "min_episodes_between_stages": 2,
                    "stages": [
                        {"id": "spark", "summary": "Something from before comes back.", "sets": {"walk.x": "a"}},
                        {"id": "pressure", "summary": "It costs something real.", "sets": {"walk.x": "b"}},
                        {"id": "tentpole", "summary": "It is settled out loud.", "sets": {"walk.x": True}},
                    ],
                }
                for index in range(3)
            ],
            "open_threads": [
                {"text": "A question comes back.", "text_fr": "Une question revient.", "grounded_in": refs[index % len(refs)]}
                for index in range(3)
            ],
        }
    accepted = CONTROL["writer_mode"] != "refuse"
    return {"accepted": accepted, "issues": [] if accepted else ["fake critic: refused by the walk's control"]}


def install_fake_provider() -> None:
    """The suite's season provider (it writes every day to a season's end, as the walk's
    own fake does not), under the writer's fake. Plumbing only, never a reading."""

    from app.services import living_story as engine
    from tests.test_living_story_longitudinal import TurnScript
    from tests.test_season_one import SeasonProvider

    plain = SeasonProvider()
    plain.spoil_once = False
    plain.critic_refusals_left = 0
    plain.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Tu as parlé.")
    engine.DUAL_DRAFTS_ENABLED = False

    class Provider:
        def generate_chat_completion(self, messages, **kwargs):
            schema = schema_of(messages)

            def call():
                inject(schema, kwargs)
                if schema in WRITER_SCHEMAS:
                    if schema == "SeasonDraft" and CONTROL["writer_mode"] == "garbage":
                        content = '{"title_fr": "cut off'
                    else:
                        source = json.loads(messages[0]["content"])["data"]
                        content = json.dumps(fake_writer_answer(schema, source), ensure_ascii=False)
                    return SimpleNamespace(content=content, model="fake-season", provider="fake", total_tokens=10, cost=0.0)
                return plain.generate_chat_completion(messages, **kwargs)

            return observed(schema, kwargs, call)

    provider = Provider()
    engine._client = lambda: provider


# ---------------------------------------------------------------------------
# What Postgres holds while the writer runs
# ---------------------------------------------------------------------------


def lock_sampler(database_url: str) -> None:
    import psycopg2

    connection = psycopg2.connect(database_url.replace("postgresql+psycopg2", "postgresql"))
    connection.autocommit = True
    cursor = connection.cursor()
    while True:
        WRITER_INFLIGHT.wait()
        cursor.execute(
            """
            select a.pid, a.state, a.wait_event_type, a.wait_event,
                   round(extract(epoch from (now() - a.xact_start))::numeric, 1), left(a.query, 90),
                   (select count(*) from pg_locks l where l.pid = a.pid and not l.granted)
            from pg_stat_activity a
            where a.datname = current_database() and a.pid <> pg_backend_pid() and a.xact_start is not null
            """
        )
        jsonl("locks.jsonl", {"rows": cursor.fetchall()})
        time.sleep(1.0)


# ---------------------------------------------------------------------------
# Timing and the walk's own routes
# ---------------------------------------------------------------------------


class Timing:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = {"code": None}

        async def sending(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        started = time.monotonic()
        try:
            await self.app(scope, receive, sending)
        finally:
            jsonl("requests.jsonl", {
                "method": scope["method"], "path": scope["path"], "status": status["code"],
                "seconds": round(time.monotonic() - started, 3),
            })


def add_walk_routes(app) -> None:
    from fastapi import Body
    from sqlalchemy import select

    from app.core.security import create_access_token
    from app.db.models.user import User
    from app.db.session import SessionLocal
    from app.services import living_story as engine
    from app.services.journey_latency import prefetch_scene_for
    from app.services.season.admin import jump_to_day

    def user_of(db, email: str) -> User:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise ValueError(f"no user {email}")
        return user

    @app.post("/__walk/control", include_in_schema=False)
    def control(values: dict = Body(default={})):
        CONTROL.update(values)
        return CONTROL

    @app.get("/__walk/spend", include_in_schema=False)
    def spend():
        return {
            **(LEDGER.state if LEDGER else {"usd": 0.0, "note": "fake mode: nothing can bill"}),
            "keys": {key: bool(os.environ.get(key)) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")},
            "mode": MODE,
        }

    @app.post("/__walk/token", include_in_schema=False)
    def token(values: dict = Body(...)):
        with SessionLocal() as db:
            user = user_of(db, values["email"])
            return {"access_token": create_access_token(str(user.id), auth_version=getattr(user, "auth_version", None))}

    @app.post("/__walk/level", include_in_schema=False)
    def level(values: dict = Body(...)):
        with SessionLocal() as db:
            user = user_of(db, values["email"])
            user.cefr_estimate = values["cefr"]
            db.commit()
            return {"cefr_estimate": user.cefr_estimate}

    @app.post("/__walk/jump", include_in_schema=False)
    def jump(values: dict = Body(...)):
        with SessionLocal() as db:
            summary = jump_to_day(db, user_of(db, values["email"]), day=int(values["day"]), flags=dict(values.get("flags") or {}))
            db.commit()
            return json.loads(json.dumps(summary, default=str))

    @app.post("/__walk/prefetch", include_in_schema=False)
    def prefetch(values: dict = Body(...)):
        """The night's beat, for one learner: production's prefetch, ahead of time."""

        started = time.monotonic()
        with SessionLocal() as db:
            user = user_of(db, values["email"])
            status = prefetch_scene_for(db, user)
            # The row's timestamp is the database's own, which the test clock does not move:
            # stamped with the walk's date, or the morning's TTL floor reads it as expired.
            from sqlalchemy import func, select

            from app.db.models.pilot_event import PilotEvent
            from app.services import journey_latency

            # Rows already stamped are in the future of the database's clock, so the newest
            # row at or before its own now is the one this call just wrote.
            row = db.scalar(
                select(PilotEvent)
                .where(
                    PilotEvent.event_type == journey_latency.PREFETCH_EVENT,
                    PilotEvent.user_id == user.id,
                    PilotEvent.occurred_at <= func.clock_timestamp(),
                )
                .order_by(PilotEvent.occurred_at.desc())
                .limit(1)
            )
            if row is not None:
                row.occurred_at = journey_latency._utcnow()
            # The beat commits its row itself (app/tasks); without this the page is lost
            # when the session closes and the morning generates it cold.
            db.commit()
        return {"status": status, "seconds": round(time.monotonic() - started, 2)}

    @app.post("/__walk/writer_bench", include_in_schema=False)
    def writer_bench(values: dict = Body(...)):
        """One more writer and critic on this learner's stored material, nothing saved."""

        from app.db.models.serial import SerialThread
        from app.services import season_writer

        with SessionLocal() as db:
            user = user_of(db, values["email"])
            thread = db.scalar(
                select(SerialThread).where(SerialThread.user_id == user.id, SerialThread.status == "active")
                .order_by(SerialThread.created_at.desc())
            )
            story = dict((thread.state or {}).get(engine.STATE_KEY) or {})
            world = dict(thread.world_bible or {})
        season = int(story.get("season_index") or world.get("season_number") or 1)
        started = time.monotonic()
        written = season_writer.draft_next_season(live=story, world=world, next_season=season + 1)
        return {
            "accepted": bool(written),
            "seconds": round(time.monotonic() - started, 2),
            "title_fr": (written or {}).get("season_title_fr"),
            "material_rows": len(season_writer.season_material(story, world)),
        }

    @app.post("/__walk/install_written", include_in_schema=False)
    def install_written(values: dict = Body(...)):
        """Harness only: swap a reprise that no page has served yet for a written season.

        Both real lives ended on the reprise, so the start of a written season could not be
        read. This repeats the writer until one draft is accepted, at most ``tries`` times,
        then installs it the way ``roll_over_season`` does. It says nothing about how often
        the writer succeeds: the bench and the real rollovers measure that.
        """

        from app.db.models.serial import SerialThread
        from app.services import season_writer
        from app.services.serial import SerialThreadService

        with SessionLocal() as db:
            user = user_of(db, values["email"])
            thread = db.scalar(
                select(SerialThread).where(SerialThread.user_id == user.id, SerialThread.status == "active")
                .order_by(SerialThread.created_at.desc())
            )
            state = dict(thread.state or {})
            story = dict(state.get(engine.STATE_KEY) or {})
            premiere = dict(story.get("season_premiere") or {})
            if not premiere.get("pending") or premiere.get("source") != "reprise":
                return {"installed": False, "reason": "no unserved reprise", "premiere": premiere}
            world = dict(thread.world_bible or {})
            number = int(premiere["number"])
            tries = int(values.get("tries") or 4)
            attempts = 0
            written = None
            while attempts < tries and not written:
                attempts += 1
                written = season_writer.draft_next_season(live=story, world=world, next_season=number)
            if not written:
                return {"installed": False, "attempts": attempts}
            following = SerialThreadService(db).merge_season_world_bible(world, written, next_season=number)
            thread.world_bible = following
            story["season_premiere"] = {
                **engine.season_premiere_of(following),
                "source": "written",
                "pending": True,
                "day": premiere.get("day"),
            }
            thread.state = {**state, engine.STATE_KEY: story}
            db.commit()
            return {"installed": True, "attempts": attempts, "premiere": story["season_premiere"]}

    @app.get("/__walk/live", include_in_schema=False)
    def live(email: str):
        from app.db.models.serial import SerialThread
        from app.services.season.clock import SEASON_KEY

        with SessionLocal() as db:
            user = user_of(db, email)
            thread = db.scalar(
                select(SerialThread).where(SerialThread.user_id == user.id, SerialThread.status == "active")
                .order_by(SerialThread.created_at.desc())
            )
            state = dict(thread.state or {}) if thread else {}
            story = dict(state.get(engine.STATE_KEY) or {})
            world = thread.world_bible if thread and isinstance(thread.world_bible, dict) else {}
            season = dict(story.get(SEASON_KEY) or {})
            chapter = dict(story.get("chapter") or {})
            return json.loads(json.dumps({
                "cefr": user.cefr_estimate,
                "season_index": story.get("season_index"),
                "season_stage": story.get("season_stage"),
                "day_index": story.get("day_index"),
                "chapters_total": story.get("chapters_total"),
                "chapter": {k: chapter.get(k) for k in (
                    "id", "shape", "interlude", "interlude_beat_id", "finale", "resolved", "exhausted",
                    "index_in_season", "dramatic_question",
                )},
                "interlude": story.get("interlude"),
                "interludes": story.get("interludes"),
                "season_premiere": story.get("season_premiere"),
                "seasons": story.get("seasons"),
                "world_flags": story.get("world_flags"),
                "threads_archive": story.get("threads_archive"),
                "season_ended": season.get("ended"),
                "season_played_tail": (season.get("played") or [])[-3:],
                "world": {
                    "version": world.get("world_bible_version"),
                    "number": world.get("season_number"),
                    "source": world.get("season_source"),
                    "title_fr": world.get("season_title_fr"),
                    "logline_fr": world.get("season_logline_fr"),
                    "arcs": world.get("season_arcs"),
                    "situation": engine.season_situation(world) if world else None,
                },
            }, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8021)
    args = parser.parse_args()
    global LEDGER
    if MODE not in ("fake", "live"):
        sys.exit("SEASON_END_MODE is fake or live.")
    if OUT is None:
        sys.exit("SEASON_END_OUT is required.")
    OUT.mkdir(parents=True, exist_ok=True)
    guard_database()
    production_environment()
    if MODE == "live":
        if CAP <= 0:
            sys.exit("A live walk needs SEASON_END_MAX_USD.")
        shared_env_keys()
    else:
        import dev_story_engine_server

        keep = dict(os.environ)
        dev_story_engine_server._guard_environment()
        for key in ("STORY_WRITER_MODEL", "STORY_CRITIC_MODEL", "STORY_LIVE_MODEL"):
            os.environ[key] = keep.get(key, os.environ.get(key, ""))
        # No key is real here and nothing may try: the fake answers the story's schemas.
        os.environ["ATELIER_LLM_ENABLED"] = "false"
        os.environ["ATELIER_CORRECTION_LLM_ENABLED"] = "false"
        os.environ["ATELIER_STORY_ENGINE_ENABLED"] = "true"
        os.environ.update(OVERRIDES)
    os.environ.setdefault("ATELIER_DAILY_JOURNEY_COHORT", "*")
    subprocess.run(  # noqa: S603 - our own script, fixed argv, no shell
        [sys.executable, "scripts/import_french_core_grammar.py", "--backfill-blueprints"],
        cwd=REPO, env=os.environ, stdout=subprocess.DEVNULL, check=False,
    )

    import uvicorn

    install_allowlist()
    from app.main import app

    if MODE == "live":
        LEDGER = Ledger()
        install_live_guard()
    else:
        install_fake_provider()
    add_walk_routes(app)
    threading.Thread(target=lock_sampler, args=(os.environ["DATABASE_URL"],), daemon=True).start()
    from app.config import settings

    print(
        f"[season-end] mode={MODE} cap={CAP} writer={settings.ATELIER_SEASON_WRITER_ENABLED} "
        f"lanes={settings.ATELIER_STORY_TURN_LANES_ENABLED} season={settings.ATELIER_SEASON_SCRIPT} "
        f"models=writer:{settings.STORY_WRITER_MODEL} critic:{settings.STORY_CRITIC_MODEL} live:{settings.STORY_LIVE_MODEL} "
        f"anthropic_key={bool(settings.ANTHROPIC_API_KEY)}",
        flush=True,
    )
    uvicorn.run(Timing(app), host=args.host, port=args.port, timeout_keep_alive=75)


if __name__ == "__main__":
    main()
