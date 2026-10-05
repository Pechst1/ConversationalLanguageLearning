"""The season on the learner's own day count (S-12), with the weekend flex.

The bible's calendar (§8) is a sequence of segments: tentpole (two days), gap
(generated days), tentpole… The season moves one day each time the learner
*finishes* a day — never on the wall clock — so a learner who skips a week comes
back to the next day of their story, not to a gap that ran on without them.

**The weekend flex.** "The engine may flex each gap by ±1 day so that a tentpole's
Day A falls on the learner's weekend when possible." When a gap would end on a
Friday, it gets one more day, so Day A lands on Saturday; when the last gap day
falls on a Saturday or a Sunday, the gap ends one day early, so Day A lands on the
weekend. Each gap flexes at most once, by one day. The decision is taken on the
learner's local date of the day being played (the prefetch passes the day it
prepares), and it is never stored: a gap's real length is simply how many of its
days were played before the tentpole began, which the played log already says.

Pure functions over ``live["season_script"]``; no database, no model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.season.format import Season, Segment

#: ``live[SEASON_KEY]`` holds the season a thread is playing and what it has played.
SEASON_KEY = "season_script"
FRIDAY, SATURDAY, SUNDAY = 4, 5, 6
#: A gap shorter than this never shortens (the bible's shortest gap is 5).
MIN_GAP_TO_SHORTEN = 3


@dataclass(frozen=True)
class Position:
    """Where the next day to play sits in the season."""

    season_id: str
    segment: Segment | None
    segment_index: int
    #: 1-based day inside the segment (a tentpole's Day A is 1, Day B is 2).
    day_in_segment: int
    #: 1-based day of the season, counted over the days the learner played.
    season_day: int
    #: -1, 0 or +1 when this position is the result of a weekend flex.
    flex: int = 0
    finished: bool = False

    @property
    def is_tentpole(self) -> bool:
        return bool(self.segment and self.segment.kind == "tentpole")

    @property
    def is_gap(self) -> bool:
        return bool(self.segment and self.segment.kind == "gap")

    @property
    def tentpole_day(self) -> str | None:
        """``"a"`` or ``"b"`` on a tentpole day."""

        if not self.is_tentpole:
            return None
        return "a" if self.day_in_segment == 1 else "b"

    @property
    def key(self) -> str:
        """A stable name for this day, e.g. ``t1.a`` or ``g2.4``."""

        if self.finished or self.segment is None:
            return f"{self.season_id}.end"
        if self.is_tentpole:
            return f"{self.segment.id}.{self.tentpole_day}"
        return f"{self.segment.id}.{self.day_in_segment}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "season_id": self.season_id,
            "segment": self.segment.id if self.segment else None,
            "kind": self.segment.kind if self.segment else None,
            "day_in_segment": self.day_in_segment,
            "season_day": self.season_day,
            "flex": self.flex,
            "key": self.key,
            "finished": self.finished,
        }


def played_log(state: dict | None) -> list[dict]:
    return [row for row in (state or {}).get("played") or [] if isinstance(row, dict)]


#: WP-124b: ``state[SHORTENED_KEY]`` — the gaps the recovery closed early, one row
#: each (``{gap, played_days, nominal_days, via, moments_bridged, date, event_id}``).
SHORTENED_KEY = "shortened"


def shortened_gaps(state: dict | None) -> dict[str, dict]:
    """The gaps a recovery closed early (WP-124b), by id: such a gap is over —
    its next day is the following tentpole, whatever its nominal length said."""

    return {
        str(row.get("gap")): row
        for row in (state or {}).get(SHORTENED_KEY) or []
        if isinstance(row, dict) and row.get("gap")
    }


def _played_in(log: list[dict], segment_id: str) -> int:
    return sum(1 for row in log if row.get("segment") == segment_id)


def position(season: Season, state: dict | None, *, today: date | None) -> Position:
    """The next day to play, given what was played and the learner's local ``today``."""

    log = played_log(state)
    season_day = len(log) + 1
    segments = season.segments
    closed = shortened_gaps(state)
    for index, segment in enumerate(segments):
        done = _played_in(log, segment.id)
        if segment.kind == "tentpole":
            if done < 2:
                return Position(season.id, segment, index, done + 1, season_day)
            continue
        following = segments[index + 1] if index + 1 < len(segments) else None
        entered_next = bool(following and _played_in(log, following.id))
        if entered_next:
            # The gap is over; whatever it ran to is its length.
            continue
        if segment.id in closed:
            # WP-124b: a recovery bridged this gap; it ran to what was played (no
            # weekend flex: the tentpole comes next, on whatever day that is).
            if following is None:
                continue
            return Position(season.id, following, index + 1, 1, season_day)
        nominal = segment.days
        weekday = today.weekday() if isinstance(today, date) else None
        if (
            following is not None
            and following.kind == "tentpole"
            and done == nominal - 1
            and nominal >= MIN_GAP_TO_SHORTEN
            and weekday in (SATURDAY, SUNDAY)
        ):
            # Tomorrow would be a weekday: start the tentpole on this weekend day.
            return Position(season.id, following, index + 1, 1, season_day, flex=-1)
        if done < nominal:
            return Position(season.id, segment, index, done + 1, season_day)
        if done == nominal and weekday == FRIDAY and following is not None:
            # A Friday Day A would put Day B on Saturday; one more day of the gap
            # puts Day A on Saturday instead.
            return Position(season.id, segment, index, done + 1, season_day, flex=1)
        # The gap is over (at its nominal length or after its one extra day).
        if following is not None and following.kind == "tentpole":
            return Position(
                season.id, following, index + 1, 1, season_day, flex=1 if done > nominal else 0
            )
    return Position(season.id, None, len(segments), 0, season_day, finished=True)


def record_played(
    state: dict | None,
    pos: Position,
    *,
    date_iso: str | None,
    event_id: str,
    extra: dict[str, Any] | None = None,
) -> dict:
    """The season state once the day at ``pos`` has been played. Idempotent per event.
    ``extra`` annotates the row (WP-124b: a bridge or a recovered tentpole says so)."""

    state = dict(state or {})
    log = played_log(state)
    if any(row.get("event_id") == event_id for row in log):
        return state
    if pos.finished or pos.segment is None:
        return state
    log.append(
        {
            "segment": pos.segment.id,
            "kind": pos.segment.kind,
            "day_in_segment": pos.day_in_segment,
            "season_day": pos.season_day,
            "key": pos.key,
            "flex": pos.flex,
            "date": date_iso,
            "event_id": event_id,
            **(extra or {}),
        }
    )
    state["played"] = log
    return state


def nominal_calendar(season: Season) -> list[dict[str, Any]]:
    """The bible's calendar as rows: season day → segment and day, no flex."""

    rows: list[dict[str, Any]] = []
    day = 0
    for segment in season.segments:
        for inside in range(1, segment.days + 1):
            day += 1
            rows.append(
                {
                    "season_day": day,
                    "segment": segment.id,
                    "kind": segment.kind,
                    "day_in_segment": inside,
                    "key": f"{segment.id}.{'a' if inside == 1 else 'b'}"
                    if segment.kind == "tentpole"
                    else f"{segment.id}.{inside}",
                }
            )
    return rows
