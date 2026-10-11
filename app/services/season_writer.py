"""WP-98 «La saison suivante» — the story never runs out.

Three ways a finished season is followed, in this order (``living_story.roll_over_season``):

1. **Authored** — a season file exists (``serial.AUTHORED_SEASON_PATHS``: seasons 2 and 3).
2. **Written** — behind ``ATELIER_SEASON_WRITER_ENABLED`` (default on since WP-168: it only
   runs once a season has ended), season N+1's arcs are drafted from THIS learner's own
   material — the archived season questions, the plants nobody paid, the branches nobody
   picked up again, the open promises and the world flags — by one director-class call,
   gated by structural checks and one critic call. Every arc and every thread must name
   the row of material it grows from; a season that invents its premise from nothing is
   refused.

   WP-168 «the writer may move the story» (``ATELIER_SEASON_WRITER_MAY_MOVE``, owner
   decision of 11 October): the season may change city, genre and the learner's
   situation, anywhere French is spoken, with new places (painted lazily, a stand-in
   until then: ``season.written_world``) and new characters (drawn from rig parameters)
   beside the cast members who travel. The move itself must name the material row that
   pulls the learner there, and the critic judges both «grows from the material» and «is
   it a fresh story». Canon guards stay: the departed cast never travels on stage, the
   finished season's own rules and closed places hold.
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

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.season.written_world import (
    PLACE_KINDS,
    RIG_DEFAULTS,
    RIG_VOCABULARY,
    normalise_rig,
)

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


def _enum(key: str, description: str) -> Any:
    return Field(
        default=RIG_DEFAULTS[key],
        description=description,
        json_schema_extra={"enum": list(RIG_VOCABULARY[key])},
    )


class RigDraft(_Strict):
    """How a new character is drawn: the drawn set builds the figure from these. A value
    outside the vocabulary is the default, never an error."""

    build: str = _enum("build", "body width")
    height: str = _enum("height", "height")
    head: str = _enum("head", "face shape")
    skin: str = _enum("skin", "skin tone, lightest to deepest")
    hair: str = _enum("hair", "hairstyle")
    hair_colour: str = _enum("hair_colour", "hair colour")
    facial_hair: str = _enum("facial_hair", "facial hair")
    glasses: str = _enum("glasses", "glasses")
    top: str = _enum("top", "what they wear on top")
    top_colour: str = _enum("top_colour", "its colour")
    bottom_colour: str = _enum("bottom_colour", "trousers or skirt colour")
    accessory: str = _enum("accessory", "one accessory")
    accessory_colour: str = _enum("accessory_colour", "its colour")
    idle: str = _enum("idle", "how they move when still: bob, bounce, sway or nod")

    @model_validator(mode="before")
    @classmethod
    def _closed_vocabulary(cls, value: Any) -> Any:
        return normalise_rig(value)


class PlaceDraft(_Strict):
    id: str = Field(min_length=2, max_length=63, description="snake_case French slug that starts with the kind of place: quai_…, gare_…, cafe_…, marche_…, appartement_…")
    name_fr: str = Field(min_length=2, max_length=80)
    kind: str = Field(
        min_length=2,
        max_length=20,
        json_schema_extra={"enum": sorted(PLACE_KINDS)},
    )
    description: str = Field(min_length=10, max_length=300, description="English, for the director: what it is and what happens there")
    brief: str = Field(
        min_length=30,
        max_length=420,
        description="English plate brief for the painter: the place, three concrete landmarks, the light. No people, no readable text.",
    )


class NewCharacterDraft(_Strict):
    id: str = Field(min_length=2, max_length=63, description="snake_case slug of their name, e.g. awa_ndiaye")
    name: str = Field(min_length=2, max_length=60)
    gender: str = Field(default="x", max_length=2, description="f, m or x")
    role: str = Field(min_length=5, max_length=240)
    personality: str = Field(min_length=5, max_length=240)
    wants: str = Field(min_length=5, max_length=200)
    speech_pattern: str = Field(min_length=5, max_length=200)
    register_with_user: str = Field(default="vous", max_length=4, description="tu or vous")
    grounded_in: str = Field(default="", max_length=200, description="the material row or cast id they are tied to")
    rig: RigDraft = Field(default_factory=RigDraft)


class SettingDraft(_Strict):
    city: str = Field(min_length=2, max_length=80)
    region: str = Field(default="", max_length=120, description="region and country")
    neighborhood: str = Field(default="", max_length=200)
    genre: str = Field(min_length=3, max_length=80)
    tone: str = Field(default="", max_length=200)
    situation: str = Field(min_length=10, max_length=300, description="the learner's situation this season, English")
    situation_fr: str = Field(min_length=5, max_length=200, description="the same, one A2 French sentence")
    why: str = Field(min_length=10, max_length=300, description="how the material row pulls the learner into this setting")
    grounded_in: str = Field(min_length=1, max_length=200)
    travelling_cast: list[str] = Field(default_factory=list, max_length=6)
    keep_locations: list[str] = Field(default_factory=list, max_length=8)


class SeasonDraft(_Strict):
    title_fr: str = Field(min_length=2, max_length=80)
    logline: str = Field(min_length=10, max_length=400)
    logline_fr: str = Field(min_length=10, max_length=300)
    your_arc: str = Field(min_length=10, max_length=400)
    first_episode_seed: str = Field(min_length=10, max_length=400)
    arcs: list[ArcDraft] = Field(min_length=3, max_length=5)
    open_threads: list[ThreadDraft] = Field(min_length=3, max_length=5)
    # WP-168: only read under ATELIER_SEASON_WRITER_MAY_MOVE.
    setting: SettingDraft | None = None
    places: list[PlaceDraft] = Field(default_factory=list, max_length=6)
    new_characters: list[NewCharacterDraft] = Field(default_factory=list, max_length=3)


class SeasonReview(_Strict):
    accepted: bool
    # WP-168: the critic's two judgements of a season that may move. Absent (an older
    # critic) they do not refuse; ``False`` does.
    grows_from_material: bool | None = None
    fresh: bool | None = None
    issues: list[str] = Field(default_factory=list)

    @property
    def passes(self) -> bool:
        return bool(self.accepted) and self.grows_from_material is not False and self.fresh is not False


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


SEASON_WRITER_MOVING = """You are Atelier's season director. A learner has lived a whole season (or
several) of a French-learning serial. Write the NEXT season's spine — not scenes.

This season MAY MOVE. You may change the city, the genre and the learner's situation,
anywhere French is spoken: Marseille, Brussels, Montréal, Dakar, a ferry to Corsica, a
vineyard in Burgundy, a radio station in Abidjan, a lighthouse in Brittany — invent, there
is no list. You may also stay and change only the genre or the situation. Prefer the bold,
specific, surprising choice that THIS learner's material makes inevitable over the safe one.

What may not change: the season grows from `material`, the rows of this learner's own life
(unpaid plants, branches nobody picked up again, open promises, the season questions and
how they closed, facts a season established).
- Every arc and every open thread names, in `grounded_in`, the exact `id` of its row.
- A move is motivated: `setting.grounded_in` names the row that pulls the learner there and
  `setting.why` says how (a thread that leads elsewhere, a promise to keep in another city,
  someone to find, a job the story gave them). A move nothing in the material asks for is
  refused. Always give `setting`, with `city` even when you stay.
- `canon` holds: a `departed` cast member is never in `characters` or `travelling_cast`
  (they may write, call, be remembered); `canon.rules` and `canon.facts` stay true; a
  `closed_locations` place is never kept.

Who comes along: `setting.travelling_cast` lists the cast ids physically there this season,
each with a reason in an arc; everyone else stays where they were and reaches the learner
from afar. Add 1–3 `new_characters` who live in the new setting, each tied in `grounded_in`
to a material row or a cast id, each with a `rig` (how they are drawn: choose from the
enums, make them distinct from each other and from the cast). Their ids are slugs of their
names; never reuse any word of a cast member's name.

Places: 3–6 `places` where this season's scenes happen (when you stay, fewer new ones plus
`keep_locations`). Each: a French slug id that starts with its kind word, a French name, a
`kind`, an English `description` for the director, and an English `brief` for the painter
(the place, three concrete landmarks, the light; no people, no readable text).

3–5 arcs, each 3 stages (spark → pressure → tentpole; the last one is the payoff), each
stage a one-sentence summary in English and `sets` flags named `<character>.<fact>`;
`characters` are cast ids, new character ids, and "user" for the learner.
3–5 open threads: the English line the director reads and the short French line the learner
reads (A2 French, one sentence). `title_fr` and `logline_fr` are short, warm, A2 French;
`logline` (English) tells the director where the story is now and what this season is
about. One real feeling per arc. Return JSON matching the schema."""

SEASON_CRITIC_MOVING = """Independently judge a proposed next season of a French-learning serial
against the learner material it claims to grow from (`source.material`) and against the
season the learner already lived (`source.world`). Set two booleans and the verdict.

grows_from_material: true only when every arc, every thread AND the setting itself grow
from the material row each one names. A move must be motivated by its row: the learner is
pulled there by a thread, a promise, a person, a consequence of their own choices. A season
that could have been written for any learner, or a move nothing in the material asks for,
is false.
fresh: true only when it is a new story and not the previous season again: a new central
question, new places or a real change of genre or situation, new people to meet, the
travelling cast with new goals. The previous premise re-run in new clothes is false.

accepted: grows_from_material and fresh, no canon contradiction (a departed cast member on
stage, a closed place kept, a canon fact contradicted), and natural A2 learner-facing
French. A move to another city or a change of genre is welcome, never a problem in itself.
List concrete issues."""


class SeasonRejected(ValueError):
    pass


def season_canon(live: dict) -> dict:
    """What a written season may not undo: the cast the finished season sent away (never
    on stage), its rules and facts, and the places its ending closed. Empty for a life
    that never played a scripted season."""

    empty: dict[str, Any] = {"departed": [], "rules": [], "facts": [], "closed_locations": []}
    state = (live or {}).get("season_script")
    if not isinstance(state, dict) or not state.get("id"):
        return empty
    try:
        from app.services.season import epilogue as ep
        from app.services.season.flags import effective_flags
        from app.services.season.format import load_season

        season = load_season(str(state["id"]))
        flags = effective_flags(season, state)
        carried = ep.carried(season, state, flags, band="A2", language="en")
    except Exception:  # noqa: BLE001 - no canon read is an empty canon, never a lost season
        logger.exception("season_writer: canon of %s unreadable", state.get("id"))
        return empty
    return {
        "departed": [
            {key: row.get(key) for key in ("id", "name", "why")} for row in carried.get("departed") or []
        ],
        # The continuation's rules that bind a later season too: the cast knows the
        # learner, and «L.» is looked for, never revealed. (The others are about days
        # inside the finished season's world, which a new season may leave.)
        "rules": [rule for rule in ep.CONTINUATION_RULES if "stranger" in rule or "L." in rule],
        "facts": list(carried.get("facts") or []),
        "closed_locations": list(carried.get("closed_locations") or []),
    }


#: Words a name may share with the cast without being theirs.
_NAME_COMMON = frozenset({"mme", "madame", "monsieur", "maitre", "the", "and", "les", "des"})
#: Names the reader already maps onto the fixed cast (``lib/cast-faces``), besides the cast's own.
_NAME_ALIASES = frozenset(
    {"romane", "gus", "odile", "ferrand", "toi", "you", "user", "learner", "landlord", "proprietaire"}
)


def _cast_name_words(world: dict) -> set[str]:
    """Every word of a cast member's id or name: a new face carrying one would be read
    as theirs by the reader (their face, their voice), so it may not."""

    from app.services.season.written_world import _tokens

    words: set[str] = set(_NAME_ALIASES)
    for member in world.get("cast") or []:
        if isinstance(member, dict):
            words.update(_tokens(member.get("name")))
            words.update(_tokens(member.get("id")))
    return {word for word in words if len(word) > 2 and word not in _NAME_COMMON}


def _place_ids(world: dict) -> set[str]:
    setting = world.get("setting") or {}
    return {
        str(place.get("id"))
        for place in (setting.get("recurring_locations") if isinstance(setting, dict) else None) or []
        if isinstance(place, dict) and place.get("id")
    }


def validate_season(
    draft: SeasonDraft,
    *,
    material: list[dict],
    cast_ids: list[str],
    may_move: bool = False,
    world: dict | None = None,
    canon: dict | None = None,
) -> None:
    """The structural gate — deterministic, before the critic ever sees the draft.

    WP-168, under ``may_move``: the setting names its material row; nobody departed
    travels; kept places exist and are not closed; new places and new characters have
    fresh slugs (a new face shares no word with a cast member's name, so it never gets
    their face or their voice in the reader); a change of city brings at least two new
    places and three in all.
    """

    from app.services.season.written_world import same_city, valid_slug

    world = world or {}
    canon = canon or {}
    refs = {row["id"] for row in material}
    departed = {str(row.get("id")) for row in canon.get("departed") or [] if row.get("id")}
    new_ids: set[str] = set()
    if may_move:
        from app.services.season.written_world import _tokens

        reserved = set(cast_ids) | {"user"}
        taken = _cast_name_words(world)
        for character in draft.new_characters:
            if not valid_slug(character.id) or character.id in reserved or character.id in new_ids:
                raise SeasonRejected(f"new_character_id:{character.id}")
            if set(_tokens(character.id)) & taken:
                raise SeasonRejected(f"new_character_id:{character.id}")
            if set(_tokens(character.name)) & taken:
                raise SeasonRejected(f"name_taken:{character.name}")
            new_ids.add(character.id)
        places = _place_ids(world)
        closed = set(canon.get("closed_locations") or [])
        setting = draft.setting
        moved = False
        if setting is not None:
            if setting.grounded_in not in refs:
                raise SeasonRejected("ungrounded_setting")
            for who in setting.travelling_cast:
                if who in departed:
                    raise SeasonRejected(f"departed_travels:{who}")
                if who not in cast_ids:
                    raise SeasonRejected(f"unknown_traveller:{who}")
            for place_id in setting.keep_locations:
                if place_id not in places:
                    raise SeasonRejected(f"unknown_place:{place_id}")
                if place_id in closed:
                    raise SeasonRejected(f"closed_place:{place_id}")
            current = (world.get("setting") or {}).get("city") if isinstance(world.get("setting"), dict) else None
            moved = bool(current) and not same_city(setting.city, current)
        seen: set[str] = set()
        for place in draft.places:
            if not valid_slug(place.id) or place.id in places or place.id in seen:
                raise SeasonRejected(f"place_id:{place.id}")
            seen.add(place.id)
        if moved and (len(seen) < 2 or len(seen) + len(setting.keep_locations) < 3):
            raise SeasonRejected("too_few_places")
    allowed = set(cast_ids) | {"user"} | new_ids
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
        gone = [who for who in arc.characters if who in departed]
        if gone:
            raise SeasonRejected(f"departed_character:{gone[0]}")
        stage_ids = [stage.id for stage in arc.stages]
        if len(set(stage_ids)) != len(stage_ids):
            raise SeasonRejected(f"stage_ids:{arc.id}")
    for thread in draft.open_threads:
        if thread.grounded_in not in refs:
            raise SeasonRejected("ungrounded_thread")


def _setting_move(draft: SeasonDraft, *, number: int, world: dict) -> dict | None:
    """The ``setting_move`` directive ``merge_season_world_bible`` applies (WP-168)."""

    from app.services.season.written_world import place_kind, plate_id_for, stand_in_location

    if draft.setting is None and not draft.places:
        return None
    setting = draft.setting
    current = world.get("setting") if isinstance(world.get("setting"), dict) else {}
    places = []
    for place in draft.places:
        kind = place_kind(place.kind, place.id, place.name_fr)
        row = {
            "id": place.id,
            "name": place.name_fr,
            "name_fr": place.name_fr,
            "type": kind,
            "description": place.description,
            "brief": " ".join(place.brief.split()),
            "plate_id": plate_id_for(place.id, place.brief),
            "written_season": int(number),
        }
        row["stand_in"] = stand_in_location(row)
        places.append(row)
    move: dict[str, Any] = {"city": setting.city if setting else current.get("city"), "places": places}
    if setting is not None:
        move.update(
            {
                "region": setting.region,
                "neighborhood": setting.neighborhood,
                "genre": setting.genre,
                "tone": setting.tone,
                "situation": setting.situation,
                "situation_fr": setting.situation_fr,
                "why": setting.why,
                "grounded_in": setting.grounded_in,
                "travelling_cast": list(setting.travelling_cast),
                "keep_locations": list(setting.keep_locations),
            }
        )
    return move


def _new_character(character: NewCharacterDraft, *, number: int) -> dict:
    gender = character.gender.strip().lower()[:1]
    return {
        "id": character.id,
        "name": character.name,
        "gender": gender if gender in {"f", "m", "x"} else "x",
        "role": character.role,
        "personality": character.personality,
        "wants": character.wants,
        "speech_pattern": character.speech_pattern,
        "register_with_user": "tu" if character.register_with_user.strip().lower() == "tu" else "vous",
        "grounded_in": character.grounded_in,
        "rig": normalise_rig(character.rig.model_dump()),
        "written_season": int(number),
    }


def season_file_from_draft(
    draft: SeasonDraft,
    *,
    number: int,
    source: str,
    may_move: bool = False,
    world: dict | None = None,
) -> dict:
    """A written season, in the authored season-file format.

    WP-168, under ``may_move``: plus the ``setting_move`` directive (city, genre, the
    learner's situation, the new places with their plate briefs, who travels), the new
    faces as ``cast_additions`` with their rig parameters, and the director's own
    ``logline`` for the world the story is in now.
    """

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
    world = world or {}
    written: dict[str, Any] = {
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
    if may_move:
        move = _setting_move(draft, number=int(number), world=world)
        if move:
            written["setting_move"] = move
            city = re.sub(r"[^a-z0-9]+", "-", str(move.get("city") or "").lower()).strip("-")
            if city:
                written["world_bible_version"] = f"{city}-s{number}-{source}"
        if draft.setting is not None:
            # The director reads ``world.logline``: after a move it is this season's.
            written["logline"] = draft.logline
            written["season_setting"] = {
                "city": draft.setting.city,
                "region": draft.setting.region,
                "genre": draft.setting.genre,
                "situation_fr": draft.setting.situation_fr,
            }
        if draft.new_characters:
            written["cast_additions"] = [_new_character(row, number=int(number)) for row in draft.new_characters]
    return written


def _writer_payload(world: dict, *, next_season: int, material: list[dict], may_move: bool, canon: dict) -> dict:
    keys = ("id", "name", "role", "wants", "gender") + (("away",) if may_move else ())
    cast = [
        {key: member.get(key) for key in keys if member.get(key) is not None}
        for member in world.get("cast") or []
        if isinstance(member, dict) and member.get("id")
    ]
    previous = [arc.get("id") for arc in world.get("season_arcs") or [] if isinstance(arc, dict)]
    payload: dict[str, Any] = {
        "world": {"logline": world.get("logline"), "cast": cast, "previous_season_arcs": previous},
        "season_number": int(next_season),
        "material": material,
    }
    if may_move:
        setting = world.get("setting") if isinstance(world.get("setting"), dict) else {}
        payload["world"]["setting"] = {
            key: setting.get(key) for key in ("city", "neighborhood", "genre", "tone") if setting.get(key)
        }
        payload["world"]["places"] = [
            {"id": place.get("id"), "name_fr": place.get("name_fr") or place.get("name")}
            for place in setting.get("recurring_locations") or []
            if isinstance(place, dict) and place.get("id")
        ]
        payload["world"]["previous_season_title_fr"] = world.get("season_title_fr")
        payload["canon"] = canon
        payload["may_move"] = True
    return payload


def draft_next_season(
    *, live: dict, world: dict, next_season: int, db=None, user=None, record: dict | None = None
) -> dict | None:
    """One director-class call and one critic call; ``None`` on any failure.

    Never raises: a season that could not be written is a named interlude, not a lost
    day. Uses the story engine's own provider seam, so the tests' fake provider (and the
    spend records) apply unchanged. ``record``, when given, receives the draft, the
    critic's verdict, the refusal and the usage (the WP-168 dry run reads it).
    """

    from app.config import settings
    from app.services import living_story as engine

    record = record if record is not None else {}
    material = season_material(live, world)
    record["material"] = material
    if len(material) < 3:
        logger.info("season_writer: too little material for season %s (%s rows)", next_season, len(material))
        record["refused"] = "too_little_material"
        return None
    may_move = bool(getattr(settings, "ATELIER_SEASON_WRITER_MAY_MOVE", False))
    canon = season_canon(live)
    payload = _writer_payload(world, next_season=next_season, material=material, may_move=may_move, canon=canon)
    record["may_move"] = may_move
    record["canon"] = canon
    usage: list[dict] = []
    record["usage"] = usage
    deadline = time.monotonic() + WRITER_BUDGET_SECONDS
    try:
        draft, _ = engine._json_call(
            SEASON_WRITER_MOVING if may_move else SEASON_WRITER,
            payload,
            SeasonDraft,
            usage.append,
            deadline=deadline,
            max_tokens=12000 if may_move else 6000,
            reasoning_effort="medium",
            window=80 if may_move else 60,
        )
        record["draft"] = draft.model_dump(mode="json")
        validate_season(
            draft, material=material, cast_ids=_cast_ids(world), may_move=may_move, world=world, canon=canon
        )
        review, _ = engine._json_call(
            SEASON_CRITIC_MOVING if may_move else SEASON_CRITIC,
            {"source": payload, "proposal": draft.model_dump(mode="json")},
            SeasonReview,
            usage.append,
            deadline=deadline,
            max_tokens=4000 if may_move else None,
        )
        record["review"] = review.model_dump(mode="json")
        if not review.passes:
            logger.info("season_writer: critic refused season %s: %s", next_season, review.issues[:3])
            record["refused"] = "critic"
            return None
        return season_file_from_draft(
            draft, number=int(next_season), source="written", may_move=may_move, world=world
        )
    except (engine.StoryUnavailable, SeasonRejected) as exc:
        logger.info("season_writer: season %s not written (%s)", next_season, exc)
        record["refused"] = str(exc)
        if getattr(exc, "details", None):
            record["details"] = exc.details
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
