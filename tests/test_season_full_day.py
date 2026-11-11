"""#717: the season's tentpoles land on their days when the learner plays the whole day.

The browser walk (11 Nov 2026) played each day to its end (the scene, La Forge, the
day's word deck, «Fertig») and saw season 1's second tentpole on no day. The season was
not moved: the server served t2.a on day 9 and t2.b on day 10, in their A1 wording,
because the walker's scripted misses had pulled its estimate from A2 to A1, and the walk
looked for the A2 wording only (fixed in web-frontend/e2e/lib/season-pages.mjs). Day 7 was
lost because the walk's fake director repeated a recent situation (fixed in
scripts/dev_story_engine_server.py); a lost gap day re-reads the last page by design
(WP-124a), since no day of gap g1 has a contract stand-in.

This plays the same A2 life through the real routes with the scripted season provider,
whole days, with and without a lost day 7, and holds the tentpoles to the walk's days.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime

import pytest

from app.services.season import clock as season_clock
from tests import experience_walk as walk
from tests import test_journey_end_to_end as support
from tests.test_season_one import (  # noqa: F401 - fixture
    _latest_scene,
    _season_state,
    _user_id_of,
    season_on,
)

assembled_client = support.assembled_client
clock = support.clock
journey_enabled = support.journey_enabled


def _rest_of_the_day(client, db, headers, rng) -> None:
    """What the walk does after the scene: La Forge, the day's word deck, «Fertig»."""

    today = client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": support.TZ}).json()
    steps = {step["kind"]: step for step in ((today.get("session") or {}).get("steps") or [])}
    if steps.get("grammar", {}).get("state") != "done":
        walk.play_forge(client, headers, today.get("forge") or {}, quality="average", native="en", rng=rng)
    walk.drill(client, db, headers, quality="average", rng=rng)
    client.post("/api/v1/daily-journeys/session/words-done", headers=headers)
    client.get("/api/v1/daily-journeys/today", headers=headers, params={"timezone": support.TZ})


def _life(assembled_client, db_session, clock, provider, *, days: int, lost: tuple[int, ...] = ()) -> list[dict]:
    """Whole days: the scene, then La Forge, the word deck and «Fertig»."""

    provider.routes = {"Odile, c'est ma grand-mère.": "a"}
    headers = support.register(assembled_client, f"s1-full-{uuid.uuid4()}@example.com", cefr="A2.1")
    d = support.Driver(assembled_client, headers, db=db_session)
    rng = random.Random(7)
    rows: list[dict] = []
    user_id = None
    for day in range(1, days + 1):
        provider_day_start = clock.moment
        original = provider._season_draft
        if day in lost:
            def refused(context):
                from app.services.llm_service import LLMProviderError

                raise LLMProviderError("test: every draft of this day is refused")

            provider._season_draft = refused
        try:
            journey = _play_the_scene(d, provider)
        finally:
            provider._season_draft = original
        user_id = user_id or _user_id_of(db_session, journey)
        scene = _latest_scene(db_session, user_id)
        season = dict((scene.script_payload or {}).get("season") or {})
        _rest_of_the_day(assembled_client, db_session, headers, rng)
        state = _season_state(db_session, user_id)
        rows.append(
            {
                "day": day,
                "date": provider_day_start.date().isoformat(),
                "key": season.get("key"),
                "kind": season.get("kind"),
                "reprise": bool(season.get("reprise")),
                "played": len(season_clock.played_log(state)),
            }
        )
        clock.advance(days=1)
    return rows


def _play_the_scene(d, provider):
    """``test_season_one._play`` without its clock step: the rest of the day comes first."""

    from tests.test_living_story_longitudinal import TurnScript

    provider.turn = TurnScript(reply_fr="D'accord.", resolution_fr="La journée se termine.", callback_fr="Vous avez parlé.")
    d.create()
    assert d.journey["status"] == "active", d.journey
    d.play(answer="Odile, c'est ma grand-mère.")
    response = d.finish("complete")
    assert response.status_code == 200, response.text
    return d.journey


@pytest.mark.parametrize("lost", [(), (7,)], ids=["no-lost-day", "day-7-lost"])
def test_the_second_tentpole_lands_on_its_day_when_the_whole_day_is_played(
    assembled_client, db_session, journey_enabled, clock, season_on, lost  # noqa: F811 - fixtures
):
    # The walk's first day: Wednesday 11 November 2026, as the browser walk played it.
    clock.moment = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
    rows = _life(assembled_client, db_session, clock, season_on, days=10, lost=lost)
    keys = {row["key"]: row["day"] for row in rows if not row["reprise"]}
    # The first tentpole on its two days, and a lost day re-read, never settled.
    assert (keys.get("t1.a"), keys.get("t1.b")) == (1, 2), rows
    assert [row["played"] for row in rows][-1] == (9 if lost else 10), rows
    assert keys.get("t2.a") in (7, 8, 9), rows
    assert keys.get("t2.b") in (8, 9, 10), rows
