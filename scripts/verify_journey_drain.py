#!/usr/bin/env python
"""Prove the WP-18 drain: turning the daily journey off never strands a learner.

The rollout runbook (docs/implementation/atelier-v2/ROLLOUT.md §Drain) promises
that flipping ``ATELIER_DAILY_JOURNEY_ENABLED`` to ``false`` stops *creation*
only: a learner who is already inside today's journey can still read it, resume
it and finish it, the legacy ``today()`` envelope keeps answering, and a learner
who was never in the cohort sees no change at all. This driver proves that
against a real HTTP surface, a throwaway PostgreSQL database and the fake
provider — no paid call can leave the process.

It owns the server lifecycle: ``scripts/dev_story_engine_server.py`` is started,
stopped and restarted with different flag values, because ``journey_enabled_for``
reads ``settings`` and the settings object is built once per process. That is
exactly the production procedure (a Render env-var change restarts the service).

Usage (from the repository root):

    createdb atelier_wp18_$(date +%s)
    DATABASE_URL=postgresql://localhost/atelier_wp18_XXXX .venv/bin/alembic upgrade head
    .venv/bin/python scripts/verify_journey_drain.py \
        --database-url postgresql://localhost/atelier_wp18_XXXX

Exit code 0 means every check held. Nothing is downgraded to a warning. The
script refuses the owner's live ``language_learning`` database.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parent.parent
PASSWORD = "Verify-Journey-Drain-1!"  # noqa: S105 - throwaway account on a throwaway database
BOOT_TIMEOUT_SECONDS = 90


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class Report:
    rows: list[tuple[str, str, bool, str]] = field(default_factory=list)

    def record(self, phase: str, name: str, ok: bool, detail: str = "") -> bool:
        self.rows.append((phase, name, bool(ok), detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{f' — {detail}' if detail else ''}", flush=True)
        return bool(ok)

    @property
    def failed(self) -> list[tuple[str, str, bool, str]]:
        return [row for row in self.rows if not row[2]]

    def table(self) -> str:
        head = ("Phase", "Check", "Result", "Detail")
        body = [(phase, name, "PASS" if ok else "FAIL", detail) for phase, name, ok, detail in self.rows]
        widths = [max(len(str(row[i])) for row in [head, *body]) for i in range(4)]
        line = "-+-".join("-" * w for w in widths)

        def fmt(row: tuple[str, str, str, str]) -> str:
            return " | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)).rstrip()

        return "\n".join([fmt(head), line, *(fmt(row) for row in body)])


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


class Db:
    def __init__(self, url: str) -> None:
        if "language_learning" in url:
            sys.exit("Refusing to touch the owner's live language_learning database.")
        self.url = url
        self.engine = create_engine(url)

    def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    def one(self, sql: str, **params: Any) -> Any:
        return next(iter(self.rows(sql, **params)[0].values()))

    def execute(self, sql: str, **params: Any) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(sql), params)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


class Server:
    """The fake-provider dev server, started with an explicit flag state."""

    def __init__(self, *, database_url: str, host: str, port: int, log_path: Path) -> None:
        self.database_url = database_url
        self.host = host
        self.port = port
        self.log_path = log_path
        self.process: subprocess.Popen | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self, *, journey_enabled: bool, cohort: str = "") -> None:
        env = dict(os.environ)
        env.update(
            {
                "DATABASE_URL": self.database_url,
                "ATELIER_DAILY_JOURNEY_ENABLED": "true" if journey_enabled else "false",
                "ATELIER_DAILY_JOURNEY_COHORT": cohort,
                "ATELIER_STORY_ENGINE_ENABLED": "true",
                "APP_ENV": "development",
                "PYTHONUNBUFFERED": "1",
            }
        )
        handle = self.log_path.open("a")
        handle.write(
            f"\n=== server start enabled={journey_enabled} cohort={cohort or '(everyone)'} ===\n"
        )
        handle.flush()
        self.process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "dev_story_engine_server.py"),
                "--host",
                self.host,
                "--port",
                str(self.port),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        self._wait_for_health()

    def _wait_for_health(self) -> None:
        deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self.process is not None and self.process.poll() is not None:
                sys.exit(f"dev server exited early; see {self.log_path}")
            try:
                if httpx.get(f"{self.base_url}/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        self.stop()
        sys.exit(f"dev server did not become healthy on {self.base_url}; see {self.log_path}")

    def stop(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.process = None

    def restart(self, *, journey_enabled: bool, cohort: str = "") -> None:
        self.stop()
        self.start(journey_enabled=journey_enabled, cohort=cohort)


# ---------------------------------------------------------------------------
# Learner
# ---------------------------------------------------------------------------


class Learner:
    def __init__(self, server: Server, db: Db, email: str, *, cefr: str = "A1.1") -> None:
        self.server = server
        self.email = email
        self.client = httpx.Client(base_url=server.base_url, timeout=120)
        register = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "target_language": "fr",
                "native_language": "en",
                "cefr_estimate": cefr,
            },
        )
        if register.status_code not in (200, 201):
            raise SystemExit(f"register failed: {register.status_code} {register.text}")
        self.login()
        self.user_id = str(db.one("select id from users where email = :e", e=email))
        self.journey: dict[str, Any] = {}

    def login(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login", json={"email": self.email, "password": PASSWORD}
        )
        if response.status_code != 200:
            raise SystemExit(f"login failed: {response.status_code} {response.text}")
        self.headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def rebind(self) -> None:
        """After a server restart the port is the same; only the token matters."""

        self.client = httpx.Client(base_url=self.server.base_url, timeout=120)
        self.login()

    # -- HTTP helpers ---------------------------------------------------
    def get(self, path: str) -> httpx.Response:
        return self.client.get(path, headers=self.headers)

    def post(self, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        return self.client.post(path, headers=self.headers, json=body or {})

    # -- journey helpers ------------------------------------------------
    def create_body(self) -> dict[str, Any]:
        return {
            "mutation_id": uuid.uuid4().hex,
            "timezone": "Europe/Paris",
            "budget_seconds": 300,
            "preferred_input_mode": "text",
        }

    def create(self) -> httpx.Response:
        return self.post("/api/v1/daily-journeys", self.create_body())

    def today(self) -> httpx.Response:
        return self.get("/api/v1/daily-journeys/today")

    def refresh(self) -> dict[str, Any]:
        response = self.get(f"/api/v1/daily-journeys/{self.journey['id']}")
        if response.status_code != 200:
            raise SystemExit(f"refresh failed: {response.status_code} {response.text}")
        self.journey = response.json()
        return self.journey

    def current(self) -> dict[str, Any] | None:
        step_id = self.journey.get("current_step_id")
        if not step_id:
            return None
        return next((s for s in self.journey["steps"] if s["id"] == step_id), None)

    def advance(self) -> httpx.Response:
        step = self.current()
        response = self.post(
            f"/api/v1/daily-journeys/{self.journey['id']}/advance",
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": self.journey["revision"],
                "current_step_id": step["id"],
            },
        )
        if response.status_code == 200:
            self.journey = response.json()
        return response

    def attempt(self, answer: str) -> httpx.Response:
        step = self.current()
        response = self.post(
            f"/api/v1/daily-journeys/{self.journey['id']}/steps/{step['id']}/attempts",
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": self.journey["revision"],
                "input": {"mode": "text", "text": answer},
            },
        )
        return response

    def finish(self, kind: str = "complete") -> httpx.Response:
        return self.post(
            f"/api/v1/daily-journeys/{self.journey['id']}/finish",
            {
                "mutation_id": uuid.uuid4().hex,
                "expected_revision": self.journey["revision"],
                "finish_kind": kind,
            },
        )

    def play_to_end(self, answer: str) -> list[str]:
        """Advance/answer every remaining step; returns the kinds it walked."""

        walked: list[str] = []
        guard = 0
        while self.current() is not None and guard < 24:
            guard += 1
            step = self.current()
            walked.append(step["kind"])
            if step["kind"] == "respond":
                response = self.attempt(answer)
                if response.status_code != 200:
                    raise SystemExit(f"attempt failed: {response.status_code} {response.text}")
                self.refresh()
                if self.current() is not None and self.current()["id"] == step["id"]:
                    self.advance()
                continue
            response = self.advance()
            if response.status_code != 200:
                raise SystemExit(f"advance failed: {response.status_code} {response.text}")
        return walked


def free_port(host: str) -> int:
    """First free port in 8021-8059; other agents' servers are stepped over."""

    for candidate in range(8021, 8060):
        with socket.socket() as probe:
            try:
                probe.bind((host, candidate))
            except OSError:
                continue
            return candidate
    sys.exit("No free port in 8021-8059.")


def detail_of(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    detail = body.get("detail") if isinstance(body, dict) else None
    return detail if isinstance(detail, dict) else {}


# ---------------------------------------------------------------------------
# Phases
# ---------------------------------------------------------------------------


def phase_one(report: Report, db: Db, cohort: Learner, legacy: Learner) -> dict[str, Any]:
    """Flag ON, cohort = the cohort learner only."""

    phase = "1 · flag on"
    envelope = cohort.today().json()
    report.record(phase, "cohort learner: today() enabled", envelope.get("enabled") is True, str(envelope.get("enabled")))

    created = cohort.create()
    report.record(phase, "cohort learner: create journey", created.status_code in (200, 201), str(created.status_code))
    cohort.journey = created.json()
    cohort.refresh()
    first = cohort.current()
    report.record(
        phase,
        "cohort learner: journey active, scene step first",
        cohort.journey["status"] == "active" and bool(first) and first["kind"] == "scene",
        f"status={cohort.journey['status']} step={first and first['kind']}",
    )

    advanced = cohort.advance()
    report.record(
        phase,
        "cohort learner: one step advanced before the flip",
        advanced.status_code == 200 and cohort.journey["revision"] > created.json()["revision"],
        f"{advanced.status_code} revision {created.json()['revision']}->{cohort.journey['revision']}",
    )

    legacy_envelope = legacy.today().json()
    report.record(
        phase,
        "outside-cohort learner: today() disabled, no journey",
        legacy_envelope.get("enabled") is False and legacy_envelope.get("journey") is None,
        f"enabled={legacy_envelope.get('enabled')} journey={legacy_envelope.get('journey')}",
    )
    refused = legacy.create()
    report.record(
        phase,
        "outside-cohort learner: create refused 403 journey_disabled",
        refused.status_code == 403 and detail_of(refused).get("code") == "journey_disabled",
        f"{refused.status_code} {detail_of(refused).get('code')}",
    )

    baseline = legacy_baseline(report, phase, legacy)
    return {"steps_seen": len(cohort.journey["steps"]), "legacy": baseline}


def legacy_baseline(report: Report, phase: str, legacy: Learner) -> dict[str, Any]:
    """The legacy Séance start/resume path, recorded so it can be compared."""

    today = legacy.get("/api/v1/atelier/today")
    report.record(phase, "legacy learner: GET /atelier/today", today.status_code == 200, str(today.status_code))
    started = legacy.post("/api/v1/atelier/sessions", {})
    body = started.json() if started.status_code in (200, 201) else {}
    session_id = body.get("session_id")
    concepts = [c.get("id") for c in (body.get("concepts") or [])]
    exercise_sets = len(body.get("exercise_sets") or [])
    report.record(
        phase,
        "legacy learner: POST /atelier/sessions starts a real session",
        started.status_code in (200, 201) and bool(session_id) and exercise_sets > 0,
        f"{started.status_code} session={session_id} concepts={concepts} exercise_sets={exercise_sets}",
    )
    active = legacy.get("/api/v1/atelier/sessions/active")
    active_body = active.json() if active.status_code == 200 else {}
    active_session = (active_body or {}).get("session") or {}
    report.record(
        phase,
        "legacy learner: /atelier/sessions/active resumes that same session",
        active.status_code == 200 and active_session.get("session_id") == session_id,
        f"{active.status_code} id={active_session.get('session_id')}",
    )
    return {
        "session_id": session_id,
        "concepts": concepts,
        "exercise_sets": exercise_sets,
        "active_id": active_session.get("session_id"),
    }


def phase_two(report: Report, db: Db, cohort: Learner, legacy: Learner, baseline: dict[str, Any]) -> None:
    """Flag OFF for the whole service: the drain."""

    phase = "2 · drained"
    cohort.rebind()
    legacy.rebind()

    envelope = cohort.today()
    body = envelope.json()
    report.record(
        phase,
        "cohort learner: today() still answers 200",
        envelope.status_code == 200,
        str(envelope.status_code),
    )
    report.record(
        phase,
        "cohort learner: today() reports disabled but keeps the open journey",
        body.get("enabled") is False and (body.get("journey") or {}).get("id") == cohort.journey["id"],
        f"enabled={body.get('enabled')} journey={(body.get('journey') or {}).get('id')}",
    )

    read = cohort.get(f"/api/v1/daily-journeys/{cohort.journey['id']}")
    report.record(phase, "cohort learner: the journey is still readable", read.status_code == 200, str(read.status_code))
    cohort.refresh()

    scene_id = None
    listing = cohort.get(f"/api/v1/story-engine/episodes?journey_id={cohort.journey['id']}")
    episodes = listing.json().get("episodes", []) if listing.status_code == 200 else []
    if episodes:
        scene_id = episodes[0]["id"]
    report.record(
        phase,
        "cohort learner: the engine scene is still readable",
        listing.status_code == 200 and len(episodes) == 1 and len(episodes[0]["panels"]) >= 2,
        f"{listing.status_code} episodes={len(episodes)}",
    )
    if scene_id:
        position = cohort.client.put(
            f"/api/v1/story-engine/episodes/{scene_id}/position",
            headers=cohort.headers,
            json={"panel_index": 1},
        )
        report.record(
            phase,
            "cohort learner: reading position still saves",
            position.status_code == 200,
            str(position.status_code),
        )

    walked = cohort.play_to_end("Oui, je peux apporter les affiches samedi.")
    report.record(
        phase,
        "cohort learner: every remaining step completes while drained",
        "respond" in walked and cohort.current() is None,
        f"steps={walked}",
    )
    finished = cohort.finish("complete")
    report.record(
        phase,
        "cohort learner: finish accepted while drained",
        finished.status_code == 200,
        str(finished.status_code),
    )
    cohort.refresh()
    recap = cohort.journey.get("recap") or {}
    report.record(
        phase,
        "cohort learner: journey completed with a story outcome",
        cohort.journey["status"] == "completed" and bool(recap.get("story_outcome")),
        f"status={cohort.journey['status']} story_outcome={bool(recap.get('story_outcome'))}",
    )
    sessions = db.rows("select status from learning_sessions where user_id = :u", u=cohort.user_id)
    report.record(
        phase,
        "cohort learner: exactly one completed learning session",
        len(sessions) == 1 and sessions[0]["status"] == "completed",
        str(sessions),
    )

    refused = cohort.create()
    report.record(
        phase,
        "cohort learner: a new create is refused 403 journey_disabled",
        refused.status_code == 403 and detail_of(refused).get("code") == "journey_disabled",
        f"{refused.status_code} {detail_of(refused).get('code')}",
    )
    report.record(
        phase,
        "the refusal carries the documented message",
        detail_of(refused).get("message") == "The daily journey is not enabled for this account.",
        repr(detail_of(refused).get("message")),
    )
    retry = cohort.post(
        f"/api/v1/daily-journeys/{cohort.journey['id']}/retry", {"mutation_id": uuid.uuid4().hex}
    )
    report.record(
        phase,
        "regeneration (retry) is refused too",
        retry.status_code == 403 and detail_of(retry).get("code") == "journey_disabled",
        f"{retry.status_code} {detail_of(retry).get('code')}",
    )
    journeys = db.rows("select status from daily_journeys where user_id = :u", u=cohort.user_id)
    report.record(
        phase,
        "no journey row was deleted or downgraded by the flip",
        len(journeys) == 1 and journeys[0]["status"] == "completed",
        str(journeys),
    )

    legacy_envelope = legacy.today()
    legacy_body = legacy_envelope.json()
    report.record(
        phase,
        "legacy learner: today() unchanged (200, disabled, no journey)",
        legacy_envelope.status_code == 200
        and legacy_body.get("enabled") is False
        and legacy_body.get("journey") is None,
        f"{legacy_envelope.status_code} enabled={legacy_body.get('enabled')}",
    )
    now = legacy_baseline(report, phase, legacy)
    report.record(
        phase,
        "legacy learner: start/resume identical to the flag-on run",
        bool(now["session_id"])
        and now["session_id"] == baseline["session_id"]
        and now["active_id"] == baseline["active_id"]
        and now["concepts"] == baseline["concepts"]
        and now["exercise_sets"] == baseline["exercise_sets"],
        f"session={now['session_id']} concepts={now['concepts']} sets={now['exercise_sets']}",
    )


def phase_three(report: Report, db: Db, cohort: Learner) -> None:
    """Flag back ON: the next local day resumes the same serial thread."""

    phase = "3 · re-enabled"
    cohort.rebind()
    first_journey_id = cohort.journey["id"]
    thread_before = db.rows(
        "select id, current_episode_index, state from serial_threads where user_id = :u", u=cohort.user_id
    )
    report.record(
        phase,
        "one serial thread exists after day 1",
        len(thread_before) == 1,
        str([str(r["id"]) for r in thread_before]),
    )
    thread_id = str(thread_before[0]["id"]) if thread_before else ""
    events_before = ((thread_before[0]["state"] or {}).get("living_story") or {}).get("events", [])

    # Simulate the next learner-local day: date yesterday's rows one day back.
    # The journey's uniqueness and "one open journey" rules are keyed on
    # ``local_date``; nothing else in the engine reads wall-clock time here.
    db.execute(
        "update daily_journeys set local_date = local_date - 1 where user_id = :u", u=cohort.user_id
    )

    created = cohort.create()
    report.record(
        phase,
        "day 2: a new journey is created again",
        created.status_code in (200, 201) and created.json()["id"] != first_journey_id,
        f"{created.status_code} id={created.json().get('id') if created.status_code < 400 else created.text[:80]}",
    )
    cohort.journey = created.json()
    cohort.refresh()

    thread_after = db.rows(
        "select id, current_episode_index from serial_threads where user_id = :u", u=cohort.user_id
    )
    report.record(
        phase,
        "day 2 reuses the same serial thread (no second thread)",
        len(thread_after) == 1 and str(thread_after[0]["id"]) == thread_id,
        f"threads={[str(r['id']) for r in thread_after]}",
    )
    episodes = db.rows(
        "select status, episode_index from serial_episodes where thread_id = :t order by episode_index",
        t=thread_id,
    )
    report.record(
        phase,
        "day 2 is episode 2 of the same thread, day 1 stays completed",
        len(episodes) == 2
        and episodes[0]["status"] == "completed"
        and episodes[1]["episode_index"] == 1,
        str(episodes),
    )
    draft = db.rows(
        "select private_task->'scenario_brief'->'story_context'->'draft' as draft "
        "from daily_journey_steps where journey_id = :j "
        "and private_task ? 'scenario_brief' order by ordinal limit 1",
        j=cohort.journey["id"],
    )
    source_ids = (draft[0]["draft"] or {}).get("source_event_ids") if draft else None
    expected = [f"journey:{first_journey_id}:story"]
    report.record(
        phase,
        "day 2's scene continues day 1's story event",
        source_ids == expected,
        f"source_event_ids={source_ids}",
    )
    report.record(
        phase,
        "day 1's story event survived the whole flip cycle",
        len(events_before) == 1 and events_before[0]["id"] == expected[0],
        f"events={[e.get('id') for e in events_before]}",
    )
    scenes = db.rows(
        "select count(*) as n from graphic_novel_scenes where user_id = :u", u=cohort.user_id
    )
    report.record(
        phase,
        "exactly two engine scenes exist (one per day, none lost)",
        scenes[0]["n"] == 2,
        f"scenes={scenes[0]['n']}",
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="0 picks the first free port in 8021-8059. Never 8000 (another project) "
        "and never 8010 (the owner's backend).",
    )
    parser.add_argument(
        "--log",
        default=str(REPO_ROOT / "var" / "verify-journey-drain.log"),
        help="Where the dev server's output is written.",
    )
    args = parser.parse_args()

    if args.port in (8000, 8010):
        sys.exit("Refusing port 8000 (other project) / 8010 (the owner's backend). Use e.g. 8021.")
    port = args.port or free_port(args.host)

    db = Db(args.database_url)
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("")

    cohort_email = f"drain-cohort-{uuid.uuid4().hex[:8]}@example.com"
    legacy_email = f"drain-legacy-{uuid.uuid4().hex[:8]}@example.com"

    server = Server(database_url=args.database_url, host=args.host, port=port, log_path=log_path)
    report = Report()
    print(f"Server: {server.base_url} · database: {args.database_url}")
    try:
        print("\n1. Flag ON, cohort = one learner")
        server.start(journey_enabled=True, cohort=cohort_email)
        cohort = Learner(server, db, cohort_email)
        legacy = Learner(server, db, legacy_email)
        state = phase_one(report, db, cohort, legacy)

        print("\n2. ATELIER_DAILY_JOURNEY_ENABLED=false — the drain")
        server.restart(journey_enabled=False, cohort=cohort_email)
        phase_two(report, db, cohort, legacy, state["legacy"])

        print("\n3. Flag back ON — the next local day")
        server.restart(journey_enabled=True, cohort=cohort_email)
        phase_three(report, db, cohort)
    finally:
        server.stop()

    print("\n" + report.table())
    print(f"\n{len(report.rows) - len(report.failed)}/{len(report.rows)} checks passed")
    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
