"""The season, played by the story engine (WP-111).

``living_story`` calls in at five points and nowhere else:

* ``story_context`` → :func:`context_block` — which season this life is on, where
  it stands today, and on a generated day the gap's brief for the director;
* ``generate_scene`` → :func:`tentpole_brief` — on a tentpole day the authored page,
  with no model call at all;
* ``bind_journey`` → :func:`payload_for_scene` — the resolved page stored on the scene;
* ``evaluate_turn`` → :func:`evaluate_tentpole_turn` — the learner's reply routed to
  the bible's likely reply, and the bible's reaction;
* ``settle_resolution`` → :func:`settle` — flags, Lila's gate signals and the played log.

A learner is on a season when their thread says so (``live["season_script"]``), or
when they have not started a story yet and ``ATELIER_SEASON_SCRIPT`` names one. A
life already under way on the generated serial keeps it: the season never rewrites a
story a learner is in the middle of.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from datetime import date
from typing import Any

from app.config import settings
from app.services.season.clock import SEASON_KEY, Position, position, record_played
from app.services.season.director import gap_brief
from app.services.season.flags import (
    add_signal,
    apply_sets,
    conditional_sets,
    effective_flags,
    holds,
)
from app.services.season.format import Season, load_season
from app.services.season.page import (
    choice_cards,
    convince_outcome,
    exchanges_for,
    hook_caption,
    option_by_id,
    posed_as_turn,
    posed_choice,
    project,
    reply_by_id,
    resolve_day,
    solves_of,
    spoken_lines,
    turns_of,
)
from app.services.season.turns import (
    CLASSIFIER,
    MATCH_THRESHOLD,
    ReplyChoice,
    classifier_payload,
    gate_signal,
    match_reply,
    reaction_native,
    reaction_text,
)
from app.services.season.world import location_name_fr, plate_for

logger = logging.getLogger(__name__)

#: ``brief.story_context[SEASON_CONTEXT_KEY]`` — the season part of a served day.
SEASON_CONTEXT_KEY = "season"
#: Holidays and the real-calendar window in which their dated wording is kept (S-12).
HOLIDAY_WINDOWS = {"noel": ((12, 18), (12, 27)), "reveillon": ((12, 26), (1, 3))}
_ROUTE_CACHE: OrderedDict[tuple[str, str, str], ReplyChoice] = OrderedDict()
_ROUTE_CACHE_LIMIT = 512


# ---------------------------------------------------------------------------
# Which season, and where
# ---------------------------------------------------------------------------


def enabled_season() -> str | None:
    value = str(getattr(settings, "ATELIER_SEASON_SCRIPT", "") or "").strip()
    return value or None


def _started(live: dict | None) -> bool:
    live = live or {}
    return bool(live.get("day_index") or live.get("events") or live.get("chapter"))


def season_id_for(live: dict | None) -> str | None:
    """The season this life plays: its own, or the enabled one for a life not yet begun."""

    state = (live or {}).get(SEASON_KEY)
    if isinstance(state, dict) and state.get("id"):
        return str(state["id"])
    if not _started(live):
        return enabled_season()
    return None


def learner_date(user: Any, now: Any = None) -> date:
    from app.services.daily_journey import _utcnow, local_date_for

    return local_date_for(getattr(user, "timezone", None) or "UTC", now=now or _utcnow())


def off_calendar(holiday: str | None, today: date | None) -> bool:
    """S-12: a date-bound day reads its neutral wording away from that date."""

    if not holiday or holiday not in HOLIDAY_WINDOWS or today is None:
        return False
    (m0, d0), (m1, d1) = HOLIDAY_WINDOWS[holiday]
    key = (today.month, today.day)
    inside = (m0, d0) <= key <= (m1, d1) if (m0, d0) <= (m1, d1) else key >= (m0, d0) or key <= (m1, d1)
    return not inside


@dataclass(frozen=True)
class Today:
    season: Season
    pos: Position
    state: dict
    flags: dict
    seed: str
    band: str
    language: str
    local_date: date

    @property
    def neutral(self) -> bool:
        if not self.pos.is_tentpole or self.pos.segment is None:
            return False
        tentpole = self.season.tentpoles.get(self.pos.segment.id)
        day = next((d for d in (tentpole.days if tentpole else []) if d.day == self.pos.tentpole_day), None)
        return off_calendar(day.holiday if day else None, self.local_date)


def today_for(live: dict | None, *, user: Any, seed: str, now: Any = None) -> Today | None:
    season_id = season_id_for(live)
    if not season_id:
        return None
    try:
        season = load_season(season_id)
    except Exception:  # noqa: BLE001 - a broken season file must not cost a day
        logger.exception("season: %s could not be loaded; the generated serial serves the day", season_id)
        return None
    from app.services.chrome_language import user_chrome_language
    from app.services.living_story import learner_level_band

    state = dict((live or {}).get(SEASON_KEY) or {"id": season_id})
    state.setdefault("id", season_id)
    local = learner_date(user, now)
    pos = position(season, state, today=local)
    return Today(
        season=season,
        pos=pos,
        state=state,
        flags=effective_flags(season, state, seed=seed),
        seed=seed,
        band=learner_level_band(user),
        # The one-language rule: the page's own words (the task, the hint) are in the
        # learner's language up to A2 and in French from B1. The story is French.
        language=user_chrome_language(user),
        local_date=local,
    )


def context_block(today: Today | None) -> dict[str, Any] | None:
    """``context["season_script"]``: the director's view of the season today."""

    if today is None:
        return None
    block: dict[str, Any] = {
        "id": today.season.id,
        "title_fr": today.season.title_fr,
        "position": today.pos.as_dict(),
    }
    if today.pos.is_gap:
        block["brief"] = gap_brief(
            today.season, today.pos, flags=today.flags, state=today.state, seed=today.seed
        )
    return block


# ---------------------------------------------------------------------------
# A tentpole day: the authored page, served
# ---------------------------------------------------------------------------


def page_for(today: Today) -> dict[str, Any] | None:
    if not today.pos.is_tentpole or today.pos.segment is None:
        return None
    return resolve_day(
        today.season,
        today.pos.segment.id,
        str(today.pos.tentpole_day),
        flags=today.flags,
        band=today.band,
        language=today.language,
        neutral=today.neutral,
    )


def projected_turns(page: dict[str, Any]) -> list[dict[str, Any]]:
    """The day's turns in order, each with the lines that lead into it.

    Until WP-110 draws the page, the reply step is one conversation: the panels
    between two turns (and the default beats of a solve on the way) are said as the
    lead-in to the next question.
    """

    projection = project(page)
    first = projection["turn"]
    turns: list[dict[str, Any]] = []
    movements = list(page.get("movements") or [])
    if first is not None and first.get("from_solve") and not any(row.get("kind") == "turn" or posed_choice(row) for row in movements):
        # A day with nothing but a solve WP-112 has not posed yet: that solve is the question.
        return [{**first, "lead_in": []}]
    lead: list[dict[str, Any]] = []
    started = False
    for movement in page.get("movements") or []:
        kind = movement.get("kind")
        if kind == "turn":
            if started:
                turns.append({**movement, "lead_in": list(lead)})
            else:
                turns.append({**movement, "lead_in": []})
                started = True
            lead = []
        elif posed_choice(movement):
            # WP-113: «Le choix» and «Convaincre» are asked, not defaulted; one met
            # before any free question opens the conversation itself.
            turns.append({**posed_as_turn(movement), "lead_in": list(lead) if started else []})
            started = True
            lead = []
        elif not started:
            continue
        elif kind == "panel":
            lead.append(movement)
        elif kind == "solve":
            if movement.get("mechanic") == "enquete":
                lead.extend(movement.get("nudge") or [])
            else:
                option = option_by_id(movement, movement.get("default")) or next(
                    iter(movement.get("options") or []), None
                )
                lead.extend((option or {}).get("beats") or [])
        elif kind == "hook":
            break
    return turns


def page_tail(page: dict[str, Any]) -> list[dict[str, Any]]:
    """What the page says after its last turn — panels, the default beats of a solve,
    and the hook's own voices (not its «À suivre…» caption, which is the ending)."""

    movements = list(page.get("movements") or [])
    last = max((i for i, row in enumerate(movements) if row.get("kind") == "turn" or posed_choice(row)), default=None)
    if last is None:
        return []
    tail: list[dict[str, Any]] = []
    for movement in movements[last + 1 :]:
        kind = movement.get("kind")
        if kind == "panel":
            tail.append(movement)
        elif kind == "solve":
            if movement.get("mechanic") == "enquete":
                tail.extend(movement.get("nudge") or [])
            else:
                option = option_by_id(movement, movement.get("default"))
                tail.extend((option or {}).get("beats") or [])
        elif kind == "hook":
            panel = dict(movement.get("panel") or {})
            panel["lines"] = [line for line in panel.get("lines") or [] if line.get("kind") != "caption"]
            tail.append(panel)
            break
    return tail


def _lexicon(page: dict[str, Any], language: str, draft_text: str) -> list[dict[str, Any]]:
    """The words the scene needs (``11-pedagogie.md``), for the day's word drills —
    below B1 only: they are A1–A2 words, glossed in the learner's own language."""

    if str(page.get("band") or "")[:2].upper() not in {"A1", "A2"}:
        return []
    entries = []
    folded = draft_text.casefold()
    for row in page.get("lexicon") or []:
        surface = str(row.get("surface_fr") or "")
        if not surface or surface.casefold() not in folded:
            continue
        entries.append(
            {
                "surface_fr": surface,
                "lemma": row.get("lemma") or surface,
                "gloss_native": (row.get("gloss") or {}).get(language) or (row.get("gloss") or {}).get("en") or "",
                "part_of_speech": row.get("part_of_speech"),
                "gender": row.get("gender"),
                "line_ref": "premise",
            }
        )
    return entries[:5]


def _engine_panel(panel: dict[str, Any], *, language: str) -> dict[str, Any]:
    captions = [line for line in panel.get("lines") or [] if line.get("kind") != "speech"]
    speech = [line for line in panel.get("lines") or [] if line.get("kind") == "speech"]
    narration = " ".join(str(line.get("text_fr") or "") for line in captions).strip()
    return {
        "narration_fr": narration,
        "dialogue": [
            {
                "character_id": line["who"],
                "text_fr": line["text_fr"],
                "mood": line.get("mood") or "neutral",
                "text_native": line.get("text_native"),
            }
            for line in speech
        ],
        "visual_direction": panel.get("visual") or "Same framing as the panel before.",
        "alt_native": (panel.get("visual") or "")[:159] if language == "en" and panel.get("visual") else None,
    }


_EXAMPLE_LEAD = {"en": "For example:", "de": "Zum Beispiel:", "fr": "Par exemple :"}


def authored_draft(today: Today, page: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    """The page as a scene draft the engine can publish (``AuthoredSceneDraft``)."""

    projection = project(page)
    scene = projection["scene_panels"]
    first = turns[0] if turns else None
    opening = [
        line
        for line in ((first or {}).get("panel") or {}).get("lines") or []
        if line.get("kind") == "speech" and line.get("who") == (first or {}).get("to")
    ] or [line for line in ((first or {}).get("panel") or {}).get("lines") or [] if line.get("text_fr")]
    opening_fr = " ".join(str(line.get("text_fr")) for line in opening).strip() or page["title_fr"]
    opening_native = " ".join(str(line.get("text_native") or "") for line in opening).strip()
    replies = (first or {}).get("replies") or []
    example = next(
        (reply["examples"][0] for reply in replies if reply.get("examples") and not reply.get("clumsy")),
        next((reply["examples"][0] for reply in replies if reply.get("examples")), opening_fr),
    )
    captions = [
        line for panel in scene for line in panel.get("lines") or [] if line.get("kind") == "caption"
    ]
    premise = str((captions[0] if captions else {}).get("text_fr") or page["title_fr"])
    premise_native = str((captions[0] if captions else {}).get("text_native") or "") or premise
    ending = hook_caption(page) or {}
    hooks = [
        str((hook_caption(page) or {}).get("text_fr") or page["title_fr"]),
        str(page.get("tentpole_title_fr") or page["title_fr"]),
    ]
    panels = [_engine_panel(panel, language=today.language) for panel in scene] or [
        _engine_panel({"lines": [], "visual": page["title_fr"]}, language=today.language)
    ]
    text = " ".join(
        [premise, opening_fr]
        + [line["text_fr"] for panel in panels for line in panel["dialogue"]]
        + [panel["narration_fr"] for panel in panels]
    )
    to = str((first or {}).get("to") or "margaux_barman")
    return {
        "title_fr": page["title_fr"][:100],
        "premise_fr": premise[:600],
        "setup_native": premise_native[:600],
        "objective_native": str((first or {}).get("task_native") or page.get("can_do_native") or page["title_fr"])[:320],
        "objective_semantics": str((first or {}).get("listens_for") or "Any sincere reply.")[:700],
        "character_id": to,
        "location_id": page["location_id"],
        "causal_reason": f"Season {today.season.id}, {today.pos.key}: the owner-approved tentpole.",
        "source_event_ids": [],
        "novelty_key": f"{today.season.id}:{today.pos.key}",
        "chapter": {
            "title_fr": page["tentpole_title_fr"][:100],
            "dramatic_question": today.season.question.a2[:300],
            "possible_developments": hooks,
        },
        "beat": "setup" if today.pos.tentpole_day == "a" else "resolution",
        # A tentpole is not one of the director's practical problems: it records none,
        # so a generated day is never refused as a «stale problem» against it.
        "problem_key": "",
        "arc_id": None,
        "panels": panels,
        "opening_line_fr": opening_fr[:320],
        "suggested_response_fr": str(example)[:400],
        "hint_native": f"{_EXAMPLE_LEAD.get(today.language, _EXAMPLE_LEAD['en'])} «{example}»"[:400],
        "translation_native": (opening_native or opening_fr)[:400],
        "capability_key": None,
        "lexicon": _lexicon(page, today.language, text),
        "can_do_id": None,
        "_ending": ending,
    }


def panel_images(page: dict[str, Any], scene_panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each scene panel's picture: its own location's plate (authored drawings are
    drawn once, offline, and replace these when they exist)."""

    images = []
    for panel in scene_panels:
        location = panel.get("location_id") or page.get("location_id")
        images.append({"panel_id": panel.get("id"), "image_url": plate_for(location), "location_id": location})
    return images


def tentpole_brief(today: Today, context: dict[str, Any]):
    """Today's authored page as the brief the journey plans and binds. No model call."""

    from app.services import living_story as engine

    page = page_for(today)
    if page is None:
        return None
    turns = projected_turns(page)
    draft_dict = authored_draft(today, page, turns)
    ending = draft_dict.pop("_ending", {}) or {}
    draft = engine.AuthoredSceneDraft.model_validate(draft_dict)
    world = context.get("world") or {}
    if not any(member.get("id") == draft.character_id for member in world.get("cast") or []):
        logger.warning("season: %s is not in the world cast; the day falls back", draft.character_id)
        return None
    if not any(place.get("id") == draft.location_id for place in world.get("locations") or []):
        logger.warning("season: %s is not a world location; the day falls back", draft.location_id)
        return None
    brief = engine._brief(draft, context, usage=[])
    scene_panels = project(page)["scene_panels"]
    season_ctx = {
        "id": today.season.id,
        "kind": "tentpole",
        "position": today.pos.as_dict(),
        "page": page,
        "turns": turns,
        "ending": ending,
        "tail": page_tail(page),
        "panel_images": panel_images(page, scene_panels),
        "seed": today.seed,
    }
    # One exchange per authored turn, plus one when a reply may ask the turn again
    # («Tu dis ça vite. Encore une fois ?»).
    repeats = any(reply.get("repeat_once") for turn in turns for reply in turn.get("replies") or [])
    # WP-113: the conversation must reach the day's last posed solve and Lila's gate
    # (both move the story), and a «Convaincre» can take one exchange per objection.
    last_posed = max(
        (i for i, turn in enumerate(turns) if turn.get("from_solve") in ("choix", "convaincre") or turn.get("gate")),
        default=-1,
    )
    exchanges = sum(exchanges_for(turn) for turn in turns)
    task = dc_replace(
        brief.response_task,
        min_turns=sum(exchanges_for(turn) for turn in turns[: last_posed + 1]),
        opening_choices=choice_cards(turns[0]) if turns else [],
        max_turns=max(1, exchanges + (1 if repeats else 0)),
        allowed_outcomes=["resolved", "open"],
        estimated_seconds=60 * max(1, len(turns)),
    )
    return dc_replace(
        brief,
        response_task=task,
        control_language=today.language,
        location_name=location_name_fr(draft.location_id),
        image_url=plate_for(draft.location_id) or brief.image_url,
        estimated_seconds=60 * int(page.get("minutes") or 6),
        story_context={**brief.story_context, SEASON_CONTEXT_KEY: season_ctx},
    )


def season_teaser(story_context: dict[str, Any], *, date: str | None) -> dict[str, Any] | None:
    """Tomorrow's line on a tentpole day: the page's own «À suivre…», unvoiced."""

    season_ctx = story_context.get(SEASON_CONTEXT_KEY) or {}
    if season_ctx.get("kind") != "tentpole":
        return None
    text = str((season_ctx.get("ending") or {}).get("text_fr") or "").strip()
    if not text:
        return None
    return {
        "text_fr": text,
        "character_id": None,
        "date": date,
        "ref": f"season:{(season_ctx.get('position') or {}).get('key')}",
        "kind": "season",
    }


def payload_for_scene(story_context: dict[str, Any]) -> dict[str, Any]:
    """What ``bind_journey`` stores on the scene's ``script_payload``."""

    season_ctx = story_context.get(SEASON_CONTEXT_KEY) or {}
    if not season_ctx:
        return {}
    payload = {"season": {"id": season_ctx.get("id"), "kind": season_ctx.get("kind"), **(season_ctx.get("position") or {})}}
    if season_ctx.get("page"):
        payload["season_page"] = season_ctx["page"]
    if season_ctx.get("checklist"):
        payload["season"]["checklist"] = season_ctx["checklist"]
    return payload


def is_tentpole(story_context: dict[str, Any] | None) -> bool:
    return ((story_context or {}).get(SEASON_CONTEXT_KEY) or {}).get("kind") == "tentpole"


# ---------------------------------------------------------------------------
# A tentpole turn
# ---------------------------------------------------------------------------


def card_choice(turn: dict[str, Any], text: str) -> ReplyChoice | None:
    """WP-113: a «Le choix» card tapped — the answer is the card's label, so the route
    is certain and costs no model call. ``None`` for any other turn or text."""

    if not turn.get("choice"):
        return None
    said = " ".join(str(text or "").split()).casefold()
    for reply in turn.get("replies") or []:
        if said in {str(reply.get("label") or "").casefold(), str(reply.get("id") or "").casefold()}:
            return ReplyChoice(reply_id=str(reply["id"]), confidence=1.0)
    return None


def _cache_key(scene_id: str, turn_id: str, text: str) -> tuple[str, str, str]:
    return (scene_id, turn_id, hashlib.sha256(" ".join(str(text).split()).casefold().encode()).hexdigest())


def classify(db, user, *, scene_id: str, turn: dict[str, Any], text: str, history: list | None = None, use_model: bool = True) -> ReplyChoice:
    """Which of the turn's replies the learner expressed (model, else matcher)."""

    key = _cache_key(scene_id, str(turn.get("id")), text)
    cached = _ROUTE_CACHE.get(key)
    if cached is not None:
        _ROUTE_CACHE.move_to_end(key)
        return cached
    ids = {str(reply.get("id")) for reply in turn.get("replies") or []}
    choice: ReplyChoice | None = None
    if use_model:
        from app.services import living_story as engine

        usage: list[dict] = []
        try:
            parsed, _ = engine._json_call(
                CLASSIFIER,
                classifier_payload(turn, text, history),
                ReplyChoice,
                usage.append,
                deadline=time.monotonic() + 20,
                max_tokens=1200,
                reasoning_effort="minimal",
                window=15,
            )
            if isinstance(parsed, ReplyChoice) and parsed.reply_id in ids:
                choice = parsed
        except engine.StoryUnavailable as exc:
            logger.info("season: reply classifier unavailable (%s); matching instead", exc)
        except Exception:  # noqa: BLE001 - a reading never costs a turn
            logger.warning("season: reply classifier failed; matching instead", exc_info=True)
        if usage and db is not None and user is not None:
            _record_classifier_cost(db, user, usage)
    if choice is None:
        reply_id, score = match_reply(turn, text)
        reply = reply_by_id(turn, reply_id)
        choice = ReplyChoice(
            reply_id=str(reply.get("id")),
            expresses=(reply.get("path") or "none") if turn.get("gate") else "none",
            confidence=round(min(1.0, score), 3),
        )
    _ROUTE_CACHE[key] = choice
    while len(_ROUTE_CACHE) > _ROUTE_CACHE_LIMIT:
        _ROUTE_CACHE.popitem(last=False)
    return choice


def _record_classifier_cost(db, user, usage: list[dict]) -> None:
    try:
        from app.services.pilot_events import PilotEventService

        PilotEventService(db).record(
            "journey_story_model_call",
            user_id=user.id,
            entity_type="season_script",
            payload={"stage": "ReplyChoice", **usage[-1], "call_cost_usd": usage[-1].get("cost_usd") or 0.0},
            cost_usd=float(sum(float(row.get("cost_usd") or 0.0) for row in usage)),
        )
    except Exception:  # noqa: BLE001 - telemetry never costs a turn
        logger.warning("season: classifier cost row not recorded", exc_info=True)


def _walk(turns: list[dict[str, Any]], routed: list[tuple[str, dict[str, Any]]]) -> tuple[int, dict[int, int]]:
    """Where the conversation stands after ``routed`` exchanges: the turn index now
    owed, and how many times each turn has been answered."""

    index = 0
    answered: dict[int, int] = {}
    for _text, reply in routed:
        if index >= len(turns):
            break
        answered[index] = answered.get(index, 0) + 1
        if reply.get("repeat_once") and answered[index] == 1:
            continue
        convince = turns[index].get("convince")
        if convince and reply.get("id") == "objection" and answered[index] < int(convince.get("attempts") or 1):
            continue  # WP-113: the next objection; the learner tries again
        index += 1
    return index, answered


def evaluate_tentpole_turn(db, *, user, scenario, task, answer, turn_index: int, assistance, history=None):
    """The learner's reply, routed; the bible's reaction; the day's close when due."""

    from app.services import living_story as engine
    from app.services.journey_contracts import (
        ResponseEvaluation,
        StoryOutcomeProposal,
        TaskOutcome,
    )

    season_ctx = scenario.story_context.get(SEASON_CONTEXT_KEY) or {}
    turns: list[dict[str, Any]] = list(season_ctx.get("turns") or [])
    scene_id = str(scenario.story_context.get("scene_id") or "")
    if answer.is_blank or not turns:
        return ResponseEvaluation(
            outcome=TaskOutcome.UNSCORED,
            assistance=assistance,
            observations=[],
            turn_consumed=False,
            pending=True,
            failure_reason="empty_answer" if answer.is_blank else "season_turn_missing",
        )
    # Replay the conversation so far (cached readings) to know which turn this is.
    routed: list[tuple[str, dict[str, Any]]] = []
    for exchange in history or []:
        learner = str((exchange or {}).get("learner") or "")
        if not learner.strip() or (exchange or {}).get("free"):
            continue
        index, _ = _walk(turns, routed)
        if index >= len(turns):
            break
        choice = card_choice(turns[index], learner) or classify(db, user, scene_id=scene_id, turn=turns[index], text=learner, use_model=False)
        routed.append((learner, reply_by_id(turns[index], choice.reply_id)))
    index, answered = _walk(turns, routed)
    index = min(index, len(turns) - 1)
    turn = turns[index]
    choice = card_choice(turn, answer.text) or classify(db, user, scene_id=scene_id, turn=turn, text=answer.text, history=history)
    reply = reply_by_id(turn, choice.reply_id)
    again = bool(reply.get("repeat_once") and answered.get(index, 0) >= 1)
    beats = list(reply.get("again") or []) if again and reply.get("again") else list(reply.get("beats") or [])
    if turn.get("convince"):
        # WP-113 «Convaincre»: the next objection, or the interlude and the outcome.
        beats = convince_outcome(turn, reply.get("id"), attempt=answered.get(index, 0))
    routed.append((answer.text, reply))
    next_index, _ = _walk(turns, routed)
    # The day's rhythm may plan fewer exchanges than the page has turns: the
    # conversation then closes on this one, and the turns it did not reach keep
    # only what they set whatever is said (``_settle_tentpole``).
    planned = int(getattr(task, "max_turns", 0) or len(turns))
    closing = next_index >= len(turns) or int(turn_index) + 1 >= planned
    beats += list(turn.get("after") or []) if (not reply.get("repeat_once") or again) else []
    if closing:
        # Until WP-110 draws the page, the rest of the day is said here; the
        # ending is the «À suivre…» caption alone.
        beats += list(season_ctx.get("tail") or [])
    from app.services.season.turns import reaction_lines

    addressee = str(scenario.character_id)
    reply_fr = reaction_text(beats, addressee=addressee)
    spoken_lines_out = reaction_lines(beats, addressee=addressee)
    if not closing:
        upcoming = turns[next_index] if next_index != index else turn
        lead = list(upcoming.get("lead_in") or []) if next_index != index else []
        asked = [*lead, upcoming["panel"]] if next_index != index else []
        question = reaction_text(asked, addressee=addressee) if asked else ""
        spoken_lines_out += reaction_lines(asked, addressee=addressee)
        reply_fr = "\n".join(part for part in (reply_fr, question) if part)
    reply_fr = reply_fr or "…"
    # WP-113: when the next question is «Le choix», its cards go with the reply.
    upcoming_turn = turns[next_index] if not closing and next_index < len(turns) and next_index != index else None
    next_choices = choice_cards(upcoming_turn) if upcoming_turn else []
    next_task = str(upcoming_turn.get("task_native") or "") if upcoming_turn and upcoming_turn.get("from_solve") else ""
    proposal = None
    if closing:
        proposal = _closing_proposal(
            engine, db, user, scenario, turns=turns, routed=routed, final_choice=choice
        )
        proposal = StoryOutcomeProposal(
            outcome_key="resolved",
            callback_fr=proposal["callback_fr"],
            character_id=scenario.character_id,
            details=proposal,
        )
    # The story answers every reply; the verdict only says whether the learner's words
    # were understood as one of the scene's replies (never «right» or «wrong» plot).
    understood = choice.confidence >= MATCH_THRESHOLD
    # The page answers what the learner meant; the form is corrected in the margin
    # (never punished in the plot — the bible's rule).
    from app.services.story_lanes import margin_correction

    correction = margin_correction(
        db, user=user, scenario=scenario, task=task, answer=answer, turn_index=turn_index, history=history
    )
    return ResponseEvaluation(
        outcome=TaskOutcome.MET if understood else TaskOutcome.PARTIALLY_MET,
        assistance=assistance,
        observations=[],
        character_reply_fr=reply_fr,
        correction=correction,
        consequence=proposal,
        needs_repair=not closing,
        failure_reason="reply_source:authored_season",
        reply_lines=spoken_lines_out,
        next_choices=next_choices,
        next_task_native=next_task or None,
    )


def _closing_proposal(engine, db, user, scenario, *, turns, routed, final_choice: ReplyChoice) -> dict[str, Any]:
    season_ctx = scenario.story_context.get(SEASON_CONTEXT_KEY) or {}
    ending = season_ctx.get("ending") or {}
    routing = []
    index = 0
    answered: dict[int, int] = {}
    for text, reply in routed:
        if index >= len(turns):
            break
        turn = turns[index]
        choice = final_choice if (text, reply) == routed[-1] else None
        routing.append(
            {
                "turn_id": turn.get("id"),
                "reply_id": reply.get("id"),
                "signal": gate_signal(turn, reply, choice),
                "gate": turn.get("gate"),
                "value": choice.value if choice else None,
                "learner": text[:300],
            }
        )
        answered[index] = answered.get(index, 0) + 1
        if not (reply.get("repeat_once") and answered[index] == 1):
            index += 1
    last_reply = reaction_text(list(routed[-1][1].get("beats") or []), addressee=str(scenario.character_id))
    resolution_fr = str(ending.get("text_fr") or scenario.title_fr)
    summary = str(ending.get("text_native") or ending.get("text_fr") or scenario.title_fr)
    return {
        "outcome": "met",
        "understood_intent": f"season:{season_ctx.get('position', {}).get('key')}:" + ",".join(
            f"{row['turn_id']}={row['reply_id']}" for row in routing
        ),
        "evidence_quotes": [text[:300] for text, _ in routed][-6:],
        "reply_fr": (last_reply or "…")[:450],
        "needs_clarification": False,
        "resolution_fr": resolution_fr[:450],
        "summary_native": summary[:350],
        "callback_fr": resolution_fr[:220],
        "commitments": [],
        "resolved_commitment_ids": [],
        "chapter_resolved": season_ctx.get("position", {}).get("day_in_segment") == 2,
        "demonstrated_target_ids": [],
        "feeling_shift": "steady",
        "development_index": 0,
        "season_turns": routing,
        "usage": [],
        "revision": engine.story_revision(db, user),
    }


# ---------------------------------------------------------------------------
# Settling a day
# ---------------------------------------------------------------------------


def _position_of(season: Season, row: dict[str, Any]) -> Position | None:
    segment = next((seg for seg in season.segments if seg.id == row.get("segment")), None)
    if segment is None:
        return None
    return Position(
        season_id=season.id,
        segment=segment,
        segment_index=season.segments.index(segment),
        day_in_segment=int(row.get("day_in_segment") or 1),
        season_day=int(row.get("season_day") or 1),
        flex=int(row.get("flex") or 0),
    )


def settle(
    live: dict[str, Any],
    *,
    story_context: dict[str, Any],
    details: dict[str, Any],
    event_id: str,
    date_iso: str | None,
    day_index: int,
    relationships: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The season state once a day's exchange is settled (idempotent per event)."""

    season_ctx = story_context.get(SEASON_CONTEXT_KEY) or {}
    if not season_ctx.get("id"):
        return live
    season = load_season(str(season_ctx["id"]))
    state = dict(live.get(SEASON_KEY) or {"id": season.id})
    state.setdefault("id", season.id)
    if any(row.get("event_id") == event_id for row in state.get("played") or []):
        return live
    pos = _position_of(season, season_ctx.get("position") or {})
    seed = str(season_ctx.get("seed") or "")
    if season_ctx.get("kind") == "tentpole":
        state = _settle_tentpole(season, state, season_ctx, details, event_id=event_id, day=day_index, seed=seed)
    else:
        state = _settle_gap(season, state, season_ctx, details, event_id=event_id, day=day_index)
    if pos is not None:
        state = record_played(state, pos, date_iso=date_iso, event_id=event_id)
    live = dict(live)
    live[SEASON_KEY] = state
    if relationships is not None:
        _apply_registers(season, state, relationships)
    return live


def _settle_tentpole(season: Season, state: dict, season_ctx: dict, details: dict, *, event_id: str, day: int, seed: str) -> dict:
    page = season_ctx.get("page") or {}
    turns = {turn.get("id"): turn for turn in turns_of(page)}
    projected = {turn.get("id"): turn for turn in season_ctx.get("turns") or []}
    turns.update({key: value for key, value in projected.items() if key not in turns})
    routing = list(details.get("season_turns") or [])
    answered = set()
    convinced: dict[str, set[str]] = {}
    for position_in_day, row in enumerate(routing):
        turn = turns.get(row.get("turn_id"))
        if not turn:
            continue
        answered.add(turn.get("id"))
        reply = reply_by_id(turn, row.get("reply_id"))
        if turn.get("convince"):
            convinced.setdefault(str(turn.get("id")), set()).add(str(reply.get("id")))
        if row.get("gate"):
            # The gate's own signal first: what this reply expressed colours the
            # path its conditional sets read (T5: «je veux toi ici» on the romance path).
            state = add_signal(
                state,
                gate=row.get("gate"),
                signal=row.get("signal") or "none",
                source=f"{event_id}:{turn.get('id')}:{position_in_day}",
                day=day,
            )
        flags = effective_flags(season, state, seed=seed)
        state = apply_sets(season, state, turn.get("sets"), source=f"{turn.get('id')}")
        state = apply_sets(season, state, reply.get("sets"), source=f"{turn.get('id')}/{reply.get('id')}")
        state = apply_sets(
            season,
            state,
            conditional_sets(_sets_if(turn) + _sets_if(reply), flags),
            source=f"{turn.get('id')}/{reply.get('id')}/if",
        )
        if row.get("value") and turn.get("value_flag"):
            state = apply_sets(season, state, {turn["value_flag"]: row["value"]}, source=f"{turn.get('id')}/value")
    # WP-113: a «Convaincre» argued to its last objection without landing fails.
    for turn_id, replies in convinced.items():
        if not replies & {"lands", "give_up"}:
            state = apply_sets(season, state, (turns.get(turn_id) or {}).get("convince", {}).get("sets_on_fail"), source=f"{turn_id}/fail")
    # Turns the day's reply did not reach still set what they set whatever is said.
    for turn in turns_of(page):
        if turn.get("id") not in answered:
            state = apply_sets(season, state, turn.get("sets"), source=f"{turn.get('id')}/unplayed")
    # Solves the page could not pose yet (WP-112) take the story's default; a choice
    # the learner made (WP-113) was settled above with the turns.
    for solve in solves_of(page):
        if solve.get("id") in answered:
            continue
        option = option_by_id(solve, solve.get("default"))
        if option is None and solve.get("flag") == "s1.camille_gender":
            gender = effective_flags(season, state, seed=seed).get("s1.camille_gender")
            option = next(
                (row for row in solve.get("options") or [] if (row.get("sets") or {}).get("s1.camille_gender") == gender),
                None,
            )
        if option is not None:
            flags = effective_flags(season, state, seed=seed)
            state = apply_sets(season, state, option.get("sets"), source=f"{solve.get('id')}/default")
            state = apply_sets(season, state, conditional_sets(_sets_if(option), flags), source=f"{solve.get('id')}/default/if")
        elif solve.get("mechanic") == "convaincre" and solve.get("sets_on_fail"):
            state = apply_sets(season, state, solve.get("sets_on_fail"), source=f"{solve.get('id')}/default")
    position = season_ctx.get("position") or {}
    tentpole = season.tentpoles.get(str(position.get("segment")))
    if tentpole is not None and int(position.get("day_in_segment") or 0) == 2:
        state = apply_sets(season, state, tentpole.state_out, source=f"{tentpole.id}/state_out")
    return state


def _sets_if(row: dict[str, Any]):
    from app.services.season.format import SetsIf

    return [SetsIf.model_validate(item) for item in row.get("sets_if") or []]


def _settle_gap(season: Season, state: dict, season_ctx: dict, details: dict, *, event_id: str, day: int) -> dict:
    position = season_ctx.get("position") or {}
    gap = season.gaps.get(str(position.get("segment")))
    if gap is None:
        return state
    allowed = set(gap.sets_allowed)
    wanted = {
        str(row.get("flag")): row.get("value")
        for row in details.get("season_flags") or []
        if isinstance(row, dict) and str(row.get("flag")) in allowed and row.get("value") not in (None, "")
    }
    if wanted:
        state = apply_sets(season, state, wanted, source=f"{gap.id}.{position.get('day_in_segment')}")
    checklist = season_ctx.get("checklist") or {}
    # Only what the day says it staged counts: a scheduled moment the draft skipped
    # stays owed (``director.gap_brief`` offers it again).
    premise = checklist.get("premise_id")
    if premise and not any(row.id == premise for row in gap.premises):
        premise = None
    # WP-113 (owner OK 2026-10-02): the in-between story moves on the learner's
    # engagement, not the calendar. A day the learner did not take up (the turn
    # ended «not_yet») leaves its scheduled moment owed; it is staged again.
    engaged = details.get("outcome") in (None, "met", "partially_met")
    if premise and not engaged:
        premise = None
    # WP-113: today's complication card is tomorrow's obstacle (faced today, it is
    # replaced by today's own, or cleared).
    complication = str(checklist.get("complication") or "").strip()
    if complication:
        state["obstacle"] = {"gap": gap.id, "text": complication[:240], "day": int(day), "event_id": event_id}
    else:
        state.pop("obstacle", None)
    if premise:
        rows = [row for row in state.get("premises") or [] if isinstance(row, dict)]
        if not any(row.get("gap") == gap.id and row.get("premise") == premise for row in rows):
            rows.append({"gap": gap.id, "premise": premise, "day": int(day), "event_id": event_id})
        state["premises"] = rows
    moment = checklist.get("small_moment_id")
    if moment:
        moments = list(state.get("moments") or [])
        if moment not in moments:
            moments.append(moment)
        state["moments"] = moments
    staged = next((row for row in gap.premises if row.id == premise), None) if premise else None
    gate = season_ctx.get("gate") or (staged.gate if staged else None)
    signal = details.get("season_signal")
    if gate and signal:
        state = add_signal(state, gate=gate, signal=signal, source=f"{event_id}:gap", day=day)
    return state


def _apply_registers(season: Season, state: dict, relationships: dict[str, Any]) -> None:
    """``register.<cast id>`` flags (Gus's vous until T3) onto the relationship map."""

    flags = effective_flags(season, state)
    for member in season.cast:
        value = flags.get(f"register.{member.id}") or member.address
        entry = dict(relationships.get(member.id) or {})
        if entry.get("register") != value:
            entry["register"] = value
            relationships[member.id] = entry


def initial_state(season_id: str) -> dict[str, Any]:
    return {"id": season_id, "played": [], "flags": {}, "signals": []}


def initial_relationships(season_id: str) -> dict[str, Any]:
    season = load_season(season_id)
    return {member.id: {"register": member.address, "closeness": 0} for member in season.cast if not member.minor}


def holds_for(today: Today, cond: dict | None) -> bool:
    return holds(cond, today.flags, band=today.band)


def spoken(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return spoken_lines(panels)


__all__ = [
    "SEASON_CONTEXT_KEY",
    "SEASON_KEY",
    "Today",
    "context_block",
    "enabled_season",
    "evaluate_tentpole_turn",
    "initial_relationships",
    "initial_state",
    "is_tentpole",
    "page_for",
    "payload_for_scene",
    "projected_turns",
    "reaction_native",
    "season_id_for",
    "settle",
    "tentpole_brief",
    "today_for",
]
