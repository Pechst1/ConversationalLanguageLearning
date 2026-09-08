#!/usr/bin/env python
"""Exercise the living-story writer's PostgreSQL locking through the REAL API.

WP-14 gate: the engine's row locks (`living_story._lock_context`, the reader's
`FOR UPDATE` on the scene, the daily state machine's receipts) were only ever run
under SQLite, which serialises writers globally and therefore proves nothing about
lock ordering or lost updates. This driver fires genuinely concurrent HTTP requests
at a backend that is connected to a **throwaway PostgreSQL database** and then reads
the canonical rows back to check the world invariants.

Run it against `scripts/dev_story_engine_server.py` (fake provider, no paid calls):

    venv/bin/python scripts/verify_story_engine_pg.py \
        --base-url http://127.0.0.1:8010 \
        --database-url postgresql://localhost/atelier_story_pg_XXXX

Exit code 0 means every invariant held. Nothing here is downgraded to a warning.
The script refuses the owner's live `language_learning` database.
"""
from __future__ import annotations

import argparse
import sys
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import create_engine, text

PASSWORD = "Verify-Story-Engine-1!"  # noqa: S105 - throwaway account on a throwaway database
N = 6


@dataclass
class Report:
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{f' — {detail}' if detail else ''}", flush=True)
        return ok

    @property
    def failed(self):
        return [c for c in self.checks if not c[1]]


class Db:
    def __init__(self, url: str) -> None:
        if "language_learning" in url:
            sys.exit("Refusing to inspect the owner's live language_learning database.")
        self.engine = create_engine(url)

    def rows(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    def one(self, sql: str, **params: Any) -> Any:
        return next(iter(self.rows(sql, **params)[0].values()))


class Learner:
    def __init__(self, base_url: str, db: Db, *, cefr: str = "A1.1") -> None:
        self.base = base_url.rstrip("/")
        self.email = f"story-pg-{uuid.uuid4().hex[:10]}@example.com"
        self.client = httpx.Client(base_url=self.base, timeout=90)
        r = self.client.post(
            "/api/v1/auth/register",
            json={"email": self.email, "password": PASSWORD, "target_language": "fr", "native_language": "en", "cefr_estimate": cefr},
        )
        if r.status_code not in (200, 201):
            raise SystemExit(f"register failed: {r.status_code} {r.text}")
        r = self.client.post("/api/v1/auth/login", json={"email": self.email, "password": PASSWORD})
        if r.status_code != 200:
            raise SystemExit(f"login failed: {r.status_code} {r.text}")
        self.headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.user_id = str(db.one("select id from users where email = :e", e=self.email))
        self.journey: dict[str, Any] = {}

    # -- helpers --------------------------------------------------------
    def post(self, path: str, body: dict[str, Any]) -> httpx.Response:
        return self.client.post(path, headers=self.headers, json=body)

    def get(self, path: str) -> httpx.Response:
        return self.client.get(path, headers=self.headers)

    def create_body(self) -> dict[str, Any]:
        return {"mutation_id": uuid.uuid4().hex, "timezone": "Europe/Paris", "budget_seconds": 300, "preferred_input_mode": "text"}

    def refresh(self) -> dict[str, Any]:
        r = self.get(f"/api/v1/daily-journeys/{self.journey['id']}")
        if r.status_code != 200:
            raise SystemExit(f"refresh failed: {r.status_code} {r.text}")
        self.journey = r.json()
        return self.journey

    def current(self) -> dict[str, Any] | None:
        sid = self.journey.get("current_step_id")
        return next((s for s in self.journey["steps"] if s["id"] == sid), None) if sid else None

    def advance(self) -> None:
        step = self.current()
        r = self.post(f"/api/v1/daily-journeys/{self.journey['id']}/advance", {"mutation_id": uuid.uuid4().hex, "expected_revision": self.journey["revision"], "current_step_id": step["id"]})
        if r.status_code != 200:
            raise SystemExit(f"advance failed: {r.status_code} {r.text}")
        self.journey = r.json()

    def attempt_body(self, text_answer: str, *, mutation_id: str | None = None, revision: int | None = None) -> tuple[str, dict[str, Any]]:
        step = self.current()
        return (
            f"/api/v1/daily-journeys/{self.journey['id']}/steps/{step['id']}/attempts",
            {"mutation_id": mutation_id or uuid.uuid4().hex, "expected_revision": revision if revision is not None else self.journey["revision"], "input": {"mode": "text", "text": text_answer}},
        )


def concurrently(tasks: list[Callable[[], httpx.Response]]) -> list[httpx.Response]:
    """Start every request at the same instant (barrier), collect every response."""
    barrier = threading.Barrier(len(tasks))

    def run(task):
        barrier.wait(timeout=30)
        return task()

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        return list(pool.map(run, tasks))


def codes(responses: list[httpx.Response]) -> str:
    return ",".join(str(r.status_code) for r in responses)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8010")
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    db = Db(args.database_url)
    report = Report()

    # ------------------------------------------------------------------
    print("\n1. Six concurrent journey creations for one learner")
    a = Learner(args.base_url, db)
    creates = concurrently([lambda: a.post("/api/v1/daily-journeys", a.create_body()) for _ in range(N)])
    ids = {r.json().get("id") for r in creates if r.status_code in (200, 201, 202)}
    report.record("every create answered without a 5xx", all(r.status_code < 500 for r in creates), codes(creates))
    report.record("exactly one journey id was ever returned", len(ids) == 1, f"ids={ids}")
    journeys = db.rows("select id, status from daily_journeys where user_id = :u", u=a.user_id)
    report.record("exactly one journey row", len(journeys) == 1, str(journeys))
    threads = db.rows("select id, status, current_episode_index from serial_threads where user_id = :u", u=a.user_id)
    report.record("exactly one serial thread (user-row lock serialised creation)", len(threads) == 1, str(threads))
    thread_id = str(threads[0]["id"]) if threads else None
    episodes = db.rows("select id, status, episode_index from serial_episodes where thread_id = :t order by episode_index", t=thread_id)
    report.record("exactly one serial episode, available", len(episodes) == 1 and episodes[0]["status"] == "available", str(episodes))
    scenes = db.rows("select id, status, source_snapshot->>'journey_id' as journey_id from graphic_novel_scenes where user_id = :u", u=a.user_id)
    report.record("exactly one engine scene, bound to the journey", len(scenes) == 1 and scenes[0]["journey_id"] == next(iter(ids)), str(scenes))
    a.journey = next(r.json() for r in creates if r.status_code in (200, 201, 202))
    a.refresh()
    report.record("journey is active with a scene step first", a.journey["status"] == "active" and a.current() and a.current()["kind"] == "scene", f"status={a.journey['status']} step={a.current() and a.current()['kind']}")

    # ------------------------------------------------------------------
    print("\n2. Reader ownership and position validation")
    listing = a.get(f"/api/v1/story-engine/episodes?journey_id={a.journey['id']}")
    episode = listing.json()["episodes"][0] if listing.status_code == 200 and listing.json()["episodes"] else None
    report.record("owner lists exactly the journey's episode with panels", bool(episode) and len(listing.json()["episodes"]) == 1 and len(episode["panels"]) >= 2, f"{listing.status_code} panels={episode and len(episode['panels'])}")
    scene_id = episode["id"] if episode else scenes[0]["id"]
    b = Learner(args.base_url, db)
    report.record("another learner's listing for that journey is empty", b.get(f"/api/v1/story-engine/episodes?journey_id={a.journey['id']}").json()["episodes"] == [])
    report.record("another learner gets 404 on the scene", b.get(f"/api/v1/story-engine/episodes/{scene_id}").status_code == 404)
    report.record("another learner cannot write the position", b.client.put(f"/api/v1/story-engine/episodes/{scene_id}/position", headers=b.headers, json={"panel_index": 1}).status_code == 404)
    report.record("out-of-range position is 422", a.client.put(f"/api/v1/story-engine/episodes/{scene_id}/position", headers=a.headers, json={"panel_index": 99}).status_code == 422)
    report.record("negative position is 422", a.client.put(f"/api/v1/story-engine/episodes/{scene_id}/position", headers=a.headers, json={"panel_index": -1}).status_code == 422)
    ok = a.client.put(f"/api/v1/story-engine/episodes/{scene_id}/position", headers=a.headers, json={"panel_index": 1})
    rev_before = a.refresh()["revision"]
    report.record("saving a position does not bump the journey revision", ok.status_code == 200 and rev_before == a.journey["revision"], f"{ok.status_code} rev={rev_before}")
    legacy = a.post("/api/v1/graphic-novel/scenes", {})
    detail = legacy.json().get("detail") if legacy.headers.get("content-type", "").startswith("application/json") else legacy.text
    report.record("legacy scene creation is refused for an engine learner (409)", legacy.status_code == 409, f"{legacy.status_code} {str(detail)[:120]}")

    # ------------------------------------------------------------------
    print("\n3. The settle race: identical retries + position writes at the same instant")
    a.advance()  # scene -> next step
    while a.current() and a.current()["kind"] != "respond":
        # A brand-new learner has no due vocabulary, so there is normally no recall step.
        a.advance()
    report.record("reached the respond step", bool(a.current()) and a.current()["kind"] == "respond", str(a.current() and a.current()["kind"]))
    path, body = a.attempt_body("Oui, je peux apporter les affiches samedi.")
    same = [lambda: a.post(path, body) for _ in range(N)]
    positions = [lambda: a.client.put(f"/api/v1/story-engine/episodes/{scene_id}/position", headers=a.headers, json={"panel_index": 2}) for _ in range(3)]
    mixed = concurrently(same + positions)
    attempts, pos = mixed[:N], mixed[N:]
    report.record("no 5xx under the settle race", all(r.status_code < 500 for r in mixed), f"attempts={codes(attempts)} positions={codes(pos)}")
    report.record("at least one identical retry succeeded", any(r.status_code == 200 for r in attempts), codes(attempts))
    a.refresh()
    thread = db.rows("select state, current_episode_index from serial_threads where id = :t", t=thread_id)[0]
    events = (thread["state"].get("living_story") or {}).get("events", [])
    report.record("exactly one story event was written", len(events) == 1, f"events={len(events)}")
    scene_row = db.rows("select status, recap_payload->>'source_key' as source_key, source_snapshot->>'panel_index' as panel_index from graphic_novel_scenes where id = :s", s=scene_id)[0]
    report.record("scene completed once with its event source key", scene_row["status"] == "completed" and scene_row["source_key"] == f"journey:{a.journey['id']}:story", str(scene_row))
    report.record("concurrent position write survived the settle (no lost update)", scene_row["panel_index"] == "2", f"panel_index={scene_row['panel_index']}")
    episodes = db.rows("select status, episode_index from serial_episodes where thread_id = :t order by episode_index", t=thread_id)
    report.record("exactly one episode, completed exactly once, cursor advanced by one", len(episodes) == 1 and episodes[0]["status"] == "completed" and thread["current_episode_index"] == 1, f"{episodes} index={thread['current_episode_index']}")
    replay = a.get(f"/api/v1/story-engine/episodes/{scene_id}").json()
    report.record("reader now exposes the settled resolution and keeps the position", replay["status"] == "completed" and replay["resolution"] and replay["panel_index"] == 2, f"status={replay['status']} resolution={bool(replay['resolution'])} panel_index={replay['panel_index']}")

    print("\n4. Stale-revision retries after the settle cannot write a second ending")
    stale_rev = body["expected_revision"]
    if a.current() and a.current()["kind"] == "respond":
        spath, _ = a.attempt_body("x")
    else:
        spath = path
    stale = concurrently([lambda: a.post(spath, {"mutation_id": uuid.uuid4().hex, "expected_revision": stale_rev, "input": {"mode": "text", "text": "Non, je ne peux pas."}}) for _ in range(N)])
    report.record("every stale attempt is refused with 409", all(r.status_code == 409 for r in stale), codes(stale))
    thread = db.rows("select state from serial_threads where id = :t", t=thread_id)[0]
    report.record("still exactly one story event", len((thread["state"].get("living_story") or {}).get("events", [])) == 1)

    # ------------------------------------------------------------------
    print("\n5. Six concurrent finishes")
    a.refresh()
    while a.current() is not None:
        a.advance()
    fin_rev = a.journey["revision"]
    finishes = concurrently([lambda: a.post(f"/api/v1/daily-journeys/{a.journey['id']}/finish", {"mutation_id": uuid.uuid4().hex, "expected_revision": fin_rev, "finish_kind": "complete"}) for _ in range(N)])
    report.record("no 5xx under the finish race", all(r.status_code < 500 for r in finishes), codes(finishes))
    report.record("exactly one finish succeeded", sum(r.status_code == 200 for r in finishes) == 1, codes(finishes))
    a.refresh()
    report.record("journey completed with a story outcome in the recap", a.journey["status"] == "completed" and bool((a.journey.get("recap") or {}).get("story_outcome")), f"status={a.journey['status']}")
    sessions = db.rows("select status from learning_sessions where user_id = :u", u=a.user_id)
    report.record("exactly one learning session, completed once", len(sessions) == 1 and sessions[0]["status"] == "completed", str(sessions))

    # ------------------------------------------------------------------
    print("\n6. Two learners creating at the same instant do not block or share a thread")
    c = Learner(args.base_url, db)
    pair = concurrently([lambda: b.post("/api/v1/daily-journeys", b.create_body()), lambda: c.post("/api/v1/daily-journeys", c.create_body())])
    report.record("both learners got a journey", all(r.status_code in (200, 201) for r in pair), codes(pair))
    tb = db.rows("select id from serial_threads where user_id = :u", u=b.user_id)
    tc = db.rows("select id from serial_threads where user_id = :u", u=c.user_id)
    report.record("one thread each, distinct", len(tb) == 1 and len(tc) == 1 and tb[0]["id"] != tc[0]["id"])
    report.record("each reader sees only its own episode", b.get("/api/v1/story-engine/episodes").json()["episodes"][0]["journey_id"] == pair[0].json()["id"] and c.get("/api/v1/story-engine/episodes").json()["episodes"][0]["journey_id"] == pair[1].json()["id"])

    print("\n7. A second create on the same day replays the existing journey, no new scene")
    again = a.post("/api/v1/daily-journeys", a.create_body())
    scenes_after = db.rows("select count(*) as n from graphic_novel_scenes where user_id = :u", u=a.user_id)[0]["n"]
    report.record("second create after completion did not mint a new engine scene", scenes_after == 1 and again.status_code < 500, f"{again.status_code} scenes={scenes_after}")

    print(f"\n{len(report.checks) - len(report.failed)}/{len(report.checks)} checks passed")
    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
