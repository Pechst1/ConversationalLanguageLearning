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
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from dataclasses import replace as dc_replace
from datetime import date
from functools import lru_cache
from typing import Any

from app.config import settings
from app.services.season.clock import SEASON_KEY, Position, record_played
from app.services.season.director import gap_brief
from app.services.season.epilogue import after_settle, context_extra, position_for, season_finished
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
    reply_is_not_french,
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
    pos = position_for(season, state, today=local)
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
            today.season,
            today.pos,
            flags=today.flags,
            state=today.state,
            seed=today.seed,
            band=today.band,
        )
    # WP-132B: after the finale, what this life's ending leaves the continuation.
    block.update(context_extra(today))
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


def turn_example(turn: dict[str, Any] | None) -> str | None:
    """A turn's example reply for the hint: a polished one first, else any."""

    replies = (turn or {}).get("replies") or []
    return next(
        (reply["examples"][0] for reply in replies if reply.get("examples") and not reply.get("clumsy")),
        next((reply["examples"][0] for reply in replies if reply.get("examples")), None),
    )


def hint_for(turn: dict[str, Any] | None, language: str | None) -> str | None:
    """The turn's hint: the *opening* of an example reply to finish, never the whole
    reply — that is the «suggested response», one tap further (EXPERIENCE-REVIEW
    2026-10-04: hint and suggestion were the same sentence, so the hint taught
    nothing a learner could not copy)."""

    example = turn_example(turn)
    if not example:
        return None
    words = example.split()
    if len(words) >= 4:
        example = " ".join(words[: max(2, len(words) // 2)]) + " …"
    return f"{_EXAMPLE_LEAD.get(str(language or ''), _EXAMPLE_LEAD['en'])} «{example}»"[:400]


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
    example = turn_example(first) or opening_fr
    captions = [
        line for panel in scene for line in panel.get("lines") or [] if line.get("kind") == "caption"
    ]
    premise = str((captions[0] if captions else {}).get("text_fr") or page["title_fr"])
    # A page whose scene has no caption (every day B, the epilogue, some B1 day A)
    # used to fall back to its French title as the «native» setup, so a German or
    # English learner read «La lumière est fausse». The page's own can-do is already
    # in the learner's language: it stands in. A French-chrome learner keeps the title.
    premise_native = str((captions[0] if captions else {}).get("text_native") or "") or (
        premise if today.language == "fr" else str(page.get("can_do_native") or premise)
    )
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
            "dramatic_question": today.season.question.text(today.band)[:300],
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
        "hint_native": (hint_for(first, today.language) or f"{_EXAMPLE_LEAD.get(today.language, _EXAMPLE_LEAD['en'])} «{example}»")[:400],
        "translation_native": (opening_native or opening_fr)[:400],
        "capability_key": None,
        "lexicon": _lexicon(page, today.language, text),
        # T-1 (2026-10-03): the syllabus can-do this authored day practises.
        "can_do_id": tentpole_annotation(today.season.id, today.pos.key).get("can_do"),
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


def routes_the_story(turn: dict[str, Any]) -> bool:
    """Does what the learner answers here change the story? A «Le choix» or a
    «Convaincre», Lila's gate, a reply that sets (or conditionally sets) a flag,
    or a turn whose answer is a flag's value."""

    if turn.get("from_solve") in ("choix", "convaincre") or turn.get("gate") or turn.get("choice"):
        return True
    if turn.get("moment"):
        # WP-124b: a bridge's turn stages one of the gap's required moments.
        return True
    if turn.get("value_flag") or turn.get("sets_if"):
        return True
    return any(
        isinstance(reply, dict) and (reply.get("sets") or reply.get("sets_if"))
        for reply in turn.get("replies") or []
    )


def tentpole_brief(
    today: Today,
    context: dict[str, Any],
    *,
    page: dict[str, Any] | None = None,
    season_extra: dict[str, Any] | None = None,
):
    """Today's authored page as the brief the journey plans and binds. No model call.

    WP-124b: the recovery serves the next tentpole (``today.pos`` moved to it) or a
    bridge (``page`` given, a gap position) through here; ``season_extra`` marks the
    served day (``recovery`` / ``bridge``) so :func:`settle` records it honestly."""

    from app.services import living_story as engine

    page = page if page is not None else page_for(today)
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
        # T-1: the grammar units this page uses — the Règle step reviews one of
        # them instead of introducing a unit the authored page never says.
        "units": list(tentpole_annotation(today.season.id, today.pos.key).get("units") or []),
        **(season_extra or {}),
    }
    # One exchange per authored turn, plus one when a reply may ask the turn again
    # («Tu dis ça vite. Encore une fois ?»).
    repeats = any(reply.get("repeat_once") for turn in turns for reply in turn.get("replies") or [])
    # WP-113: the conversation must reach the day's last posed solve and Lila's gate
    # (both move the story), and a «Convaincre» can take one exchange per objection.
    # WP-129 (owner decision 2026-10-04): the A1/A2 core reply asks for fewer
    # exchanges, never fewer than the page needs — a turn whose answer routes the
    # story or sets a flag (its replies' ``sets`` / ``sets_if``, a ``value_flag``)
    # is never dropped either; only a turn whose ``sets`` hold whatever is said
    # may go unreached (``_settle_tentpole`` sets them).
    last_posed = max(
        (i for i, turn in enumerate(turns) if routes_the_story(turn)),
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


@lru_cache(maxsize=8)
def _season_units(season_id: str) -> dict[str, Any]:
    from app.services.season.format import SEASON_ROOT

    path = SEASON_ROOT / season_id / "units.json"
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")).get("days") or {})
    except (OSError, ValueError):
        return {}


def season_script_finished(live: dict | None) -> bool:
    """True once a life on a scripted season has played its last tentpole."""

    state = (live or {}).get(SEASON_KEY)
    if not isinstance(state, dict) or not state.get("id"):
        return False
    try:
        season = load_season(str(state["id"]))
    except Exception:  # noqa: BLE001 - an unreadable season is not a finished one
        return False
    return season_finished(season, state)


def tentpole_annotation(season_id: str, key: str) -> dict[str, Any]:
    """``{"units": [...], "can_do": id|None}`` for a tentpole day (``t1.a`` → ``t1a``),
    from ``scripts/season_units.py``; ``{}`` when the season has none."""

    return dict(_season_units(season_id).get(str(key).replace(".", ""), {}))


def tentpole_units(story_context: dict[str, Any] | None) -> list[str]:
    """The grammar units today's tentpole page uses ([] on any other day)."""

    season_ctx = (story_context or {}).get(SEASON_CONTEXT_KEY) or {}
    if season_ctx.get("kind") != "tentpole":
        return []
    return [str(unit) for unit in season_ctx.get("units") or []]


def is_tentpole(story_context: dict[str, Any] | None) -> bool:
    """Is today's reply answered by an authored page? Also true of a WP-124a reprise,
    which is a past page re-read (``season.reprise.is_reprise`` tells them apart)."""

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
            # QA-STORY: below the threshold no route was expressed — the fallback is
            # where the scene goes, not what the learner said.
            clear=score >= MATCH_THRESHOLD,
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
    # WP-124a: a reprise re-reads a page on a day the model already failed — its
    # replies are routed by the matcher alone, under the reprise's own cache key.
    reprise = season_ctx.get("reprise") if isinstance(season_ctx.get("reprise"), dict) else None
    if reprise is not None:
        scene_id = scene_id or f"reprise:{reprise.get('token') or ''}"
    use_model = reprise is None
    if answer.is_blank or not turns:
        return ResponseEvaluation(
            outcome=TaskOutcome.UNSCORED,
            assistance=assistance,
            observations=[],
            turn_consumed=False,
            pending=True,
            failure_reason="empty_answer" if answer.is_blank else "season_turn_missing",
        )
    # Replay the conversation so far to know which turn this is: the route each
    # exchange took is kept with it (QA-STORY); older exchanges are re-read.
    routed: list[tuple[str, dict[str, Any]]] = []
    asked: set[str] = set()
    for exchange in history or []:
        exchange = exchange or {}
        learner = str(exchange.get("learner") or "")
        route = exchange.get("route") if isinstance(exchange.get("route"), dict) else {}
        if exchange.get("free"):
            if route.get("reply") == ASK_AGAIN:
                asked.add(str(route.get("turn")))
            continue
        if not learner.strip():
            continue
        index, _ = _walk(turns, routed)
        if index >= len(turns):
            break
        kept = route.get("turn") == turns[index].get("id") and any(
            row.get("id") == route.get("reply") for row in turns[index].get("replies") or []
        )
        if kept:
            routed.append((learner, reply_by_id(turns[index], str(route.get("reply")))))
            continue
        choice = card_choice(turns[index], learner) or classify(db, user, scene_id=scene_id, turn=turns[index], text=learner, use_model=False)
        routed.append((learner, reply_by_id(turns[index], choice.reply_id)))
    index, answered = _walk(turns, routed)
    index = min(index, len(turns) - 1)
    turn = turns[index]
    carded = card_choice(turn, answer.text)
    if carded is None and reply_is_not_french(answer.text):
        # QA-CLOSE: a reply in German or English is never routed to a branch; the
        # addressee asks for it in French, in character, and the turn is still owed.
        return _ask_again_evaluation(
            db, user, scenario, task, answer, turn_index, assistance, history, turn, french_please=True
        )
    choice = carded or classify(
        db, user, scene_id=scene_id, turn=turn, text=answer.text, history=history, use_model=use_model
    )
    if (
        carded is None
        and not choice.clear
        and not turn.get("from_solve")
        and str(turn.get("id")) not in asked
        and turn.get("ask_again")
    ):
        # QA-STORY: the reply said none of what the turn is about (a name alone, a
        # greeting, another subject). The addressee asks once for the missing part;
        # nothing is assumed, nothing is spent. A second unclear reply takes the
        # turn's fallback.
        return _ask_again_evaluation(db, user, scenario, task, answer, turn_index, assistance, history, turn)
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
    # QA-STORY: every next question brings its own task line (it was only a posed
    # solve's, so turn 2 was asked under turn 1's task).
    next_task = str(upcoming_turn.get("task_native") or "") if upcoming_turn else ""
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
        next_hint_native=hint_for(upcoming_turn, (season_ctx.get("page") or {}).get("language")) if upcoming_turn else None,
        next_suggested_fr=turn_example(upcoming_turn) if upcoming_turn else None,
        next_translation_native=" ".join(
            str(line.get("text_native") or "")
            for line in ((upcoming_turn or {}).get("panel") or {}).get("lines") or []
            if line.get("text_native")
        ).strip() or None,
        route={"turn": str(turn.get("id")), "reply": str(reply.get("id"))},
    )


#: The route an «ask again» exchange records: no reply of the turn was expressed.
ASK_AGAIN = "__ask_again__"


def _cast_names(scenario) -> set[str]:
    season_ctx = scenario.story_context.get(SEASON_CONTEXT_KEY) or {}
    names: set[str] = {"Odile", "Margaux", "Lila", "Marin", "Gus", "Augustin", "Romy", "Camille", "Marchand"}
    try:
        season = load_season(str(season_ctx.get("id") or "s1"))
        for member in season.cast:
            names.update(part for part in member.name.replace("«", " ").replace("»", " ").split() if part[:1].isupper())
    except Exception:  # noqa: BLE001 - a name filter never costs a turn
        pass
    return names


def _named_turn(scenario, turn: dict[str, Any]) -> dict[str, Any]:
    """The turn with its addressee's display name. A «choix» posed as a turn carries
    ``to_name: None``; without a name the ask-again line read «lila_bonnet : Pardon ?»
    (EXPERIENCE-REVIEW 2026-10-04, A1 day 27 of the walk)."""

    if turn.get("to_name") or not turn.get("to"):
        return turn
    season_ctx = scenario.story_context.get(SEASON_CONTEXT_KEY) or {}
    try:
        season = load_season(str(season_ctx.get("id") or "s1"))
    except Exception:  # noqa: BLE001 - a missing name never costs the turn
        return turn
    name = next((member.name for member in season.cast if member.id == turn.get("to")), None)
    return {**turn, "to_name": name} if name else turn


def _ask_again_evaluation(db, user, scenario, task, answer, turn_index, assistance, history, turn, *, french_please=False):
    from app.services.journey_contracts import ResponseEvaluation, TaskOutcome
    from app.services.season.page import translates
    from app.services.season.turns import ask_again_panel, french_please_panel, reaction_lines
    from app.services.story_lanes import margin_correction

    turn = _named_turn(scenario, turn)
    if french_please:
        page = (scenario.story_context.get(SEASON_CONTEXT_KEY) or {}).get("page") or {}
        language = str(page.get("language") or "")
        panel = french_please_panel(turn, native=language if translates(page.get("band"), language) else None)
    else:
        panel = ask_again_panel(turn, answer.text, not_names=_cast_names(scenario))
    addressee = str(scenario.character_id)
    beats = [panel] if panel else []
    correction = margin_correction(
        db, user=user, scenario=scenario, task=task, answer=answer, turn_index=turn_index, history=history
    )
    return ResponseEvaluation(
        outcome=TaskOutcome.PARTIALLY_MET,
        assistance=assistance,
        observations=[],
        character_reply_fr=reaction_text(beats, addressee=addressee) or "…",
        correction=correction,
        needs_repair=True,
        # Free: the question is still owed, so the exchange it took is given back.
        turn_consumed=False,
        failure_reason="reply_source:authored_season",
        reply_lines=reaction_lines(beats, addressee=addressee),
        next_choices=[],
        next_task_native=str(turn.get("task_native") or "") or None,
        route={"turn": str(turn.get("id")), "reply": ASK_AGAIN},
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
    if not season_ctx.get("id") or season_ctx.get("reprise"):
        # WP-124a: a reprise re-reads a settled page; it settles nothing again and
        # is not a played season day.
        return live
    season = load_season(str(season_ctx["id"]))
    state = dict(live.get(SEASON_KEY) or {"id": season.id})
    state.setdefault("id", season.id)
    if any(row.get("event_id") == event_id for row in state.get("played") or []):
        return live
    pos = _position_of(season, season_ctx.get("position") or {})
    seed = str(season_ctx.get("seed") or "")
    extra: dict[str, Any] | None = None
    if season_ctx.get("kind") == "tentpole":
        state = _settle_tentpole(season, state, season_ctx, details, event_id=event_id, day=day_index, seed=seed)
    else:
        state = _settle_gap(season, state, season_ctx, details, event_id=event_id, day=day_index)
    # WP-124b: a bridge stages the gap's missing moments (and may close the gap); a
    # tentpole served by the recovery closes the gap it cut short. Both say so.
    if isinstance(season_ctx.get("bridge"), dict):
        state, extra = _settle_bridge(season, state, season_ctx, details, event_id=event_id, day=day_index, date_iso=date_iso)
    elif isinstance(season_ctx.get("recovery"), dict):
        state, extra = _settle_recovered_tentpole(season, state, season_ctx, event_id=event_id, date_iso=date_iso)
    if pos is not None:
        state = record_played(state, pos, date_iso=date_iso, event_id=event_id, extra=extra)
    live = dict(live)
    live[SEASON_KEY] = state
    # WP-132B: the archive day or the epilogue's last page closes the season; a
    # finished season's ending is carried into the life the continuation reads.
    live = after_settle(live, season_ctx, date_iso=date_iso, event_id=event_id)
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


def _shorten(state: dict, row: dict[str, Any]) -> dict:
    """Record a gap the recovery closed early (once per gap)."""

    from app.services.season.clock import SHORTENED_KEY

    rows = [item for item in state.get(SHORTENED_KEY) or [] if isinstance(item, dict)]
    if not any(item.get("gap") == row.get("gap") for item in rows):
        rows.append(row)
    state[SHORTENED_KEY] = rows
    return state


def _settle_bridge(
    season: Season, state: dict, season_ctx: dict, details: dict, *, event_id: str, day: int, date_iso: str | None
) -> tuple[dict, dict[str, Any]]:
    """WP-124b: the bridge's moments the learner played are staged (their turns
    answered); each staged moment's fixed fact is applied. When nothing the gap
    requires is still owed, the gap is closed: tomorrow is the next tentpole."""

    from app.services.season.director import used_premises

    bridge = season_ctx.get("bridge") or {}
    gap = season.gaps.get(str(bridge.get("gap")))
    if gap is None:
        return state, {"bridge": True}
    answered = {str(row.get("turn_id")) for row in details.get("season_turns") or [] if isinstance(row, dict)}
    rows = [row for row in state.get("premises") or [] if isinstance(row, dict)]
    staged: list[str] = []
    for moment in bridge.get("moments") or []:
        premise = str(moment.get("premise") or "")
        if not premise or not answered & {str(turn) for turn in moment.get("turns") or []}:
            continue  # the learner never reached it: still owed
        staged.append(premise)
        if not any(row.get("gap") == gap.id and row.get("premise") == premise for row in rows):
            rows.append({"gap": gap.id, "premise": premise, "day": int(day), "event_id": event_id, "bridge": True})
        state = apply_sets(season, state, moment.get("fixed") or {}, source=f"{gap.id}/bridge/{premise}")
    state["premises"] = rows
    state.pop("obstacle", None)
    owed = [need.premise for need in gap.required if need.premise not in used_premises(state, gap.id)]
    if not owed:
        played = sum(1 for row in state.get("played") or [] if isinstance(row, dict) and row.get("segment") == gap.id)
        segment = next((seg for seg in season.segments if seg.id == gap.id), None)
        state = _shorten(
            state,
            {
                "gap": gap.id,
                # This bridge day is one of the gap's played days.
                "played_days": played + 1,
                "nominal_days": segment.days if segment else None,
                "via": "bridge",
                "moments_bridged": staged,
                "reason": str((season_ctx.get("recovery") or {}).get("reason") or "")[:120],
                "date": date_iso,
                "event_id": event_id,
            },
        )
    return state, {"bridge": True, "moments": staged, "recovery": "bridge"}


def _settle_recovered_tentpole(
    season: Season, state: dict, season_ctx: dict, *, event_id: str, date_iso: str | None
) -> tuple[dict, dict[str, Any]]:
    """WP-124b: a tentpole Day A served after repeated failures cuts its gap short."""

    recovery = season_ctx.get("recovery") or {}
    gap_id = str(recovery.get("gap") or "")
    segment = next((seg for seg in season.segments if seg.id == gap_id), None)
    if segment is None or segment.kind != "gap":
        return state, {"recovery": "tentpole"}
    played = sum(1 for row in state.get("played") or [] if isinstance(row, dict) and row.get("segment") == gap_id)
    state = _shorten(
        state,
        {
            "gap": gap_id,
            "played_days": played,
            "nominal_days": segment.days,
            "via": "tentpole",
            "moments_bridged": [],
            "reason": str(recovery.get("reason") or "")[:120],
            "date": date_iso,
            "event_id": event_id,
        },
    )
    return state, {"recovery": "tentpole", "after_gap": gap_id}


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
