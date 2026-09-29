"""WP-98 «La saison suivante» — the story never runs out.

Three ways a finished season is followed, in this order (``living_story.roll_over_season``):

1. **Authored** — a season file exists (``serial.AUTHORED_SEASON_PATHS``: seasons 2 and 3).
2. **Written** — behind ``ATELIER_SEASON_WRITER_ENABLED`` (default off), season N+1's arcs
   are drafted from THIS learner's own material — the archived season questions, the
   plants nobody paid, the branches nobody picked up again, the open promises and the
   world flags — by one director-class call, gated by structural checks and one critic
   call. Every arc and every thread must name the row of material it grows from; a
   season that invents its premise from nothing is refused.
3. **Named interlude** — when neither is ready, the life does not sit in an interlude
   that never ends. It is told honestly: ``{"since", "returns_on", "reason_fr"}``, with
   ``returns_on`` :data:`INTERLUDE_WAIT_DAYS` days out. On that date the question is asked
   again (the writer, if on), and if there is still nothing the **reprise** season —
   built here, deterministically, with no model call, from the same material — begins.
   The promised date is kept.

Everything returned is a *season file*, in the format of the authored ones, merged over the
current world by ``SerialThreadService.merge_season_world_bible``.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

INTERLUDE_WAIT_DAYS = 14
WRITER_BUDGET_SECONDS = 90
MATERIAL_LIMIT = 12
REPRISE_ARCS = 5
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_]{1,62}$")

MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
ORDINALS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine"}


def _iso(value: Any) -> str | None:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def french_date(value: Any) -> str:
    """``2026-10-13`` → ``13 octobre`` (``1er`` for the first of the month)."""

    iso = _iso(value)
    if not iso:
        return ""
    day = date.fromisoformat(iso)
    number = "1er" if day.day == 1 else str(day.day)
    return f"{number} {MONTHS_FR[day.month - 1]}"


def named_interlude(since: Any, *, days: int = INTERLUDE_WAIT_DAYS) -> dict:
    """The honest between-seasons record: when it began, when the story resumes."""

    start = date.fromisoformat(_iso(since) or date.today().isoformat())
    returns_on = start + timedelta(days=int(days))
    return {
        "since": start.isoformat(),
        "returns_on": returns_on.isoformat(),
        "reason_fr": f"Entre deux saisons : l'histoire reprend le {french_date(returns_on)}.",
    }


def situation_key(number: int) -> str:
    ordinal = ORDINALS.get(int(number))
    return f"season_{ordinal}_situation" if ordinal else "season_situation"


# --- the learner's own material ---------------------------------------------


def season_material(live: dict, world: dict) -> list[dict]:
    """What the next season may grow from: rows of this life, each with a stable id.

    ``kind`` is one of ``plant`` (a detail planted and never paid), ``branch`` (a
    development the learner caused that no later scene picked up), ``commitment`` (a
    promise still open), ``thread`` (a season question, with the state it closed in) and
    ``flag`` (a fact a finished season established).
    """

    rows: list[dict] = []
    for row in live.get("planted") or []:
        if isinstance(row, dict) and row.get("id") and row.get("status") != "paid" and row.get("text_fr"):
            rows.append({"id": str(row["id"]), "kind": "plant", "text_fr": str(row["text_fr"]),
                         "character_id": row.get("character_id")})
    branches = [
        row for row in live.get("consequences") or []
        if isinstance(row, dict) and row.get("kind") == "branch" and row.get("last_referenced") is None
        and row.get("id") and row.get("text_fr")
    ]
    branches.sort(key=lambda row: (-int(row.get("weight") or 1), -int(row.get("day") or 0)))
    for row in branches:
        rows.append({"id": str(row["id"]), "kind": "branch", "text_fr": str(row["text_fr"]),
                     "character_id": row.get("character_id")})
    for row in live.get("commitments") or []:
        if isinstance(row, dict) and row.get("status") == "open" and row.get("id") and row.get("text_fr"):
            rows.append({"id": str(row["id"]), "kind": "commitment", "text_fr": str(row["text_fr"]),
                         "character_id": (row.get("witnesses") or [None])[0]})
    for row in reversed(live.get("threads_archive") or []):
        if isinstance(row, dict) and row.get("key") and row.get("text_fr"):
            rows.append({"id": f"thread:{row['key']}", "kind": "thread", "text_fr": str(row["text_fr"]),
                         "state": row.get("state"), "character_id": None})
    for key, value in sorted((live.get("world_flags") or {}).items()):
        if value not in (None, False, ""):
            rows.append({"id": f"flag:{key}", "kind": "flag", "text_fr": f"{key} = {value}", "character_id": None})
    seen: set[str] = set()
    unique = []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        unique.append(row)
    # A balanced handful: never all flags, never all threads.
    by_kind: dict[str, list[dict]] = {}
    for row in unique:
        by_kind.setdefault(row["kind"], []).append(row)
    picked: list[dict] = []
    while len(picked) < MATERIAL_LIMIT and any(by_kind.values()):
        for kind in ("plant", "branch", "commitment", "thread", "flag"):
            if by_kind.get(kind) and len(picked) < MATERIAL_LIMIT:
                picked.append(by_kind[kind].pop(0))
    return picked


def _cast_ids(world: dict) -> list[str]:
    return [str(member["id"]) for member in world.get("cast") or [] if isinstance(member, dict) and member.get("id")]


# --- the written season (behind the flag) -----------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StageDraft(_Strict):
    id: str = Field(min_length=2, max_length=40)
    summary: str = Field(min_length=10, max_length=300)
    sets: dict[str, str | bool] = Field(default_factory=dict)


class ArcDraft(_Strict):
    id: str = Field(min_length=2, max_length=63)
    title_fr: str = Field(min_length=2, max_length=80)
    characters: list[str] = Field(min_length=1, max_length=4)
    grounded_in: str = Field(min_length=1, max_length=200)
    min_episodes_between_stages: int = Field(default=3, ge=2, le=4)
    stages: list[StageDraft] = Field(min_length=3, max_length=4)


class ThreadDraft(_Strict):
    text: str = Field(min_length=5, max_length=240)
    text_fr: str = Field(min_length=5, max_length=200)
    grounded_in: str = Field(min_length=1, max_length=200)


class SeasonDraft(_Strict):
    title_fr: str = Field(min_length=2, max_length=80)
    logline: str = Field(min_length=10, max_length=400)
    logline_fr: str = Field(min_length=10, max_length=300)
    your_arc: str = Field(min_length=10, max_length=400)
    first_episode_seed: str = Field(min_length=10, max_length=400)
    arcs: list[ArcDraft] = Field(min_length=3, max_length=5)
    open_threads: list[ThreadDraft] = Field(min_length=3, max_length=5)


class SeasonReview(_Strict):
    accepted: bool
    issues: list[str] = Field(default_factory=list)


SEASON_WRITER = """You are Atelier's season director. A learner has lived a whole season (or
several) of a French-learning serial set in Paris. Write the NEXT season's spine — not scenes.

Build it ONLY from `material`: rows of this learner's own life (unpaid plants, branches
nobody picked up again, open promises, the season questions and how they closed, facts a
season established). Every arc and every open thread names the row it grows from in
`grounded_in` (its exact `id`). Invent no backstory that contradicts `cast`; add no new
character; use only cast ids (and "user" for the learner) in `characters`.

3–5 arcs, each 3 stages (spark → pressure → tentpole; the last one is the payoff), each
stage a one-sentence summary in English and `sets` flags named `<character>.<fact>`.
3–5 open threads: the English line the director reads and the short French line the learner
reads (A2 French, one sentence). `title_fr` and `logline_fr` are short, warm, A2 French.
Tone: warm, wry, one real feeling per arc. Return JSON matching the schema."""

SEASON_CRITIC = """Independently check a proposed next season against the learner material it
claims to grow from. Reject (accepted=false) when an arc or thread is not really about the
material row it names, when it contradicts the cast, when the French is above A2 or
unnatural, or when it merely repeats the previous season. List concrete issues."""


class SeasonRejected(ValueError):
    pass


def validate_season(draft: SeasonDraft, *, material: list[dict], cast_ids: list[str]) -> None:
    """The structural gate — deterministic, before the critic ever sees the draft."""

    refs = {row["id"] for row in material}
    allowed = set(cast_ids) | {"user"}
    ids: set[str] = set()
    for arc in draft.arcs:
        if not _SLUG.match(arc.id) or arc.id in ids:
            raise SeasonRejected(f"arc_id:{arc.id}")
        ids.add(arc.id)
        if arc.grounded_in not in refs:
            raise SeasonRejected(f"ungrounded_arc:{arc.id}")
        unknown = [who for who in arc.characters if who not in allowed]
        if unknown:
            raise SeasonRejected(f"unknown_character:{unknown[0]}")
        stage_ids = [stage.id for stage in arc.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise SeasonRejected(f"stage_ids:{arc.id}")
    for thread in draft.open_threads:
        if thread.grounded_in not in refs:
            raise SeasonRejected("ungrounded_thread")


def season_file_from_draft(draft: SeasonDraft, *, number: int, source: str) -> dict:
    """A written season, in the authored season-file format."""

    arcs = []
    for arc in draft.arcs:
        stages = []
        for index, stage in enumerate(arc.stages):
            row: dict[str, Any] = {"id": stage.id, "summary": stage.summary, "sets": dict(stage.sets)}
            if index == len(arc.stages) - 1:
                row["tentpole"] = True
            stages.append(row)
        arcs.append({
            "id": arc.id,
            "title": arc.title_fr,
            "title_fr": arc.title_fr,
            "characters": list(arc.characters),
            "min_episodes_between_stages": int(arc.min_episodes_between_stages),
            "grounded_in": arc.grounded_in,
            "stages": stages,
        })
    return {
        "world_bible_version": f"paris-s{number}-{source}",
        "season_number": number,
        "season_source": source,
        "season_title_fr": draft.title_fr,
        "season_logline": draft.logline,
        "season_logline_fr": draft.logline_fr,
        situation_key(number): {
            "your_arc": draft.your_arc,
            "open_threads": [thread.text for thread in draft.open_threads],
            "open_threads_fr": [thread.text_fr for thread in draft.open_threads],
            "first_episode_seed": draft.first_episode_seed,
        },
        # A written season has no authored private plans; the cast's off-screen week is
        # quiet until an authored season gives them one again.
        "character_agendas": {},
        "season_arcs": arcs,
    }


def draft_next_season(
    *, live: dict, world: dict, next_season: int, db=None, user=None
) -> dict | None:
    """One director-class call and one critic call; ``None`` on any failure.

    Never raises: a season that could not be written is a named interlude, not a lost
    day. Uses the story engine's own provider seam, so the tests' fake provider (and the
    spend records) apply unchanged.
    """

    from app.services import living_story as engine

    material = season_material(live, world)
    if len(material) < 3:
        logger.info("season_writer: too little material for season %s (%s rows)", next_season, len(material))
        return None
    cast = [
        {key: member.get(key) for key in ("id", "name", "role", "wants", "gender")}
        for member in world.get("cast") or []
        if isinstance(member, dict) and member.get("id")
    ]
    previous = [arc.get("id") for arc in world.get("season_arcs") or [] if isinstance(arc, dict)]
    payload = {
        "world": {"logline": world.get("logline"), "cast": cast, "previous_season_arcs": previous},
        "season_number": int(next_season),
        "material": material,
    }
    usage: list[dict] = []
    deadline = time.monotonic() + WRITER_BUDGET_SECONDS
    try:
        draft, _ = engine._json_call(
            SEASON_WRITER, payload, SeasonDraft, usage.append, deadline=deadline,
            max_tokens=6000, reasoning_effort="medium", window=60,
        )
        validate_season(draft, material=material, cast_ids=_cast_ids(world))
        review, _ = engine._json_call(
            SEASON_CRITIC, {"source": payload, "proposal": draft.model_dump(mode="json")},
            SeasonReview, usage.append, deadline=deadline,
        )
        if not review.accepted:
            logger.info("season_writer: critic refused season %s: %s", next_season, review.issues[:3])
            return None
        return season_file_from_draft(draft, number=int(next_season), source="written")
    except (engine.StoryUnavailable, SeasonRejected) as exc:
        logger.info("season_writer: season %s not written (%s)", next_season, exc)
        return None
    except Exception:  # pragma: no cover - a writer never costs the learner a day
        logger.exception("season_writer: season %s failed", next_season)
        return None
    finally:
        if usage and db is not None and user is not None:
            try:
                engine._record_cost(
                    db, user, "story_season_writer_cost", usage,
                    entity_type="living_story_season",
                    payload={"season": int(next_season)},
                )
            except Exception:  # pragma: no cover - bookkeeping never blocks the story
                logger.exception("season_writer: cost row not written")


# --- the reprise season (no model) -------------------------------------------

_REPRISE_STAGES = {
    "plant": (
        "A detail from before comes back: {text}",
        "The detail turns out to matter to someone in the group, and nobody wants to say why.",
        "The group finally opens what that detail was hiding, together.",
    ),
    "branch": (
        "What the learner once set in motion comes back to the table: {text}",
        "Its consequences reach someone who was not there that day.",
        "The group decides together what to do with it — and it is settled out loud.",
    ),
    "commitment": (
        "A promise still stands: {text}",
        "Keeping it costs more than it did when it was made.",
        "The promise is kept, or honestly released, in front of the person it was made to.",
    ),
    "thread": (
        "An old question of the group comes back in a new form: {text}",
        "The answer everyone gave last time no longer fits.",
        "The group answers it again, differently, and means it.",
    ),
    "flag": (
        "Something this life established is tested: {text}",
        "The test becomes personal for one of the group.",
        "What was true is chosen again, on purpose.",
    ),
}
_REPRISE_THREAD_FR = {
    "plant": "Ce détail revient : « {text} »",
    "branch": "Ce que vous avez commencé revient : « {text} »",
    "commitment": "Une promesse attend toujours : « {text} »",
    "thread": "Une vieille question revient : « {text} »",
    "flag": "Une chose sûre est mise à l'épreuve.",
}
# When a life left nothing open at all, the quartier itself is the material.
_REPRISE_QUARTIER = (
    ("quartier_voisins", "Les voisins", "A new neighbour on your landing needs help with the building's rules.",
     "Un nouveau voisin a besoin d'aide sur votre palier."),
    ("quartier_fete", "La fête du canal", "The quartier prepares its summer party and the group volunteers for too much.",
     "La fête du quartier approche, et le groupe a promis trop de choses."),
    ("quartier_souvenirs", "Les photos du Mistral", "Old photos of Le Mistral turn up at the brocante.",
     "De vieilles photos du Mistral apparaissent à la brocante."),
)


def _clip(text: str, limit: int = 110) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def reprise_season(*, live: dict, world: dict, next_season: int, seed: str) -> dict:
    """The season that begins on the promised date when nothing was written.

    Built from the same material, with fixed templates: every arc names its row, the
    French threads quote the learner's own ledgers verbatim, and nothing is invented
    that the life does not already contain. Deterministic per learner and season.
    """

    import hashlib

    number = int(next_season)
    material = [row for row in season_material(live, world) if row["kind"] != "flag"][:REPRISE_ARCS]
    cast = list(_cast_ids(world))
    if not cast:
        cast = ["user"]
    order = sorted(cast, key=lambda cid: hashlib.sha256(f"{seed}:reprise:{number}:{cid}".encode()).hexdigest())
    arcs: list[dict] = []
    english: list[str] = []
    french: list[str] = []
    for index, row in enumerate(material):
        who = row.get("character_id") if row.get("character_id") in cast else order[index % len(order)]
        spark, pressure, payoff = _REPRISE_STAGES[row["kind"]]
        text = _clip(row["text_fr"])
        arc_id = f"s{number}_reprise_{index + 1}"
        arcs.append({
            "id": arc_id,
            "title": f"Reprise {index + 1}",
            "title_fr": f"Les fils repris ({index + 1})",
            "characters": [who, "user"],
            "min_episodes_between_stages": 2,
            "grounded_in": row["id"],
            "stages": [
                {"id": "spark", "summary": spark.format(text=text), "sets": {f"{arc_id}.state": "spark"}},
                {"id": "pressure", "summary": pressure, "sets": {f"{arc_id}.state": "pressure"}},
                {"id": "tentpole", "summary": payoff, "sets": {f"{arc_id}.state": "settled"}, "tentpole": True},
            ],
        })
        english.append(spark.format(text=text))
        french.append(_REPRISE_THREAD_FR[row["kind"]].format(text=text))
    for arc_id, title_fr, summary, line_fr in _REPRISE_QUARTIER:
        if len(arcs) >= 3:
            break
        who = order[len(arcs) % len(order)]
        full_id = f"s{number}_{arc_id}"
        arcs.append({
            "id": full_id,
            "title": title_fr,
            "title_fr": title_fr,
            "characters": [who, "user"],
            "min_episodes_between_stages": 2,
            "grounded_in": "quartier",
            "stages": [
                {"id": "spark", "summary": summary, "sets": {f"{full_id}.state": "spark"}},
                {"id": "pressure", "summary": "It asks more of the group than anyone planned.",
                 "sets": {f"{full_id}.state": "pressure"}},
                {"id": "tentpole", "summary": "The group sees it through together, with the learner's French at the centre.",
                 "sets": {f"{full_id}.state": "settled"}, "tentpole": True},
            ],
        })
        english.append(summary)
        french.append(line_fr)
    return {
        "world_bible_version": f"paris-s{number}-reprise",
        "season_number": number,
        "season_source": "reprise",
        "season_title_fr": "Les fils repris",
        "season_logline": "The story resumes from what this learner's life left open.",
        "season_logline_fr": "L'histoire reprend là où votre vie au quartier l'avait laissée.",
        situation_key(number): {
            "your_arc": "Pick up what was left open, with the people who were there.",
            "open_threads": english,
            "open_threads_fr": french,
            "first_episode_seed": "The group is back at Le Mistral after a few quiet weeks; something from before is waiting on the table.",
        },
        "character_agendas": {},
        "season_arcs": arcs,
    }
