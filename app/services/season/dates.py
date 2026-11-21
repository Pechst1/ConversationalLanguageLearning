"""The season's opening calendar, moved to the week the learner starts in.

The bible dates season 1 from Wednesday 11 November 2026 (``ANCHOR``): the return
ticket «Retour : mercredi 18 novembre», the move to «mercredi 2 décembre», the party
of Saturday 5 December. A learner who started on 19 November read a return ticket in
the past (walk of 19 Nov, item 9). The dates of that stretch are written in the season
data as tokens, ``{date:2026-11-18}``, and rendered for each learner moved by whole
weeks (``shift_days``): the Wednesday of day 1 becomes the Wednesday nearest the
learner's first day, so every weekday the story names («mercredi prochain», «Jeudi
prochain, dix-huit heures», «Le mercredi, je n'ai pas classe») stays true and every
interval between two dates stays as the bible wrote it.

Tokens: ``{date:YYYY-MM-DD}`` is the French date with its weekday («mercredi 18
novembre»); a format after a bar picks another form — ``fr-cap`` «Mercredi 18
novembre» (a sentence's start), ``fr-dm`` «18 novembre»,
``fr-abbr`` «18 nov.», ``en`` «Wednesday 18 November», ``en-dm`` «18 November», ``de``
«Mittwoch, 18. November», ``de-dm`` «18. November».

Only the stretch up to T4 is moved. From T5 on the season is tied to the holidays
(Lila's Berlin deadline, Christmas, the réveillon, Solvel's 8 January) and keeps the
bible's dates; ``tests/test_season_dates.py`` lists them with the reason.

Rendering with shift 0 gives the bible's text exactly: the bible check
(``fidelity``), the level variants' keys and the lexicon all read the data that way,
and every path that does not know the learner's start shows the bible's date rather
than a token. Pure functions; no database, no model.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

#: Day 1 of season 1 in the bible (T1 Day A, a Wednesday).
ANCHOR = date(2026, 11, 11)

TOKEN = re.compile(r"\{date:(\d{4}-\d{2}-\d{2})(?:\|([a-z-]+))?\}")
#: Anything that looks like a date token, well formed or not (the guard's net).
ANY_TOKEN = re.compile(r"\{date[^}]*\}")

_WEEKDAYS = {
    "fr": ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
    "de": ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"),
}
_MONTHS = {
    "fr": (
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ),
    "en": (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ),
    "de": (
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ),
}
_FR_ABBR = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)
FORMATS = ("fr", "fr-cap", "fr-dm", "fr-abbr", "en", "en-dm", "de", "de-dm")


def format_date(day: date, fmt: str = "fr") -> str:
    """One date in one of ``FORMATS``."""

    lang, _, form = fmt.partition("-")
    if fmt not in FORMATS:
        raise ValueError(f"unknown date format {fmt!r}")
    if lang == "fr":
        number = "1er" if day.day == 1 else str(day.day)
        if form == "abbr":
            return f"{number} {_FR_ABBR[day.month - 1]}"
        dm = f"{number} {_MONTHS['fr'][day.month - 1]}"
        if form == "dm":
            return dm
        weekday = _WEEKDAYS["fr"][day.weekday()]
        return f"{weekday.capitalize() if form == 'cap' else weekday} {dm}"
    if lang == "en":
        dm = f"{day.day} {_MONTHS['en'][day.month - 1]}"
        return dm if form == "dm" else f"{_WEEKDAYS['en'][day.weekday()]} {dm}"
    dm = f"{day.day}. {_MONTHS['de'][day.month - 1]}"
    return dm if form == "dm" else f"{_WEEKDAYS['de'][day.weekday()]}, {dm}"


def shift_days(start: date | None) -> int:
    """Whole weeks from the bible's day 1 to the Wednesday nearest ``start`` (never
    earlier than the bible). ``None`` (no start known): 0, the bible's own dates."""

    if not isinstance(start, date):
        return 0
    weeks = round((start - ANCHOR).days / 7)
    return max(0, weeks) * 7


def season_start(state: dict | None, today: date | None = None) -> date | None:
    """The learner's first season day: the date of the first day they played, else
    ``today`` (the first day itself is being served)."""

    for row in (state or {}).get("played") or []:
        if isinstance(row, dict) and row.get("date"):
            try:
                return date.fromisoformat(str(row["date"])[:10])
            except ValueError:
                continue
    return today if isinstance(today, date) else None


def shift_for(state: dict | None, today: date | None = None) -> int:
    return shift_days(season_start(state, today))


def render_text(text: str, shift: int = 0) -> str:
    def one(match: re.Match[str]) -> str:
        day = date.fromisoformat(match.group(1)) + timedelta(days=shift)
        return format_date(day, match.group(2) or "fr")

    return TOKEN.sub(one, text) if "{date" in text else text


def render(value: Any, shift: int = 0) -> Any:
    """``value`` (any JSON-like structure) with every date token rendered; a copy
    where something changed, the same object otherwise."""

    if isinstance(value, str):
        return render_text(value, shift)
    if isinstance(value, list):
        out = [render(item, shift) for item in value]
        return value if all(a is b for a, b in zip(out, value, strict=True)) else out
    if isinstance(value, dict):
        out = {key: render(item, shift) for key, item in value.items()}
        return value if all(out[key] is value[key] for key in value) else out
    return value


def has_token(value: Any) -> bool:
    if isinstance(value, str):
        return bool(ANY_TOKEN.search(value))
    if isinstance(value, list):
        return any(has_token(item) for item in value)
    if isinstance(value, dict):
        return any(has_token(item) for item in value.values())
    return False
