"""The day contract at run time (red-thread design, 2026-11-10), behind
``STORY_DAY_CONTRACT`` (off by default).

Production printed a random loose end as «À suivre…» on every generated day (0 of
9 walked days showed the planned hook) and no surface said where the week was going.
With the flag on, a planned day that carries a contract (``gaps.json`` →
``days[].contract``) ends on its own hook, and the gap's destination and the days
left to it are read from the season, by code. Nothing here calls a model, and every
failure leaves the day as it was without the flag.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.season.director import pattern_hits
from app.services.season.format import (
    TEXT_SPEAKERS,
    DayBeat,
    Forbidden,
    Gap,
    Mark,
    Season,
    written_levels,
)

logger = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(getattr(settings, "STORY_DAY_CONTRACT", False))


def stand_in_enabled() -> bool:
    """Whether a contract day no writer delivered is served as its stand-in page."""

    return enabled() and bool(getattr(settings, "STORY_CONTRACT_STAND_IN", False))


#: Where ``for_turn`` carries the simpler question (never sent to the reply lane).
ASK_AGAIN_KEY = "ask_again_fr"


def reask_enabled() -> bool:
    """Whether a reply that misses the day's question is asked once more, simpler."""

    return enabled() and bool(getattr(settings, "STORY_CONTRACT_REASK", False))


def plans_gap(season: Season, gap_id: str | None) -> bool:
    """Whether the days of ``gap_id`` are planned by contracts (and the flag is on)."""

    gap = season.gaps.get(str(gap_id or "")) if enabled() else None
    return gap is not None and any(beat.contract for beat in gap.days)


def beat_for(season: Season, gap_id: str | None, premise: str | None) -> tuple[Gap, DayBeat] | None:
    """The planned day of ``gap_id`` that stages ``premise``, when it has a contract."""

    gap = season.gaps.get(str(gap_id or ""))
    if gap is None or not premise:
        return None
    beat = next((row for row in gap.days if row.premise == premise and row.contract), None)
    return (gap, beat) if beat else None


def staged_beat(season: Season, season_ctx: dict[str, Any]) -> tuple[Gap, DayBeat] | None:
    """The contract of the day a served page staged: the premise its checklist names,
    which is the one the plan asked for (a page about something else has none)."""

    if season_ctx.get("kind") == "tentpole" or season_ctx.get("bridge") or season_ctx.get("reprise"):
        # A reprise re-reads a settled page: it settles nothing again.
        return None
    position = season_ctx.get("position") or {}
    premise = (season_ctx.get("checklist") or {}).get("premise_id")
    owed = season_ctx.get("required_premise")
    if owed and premise != owed:
        return None
    return beat_for(season, position.get("segment"), premise)


def hook_teaser(
    season: Season, season_ctx: dict[str, Any], *, band: str | None, date: str | None
) -> dict[str, Any] | None:
    """Tomorrow's line on a contract day: the plan's own hook, in its speaker's mouth.

    None on the gap's last planned day (the tentpole's own teaser stands), on a day
    without a contract, and with the flag off: the caller then keeps its old line.
    """

    if not enabled():
        return None
    try:
        found = staged_beat(season, season_ctx)
        if found is None:
            return None
        gap, beat = found
        hook = beat.contract.hook
        if hook.about in season.tentpoles:
            return None
        text = hook.fr.text(str(band or "A2")).strip()
        if not text:
            return None
        return {
            "text_fr": text,
            "character_id": None if hook.speaker in TEXT_SPEAKERS else hook.speaker,
            "date": date,
            "ref": f"contract:{gap.id}.{beat.premise}",
            "kind": "season",
        }
    except Exception:  # noqa: BLE001 - a teaser never costs the day's ending
        logger.exception("day_contract: the planned hook is unavailable; the old teaser stands")
        return None


def arc(season: Season, pos: Any) -> dict[str, Any] | None:
    """Where the gap is going and how far it is: ``{gap_title_fr, title_fr, when_fr,
    days_left}``. ``days_left`` counts the days until the tentpole's first day (on day
    5 of 7, Saturday's party is 3 days away)."""

    if not enabled() or not getattr(pos, "is_gap", False) or pos.segment is None:
        return None
    gap = season.gaps.get(pos.segment.id)
    if gap is None or gap.destination is None:
        return None
    left = pos.segment.days - int(pos.day_in_segment or 0) + 1
    if left < 1:
        return None
    return {
        "gap_title_fr": gap.title_fr,
        "title_fr": gap.destination.title_fr,
        "when_fr": gap.destination.when_fr,
        "days_left": left,
    }


# ---------------------------------------------------------------------------
# Slice 3: the ending keeps the day's «after»
# ---------------------------------------------------------------------------
#
# 10 November, the canapé day: the plan said «there is a menu, and one canapé has a
# name the learner gave it»; the learner asked «C'est quoi, un canapé ?»; the ending
# read «je ne choisis pas encore», and the settle marked the beat done. With the flag
# on, the day's ending is the contract's: every route makes every ``lands`` fact true,
# the learner's own words fill the mark when they gave some, and the season keeps a
# ledger of what became true and how.

#: The key of the ledger inside the season's state (``living_story`` → ``season_script``).
LEDGER_KEY = "contract_ledger"
#: The keys a turn's details carry the model's reading under.
ROUTE_KEY, MARK_KEY = "contract_route", "contract_mark_fr"
#: What stands for ``{name}`` when nobody in the story knows the learner's name.
NO_NAME_FR = "la maison"
_AFTER_KEPT = 7

#: Added to the reply lane's prompt on a contract day, and only then. ``{at}`` is where
#: the lane's payload carries the plan.
_VOICE_NOTE = """
{at} is today's plan. contract.must_hold lists what becomes true
today whatever the learner answers: reply_fr never refuses it, postpones it or leaves it
for another day («je ne choisis pas encore», «on verra demain»), and never announces it
either: the ending does that. When the conversation goes on after this reply and
contract.mark is present and the learner has not given it yet, your ONE new question
asks for it (contract.mark.ask), in the character's own words."""

#: Added to the ending lane's prompt (and the one-call actor's) on a contract day.
_ENDING_NOTE = """
{at} is today's plan, and the app closes the day from it: your ending is a draft, and
what counts is how you read the learner. contract_route is the id of the ONE entry of contract.routes
whose `when` the learner's own words fulfil, read from meaning; a question, a refusal,
silence or anything nobody planned for is contract.default_route. contract_mark_fr,
when contract.mark is present, is the learner's own words for it, copied verbatim from
their text (at most contract.mark.max_words words: the name they gave, the choice they
made, the words they wrote), or null when they gave none. Never invent or improve it."""


def voice_note(at: str = "story.season_turn.contract") -> str:
    return _VOICE_NOTE.replace("{at}", at)


def ending_note(at: str = "story.season_turn.contract") -> str:
    return _ENDING_NOTE.replace("{at}", at)


def _level_ask(ask: dict[str, str], band: str | None) -> str:
    for field in written_levels(band):
        if ask.get(field):
            return ask[field]
    return ask.get("a1") or next(iter(ask.values()), "")


def for_turn(season: Season, season_ctx: dict[str, Any], *, band: str | None) -> dict[str, Any] | None:
    """``story.season_turn.contract``: what the reply and the ending lanes read on a
    contract day. None off a contract day and with the flag off."""

    if not enabled():
        return None
    try:
        found = staged_beat(season, season_ctx)
        if found is None:
            return None
        contract = found[1].contract
        out: dict[str, Any] = {
            "must_hold": [fact.text for fact in contract.lands],
            "routes": [{"id": route.id, "when": route.when} for route in contract.routes],
            "default_route": next(route.id for route in contract.routes if route.default),
        }
        if reask_enabled() and contract.turns[0].ask_again_fr:
            out[ASK_AGAIN_KEY] = contract.turns[0].ask_again_fr
        mark_turn = next((turn for turn in contract.turns if turn.mark), None)
        if mark_turn is not None:
            out["mark"] = {
                "kind": mark_turn.mark.kind,
                "max_words": mark_turn.mark.max_words,
                "ask": _level_ask(mark_turn.ask, band),
            }
        return out
    except Exception:  # noqa: BLE001 - the plan never costs the learner their reply
        logger.exception("day_contract: no contract for the turn; the lanes run as before")
        return None


def reask(
    plan: dict[str, Any] | None,
    *,
    outcome: str,
    turns_left: int,
    learner_asked: Any,
    history: list[Any] | None,
    ledger: dict[str, Any] | None = None,
) -> str | None:
    """The day's question once more, in the simpler French the contract wrote for it
    (``turns[].ask_again_fr``), or None. Only while it is unanswered and the
    conversation goes on, never over a question the learner asked (that one is
    answered first) and never twice in a scene.

    This is the only code that asks the day's question again. With
    ``STORY_SCENE_RECORD`` on, «answered» is read from the scene record (``ledger``,
    :func:`app.services.scene_ledger.build`) and nothing else: a «non» answers it
    (#467), whatever the tutor made of the reply. With the flag off it is main's rule:
    the tutor's ``not_yet``, and the line not yet in the history."""

    from app.services import scene_record

    again = str((plan or {}).get(ASK_AGAIN_KEY) or "").strip()
    if not again or turns_left <= 0 or learner_asked:
        return None
    if scene_record.enabled():
        return again if _open_in_record(ledger, again) else None
    if outcome != "not_yet":
        return None
    said = [str(row.get("character") or "") for row in history or [] if isinstance(row, dict)]
    if any(_folded(again) in _folded(line) for line in said):
        return None
    return again


def _open_in_record(ledger: dict[str, Any] | None, again: str) -> bool:
    """Whether the scene record has the day's question unanswered and not yet asked again.

    The day's question is the character's first question in the record (the opening
    line's, as a rule). It is open while its ``answered_at`` is unset. It counts as asked
    again once any later question of the character's is the simpler line, or asks it
    again in other words (:func:`app.services.lane_guards.reasked_question`). A record that
    holds no question of the character's has nothing to ask again."""

    from app.services import lane_guards, scene_ledger

    rows = [
        row
        for row in (ledger or {}).get("asked") or []
        if isinstance(row, dict) and row.get("by") == "character" and str(row.get("text_fr") or "").strip()
    ]
    if not rows or rows[0].get("answered_at") is not None:
        return False
    day = rows[0]
    simpler = _folded(scene_ledger.character_question(again) or again)
    as_answered = {"asked": [{**day, "answered_at": day.get("at", 0)}]}
    for row in rows[1:]:
        text = str(row.get("text_fr") or "")
        if simpler and simpler in _folded(text):
            return False
        if lane_guards.reasked_question(text, as_answered):
            return False
    return True


_QUOTES = "«»\"“”„‟'’‘ \t\n"
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'"})


def _folded(text: str) -> str:
    return " ".join(str(text or "").translate(_APOSTROPHES).casefold().split())


def kept_mark(mark: Mark, proposed: Any, learner_lines: list[str], *, forbidden: list[Forbidden]) -> str | None:
    """The learner's own words for the day's mark, or None.

    Kept only when they are the learner's (a verbatim span of something they wrote
    today), short enough, not a question, and free of what the season keeps for later:
    a mark is printed again on later days, in the story's own voice."""

    text = " ".join(str(proposed or "").split()).strip(_QUOTES).rstrip(".,;:!… ").strip(_QUOTES)
    if not text or "?" in text or "{" in text or "}" in text or len(text) > 80:
        return None
    if len(text.split()) > mark.max_words:
        return None
    folded = _folded(text)
    source = next((line for line in learner_lines if folded in _folded(line)), None)
    if source is None:
        return None
    if pattern_hits(forbidden, [text]):
        return None
    # The learner's own casing and accents, where the span can be found as written.
    at = source.translate(_APOSTROPHES).casefold().find(text.translate(_APOSTROPHES).casefold())
    span = source[at : at + len(text)] if at >= 0 else ""
    return span if _folded(span) == folded else text


def choose(
    season: Season,
    gap: Gap,
    beat: DayBeat,
    *,
    route: Any,
    mark: Any,
    learner_lines: list[str],
    name: str | None,
) -> dict[str, Any]:
    """What the day settles on: ``{route, route_source, mark?}``. The model reads the
    learner; the code decides. An unknown route is the default one; a mark that is not
    the learner's own words is the authored one."""

    contract = beat.contract
    routes = {row.id: row for row in contract.routes}
    default = next(row for row in contract.routes if row.default)
    chosen = routes.get(str(route or ""))
    out: dict[str, Any] = {
        "route": (chosen or default).id,
        "route_source": "learner" if chosen is not None and not chosen.default else "default",
    }
    if contract.mark is not None:
        kept = kept_mark(
            contract.mark, mark, learner_lines, forbidden=[*gap.must_not, *season.global_must_not]
        )
        given = (name or "").split()[0] if (name or "").strip() else NO_NAME_FR
        out["mark"] = {
            "id": contract.mark.id,
            "text": kept or contract.mark.default_fr.replace("{name}", given),
            "kept": kept is not None,
        }
        if kept is None and chosen is not None and chosen.needs_mark:
            # «named» without a name: the route that needs none, else the default.
            plain = next((row for row in contract.routes if not row.default and not row.needs_mark), default)
            out["route"] = plain.id
            out["route_source"] = "learner" if not plain.default else "default"
    return out


def _filled(text: str, choice: dict[str, Any]) -> str:
    mark = choice.get("mark")
    return text.replace("{" + mark["id"] + "}", mark["text"]) if mark else text


def ending(
    beat: DayBeat, choice: dict[str, Any], *, band: str | None, language: str | None, character_id: str | None
) -> dict[str, Any]:
    """The day's ending, from the contract: ``{resolution_fr, summary_native,
    fact_fr, narrated}`` (``fact_fr``: «what changed», the fact the story keeps).

    The lead's own closing line when the page turned to them; otherwise «what changed»
    as a caption (``narrated``: said by nobody, never under another character's face).
    """

    contract = beat.contract
    after, field = contract.after_fr.served(str(band or "A2"))
    native = None if str(language or "") == "fr" else contract.after_fr.native_at(field, language)
    if native is None and field != "a2" and str(language or "") != "fr":
        # A level nobody translated reads the A2 line's translation rather than French.
        native = contract.after_fr.native.get(str(language or ""))
    route = next(row for row in contract.routes if row.id == choice["route"])
    spoken = route.line is not None and contract.lead is not None and contract.lead == character_id
    line = route.line.text(str(band or "A2")) if spoken else after
    return {
        "resolution_fr": _filled(line, choice),
        "summary_native": _filled(native or after, choice),
        "fact_fr": _filled(contract.after_fr.a2, choice)[:220],
        "narrated": not spoken,
    }


def record(
    state: dict[str, Any],
    gap: Gap,
    beat: DayBeat,
    choice: dict[str, Any],
    *,
    after_fr: str,
    event_id: str,
    day_index: int,
    date: str | None,
) -> dict[str, Any]:
    """The season's state with today's entry in the ledger (idempotent per event):
    which facts became true, by which route, and the learner's mark as they wrote it."""

    ledger = dict(state.get(LEDGER_KEY) or {})
    facts = [row for row in ledger.get("facts") or [] if isinstance(row, dict)]
    if any(row.get("event_id") == event_id for row in facts):
        return state
    key = f"{gap.id}.{beat.day}"
    for fact in beat.contract.lands:
        facts.append(
            {"id": fact.id, "day": key, "route": choice["route"], "source": "contract", "event_id": event_id}
        )
    marks = dict(ledger.get("marks") or {})
    if choice.get("mark"):
        mark = beat.contract.mark
        marks[mark.id] = {
            "text": choice["mark"]["text"],
            "kept": bool(choice["mark"]["kept"]),
            "kind": mark.kind,
            "day": key,
            "comes_back": list(mark.comes_back),
            "event_id": event_id,
        }
    after = [row for row in ledger.get("after") or [] if isinstance(row, dict)]
    after.append(
        {"day": key, "premise": beat.premise, "route": choice["route"], "route_source": choice["route_source"],
         "text_fr": after_fr, "event_id": event_id, "day_index": day_index, "date": date}
    )
    return {**state, LEDGER_KEY: {"facts": facts, "marks": marks, "after": after[-_AFTER_KEPT:]}}


def previously(live: dict[str, Any], lines: list[str], *, limit: int = 3) -> list[str]:
    """«Précédemment» on the day after a contract day: what that day changed, last and
    in the contract's own words. Only when it was the last day played (a ledger row of
    an older day is history, and the box has its own)."""

    if not enabled():
        return lines
    try:
        ledger = ((live or {}).get("season_script") or {}).get(LEDGER_KEY) or {}
        last = next((row for row in reversed(ledger.get("after") or []) if isinstance(row, dict)), None)
        if not last or not last.get("text_fr") or last.get("day_index") != int(live.get("day_index") or 0):
            return lines
        text = str(last["text_fr"])
        return ([line for line in lines if _folded(line) != _folded(text)] + [text])[-limit:]
    except Exception:  # noqa: BLE001 - the box never costs the page
        logger.exception("day_contract: «Précédemment» keeps its own lines")
        return lines


# ---------------------------------------------------------------------------
# Slice 4: the page is written to the contract
# ---------------------------------------------------------------------------
#
# The ending is the contract's (slice 3); the page before it was still planned from the
# day's prose. On 3 of the owner's last 4 days the plan's own turn was refused at A1 as
# a chained task, and the page asked something else. The writer now reads who asks,
# where, the one ask at the learner's level, and that the page stops just before the
# day's facts become true: the ending makes them true.

#: Added to the planner's prompt (``story_split.PLANNER``) on a contract day only.
PLANNER_NOTE = """

TODAY'S CONTRACT (brief.today.contract)
Today is planned as a contract. Where it speaks, it decides.
- lead_id is contract.lead, when it is set.
- location_id is the first id of contract.places that is in places. When none of them is
  there, choose a place as usual.
- question and task are contract.ask: that ONE ask, in control_language, with nothing
  added (no second ask, no «and say why» the contract did not write).
- contract.must_hold becomes true at the end of today whatever the learner answers. The
  app closes the day itself, from the learner's reply: the page never has to. So the page
  stops just before it: the lead is about to do it and turns to the learner. No beat says
  it has already happened, nothing makes it depend on a yes, and nobody puts it off to
  another day. change.after is contract.must_hold.
- replies follow contract.routes, in that order.
- hook is contract.hook_fr, as written.
- contract.brings_back, when present, is what the learner left on an earlier day, in
  their own words. Today someone says it or shows it, once: one beat carries its slot
  exactly as written (for example {g3.canape_name}). The app puts the learner's words
  there. Never describe, translate or guess what the words are."""

#: Added to the page writer's prompt (``story_split.AUTHOR``) on a contract day only.
AUTHOR_NOTE = """

TODAY'S CONTRACT (contract)
- contract.must_hold becomes true at the end of today whatever the learner answers, and
  the app writes that ending itself from the learner's reply. So, against the rule above,
  plan.change.after does NOT happen on the page: the page stops just before it, the lead
  is about to do it and turns to the learner. No line or caption says it has already
  happened, makes it depend on a yes, or puts it off to another day.
- hook_fr is contract.hook_fr, word for word.
- contract.brings_back, when present: each slot (for example {g3.canape_name}) stands for
  the learner's own words from an earlier day. Write the slot exactly as given, braces
  included, once, inside a line of dialogue or a caption, where a name or a quotation
  would go: «Sur le menu : « {g3.canape_name} ».» The app puts the words there. Never
  write words of your own in its place."""

#: Added to the one-call director's prompt on a contract day only.
DIRECTOR_NOTE = """
season_script.brief.today.contract, when set, is today's plan as a contract; where it
speaks, it decides. character_id is contract.lead when it is set. location_id is the first
id of contract.places that the world has; when it has none of them, choose as usual.
objective_native and objective_semantics are contract.ask: that ONE ask, nothing added.
contract.must_hold becomes true at the end of today whatever the learner answers, and the
app closes the day itself from the learner's reply: the page stops just before it (the
character is about to do it and turns to the learner), no panel says it has already
happened, nothing makes it depend on a yes, nobody puts it off to another day.
season_checklist.change_after is contract.must_hold and season_checklist.hook_fr is
contract.hook_fr, as written. contract.brings_back, when present: each slot (for example
{g3.canape_name}) stands for the learner's own words from an earlier day; write the slot
exactly as given, braces included, once, inside a line of dialogue or a caption, where a
name or a quotation would go. The app puts the words there: never write your own."""


def due_marks(gap: Gap, beat: DayBeat, state: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The learner's marks that come back on this planned day, from the ledger:
    ``[{id, slot, what, text}]``. A mark the ledger does not hold is not due."""

    key = f"{gap.id}.{beat.day}"
    held = ((state or {}).get(LEDGER_KEY) or {}).get("marks") or {}
    due = []
    for earlier in gap.days:
        mark = earlier.contract.mark if earlier.contract else None
        row = held.get(mark.id) if mark else None
        if mark is None or key not in mark.comes_back or not isinstance(row, dict) or not row.get("text"):
            continue
        due.append({"id": mark.id, "slot": "{" + mark.id + "}", "what": mark.what, "text": str(row["text"])})
    return due


def for_page(
    beat: DayBeat, *, band: str | None, gap: Gap | None = None, state: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """``brief.today.contract``: what the page's writer reads on a contract day. The
    writer reads a returning mark as a slot, never as the learner's words: the page is
    the same whoever reads it, and the app fills the slot (``fill_slots``)."""

    contract = beat.contract
    if not enabled() or contract is None:
        return None
    back = [{"slot": row["slot"], "what": row["what"]} for row in due_marks(gap, beat, state)] if gap else []
    return {
        **({"brings_back": back} if back else {}),
        **({"lead": contract.lead} if contract.lead else {}),
        "places": [place for place in (contract.place, contract.place_alt) if place],
        "ask": _level_ask(contract.turns[0].ask, band),
        "must_hold": [fact.text for fact in contract.lands],
        "routes": [route.when for route in contract.routes],
        "hook_fr": contract.hook.fr.text(str(band or "A2")),
    }


def page_issue(
    plan: dict[str, Any] | None, *, lead_id: Any, location_id: Any, speakers: set[str], places: set[str]
) -> str | None:
    """Why a planned or written page does not follow today's contract, as a hint for
    the next attempt; None when it does (or when the world cannot follow it: a lead who
    may not speak today, a place not built yet)."""

    if not plan:
        return None
    lead = plan.get("lead")
    if lead and lead in speakers and str(lead_id or "") != lead:
        return f"Today's contract (brief.today.contract.lead): {lead} asks the learner, not {lead_id}."
    place = next((row for row in plan.get("places") or [] if row in places), None)
    if place and str(location_id or "") != place:
        return f"Today's contract (brief.today.contract.places): the page is set at {place!r}, not {location_id!r}."
    return None


def follows(plan: dict[str, Any] | None, *, lead_id: Any, location_id: Any) -> bool:
    """Whether a lead and a place are the contract's own: the day's variety rule («the
    same person at the same place carried the last days») then yields to the plan."""

    if not plan:
        return False
    return str(lead_id or "") == str(plan.get("lead") or "") and str(location_id or "") in (plan.get("places") or [])


def _walk_text(node: Any, change) -> None:
    """Every string a model carries, in place: its own fields, its lists, its models."""

    from pydantic import BaseModel

    if isinstance(node, BaseModel):
        for name in type(node).model_fields:
            value = getattr(node, name, None)
            if isinstance(value, str):
                changed = change(value)
                if changed != value:
                    setattr(node, name, changed)
            else:
                _walk_text(value, change)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, str):
                node[index] = change(value)
            else:
                _walk_text(value, change)


def fill_slots(draft: Any, marks: list[dict[str, Any]]) -> list[str]:
    """Put the learner's own words where a page carries their slot, in place. Returns
    the slots the page does not carry at all (the writer dropped them): the caller asks
    once more, then serves the page without."""

    if not marks:
        return []
    found: set[str] = set()

    def change(text: str) -> str:
        for mark in marks:
            if mark["slot"] in text:
                found.add(mark["slot"])
                text = text.replace(mark["slot"], mark["text"])
        return text

    _walk_text(draft, change)
    return [mark["slot"] for mark in marks if mark["slot"] not in found]


def stand_in_draft(
    season: Season,
    gap: Gap,
    beat: DayBeat,
    *,
    band: str | None,
    language: str | None,
    places: set[str],
    speakers: set[str],
    chapter: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """The planned day's stand-in page as a scene draft (``living_story.SceneDraft``),
    at the reader's level and in their language; None when the day has none, or when
    its lead may not speak today or the page cannot be set at a place offered today.
    No model: the page is the one written in ``gaps.json`` (``contract.stand_in``)."""

    contract = beat.contract
    page = contract.stand_in if contract else None
    place = next((row for row in (contract.place, contract.place_alt) if row in places), None) if contract else None
    if page is None or contract.lead not in speakers or place is None:
        return None
    # The page says where it is: at the day's second place it reads its own panels
    # for that place, or it is not served there at all.
    written = page.panels if place == contract.place else page.alt_panels
    if not written:
        return None
    lang = str(language or "en")

    def read(wording) -> tuple[str, str]:
        text, field = wording.served(str(band or "A1"))
        return text, (text if lang == "fr" else wording.native_at(field, lang) or wording.native_at(field, "en") or text)

    def at_level(rows: dict[str, Any]) -> Any:
        return next((rows[field] for field in written_levels(band) if rows.get(field)), None) or rows.get("a1") or rows["a2"]

    panels = [(row, *read(row.text)) for row in written]
    captions = [(text, native) for row, text, native in panels if not row.says]
    asks, asks_native = read(page.asks)
    ask_en = _level_ask(contract.turns[0].ask, band)
    task = ask_en if lang not in ("de", "fr") else at_level(page.task)[lang]
    reply = at_level(page.reply_fr)
    premise = next((row for row in gap.premises if row.id == beat.premise), None)
    title = (premise.title_fr if premise else "") or beat.premise
    keeps = bool(chapter) and not (chapter.get("resolved") or chapter.get("exhausted"))
    lean = {"de": "Zum Beispiel:", "fr": "Par exemple :"}.get(lang, "For example:")
    return {
        "title_fr": title[:100],
        "premise_fr": " ".join(text for text, _native in captions[:2])[:600],
        "setup_native": " ".join(native for _text, native in captions[:2])[:600],
        "objective_native": task[:320],
        "objective_semantics": f"{ask_en} Any sincere reply on that counts.",
        "character_id": contract.lead,
        "location_id": place,
        "causal_reason": f"Season {season.id}, {gap.id}.{beat.day}: the planned day «{beat.premise}», as written (stand-in page).",
        "source_event_ids": [],
        "novelty_key": f"{season.id}:{gap.id}:{beat.premise}:stand-in",
        "chapter": {key: chapter[key] for key in ("title_fr", "dramatic_question", "possible_developments")}
        if keeps
        else {
            "title_fr": title[:100],
            "dramatic_question": page.asks.a2[:300],
            "possible_developments": [route.when for route in contract.routes][:5],
        },
        "panels": [
            {
                "narration_fr": "" if row.says else text,
                "dialogue": [{"character_id": contract.lead, "text_fr": text, "text_native": native}] if row.says else [],
                "visual_direction": row.text.native.get("en") or text,
                "alt_native": native,
            }
            for row, text, native in panels
        ],
        "opening_line_fr": asks,
        "suggested_response_fr": reply,
        "hint_native": f"{lean} «{reply}»",
        "translation_native": asks_native,
        "capability_key": None,
        "season_checklist": {
            "premise_id": beat.premise,
            "threads": [],
            "change_before": beat.before,
            "change_after": beat.after,
            "turn_want": ask_en,
            "small_moment_id": None,
            "hook_fr": contract.hook.fr.text(str(band or "A2")),
            "forbidden_respected": True,
        },
    }
