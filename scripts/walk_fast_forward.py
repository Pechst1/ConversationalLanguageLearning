"""The browser walk's fast-forward: a season learner's first days played through the API.

The season walk is split in two shards (web-frontend/e2e/lib/walk-scope.mjs). The second
one starts its learner on day 6 in the browser; this script plays days 1-5 for that
learner first, against the walk's own running stack (its API on the fake story provider,
its throwaway database), the way the browser walk plays a day and the backend learner
walk's helpers answer it:

* the scene, through the day's journey routes (tests.test_journey_end_to_end.Driver):
  «Le choix» answered by a card, picked as the browser walk picks it (the day plus the
  number of cards tapped that day, modulo the cards), the conversation with the browser
  walk's own replies, recall items answered right;
* the rest of the day as the browser walk plays it to its end: La Forge
  (tests.experience_walk.play_forge, «average»), the day's word deck
  (tests.experience_walk.drill, «average») and «Fertig» (POST session/words-done).

Each day is played on the walk's test clock (POST /dev/test-clock), as the browser walk
sets it. It prints one JSON line: per day, the season page the server served (its key,
kind, whether it was a reprise), the season's played-day count and the cards tapped, so
the walk can hold the tentpoles of days 1-5 to their days without having seen them.

    python scripts/walk_fast_forward.py --api http://127.0.0.1:PORT --db-url URL \
        --email E --password P --days 1-5

Test data only: the database URL must be one of the walk's throwaway databases.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.services.season import clock as season_clock  # noqa: E402
from tests import experience_walk as life  # noqa: E402
from tests import test_journey_end_to_end as support  # noqa: E402
from tests.test_season_one import _latest_scene, _season_state, _user_id_of  # noqa: E402

TZ = "Europe/Paris"
# The browser walk's own lines (web-frontend/e2e/lib/learner-walk.mjs REPLIES and FREE).
REPLIES = [
    "Oui, je peux vous aider samedi.",
    "Merci, à samedi !",
    "Avec plaisir, à bientôt.",
    "D’accord, je viens.",
]


class WalkClient(httpx.Client):
    """The walk's API, signed in as the learner. Access tokens live one minute on the
    walk (WP-107): a 401 signs in again and repeats the request once."""

    def __init__(self, base: str, email: str, password: str) -> None:
        super().__init__(base_url=base, timeout=120)
        self.email = email
        self.password = password
        self.headers_ = {"Authorization": ""}
        self.sign_in()

    def sign_in(self) -> None:
        response = super().request(
            "POST", "/api/v1/auth/login", json={"email": self.email, "password": self.password}
        )
        response.raise_for_status()
        self.headers_["Authorization"] = f"Bearer {response.json()['access_token']}"

    def request(self, method: str, url: Any, **kwargs: Any) -> httpx.Response:  # type: ignore[override]
        response = super().request(method, url, **kwargs)
        if response.status_code == 401 and "headers" in kwargs:
            self.sign_in()
            kwargs["headers"] = {**(kwargs["headers"] or {}), **self.headers_}
            response = super().request(method, url, **kwargs)
        # The API's rate limit runs on the wall clock, and an API day is played in a few
        # seconds where the browser takes minutes: wait as long as it asks, as a learner would.
        for _ in range(3):
            if response.status_code != 429:
                break
            try:
                wait = float((response.json().get("detail") or {}).get("retry_after_seconds") or 5)
            except (ValueError, AttributeError):
                wait = 5.0
            print(
                f"[fast-forward] rate limited on {method} {url}: waiting {wait:.0f}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(min(wait, 60) + 0.5)
            response = super().request(method, url, **kwargs)
        return response


def _days(spec: str) -> list[int]:
    first, _, last = spec.partition("-")
    return list(range(int(first), int(last or first) + 1))


def play_day(client: WalkClient, db, day: int, state: dict[str, Any]) -> dict[str, Any]:
    headers = client.headers_
    driver = support.Driver(client, headers, tz=TZ, db=db)
    cards_today = 0

    def answer(step: dict[str, Any]) -> str:
        nonlocal cards_today
        cards = (step.get("prompt") or {}).get("choices") or []
        if cards:
            pick = cards[(day + cards_today) % len(cards)]
            cards_today += 1
            return pick["label_fr"]
        line = REPLIES[state["replies"] % len(REPLIES)]
        state["replies"] += 1
        return line

    journey = driver.create()
    if journey.get("status") == "active":
        driver.play(answer=answer)
        response = driver.finish("complete")
        if response.status_code != 200:
            raise RuntimeError(
                f"day {day}: finish refused {response.status_code}: {response.text[:300]}"
            )
    rng = random.Random(f"walk-fast-forward-{day}")  # noqa: S311 - a seeded walk, not a secret
    today = client.get(
        "/api/v1/daily-journeys/today", headers=headers, params={"timezone": TZ}
    ).json()
    steps = {step["kind"]: step for step in ((today.get("session") or {}).get("steps") or [])}
    if steps.get("grammar", {}).get("state") != "done":
        life.play_forge(
            client, headers, today.get("forge") or {}, quality="average", native="en", rng=rng
        )
    life.drill(client, db, headers, quality="average", rng=rng)
    client.post("/api/v1/daily-journeys/session/words-done", headers=headers)
    client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": TZ})

    db.expire_all()
    user_id = state.get("user_id") or _user_id_of(db, driver.journey)
    state["user_id"] = user_id
    scene = _latest_scene(db, user_id)
    season = dict((scene.script_payload or {}).get("season") or {}) if scene else {}
    played = season_clock.played_log(_season_state(db, user_id))
    return {
        "day": day,
        "key": season.get("key"),
        "kind": season.get("kind"),
        "reprise": bool(season.get("reprise")),
        "played": len(played),
        "cards": cards_today,
        "status": driver.journey.get("status"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", required=True, help="the walk API's origin, without /api/v1")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--days", default="1-5")
    args = parser.parse_args(argv)
    if "/atelier_walk_" not in args.db_url:
        raise SystemExit("refusing a database that is not one of the walk's throwaway databases")

    engine = create_engine(args.db_url, pool_pre_ping=True)
    db = sessionmaker(bind=engine)()
    client = WalkClient(args.api.rstrip("/"), args.email, args.password)
    state: dict[str, Any] = {"replies": 0}
    rows = []
    try:
        for day in _days(args.days):
            t0 = time.monotonic()
            clock = client.post("/api/v1/dev/test-clock", json={"offset_days": day - 1})
            clock.raise_for_status()
            row = play_day(client, db, day, state)
            row["seconds"] = round(time.monotonic() - t0, 1)
            rows.append(row)
            print(
                f"[fast-forward] day {day}: {json.dumps(row, ensure_ascii=False)}",
                file=sys.stderr,
                flush=True,
            )
    finally:
        db.close()
        engine.dispose()
        client.close()
    print(json.dumps({"days": rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
