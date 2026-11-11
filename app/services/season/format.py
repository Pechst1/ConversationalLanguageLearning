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
Since 2026-10-03 a line may also carry ``a1`` / ``b2`` / ``c1`` level variants
(:data:`LEVEL_PREFERENCE`), so the season reads at the learner's own level.

Everything here is pure: loading and validating never touches a database or a
model. ``load_season`` is cached; a malformed file fails loudly at load time,
never in a learner's day (``tests/test_season_format.py`` loads every season).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SEASON_ROOT = Path(__file__).resolve().parents[2] / "data" / "season"

#: Bands that read the B1 line when one is written. A1/A2 read the A2 line.
B1_BANDS = frozenset({"B1", "B2", "C1", "C2"})
#: Chrome languages a task or a translation is written in.
LANGUAGES = ("en", "de", "fr")
#: WP-137 C-4: ``cold`` — a dry or frosty line; the drawn face holds no smile.
MOODS = ("neutral", "happy", "cross", "moved", "cold")
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


#: 2026-10-03 (content program, T-2): which written level each learner band
#: reads, nearest first. The bible's A2 line (and its B1 line where it wrote
#: one) stays canonical; ``a1``, ``b2`` and ``c1`` are level variants derived
#: from it offline and validated against the band's words and grammar
#: (``scripts/season_levels.py``). A band never reads a line written above it.
LEVEL_PREFERENCE: dict[str, tuple[str, ...]] = {
    "A1": ("a1", "a2"),
    "A2": ("a2",),
    "B1": ("b1", "a2"),
    "B2": ("b2", "b1", "a2"),
    "C1": ("c1", "b2", "b1", "a2"),
    "C2": ("c1", "b2", "b1", "a2"),
}
LEVEL_FIELDS = ("a1", "a2", "b1", "b2", "c1")


def examples_at(canonical: list[str], by_level: dict[str, list[str]], band: str | None) -> list[str]:
    """A band's own example replies first (nearest written level), then the bible's."""

    own: list[str] = []
    for field in written_levels(band):
        own = list(by_level.get(field) or [])
        if own:
            break
    return list(dict.fromkeys([*own, *canonical]))


def written_levels(band: str | None) -> tuple[str, ...]:
    """The level fields a band reads, nearest first (unreadable bands read as A1)."""

    return LEVEL_PREFERENCE.get(str(band or "")[:2].upper(), LEVEL_PREFERENCE["A1"])


def _same(a: str | None, b: str | None) -> bool:
    return " ".join(str(a or "").split()) == " ".join(str(b or "").split())


def _native_at(owner: Any, field: str, language: str | None) -> str | None:
    """The translation of ``owner``'s ``field`` text: the A2 line's ``native`` for the
    A2 line (or an A1 variant that says the same), ``native_a1`` for an A1 variant.
    Above A2 nobody is translated, so other fields have none."""

    lang = str(language or "")
    if field == "a1" and not _same(getattr(owner, "a1", None), owner.a2):
        return (owner.native_a1 or {}).get(lang) or None
    if field in ("a1", "a2"):
        return (owner.native or {}).get(lang) or None
    return None


class Wording(_Model):
    """A2 wording with optional other levels (a date-free alternative, S-12)."""

    a2: str = Field(min_length=1)
    a1: str | None = None
    b1: str | None = None
    b2: str | None = None
    c1: str | None = None
    #: Fingerprint of the a2/b1 text the variants were written from (stale check).
    level_src: str | None = None
    #: The A2 wording / the A1 variant in the learner's own language (en, de).
    native: dict[str, str] = Field(default_factory=dict)
    native_a1: dict[str, str] = Field(default_factory=dict)

    def served(self, band: str) -> tuple[str, str]:
        """``(text, field)``: the wording a band reads and which level it is."""

        for field in written_levels(band):
            value = getattr(self, field, None)
            if value:
                return value, field
        return self.a2, "a2"

    def text(self, band: str) -> str:
        return self.served(band)[0]

    def native_at(self, field: str, language: str | None) -> str | None:
        return _native_at(self, field, language)


class Say(_Model):
    """One piece of French the learner reads, at the bands the bible writes."""

    a2: str = Field(min_length=1)
    a1: str | None = None
    b1: str | None = None
    b2: str | None = None
    c1: str | None = None
    #: Fingerprint of the a2/b1 text the variants were written from (stale check).
    level_src: str | None = None
    #: The A2 line in the learner's own language, for A1/A2 learners (en, de).
    native: dict[str, str] = Field(default_factory=dict)
    #: QA-STORY 2026-10-03: the A1 variant in the learner's own language. An A1
    #: line is not the A2 line, so it never borrows the A2 line's translation.
    native_a1: dict[str, str] = Field(default_factory=dict)
    #: S-12: the wording for a learner whose calendar is not the story's (a
    #: Christmas or New Year's Eve line away from those dates).
    neutral: Wording | None = None

    def served(self, band: str, *, neutral: bool = False) -> tuple[str, str, Say | Wording]:
        """``(text, field, owner)``: what a band reads, at which written level, and
        whether it is the line itself or its neutral wording."""

        if neutral and self.neutral:
            text, field = self.neutral.served(band)
            return text, field, self.neutral
        for field in written_levels(band):
            value = getattr(self, field, None)
            if value:
                return value, field, self
        return self.a2, "a2", self

    def text(self, band: str, *, neutral: bool = False) -> str:
        return self.served(band, neutral=neutral)[0]

    def native_for(self, language: str | None) -> str | None:
        return self.native.get(str(language or "")) or None

    def native_served(self, band: str, language: str | None, *, neutral: bool = False) -> str | None:
        """The translation of exactly the French served at ``band`` — never another
        level's: an A1 variant reads its own ``native_a1``, or nothing."""

        _text, field, owner = self.served(band, neutral=neutral)
        return _native_at(owner, field, language)


class SetsIf(_Model):
    """Flags set only when a condition holds (e.g. only on the romance path)."""

    when: Cond
    sets: dict[str, Any]


#: Le Quartier phase 1: a question asked only when the learner's answer to an earlier
#: question of the same day took one of these replies, ``{turn or solve id: [reply or
#: option ids]}`` (Margaux's café crème follows only the replies where she sets the cup
#: down). Read during the conversation, not when the page is resolved.
OnlyAfter = dict[str, list[str]]


class Line(_Model):
    """A caption under the art: a character's line, or diegetic text.

    ``who`` is a cast id, a minor character's id (``season.minor_cast``), or one of
    :data:`TEXT_SPEAKERS`. ``toi`` is the learner's own *fixed* line (drawn as a
    balloon); the learner's free lines are turns, never lines.
    """

    who: str = Field(min_length=1)
    say: Say
    mood: Literal["neutral", "happy", "cross", "moved", "cold"] = "neutral"
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
    #: Level variants of the examples (``a1``/``b2``/``c1``, T-2): what a learner at
    #: that band would plausibly say. They come first for that band and add to
    #: the routing examples; they never replace the bible's.
    examples_by_level: dict[str, list[str]] = Field(default_factory=dict)
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
    #: QA-STORY: the same task in one plain sentence (en/de/fr) — what is served.
    task_plain: dict[str, str] = Field(default_factory=dict)
    #: QA-STORY: what the addressee says, once, when a reply clearly expresses none
    #: of the routes: ``{fr, en, de, fr_named?, en_named?, de_named?}``.
    ask_again: dict[str, str] | None = None
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
    only_after: OnlyAfter = Field(default_factory=dict)

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
    #: Le Quartier phase 1 (owner decision 2026-10-28): a «Le choix» answered in the
    #: learner's own French rather than by its card. What the reader listens for, and
    #: some French ways to say it (the card's label always routes too).
    means: str = ""
    examples: list[str] = Field(default_factory=list)


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
    task_plain: dict[str, str] = Field(default_factory=dict)
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
    lands_examples_by_level: dict[str, list[str]] = Field(default_factory=dict)
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
    only_after: OnlyAfter = Field(default_factory=dict)

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


class Forbidden(_Model):
    """A reveal the gap must not make. ``patterns`` are regular expressions over the
    French a learner reads (case-insensitive); the story critic judges the rest."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    patterns: list[str] = Field(default_factory=list)
    #: A flag condition under which this is no longer forbidden.
    unless: Cond = Field(default_factory=dict)


class Tentpole(_Model):
    id: str = Field(pattern=r"^t[1-9]$")
    number: int = Field(ge=1, le=9)
    title_fr: str = Field(min_length=1)
    intent: str = ""
    state_in: list[str] = Field(default_factory=list)
    flags_read: list[str] = Field(default_factory=list)
    days: list[Day] = Field(min_length=2)
    shared: dict[str, list[Movement]] = Field(default_factory=dict)
    #: Fixed facts this tentpole establishes for everybody, once its Day B is played.
    state_out: dict[str, Any] = Field(default_factory=dict)
    #: What already holds on its first page, where the page is written with it (#147: Gus
    #: says «tu» from T3 A's first panel, while ``state_out`` would move him after T3 B).
    opens_with: dict[str, Any] = Field(default_factory=dict)
    #: What the next gap must know (the "For gap N" notes).
    for_next_gap: list[str] = Field(default_factory=list)
    #: WP-155: what this tentpole reveals (T5: Berlin). Every generated day before it
    #: inherits these as ``must_not`` rows: the director reads them in its brief and
    #: the page and reply-lane guards refuse a draft that names them.
    reveals: list[Forbidden] = Field(default_factory=list)

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


class Premise(_Model):
    id: str = Field(min_length=1)
    title_fr: str = Field(min_length=1)
    text: str = Field(min_length=1)
    change: str = ""
    turn: str = ""
    gate: int | None = None
    #: Flags this premise may set (whitelisted for the day's turn).
    sets: list[str] = Field(default_factory=list)
    #: What a planned day settles when the learner let it pass and did not set the flag
    #: themselves (the ticket moves to a date the story picks).
    settles: dict[str, Any] = Field(default_factory=dict)
    when: Cond = Field(default_factory=dict)


class Required(_Model):
    """A moment the gap must stage before it ends (a gate, a seeded scene)."""

    premise: str = Field(min_length=1)
    #: The gap day (1-based) by which it is staged; it is offered from ``from_day``.
    from_day: int = Field(default=1, ge=1)
    by_day: int = Field(ge=1)


class Lands(_Model):
    """One fact a planned day makes true whatever the learner answers (the floor)."""

    #: ``g3.menu``: the gap's id, a dot, a short name. Unique in the season.
    id: str = Field(pattern=r"^g[1-9]\.[a-z0-9_]+$")
    text: str = Field(min_length=1)
    #: French words every landing shows when this fact becomes true («menu»).
    show: list[str] = Field(default_factory=list)


class Mark(_Model):
    """What the learner's own words add to a day, kept word for word."""

    id: str = Field(pattern=r"^g[1-9]\.[a-z0-9_]+$")
    kind: Literal["name", "choice", "words"]
    #: What it is, for the writer of the day it comes back on («the name the learner
    #: gave one of Marin's canapés»).
    what: str = ""
    max_words: int = Field(default=4, ge=1, le=12)
    #: What stands in when the learner gave nothing usable. ``{name}`` is their first name.
    default_fr: str = Field(min_length=1)
    #: Where it is shown again: a later day of this gap (``g3.7``) or a later tentpole (``t4``).
    comes_back: list[str] = Field(default_factory=list)


class ContractTurn(_Model):
    """One ask of the learner. ``ask`` is the task line's intent per written level, in
    English, one ask each: the level guard that refuses a chained task line
    (``objective_too_complex``) is run over these when the season is tested."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    ask: dict[str, str] = Field(min_length=1)
    #: The same question in simpler French, put once more after an off-topic reply.
    ask_again_fr: str = ""
    mark: Mark | None = None


class Route(_Model):
    """One way a planned day can land. Every route makes every ``lands`` fact true."""

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    when: str = Field(min_length=1)
    #: The route taken on a question, a refusal, silence, or a reply nobody planned for.
    default: bool = False
    #: The lead's last spoken line on this route (their bubble closes the day). The
    #: day's mark is its ``{g3.canape_name}`` slot. None: the day closes on ``after_fr``,
    #: narrated (a route where nobody speaks, or a day whose lead is not in the cast).
    line: Wording | None = None
    #: Taken only with the learner's own mark («named»): without one, the day lands on
    #: the route that needs none.
    needs_mark: bool = False


class ContractHook(_Model):
    """The «À suivre…» of a planned day: who says it, the beat it leads into, the line."""

    speaker: str = Field(min_length=1)
    #: The premise of the next planned day, or the tentpole that follows the gap.
    about: str = Field(min_length=1)
    fr: Wording
    #: Words a rephrased hook must still contain (a first filter, never the whole check).
    must_name: list[str] = Field(default_factory=list)


class StandInPanel(_Model):
    """One panel of a stand-in page: a caption, or one line the day's lead says."""

    text: Wording
    says: bool = False


class StandIn(_Model):
    """The page of a planned day as written here: four to six short panels that set
    the scene, the lead's question, the task and a reply to lean on. Served, without a
    model, on the day every attempt to write the page failed
    (``STORY_CONTRACT_STAND_IN``), so the day is still today's day of the story and
    lands on its contract."""

    panels: list[StandInPanel] = Field(min_length=4, max_length=6)
    #: The panels on the day the page is set at the contract's ``place_alt`` (the first
    #: place is not built yet). None: the page cannot move, and such a day has no
    #: stand-in.
    alt_panels: list[StandInPanel] | None = Field(default=None, min_length=4, max_length=6)
    #: What the lead says to the learner (the page's opening line).
    asks: Wording
    #: The task line per written level, in German and French; the English one is the
    #: turn's own ``ask``.
    task: dict[str, dict[str, str]] = Field(min_length=1)
    #: A reply the learner may lean on, per written level.
    reply_fr: dict[str, str] = Field(min_length=1)


class DayContract(_Model):
    """A planned day as a contract (red-thread design, 2026-11-10): what becomes true
    whatever the learner says, what their words add, where the page is set and the one
    thing owed tomorrow. Data only until ``STORY_DAY_CONTRACT`` reads it."""

    place: str = Field(min_length=1)
    #: A canon-safe second place for the day its own is not built yet.
    place_alt: str | None = None
    #: Who the learner talks to, and whose bubble closes the day (``routes[].line``).
    lead: str | None = None
    lands: list[Lands] = Field(min_length=1)
    turns: list[ContractTurn] = Field(min_length=1, max_length=2)
    routes: list[Route] = Field(min_length=2, max_length=4)
    hook: ContractHook
    #: «What changed», one line, for tomorrow's «Précédemment» and today's Done screen.
    #: ``{g3.canape_name}`` is the day's mark.
    after_fr: Wording
    #: The closing turn has one job: the learner's mark, or the plain turn.
    closing_job: Literal["mark", "turn"] = "turn"
    #: The page as written here, for the day no writer delivers one.
    stand_in: StandIn | None = None

    @model_validator(mode="after")
    def _holds_together(self) -> DayContract:
        if sum(1 for route in self.routes if route.default) != 1:
            raise ValueError("a day contract has exactly one default route")
        for label, ids in (("route", [r.id for r in self.routes]), ("turn", [t.id for t in self.turns])):
            if len(set(ids)) != len(ids):
                raise ValueError(f"a day contract repeats a {label} id")
        marks = [turn.mark for turn in self.turns if turn.mark]
        if len(marks) > 1:
            raise ValueError("a day contract carries at most one mark")
        if not marks and any(route.needs_mark for route in self.routes):
            raise ValueError("a route needs a mark and the day carries none")
        if any(route.needs_mark and route.default for route in self.routes):
            raise ValueError("the default route never needs the learner's mark")
        if (self.closing_job == "mark") != bool(marks and self.turns[-1].mark):
            raise ValueError("closing_job is 'mark' exactly when the last turn carries the mark")
        return self

    @property
    def mark(self) -> Mark | None:
        return next((turn.mark for turn in self.turns if turn.mark), None)


class Destination(_Model):
    """Where a gap is going: the tentpole it leads to, in the words the learner reads."""

    tentpole: str = Field(pattern=r"^t[1-9]$")
    title_fr: str = Field(min_length=1)
    #: The day it happens, as the pages say it («samedi»).
    when_fr: str = Field(min_length=1)
    stake_fr: Wording | None = None


class DayBeat(_Model):
    """One generated day of a gap, planned: the premise it stages and the change it
    makes (story plan, 2026-10-15). The director still writes the page; it no longer
    has to invent what moves."""

    #: The gap day (1-based).
    day: int = Field(ge=1)
    premise: str = Field(min_length=1)
    #: The change, «before → after», in plain words.
    before: str = Field(min_length=1)
    after: str = Field(min_length=1)
    #: A small extra the page may carry if it fits (a glimpse, a running gag).
    also: str = ""
    #: Where the «À suivre…» points.
    hook: str = ""
    #: «Demain» (steering read 2026-10-24): what the learner picks when they choose
    #: this beat for tomorrow, an infinitive phrase in short French («Cuisiner avec
    #: Lila»). A beat without one is never offered out of the plan's order.
    pick_fr: str = ""
    #: The premises this beat stands on (the box is open before Gus's Polaroid is
    #: given): it is offered for tomorrow only once they are staged.
    needs: list[str] = Field(default_factory=list)
    #: The day as a contract; a beat without one is planned in prose only.
    contract: DayContract | None = None


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
    #: The day plan: one beat per generated day. A gap without one leaves the day's
    #: premise to the director (``required`` still holds either way).
    days: list[DayBeat] = Field(default_factory=list)
    #: Where the gap is going, for the strip above its pages.
    destination: Destination | None = None


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
        asked: dict[str, set[str]] = {}
        for movement in day.movements:
            if isinstance(movement, Include) and movement.ref not in tentpole.shared:
                problems.append(f"{tentpole.id}.{day.day}: include {movement.ref!r} is not shared")
            if isinstance(movement, Turn | Solve):
                for earlier, replies in movement.only_after.items():
                    if earlier not in asked:
                        problems.append(f"{tentpole.id}.{day.day}: {movement.id} is asked only after {earlier!r}, which is not an earlier question of the day")
                    elif not replies or set(replies) - asked[earlier]:
                        problems.append(f"{tentpole.id}.{day.day}: {movement.id} is asked only after replies of {earlier!r} it does not have: {sorted(set(replies) - asked[earlier])}")
                asked[movement.id] = (
                    {reply.id for reply in movement.replies}
                    if isinstance(movement, Turn)
                    else {option.id for option in [*movement.options, *(movement.options_b1 or [])]}
                )
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
    bad = set(tentpole.opens_with) - known_flags
    if bad:
        problems.append(f"{tentpole.id}: opens_with sets unknown {sorted(bad)}")
    if any(key in tentpole.state_out and tentpole.state_out[key] != value for key, value in tentpole.opens_with.items()):
        problems.append(f"{tentpole.id}: opens_with and state_out disagree")
    return problems


def _exclusive(one: Cond, other: Cond) -> bool:
    """Can two conditions never hold together? Only a flag both name with no value in
    common counts (gap 6 plans one beat per ``s1.plan`` on the same day)."""

    def values(want: Any) -> set[str]:
        return {str(item) for item in (want if isinstance(want, list) else [want])}

    return any(
        key not in {"any", "all"} and key in other and not values(want) & values(other[key])
        for key, want in one.items()
    )


#: A pick label opens on an infinitive («Cuisiner avec Lila»): the pick is filed as
#: tomorrow's line «On va cuisiner avec Lila.» (``story_tomorrow.hook_for``).
_INFINITIVE = re.compile(r"^[A-ZÀ-Ý][a-zà-ÿ]*(?:er|ir|re)\b")


def _check_day_plan(season: Season, gap: Gap, premise_ids: set[str]) -> list[str]:
    """A gap's day plan: real premises, one beat a day inside the gap, each premise
    once, and every required moment planned inside its own window."""

    if not gap.days:
        return []
    problems: list[str] = []
    length = next((segment.days for segment in season.segments if segment.id == gap.id), None)
    when = {premise.id: premise.when for premise in gap.premises}
    by_day: dict[int, list[str]] = {}
    for beat in gap.days:
        by_day.setdefault(beat.day, []).append(beat.premise)
    for same_day in by_day.values():
        pairs = [(a, b) for n, a in enumerate(same_day) for b in same_day[n + 1 :]]
        if any(not _exclusive(when.get(a) or {}, when.get(b) or {}) for a, b in pairs):
            problems.append(f"{gap.id}: the day plan has two beats on one day")
            break
    premises = [beat.premise for beat in gap.days]
    if len(set(premises)) != len(premises):
        problems.append(f"{gap.id}: the day plan stages a premise twice")
    planned = {beat.premise: beat.day for beat in gap.days}
    for beat in gap.days:
        if beat.premise not in premise_ids:
            problems.append(f"{gap.id}: day {beat.day} plans {beat.premise!r}, which is not a premise")
        if length is not None and beat.day > length:
            problems.append(f"{gap.id}: day {beat.day} is past the gap's {length} days")
        for need in beat.needs:
            if planned.get(need, beat.day) >= beat.day:
                problems.append(f"{gap.id}: {beat.premise!r} needs {need!r}, which the plan does not stage before it")
        if beat.pick_fr and not _INFINITIVE.match(beat.pick_fr):
            problems.append(f"{gap.id}: {beat.premise!r} pick_fr {beat.pick_fr!r} is not an infinitive phrase")
    for need in gap.required:
        day = planned.get(need.premise)
        if day is None or not need.from_day <= day <= need.by_day:
            problems.append(
                f"{gap.id}: required {need.premise!r} is not planned inside days {need.from_day}-{need.by_day}"
            )
    return problems


_SLOT = re.compile(r"\{([^{}]+)\}")


def _check_day_contracts(season: Season, gap: Gap, *, locations: set[str] | None) -> list[str]:
    """A gap's day contracts: places the season has, hooks that lead into the next day,
    marks that come back later and nowhere else, facts named once."""

    problems: list[str] = []
    order = [segment.id for segment in season.segments]
    after = order[order.index(gap.id) + 1 :] if gap.id in order else []
    following = after[0] if after else None
    by_day: dict[int, set[str]] = {}
    for beat in gap.days:
        by_day.setdefault(beat.day, set()).add(beat.premise)
    last = max(by_day, default=0)
    if gap.destination and gap.destination.tentpole != following:
        problems.append(f"{gap.id}: destination {gap.destination.tentpole!r} is not the tentpole that follows")
    speakers = season.speaker_ids()
    seen: set[str] = set()
    for beat in gap.days:
        contract = beat.contract
        if contract is None:
            continue
        where = f"{gap.id}.{beat.day} {beat.premise!r}"
        for place in (contract.place, contract.place_alt):
            if place and locations is not None and place not in locations:
                problems.append(f"{where}: place {place!r} is not a place of the season")
        if contract.place_alt == contract.place:
            problems.append(f"{where}: place_alt repeats place")
        for row in [*contract.lands, *([contract.mark] if contract.mark else [])]:
            if not row.id.startswith(f"{gap.id}."):
                problems.append(f"{where}: {row.id!r} does not carry the gap's id")
            if row.id in seen:
                problems.append(f"{where}: {row.id!r} is named twice in the gap")
            seen.add(row.id)
        for turn in contract.turns:
            unknown = set(turn.ask) - set(LEVEL_FIELDS)
            if unknown or "a1" not in turn.ask:
                problems.append(f"{where}: turn {turn.id!r} asks need 'a1' and only written levels")
        if contract.hook.speaker not in speakers:
            problems.append(f"{where}: hook speaker {contract.hook.speaker!r} is not in the cast")
        leads = by_day.get(beat.day + 1) or ({following} if beat.day >= last and following else set())
        if contract.hook.about not in leads:
            problems.append(f"{where}: the hook is about {contract.hook.about!r}, not what comes next {sorted(leads)}")
        for field in LEVEL_FIELDS:
            line = getattr(contract.hook.fr, field, None)
            missing = [word for word in contract.hook.must_name if line and word.casefold() not in line.casefold()]
            if missing:
                problems.append(f"{where}: hook {field} does not name {missing}")
        mark = contract.mark
        if mark:
            for target in mark.comes_back:
                later_day = re.fullmatch(rf"{gap.id}\.(\d+)", target)
                if not ((later_day and beat.day < int(later_day.group(1)) <= last) or target in after):
                    problems.append(f"{where}: mark {mark.id!r} comes back at {target!r}, which is not later")
            if not mark.comes_back:
                problems.append(f"{where}: mark {mark.id!r} comes back nowhere")
            if not mark.what.strip():
                problems.append(f"{where}: mark {mark.id!r} does not say what it is")
        allowed = {mark.id} if mark else set()
        for field in LEVEL_FIELDS:
            loose = set(_SLOT.findall(getattr(contract.after_fr, field, None) or "")) - allowed
            if loose:
                problems.append(f"{where}: after_fr {field} has slots {sorted(loose)} the day does not fill")
        # The ending the learner reads in their own language: «what changed», translated.
        for language in ("en", "de"):
            if not contract.after_fr.native.get(language):
                problems.append(f"{where}: after_fr has no {language} translation")
            if contract.after_fr.a1 and not contract.after_fr.native_a1.get(language):
                problems.append(f"{where}: after_fr a1 has no {language} translation")
        for texts in (contract.after_fr.native, contract.after_fr.native_a1):
            for language, text in texts.items():
                if set(_SLOT.findall(text)) - allowed:
                    problems.append(f"{where}: after_fr {language} has slots the day does not fill")
        if contract.lead is not None and contract.lead not in {member.id for member in season.cast}:
            problems.append(f"{where}: lead {contract.lead!r} is not in the cast")
        for route in contract.routes:
            if route.line is None:
                continue
            if contract.lead is None:
                problems.append(f"{where}: route {route.id!r} has a line and the day has no lead")
            for field in LEVEL_FIELDS:
                line = getattr(route.line, field, None) or ""
                if set(_SLOT.findall(line)) - allowed:
                    problems.append(f"{where}: route {route.id!r} {field} has slots the day does not fill")
                # The bubble has no reply box after it: it never ends on a question.
                if line.rstrip().endswith("?"):
                    problems.append(f"{where}: route {route.id!r} {field} ends on a question")
        problems.extend(_check_stand_in(season, gap, contract, where))
    return problems


def _check_stand_in(season: Season, gap: Gap, contract: DayContract, where: str) -> list[str]:
    """A stand-in page: somebody asks, every reader has their language, no slot is
    left open and no line makes a reveal the gap forbids."""

    page = contract.stand_in
    if page is None:
        return []
    problems: list[str] = []
    if contract.lead is None:
        problems.append(f"{where}: a stand-in page needs a lead to ask the learner")
    french: list[str] = []
    if page.alt_panels and not contract.place_alt:
        problems.append(f"{where}: stand-in alt_panels without a place_alt")
    lines = [
        *((f"panel {i + 1}", row.text) for i, row in enumerate(page.panels)),
        *((f"alt panel {i + 1}", row.text) for i, row in enumerate(page.alt_panels or [])),
        ("asks", page.asks),
    ]
    for label, wording in lines:
        french.extend(text for field in LEVEL_FIELDS if (text := getattr(wording, field, None)))
        for language in ("en", "de"):
            if not wording.native.get(language):
                problems.append(f"{where}: stand-in {label} has no {language} translation")
            if wording.a1 and not _same(wording.a1, wording.a2) and not wording.native_a1.get(language):
                problems.append(f"{where}: stand-in {label} a1 has no {language} translation")
    for label, rows in (("task", page.task), ("reply_fr", page.reply_fr)):
        if set(rows) - set(LEVEL_FIELDS):
            problems.append(f"{where}: stand-in {label} names a level nobody reads")
    if "a1" not in page.task or any(not row.get(language) for row in page.task.values() for language in ("de", "fr")):
        problems.append(f"{where}: stand-in task needs 'a1', and German and French at every level")
    if "a2" not in page.reply_fr:
        problems.append(f"{where}: stand-in reply_fr needs 'a2'")
    french.extend(page.reply_fr.values())
    everything = [
        *french,
        *(text for _label, wording in lines for texts in (wording.native, wording.native_a1) for text in texts.values()),
        *(text for row in page.task.values() for text in row.values()),
    ]
    if any(_SLOT.search(text) for text in everything):
        problems.append(f"{where}: a stand-in page carries no slot")
    from app.services.season.director import _must_not, pattern_hits

    # Every row, whatever the life has learned: the page is the same for everybody.
    for row_id, matched in pattern_hits(_must_not(gap, season, {}), french):
        problems.append(f"{where}: stand-in says {matched!r}, which {row_id!r} forbids")
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
        problems.extend(_check_day_plan(season, gap, premise_ids))
        problems.extend(_check_day_contracts(season, gap, locations=locations))
        for premise in gap.premises:
            unknown = cond_flags(premise.when) - known_flags
            if unknown:
                problems.append(f"{gap.id}: premise {premise.id} when names unknown {sorted(unknown)}")
            loose = set(premise.settles) - (set(premise.sets) & set(gap.sets_allowed))
            if loose:
                problems.append(f"{gap.id}: premise {premise.id} settles {sorted(loose)} it may not set")
        for forbidden in gap.must_not:
            unknown = cond_flags(forbidden.unless) - known_flags
            if unknown:
                problems.append(f"{gap.id}: must_not {forbidden.id} unless names unknown {sorted(unknown)}")
    for tentpole in season.tentpoles.values():
        problems.extend(_check_tentpole(season, tentpole, locations=locations))
        for forbidden in tentpole.reveals:
            unknown = cond_flags(forbidden.unless) - known_flags
            if unknown:
                problems.append(f"{tentpole.id}: reveal {forbidden.id} unless names unknown {sorted(unknown)}")
    return problems


@lru_cache(maxsize=4)
def load_season(season_id: str, *, root: Path | None = None) -> Season:
    """The season in ``app/data/season/<season_id>/``, validated. Cached."""

    folder = (root or SEASON_ROOT) / season_id
    if not folder.is_dir():
        raise SeasonFormatError(f"no season folder {folder}")
    from app.services.season.levels import apply_levels, apply_tasks, read_levels, read_tasks

    levels = read_levels(folder)
    tasks = read_tasks(folder)
    season = Season.model_validate(apply_levels(_read(folder / "season.json"), levels, file_id="season"))
    tentpoles: dict[str, Tentpole] = {}
    for segment in season.segments:
        if segment.kind != "tentpole":
            continue
        path = folder / f"{segment.id}.json"
        if path.is_file():
            tentpoles[segment.id] = Tentpole.model_validate(
                apply_tasks(apply_levels(_read(path), levels, file_id=segment.id), tasks, file_id=segment.id)
            )
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
    # WP-132B: the authored epilogue week after the finale, when the season has a whole one.
    from app.services.season.epilogue import attach_epilogue

    season = attach_epilogue(season, folder, levels=levels, tasks=tasks)
    problems = validate_season(season)
    if problems:
        raise SeasonFormatError(f"season {season_id}: " + "; ".join(problems[:12]))
    return season


def available_seasons(root: Path | None = None) -> list[str]:
    base = root or SEASON_ROOT
    if not base.is_dir():
        return []
    return sorted(path.name for path in base.iterdir() if (path / "season.json").is_file())
