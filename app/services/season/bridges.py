"""WP-124b «Le pont»: a short authored page that supplies a gap's indispensable moments.

When generated days keep failing (``season.recovery``), the season moves on to the
next tentpole — but a tentpole is only served once what it depends on has
happened. Each gap marks those moments as ``required`` in ``gaps.json`` (Romy's
interview, the usual order and the ticket in gap 1; Lila's dinner, the roof and
the argument in gaps 2–4). A **bridge** stages exactly the moments still missing,
in a page of the tentpole format (panels, the learner's turns, a «Le choix», a
hook), played without any model, and then the gap is over.

The bridges are new story text, so they live in their own file,
``app/data/season/<id>/bridges.json`` (with their level variants in a
``levels*.json`` shard and their plain tasks in ``tasks.json``), and they are an
owner-approved deviation from the bible (``scripts/season_check.py`` records it).
**Without that file the code is safe**: :func:`load_bridges` returns ``{}`` and the
recovery keeps the WP-124a reprise for a gap whose moments are missing.

What a bridge may do, enforced by :func:`validate_bridges` (at load and in
``season_check``):

* stage only the gap's own ``required`` moments, one block per moment, and a gate
  moment through a turn carrying that gate with a romance, a friendship and a
  neutral reply — what the learner *expresses* records the signal, as on any day;
* set only the flags the gap may set; a flag the learner decides (the usual order)
  is set by the learner's reply or card, never by the page. A ``fixed`` fact is
  allowed only when it quotes the gap's own ``establish`` line (the ticket moved to
  2 December), the same fact every life reaches;
* make none of the gap's forbidden reveals (``must_not``), at any level.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.season.format import (
    LANGUAGES,
    SEASON_ROOT,
    Hook,
    LexiconEntry,
    Panel,
    Season,
    Solve,
    Turn,
    cond_flags,
    iter_movements,
    load_season,
)

logger = logging.getLogger(__name__)

BRIDGES_FILE = "bridges.json"
#: ``file_id`` of the bridges in the level and task overlays (``tasks.json`` keys
#: ``bridges:<turn id>``; ``season_levels.py --file bridges``).
BRIDGES_FILE_ID = "bridges"

BridgeMovement = Annotated[Panel | Turn | Solve, Field(discriminator="kind")]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FixedFact(_Model):
    """A flag a moment sets whatever the learner says — only a fact the gap
    establishes for everybody (``because`` quotes the gap's ``establish`` line)."""

    flag: str = Field(min_length=1)
    value: Any
    because: str = Field(min_length=1)


class BridgeMoment(_Model):
    """One required moment of a gap, staged in a few panels and one learner turn."""

    premise: str = Field(min_length=1)
    movements: list[BridgeMovement] = Field(min_length=1)
    #: Set when the moment is played (the ticket moved): never a learner's choice.
    fixed: list[FixedFact] = Field(default_factory=list)


class Bridge(_Model):
    gap: str = Field(pattern=r"^g[1-9]$")
    title_fr: str = Field(min_length=1, max_length=100)
    story_date_fr: str = Field(min_length=1)
    location_id: str = Field(min_length=1)
    minutes: int = Field(default=5, ge=1, le=30)
    can_do: dict[str, str] = Field(default_factory=dict)
    lexicon: list[LexiconEntry] = Field(default_factory=list)
    moments: list[BridgeMoment] = Field(min_length=1)
    hook: Hook


class BridgesFile(_Model):
    #: The owner decision this new text stands on (season_check's deviation record).
    deviation: dict[str, str] = Field(default_factory=dict)
    about: str = Field(default="", alias="_about")
    bridges: list[Bridge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def read_bridges_file(season_id: str, *, root: Path | None = None) -> BridgesFile | None:
    """The bridges file with its level variants and plain tasks folded in, or
    ``None`` when the season has none. Raises on a file that does not parse."""

    from app.services.season.levels import apply_levels, apply_tasks, read_levels, read_tasks

    folder = (root or SEASON_ROOT) / season_id
    path = folder / BRIDGES_FILE
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw = apply_tasks(apply_levels(raw, read_levels(folder), file_id=BRIDGES_FILE_ID), read_tasks(folder), file_id=BRIDGES_FILE_ID)
    return BridgesFile.model_validate(raw)


@lru_cache(maxsize=4)
def load_bridges(season_id: str, *, root: Path | None = None) -> dict[str, Bridge]:
    """``{gap id: Bridge}`` — validated; ``{}`` when there is no file or it does not
    hold (logged): the recovery then keeps the reprise, never a blind jump."""

    try:
        parsed = read_bridges_file(season_id, root=root)
        if parsed is None:
            return {}
        season = load_season(season_id, root=root) if root is not None else load_season(season_id)
    except Exception:  # noqa: BLE001 - a broken bridges file costs the bridge, never the day
        logger.exception("season bridges: %s could not be read", season_id)
        return {}
    problems = validate_bridges(season, parsed.bridges)
    if problems:
        logger.error("season bridges: %s does not hold: %s", season_id, "; ".join(problems[:8]))
        return {}
    return {bridge.gap: bridge for bridge in parsed.bridges}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _turns_and_solves(moment: BridgeMoment) -> list[Turn | Solve]:
    return [row for row in moment.movements if isinstance(row, Turn | Solve)]


def _all_text(node: Any) -> list[str]:
    """Every French wording in a bridge (every level), for the forbidden-reveal guard."""

    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"a1", "a2", "b1", "b2", "c1"} and isinstance(value, str):
                out.append(value)
            elif key == "examples" and isinstance(value, list):
                out.extend(str(item) for item in value)
            elif key not in {"native", "native_a1", "visual", "note", "means", "listens_for", "task", "task_plain"}:
                out.extend(_all_text(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_all_text(value))
    return out


def validate_bridges(season: Season, bridges: list[Bridge], *, locations: set[str] | None = None) -> list[str]:
    """Every rule a bridge must keep (see the module docstring). Empty means it holds."""

    from app.services.season.director import forbidden_hits

    problems: list[str] = []
    known_flags = {row.id for row in season.flags}
    speakers = season.speaker_ids()
    seen_gaps: set[str] = set()
    for bridge in bridges:
        where = f"bridge {bridge.gap}"
        gap = season.gaps.get(bridge.gap)
        if gap is None:
            problems.append(f"{where}: no such gap")
            continue
        if bridge.gap in seen_gaps:
            problems.append(f"{where}: two bridges for one gap")
        seen_gaps.add(bridge.gap)
        required = {need.premise for need in gap.required}
        premises = {premise.id: premise for premise in gap.premises}
        if locations is not None and bridge.location_id not in locations:
            problems.append(f"{where}: unknown location {bridge.location_id!r}")
        staged = [moment.premise for moment in bridge.moments]
        if len(set(staged)) != len(staged):
            problems.append(f"{where}: a moment is staged twice")
        missing = required - set(staged)
        if missing:
            problems.append(f"{where}: does not stage required {sorted(missing)}")
        allowed = set(gap.sets_allowed)
        for moment in bridge.moments:
            here = f"{where}/{moment.premise}"
            if moment.premise not in required:
                problems.append(f"{here}: not a required moment of {gap.id} (a bridge stages only those)")
                continue
            premise = premises[moment.premise]
            for fact in moment.fixed:
                if fact.flag not in allowed or fact.flag not in premise.sets:
                    problems.append(f"{here}: fixed fact {fact.flag} is not a flag this moment may set")
                if fact.because not in gap.establish:
                    problems.append(f"{here}: fixed fact {fact.flag} does not quote the gap's establish line")
            asked = _turns_and_solves(moment)
            if not asked:
                problems.append(f"{here}: no turn — a moment is played, not narrated")
            # A moment sets only what its premise lists (and the gap may set).
            may_set = allowed & set(premise.sets)
            for item in iter_movements(list(moment.movements)):
                conds = [getattr(item, "when", {}) or {}]
                if isinstance(item, Turn):
                    if item.to not in speakers:
                        problems.append(f"{here}: turn {item.id} addressed to unknown {item.to!r}")
                    if item.sets or item.sets_if:
                        # Whatever-is-said sets would decide for the learner.
                        problems.append(f"{here}: turn {item.id} sets flags whatever is said (fabricated choice)")
                    for lang in LANGUAGES:
                        if not item.task.get(lang):
                            problems.append(f"{here}: turn {item.id} has no task in {lang}")
                    for reply in item.replies:
                        conds.append(reply.when)
                        bad = set(reply.sets) | {k for row in reply.sets_if for k in row.sets}
                        if bad - may_set:
                            problems.append(f"{here}: reply {item.id}/{reply.id} sets {sorted(bad - may_set)}, not the moment's own flags")
                        if bad - known_flags:
                            problems.append(f"{here}: reply {item.id}/{reply.id} sets unknown {sorted(bad - known_flags)}")
                if isinstance(item, Solve):
                    if item.mechanic != "choix":
                        problems.append(f"{here}: solve {item.id} is {item.mechanic}; a bridge poses only «Le choix»")
                    if item.default:
                        problems.append(f"{here}: solve {item.id} has a default (the learner chooses, the page never does)")
                    for option in [*item.options, *(item.options_b1 or [])]:
                        conds.append(option.when)
                        bad = set(option.sets) | {k for row in option.sets_if for k in row.sets}
                        if bad - may_set:
                            problems.append(f"{here}: option {item.id}/{option.id} sets {sorted(bad - may_set)}, not the moment's own flags")
                    for lang in LANGUAGES:
                        if not item.task.get(lang):
                            problems.append(f"{here}: solve {item.id} has no task in {lang}")
                if isinstance(item, Panel):
                    for line in item.lines:
                        conds.append(line.when)
                        if line.who not in speakers:
                            problems.append(f"{here}: panel {item.id} speaker {line.who!r} is not in the season cast")
                    if locations is not None and item.location_id and item.location_id not in locations:
                        problems.append(f"{here}: panel {item.id} at unknown location {item.location_id!r}")
                for cond in conds:
                    unknown = cond_flags(cond or {}) - known_flags
                    if unknown:
                        problems.append(f"{here}: unknown flags in when: {sorted(unknown)}")
            if premise.gate:
                gates = [row for row in asked if isinstance(row, Turn) and row.gate == premise.gate]
                if not gates:
                    problems.append(f"{here}: gate {premise.gate} moment has no turn carrying the gate")
                for turn in gates:
                    paths = {reply.path for reply in turn.replies}
                    if not {"romance", "friendship", None} <= paths:
                        problems.append(f"{here}: gate turn {turn.id} needs a romance, a friendship and a neutral reply")
                    fallback = next((reply for reply in turn.replies if reply.id == turn.fallback), None)
                    if fallback is not None and fallback.path is not None:
                        problems.append(f"{here}: gate turn {turn.id}'s fallback leans {fallback.path} (never assume what was meant)")
            elif any(isinstance(row, Turn) and row.gate for row in asked):
                problems.append(f"{here}: a turn carries a gate the moment does not hold")
        # The gap's forbidden reveals, deterministically, at every written level (the
        # ``unless`` escapes are read against no flags: a bridge holds for every life).
        texts = _all_text(json.loads(bridge.model_dump_json()))
        hits = forbidden_hits(season, gap.id, texts, flags={})
        for key, text in hits:
            problems.append(f"{where}: forbidden reveal {key} («{text}»)")
        if not re.search(r"suivre", " ".join(_all_text(json.loads(bridge.hook.model_dump_json())))):
            problems.append(f"{where}: the hook does not end on «À suivre…»")
    return problems


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------


def moments_for(bridge: Bridge, missing: list[str]) -> list[BridgeMoment]:
    """The bridge's blocks for the moments still owed, in the gap's own order."""

    wanted = set(missing)
    return [moment for moment in bridge.moments if moment.premise in wanted]


def bridge_page(
    season: Season,
    bridge: Bridge,
    missing: list[str],
    *,
    flags: dict[str, Any],
    band: str,
    language: str,
) -> dict[str, Any] | None:
    """The bridge as a resolved page (the shape of ``page.resolve_day``): the
    missing moments' blocks in order, then the hook. ``None`` when nothing is owed."""

    from app.services.season.page import _Ctx, _movement

    blocks = moments_for(bridge, missing)
    if not blocks:
        return None
    names = {member.id: member.name for member in season.cast}
    ctx = _Ctx(flags=flags, band=band, language=language, neutral=False, names=names)
    # ``_movement`` reads a tentpole only for its shared blocks; a bridge has none.
    holder = SimpleNamespace(shared={})
    movements: list[dict[str, Any]] = []
    staged: list[dict[str, Any]] = []
    for moment in blocks:
        asked: list[str] = []
        for movement in moment.movements:
            for row in _movement(movement, holder, ctx):
                if row.get("kind") in ("turn", "solve"):
                    # The moment's own question: always reached (``runtime.routes_the_story``),
                    # and the moment counts as staged only once it is answered.
                    row["moment"] = moment.premise
                    asked.append(str(row.get("id")))
                movements.append(row)
        staged.append(
            {
                "premise": moment.premise,
                "turns": asked,
                "fixed": {fact.flag: fact.value for fact in moment.fixed},
            }
        )
    movements.extend(_movement(bridge.hook, holder, ctx))
    gap = season.gaps[bridge.gap]
    return {
        "season_id": season.id,
        "tentpole": None,
        "bridge": bridge.gap,
        "moments": staged,
        "number": gap.number,
        "tentpole_title_fr": bridge.title_fr,
        "day": None,
        "variant": "bridge:" + "+".join(moment.premise for moment in blocks),
        "title_fr": bridge.title_fr,
        "story_date_fr": bridge.story_date_fr,
        "holiday": None,
        "location_id": bridge.location_id,
        "minutes": bridge.minutes,
        "band": band,
        "language": language,
        "previously": [],
        "movements": movements,
        "lexicon": [row.model_dump() for row in bridge.lexicon],
        "can_do_native": bridge.can_do.get(language) or bridge.can_do.get("en"),
    }


__all__ = [
    "BRIDGES_FILE",
    "BRIDGES_FILE_ID",
    "Bridge",
    "BridgeMoment",
    "BridgesFile",
    "FixedFact",
    "bridge_page",
    "load_bridges",
    "moments_for",
    "read_bridges_file",
    "validate_bridges",
]
