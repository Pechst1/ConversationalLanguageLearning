"""EXPERIENCE-REVIEW 2026-10-04 — thirty days of a whole learner life, every surface.

Five personas × three qualities (strong, average, struggling), each a 30-day life
through sign-up, placement, the vocabulary check, La Une, the day, the drill, La
Forge (WP-123b), the Courrier and the Cahier, with every app clock moved a day at a
time. Runs with the long walk (``-m walk`` or ``WALK=1``); ``EXPERIENCE_OUT=<dir>``
writes one JSON per life plus ``summary.json`` (time by kind, intake, level) for
the review.

The month is held to the learner-walk checks (:mod:`tests.walk_checks`) and to the
life invariants of :func:`tests.walk_checks.check_life`.

The command set (WP-123b; from the repository root, ``PY`` = the venv python):

* all 15 lives — ``WALK=1 EXPERIENCE_OUT=<dir> $PY -m pytest tests/test_experience_walk.py -m walk``;
* a pull request's three — ``… -k "a1-de-fresh-average or b1-en-struggling or c1-de-strong"``;
* **a forced total outage** (every generated scene refused; WP-124b's checks run) —
  ``WALK_FAIL_RATE=1 WALK=1 … -k "b1-en-average"``; ``WALK_FAIL_RATE=0.3`` loses
  three days in ten instead. The Courrier always runs on its provider-off path in
  this walk (``ATELIER_LLM_ENABLED`` is off in tests), so every letter is already an
  outage letter;
* **La Forge played** from the after-day chip at the drill's cadence — ``WALK_FORGE=1 …``
  (opt-in until the La Forge defects in WP-123b-RESULTS.md are fixed; then the default);
* a shorter life — ``LIFE_DAYS=<n>``.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

import pytest

from app.core import test_clock
from tests import experience_walk as life
from tests import learner_walk as walk
from tests import (
    walk_checks,
    walk_checks_wp123b,
    walk_checks_wp124b,
    walk_checks_wp125b,
    walk_checks_wp126,
    walk_checks_wp128,
    walk_checks_wp129,
    walk_checks_wp130a,
    walk_checks_wp130b,
    walk_checks_wp131,
)
from tests.test_learner_walk import (  # noqa: F401 - fixtures
    assembled_client,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: F401 - fixture

#: WP-124b: a forced outage — the share of days whose generated scene is lost
#: (deterministic per life; 1 = every generated day). Off unless set.
WALK_FAIL_RATE = float(os.environ.get("WALK_FAIL_RATE") or 0)
#: WP-123b: the life plays La Forge when Home offers it (``WALK_FORGE=1``). Opt-in
#: until three La Forge defects the Forge walk found are fixed (the 5-minute chip
#: runs 5–14 minutes; English cues for German C1 learners; a give-up in a séance
#: comes back as a journey repair): see docs/implementation/atelier-v2/WP-123b-RESULTS.md.
WALK_FORGE = os.environ.get("WALK_FORGE", "0") == "1"


@pytest.fixture
def shifted_clock():
    """Every app clock, a whole number of days ahead (E-3's test clock), restored after."""

    import datetime as dt
    import sys

    test_clock.install()
    yield test_clock
    test_clock.set_offset_days(0)
    for name, module in list(sys.modules.items()):
        if module is None or not name.startswith("app."):
            continue
        for attr, stand_in, real in (
            ("datetime", test_clock.ShiftedDatetime, test_clock._REAL_DATETIME),
            ("date", test_clock.ShiftedDate, test_clock._REAL_DATE),
            ("_date", test_clock.ShiftedDate, test_clock._REAL_DATE),
        ):
            if getattr(module, attr, None) is stand_in:
                setattr(module, attr, real)
    del dt


def _to_local_noon(offset_days: int):
    """How far to move ``real now + offset_days`` to noon of the walk's day: the real
    local date plus ``offset_days`` calendar days, in the learner's zone."""

    import datetime as dt
    from zoneinfo import ZoneInfo

    from tests.test_journey_end_to_end import TZ

    zone = ZoneInfo(TZ)
    now = dt.datetime.now(dt.UTC)
    walk_date = now.astimezone(zone).date() + dt.timedelta(days=offset_days)
    noon = dt.datetime.combine(walk_date, dt.time(12), tzinfo=zone)
    return noon - (now + dt.timedelta(days=offset_days))


def live(client, db, monkeypatch, persona, quality, provider, *, days: int = life.LIFE_DAYS) -> dict:
    headers, email = life.register_as_onboarding(client, persona)
    record: dict = {"persona": persona.key, "native": persona.native, "true_level": persona.cefr, "quality": quality, "days": []}
    answered: set[str] = set()
    met: set[str] = set()
    placed = False
    ladder_open = True
    # WP-124b: the forced outage's lost days (none unless WALK_FAIL_RATE is set).
    down = life.outage_days(persona.key, quality, days, WALK_FAIL_RATE)
    if down:
        record["outage"] = {"rate": WALK_FAIL_RATE, "days": sorted(down)}
    for day in range(1, days + 1):
        test_clock.install()
        test_clock.set_offset_days(day - 1)
        # Every walk day is lived at local noon: a whole-day offset from a real "now"
        # near midnight crossed a daylight-saving change (2026-10-25) into the day
        # before, and the walk found that day already completed.
        test_clock._offset += _to_local_noon(day - 1)
        rng = random.Random(f"life-{persona.key}-{quality}-{day}")
        today: dict = {"day": day}
        today["la_une"] = life.la_une(client, headers)
        # WP-126: at the start of a day the offer is already decided by the
        # endings before it; the walk records it, and takes it at the day's end.
        offer = client.get("/api/v1/placement/offer", headers=headers)
        today["placement_offered_at_start"] = bool(offer.status_code == 200 and offer.json().get("offer"))
        answerer = life.LifeAnswerer(quality, rng, native=persona.native)
        with monkeypatch.context() as outage:
            if day in down:
                life.director_down(provider, outage)
            transcript = walk.play_day(
                client, db, headers, persona=persona, quality=quality, day=day, provider=provider, answerer=answerer
            )
        transcript["names_met_before"] = sorted(met)
        # WP-124b: the season cursor after the day (the walk check reads it).
        today["season"] = life.season_cursor(db, email)
        # WP-128: the plan's core estimate as Home, the plan and the ending carry it.
        today["time_budget"] = life.day_time_estimate(client, headers)
        # WP-126: the end-of-day transition — the offer surfaces right after the
        # ending (from the first one on). WP-127: one bounded visit of the
        # top-down check after the placement, resumed on later days if it paused.
        offer = client.get("/api/v1/placement/offer", headers=headers)
        today["placement_offer"] = offer.json() if offer.status_code == 200 else {"status_code": offer.status_code}
        today["placement_offered"] = bool(today["placement_offer"].get("offer"))
        if today["placement_offered"] and not placed:
            today["placement"] = life.take_placement(client, headers, monkeypatch, true_band=persona.cefr, quality=quality)
            placed = True
        if placed and ladder_open:
            today["band_check"] = life.take_band_checks(client, db, headers, email, quality=quality, rng=rng)
            last = (today["band_check"] or [{}])[-1]
            ladder_open = bool(today["band_check"]) and last.get("ladder_status") == "paused"
        met |= walk_checks.names_met(transcript)
        today["journey"] = transcript
        if quality != "struggling" or day % 2 == 1:
            today["drill"] = life.drill(client, db, headers, quality=quality, rng=rng)
        # WP-123b: La Forge, when Home offers it after the day (the Léger/Régulier
        # chip), played at the drill's cadence (WALK_FORGE=1).
        today["forge_offer"] = life.forge_offer(client, headers)
        offer_open = today["forge_offer"] and not today["forge_offer"].get("folded")
        if WALK_FORGE and offer_open and life.plays_forge(quality, day):
            today["forge"] = life.play_forge(
                client, headers, today["forge_offer"], quality=quality, native=persona.native, rng=rng
            )
        band = life.band_number(transcript.get("learner_level") or persona.cefr)
        today["courrier"] = life.courrier(client, headers, quality=quality, band=band, rng=rng, answered=answered)
        today["cahier"] = life.cahier(client, headers, full=day in (1, 7, 14, 30))
        if day in (15, 30):
            today["grammar_life"] = life.grammar_life(db, email)
        level = transcript.get("learner_level") or persona.cefr
        journey_clock, steps = life.time_journey(transcript, quality=quality)
        today["time"] = {
            "journey": journey_clock.as_dict(),
            "steps": steps,
            "drill": life.time_drill(today.get("drill") or {}, level, quality).as_dict(),
            "forge": life.time_forge(today.get("forge") or {}, level, quality).as_dict(),
            "letters": life.time_letters(today["courrier"], level, quality).as_dict(),
            "onboarding": life.time_onboarding(today, level, quality).as_dict(),
        }
        record["days"].append(today)
    return record


@pytest.fixture
def long_walk(request):
    """Skips *before* the heavy fixtures (catalogue, core lexicon, clock) are built."""

    selected = "walk" in str(request.config.getoption("-m") or "") or os.environ.get("WALK") == "1"
    if not selected:
        pytest.skip("the life walk runs with `-m walk` (or WALK=1)")


@pytest.mark.walk
@pytest.mark.parametrize("quality", life.LIFE_QUALITIES)
@pytest.mark.parametrize("persona", walk.PERSONAS, ids=lambda p: p.key)
def test_a_month_of_a_whole_life(
    long_walk, persona, quality, monkeypatch, assembled_client, db_session, journey_enabled, production_day, shifted_clock  # noqa: F811
):
    record = live(assembled_client, db_session, monkeypatch, persona, quality, production_day)
    out = os.environ.get("EXPERIENCE_OUT")
    if out:
        folder = Path(out)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"life-{persona.key}-{quality}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    problems = walk_checks.check_life(record)
    # WP-126/127: ≤ 48 check items a visit; no own-band offer to «Nouveau»; B2/C1 day one at its band.
    problems += walk_checks_wp126.check_life_wp126(record)
    problems += walk_checks_wp125b.check_letter_repeats(record)
    problems += walk_checks_wp125b.check_letter_levels(record)
    # WP-131: an average learner's new words do not swing on noise; no numeral blocks.
    problems += walk_checks_wp131.check_life_wp131(record)
    # WP-128: a core day within 20 % of its rhythm unless flagged longer; one core number.
    problems += walk_checks_wp128.check_life_wp128(record)
    # WP-130 A: the notebook and the level count the same units per state; no false «tenue».
    problems += walk_checks_wp130a.check_progress_labels_agree(record)
    # WP-129: B1+ practice volume and mix; one sentence per item; D7 reviews a met unit.
    problems += walk_checks_wp129.check_life_wp129(record)
    # WP-130 B: every held unit earned «Tenue» with unassisted, spaced evidence.
    problems += walk_checks_wp130b.check_held_evidence_chain(record)
    # WP-123b: La Forge opens, grades, ends, seats the chip's rule, fits its budget,
    # speaks the learner's language and never grades a give-up correct (WALK_FORGE=1).
    problems += walk_checks_wp123b.check_life_wp123b(record)
    if WALK_FAIL_RATE:
        # WP-124b: under a forced outage, lost days never stall the season.
        problems += walk_checks_wp124b.check_life_wp124b(record)
    transcripts = [day["journey"] for day in record["days"]]
    problems += walk_checks.run_all(transcripts, db=db_session)
    assert not problems, "\n".join(problems[:60]) + (f"\n… {len(problems) - 60} more" if len(problems) > 60 else "")
