"""The season format (WP-111): what a season file must hold, and the loader.

One season is a folder, ``app/data/season/<id>/``:

* ``season.json`` — the question, the segments (tentpoles and gaps, with their
  nominal lengths), the flag table, the registers, the cast the season adds, and
  Lila's path gates;
* ``t1.json`` … ``t8.json`` — the tentpoles, each an authored two-day page
  (Day A ends on the mid-point hook, Day B resolves it), with its variants;
* ``gaps.json`` — the generated days between tentpoles: what may advance, what
  must not yet, the small moments, the complications and the example premises.

Text is written at A2, with B1 only where it differs (the bible's rule). A1 and
A2 learners who read another language get ``native`` translations of the A2 line
(«Traduire la case»). A date-bound line may carry a ``neutral`` wording (S-12).

Everything here is pure: loading and validating never touches a database or a
model. ``load_season`` is cached; a malformed file fails loudly at load time,
never in a learner's day (``tests/test_season_format.py`` loads every season).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SEASON_ROOT = Path(__file__).resolve().parents[2] / "data" / "season"

#: Bands that read the B1 line when one is written. A1/A2 read the A2 line.
B1_BANDS = frozenset({"B1", "B2", "C1", "C2"})
#: Chrome languages a task or a translation is written in.
LANGUAGES = ("en", "de", "fr")
MOODS = ("neutral", "happy", "cross", "moved")
MECHANICS = ("enquete", "choix", "dechiffrer", "convaincre", "balloon_choice")
#: Speakers that are not cast members: diegetic text and the learner's own fixed line.
TEXT_SPEAKERS = frozenset({"caption", "sms", "letter", "card", "toi", "all"})

#: A condition on the story state. Every key must hold:
#:
#: * a flag id → a value (equality), a list (membership), ``{"not": v}``, or
#:   ``{"set": bool}`` (whether the flag has been set at all);
#: * ``"path"`` → Lila's path (``romance``, ``friendship``, ``open``);
#: * ``"band"`` → ``"a1a2"`` or ``"b1"`` (B1 and above);
#: * ``"any"`` / ``"all"`` → a list of conditions.
Cond = dict[str, Any]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Wording(_Model):
    """A2 wording with an optional B1 one (a date-free alternative, S-12)."""

    a2: str = Field(min_length=1)
    b1: str | None = None


class Say(_Model):
    """One piece of French the learner reads, at the bands the bible writes."""

    a2: str = Field(min_length=1)
    b1: str | None = None
    #: The A2 line in the learner's own language, for A1/A2 learners (en, de).
    native: dict[str, str] = Field(default_factory=dict)
    #: S-12: the wording for a learner whose calendar is not the story's (a
    #: Christmas or New Year's Eve line away from those dates).
    neutral: Wording | None = None

    def text(self, band: str, *, neutral: bool = False) -> str:
        source: Say | Wording = self.neutral if (neutral and self.neutral) else self
        if str(band or "")[:2].upper() in B1_BANDS and source.b1:
            return source.b1
        return source.a2

    def native_for(self, language: str | None) -> str | None:
        return self.native.get(str(language or "")) or None


class SetsIf(_Model):
    """Flags set only when a condition holds (e.g. only on the romance path)."""

    when: Cond
    sets: dict[str, Any]


class Line(_Model):
    """A caption under the art: a character's line, or diegetic text.

    ``who`` is a cast id, a minor character's id (``season.minor_cast``), or one of
    :data:`TEXT_SPEAKERS`. ``toi`` is the learner's own *fixed* line (drawn as a
    balloon); the learner's free lines are turns, never lines.
    """

    who: str = Field(min_length=1)
    say: Say
    mood: Literal["neutral", "happy", "cross", "moved"] = "neutral"
    #: The script's stage direction, e.g. "to Lila, a whisper" — for the art and
    #: the owner, never printed as dialogue.
    direction: str = ""
    when: Cond = Field(default_factory=dict)


class Panel(_Model):
    """One panel. ``visual`` is the art direction (English); an empty ``visual``
    keeps the previous picture (a reaction line under the same framing)."""

    kind: Literal["panel"] = "panel"
    id: str = Field(min_length=1)
    visual: str = ""
    location_id: str | None = None
    in_frame: list[str] = Field(default_factory=list)
    silence: bool = False
    flashback: bool = False
    #: Text legible inside the art (Polaroid captions, the calendar, the neon…),
    #: written verbatim into the art prompt and overlaid by the reader.
    diegetic: list[str] = Field(default_factory=list)
    lines: list[Line] = Field(default_factory=list)
    #: The learner's balloon is drawn in this panel (F-2).
    balloon: bool = False
    when: Cond = Field(default_factory=dict)
    #: For the owner only; never shown to a learner.
    note: str = ""

    @model_validator(mode="after")
    def _silence_is_silent(self) -> Panel:
        speaking = [line for line in self.lines if line.who not in {"caption"}]
        if self.silence and speaking and not self.diegetic:
            # A silent panel may carry a caption or diegetic text, never a voice.
            raise ValueError(f"panel {self.id} is marked silence but has spoken lines")
        return self


class Reply(_Model):
    """One likely reply to a turn and how the scene answers it.

    ``means`` is what the classifier listens for; ``examples`` are the bible's
    French replies. What is read is what the learner *expresses* — never how
    well: a clumsy reply routes exactly like a polished one.
    """

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    means: str = Field(min_length=1)
    examples: list[str] = Field(default_factory=list)
    clumsy: bool = False
    beats: list[Panel] = Field(default_factory=list)
    sets: dict[str, Any] = Field(default_factory=dict)
    #: Lila's path (bible §7): what this reply expresses toward her.
    path: Literal["romance", "friendship"] | None = None
    #: "The exchange repeats once": the turn is asked again after these beats.
    repeat_once: bool = False
    #: When the same reply comes a second time after a repeat, these beats instead.
    again: list[Panel] = Field(default_factory=list)
    sets_if: list[SetsIf] = Field(default_factory=list)
    when: Cond = Field(default_factory=dict)


class Turn(_Model):
    """A character turns to the learner: the learner's balloon, then the routes."""

    kind: Literal["turn"] = "turn"
    id: str = Field(min_length=1)
    to: str = Field(min_length=1)
    panel: Panel
    #: What the learner must want to say, in their language (never a grammar target).
    task: dict[str, str]
    listens_for: str = Field(min_length=1)
    replies: list[Reply] = Field(min_length=1)
    fallback: str
    #: Bible §7: this turn is one of Lila's path gates.
    gate: int | None = None
    #: "Your task (small)": a light exchange inside a larger scene.
    small: bool = False
    #: Set whatever the learner says (e.g. Lila pockets the Polaroid in every version).
    sets: dict[str, Any] = Field(default_factory=dict)
    sets_if: list[SetsIf] = Field(default_factory=list)
    #: Beats that follow whichever reply ("In every route, Camille sets the visit").
    after: list[Panel] = Field(default_factory=list)
    when: Cond = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fallback_exists(self) -> Turn:
        ids = [reply.id for reply in self.replies]
        if len(set(ids)) != len(ids):
            raise ValueError(f"turn {self.id} has duplicate reply ids")
        if self.fallback not in ids:
            raise ValueError(f"turn {self.id}: fallback {self.fallback!r} is not a reply id")
        return self


class Option(_Model):
    """A card, a tap target or a reading. ``correct`` marks the evidence an
    enquête or a déchiffrer is looking for (never praised, never punished)."""

    id: str = Field(min_length=1)
    label: Say
    subtitle: Say | None = None
    sets: dict[str, Any] = Field(default_factory=dict)
    sets_if: list[SetsIf] = Field(default_factory=list)
    beats: list[Panel] = Field(default_factory=list)
    correct: bool | None = None
    when: Cond = Field(default_factory=dict)


class Solve(_Model):
    """The page pauses for the learner to do something that moves the plot.

    * ``enquete`` — tap the detail / the line the evidence contradicts;
    * ``choix`` — cards with a visible consequence;
    * ``dechiffrer`` — read a document; what is read changes the next beat;
    * ``convaincre`` — persuade: up to three objections, any sincere argument lands;
    * ``balloon_choice`` — the learner picks their own line (S-9, Camille).
    """

    kind: Literal["solve"] = "solve"
    id: str = Field(min_length=1)
    mechanic: Literal["enquete", "choix", "dechiffrer", "convaincre", "balloon_choice"]
    prompt: Say
    task: dict[str, str] = Field(default_factory=dict)
    #: Who is being persuaded (convaincre) or who poses the question.
    to: str | None = None
    #: What fills the screen: the photo, the calendar, the card, the letter.
    visual: str = ""
    document: Say | None = None
    options: list[Option] = Field(default_factory=list)
    #: B1's version when it differs (e.g. two lines to contradict instead of a picture).
    options_b1: list[Option] | None = None
    #: B1 "all that is true": several options may be chosen.
    multi_b1: bool = False
    #: Said when the learner taps elsewhere; the page continues.
    nudge: list[Panel] = Field(default_factory=list)
    #: Convaincre: the objections, in order, and what happens either way.
    objections: list[Say] = Field(default_factory=list)
    lands_means: str = ""
    lands_examples: list[str] = Field(default_factory=list)
    lands: list[Panel] = Field(default_factory=list)
    fails: list[Panel] = Field(default_factory=list)
    give_up: Say | None = None
    #: Beats that always come after objection N, whatever the learner said
    #: (T7: Gus's confession after his third objection).
    interlude_after: int | None = None
    interlude: list[Panel] = Field(default_factory=list)
    sets_on_land: dict[str, Any] = Field(default_factory=dict)
    sets_on_fail: dict[str, Any] = Field(default_factory=dict)
    #: The option (or "fail") the story takes when the solve is not played.
    default: str | None = None
    #: The flag this solve decides, for the flag table's "set where".
    flag: str | None = None
    when: Cond = Field(default_factory=dict)

    @model_validator(mode="after")
    def _well_formed(self) -> Solve:
        if self.mechanic == "convaincre":
            if not self.objections:
                raise ValueError(f"solve {self.id}: convaincre needs objections")
        elif not self.options:
            raise ValueError(f"solve {self.id}: {self.mechanic} needs options")
        ids = [option.id for option in [*self.options, *(self.options_b1 or [])]]
        if self.default and self.default not in {*ids, "fail", "land"}:
            raise ValueError(f"solve {self.id}: default {self.default!r} is not an option")
        return self


class Hook(_Model):
    """The mid-point hook (end of Day A) or «À suivre…» (end of Day B)."""

    kind: Literal["hook"] = "hook"
    id: str = Field(min_length=1)
    role: Literal["midpoint", "a_suivre"]
    panel: Panel
    when: Cond = Field(default_factory=dict)


class Include(_Model):
    """A shared block of the tentpole (T8's letter and platform)."""

    kind: Literal["include"] = "include"
    ref: str = Field(min_length=1)
    when: Cond = Field(default_factory=dict)


Movement = Annotated[Panel | Turn | Solve | Hook | Include, Field(discriminator="kind")]


class Recap(_Model):
    """«Précédemment»: a strip of earlier panels, by id, with a short label."""

    ref: str = Field(min_length=1)
    label: str = ""


class LexiconEntry(_Model):
    """A word the scene needs (``11-pedagogie.md``), where it is said."""

    surface_fr: str = Field(min_length=1)
    lemma: str = Field(min_length=1)
    gloss: dict[str, str] = Field(default_factory=dict)
    part_of_speech: str | None = None
    gender: Literal["m", "f"] | None = None


class Day(_Model):
    """One day of a tentpole: Day A (to the mid-point hook) or Day B."""

    day: Literal["a", "b"]
    #: A named variant (T5 «elle te le dit» / «tu le découvres»; T8's endings).
    variant: str | None = None
    when: Cond = Field(default_factory=dict)
    story_date_fr: str = Field(min_length=1)
    #: Date-bound (S-12): "noel", "reveillon". A learner off that calendar reads
    #: the ``neutral`` wordings.
    holiday: str | None = None
    title_fr: str | None = None
    previously: list[Recap] = Field(default_factory=list)
    movements: list[Movement] = Field(min_length=1)
    lexicon: list[LexiconEntry] = Field(default_factory=list)
    can_do: dict[str, str] = Field(default_factory=dict)
    #: The location the day opens in (the scene's plate and the chapter's place).
    location_id: str = Field(min_length=1)
    #: Estimated minutes of reading and speaking, for the day's budget.
    minutes: int = Field(default=6, ge=1, le=30)


class Tentpole(_Model):
    id: str = Field(pattern=r"^t[1-9]$")
    number: int = Field(ge=1, le=9)
    title_fr: str = Field(min_length=1)
    intent: str = ""
    state_in: list[str] = Field(default_factory=list)
    flags_read: list[str] = Field(default_factory=list)
    days: list[Day] = Field(min_length=2)
    shared: dict[str, list[Movement]] = Field(default_factory=dict)
    #: Fixed facts this tentpole establishes for everybody.
    state_out: dict[str, Any] = Field(default_factory=dict)
    #: What the next gap must know (the "For gap N" notes).
    for_next_gap: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _both_days(self) -> Tentpole:
        if {day.day for day in self.days} != {"a", "b"}:
            raise ValueError(f"{self.id} needs a Day A and a Day B")
        return self


class FlagSpec(_Model):
    """One row of the bible's flag table (§6)."""

    id: str = Field(min_length=1)
    #: The allowed values, or a type: "text", "date", "bool", "list".
    values: list[str] | Literal["text", "date", "bool", "list"]
    default: Any = None
    set_where: str = ""
    read_where: str = ""
    effect: str = ""
    #: Set the same way for everybody by a tentpole.
    fixed: bool = False


class Segment(_Model):
    """A stretch of the season: a tentpole (two days) or a gap (generated days)."""

    id: str = Field(min_length=1)
    kind: Literal["tentpole", "gap"]
    #: Nominal days (the bible's calendar, §8). A gap may flex by ±1.
    days: int = Field(ge=1, le=10)
    #: The bible's story dates, e.g. "mer. 11 – jeu. 12 nov.".
    story_dates: str = ""


class Gate(_Model):
    """One of Lila's path gates (bible §7)."""

    number: int = Field(ge=1, le=9)
    where: str = Field(min_length=1)
    romance: str = ""
    friendship: str = ""


class SmallMoment(_Model):
    id: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sets: dict[str, Any] = Field(default_factory=dict)


class Forbidden(_Model):
    """A reveal the gap must not make. ``patterns`` are regular expressions over the
    French a learner reads (case-insensitive); the story critic judges the rest."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    patterns: list[str] = Field(default_factory=list)
    #: A flag condition under which this is no longer forbidden.
    unless: Cond = Field(default_factory=dict)


class Premise(_Model):
    id: str = Field(min_length=1)
    title_fr: str = Field(min_length=1)
    text: str = Field(min_length=1)
    change: str = ""
    turn: str = ""
    gate: int | None = None
    #: Flags this premise may set (whitelisted for the day's turn).
    sets: list[str] = Field(default_factory=list)
    when: Cond = Field(default_factory=dict)


class Required(_Model):
    """A moment the gap must stage before it ends (a gate, a seeded scene)."""

    premise: str = Field(min_length=1)
    #: The gap day (1-based) by which it is staged; it is offered from ``from_day``.
    from_day: int = Field(default=1, ge=1)
    by_day: int = Field(ge=1)


class Gap(_Model):
    id: str = Field(pattern=r"^g[1-9]$")
    number: int = Field(ge=1, le=9)
    title_fr: str = Field(min_length=1)
    threads: list[str] = Field(default_factory=list)
    small_moments: list[SmallMoment] = Field(default_factory=list)
    complications: list[str] = Field(default_factory=list)
    must_not: list[Forbidden] = Field(default_factory=list)
    premises: list[Premise] = Field(default_factory=list)
    required: list[Required] = Field(default_factory=list)
    #: Flags a generated day of this gap may set from the learner's turn.
    sets_allowed: list[str] = Field(default_factory=list)
    #: What must be true before the next tentpole (its "State in").
    establish: list[str] = Field(default_factory=list)
    #: Plot facts, by flag, the director is told (e.g. by ``s1.fire_photo``).
    by_flag: dict[str, dict[str, str]] = Field(default_factory=dict)


class CastMember(_Model):
    """A cast member the season adds or recasts (projected into the world bible)."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: Literal["tu", "vous"]
    minor: bool = False


class Season(_Model):
    id: str = Field(min_length=1)
    title_fr: str = Field(min_length=1)
    question: Say
    logline: str = ""
    segments: list[Segment] = Field(min_length=2)
    flags: list[FlagSpec] = Field(default_factory=list)
    cast: list[CastMember] = Field(default_factory=list)
    gates: list[Gate] = Field(default_factory=list)
    writing_rules: list[str] = Field(default_factory=list)
    #: Set after loading: the tentpoles and gaps by id, the rules every generated
    #: day follows (``gaps.json`` → ``rules``) and the reveals no gap may make.
    tentpoles: dict[str, Tentpole] = Field(default_factory=dict)
    gaps: dict[str, Gap] = Field(default_factory=dict)
    gap_rules: dict[str, Any] = Field(default_factory=dict)
    global_must_not: list[Forbidden] = Field(default_factory=list)

    @property
    def total_days(self) -> int:
        return sum(segment.days for segment in self.segments)

    def flag(self, flag_id: str) -> FlagSpec | None:
        return next((row for row in self.flags if row.id == flag_id), None)

    def speaker_ids(self) -> set[str]:
        return {member.id for member in self.cast} | set(TEXT_SPEAKERS)


class SeasonFormatError(ValueError):
    """A season file that does not hold together (raised at load, never mid-day)."""


def _read(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeasonFormatError(f"{path.name}: {exc}") from exc


def iter_movements(movements: list[Any]):
    """Every movement, and every panel nested in a reply, an option or a solve."""

    for movement in movements:
        yield movement
        if isinstance(movement, Turn):
            yield movement.panel
            for reply in movement.replies:
                yield from reply.beats
                yield from reply.again
            yield from movement.after
        elif isinstance(movement, Solve):
            for option in [*movement.options, *(movement.options_b1 or [])]:
                yield from option.beats
            yield from movement.nudge
            yield from movement.lands
            yield from movement.fails
            yield from movement.interlude
        elif isinstance(movement, Hook):
            yield movement.panel


def iter_panels(movements: list[Any]):
    for item in iter_movements(movements):
        if isinstance(item, Panel):
            yield item


def cond_flags(cond: Cond) -> set[str]:
    """The flag ids a condition reads (``any``/``all`` recursively)."""

    names: set[str] = set()
    for key, value in (cond or {}).items():
        if key in {"any", "all"}:
            for inner in value or []:
                names |= cond_flags(inner)
        elif key not in {"path", "band"}:
            names.add(key)
    return names


def _check_tentpole(season: Season, tentpole: Tentpole, *, locations: set[str] | None) -> list[str]:
    problems: list[str] = []
    speakers = season.speaker_ids()
    known_flags = {row.id for row in season.flags}
    blocks = [day.movements for day in tentpole.days] + list(tentpole.shared.values())
    for day in tentpole.days:
        for cond in [day.when]:
            unknown = cond_flags(cond) - known_flags
            if unknown:
                problems.append(f"{tentpole.id}.{day.day}: unknown flags in when: {sorted(unknown)}")
        for movement in day.movements:
            if isinstance(movement, Include) and movement.ref not in tentpole.shared:
                problems.append(f"{tentpole.id}.{day.day}: include {movement.ref!r} is not shared")
        if locations is not None and day.location_id not in locations:
            problems.append(f"{tentpole.id}.{day.day}: unknown location {day.location_id!r}")
    for movements in blocks:
        for item in iter_movements(movements):
            conds = [getattr(item, "when", {}) or {}]
            if isinstance(item, Turn):
                conds += [reply.when for reply in item.replies]
                if item.to not in speakers:
                    problems.append(f"{tentpole.id}: turn {item.id} addressed to unknown {item.to!r}")
                for reply in item.replies:
                    conds += [row.when for row in reply.sets_if]
                    bad = (set(reply.sets) | {k for row in reply.sets_if for k in row.sets}) - known_flags
                    if bad:
                        problems.append(f"{tentpole.id}: reply {item.id}/{reply.id} sets unknown {sorted(bad)}")
                bad = set(item.sets) - known_flags
                if bad:
                    problems.append(f"{tentpole.id}: turn {item.id} sets unknown {sorted(bad)}")
                missing = [lang for lang in LANGUAGES if not item.task.get(lang)]
                if missing:
                    problems.append(f"{tentpole.id}: turn {item.id} has no task in {missing}")
            if isinstance(item, Solve):
                for option in [*item.options, *(item.options_b1 or [])]:
                    conds.append(option.when)
                    conds += [row.when for row in option.sets_if]
                    bad = (set(option.sets) | {k for row in option.sets_if for k in row.sets}) - known_flags
                    if bad:
                        problems.append(f"{tentpole.id}: option {item.id}/{option.id} sets unknown {sorted(bad)}")
                bad = (set(item.sets_on_land) | set(item.sets_on_fail)) - known_flags
                if bad:
                    problems.append(f"{tentpole.id}: solve {item.id} sets unknown {sorted(bad)}")
                if item.flag and item.flag not in known_flags:
                    problems.append(f"{tentpole.id}: solve {item.id} decides unknown flag {item.flag!r}")
                missing = [lang for lang in LANGUAGES if not item.task.get(lang)]
                if missing:
                    problems.append(f"{tentpole.id}: solve {item.id} has no task in {missing}")
            if isinstance(item, Panel):
                for line in item.lines:
                    conds.append(line.when)
                    if line.who not in speakers:
                        problems.append(f"{tentpole.id}: panel {item.id} speaker {line.who!r} is not in the season cast")
                if locations is not None and item.location_id and item.location_id not in locations:
                    problems.append(f"{tentpole.id}: panel {item.id} at unknown location {item.location_id!r}")
                for cid in item.in_frame:
                    if cid not in speakers:
                        problems.append(f"{tentpole.id}: panel {item.id} frames unknown {cid!r}")
            for cond in conds:
                unknown = cond_flags(cond or {}) - known_flags
                if unknown:
                    problems.append(f"{tentpole.id}: unknown flags in when: {sorted(unknown)}")
    bad = set(tentpole.state_out) - known_flags
    if bad:
        problems.append(f"{tentpole.id}: state_out sets unknown {sorted(bad)}")
    return problems


def validate_season(season: Season, *, locations: set[str] | None = None) -> list[str]:
    """Every cross-reference a season file makes, checked. Empty means it holds."""

    problems: list[str] = []
    ids = [segment.id for segment in season.segments]
    if len(set(ids)) != len(ids):
        problems.append("segment ids repeat")
    for segment in season.segments:
        if segment.kind == "tentpole":
            if segment.days != 2:
                problems.append(f"{segment.id}: a tentpole runs over two days (S-7)")
            if segment.id not in season.tentpoles:
                problems.append(f"{segment.id}: no tentpole file")
        elif segment.id not in season.gaps:
            problems.append(f"{segment.id}: no gap rules")
    known_flags = {row.id for row in season.flags}
    for gap in season.gaps.values():
        bad = set(gap.sets_allowed) - known_flags
        if bad:
            problems.append(f"{gap.id}: sets_allowed names unknown flags {sorted(bad)}")
        premise_ids = {premise.id for premise in gap.premises}
        for need in gap.required:
            if need.premise not in premise_ids:
                problems.append(f"{gap.id}: required premise {need.premise!r} is not a premise")
        for premise in gap.premises:
            unknown = cond_flags(premise.when) - known_flags
            if unknown:
                problems.append(f"{gap.id}: premise {premise.id} when names unknown {sorted(unknown)}")
        for forbidden in gap.must_not:
            unknown = cond_flags(forbidden.unless) - known_flags
            if unknown:
                problems.append(f"{gap.id}: must_not {forbidden.id} unless names unknown {sorted(unknown)}")
    for tentpole in season.tentpoles.values():
        problems.extend(_check_tentpole(season, tentpole, locations=locations))
    return problems


@lru_cache(maxsize=4)
def load_season(season_id: str, *, root: Path | None = None) -> Season:
    """The season in ``app/data/season/<season_id>/``, validated. Cached."""

    folder = (root or SEASON_ROOT) / season_id
    if not folder.is_dir():
        raise SeasonFormatError(f"no season folder {folder}")
    season = Season.model_validate(_read(folder / "season.json"))
    tentpoles: dict[str, Tentpole] = {}
    for segment in season.segments:
        if segment.kind != "tentpole":
            continue
        path = folder / f"{segment.id}.json"
        if path.is_file():
            tentpoles[segment.id] = Tentpole.model_validate(_read(path))
    gaps_path = folder / "gaps.json"
    gaps_file = _read(gaps_path) if gaps_path.is_file() else {}
    gaps = {row["id"]: Gap.model_validate(row) for row in gaps_file.get("gaps") or []}
    season = season.model_copy(
        update={
            "tentpoles": tentpoles,
            "gaps": gaps,
            "gap_rules": dict(gaps_file.get("rules") or {}),
            "global_must_not": [Forbidden.model_validate(row) for row in gaps_file.get("global_must_not") or []],
        }
    )
    problems = validate_season(season)
    if problems:
        raise SeasonFormatError(f"season {season_id}: " + "; ".join(problems[:12]))
    return season


def available_seasons(root: Path | None = None) -> list[str]:
    base = root or SEASON_ROOT
    if not base.is_dir():
        return []
    return sorted(path.name for path in base.iterdir() if (path / "season.json").is_file())
