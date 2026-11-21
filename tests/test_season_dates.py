"""Round 4 (third real-model walk, 19 Nov 2026, item 9): the season's opening dates
follow the learner's own start.

The walk's B1 learner started on 19 November and read, at the end of day 2,
«Retour : mercredi 18 novembre» — a return ticket in the past. The dates of the
season's opening stretch (T1–T4, gaps 1–4, the ticket and its move) are tokens in the
season data, rendered per learner by whole weeks (``app.services.season.dates``).
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services.season import dates
from app.services.season.bridges import bridge_page, load_bridges
from app.services.season.clock import Position
from app.services.season.director import gap_brief
from app.services.season.flags import apply_sets, stored_flags
from app.services.season.format import SEASON_ROOT, load_season
from app.services.season.page import resolve_day

FOLDER = SEASON_ROOT / "s1"
BANDS = ("A1", "A2", "B1", "B2", "C1")
#: The walk's start (B1 learner, 19 Nov) and the pilot's likely start.
STARTS = (date(2026, 11, 19), date(2026, 11, 24))


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def _season_files() -> list[Path]:
    return sorted(path for path in FOLDER.glob("*.json") if path.name != "lexicon.json")


def _played(start: date) -> dict:
    return {
        "id": "s1",
        "played": [{"key": "t1.a", "segment": "t1", "date": start.isoformat(), "event_id": "e1"}],
    }


# ---------------------------------------------------------------------------
# The calendar
# ---------------------------------------------------------------------------


def test_the_bible_reads_as_written_at_its_own_start() -> None:
    assert dates.shift_days(dates.ANCHOR) == 0
    assert dates.shift_days(None) == 0
    assert dates.render_text("Retour : {date:2026-11-18}") == "Retour : mercredi 18 novembre"
    assert dates.render_text("{date:2026-12-02|fr-cap}, alors.") == "Mercredi 2 décembre, alors."
    assert dates.render_text("{date:2026-12-01|fr-dm}") == "1er décembre"


@pytest.mark.parametrize("offset", range(0, 60))
def test_the_ticket_is_a_wednesday_about_a_week_after_any_start(offset: int) -> None:
    start = dates.ANCHOR + timedelta(days=offset)
    shift = dates.shift_days(start)
    ticket = date(2026, 11, 18) + timedelta(days=shift)
    assert ticket.weekday() == 2  # «mercredi prochain», «Le mercredi, je n'ai pas classe»
    assert 4 <= (ticket - start).days <= 10, (start, ticket)
    # Day 2 (the day the ticket is shown) is never on or after it.
    assert ticket > start + timedelta(days=1)


def test_the_walks_learner_reads_a_ticket_in_the_future() -> None:
    """The walk's B1 learner (started Thursday 19 Nov) read «Retour : mercredi 18 novembre»."""

    season = load_season("s1")
    shift = dates.shift_for(_played(date(2026, 11, 19)))
    page = resolve_day(season, "t1", "b", flags={}, band="B1", language="en", shift=shift)
    text = json.dumps(page, ensure_ascii=False)
    assert "Retour : mercredi 25 novembre" in text
    assert "18 novembre" not in text
    pilot = resolve_day(
        season, "t1", "b", flags={}, band="A1", language="de", shift=dates.shift_days(STARTS[1])
    )
    assert "Retour : mercredi 2 décembre" in json.dumps(pilot, ensure_ascii=False)


def test_the_ticket_is_stored_and_moved_on_the_learners_calendar() -> None:
    season = load_season("s1")
    state = apply_sets(
        season, _played(STARTS[1]), season.tentpoles["t1"].state_out, source="t1/state_out"
    )
    assert stored_flags(state)["user.return_ticket"] == "mercredi 2 décembre"
    moment = next(row for row in load_bridges("s1")["g1"].moments if row.premise == "le_billet")
    moved = apply_sets(
        season, state, {fact.flag: fact.value for fact in moment.fixed}, source="g1/bridge"
    )
    assert stored_flags(moved)["user.return_ticket"] == "mercredi 16 décembre"
    settles = next(row for row in season.gaps["g1"].premises if row.id == "le_billet").settles
    assert (
        stored_flags(apply_sets(season, state, settles, source="g1"))["user.return_ticket"]
        == "mercredi 16 décembre"
    )
    # No start known (an old state, a fixture): the bible's own dates, never a token.
    assert (
        stored_flags(apply_sets(season, {}, settles, source="g1"))["user.return_ticket"]
        == "mercredi 2 décembre"
    )


# ---------------------------------------------------------------------------
# Guards: no token reaches a learner, no stray calendar date in the data
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", _season_files(), ids=lambda path: path.name)
def test_every_token_is_well_formed_and_renders(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    for text in _strings(raw):
        found = dates.ANY_TOKEN.findall(text)
        good = [
            match.group(0)
            for match in dates.TOKEN.finditer(text)
            if (match.group(2) or "fr") in dates.FORMATS
        ]
        assert found == good, f"{path.name}: malformed date token in «{text}»"
    for shift in (0, 7, 14, 21):
        assert not dates.has_token(dates.render(raw, shift)), path.name


@pytest.mark.parametrize("start", STARTS)
def test_no_token_on_any_served_page_brief_or_bridge(start: date) -> None:
    season = load_season("s1")
    state = _played(start)
    shift = dates.shift_for(state)
    for tentpole_id, tentpole in season.tentpoles.items():
        for day in {row.day for row in tentpole.days}:
            for band in BANDS:
                for language in ("en", "de"):
                    page = resolve_day(
                        season,
                        tentpole_id,
                        day,
                        flags={},
                        band=band,
                        language=language,
                        shift=shift,
                    )
                    assert not dates.has_token(page), (tentpole_id, day, band)
    for bridge in load_bridges("s1").values():
        page = bridge_page(
            season,
            bridge,
            [moment.premise for moment in bridge.moments],
            flags={},
            band="A2",
            language="en",
            shift=shift,
        )
        assert not dates.has_token(page), bridge.gap
    for index, segment in enumerate(season.segments):
        if segment.kind != "gap":
            continue
        for day in range(1, segment.days + 1):
            pos = Position(season.id, segment, index, day, day + 2)
            brief = gap_brief(season, pos, flags={}, state=state, seed="seed", band="A2")
            assert not dates.has_token(brief), (segment.id, day)


_FR = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
_EN = "January|February|March|April|June|July|August|September|October|November|December"
_DE = "Januar|Februar|März|Juni|Juli|Oktober|Dezember"
_ABBR = "janv|févr|avr|juil|sept|oct|nov|déc"
#: An absolute day-and-month in French, English or German («18 novembre», «2 December»,
#: «2. Dezember», «18 nov.»).
_MONTH_DAY = re.compile(
    rf"\b(\d{{1,2}}(?:er)?\.? (?:{_FR}|{_EN}|{_DE})(?![a-zà-ÿ])|\d{{1,2}}(?:er)? (?:{_ABBR})\.|(?:{_EN}) \d{{1,2}}\b)"
)

#: The dates that stay absolute, with the reason. Everything up to T4 follows the
#: learner's start (tokens); from T5 the season is tied to the holidays and the year's
#: end, and the backstory's dates are the past.
FIXED_DATES: dict[str, str] = {
    # T5 onward and the ending: Lila's Berlin deadline and start, Christmas, the
    # réveillon, the Mistral closing, Solvel's offer, Lila's train, the epilogue week.
    "13 décembre": "T5 Day A (Berlin letter), tied to the Berlin deadline",
    "14 décembre": "T5 Day B",
    "14 December": "T5 Day B (authoring note)",
    "15 décembre": "Lila's Berlin deadline (T5)",
    "15 December": "Lila's Berlin deadline (T5)",
    "15. Dezember": "Lila's Berlin deadline (T5)",
    "18 December": "Lila's last school day before Christmas (gap 5)",
    "22 décembre": "T6 Day A, the Christmas week",
    "23 décembre": "T6 Day B, the Christmas week",
    "31 décembre": "T7, the réveillon",
    "31 December": "T7, the réveillon",
    "31. Dezember": "T7, the réveillon",
    "1er janvier": "T7 Day B, New Year's Day",
    "4 janvier": "gap 5: the ticket after the new year",
    "7 janvier": "the Mistral's last day before the signing",
    "7 January": "the Mistral's last day before the signing",
    "7. Januar": "the Mistral's last day before the signing",
    "8 janvier": "Solvel's offer ends and Lila's train leaves (the season's end)",
    "8 January": "Solvel's offer ends and Lila's train leaves (the season's end)",
    "8. Januar": "Solvel's offer ends and Lila's train leaves (the season's end)",
    "9 janvier": "Berlin residency starts; epilogue week",
    "9 January": "Berlin residency starts",
    "9. Januar": "Berlin residency starts",
    "10 janvier": "epilogue week",
    "10 janv.": "epilogue week",
    "12 janvier": "epilogue week",
    "13 janvier": "epilogue week",
    "13 janv.": "epilogue week",
    "14 janvier": "epilogue week",
    "15 janvier": "epilogue week",
    "15 janv.": "epilogue week",
    "15 January": "epilogue week",
    # The backstory: dates in the past (Polaroids, the fire, Odile's life).
    "12 April": "backstory (a Polaroid's date)",
    "12. April": "backstory (a Polaroid's date)",
    "13 mars": "backstory (the fire)",
    "13 March": "backstory (the fire)",
    "13. März": "backstory (the fire)",
    "14 mars": "backstory",
    "14 March": "backstory",
    "14. März": "backstory",
    "15 mars": "backstory",
    "15 March": "backstory",
    "15. März": "backstory",
    "31 mars": "backstory",
    "31 March": "backstory",
    "31. März": "backstory",
}
#: Whole files or fields that document the bible's calendar and are served to nobody.
FIXED_PLACES: dict[tuple[str, str], str] = {
    (
        "season.json",
        "story_dates",
    ): "planning table of the bible's calendar (``Segment.story_dates``), never served",
    (
        "t1.json",
        "11 November is a public holiday",
    ): "T1's state_in, an authoring note no brief reads (no gap precedes T1)",
}


def test_no_absolute_date_in_the_season_data_unless_fixed_with_a_reason() -> None:
    stray: list[str] = []
    for path in _season_files():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "season.json":
            for segment in raw.get("segments") or []:
                segment.pop("story_dates", None)
            for flag in raw.get("flags") or []:
                flag.pop("set_where", None)  # «T1 (18 nov.)»: where a flag is set, for authors
        for text in _strings(raw):
            if any(name == path.name and marker in text for (name, marker) in FIXED_PLACES):
                continue
            for found in _MONTH_DAY.findall(text):
                if found not in FIXED_DATES:
                    stray.append(f"{path.name}: «{found}» in «{text[:90]}»")
    assert not stray, "absolute dates outside the whitelist:\n" + "\n".join(stray)
