"""Le Quartier phase 1: what the learner does in the 3D besides answer.

Owner decision 2026-10-28 («Go with all five»): on the days ``quartier.json``
writes for (T1 day a), the learner may walk out of Le Mistral and come back, answer
Margaux's text while they are away, and talk to anyone in the room in their own
French. Each is a storylet in the season's condition syntax, answered with the
person's own canon line:

* :func:`storylets_view` — the day's gestures for the scene step (``stage.storylets``);
* :func:`answer` — one gesture answered (``POST /daily-journeys/{id}/choices``);
* :func:`fold_into_season` — at a day's settle, the flags gestures set join the
  season, so the next day reads them in either renderer.

Free talk is read like a turn (the reply classifier, else the matcher on each
line's examples): the line it hears plays; when it hears none, the person's first
line back to what was said (the classifier's ``ack_fr``, under the same guards as a
turn's) or their fallback. A slip of register is answered first, once a day.

Gestures are kept beside the story, in ``thread.state["quartier"]``, which the
story's fingerprint ignores (``living_story.FINGERPRINT_IGNORED_STATE_KEYS``): a
talk mid-day never makes the day's page stale.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.season.flags import holds
from app.services.season.format import SEASON_ROOT, Cond, Line, Say

logger = logging.getLogger(__name__)

#: ``thread.state[STATE_KEY]``: ``{pending, learned, heard, days, log}``.
STATE_KEY = "quartier"
#: How many days of per-day talk memory (slips, fallbacks used) a life keeps.
MAX_DAYS = 7
MAX_LOG = 80
#: The talk turn's own reply when the engine hears none of the person's lines.
NONE_HEARD = "none"
CUE_STORYLETS = ("walk_out", "away")
TALK = "talk"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CueLine(_Model):
    id: str = Field(min_length=1)
    role: Literal["asked", "back", "text", "answer"]
    who: str = Field(min_length=1)
    #: ``back``: said when the learner comes back during this panel.
    during: str | None = None
    #: An SMS's sender, as the phone shows it.
    from_fr: str | None = None
    mood: Literal["neutral", "happy", "cross", "moved", "cold"] = "neutral"
    direction: str = ""
    say: Say


class Cue(_Model):
    id: str = Field(min_length=1)
    cue: Literal["walk_out", "away"]
    who: str = Field(min_length=1)
    after_seconds: int | None = None
    #: Season flags the gesture sets (folded in at the next settle).
    sets: dict[str, Any] = Field(default_factory=dict)
    chips: list[str] = Field(default_factory=list)
    lines: list[CueLine] = Field(min_length=1)


class Learn(_Model):
    id: str = Field(min_length=1)
    say: Say


class Hello(_Model):
    id: str = Field(min_length=1)
    when: Cond = Field(default_factory=dict)
    salience: int = 0
    mood: Literal["neutral", "happy", "cross", "moved", "cold"] = "neutral"
    direction: str = ""
    say: Say


class Intent(_Model):
    id: str = Field(min_length=1)
    #: The example the 3D offers as a chip (help only).
    chip: str | None = None
    when: Cond = Field(default_factory=dict)
    salience: int = 0
    #: Plays once in a life.
    once: bool = False
    mood: Literal["neutral", "happy", "cross", "moved", "cold"] = "neutral"
    direction: str = ""
    #: What the reader listens for (English), and French ways to say it.
    means: str = Field(min_length=1)
    examples: list[str] = Field(min_length=1)
    say: Say
    learn: Learn | None = None


class Person(_Model):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    who: str = Field(min_length=1)
    #: ``register`` in the file: tu or vous, as they speak to the learner.
    register_value: Literal["tu", "vous"] = Field(alias="register")
    hello: list[Hello] = Field(min_length=1)
    intents: list[Intent] = Field(default_factory=list)
    slip: Say
    fallback: list[Say] = Field(min_length=1)
    bye: Say | None = None


class QuartierDay(_Model):
    cues: list[Cue] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)


class Quartier(BaseModel):
    model_config = ConfigDict(extra="ignore")

    days: dict[str, QuartierDay] = Field(default_factory=dict)


class GestureRefused(ValueError):
    """The gesture is not one this day offers (an unknown storylet or person)."""


@lru_cache(maxsize=4)
def load_quartier(season_id: str) -> Quartier:
    path = SEASON_ROOT / season_id / "quartier.json"
    if not path.is_file():
        return Quartier()
    return Quartier.model_validate(json.loads(path.read_text(encoding="utf-8")))


def day_for(season_id: str, key: str) -> QuartierDay | None:
    """The gestures ``key`` (``t1.a``) offers, or ``None``."""

    try:
        return load_quartier(season_id).days.get(str(key))
    except Exception:  # noqa: BLE001 - a broken file never costs the day its page
        logger.exception("quartier: %s/quartier.json could not be read", season_id)
        return None


#: Condition keys read from the day itself rather than the season's flag table.
DAY_PREFIXES = ("route.", "knows.", "heard.")


def validate_quartier(season: Any) -> list[str]:
    """The problems ``quartier.json`` has against the season: an unknown person, a
    flag the flag table does not have, a condition on an unknown flag."""

    from app.services.season.format import cond_flags

    problems: list[str] = []
    cast = {member.id for member in season.cast}
    known = {spec.id for spec in season.flags}
    for key, day in load_quartier(season.id).days.items():
        conds: list[tuple[str, Cond]] = []
        for cue in day.cues:
            if cue.who not in cast:
                problems.append(f"{key}: {cue.id} is said by {cue.who!r}, not in the cast")
            for flag in cue.sets:
                if flag not in known:
                    problems.append(f"{key}: {cue.id} sets unknown flag {flag!r}")
            for line in cue.lines:
                if line.who not in cast and line.who != "sms":
                    problems.append(f"{key}: {line.id} is said by {line.who!r}, not in the cast")
        for person in day.people:
            if person.who not in cast:
                problems.append(f"{key}: {person.who!r} is not in the cast")
            conds += [(row.id, row.when) for row in person.hello] + [(row.id, row.when) for row in person.intents]
            if person.hello[-1].when:
                problems.append(f"{key}: {person.who}'s last hello must hold always (it is the default)")
        for owner, cond in conds:
            unknown = {flag for flag in cond_flags(cond) if not flag.startswith(DAY_PREFIXES)} - known
            if unknown:
                problems.append(f"{key}: {owner} reads unknown flags {sorted(unknown)}")
    return problems


# ---------------------------------------------------------------------------
# Reading what the learner types
# ---------------------------------------------------------------------------


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").casefold().replace("’", "'"))
    return "".join(char for char in text if not unicodedata.combining(char))


_VOUS = re.compile(r"\b(vous|votre|vos)\b")
_TU = re.compile(r"\b(tu|te|toi|ton|ta|tes)\b|\bt'")


def register_of(text: str) -> str | None:
    """Does a French line speak to someone as ``tu`` or as ``vous``? ``None`` when it
    says neither, or both."""

    folded = f" {_fold(text)} "
    vous, tu = bool(_VOUS.search(folded)), bool(_TU.search(folded))
    if vous != tu:
        return "vous" if vous else "tu"
    return None


# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------


def _ctx(*, band: str | None, language: str | None, names: dict[str, str]):
    from app.services.season.page import _Ctx

    return _Ctx(flags={}, band=str(band or "A2"), language=str(language or "en"), neutral=False, names=names)


def _line(who: str, say: Say, ctx: Any, *, mood: str = "neutral", direction: str = "") -> dict[str, Any] | None:
    from app.services.season.page import _line as page_line
    from app.services.season.stage import line_view

    resolved = page_line(Line(who=who, say=say, mood=mood, direction=direction), ctx)
    return line_view(resolved) if resolved else None


def _cue_line(line: CueLine, ctx: Any) -> dict[str, Any] | None:
    row = _line(line.who, line.say, ctx, mood=line.mood, direction=line.direction)
    if row is None:
        return None
    return {**row, "id": line.id, "role": line.role, "during": line.during, "from_fr": line.from_fr}


def _panel(panel_id: str, lines: list[dict[str, Any] | None]) -> dict[str, Any]:
    return {
        "kind": "panel",
        "id": panel_id,
        "location_id": None,
        "in_frame": [],
        "visual": None,
        "silence": False,
        "flashback": False,
        "diegetic": [],
        "lines": [{key: value for key, value in line.items() if key in _LINE_KEYS} for line in lines if line],
    }


_LINE_KEYS = ("who", "name", "kind", "mood", "direction", "text_fr", "text_native")


def _hello(person: Person, flags: dict[str, Any]) -> Hello:
    rows = [row for row in person.hello if holds(row.when, flags)]
    return sorted(rows, key=lambda row: -row.salience)[0] if rows else person.hello[-1]


def _playable(person: Person, flags: dict[str, Any], heard: set[str]) -> list[Intent]:
    rows = [row for row in person.intents if holds(row.when, flags) and not (row.once and row.id in heard)]
    return sorted(rows, key=lambda row: -row.salience)


def _chips(person: Person, flags: dict[str, Any], heard: set[str]) -> list[str]:
    """Up to three things the learner might say next, most salient first: only
    lines that may play and that they have not heard yet."""

    chips: list[str] = []
    for intent in _playable(person, flags, heard):
        if intent.chip and intent.id not in heard and intent.chip not in chips:
            chips.append(intent.chip)
    return chips[:3]


def _person_view(person: Person, ctx: Any, flags: dict[str, Any]) -> dict[str, Any]:
    hello = _hello(person, flags)
    return {
        "who": person.who,
        "name": ctx.names.get(person.who),
        "register": person.register_value,
        "hello": _line(person.who, hello.say, ctx, mood=hello.mood, direction=hello.direction),
        "bye": _line(person.who, person.bye, ctx) if person.bye else None,
    }


def storylets_view(
    season_id: str,
    key: str,
    *,
    band: str | None,
    language: str | None,
    names: dict[str, str],
    flags: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """The day's gestures for the scene step: walking out, the text while away, and
    the people to talk to (with their hello as the day opens)."""

    day = day_for(season_id, key)
    if day is None:
        return []
    ctx = _ctx(band=band, language=language, names=names)
    rows: list[dict[str, Any]] = [
        {
            "id": cue.id,
            "cue": cue.cue,
            "who": cue.who,
            "after_seconds": cue.after_seconds,
            "lines": [row for row in (_cue_line(line, ctx) for line in cue.lines) if row],
            "chips": list(cue.chips),
            "people": [],
        }
        for cue in day.cues
    ]
    if day.people:
        rows.append(
            {
                "id": TALK,
                "cue": TALK,
                "who": None,
                "after_seconds": None,
                "lines": [],
                "chips": [],
                "people": [_person_view(person, ctx, flags or {}) for person in day.people],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Answering a gesture
# ---------------------------------------------------------------------------


def condition_flags(season_flags: dict[str, Any], routes: dict[str, str], state: dict[str, Any]) -> dict[str, Any]:
    """What a gesture's conditions read: the season's flags, today's routes
    (``route.<turn>``), what the learner learned (``knows.<id>``) and heard
    (``heard.<id>``), and what their gestures set that has not joined the season yet."""

    flags = dict(season_flags or {})
    flags.update({f"route.{turn}": reply for turn, reply in (routes or {}).items()})
    flags.update({f"knows.{fact}": True for fact in state.get("learned") or []})
    flags.update({f"heard.{intent}": True for intent in state.get("heard") or []})
    flags.update(dict(state.get("pending") or {}))
    return flags


def _talk_turn(person: Person, intents: list[Intent], ctx: Any, hello: dict[str, Any] | None) -> dict[str, Any]:
    """The person's lines as a turn the reply classifier reads (``season.turns``)."""

    name = ctx.names.get(person.who) or person.who
    replies = [
        {
            "id": intent.id,
            "label": intent.chip or intent.id,
            "means": intent.means,
            "examples": list(intent.examples),
            "beats": [_panel(f"talk.{intent.id}", [_line(person.who, intent.say, ctx)])],
        }
        for intent in intents
    ]
    replies.append(
        {
            "id": NONE_HEARD,
            "label": NONE_HEARD,
            "means": "Anything else: a greeting, small talk, or a question none of the other replies answers.",
            "examples": [],
            "beats": [],
        }
    )
    return {
        "id": f"talk.{person.who}",
        "to": person.who,
        "to_name": name,
        "panel": {"kind": "panel", "id": f"talk.{person.who}.hello", "lines": [hello] if hello else []},
        "listens_for": f"What the learner says to {name} in passing, in the room: one of the replies' subjects, or anything else.",
        "replies": replies,
        "fallback": NONE_HEARD,
        "gate": None,
    }


def answer(
    db: Any,
    user: Any,
    *,
    day: QuartierDay,
    state: dict[str, Any],
    journey_id: str,
    scene_id: str,
    storylet_id: str,
    at: str | None,
    to: str | None,
    text: str | None,
    band: str | None,
    language: str | None,
    names: dict[str, str],
    season_flags: dict[str, Any],
    routes: dict[str, str],
    use_model: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One gesture answered: ``(result, the quartier state after it)``. Raises
    :class:`GestureRefused` for a storylet or a person the day does not have."""

    state = _fresh(state)
    days = state["days"]
    today = dict(days.pop(journey_id, None) or {})
    ctx = _ctx(band=band, language=language, names=names)
    said = " ".join(str(text or "").split())[:500]
    result: dict[str, Any] = {"storylet_id": storylet_id, "beats": [], "chips": [], "heard": None, "learned": [], "sets": {}}

    cue = next((row for row in day.cues if row.id == storylet_id), None)
    if cue is not None:
        result.update(_answer_cue(cue, ctx, at=at, said=said))
        state["pending"] = {**state["pending"], **dict(cue.sets)}
        today["gestures"] = [*list(today.get("gestures") or []), cue.id][-20:]
    elif storylet_id == TALK and day.people:
        person = next((row for row in day.people if row.who == to), None)
        if person is None:
            raise GestureRefused(f"nobody called {to!r} is here today")
        flags = condition_flags(season_flags, routes, state)
        talked = _answer_talk(db, user, person, ctx, flags, state, today, scene_id=scene_id, said=said, band=band, use_model=use_model)
        result.update(talked)
    else:
        raise GestureRefused(f"no gesture {storylet_id!r} today")

    flags = condition_flags(season_flags, routes, state)
    if storylet_id == TALK:
        person = next(row for row in day.people if row.who == to)
        result["chips"] = _chips(person, flags, set(state["heard"]))
    result["people"] = [_person_view(person, ctx, flags) for person in day.people]
    days[journey_id] = today
    state["days"] = dict(list(days.items())[-MAX_DAYS:])
    state["log"] = [
        *state["log"],
        {
            "journey": journey_id,
            "storylet": storylet_id,
            "to": to,
            "at": at,
            "text": said[:300] or None,
            "heard": result.get("heard"),
            "time": datetime.now(UTC).isoformat(),
        },
    ][-MAX_LOG:]
    return result, state


def _fresh(state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(state or {})
    return {
        "pending": dict(state.get("pending") or {}),
        "learned": list(state.get("learned") or []),
        "heard": list(state.get("heard") or []),
        "days": dict(state.get("days") or {}),
        "log": list(state.get("log") or []),
    }


def _answer_cue(cue: Cue, ctx: Any, *, at: str | None, said: str) -> dict[str, Any]:
    if cue.cue == "walk_out":
        # The learner left: what is said when they come back — during ``at``, when a
        # line is written for it. The 3D says the ``asked`` line itself, at the door.
        back = [line for line in cue.lines if line.role == "back"]
        line = next((row for row in back if row.during and row.during == at), None) or next(
            (row for row in back if not row.during), None
        )
    else:
        # Away: the text itself, then — once the learner answers — the answer to theirs.
        role = "answer" if said else "text"
        line = next((row for row in cue.lines if row.role == role), None)
    beats = []
    if line is not None:
        row = _cue_line(line, ctx)
        beats.append(_panel(line.id, [row]))
    return {"beats": beats, "sets": dict(cue.sets)}


def _answer_talk(
    db: Any,
    user: Any,
    person: Person,
    ctx: Any,
    flags: dict[str, Any],
    state: dict[str, Any],
    today: dict[str, Any],
    *,
    scene_id: str,
    said: str,
    band: str | None,
    use_model: bool,
) -> dict[str, Any]:
    from app.services.season.runtime import classify
    from app.services.season.turns import clean_ack, reply_is_not_french

    hello = _hello(person, flags)
    if not said:
        line = _line(person.who, hello.say, ctx, mood=hello.mood, direction=hello.direction)
        return {"beats": [_panel(f"talk.{hello.id}", [line])]}
    beats: list[dict[str, Any]] = []
    slipped = list(today.get("slipped") or [])
    register = register_of(said)
    if register and register != person.register_value and person.who not in slipped:
        beats.append(_panel(f"talk.{person.who}.slip", [_line(person.who, person.slip, ctx, mood="cold" if person.register_value == "vous" else "happy")]))
        today["slipped"] = [*slipped, person.who]
    heard = set(state["heard"])
    intents = _playable(person, flags, heard)
    hit: Intent | None = None
    ack: str | None = None
    if not reply_is_not_french(said):
        turn = _talk_turn(person, intents, ctx, _line(person.who, hello.say, ctx))
        # The lines that may play are part of the reading: a reload asks the same.
        playable = hashlib.sha256("|".join(row.id for row in intents).encode()).hexdigest()[:12]
        choice = classify(db, user, scene_id=f"{scene_id}:talk:{playable}", turn=turn, text=said, use_model=use_model, band=band)
        if choice.clear:
            hit = next((row for row in intents if row.id == choice.reply_id), None)
        if hit is None:
            ack = clean_ack(choice.ack_fr, learner_text=said, address=person.register_value)
    learned: list[dict[str, Any]] = []
    talks = dict(today.get("talks") or {})
    count = int(talks.get(person.who) or 0)
    if hit is not None:
        beats.append(_panel(f"talk.{hit.id}", [_line(person.who, hit.say, ctx, mood=hit.mood, direction=hit.direction)]))
        if hit.id not in heard:
            state["heard"] = [*state["heard"], hit.id]
        if hit.learn is not None and hit.learn.id not in state["learned"]:
            state["learned"] = [*state["learned"], hit.learn.id]
            fact = _line("caption", hit.learn.say, ctx) or {}
            learned.append({"id": hit.learn.id, "text_fr": fact.get("text_fr") or "", "text_native": fact.get("text_native")})
    elif ack:
        line = {"who": person.who, "name": ctx.names.get(person.who), "kind": "speech", "mood": "neutral", "direction": None, "text_fr": ack, "text_native": None}
        beats.append(_panel(f"talk.{person.who}.ack", [line]))
    elif not beats:
        fallback = person.fallback[count % len(person.fallback)]
        beats.append(_panel(f"talk.{person.who}.fallback", [_line(person.who, fallback, ctx)]))
    talks[person.who] = count + 1
    today["talks"] = talks
    return {"beats": beats, "heard": hit.id if hit else None, "learned": learned}


def choose(
    db: Any,
    user: Any,
    *,
    story_context: dict[str, Any],
    history: list[dict[str, Any]],
    journey_id: str,
    storylet_id: str,
    at: str | None = None,
    to: str | None = None,
    text: str | None = None,
) -> dict[str, Any] | None:
    """A gesture on the journey whose day is ``story_context``'s: answered, and kept
    in the learner's thread (locked: the learner's row, then the thread). ``None``
    when the day offers no gestures (not an authored page that has them, a reprise,
    no story). ``history``: the respond step's exchanges, for today's routes."""

    from app.services.cast_registry import display_names
    from app.services.living_story import STATE_KEY as LIVE_KEY
    from app.services.season.clock import SEASON_KEY
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.runtime import ASK_AGAIN, SEASON_CONTEXT_KEY

    season_ctx = story_context.get(SEASON_CONTEXT_KEY) or {}
    page = season_ctx.get("page") if isinstance(season_ctx.get("page"), dict) else {}
    if season_ctx.get("kind") != "tentpole" or season_ctx.get("reprise") or not page.get("tentpole"):
        return None
    season_id = str(season_ctx.get("id") or page.get("season_id") or "")
    day = day_for(season_id, f"{page['tentpole']}.{page.get('day')}")
    if day is None:
        return None
    thread = _locked_thread(db, user)
    if thread is None:
        return None
    season = load_season(season_id)
    live = dict((thread.state or {}).get(LIVE_KEY) or {})
    season_flags = effective_flags(season, live.get(SEASON_KEY) or {}, seed=str(season_ctx.get("seed") or ""))
    routes = {
        str(route.get("turn")): str(route.get("reply"))
        for route in (row.get("route") for row in history or [] if isinstance(row, dict))
        if isinstance(route, dict) and route.get("turn") and route.get("reply") not in (None, ASK_AGAIN)
    }
    result, quartier = answer(
        db,
        user,
        day=day,
        state=dict((thread.state or {}).get(STATE_KEY) or {}),
        journey_id=journey_id,
        scene_id=str(story_context.get("scene_id") or journey_id),
        storylet_id=storylet_id,
        at=at,
        to=to,
        text=text,
        band=page.get("band"),
        language=page.get("language"),
        names=display_names(season.cast),
        season_flags=season_flags,
        routes=routes,
    )
    state = dict(thread.state or {})
    state[STATE_KEY] = quartier
    # A JSON column is noticed only when replaced, never when mutated in place.
    thread.state = state
    return result


def _locked_thread(db: Any, user: Any) -> Any:
    from sqlalchemy import select

    from app.db.models.user import User
    from app.services.living_story import _active_thread

    db.execute(select(User.id).where(User.id == user.id).with_for_update())
    return _active_thread(db, user, lock=True)


# ---------------------------------------------------------------------------
# The settle
# ---------------------------------------------------------------------------


def fold_into_season(state: dict[str, Any], live: dict[str, Any]) -> None:
    """At a day's settle: the flags the learner's gestures set join the season (the
    flag table checks each), and wait no longer. In place on the thread's ``state``
    and the life ``live``; nothing when there is no season or nothing waits."""

    from app.services.season.clock import SEASON_KEY
    from app.services.season.flags import apply_sets
    from app.services.season.format import load_season

    quartier = state.get(STATE_KEY)
    pending = dict(quartier.get("pending") or {}) if isinstance(quartier, dict) else {}
    season_state = live.get(SEASON_KEY)
    if not pending or not isinstance(season_state, dict) or not season_state.get("id"):
        return
    try:
        season = load_season(str(season_state["id"]))
    except Exception:  # noqa: BLE001 - an unreadable season keeps the gestures waiting
        logger.exception("quartier: season %s could not be read; gestures wait", season_state.get("id"))
        return
    live[SEASON_KEY] = apply_sets(season, season_state, pending, source="quartier")
    state[STATE_KEY] = {**quartier, "pending": {}}
