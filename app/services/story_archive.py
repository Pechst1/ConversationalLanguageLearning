"""WP-96 «Les Cahiers du feuilleton» + WP-97 «Les suites» — the story you can reread.

A read-only projection of a learner's life in the Feuilleton, built from the
learner's **days** (``DailyJourney`` rows), not from the engine's scenes alone
(walk finding W14): the authored first day and every authored fallback day are
planches too, with their title, their date, their authored page, the learner's
own lines and the ending.

What the story engine writes on a scene's ``script_payload`` is read
defensively (the story lane's contract, WP-96/97):

* ``chapter`` = ``{index, title_fr, closes, digest_fr, season}``
* ``previously_fr`` = ``[str]`` (≤ 3 chronicle lines, «Précédemment»)
* ``margin_notes`` = ``[{text_fr, cause_scene_id, cause_date, character_id}]``
* ``tutoiement`` = ``{character_id, state}``

A scene written before that contract still has ``source_snapshot.chapter``
(``{id, title_fr, finale, …}``, WP-58/63) and the living story's chronicle, so a
legacy life still reads as chapters. Nothing here writes, except
:func:`mint_tutoiement_seal`, which the daily journey calls when a day ends.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.daily_journey import DailyJourney, DailyJourneyStep
from app.db.models.graphic_novel import GraphicNovelPanel, GraphicNovelScene
from app.db.models.serial import SerialThread

logger = logging.getLogger(__name__)

#: Journey statuses whose day happened (a planche exists for it).
LIVED_STATUSES = ("completed", "ended_early")
PROLOGUE_TITLE_FR = "Prologue"
MAX_MARGIN_NOTES = 5
MAX_PREVIOUSLY = 3
MAX_KNOWN_ABOUT_YOU = 5
TUTOIEMENT_SOURCE_KIND = "tutoiement"
SPECIAL_EPREUVE = "epreuve"
#: Speaker ids that are the learner, never a cast member.
_LEARNER_IDS = {"toi", "you", "learner", "vous", "user"}


# ---------------------------------------------------------------------------
# Reading one scene's story fields (the story lane's contract)
# ---------------------------------------------------------------------------


def _text(value: Any, limit: int = 400) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def margin_notes_of(payload: Any) -> list[dict[str, Any]]:
    """``script_payload.margin_notes``, sanitised. Malformed rows are dropped."""

    rows = (payload or {}).get("margin_notes") if isinstance(payload, dict) else None
    notes: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        text = _text(row.get("text_fr"), 280)
        if not text:
            continue
        cause = str(row.get("cause_scene_id") or "").strip() or None
        character = str(row.get("character_id") or "").strip() or None
        notes.append(
            {
                "text_fr": text,
                "cause_scene_id": cause,
                "cause_date": _iso_date(row.get("cause_date")),
                "character_id": character,
                "cause_edition_no": None,
                "panel_index": _int_or_none(row.get("panel_index")),
                "panel_id": str(row.get("panel_id") or "").strip() or None,
            }
        )
        if len(notes) >= MAX_MARGIN_NOTES:
            break
    return notes


def previously_of(payload: Any) -> list[str]:
    """``script_payload.previously_fr`` — at most three non-empty lines."""

    rows = (payload or {}).get("previously_fr") if isinstance(payload, dict) else None
    lines = [_text(line, 240) for line in rows if isinstance(line, str)] if isinstance(rows, list) else []
    return [line for line in lines if line][:MAX_PREVIOUSLY]


def chapter_of(payload: Any) -> dict[str, Any] | None:
    """``script_payload.chapter`` normalised, or ``None``."""

    raw = (payload or {}).get("chapter") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return None
    return {
        "index": _int_or_none(raw.get("index")),
        "title_fr": _text(raw.get("title_fr"), 120),
        "closes": bool(raw.get("closes")),
        "digest_fr": _text(raw.get("digest_fr"), 400) or None,
        "season": _int_or_none(raw.get("season")),
        "finale": bool(raw.get("finale")),
    }


def tutoiement_of(payload: Any) -> dict[str, str] | None:
    raw = (payload or {}).get("tutoiement") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        return None
    character = str(raw.get("character_id") or "").strip()
    state = str(raw.get("state") or "").strip().lower()
    if not character or not state:
        return None
    return {"character_id": character, "state": state}


def _engine_scenes(db: Session, user_id: Any) -> list[GraphicNovelScene]:
    from app.services.living_story import ENGINE_VERSION_PREFIX

    return list(
        db.scalars(
            select(GraphicNovelScene)
            .where(
                GraphicNovelScene.user_id == user_id,
                GraphicNovelScene.prompt_version.like(f"{ENGINE_VERSION_PREFIX}%"),
            )
            .order_by(GraphicNovelScene.created_at.asc(), GraphicNovelScene.id.asc())
        )
    )


def _scene_journey_id(scene: GraphicNovelScene) -> str | None:
    value = (scene.source_snapshot or {}).get("journey_id")
    return str(value) if value else None


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _journey_scene(db: Session, journey: DailyJourney) -> GraphicNovelScene | None:
    """The engine scene this day played, if it was an engine day."""

    from app.services.living_story import ENGINE_VERSION_PREFIX

    scene_id = None
    for step in journey.steps:
        brief = (step.private_task or {}).get("scenario_brief")
        if isinstance(brief, dict) and isinstance(brief.get("story_context"), dict):
            scene_id = brief["story_context"].get("scene_id")
            break
    key = _uuid(scene_id) if scene_id else None
    scene = db.get(GraphicNovelScene, key) if key else None
    if scene is None or scene.user_id != journey.user_id:
        return None
    if not str(scene.prompt_version or "").startswith(ENGINE_VERSION_PREFIX):
        return None
    return scene


def _resolve_cause_editions(db: Session, notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill ``cause_edition_no`` («— Nº 4») from the cause scene's own day."""

    from app.services.seals import edition_numbers

    wanted = {_uuid(note.get("cause_scene_id")) for note in notes} - {None}
    if not wanted:
        return notes
    try:
        scenes = list(db.scalars(select(GraphicNovelScene).where(GraphicNovelScene.id.in_(wanted))))
        journey_by_scene: dict[str, DailyJourney] = {}
        for scene in scenes:
            journey = db.get(DailyJourney, _uuid(_scene_journey_id(scene))) if _scene_journey_id(scene) else None
            if journey is not None:
                journey_by_scene[str(scene.id)] = journey
        editions = edition_numbers(db, journey_by_scene.values())
        for note in notes:
            journey = journey_by_scene.get(str(note.get("cause_scene_id")))
            if journey is not None:
                note["cause_edition_no"] = editions.get(journey.id)
                note["cause_date"] = note.get("cause_date") or journey.local_date.isoformat()
    except Exception:  # pragma: no cover - a margin note never costs the day
        logger.exception("story_archive: cause editions unreadable")
    return notes


def _attach_panel_ids(notes: list[dict[str, Any]], panel_ids: dict[int, str]) -> list[dict[str, Any]]:
    """Map a note's ``panel_index`` to the reader's public panel id."""

    for note in notes:
        if not note.get("panel_id") and note.get("panel_index") is not None:
            note["panel_id"] = panel_ids.get(int(note["panel_index"]))
    return notes


def _panel_ids(db: Session, scene: GraphicNovelScene | None) -> dict[int, str]:
    if scene is None:
        return {}
    return {
        int(row[0]): str(row[1])
        for row in db.execute(
            select(GraphicNovelPanel.panel_index, GraphicNovelPanel.id).where(
                GraphicNovelPanel.scene_id == scene.id
            )
        ).all()
    }


def scene_notes(db: Session, scene: GraphicNovelScene | None) -> list[dict[str, Any]]:
    """The scene's margin notes, with their cause's Nº and their panel's id."""

    if scene is None:
        return []
    notes = margin_notes_of(scene.script_payload)
    if not notes:
        return []
    if any(note.get("panel_index") is not None for note in notes):
        _attach_panel_ids(notes, _panel_ids(db, scene))
    return _resolve_cause_editions(db, notes)


def scene_step_story_fields(db: Session, journey: DailyJourney) -> dict[str, Any]:
    """«Précédemment» and the margin notes for the journey's scene step prompt."""

    scene = _journey_scene(db, journey)
    payload = scene.script_payload if scene is not None else {}
    return {
        "previously_fr": previously_of(payload),
        "margin_notes": scene_notes(db, scene),
    }


def _live_of(thread: SerialThread | None) -> dict[str, Any]:
    from app.services.living_story import STATE_KEY

    state = thread.state if thread is not None and isinstance(thread.state, dict) else {}
    live = state.get(STATE_KEY)
    return live if isinstance(live, dict) else {}


def _season_title(world: dict[str, Any], number: int) -> str:
    current = _int_or_none(world.get("season_number")) or 1
    title = _text(world.get("season_title_fr"), 120) if current == number else ""
    return title or f"Saison {number}"


def recap_story_fields(db: Session, journey: DailyJourney) -> dict[str, Any]:
    """The recap's «Fin du chapitre», «Tome N» and today's margin notes."""

    empty = {"margin_notes": [], "chapter_closed": None, "season_finished": None}
    scene = _journey_scene(db, journey)
    if scene is None:
        return empty
    payload = scene.script_payload or {}
    snapshot_chapter = (scene.source_snapshot or {}).get("chapter") or {}
    thread = db.get(SerialThread, scene.serial_thread_id) if scene.serial_thread_id else None
    live = _live_of(thread)
    world = thread.world_bible if thread is not None and isinstance(thread.world_bible, dict) else {}
    event_id = f"journey:{journey.id}:story"
    chronicle_row = next(
        (
            row
            for row in live.get("chronicle") or []
            if isinstance(row, dict) and row.get("event_id") == event_id
        ),
        None,
    )
    contract = chapter_of(payload)
    closes = bool((contract or {}).get("closes")) or chronicle_row is not None
    chapter_closed = None
    season_finished = None
    if closes:
        season = (contract or {}).get("season") or _int_or_none((chronicle_row or {}).get("season")) or (
            _int_or_none(live.get("season_index")) or _int_or_none(world.get("season_number")) or 1
        )
        index = (contract or {}).get("index")
        if index is None:
            index = _legacy_chapter_index(db, scene)
        chapter_closed = {
            "index": int(index or 1),
            "title_fr": (contract or {}).get("title_fr")
            or _text(snapshot_chapter.get("title_fr"), 120)
            or _text((chronicle_row or {}).get("title_fr"), 120),
            "digest_fr": (contract or {}).get("digest_fr")
            or (_text((chronicle_row or {}).get("resolved_fr"), 400) or None),
        }
        if snapshot_chapter.get("finale") or (contract or {}).get("finale"):
            season_finished = {"number": int(season), "title_fr": _season_title(world, int(season))}
    return {
        "margin_notes": scene_notes(db, scene),
        "chapter_closed": chapter_closed,
        "season_finished": season_finished,
    }


def _legacy_chapter_index(db: Session, scene: GraphicNovelScene) -> int:
    """The chapter's position among this life's chapters, from the scene records."""

    seen: list[str] = []
    for row in _engine_scenes(db, scene.user_id):
        chapter_id = str(((row.source_snapshot or {}).get("chapter") or {}).get("id") or "")
        if chapter_id and chapter_id not in seen:
            seen.append(chapter_id)
        if row.id == scene.id:
            break
    return max(1, len(seen))


# ---------------------------------------------------------------------------
# The archive — «Archives du journal»
# ---------------------------------------------------------------------------


@dataclass
class _Chapter:
    key: str
    season: int
    index: int
    title_fr: str
    closed: bool = False
    finale: bool = False
    digest_fr: str | None = None
    prologue: bool = False
    days: list[dict[str, Any]] = field(default_factory=list)
    journeys: list[DailyJourney] = field(default_factory=list)


def _season_by_ordinal(live: dict[str, Any], ordinal: int, current: int) -> int:
    """Which season the ``ordinal``-th engine day belongs to (legacy scenes)."""

    ends = sorted(
        
            (_int_or_none(row.get("ended_day")) or 0, _int_or_none(row.get("season")) or 1)
            for row in live.get("seasons") or []
            if isinstance(row, dict)
        
    )
    for ended_day, season in ends:
        if ordinal <= ended_day:
            return season
    return current


def _learner_lines(step: DailyJourneyStep | None) -> list[str]:
    turns = (step.private_task or {}).get("turns") if step is not None else None
    lines: list[str] = []
    for turn in turns if isinstance(turns, list) else []:
        if isinstance(turn, dict):
            text = _text(turn.get("learner"), 600)
            if text:
                lines.append(text)
    return lines


def _authored_panels(prompt: dict[str, Any]) -> list[dict[str, Any]] | None:
    panels = prompt.get("panels")
    if not isinstance(panels, list) or not panels:
        return None
    out = []
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        out.append(
            {
                "id": str(panel.get("id") or ""),
                "index": _int_or_none(panel.get("index")) or 0,
                "narration_fr": str(panel.get("narration_fr") or ""),
                "dialogue": [
                    {
                        "character_id": str(line.get("character_id") or ""),
                        "character_name": line.get("character_name"),
                        "text_fr": str(line.get("text_fr") or ""),
                    }
                    for line in panel.get("dialogue") or []
                    if isinstance(line, dict)
                ],
                "image_url": panel.get("image_url"),
            }
        )
    return out or None


def build_archive(db: Session, user: Any, *, season: int | None = None) -> dict[str, Any]:
    """The learner's whole Feuilleton as seasons of chapters of days.

    Seasons and chapters are newest first, days oldest first inside a chapter.
    Only one season (``season``, default the newest) carries its chapters; the
    others are headers (``loaded: false``), so the read is bounded by a season's
    worth of days however long the life is.
    """

    thread = db.scalars(
        select(SerialThread)
        .where(SerialThread.user_id == user.id)
        .order_by(SerialThread.created_at.desc())
    ).first()
    world = thread.world_bible if thread is not None and isinstance(thread.world_bible, dict) else {}
    live = _live_of(thread)
    current_season = (
        _int_or_none(live.get("season_index")) or _int_or_none(world.get("season_number")) or 1
    )

    journeys = list(
        db.scalars(
            select(DailyJourney)
            .where(DailyJourney.user_id == user.id, DailyJourney.status.in_(LIVED_STATUSES))
            .order_by(DailyJourney.local_date.asc(), DailyJourney.created_at.asc())
        )
    )
    scenes = _engine_scenes(db, user.id)
    scene_by_journey: dict[str, GraphicNovelScene] = {}
    for scene in scenes:
        journey_id = _scene_journey_id(scene)
        if journey_id:
            scene_by_journey[journey_id] = scene

    chronicle = [row for row in live.get("chronicle") or [] if isinstance(row, dict)]
    chronicle_by_id = {str(row.get("id")): row for row in chronicle if row.get("id")}
    chronicle_events = {str(row.get("event_id")): row for row in chronicle if row.get("event_id")}

    # 1. Every day into a chapter, in the order the life lived them.
    chapters: dict[str, _Chapter] = {}
    order: list[str] = []
    per_season_count: dict[int, int] = {}
    previous: _Chapter | None = None
    engine_ordinal = 0
    for journey in journeys:
        scene = scene_by_journey.get(str(journey.id))
        contract = chapter_of(scene.script_payload) if scene is not None else None
        stored = ((scene.source_snapshot or {}).get("chapter") or {}) if scene is not None else {}
        if scene is not None:
            engine_ordinal += 1
        day_season = (contract or {}).get("season")
        if day_season is None and scene is not None:
            day_season = _season_by_ordinal(live, engine_ordinal, current_season)
        if day_season is None:
            day_season = previous.season if previous is not None else 1

        key: str | None = None
        if stored.get("id"):
            key = f"id:{stored['id']}"
        elif contract is not None and contract.get("index") is not None:
            key = f"ix:{day_season}:{contract['index']}"

        if key is None:
            chapter = previous
            if chapter is None:
                key = "prologue"
                chapter = chapters.get(key)
                if chapter is None:
                    chapter = _Chapter(
                        key=key, season=1, index=0, title_fr=PROLOGUE_TITLE_FR, prologue=True
                    )
                    chapters[key] = chapter
                    order.append(key)
        else:
            chapter = chapters.get(key)
            if chapter is None:
                per_season_count[day_season] = per_season_count.get(day_season, 0) + 1
                index = (contract or {}).get("index") or per_season_count[day_season]
                chapter = _Chapter(
                    key=key,
                    season=int(day_season),
                    index=int(index),
                    title_fr=(contract or {}).get("title_fr") or _text(stored.get("title_fr"), 120),
                    finale=bool(stored.get("finale") or (contract or {}).get("finale")),
                )
                chapters[key] = chapter
                order.append(key)
                if previous is not None and previous.key != key:
                    # A later chapter opened, so the earlier one is over.
                    previous.closed = True
            chapter.finale = chapter.finale or bool(stored.get("finale"))
            if contract is not None:
                chapter.finale = chapter.finale or bool(contract.get("finale"))
                chapter.title_fr = chapter.title_fr or contract.get("title_fr") or ""
                chapter.closed = chapter.closed or bool(contract.get("closes"))
                chapter.digest_fr = contract.get("digest_fr") or chapter.digest_fr
            row = chronicle_events.get(f"journey:{journey.id}:story") or chronicle_by_id.get(
                str(stored.get("id") or "")
            )
            if row is not None:
                chapter.closed = True
                chapter.digest_fr = chapter.digest_fr or (_text(row.get("resolved_fr"), 400) or None)
        chapter.journeys.append(journey)
        previous = chapter

    # 2. Seasons, and which one is loaded.
    seasons: dict[int, list[_Chapter]] = {}
    for key in order:
        seasons.setdefault(chapters[key].season, []).append(chapters[key])
    if thread is not None and current_season not in seasons and journeys:
        seasons.setdefault(current_season, [])
    ended = {
        _int_or_none(row.get("season"))
        for row in live.get("seasons") or []
        if isinstance(row, dict)
    }
    numbers = sorted(seasons, reverse=True)
    loaded = season if season in seasons else (numbers[0] if numbers else None)

    def finished(number: int) -> bool:
        return (
            number in ended
            or any(n > number for n in numbers)
            or any(c.finale and c.closed for c in seasons.get(number, []))
        )

    # 3. The loaded season's days, read in bounded batches.
    loaded_chapters = seasons.get(loaded, []) if loaded is not None else []
    loaded_journeys = [j for c in loaded_chapters for j in c.journeys]
    days = _day_payloads(db, loaded_journeys, scene_by_journey)
    for chapter in loaded_chapters:
        chapter.days = [days[str(j.id)] for j in chapter.journeys if str(j.id) in days]

    newest = next((c for c in reversed([chapters[k] for k in order])), None)
    return {
        "seasons": [
            {
                "number": number,
                "title_fr": _season_title(world, number),
                "finished": finished(number),
                "loaded": number == loaded,
                "day_count": sum(len(c.journeys) for c in seasons[number]),
                "chapters": [
                    {
                        "index": chapter.index,
                        "title_fr": chapter.title_fr or f"Chapitre {chapter.index}",
                        "digest_fr": chapter.digest_fr,
                        "closed": chapter.closed,
                        "finale": chapter.finale,
                        "prologue": chapter.prologue,
                        "days": chapter.days,
                    }
                    for chapter in reversed(seasons[number])
                ]
                if number == loaded
                else [],
            }
            for number in numbers
        ],
        "current": {
            "season": newest.season if newest is not None else current_season,
            "chapter": newest.index if newest is not None else None,
        },
    }


def _day_payloads(
    db: Session,
    journeys: list[DailyJourney],
    scene_by_journey: dict[str, GraphicNovelScene],
) -> dict[str, dict[str, Any]]:
    from app.services.seals import edition_numbers

    if not journeys:
        return {}
    ids = [journey.id for journey in journeys]
    steps: dict[Any, dict[str, DailyJourneyStep]] = {}
    for step in db.scalars(
        select(DailyJourneyStep)
        .where(
            DailyJourneyStep.journey_id.in_(ids),
            DailyJourneyStep.kind.in_(("scene", "respond", "resolution")),
        )
        .order_by(DailyJourneyStep.ordinal.asc())
    ):
        steps.setdefault(step.journey_id, {}).setdefault(step.kind, step)

    scene_ids = [scene_by_journey[str(i)].id for i in ids if str(i) in scene_by_journey]
    first_art: dict[Any, str] = {}
    panel_ids: dict[Any, dict[int, str]] = {}
    if scene_ids:
        for panel in db.scalars(
            select(GraphicNovelPanel)
            .where(GraphicNovelPanel.scene_id.in_(scene_ids))
            .order_by(GraphicNovelPanel.scene_id, GraphicNovelPanel.panel_index.asc())
        ):
            panel_ids.setdefault(panel.scene_id, {})[int(panel.panel_index)] = str(panel.id)
            if panel.image_url and panel.scene_id not in first_art:
                first_art[panel.scene_id] = panel.image_url
    try:
        editions = edition_numbers(db, journeys)
    except Exception:  # pragma: no cover - an edition number never costs the page
        logger.exception("story_archive: edition numbers unreadable")
        editions = {}
    edition_by_scene = {
        str(scene_by_journey[str(j.id)].id): editions.get(j.id)
        for j in journeys
        if str(j.id) in scene_by_journey
    }

    out: dict[str, dict[str, Any]] = {}
    for journey in journeys:
        scene = scene_by_journey.get(str(journey.id))
        kinds = steps.get(journey.id, {})
        scene_prompt = dict((kinds.get("scene").public_prompt or {}) if kinds.get("scene") else {})
        resolution = dict(
            (kinds.get("resolution").public_prompt or {}) if kinds.get("resolution") else {}
        )
        snapshot = journey.scenario_snapshot if isinstance(journey.scenario_snapshot, dict) else {}
        payload = scene.script_payload if scene is not None and isinstance(scene.script_payload, dict) else {}
        authored = _authored_panels(scene_prompt) if scene is None else None
        image = (
            (first_art.get(scene.id) if scene is not None else None)
            or next((p.get("image_url") for p in authored or [] if p.get("image_url")), None)
            or scene_prompt.get("image_url")
            or snapshot.get("image_url")
        )
        ending = None
        if not resolution.get("story_pending"):
            ending = _text(resolution.get("character_line_fr"), 600) or None
        notes = margin_notes_of(payload)
        if scene is not None:
            _attach_panel_ids(notes, panel_ids.get(scene.id, {}))
        for note in notes:
            note["cause_edition_no"] = edition_by_scene.get(str(note.get("cause_scene_id")))
        can_do = payload.get("can_do_id")
        out[str(journey.id)] = {
            "date": journey.local_date.isoformat(),
            "journey_id": str(journey.id),
            "scene_id": str(scene.id) if scene is not None else None,
            "title_fr": (scene.title if scene is not None else "") or str(snapshot.get("title_fr") or ""),
            "edition_no": editions.get(journey.id),
            "image_url": image,
            "character_id": str(snapshot.get("character_id") or "") or None,
            "learner_lines": _learner_lines(kinds.get("respond")),
            "ending_fr": ending,
            "margin_notes": notes,
            "can_do_id": str(can_do) if can_do else None,
            "special": SPECIAL_EPREUVE if payload.get("special") == SPECIAL_EPREUVE else None,
            "authored": scene is None,
            "panels": authored,
        }
    return out


# ---------------------------------------------------------------------------
# WP-97 — the trombinoscope: trust, what they know, the «tu»
# ---------------------------------------------------------------------------


def _living_helper(name: str):
    try:
        from app.services import living_story
    except Exception:  # pragma: no cover
        return None
    helper = getattr(living_story, name, None)
    return helper if callable(helper) else None


def _trust(live: dict[str, Any], character_id: str) -> int | None:
    helper = _living_helper("trust_of")
    value: Any = None
    if helper is not None:
        try:
            value = helper(live, character_id)
        except Exception:  # pragma: no cover - a helper never costs the page
            logger.exception("story_archive: trust_of failed")
            value = None
    if value is None:
        entry = (live.get("moods") or {}).get(character_id)
        value = entry.get("trust") if isinstance(entry, dict) else None
    number = _int_or_none(value)
    return None if number is None else max(0, min(5, number))


def _known_about_you(
    live: dict[str, Any],
    character_id: str,
    *,
    journey_dates: dict[str, str],
) -> list[dict[str, Any]]:
    helper = _living_helper("known_about_learner")
    rows: list[Any] | None = None
    if helper is not None:
        try:
            rows = list(helper(live, character_id) or [])
        except Exception:  # pragma: no cover
            logger.exception("story_archive: known_about_learner failed")
            rows = None
    events = {
        str(row.get("id")): row for row in live.get("events") or [] if isinstance(row, dict)
    }
    if rows is None:
        # Fallback: the consequence ledger, where this character is a witness.
        rows = []
        for row in live.get("consequences") or []:
            if not isinstance(row, dict):
                continue
            event = events.get(str(row.get("event_id") or ""), {})
            witnesses = event.get("witnesses") or [row.get("character_id")]
            if character_id in witnesses:
                rows.append(row)
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, str):
            row = {"text_fr": row}
        if not isinstance(row, dict):
            continue
        text = _text(row.get("text_fr") or row.get("summary_fr"), 240)
        if not text:
            continue
        event_id = str(row.get("event_id") or row.get("source_event_id") or "")
        event = events.get(event_id, {})
        scene_id = row.get("scene_id") or event.get("scene_id")
        journey_id = event_id.split(":")[1] if event_id.startswith("journey:") else ""
        when = _iso_date(row.get("date")) or journey_dates.get(journey_id) or _iso_date(event.get("at"))
        out.append({"text_fr": text, "date": when, "scene_id": str(scene_id) if scene_id else None})
    # The newest first, and never the same sentence twice.
    seen: set[str] = set()
    unique = []
    for item in reversed(out):
        if item["text_fr"] in seen:
            continue
        seen.add(item["text_fr"])
        unique.append(item)
    return unique[:MAX_KNOWN_ABOUT_YOU]


def cast_memory(db: Session, thread: SerialThread) -> dict[str, dict[str, Any]]:
    """Per character: ``trust``, ``known_about_you``, ``register``, ``tu_since``."""

    world = thread.world_bible if isinstance(thread.world_bible, dict) else {}
    live = _live_of(thread)
    relationships = (thread.state or {}).get("relationships") if isinstance(thread.state, dict) else {}
    relationships = relationships if isinstance(relationships, dict) else {}
    journeys = {
        str(row[0]): row[1].isoformat()
        for row in db.execute(
            select(DailyJourney.id, DailyJourney.local_date).where(
                DailyJourney.user_id == thread.user_id
            )
        ).all()
    }
    tu_since: dict[str, dict[str, Any]] = {}
    for scene in _engine_scenes(db, thread.user_id):
        tutoiement = tutoiement_of(scene.script_payload)
        if not tutoiement or tutoiement["state"] != "accepted":
            continue
        character = tutoiement["character_id"]
        if character in tu_since:
            continue
        journey_id = _scene_journey_id(scene) or ""
        tu_since[character] = {
            "date": journeys.get(journey_id)
            or (scene.created_at.date().isoformat() if scene.created_at else None),
            "scene_id": str(scene.id),
        }
    # The engine's own «tu» ledger (live.tutoiement), for a scene row since pruned.
    ledger = live.get("tutoiement") if isinstance(live.get("tutoiement"), dict) else {}
    for character, entry in ledger.items():
        if isinstance(entry, dict) and entry.get("state") == "accepted" and character not in tu_since:
            scene_id = entry.get("accepted_scene_id") or entry.get("scene_id")
            tu_since[str(character)] = {
                "date": _iso_date(entry.get("accepted_on")),
                "scene_id": str(scene_id) if scene_id else None,
            }
    out: dict[str, dict[str, Any]] = {}
    for member in world.get("cast") or []:
        if not isinstance(member, dict) or not member.get("id"):
            continue
        character = str(member["id"])
        entry = relationships.get(character) if isinstance(relationships.get(character), dict) else {}
        register = "tu" if character in tu_since or str(entry.get("register") or "") == "tu" else "vous"
        out[character] = {
            "trust": _trust(live, character),
            "known_about_you": _known_about_you(live, character, journey_dates=journeys),
            "register": register,
            "tu_since": tu_since.get(character),
        }
    return out


def mint_tutoiement_seal(db: Session, journey: DailyJourney) -> str | None:
    """WP-97: «Le tu de Romy» — a Seal in the Relevé, once per character.

    Pressed when the day's scene says the «tu» was accepted. A ``story_seal``
    collectible (what the Relevé's collection reads, ``GET /atelier/almanac``)
    keyed ``tutoiement`` / ``<thread>:<character>``, so a retry, a replay or a
    second acceptance finds the one already pressed. Never commits.
    """

    from app.services.atelier_rewards import STORY_SEAL, AtelierRewardService

    scene = _journey_scene(db, journey)
    tutoiement = tutoiement_of(scene.script_payload) if scene is not None else None
    if scene is None or not tutoiement or tutoiement["state"] != "accepted":
        return None
    character = tutoiement["character_id"]
    thread = db.get(SerialThread, scene.serial_thread_id) if scene.serial_thread_id else None
    world = thread.world_bible if thread is not None and isinstance(thread.world_bible, dict) else {}
    name = next(
        (
            str(member.get("name") or "").strip()
            for member in world.get("cast") or []
            if isinstance(member, dict) and str(member.get("id") or "") == character
        ),
        "",
    ) or character
    item, _created = AtelierRewardService(db)._mint(
        user_id=journey.user_id,
        kind=STORY_SEAL,
        source_kind=TUTOIEMENT_SOURCE_KIND,
        source_ref=f"{scene.serial_thread_id or journey.user_id}:{character}",
        metadata={
            "name": f"Le tu de {name}",
            "title_fr": f"Le tu de {name}",
            "date": journey.local_date.isoformat(),
            "character_id": character,
            "character_name": name,
            "scene_id": str(scene.id),
            "journey_id": str(journey.id),
            "source": TUTOIEMENT_SOURCE_KIND,
        },
        commit=False,
    )
    return str(item.id)


__all__ = [
    "build_archive",
    "cast_memory",
    "chapter_of",
    "margin_notes_of",
    "mint_tutoiement_seal",
    "previously_of",
    "recap_story_fields",
    "scene_step_story_fields",
    "tutoiement_of",
]
