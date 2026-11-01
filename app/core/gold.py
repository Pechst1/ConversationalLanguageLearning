"""Package O-1 — l'or: the mint table and its rules (rule version ``gold-v1``).

One pure function holds the table, so the ledger service, the tests and the
calibration simulation run the same code, the way :mod:`app.core.forge` serves
both the séance and its simulation. Nothing here reads the database or the
clock: the caller hands in the observation and the day as the ledger has it.

``docs/ATELIER_GOLD_ECONOMY_PLAN.md`` §4 is the source:

* **§4.1 base values**, in feuilles: recognised 1, typed recall 2, guided
  production 3, free production 5, a Courrier letter 8, a repair 1.
* **R1 le meilleur du jour.** A target pays once a local day, at its best
  evidence; a better evidence later the same day pays the difference. A *unit*
  (a reply turn, a letter) pays as itself and lifts the day's best of every
  target it shows to its own value, so one sentence is never paid twice.
* **R2 aide.** None ×1, hint ×½, translation ×½, suggested response 0,
  solution 0.
* **R3 partiel.** Partly met, or an accent slip, pays half; production that
  pays anything pays at least 1.
* **R4 rappel différé ×2.** A correct, unaided spaced item (recognised or typed)
  answered at least 20 hours after the learner's last contact with the target.
* **R5 posé en dessous ×½.** An item posed below the rule's level.
* **R6 vérifié seulement.** An unchecked verdict mints *pending*; ``not_yet``
  and ``unscored`` pay nothing. Never negative.
* **R7 premier essai.** The first submission only, except the repair step.
* **R8 le plafond du jour.** Counted on the day's earned gold before the
  plafond: full rate up to 90, half rate from 90 to 150, nothing past 150, so a
  day never pays more than 120. Milestones and bonuses sit outside it.

The factors multiply as exact fractions and the product rounds down once, so
their order never matters (a recognised item answered after a long gap, posed
below its level, is 1 × 2 × ½ = 1, not 0).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from fractions import Fraction
from math import floor
from typing import Any
from zoneinfo import ZoneInfo

RULE_VERSION = "gold-v1"

# ---------------------------------------------------------------------------
# §4.1 — the table
# ---------------------------------------------------------------------------


class Category(StrEnum):
    """What one piece of evidence proves, from the server's records alone."""

    RECOGNISED = "recognised"
    TYPED = "typed"
    GUIDED = "guided"
    FREE = "free"
    LETTER = "letter"
    REPAIR = "repair"


BASE_VALUE: dict[Category, int] = {
    Category.RECOGNISED: 1,
    Category.TYPED: 2,
    Category.GUIDED: 3,
    Category.FREE: 5,
    Category.LETTER: 8,
    Category.REPAIR: 1,
}

#: R4 doubles a *spaced item*: a recognition or a typed recall, never a reply.
SPACED_CATEGORIES = frozenset({Category.RECOGNISED, Category.TYPED})
#: R3: production that pays anything pays at least one feuille.
PRODUCTION_CATEGORIES = frozenset({Category.GUIDED, Category.FREE, Category.LETTER})

#: R2, keyed by ``journey_contracts.AssistanceLevel`` values. An assistance the
#: table does not know pays nothing: help nobody can name is not «none».
ASSISTANCE_FACTOR: dict[str, Fraction] = {
    "none": Fraction(1),
    "hint": Fraction(1, 2),
    "translation": Fraction(1, 2),
    "suggested_response": Fraction(0),
    "solution": Fraction(0),
}

#: The recall formats of the journey and the Atelier, by what they prove. The
#: spec's table (§4.1) lists the journey's; the rest are their Atelier names.
#: An unknown format pays as recognition, the lowest rank, never more.
FORMAT_CATEGORY: dict[str, Category] = {
    # A pick, a pairing, or an order of pieces the screen gives.
    "choice": Category.RECOGNISED,
    "multiple_choice": Category.RECOGNISED,
    "who_said": Category.RECOGNISED,
    "listen_tap": Category.RECOGNISED,
    "match_pairs": Category.RECOGNISED,
    "classify": Category.RECOGNISED,
    "tiles": Category.RECOGNISED,
    "word_bank": Category.RECOGNISED,
    "unscramble": Category.RECOGNISED,
    "fill": Category.RECOGNISED,
    "recognise": Category.RECOGNISED,
    "recognize": Category.RECOGNISED,
    "discriminate": Category.RECOGNISED,
    "build": Category.RECOGNISED,
    # The form typed from memory.
    "short_answer": Category.TYPED,
    "transform": Category.TYPED,
    "dictation": Category.TYPED,
    # The learner's own sentence, with the rule (and often a frame) given.
    "sentence": Category.GUIDED,
    "produce": Category.GUIDED,
    "speak": Category.GUIDED,
    # The learner's own line in a situation.
    "conversation": Category.FREE,
    "reply": Category.FREE,
    "free_use": Category.FREE,
}

#: La Forge's staircase (``core.forge.Rung``): recognise, discriminate and build
#: are recognition; transform is typed recall; produce is guided production (a
#: model and a frame are given); free_use is the learner's own line.
RUNG_CATEGORY: dict[int, Category] = {
    0: Category.RECOGNISED,
    1: Category.RECOGNISED,
    2: Category.RECOGNISED,
    3: Category.TYPED,
    4: Category.GUIDED,
    5: Category.FREE,
}

#: The French label of each category, the start of an entry's reason line.
CATEGORY_LABEL_FR: dict[Category, str] = {
    Category.RECOGNISED: "Reconnu",
    Category.TYPED: "Rappel écrit",
    Category.GUIDED: "Production guidée",
    Category.FREE: "Production libre",
    Category.LETTER: "Lettre acceptée",
    Category.REPAIR: "Réparation",
}


def category_for_format(name: str | None) -> Category:
    """The category of a recall format; an unknown one pays as recognition."""

    return FORMAT_CATEGORY.get(str(name or "").strip().lower(), Category.RECOGNISED)


def category_for_rung(rung: int | None) -> Category:
    """The category of a Forge rung (clamped to the staircase)."""

    try:
        value = int(rung or 0)
    except (TypeError, ValueError):
        value = 0
    return RUNG_CATEGORY[max(0, min(5, value))]


# ---------------------------------------------------------------------------
# Milestones, the bonus and the journée pleine (§4.3, §4.4)
# ---------------------------------------------------------------------------


class Milestone(StrEnum):
    RULE_HELD = "rule_held"
    CAPABILITY_CONFIRMED = "capability_confirmed"
    EPREUVE_PASSED = "epreuve_passed"
    PERFECT_DAY = "perfect_day"


MILESTONE_VALUE: dict[Milestone, int] = {
    Milestone.RULE_HELD: 25,
    Milestone.CAPABILITY_CONFIRMED: 10,
    Milestone.EPREUVE_PASSED: 30,
    Milestone.PERFECT_DAY: 10,
}

MILESTONE_LABEL_FR: dict[Milestone, str] = {
    Milestone.RULE_HELD: "Règle tenue",
    Milestone.CAPABILITY_CONFIRMED: "Capacité confirmée",
    Milestone.EPREUVE_PASSED: "Numéro spécial réussi",
    Milestone.PERFECT_DAY: "Journée parfaite",
}

#: «Joli !»: an unaided reply scored without an erratum that uses the day's
#: unit. At most once a local day; outside the plafond.
JOLI_BONUS = 2
JOLI_LABEL_FR = "Joli !"

#: §4.4: a day is *pleine* when its settled gold reaches the rhythm's mark.
JOURNEE_PLEINE_MARK: dict[str, int] = {
    "leger": 10,
    "regulier": 20,
    "soutenu": 35,
    "intensif": 45,
}

# ---------------------------------------------------------------------------
# §5 and §18 — what the shadow numbers are compared with
# ---------------------------------------------------------------------------

#: §5: the Monte Carlo's median gold a day, by rhythm and learner. Targets for
#: the shadow data to replace, not promises.
CALIBRATION_TARGETS: dict[str, dict[str, int]] = {
    "leger": {"weak": 13, "average": 16, "strong": 20, "strong_week": 100},
    "regulier": {"weak": 24, "average": 30, "strong": 36, "strong_week": 180},
    "soutenu": {"weak": 41, "average": 51, "strong": 60, "strong_week": 300},
    "intensif": {"weak": 52, "average": 66, "strong": 78, "strong_week": 390},
}
#: §18: at least this share of the gold comes from production.
PRODUCTION_SHARE_TARGET = 0.60
#: §18: fewer than this share of the days touch the plafond.
PLAFOND_DAY_SHARE_TARGET = 0.10

# ---------------------------------------------------------------------------
# R8 — le plafond du jour
# ---------------------------------------------------------------------------

PLAFOND_FULL_RATE_UP_TO = 90
PLAFOND_STOPS_AT = 150
#: What a day can pay at most: 90 + (150 − 90) / 2.
DAY_CAP = PLAFOND_FULL_RATE_UP_TO + (PLAFOND_STOPS_AT - PLAFOND_FULL_RATE_UP_TO) // 2


def plafond(earned_today: int) -> int:
    """R8: what a day's earned gold (before the plafond) pays, in total."""

    earned = max(0, int(earned_today))
    if earned <= PLAFOND_FULL_RATE_UP_TO:
        return earned
    return PLAFOND_FULL_RATE_UP_TO + (min(earned, PLAFOND_STOPS_AT) - PLAFOND_FULL_RATE_UP_TO) // 2


def plafond_pays(earned_before: int, earned: int) -> int:
    """R8: what ``earned`` more pays once the day has already earned ``earned_before``."""

    before = max(0, int(earned_before))
    return plafond(before + max(0, int(earned))) - plafond(before)


# ---------------------------------------------------------------------------
# The observation and the day
# ---------------------------------------------------------------------------

OUTCOME_MET = "met"
OUTCOME_PARTIAL = "partially_met"
OUTCOME_NOT_YET = "not_yet"
OUTCOME_UNSCORED = "unscored"
#: R6: only these pay.
PAYING_OUTCOMES = frozenset({OUTCOME_MET, OUTCOME_PARTIAL})

STATE_PENDING = "pending"
STATE_SETTLED = "settled"
STATE_VOID = "void"


def target_key(kind: Any, target_id: Any) -> str:
    """One target's key in :attr:`DayState.best` (``"grammar:12"``)."""

    return f"{kind}:{target_id}"


@dataclass(frozen=True, slots=True)
class GoldObservation:
    """One answer as the mint reads it. Every field is server-recorded."""

    category: Category
    outcome: str = OUTCOME_MET
    #: R2: an ``AssistanceLevel`` value.
    assistance: str = "none"
    #: R6: ``False`` while only a provisional reading exists; the entry is pending.
    checked: bool = True
    #: R3: right, with a forgiven accent slip.
    accent_slip: bool = False
    #: A sentence the app displayed, typed back as one's own (WP-130 B): pays 0.
    copy: bool = False
    #: R4: at least 20 h since the learner's last contact with the target.
    delayed_recall: bool = False
    #: R5: posed below the rule's level.
    below_level: bool = False
    #: R7: the learner's first submission of this item.
    first_attempt: bool = True
    #: R1: the target (``target_key``) this evidence is about; ``None`` for a
    #: unit that pays as itself (a reply turn, a letter, «Qui a dit ça ?»).
    target: str | None = None
    #: R1: the targets a unit shows; their day's best rises to the unit's value.
    lifts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DayState:
    """The learner's local day, as the ledger's live earn entries have it."""

    #: R8: the day's earned gold before the plafond.
    earned: int = 0
    #: R1: the day's best value per target (``target_key``).
    best: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Minted:
    """What one observation mints. ``amount`` can be 0 once the plafond is spent:
    the entry is still written, so the day's best and its earned gold stay true."""

    amount: int
    earned: int
    value: int
    state: str
    breakdown: dict[str, Any]


def _factor_text(factor: Fraction) -> str:
    return str(factor.numerator) if factor.denominator == 1 else f"{factor.numerator}/{factor.denominator}"


def evidence_value(observation: GoldObservation) -> tuple[int, list[dict[str, str]]]:
    """§4.1 × R2–R5: what the evidence is worth, and the factors that made it."""

    product = Fraction(BASE_VALUE[observation.category])
    factors: list[dict[str, str]] = []

    def apply(rule: str, name: str, factor: Fraction) -> None:
        nonlocal product
        product *= factor
        factors.append({"rule": rule, "name": name, "factor": _factor_text(factor)})

    assistance = str(observation.assistance or "none")
    help_factor = ASSISTANCE_FACTOR.get(assistance, Fraction(0))
    if help_factor != 1:
        apply("R2", f"aide:{assistance}", help_factor)
    partial = observation.outcome == OUTCOME_PARTIAL or observation.accent_slip
    if partial:
        apply("R3", "accent" if observation.accent_slip and observation.outcome != OUTCOME_PARTIAL else "partiel",
              Fraction(1, 2))
    if (
        observation.delayed_recall
        and observation.category in SPACED_CATEGORIES
        and observation.outcome == OUTCOME_MET
        and not partial
        and help_factor == 1
    ):
        apply("R4", "rappel_differe", Fraction(2))
    if observation.below_level:
        apply("R5", "pose_en_dessous", Fraction(1, 2))
    value = floor(product)
    if observation.category in PRODUCTION_CATEGORIES and product > 0 and value < 1:
        value = 1
        factors.append({"rule": "R3", "name": "production_au_moins_1", "factor": "min 1"})
    return value, factors


def reason_fr(category: Category, factors: Iterable[Mapping[str, str]], *, plafond_cut: bool = False) -> str:
    """The entry's one-line explanation, as «D'où vient ton or» will print it (O-2)."""

    parts = [CATEGORY_LABEL_FR[category]]
    for factor in factors:
        name = str(factor.get("name") or "")
        if name.startswith("aide:"):
            parts.append(f"avec aide ×{factor.get('factor')}")
        elif name == "partiel":
            parts.append("en partie ×1/2")
        elif name == "accent":
            parts.append("accent oublié ×1/2")
        elif name == "rappel_differe":
            parts.append("rappel différé ×2")
        elif name == "pose_en_dessous":
            parts.append("posé en dessous ×1/2")
    if plafond_cut:
        parts.append("plafond du jour")
    return " · ".join(parts)


def mint(observation: GoldObservation, day: DayState) -> Minted | None:
    """The table, applied to one observation on the learner's day. ``None``: nothing.

    Pure: the same observation on the same day always mints the same entry.
    """

    if observation.outcome not in PAYING_OUTCOMES:
        return None
    if not observation.first_attempt and observation.category is not Category.REPAIR:
        return None
    if observation.copy:
        return None
    value, factors = evidence_value(observation)
    if value <= 0:
        return None
    best_before = int(day.best.get(observation.target, 0)) if observation.target else 0
    earned = value - best_before
    if earned <= 0:
        # R1: posed again in the same (or a weaker) form today.
        return None
    amount = plafond_pays(day.earned, earned)
    breakdown: dict[str, Any] = {
        "category": str(observation.category),
        "base": BASE_VALUE[observation.category],
        "factors": factors,
        "value": value,
        "best_before": best_before,
        "earned": earned,
        "day_earned_before": int(day.earned),
        "plafond_factor": _factor_text(Fraction(amount, earned)),
        "amount": amount,
        "reason_fr": reason_fr(observation.category, factors, plafond_cut=amount < earned),
    }
    return Minted(
        amount=amount,
        earned=earned,
        value=value,
        state=STATE_SETTLED if observation.checked else STATE_PENDING,
        breakdown=breakdown,
    )


def advance(day: DayState, observation: GoldObservation, minted: Minted | None) -> DayState:
    """The day after one minted observation (a simulation's running day)."""

    if minted is None:
        return day
    best = dict(day.best)
    for key in ([observation.target] if observation.target else []) + list(observation.lifts):
        best[key] = max(int(best.get(key, 0)), minted.value)
    return DayState(earned=int(day.earned) + minted.earned, best=best)


def resettle(breakdown: Mapping[str, Any], observation: GoldObservation) -> Minted | None:
    """A pending entry's final verdict landed (R6): its value, against the same day.

    The day is the one the entry was minted on (``best_before`` and
    ``day_earned_before`` in its breakdown), so a relecture that lands hours
    later neither reads the rest of the day nor reshuffles it. ``None``: the
    verdict pays nothing and the entry is voided.
    """

    best_before = int(breakdown.get("best_before") or 0)
    day = DayState(
        earned=int(breakdown.get("day_earned_before") or 0),
        best={observation.target: best_before} if observation.target and best_before else {},
    )
    return mint(observation, day)


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

#: §15: the ledger's week is the ISO week in Europe/Paris (the bouclage's zone).
WEEK_ZONE = "Europe/Paris"


def _aware(instant: datetime) -> datetime:
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def week_id(instant: datetime) -> str:
    """``2026-W45``: the ISO week of ``instant`` in Europe/Paris."""

    year, week, _weekday = _aware(instant).astimezone(ZoneInfo(WEEK_ZONE)).isocalendar()
    return f"{year}-W{week:02d}"


def local_date(instant: datetime, zone: str) -> date:
    """The learner's local day of ``instant`` in ``zone``."""

    return _aware(instant).astimezone(ZoneInfo(zone)).date()


__all__ = [
    "ASSISTANCE_FACTOR",
    "BASE_VALUE",
    "CALIBRATION_TARGETS",
    "CATEGORY_LABEL_FR",
    "Category",
    "DAY_CAP",
    "DayState",
    "FORMAT_CATEGORY",
    "GoldObservation",
    "JOLI_BONUS",
    "JOLI_LABEL_FR",
    "JOURNEE_PLEINE_MARK",
    "MILESTONE_LABEL_FR",
    "MILESTONE_VALUE",
    "Milestone",
    "Minted",
    "OUTCOME_MET",
    "OUTCOME_NOT_YET",
    "OUTCOME_PARTIAL",
    "OUTCOME_UNSCORED",
    "PAYING_OUTCOMES",
    "PLAFOND_DAY_SHARE_TARGET",
    "PLAFOND_FULL_RATE_UP_TO",
    "PLAFOND_STOPS_AT",
    "PRODUCTION_CATEGORIES",
    "PRODUCTION_SHARE_TARGET",
    "RULE_VERSION",
    "RUNG_CATEGORY",
    "SPACED_CATEGORIES",
    "STATE_PENDING",
    "STATE_SETTLED",
    "STATE_VOID",
    "WEEK_ZONE",
    "advance",
    "category_for_format",
    "category_for_rung",
    "evidence_value",
    "local_date",
    "mint",
    "plafond",
    "plafond_pays",
    "reason_fr",
    "resettle",
    "target_key",
    "week_id",
]
