"""WP-124a «La reprise»: a lost day of a season life re-reads the last season page.

When the director cannot write a gap day (a guard refused both drafts, the
provider is down, the story moved under the draft), a learner on the authored
season used to get one of the three generic authored scenes — a stranger's café
welcome in the «vous» of strangers, with no translation at A1 (EXPERIENCE-REVIEW
2026-10-04 §2.3 F-5). Owner decision 1(a)/(c): a season life never meets those
scenes; the stand-in is an honest *reprise* of the last page the learner played.

**Which page.** The season's pages are its tentpole days (the owner-approved
bible); a gap day is generated, and re-serving it would need the model that just
failed. So the reprise is the last *completed, resolved tentpole day* of the
learner's played log:

* first choice, the page exactly as it was served (``script_payload["season_page"]``
  of the completed scene), with the replies the learner actually took
  (``script_payload["season_routing"]``) — their real branch;
* a learner whose level (or chrome language) changed since gets the same day
  re-resolved at their band, kept only when the bible picks the same variant;
* a life with no stored scene for that day (a life moved by ``admin.jump_to_day``,
  or stored before the scene kept its page) gets the day re-resolved from the
  bible with the learner's current flags; each turn keeps the replies that agree
  with those flags.
* **No page at all** (a failure before T1 Day B was ever completed — in practice
  only a broken season file, since T1 is authored and needs no model) returns
  ``None``: the caller keeps the honest «unavailable, retry» day. The generic
  scenes are never the answer for a season life.

**What it is not.** The reprise is served as a tentpole page (the page answers in
its own words, the matcher routes the reply — no model call), but it is marked
``season_ctx["reprise"]``: the journey never binds it to the living story, never
settles it, and so it applies no flag, signal, reward or consequence and does
not move the season's day count (``clock.record_played`` is only reached through
``runtime.settle``). Every reply on its turns is inert (``sets`` stripped) as a
second guard. The learning evidence its practice produces is earned as on any day.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.services.season.clock import SEASON_KEY, played_log
from app.services.season.page import choice_cards, project, resolve_day

logger = logging.getLogger(__name__)

#: ``story_context["season"][REPRISE_KEY]`` marks a reprise (and says of which day).
REPRISE_KEY = "reprise"
#: ``plan_selection["generation_fallback"]["kind"]`` for a reprise day.
REPRISE_FALLBACK_KIND = "season_reprise"
#: ``ScenarioBrief.scenario_key`` prefix; the rest is the page's key (``t1.b``).
REPRISE_SCENARIO_PREFIX = "season_reprise:"
#: ``ScenarioBrief.content_version`` of a reprise brief.
REPRISE_CONTENT_VERSION = "season-reprise-1"
#: How many of the learner's latest scenes are read to find the page.
SCENE_SCAN_LIMIT = 120
#: What a reprise reply never carries: anything that would move the story.
_CONSEQUENCE_FIELDS = ("sets", "sets_if", "sets_on_fail", "value_flag")

#: The honest one-line note, in the learner's language (the review's «Aujourd'hui,
#: on relit.»). No praise. Kept here, in the shape of ``learner_copy.LEARNER_COPY``
#: rows, until that table takes them (see the WP-124a report).
REPRISE_COPY: dict[str, dict[str, str]] = {
    "season_reprise_note": {
        "en": "Today, we re-read.",
        "de": "Heute lesen wir noch einmal.",
        "fr": "Aujourd'hui, on relit.",
    },
    "season_reprise_summary": {
        "en": "A re-read of «{title}». The story did not move on today.",
        "de": "Noch einmal gelesen: «{title}». Die Geschichte ist heute nicht weitergegangen.",
        "fr": "Relecture de «{title}». L'histoire n'a pas avancé aujourd'hui.",
    },
}


def reprise_text(key: str, language: str | None, **fields: Any) -> str:
    from app.services.learner_copy import copy_language

    row = REPRISE_COPY[key]
    template = row.get(copy_language(language)) or row["en"]
    try:
        return template.format(**fields) if fields else template
    except (KeyError, IndexError, ValueError):  # pragma: no cover - authored above
        return template


def is_reprise(story_context: dict[str, Any] | None) -> bool:
    """Is this brief a WP-124a reprise (never bound, never settled)?"""

    from app.services.season.runtime import SEASON_CONTEXT_KEY

    season_ctx = (story_context or {}).get(SEASON_CONTEXT_KEY) if isinstance(story_context, dict) else None
    return isinstance(season_ctx, dict) and bool(season_ctx.get(REPRISE_KEY))


# ---------------------------------------------------------------------------
# Finding the page
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LastPage:
    page: dict[str, Any]
    #: ``[{turn_id, reply_id, learner}]`` as the learner played it ([] when unknown).
    routing: list[dict[str, Any]]
    #: The played-log row of that day (``segment``, ``day_in_segment``, ``key`` …).
    row: dict[str, Any]
    #: "stored", "stored_relevelled" or "bible".
    source: str
    season_id: str
    state: dict[str, Any]


def _thread_and_state(db, user) -> tuple[Any, dict[str, Any] | None]:
    from app.services.living_story import STATE_KEY, _active_thread

    thread = _active_thread(db, user)
    live = ((thread.state or {}) if thread else {}).get(STATE_KEY) or {}
    state = live.get(SEASON_KEY)
    return thread, (dict(state) if isinstance(state, dict) and state.get("id") else None)


def _stored_page(db, user, thread, key: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    """The completed scene of that tentpole day: its page and the learner's route."""

    from sqlalchemy import select

    from app.db.models.graphic_novel import GraphicNovelScene

    scenes = db.scalars(
        select(GraphicNovelScene)
        .where(
            GraphicNovelScene.user_id == user.id,
            GraphicNovelScene.serial_thread_id == thread.id,
            GraphicNovelScene.status == "completed",
        )
        .order_by(GraphicNovelScene.created_at.desc())
        .limit(SCENE_SCAN_LIMIT)
    ).all()
    for scene in scenes:
        payload = scene.script_payload if isinstance(scene.script_payload, dict) else {}
        season = payload.get("season") if isinstance(payload.get("season"), dict) else {}
        page = payload.get("season_page")
        if season.get("kind") == "tentpole" and season.get("key") == key and isinstance(page, dict):
            routing = [row for row in payload.get("season_routing") or [] if isinstance(row, dict)]
            return page, routing
    return None


def _resolve(season, row: dict[str, Any], *, flags: dict, band: str, language: str, local_date) -> dict[str, Any] | None:
    from app.services.season.runtime import off_calendar

    letter = "a" if int(row.get("day_in_segment") or 1) == 1 else "b"
    tentpole = season.tentpoles.get(str(row.get("segment")))
    holiday = next((day.holiday for day in (tentpole.days if tentpole else []) if day.day == letter and day.holiday), None)
    return resolve_day(
        season,
        str(row.get("segment")),
        letter,
        flags=flags,
        band=band,
        language=language,
        neutral=off_calendar(holiday, local_date),
    )


def last_page(db, user, *, now: Any = None) -> LastPage | None:
    """The last completed, resolved season page of this life, at the learner's level."""

    from app.services.chrome_language import user_chrome_language
    from app.services.living_story import learner_level_band
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.runtime import learner_date

    thread, state = _thread_and_state(db, user)
    if thread is None or state is None:
        return None
    rows = [row for row in played_log(state) if row.get("kind") == "tentpole" and row.get("segment")]
    if not rows:
        return None
    row = rows[-1]
    try:
        season = load_season(str(state["id"]))
    except Exception:  # noqa: BLE001 - a broken season file leaves the day unavailable
        logger.exception("season reprise: %s could not be loaded", state.get("id"))
        return None
    band = learner_level_band(user)
    language = user_chrome_language(user)
    flags = effective_flags(season, state, seed=str(user.id))
    local = learner_date(user, now)
    stored = _stored_page(db, user, thread, str(row.get("key")))
    if stored is not None:
        page, routing = stored
        if page.get("band") == band and page.get("language") == language:
            return LastPage(page, routing, row, "stored", season.id, state)
        # The learner's level moved since: the same day, at their band — only when
        # the bible picks the same variant (the branch they actually played).
        again = _resolve(season, row, flags=flags, band=band, language=language, local_date=local)
        if again is not None and again.get("variant") == page.get("variant"):
            return LastPage(again, routing, row, "stored_relevelled", season.id, state)
        return LastPage(page, routing, row, "stored", season.id, state)
    page = _resolve(season, row, flags=flags, band=band, language=language, local_date=local)
    if page is None:
        return None
    return LastPage(page, [], row, "bible", season.id, state)


# ---------------------------------------------------------------------------
# The learner's branch, made inert
# ---------------------------------------------------------------------------


def _agrees(reply: dict[str, Any], flags: dict[str, Any]) -> bool:
    sets = reply.get("sets") or {}
    return bool(sets) and all(flags.get(key) == value for key, value in sets.items())


def _inert(node: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in node.items() if key not in _CONSEQUENCE_FIELDS}


def pinned_turns(turns: list[dict[str, Any]], routing: list[dict[str, Any]], flags: dict[str, Any]) -> list[dict[str, Any]]:
    """Each turn keeps the replies the learner actually took (their real branch):
    from the stored route, else the replies whose ``sets`` the current flags show.
    A turn with no evidence keeps all its replies. Nothing a reply sets survives."""

    out: list[dict[str, Any]] = []
    for turn in turns:
        replies = [reply for reply in turn.get("replies") or [] if isinstance(reply, dict)]
        taken = {str(row.get("reply_id")) for row in routing if str(row.get("turn_id")) == str(turn.get("id"))}
        kept = [reply for reply in replies if str(reply.get("id")) in taken]
        if not kept and not routing:
            kept = [reply for reply in replies if _agrees(reply, flags)]
        kept = kept or replies
        pinned = _inert({**turn, "replies": [_inert(reply) for reply in kept]})
        if isinstance(pinned.get("convince"), dict):
            pinned["convince"] = _inert(pinned["convince"])
        out.append(pinned)
    return out


# ---------------------------------------------------------------------------
# The brief
# ---------------------------------------------------------------------------


def _public_panels(scene_panels: list[dict[str, Any]], *, language: str, names: dict[str, str]) -> list[dict[str, Any]]:
    """The scene step's page, in the authored-scene shape the reader draws
    (``journey_content.authored_panels``) — with each line's translation and mood."""

    from app.schemas.daily_journey import ScenePanel, ScenePanelLine
    from app.services.season.runtime import _engine_panel
    from app.services.season.world import plate_for

    # The scene step's public schema decides what reaches the learner: a line's
    # translation and mood travel once ``ScenePanelLine`` carries them (the WP-124a
    # report's schema patch); until then they stay in the private draft.
    line_fields = set(ScenePanelLine.model_fields)
    panel_fields = set(ScenePanel.model_fields)
    panels = []
    for index, panel in enumerate(scene_panels):
        engine_panel = _engine_panel(panel, language=language)
        plate = plate_for(panel.get("location_id"))
        row = {
            "id": f"reprise-{index}",
            "index": index,
            "narration_fr": engine_panel["narration_fr"],
            "dialogue": [
                {
                    key: value
                    for key, value in {
                        "character_id": line["character_id"],
                        "character_name": names.get(line["character_id"]),
                        "text_fr": line["text_fr"],
                        "text_native": line.get("text_native"),
                        "mood": line.get("mood") or "neutral",
                    }.items()
                    if key in line_fields
                }
                for line in engine_panel["dialogue"]
                if line.get("text_fr")
            ],
            "image_url": plate,
            "image_status": "setting_reference" if plate else "unavailable",
            "plate_url": plate,
            "alt_native": engine_panel.get("alt_native"),
        }
        panels.append({key: value for key, value in row.items() if key in panel_fields})
    return panels


def reprise_brief(db, user, *, input_mode: Any = None, now: Any = None, reason: str = ""):
    """Today's reprise as a brief the journey plans (or ``None``: no page to re-read)."""

    from app.services.chrome_language import user_chrome_language
    from app.services.journey_contracts import ResponseTask, ScenarioBrief
    from app.services.season.flags import effective_flags
    from app.services.season.format import load_season
    from app.services.season.page import exchanges_for, hook_caption
    from app.services.season.runtime import (
        SEASON_CONTEXT_KEY,
        Today,
        _position_of,
        authored_draft,
        learner_date,
        page_tail,
        panel_images,
        projected_turns,
        tentpole_annotation,
    )
    from app.services.season.world import location_name_fr, plate_for

    found = last_page(db, user, now=now)
    if found is None:
        return None
    season = load_season(found.season_id)
    pos = _position_of(season, found.row)
    if pos is None:
        return None
    page = found.page
    language = user_chrome_language(user)
    flags = effective_flags(season, found.state, seed=str(user.id))
    turns = pinned_turns(projected_turns(page), found.routing, flags)
    if not turns:
        return None
    today = Today(
        season=season,
        pos=pos,
        state=found.state,
        flags=flags,
        seed=str(user.id),
        band=str(page.get("band") or "A1"),
        language=language,
        local_date=learner_date(user, now),
    )
    draft = authored_draft(today, page, turns)
    ending = draft.pop("_ending", {}) or {}
    # A re-read stamps no can-do: the day it was performed already did.
    draft["can_do_id"] = None
    names = {member.id: member.name for member in season.cast}
    character_id = str(draft["character_id"])
    character_name = names.get(character_id) or character_id
    note = reprise_text("season_reprise_note", language)
    title = str(page.get("title_fr") or season.title_fr)
    summary = reprise_text("season_reprise_summary", language, title=title)
    scene_panels = project(page)["scene_panels"]
    panels = _public_panels(scene_panels, language=language, names=names)
    last_posed = max(
        (i for i, turn in enumerate(turns) if turn.get("from_solve") in ("choix", "convaincre") or turn.get("gate")),
        default=-1,
    )
    exchanges = sum(exchanges_for(turn) for turn in turns)
    repeats = any(reply.get("repeat_once") for turn in turns for reply in turn.get("replies") or [])
    objective = f"{note} {draft['objective_native']}".strip()
    task = ResponseTask(
        objective_native=objective[:320],
        character_id=character_id,
        character_name=character_name,
        opening_line_fr=draft["opening_line_fr"],
        max_turns=max(1, exchanges + (1 if repeats else 0)),
        required_intents=[draft["objective_semantics"]],
        allowed_outcomes=["resolved", "open"],
        rubric_native=draft["objective_semantics"],
        suggested_response_fr=draft["suggested_response_fr"],
        hint_native=draft["hint_native"],
        translation_native=draft["translation_native"],
        estimated_seconds=60 * max(1, len(turns)),
        min_turns=sum(exchanges_for(turn) for turn in turns[: last_posed + 1]),
        opening_choices=choice_cards(turns[0]),
    )
    ending_fr = str((ending or {}).get("text_fr") or hook_caption(page) or title)
    season_ctx = {
        "id": season.id,
        # Answered as an authored page (``runtime.is_tentpole``) — its own words,
        # no director. The reprise marker keeps it out of the living story.
        "kind": "tentpole",
        REPRISE_KEY: {
            "key": pos.key,
            "source": found.source,
            "played_on": found.row.get("date"),
            "reason": str(reason or "")[:120],
            # The reply router's cache key (a reprise has no scene of its own).
            "token": uuid.uuid4().hex,
        },
        "position": pos.as_dict(),
        "page": page,
        "turns": turns,
        "ending": ending,
        "tail": page_tail(page),
        "panel_images": panel_images(page, scene_panels),
        "seed": str(user.id),
        "units": list(tentpole_annotation(season.id, pos.key).get("units") or []),
    }
    brief = ScenarioBrief(
        scenario_key=f"{REPRISE_SCENARIO_PREFIX}{pos.key}",
        content_version=REPRISE_CONTENT_VERSION,
        title_fr=title[:100],
        objective_key=f"{REPRISE_SCENARIO_PREFIX}{pos.key}",
        objective_native=objective[:320],
        level_band=str(page.get("band") or "A1"),
        character_id=character_id,
        character_name=character_name,
        location_id=str(draft["location_id"]),
        location_name=location_name_fr(draft["location_id"]),
        image_url=plate_for(draft["location_id"]),
        setup_fr=draft["premise_fr"],
        setup_native=f"{note} {draft['setup_native']}".strip()[:600],
        opening_line_fr=draft["opening_line_fr"],
        response_task=task,
        resolution_lines={"resolved": ending_fr[:450], "open": ending_fr[:450]},
        resolution_summaries={"resolved": summary, "open": summary},
        estimated_seconds=60 * int(page.get("minutes") or 6),
        # Not a chapter: no serial episode, no thread, nothing written to the story.
        is_authored_fallback=True,
        control_language=language,
        story_context={SEASON_CONTEXT_KEY: season_ctx, "draft": draft},
        panels=panels,
    )
    return brief


__all__ = [
    "REPRISE_COPY",
    "REPRISE_FALLBACK_KIND",
    "REPRISE_KEY",
    "REPRISE_SCENARIO_PREFIX",
    "LastPage",
    "is_reprise",
    "last_page",
    "pinned_turns",
    "reprise_brief",
    "reprise_text",
]
