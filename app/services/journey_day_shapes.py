"""WP-66 — the dice that make one day differ from the next.

Before this package every journey was the same template with different words in
it: day 1, day 10 and day 40 were one shape (scene → ≤2 recall → 1 respond →
resolution) and three recall formats, while eight richer formats sat unused in
the off-day Séance.

This module is the *decision* half of the fix, kept apart from
:mod:`app.services.journey_planner` (which shapes the steps) and from
:mod:`app.services.daily_journey` (which owns the transaction) so that the
choice can be replayed in a test with nothing but a user id and a date.

Three rules govern everything here:

1. **Seeded, not random.** Every choice is a SHA-256 over
   ``user_id : iso_week : …`` — per learner, per week, reproducible, and never
   a fixed catalogue rotation. Two learners on the same day get different days;
   the same learner refreshing the same day gets the same day.
2. **No two identical shapes on consecutive days**, whenever an alternative is
   eligible at all. When nothing else is eligible — no audio on the deployment,
   nothing in the errata queue, no Courrier letter — the honest answer is a
   second standard day, and the decision says so in ``reason``.
3. **The story leads.** A chapter's resolution beat deals «jour de reprise»
   and a missed day deals «jour court» before the dice are consulted at all.
"""
from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.journey_contracts import (
    DEFAULT_DAY_SHAPE,
    DESK_KINDS,
    DICTATION_RECALL_FORMATS,
    DayShape,
    RecallFormat,
    TargetKind,
)

DAY_SHAPE_DICE_VERSION = "journey-day-shapes-v1"

#: Unit separator; keeps a hashed seed injection-proof across its parts.
_SEPARATOR = chr(31)

#: Chapter beats that close a chapter. A day dealt on one of these is the day
#: the learner looks back: errata first, and the ending carries the recap.
RESOLUTION_BEATS: frozenset[str] = frozenset({"resolution", "resolve", "payoff", "close"})

#: Relative weights for the *unforced* draw. Standard is the heaviest because
#: it is the shape the content is authored for, but deliberately not heavy
#: enough to own half the month: with three alternatives eligible it takes
#: 4/13 of the draws, and the no-repeat rule pushes it lower still.
SHAPE_WEIGHTS: dict[DayShape, int] = {
    DayShape.STANDARD: 4,
    DayShape.LISTENING: 3,
    DayShape.REPRISE: 3,
    DayShape.LETTER: 3,
}

#: Which formats each target kind is posed in *first*, before the dice break the
#: remaining tie. A mistake wants the rewrite that repairs it; a grammar concept
#: wants the contrast that names it; a word wants to be built and recognised.
FORMAT_BIAS: dict[str, tuple[str, ...]] = {
    str(TargetKind.ERROR): (
        str(RecallFormat.TRANSFORM),
        str(RecallFormat.TILES),
        str(RecallFormat.SHORT_ANSWER),
    ),
    str(TargetKind.GRAMMAR): (
        str(RecallFormat.CLASSIFY),
        str(RecallFormat.TRANSFORM),
        str(RecallFormat.WORD_BANK),
    ),
    str(TargetKind.VOCABULARY): (
        str(RecallFormat.WORD_BANK),
        str(RecallFormat.CHOICE),
        str(RecallFormat.CLASSIFY),
    ),
}


# --------------------------------------------------------------------------
# Seeded dice
# --------------------------------------------------------------------------


def iso_week_key(day: date) -> str:
    """``"2026-W38"`` — the week the dice are dealt for."""

    year, week, _weekday = day.isocalendar()
    return f"{year}-W{week:02d}"


def seed_digest(*parts: Any) -> str:
    """The hex digest for one seeded decision."""

    joined = _SEPARATOR.join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def roll(*parts: Any, faces: int) -> int:
    """``0..faces-1`` from a stable seed. ``faces <= 1`` always rolls zero."""

    if faces <= 1:
        return 0
    return int(seed_digest(*parts), 16) % faces


def weighted_choice(options: list[tuple[Any, int]], *parts: Any) -> Any | None:
    """Pick one weighted option with the seeded dice, or ``None`` when empty.

    Options are sorted by their own string form first, so the caller's list
    order can never change the outcome: the draw is a property of the seed and
    the eligible set, not of how the set was assembled.
    """

    pool = [(value, max(1, int(weight))) for value, weight in options if weight > 0]
    if not pool:
        return None
    pool.sort(key=lambda row: str(row[0]))
    total = sum(weight for _value, weight in pool)
    cursor = roll(*parts, faces=total)
    for value, weight in pool:
        if cursor < weight:
            return value
        cursor -= weight
    return pool[-1][0]  # pragma: no cover - the loop above is exhaustive


# --------------------------------------------------------------------------
# The WP-64 seam: a Courrier letter as the day's response step
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LetterOffer:
    """One Courrier letter, ready to become today's respond step.

    Deliberately a flat value object with no mission model in it: WP-64 owns
    ``missions.py`` and this package must not import it. A provider hands over
    exactly these six strings, and everything else about the mission stays on
    WP-64's side of the seam.
    """

    mission_id: str
    correspondent_id: str
    correspondent_name: str
    subject_fr: str
    body_fr: str
    objective_native: str

    def is_renderable(self) -> bool:
        """A letter with no sender or no body is not a letter."""

        return bool(
            (self.correspondent_name or "").strip()
            and (self.body_fr or "").strip()
            and (self.objective_native or "").strip()
        )


#: A callable ``(*, user_id: str, local_date: date) -> LetterOffer | None``.
LetterProvider = Callable[..., "LetterOffer | None"]

_LETTER_PROVIDER: LetterProvider | None = None


def set_letter_provider(provider: LetterProvider | None) -> None:
    """Register (or clear) the Courrier seam. **This is the whole seam.**

    WP-64 — «Le Courrier vit dans l'histoire» — is in flight in a package that
    owns ``missions.py``, which this one may not touch. So «jour de lettre»
    ships as a contract and a planner option that is *off* until somebody
    registers a provider here, and a test registers a stub to exercise the
    shape end to end. Nothing else in this codebase has to change when the real
    provider arrives: it is one call at wiring time.
    """

    global _LETTER_PROVIDER
    _LETTER_PROVIDER = provider


def _accepts_db(provider: LetterProvider) -> bool:
    """Would this provider take a session if it were offered one?"""

    try:
        parameters = inspect.signature(provider).parameters
    except (TypeError, ValueError):  # pragma: no cover - exotic callables
        return False
    return "db" in parameters or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


def letter_offer_for(
    *, user_id: str, local_date: date, db: Any | None = None
) -> LetterOffer | None:
    """Today's Courrier letter for this learner, or ``None``.

    ``None`` is not a failure: the shape is simply not eligible, and the dice
    deal one of the other four. A provider that raises costs the shape, never
    the day.

    ``db`` is offered and dropped rather than forced. The real provider reads the
    letter out of the session the caller is already inside — opening a second one
    to answer a question about the day's shape would be a transaction the
    learner's day does not need — while a provider written against WP-66's
    original two-argument signature (the stub in `test_journey_planner.py`, an
    older deployment's) still gets called exactly as it was.
    """

    provider = _LETTER_PROVIDER
    if provider is None:
        return None
    extra: dict[str, Any] = {}
    if db is not None and _accepts_db(provider):
        extra["db"] = db
    try:
        offer = provider(user_id=str(user_id), local_date=local_date, **extra)
    except Exception:  # pragma: no cover - a letter is never worth the day
        return None
    if offer is None or not isinstance(offer, LetterOffer) or not offer.is_renderable():
        return None
    return offer


# --------------------------------------------------------------------------
# The decision
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DayShapeInputs:
    """Everything the dice are allowed to know.

    All of it is cheap and already at hand where the plan is built: the shape
    must never cost a provider call, a second content source, or a query the
    day would not otherwise run.
    """

    user_id: str
    local_date: date
    #: What yesterday's plan was, so today is not the same object again.
    previous_shape: DayShape | None = None
    #: ``True`` when the learner has no journey for the previous local day.
    missed_previous_day: bool = False
    #: The living story's beat for this scene, when there is one.
    chapter_beat: str | None = None
    #: WP-63's chapter *shape*, when the story engine has dealt one. The only
    #: value this package acts on is ``"letter"`` — a chapter whose turn beat is
    #: a letter. Everything else is a chapter shape, not a day shape, and is
    #: deliberately ignored here rather than half-honoured.
    chapter_shape: str | None = None
    #: Whether this deployment can actually speak the scene.
    audio_available: bool = False
    #: How many due mistakes the errata queue holds.
    errata_count: int = 0
    #: The WP-64 seam's answer for today. ``None`` disables «jour de lettre».
    letter: LetterOffer | None = None
    #: WP-78. The shape the dice dealt yesterday when the planner could not
    #: build it and served a standard day instead (``None`` otherwise). Not
    #: part of the seed: it only removes a shape that just failed to build.
    previous_dealt_shape: DayShape | None = None
    #: WP-91. The day's budget (the learner's rhythm). Soutenu and Intensif
    #: (≥ :data:`LISTEN_FIRST_MIN_BUDGET_SECONDS`) hear every third day first.
    #: ``None`` — an older caller — deals no cadence at all.
    budget_seconds: int | None = None
    #: WP-119 phase 3. Le Papier is on and this week's kiosk has a story.
    revue_available: bool = False
    #: WP-119 phase 3. A Papier day was already dealt this ISO week.
    revue_dealt_this_week: bool = False
    #: WP-111 / WP-119. Today's story day is a season tentpole (served as written).
    tentpole: bool = False

    @property
    def seed_parts(self) -> tuple[str, ...]:
        return (
            DAY_SHAPE_DICE_VERSION,
            str(self.user_id),
            iso_week_key(self.local_date),
        )


@dataclass(frozen=True, slots=True)
class DayShapeDecision:
    """The shape, why it was dealt, and what it was dealt against."""

    shape: DayShape
    reason: str
    eligible: tuple[DayShape, ...] = field(default=())

    @property
    def is_forced(self) -> bool:
        """Did the story or a missed day decide this before the dice did?"""

        return self.reason in {"missed_previous_day", "chapter_resolution_beat"}


#: WP-91. Soutenu (20 min) and Intensif (30 min): every third day is
#: «Écouter d'abord» — a listening day — when the deployment can speak.
LISTEN_FIRST_MIN_BUDGET_SECONDS = 1200
LISTEN_FIRST_EVERY_DAYS = 3


def is_listen_first_day(inputs: DayShapeInputs) -> bool:
    """Is today one of this learner's every-third listening days?

    The phase is per learner (seeded on the user id alone, so it does not jump
    at a week boundary), the rhythm is the calendar: three consecutive days
    always hold exactly one. Only on the long rhythms, and only when audio is on.
    """

    if not inputs.audio_available:
        return False
    if int(inputs.budget_seconds or 0) < LISTEN_FIRST_MIN_BUDGET_SECONDS:
        return False
    phase = roll(
        DAY_SHAPE_DICE_VERSION, str(inputs.user_id), "listen-first-phase",
        faces=LISTEN_FIRST_EVERY_DAYS,
    )
    return (inputs.local_date.toordinal() + phase) % LISTEN_FIRST_EVERY_DAYS == 0


#: WP-119 phase 3: the Papier day falls on this learner's weekday of the week
#: (seeded, Monday..Friday) or the first story day after it that may hold it, so a
#: tentpole or a missed day moves it later in the week instead of skipping the week.
REVUE_WEEKDAYS = 5


def revue_weekday(inputs: DayShapeInputs) -> int:
    """This learner's Papier weekday this week (0 = Monday … 4 = Friday)."""

    return roll(*inputs.seed_parts, "revue-day", faces=REVUE_WEEKDAYS)


def is_revue_day(inputs: DayShapeInputs) -> bool:
    """Deal «jour du Papier» today? Once a week, on or after the seeded weekday, never
    on a tentpole, only while the Papier is on and has a story for the week."""

    if not inputs.revue_available or inputs.revue_dealt_this_week or inputs.tentpole:
        return False
    return inputs.local_date.weekday() >= revue_weekday(inputs)


def eligible_shapes(inputs: DayShapeInputs) -> tuple[DayShape, ...]:
    """The shapes today could honestly be, before the no-repeat rule.

    A shape is eligible only when the thing it is made of exists: no audio, no
    listening day; nothing due, no reprise; no letter, no letter day. Offering a
    shape the deployment cannot fill would be the phantom-loop mistake.
    """

    shapes = [DayShape.STANDARD]
    if inputs.audio_available:
        shapes.append(DayShape.LISTENING)
    if inputs.errata_count >= 1:
        shapes.append(DayShape.REPRISE)
    if inputs.letter is not None and inputs.letter.is_renderable():
        shapes.append(DayShape.LETTER)
    if is_revue_day(inputs):
        shapes.append(DayShape.REVUE)
    return tuple(shapes)


def choose_day_shape(inputs: DayShapeInputs) -> DayShapeDecision:
    """Deal today's shape.

    Order matters and is deliberate:

    1. A missed day deals «jour court» — unless yesterday was already short,
       because two three-step days in a row is a shrinking product, not a
       gentle one.
    2. A chapter the story engine dealt as a **letter chapter** (WP-63) deals
       «jour de lettre», when a letter is actually waiting. The story said this
       chapter's turn is a letter; the day should not then argue with it.
    3. A chapter's resolution beat deals «jour de reprise» — unless yesterday
       was already one.
    4. Otherwise the seeded dice draw from the eligible set with yesterday's
       shape removed.
    """

    pool = eligible_shapes(inputs)
    previous = inputs.previous_shape

    if inputs.missed_previous_day and previous is not DayShape.SHORT:
        return DayShapeDecision(
            shape=DayShape.SHORT, reason="missed_previous_day", eligible=pool
        )
    if (
        (inputs.chapter_shape or "").strip().lower() == str(DayShape.LETTER)
        # …and yesterday was not already a letter day. Rule 2 above binds the
        # story's overrides too: the resolution beat has always deferred to it
        # and this branch did not, so two letter chapters back to back — or one
        # chapter whose letter beat lands the morning after a letter day the
        # dice dealt — put the learner in front of two identical days (WP-68).
        and previous is not DayShape.LETTER
    ):
        # Defensive on purpose: WP-63 is in flight and the key may not exist
        # yet. When it does, a letter chapter without a letter still cannot be
        # a letter day — the pool is the honest floor under every rule here.
        if DayShape.LETTER in pool:
            return DayShapeDecision(
                shape=DayShape.LETTER, reason="chapter_letter_shape", eligible=pool
            )
    beat = (inputs.chapter_beat or "").strip().lower()
    if beat in RESOLUTION_BEATS and previous is not DayShape.REPRISE:
        # A reprise needs something to revisit; without it the beat still
        # matters but the day cannot honestly be errata-led.
        if DayShape.REPRISE in pool:
            return DayShapeDecision(
                shape=DayShape.REPRISE, reason="chapter_resolution_beat", eligible=pool
            )

    if DayShape.REVUE in pool and previous is not DayShape.REVUE:
        # WP-119 phase 3: the week's Papier day, once the seeded weekday has come.
        # After the story's own overrides (a missed day, a letter chapter, a
        # resolution beat); before the listening cadence and the dice.
        return DayShapeDecision(shape=DayShape.REVUE, reason="revue_weekly", eligible=pool)

    if (
        is_listen_first_day(inputs)
        and DayShape.LISTENING in pool
        and previous is not DayShape.LISTENING
    ):
        # WP-91: the long rhythms' cadence. After the story's own overrides
        # (a missed day, a letter chapter, a resolution beat), before the dice.
        return DayShapeDecision(
            shape=DayShape.LISTENING, reason="listen_first_cadence", eligible=pool
        )

    # The Papier day is dealt by its own rule above, never drawn by the dice.
    pool = tuple(shape for shape in pool if shape is not DayShape.REVUE)
    unrepeated = tuple(shape for shape in pool if shape is not previous)
    # WP-78 (the WP-68 finding): a shape dealt yesterday that could not be
    # built was served as a standard day, so excluding only *standard* dealt
    # the failed shape again and again. It sits out today too. When nothing
    # else is left, yesterday's *served* standard day may come again (it was
    # served in place of the failed shape, so it is not the dice repeating a
    # deal) before the shape that just failed is dealt again.
    failed = inputs.previous_dealt_shape
    untried = tuple(shape for shape in unrepeated if shape is not failed)
    not_failed = tuple(shape for shape in pool if shape is not failed) if failed else ()
    drawn_from = untried or not_failed or unrepeated or pool
    choice = weighted_choice(
        [(shape, SHAPE_WEIGHTS.get(shape, 1)) for shape in drawn_from],
        *inputs.seed_parts,
        inputs.local_date.isoformat(),
        "shape",
    )
    if choice is None:  # pragma: no cover - the pool always holds STANDARD
        return DayShapeDecision(
            shape=DEFAULT_DAY_SHAPE, reason="no_shape_eligible", eligible=pool
        )
    reason = "seeded_dice" if unrepeated else "seeded_dice_no_alternative"
    return DayShapeDecision(shape=choice, reason=reason, eligible=pool)


# --------------------------------------------------------------------------
# «Le bureau»: the Revue's other desks as an optional step (WP-121/122)
# --------------------------------------------------------------------------

#: The shapes a desk step may be dealt on: the ordinary days. Never the Papier
#: day (the Papier is that day's second half), never «jour court» (three steps,
#: coming back after a missed day costs a scene and a reply, nothing more).
DESK_SHAPES: frozenset[DayShape] = frozenset(
    {DayShape.STANDARD, DayShape.LISTENING, DayShape.REPRISE, DayShape.LETTER}
)
#: Each desk's seeded weekday is Monday..Friday, so a desk whose day was a
#: tentpole, a Papier day or a missed day still has the weekend to land on.
DESK_WEEKDAYS = 5


def desk_weekday(inputs: DayShapeInputs, desk: str) -> int:
    """This learner's weekday for ``desk`` this week (0 = Monday … 4 = Friday)."""

    return roll(*inputs.seed_parts, "desk", str(desk), faces=DESK_WEEKDAYS)


def due_desks(
    inputs: DayShapeInputs,
    *,
    shape: DayShape | str,
    dealt_this_week: set[str] | frozenset[str] | tuple[str, ...] = (),
) -> tuple[str, ...]:
    """The desks today *may* deal, in the order they are tried.

    * only on an ordinary day (:data:`DESK_SHAPES`) and never on a season
      tentpole (nor on the Papier day: ``REVUE`` is not in :data:`DESK_SHAPES`);
    * each desk at most once an ISO week (``dealt_this_week``), on or after its
      own seeded weekday, so the three spread over the week rather than piling
      onto Monday; a desk whose day passed without it (a tentpole, the Papier,
      no offer that day) waits for the next ordinary day of the week;
    * ordered by whose weekday came first, then :data:`DESK_KINDS`.

    Whether a desk has anything to offer (its flag, its offer) is the caller's
    question: :func:`choose_desk` takes the first one that does.
    """

    try:
        day_shape = DayShape(str(shape))
    except ValueError:
        return ()
    if inputs.tentpole or day_shape not in DESK_SHAPES:
        return ()
    dealt = {str(desk) for desk in dealt_this_week}
    weekday = inputs.local_date.weekday()
    due = sorted(
        (desk_weekday(inputs, desk), DESK_KINDS.index(desk), desk)
        for desk in DESK_KINDS
        if desk not in dealt and weekday >= desk_weekday(inputs, desk)
    )
    return tuple(desk for _weekday, _rank, desk in due)


def choose_desk(
    inputs: DayShapeInputs,
    *,
    shape: DayShape | str,
    offered: Callable[[str], bool] | set[str] | frozenset[str] | tuple[str, ...],
    dealt_this_week: set[str] | frozenset[str] | tuple[str, ...] = (),
) -> str | None:
    """Which desk (``relecture`` · ``radio`` · ``correcteur``) today deals, or ``None``.

    The first of :func:`due_desks` whose flag is on and whose offer is
    non-empty — ``offered`` is that set, or a predicate asked lazily in order so
    a desk that is not due never costs a query. At most one desk a day.
    """

    has = offered if callable(offered) else (lambda desk, pool=frozenset(offered): desk in pool)
    for desk in due_desks(inputs, shape=shape, dealt_this_week=dealt_this_week):
        if has(desk):
            return desk
    return None


# --------------------------------------------------------------------------
# Format rotation
# --------------------------------------------------------------------------


def shape_allows_format(shape: DayShape, task_type: str) -> bool:
    """May this shape pose this recall format?

    Only the listening day restricts it, and only to what can be taken down by
    ear. Everything else is the dice's business, not the shape's.
    """

    if shape is DayShape.LISTENING:
        return str(task_type) in DICTATION_RECALL_FORMATS
    return True


def rotate_recall_formats(
    *,
    inputs: DayShapeInputs,
    shape: DayShape,
    target_kind: str,
    target_id: str,
    eligible: list[str] | tuple[str, ...],
) -> list[str]:
    """The order in which formats are *tried* for one target today.

    Two forces, in this order:

    * **the target type** — a mistake is posed as the rewrite that repairs it
      before it is posed as a word puzzle (:data:`FORMAT_BIAS`);
    * **the seeded dice** — everything the bias does not rank is ordered by the
      same per-learner-per-week seed, so two learners meet the same word in
      different forms and the same learner does not meet it the same way every
      week.

    The planner walks this list and takes the first format that can be posed
    *without revealing the answer*; a list where nothing can is a target with no
    recall step, never a fake one.
    """

    bias = FORMAT_BIAS.get(str(target_kind), ())
    allowed = [
        task_type
        for task_type in eligible
        if shape_allows_format(shape, task_type)
    ]

    def sort_key(task_type: str) -> tuple[int, str]:
        rank = bias.index(task_type) if task_type in bias else len(bias)
        return (
            rank,
            seed_digest(*inputs.seed_parts, str(target_id), task_type, "format"),
        )

    return sorted(allowed, key=sort_key)


__all__ = [
    "DAY_SHAPE_DICE_VERSION",
    "FORMAT_BIAS",
    "RESOLUTION_BEATS",
    "SHAPE_WEIGHTS",
    "DayShapeDecision",
    "DayShapeInputs",
    "LetterOffer",
    "LetterProvider",
    "LISTEN_FIRST_EVERY_DAYS",
    "LISTEN_FIRST_MIN_BUDGET_SECONDS",
    "choose_day_shape",
    "choose_desk",
    "DESK_SHAPES",
    "DESK_WEEKDAYS",
    "desk_weekday",
    "due_desks",
    "eligible_shapes",
    "is_listen_first_day",
    "is_revue_day",
    "REVUE_WEEKDAYS",
    "revue_weekday",
    "iso_week_key",
    "letter_offer_for",
    "roll",
    "rotate_recall_formats",
    "seed_digest",
    "set_letter_provider",
    "shape_allows_format",
    "weighted_choice",
]
