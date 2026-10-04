"""EXPERIENCE-REVIEW 2026-10-04 — thirty days of a whole learner life, every surface.

Five personas × three qualities (strong, average, struggling), each a 30-day life
through sign-up, placement, the vocabulary check, La Une, the day, the drill, the
Courrier and the Cahier, with every app clock moved a day at a time. Runs with
the long walk (``-m walk`` or ``WALK=1``); ``EXPERIENCE_OUT=<dir>`` writes one JSON
per life plus ``summary.json`` (time by kind, intake, level) for the review.

The month is held to the learner-walk checks (:mod:`tests.walk_checks`) and to the
life invariants of :func:`tests.walk_checks.check_life`.
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
from tests import walk_checks, walk_checks_wp125b, walk_checks_wp126, walk_checks_wp131
from tests.test_learner_walk import (  # noqa: F401 - fixtures
    assembled_client,
    journey_enabled,
    production_day,
)
from tests.test_season_one import season_on  # noqa: F401 - fixture


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


def live(client, db, monkeypatch, persona, quality, provider, *, days: int = life.LIFE_DAYS) -> dict:
    headers, email = life.register_as_onboarding(client, persona)
    record: dict = {"persona": persona.key, "native": persona.native, "true_level": persona.cefr, "quality": quality, "days": []}
    answered: set[str] = set()
    met: set[str] = set()
    placed = False
    ladder_open = True
    for day in range(1, days + 1):
        test_clock.install()
        test_clock.set_offset_days(day - 1)
        rng = random.Random(f"life-{persona.key}-{quality}-{day}")
        today: dict = {"day": day}
        today["la_une"] = life.la_une(client, headers)
        # WP-126: at the start of a day the offer is already decided by the
        # endings before it; the walk records it, and takes it at the day's end.
        offer = client.get("/api/v1/placement/offer", headers=headers)
        today["placement_offered_at_start"] = bool(offer.status_code == 200 and offer.json().get("offer"))
        answerer = life.LifeAnswerer(quality, rng, native=persona.native)
        transcript = walk.play_day(
            client, db, headers, persona=persona, quality=quality, day=day, provider=provider, answerer=answerer
        )
        transcript["names_met_before"] = sorted(met)
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
    transcripts = [day["journey"] for day in record["days"]]
    problems += walk_checks.run_all(transcripts, db=db_session)
    assert not problems, "\n".join(problems[:60]) + (f"\n… {len(problems) - 60} more" if len(problems) > 60 else "")
