"""The session plan: this learner, this time (WP-119 §3.2, §5, §6).

Built on entry from one :class:`~app.services.revue.dossier.EditorialDossier` and the
learner's context, persisted with the journey (``DailyJourney`` row, shape ``REVUE``)
and pinned for resume. The dossier never changes for a learner; the plan does —
breakdown moves it to the next support level (§5.3, :func:`next_support_level`).

:func:`plan_for` is pure: no I/O, no model call. Vocabulary is left empty here and
filled by a later builder; when present it is validated against the dossier
(``SessionPlan.validate_against`` or ``model_validate(..., context={"dossier": d})``).

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

from app.services.revue import policy
from app.services.revue.dossier import Angle, AnglePurpose, EditorialDossier

PLAN_VERSION = "revue-plan-v1"

GlossMode = Literal["shown", "tap", "none"]
TranslationMode = Literal["one_tap", "on_request", "none"]
MakeOption = Literal["headline_choice", "headline_write", "reader_question", "tell_margaux", "short_report"]

DEFAULT_ROUTE: tuple[str, ...] = ("arrive", "facts", "pursue", "make", "close")
#: §5.4 make options by band: A1/A2 choose a headline, B1+ write one and may report.
MAKE_OPTIONS_LOWER: tuple[str, ...] = ("headline_choice", "reader_question", "tell_margaux")
MAKE_OPTIONS_UPPER: tuple[str, ...] = ("headline_write", "reader_question", "tell_margaux", "short_report")

#: Romy's prop on the Revue stage (WP-116 §12.3 tier 1, §8.3).
ROMY_ID = "romy_tremblay"
ROMY_HOLD = "notebook"
#: Shortest reading target simplification goes down to (§5.3).
MIN_READING_TARGET_WORDS = 40
SIMPLIFY_READING_FACTOR = 0.7

_GLOSS_LADDER: tuple[str, ...] = ("none", "tap", "shown")
_TRANSLATION_LADDER: tuple[str, ...] = ("none", "on_request", "one_tap")


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LearnerContext(_Model):
    band: str
    ui_language: str = Field(min_length=2)
    interests: list[str] = Field(default_factory=list)

    @field_validator("band", mode="before")
    @classmethod
    def _band(cls, value: object) -> str:
        return policy.normalize_band(str(value or ""))


class Support(_Model):
    """How much help the French comes with (§6); the encounter reads it every turn."""

    glosses: GlossMode
    translation: TranslationMode
    simplify_on_breakdown: bool = True
    reading_target_words: int = Field(ge=1)
    vocab_target: int = Field(ge=0)


class VocabItem(_Model):
    fr: str = Field(min_length=1)
    gloss: dict[str, str] = Field(default_factory=dict)
    claim_id: str = Field(min_length=1)


class StageCast(_Model):
    id: str = Field(min_length=1)
    hold: str | None = None


class Guest(_Model):
    """A cast member with a reason to care (§7). ``reason`` is English (the plan, the
    provider); ``reason_fr`` is what they say on entry; ``fit`` marks the angle's
    ``guest_fit`` (they enter at the first ``pursue`` turn instead of on topic words)."""

    id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    reason_fr: str | None = None
    fit: bool = False


class StagePlan(_Model):
    """Where the scene is set and who stands in it (§8); validated again by the Render check."""

    place_id: str = Field(min_length=1)
    plate_url: str | None = None
    dress: str = policy.DEFAULT_OUTFIT
    cast: list[StageCast] = Field(default_factory=list)
    guests_available: list[Guest] = Field(default_factory=list)

    @field_validator("dress")
    @classmethod
    def _dress(cls, value: str) -> str:
        if value not in policy.OUTFITS:
            raise ValueError(f"dress must be one of {', '.join(policy.OUTFITS)}")
        return value


class Activities(_Model):
    default: list[str] = Field(default_factory=lambda: list(DEFAULT_ROUTE))
    make_options: list[MakeOption] = Field(min_length=1)


class Budget(_Model):
    turns: int = Field(14, ge=1)
    minutes: int = Field(8, ge=1)


class SessionPlan(_Model):
    """One learner's Revue on one dossier (§3.2)."""

    plan_version: Literal["revue-plan-v1"] = PLAN_VERSION
    dossier_id: str = Field(min_length=1)
    learner: LearnerContext
    chosen_by: Literal["learner", "recommended"] = "recommended"
    angle_id: str = Field(min_length=1)
    purpose: AnglePurpose
    support: Support
    vocabulary: list[VocabItem] = Field(default_factory=list)
    activities: Activities
    stage: StagePlan
    budget: Budget = Field(default_factory=Budget)

    @model_validator(mode="after")
    def _against_context_dossier(self, info: ValidationInfo) -> SessionPlan:
        dossier = (info.context or {}).get("dossier") if isinstance(info.context, dict) else None
        if dossier is not None:
            self.validate_against(dossier)
        return self

    def validate_against(self, dossier: EditorialDossier) -> SessionPlan:
        """Raise ``ValueError`` unless the plan's references exist in ``dossier``."""

        if self.dossier_id != dossier.id:
            raise ValueError(f"plan is for dossier {self.dossier_id!r}, not {dossier.id!r}")
        angle = dossier.angle_by_id(self.angle_id)
        if angle is None:
            raise ValueError(f"angle {self.angle_id!r} is not in dossier {dossier.id!r}")
        if angle.purpose != self.purpose:
            raise ValueError(f"purpose {self.purpose!r} is not angle {angle.id}'s ({angle.purpose!r})")
        claim_ids = set(dossier.claims_by_id())
        unknown = [item.claim_id for item in self.vocabulary if item.claim_id not in claim_ids]
        if unknown:
            raise ValueError(f"vocabulary points at unknown claims: {', '.join(unknown)}")
        return self


def _make_options(band: str) -> list[str]:
    return list(MAKE_OPTIONS_LOWER if band in {"A1", "A2"} else MAKE_OPTIONS_UPPER)


def plan_for(
    dossier: EditorialDossier,
    learner: LearnerContext,
    *,
    angle_id: str | None = None,
    chosen_by: Literal["learner", "recommended"] = "recommended",
    place_known_plate: Callable[[str], str | None] | None = None,
) -> SessionPlan:
    """The default plan for ``learner`` on ``dossier`` (§3.2, §6).

    The first angle unless one is given; support from the band's §6 defaults; the
    dossier's first place; Toi dressed by the angle's ``participation`` (phase 2,
    :func:`policy.dress_for_angle` — the place alone never dresses); Romy with her
    notebook and Toi; the topic's guests with their reasons, the angle's ``guest_fit``
    first; make options by band. ``plate_url``
    comes from ``place_known_plate(place_id)`` when given (the §8.1 fallback is the
    stage's business, not the plan's).
    """

    if angle_id is None:
        angle = dossier.angles[0]
    else:
        found = dossier.angle_by_id(angle_id)
        if found is None:
            raise ValueError(f"angle {angle_id!r} is not in dossier {dossier.id!r}")
        angle = found

    defaults = policy.band_support(learner.band)
    support = Support(**{name: defaults[name] for name in Support.model_fields})

    place = dossier.places[0]
    kind = policy.place_kind(f"{place.id} {place.name_fr} {place.brief}")
    plate_url = place_known_plate(place.id) if place_known_plate is not None else None
    guests = guests_for_angle(dossier, angle, place_name=place.name_fr)

    plan = SessionPlan(
        dossier_id=dossier.id,
        learner=learner,
        chosen_by=chosen_by,
        angle_id=angle.id,
        purpose=angle.purpose,
        support=support,
        vocabulary=[],
        activities=Activities(make_options=_make_options(learner.band)),
        stage=StagePlan(
            place_id=place.id,
            plate_url=plate_url,
            dress=policy.dress_for_angle(angle.participation, kind),
            cast=[StageCast(id=ROMY_ID, hold=ROMY_HOLD), StageCast(id="user")],
            guests_available=guests,
        ),
        budget=Budget(),
    )
    return plan.validate_against(dossier)


def guests_for_angle(dossier: EditorialDossier, angle: Angle, *, place_name: str) -> list[Guest]:
    """The guests available for this angle (§7, phase 2), in order of preference.

    The topic's :data:`policy.GUEST_AFFINITY` with their reasons; an angle whose
    ``guest_fit`` names a guest cast member puts that guest first with ``fit=True`` (with
    the affinity's reason when the topic has one, else the cast member's own
    :data:`policy.GUEST_REASON_FR`). An unknown ``guest_fit`` is ignored.
    """

    rows = policy.guests_for(dossier.topic, place=place_name, title=dossier.title_fr)
    guests = [Guest(**row) for row in rows]
    fit = (angle.guest_fit or "").strip()
    if fit and fit in policy.GUEST_CAST_IDS:
        known = next((guest for guest in guests if guest.id == fit), None)
        chosen = (
            known.model_copy(update={"fit": True})
            if known is not None
            else Guest(id=fit, reason=f"the angle names {fit} as the guest who fits", reason_fr=policy.GUEST_REASON_FR[fit], fit=True)
        )
        guests = [chosen, *(guest for guest in guests if guest.id != fit)]
    return guests


def _step_up(ladder: tuple[str, ...], current: str) -> str:
    index = ladder.index(current) if current in ladder else 0
    return ladder[min(index + 1, len(ladder) - 1)]


def next_support_level(support: Support) -> Support:
    """Simplify on breakdown (§5.3): more glosses, closer translation, shorter French.

    ``glosses`` none → tap → shown, ``translation`` none → on_request → one_tap, the
    reading target × 0.7 (never below 40 words, never longer
    than before). The vocabulary target is unchanged;
    the top level is a fixed point except for the reading target's floor.
    """

    return support.model_copy(
        update={
            "glosses": _step_up(_GLOSS_LADDER, support.glosses),
            "translation": _step_up(_TRANSLATION_LADDER, support.translation),
            "reading_target_words": min(
                support.reading_target_words,
                max(MIN_READING_TARGET_WORDS, round(support.reading_target_words * SIMPLIFY_READING_FACTOR)),
            ),
        }
    )


# ---------------------------------------------------------------------------
# Vocabulary worth learning (WP-119 §10e.5)
# ---------------------------------------------------------------------------

#: A contraction or partitive in front of a noun → the dictionary article (gender kept).
_CONTRACTIONS: tuple[tuple[str, str], ...] = (
    ("de l'", "l'"), ("de l’", "l'"), ("de la ", "la "), ("du ", "le "), ("au ", "le "),
    ("aux ", "les "), ("des ", "les "), ("d'", ""), ("d’", ""),
)
#: Never a vocabulary item on their own (articles, contractions, pronouns).
NOT_WORDS: frozenset[str] = frozenset({
    "le", "la", "les", "l", "un", "une", "des", "du", "de", "d", "au", "aux", "en", "et", "ou", "a", "à",
    "ce", "ces", "cet", "cette", "son", "sa", "ses", "leur", "leurs", "qui", "que", "dont",
})
#: Grammar words, months and weekdays: the can-do catalogue lists some («pas», «pendant»,
#: «contre»), but a Papier's vocabulary is the story's nouns and verbs (folded, accent-free).
FUNCTION_WORDS: frozenset[str] = frozenset("""
    pas plus moins aussi toujours souvent jamais rien personne pendant depuis contre avant apres chez devant
    derriere comme mais donc alors car parce quand si que qui quoi en tout tous toute toutes deja seulement
    surtout peu beaucoup ici la ou bien bon oui non merci chaque chacun aucun aucune ni des dont celui celle
    mien pourtant cependant toutefois malgre neanmoins puisque selon vraiment surement certainement peut-etre
    eventuellement combien deux trois encore tres trop ensuite puis meme entre sans sous sur vers pour avec
    dans par contre-coup environ presque autre autres plusieurs quelque quelques cela ceci leur leurs notre
    votre janvier fevrier mars avril mai juin juillet aout septembre octobre novembre decembre lundi mardi
    mercredi jeudi vendredi samedi dimanche
""".split())
_LETTERS = re.compile(r"[^\W\d_]+", re.UNICODE)


def _plain(word: str) -> str:
    decomposed = unicodedata.normalize("NFKD", word.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def vocabulary_form(fr: str, source_fr: str = "") -> str | None:
    """The dictionary form of a vocabulary item, or None when it is not worth learning.

    Refused: numbers («2026»), grammar words, months and weekdays (:data:`FUNCTION_WORDS`), proper nouns (a capital after the article, or a word the
    source text only ever writes capitalised inside a sentence: «Paris», «l'Insee»), bare
    articles and contractions («du»), and words under three letters. A contraction in
    front of a noun becomes the article («du marché» → «le marché», «aux familles» →
    «les familles», «de l'énergie» → «l'énergie»)."""

    value = " ".join(str(fr or "").split()).strip(" .,;:!?«»\"")
    if not value or any(ch.isdigit() for ch in value):
        return None
    lowered = value.lower()
    for head, article in _CONTRACTIONS:
        if lowered.startswith(head) and len(value) > len(head):
            value = article + value[len(head):]
            lowered = value.lower()
            break
    if lowered.startswith(("l'", "l’")):
        article, bare = "l'", value[2:]
    else:
        first, _, rest = value.partition(" ")
        if first.lower() in {"le", "la", "les", "un", "une"} and rest:
            article, bare = first.lower() + " ", rest
        else:
            article, bare = "", value
    words = _LETTERS.findall(bare)
    if not words or bare.lower() in NOT_WORDS or max(len(w) for w in words) < 3:
        return None
    if len(words) == 1 and _plain(words[0]) in FUNCTION_WORDS:
        return None
    if any(word[:1].isupper() for word in words):
        return None
    if source_fr and _only_capitalised_inside(bare, source_fr):
        return None
    return f"{article}{bare}"


def _only_capitalised_inside(bare: str, source_fr: str) -> bool:
    """``bare`` occurs in ``source_fr`` only with a capital, never at a sentence start (a name)."""

    head = _LETTERS.findall(bare)[0]
    seen = False
    for match in re.finditer(r"(?<![\w-])" + re.escape(head) + r"(?![\w-])", source_fr, flags=re.IGNORECASE):
        token = match.group(0)
        before = source_fr[: match.start()].rstrip(" «\"'’(")
        sentence_start = not before or before[-1] in ".!?…:"
        if token[:1].islower():
            return False
        if not sentence_start:
            seen = True
    return seen
