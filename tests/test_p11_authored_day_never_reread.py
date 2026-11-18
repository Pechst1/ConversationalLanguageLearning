# ruff: noqa: F811 - fixtures are imported by name and requested as arguments
"""P11 · an authored day is never served as a re-read.

17 Nov walk (b1-part3, season day 58): «Relecture — Aujourd'hui, on relit «Huit
heures» … L'histoire n'avance pas aujourd'hui» where T8 A («Ce qu'on garde») was
due. Reproduced from the code: the test tool's jump filled g7 to its nominal five
days; day 58 fell on a Friday, so the weekend flex added a sixth, *generated* g7
day; the director failed it, and WP-124a re-read the last page (T7 B). Day 59, a
Saturday, served T8 A. The fault is not a missing band variant: the authored day
was never asked for.

* a lost weekend-flex day is the next tentpole at once (prerequisites holding);
* a tentpole or epilogue day is never ``season_reprise``: it is served as written,
  or stays the honest «unavailable, retry» day;
* a page authored only for another band is served in the nearest band's variant.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.season import runtime as season_runtime
from app.services.season.clock import nominal_calendar, position
from app.services.season.format import load_season
from app.services.season.recovery import AUTHORED_DAY_LOST, FLEX_DAY_LOST, decide
from app.services.season.reprise import REPRISE_FALLBACK_KIND
from tests.test_season_one import _season_state, season_on  # noqa: F401 - fixture
from tests.test_wp124a_season_reprise import _director_fails
from tests.test_wp124b_recovery import (  # noqa: F401 - fixtures
    _day,
    _jumped_driver,
    _marker,
    assembled_client,
    clock,
    journey_enabled,
)

THURSDAY = datetime(2026, 11, 26, 9, 0, tzinfo=UTC)
FRIDAY = date(2026, 11, 27)


def _played(n_days: int) -> dict:
    rows = nominal_calendar(load_season("s1"))[:n_days]
    return {"id": "s1", "played": [{**row, "flex": 0, "event_id": f"e{row['season_day']}"} for row in rows], "flags": {}}


def _day_of(key: str) -> int:
    return next(row["season_day"] for row in nominal_calendar(load_season("s1")) if row["key"] == key)


def test_the_policy_serves_an_authored_day_and_skips_a_lost_flex_day():
    season = load_season("s1")
    # T8 A is due: an authored page, served as written on its first loss.
    on_t8 = _played(_day_of("t8.a") - 1)
    pos = position(season, on_t8, today=date(2026, 11, 25))
    assert pos.key == "t8.a"
    decision = decide(season, on_t8, pos, failures_before=0)
    assert (decision.kind, decision.reason, decision.position.key) == ("tentpole", AUTHORED_DAY_LOST, "t8.a")
    # g7 at its nominal length on a Friday: the flex adds a generated day; lost, T8 A.
    flexed = position(season, on_t8, today=FRIDAY)
    assert flexed.is_gap and flexed.flex == 1, flexed.key
    lost = decide(season, on_t8, flexed, failures_before=0)
    assert (lost.kind, lost.reason, lost.position.key) == ("tentpole", FLEX_DAY_LOST, "t8.a")


def test_the_friday_after_g7_serves_t8_a_not_a_reread_of_huit_heures(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
):
    clock.moment = THURSDAY
    d, user = _jumped_driver(assembled_client, db_session, day=57, cefr="B1.2")
    _day(d, clock)  # g7.5, Thursday
    assert position(load_season("s1"), _season_state(db_session, user.id), today=FRIDAY).key == "g7.6"
    _director_fails(season_on, monkeypatch)

    d.create()
    marker = _marker(db_session, d.journey["id"])
    assert d.journey["status"] == "active", d.journey
    assert marker.get("kind") != REPRISE_FALLBACK_KIND, marker
    assert marker["recovery"] == "tentpole" and marker["page_key"] == "t8.a"
    assert d.journey["scenario"]["title_fr"] != "Huit heures"


def test_a_tentpole_day_whose_page_cannot_be_built_is_never_a_reread(
    assembled_client, db_session, journey_enabled, clock, season_on, monkeypatch
):
    d, _user = _jumped_driver(assembled_client, db_session, day=_day_of("t8.a"), cefr="A1.1")
    monkeypatch.setattr(season_runtime, "page_for", lambda today: None)
    _director_fails(season_on, monkeypatch)

    d.create(expect=(200, 201, 202, 503))
    marker = _marker(db_session, d.journey["id"]) if d.journey.get("id") else {}
    assert marker.get("kind") != REPRISE_FALLBACK_KIND, marker
    assert d.journey.get("status") in (None, "unavailable"), d.journey


def test_a_page_authored_for_another_band_is_served_in_the_nearest_band(monkeypatch):
    asked: list[str] = []

    def resolve(season, segment_id, letter, *, flags, band, language, neutral=False):
        asked.append(band)
        return {"band": band} if band == "B1" else None

    monkeypatch.setattr(season_runtime, "resolve_day", resolve)
    today = SimpleNamespace(
        pos=SimpleNamespace(is_tentpole=True, segment=SimpleNamespace(id="t8"), tentpole_day="a", key="t8.a"),
        season=None,
        flags={},
        band="A1",
        language="fr",
        neutral=False,
    )
    assert season_runtime.page_for(today) == {"band": "B1"}
    assert asked == ["A1", "A2", "B1"], "the learner's band first, then the nearest"
