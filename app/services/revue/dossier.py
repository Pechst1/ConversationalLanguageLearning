"""The editorial dossier: what is true, with provenance (WP-119 §3.1).

Shared by every learner and every consumer (La Revue now, season gap days later,
§11). Built once per story per week, cached under ``revue:dossier`` by
``(week, story_id)``. It carries no level, no language, no outfit and no exercises —
those belong to the session plan (``session.py``).

The models validate structure only: quote length, attribution of interpretations and
forecasts, claims pointing at a listed source, roles for people. Whether a quote is
really in the source, whether a fact reads as an opinion, whether the dates fit the
week are the checks on meaning (``checks.py``, §4.2).

:func:`fold` and :func:`quote_word_count` are the shared text helpers: the Anchor check
compares folded quotes against folded source text ([[ios-smart-quote-normalization]]).

See ``docs/implementation/atelier-v2/WP-119-LA-REVUE-DE-ROMY.md``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.revue.policy import TOPICS

DOSSIER_VERSION = "revue-v1"
#: A claim's ``quote`` may hold at most this many words after :func:`fold` (§3.1).
MAX_QUOTE_WORDS = 40

ClaimKind = Literal["fact", "interpretation", "forecast"]
AnglePurpose = Literal["understand_change", "explain_disagreement", "choose_angle", "prepare_dispatch"]

_APOSTROPHES = "’‘‛`´′"  # ’ ‘ ‛ ` ´ ′
_DOUBLE_QUOTES = "“”„‟«»‹›″"  # “ ” „ ‟ « » ‹ › ″
_FOLD_TABLE = str.maketrans({**dict.fromkeys(_APOSTROPHES, "'"), **dict.fromkeys(_DOUBLE_QUOTES, '"')})
_WHITESPACE = re.compile(r"\s+")
_WEEK = re.compile(r"^(\d{4})-W(\d{2})$")
_INTERVAL = re.compile(r"^(\d{4}-\d{2}-\d{2})/(\d{4}-\d{2}-\d{2})$")


def fold(text: str | None) -> str:
    """Collapse whitespace (incl. no-break spaces) and fold every apostrophe and quote mark.

    ``’ ‘ ‛ ` ´`` → ``'`` and ``“ ” „ « »`` → ``"``. Case and accents are kept: the
    Anchor check wants a verbatim match, not a fuzzy one.
    """

    return _WHITESPACE.sub(" ", str(text or "").translate(_FOLD_TABLE)).strip()


def quote_word_count(text: str | None) -> int:
    """Words in ``text`` after :func:`fold` (``l'homme`` is one word)."""

    folded = fold(text)
    return len(folded.split(" ")) if folded else 0


def parse_week(week: str) -> tuple[int, int]:
    """``"2026-W40"`` → ``(2026, 40)``; raises ``ValueError`` for anything else."""

    match = _WEEK.match(str(week or ""))
    if not match:
        raise ValueError(f"week must look like 2026-W40, got {week!r}")
    year, number = int(match.group(1)), int(match.group(2))
    try:
        date.fromisocalendar(year, number, 1)
    except ValueError as exc:
        raise ValueError(f"{week!r} is not an ISO week") from exc
    return year, number


def week_bounds(week: str) -> tuple[date, date]:
    """The Monday and the Sunday of an ISO week (the Temporal check's frame, §4.2)."""

    year, number = parse_week(week)
    return date.fromisocalendar(year, number, 1), date.fromisocalendar(year, number, 7)


def _as_date(value: Any) -> Any:
    """Accept an RSS-style datetime for a date field: keep only its calendar day."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and len(value) > 10 and value[4:5] == "-" and value[10:11] in {"T", " "}:
        return value[:10]
    return value


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(_Model):
    """One statement the dossier stands behind, typed and anchored in a verbatim quote."""

    id: str = Field(min_length=1)
    kind: ClaimKind
    fr: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    url: str = Field(min_length=1)
    published_at: date
    confidence: Literal["reported", "confirmed"] = "reported"
    attributed_to: str | None = None

    _published = field_validator("published_at", mode="before")(_as_date)

    @field_validator("quote")
    @classmethod
    def _quote_length(cls, value: str) -> str:
        words = quote_word_count(value)
        if words == 0:
            raise ValueError("quote is empty after folding")
        if words > MAX_QUOTE_WORDS:
            raise ValueError(f"quote has {words} words; at most {MAX_QUOTE_WORDS} after folding")
        return value

    @model_validator(mode="after")
    def _attribution(self) -> Claim:
        if self.kind in {"interpretation", "forecast"} and not (self.attributed_to or "").strip():
            raise ValueError(f"claim {self.id}: an {self.kind} needs attributed_to")
        return self


class Entity(_Model):
    """A named thing in the story. People keep their names (§3.1); the stage decides who is drawn."""

    name: str = Field(min_length=1)
    kind: Literal["person", "place", "organisation", "other"]
    role: str | None = None

    @model_validator(mode="after")
    def _person_role(self) -> Entity:
        if self.kind == "person" and not (self.role or "").strip():
            raise ValueError(f"entity {self.name!r}: a person needs a role")
        return self


class Angle(_Model):
    """An editorial purpose available for this story (§3.1, §5.2)."""

    id: str = Field(min_length=1)
    fr: str = Field(min_length=1)
    purpose: AnglePurpose
    #: WP-119 phase 2: how the learner takes part (dresses Toi, §12.5) and which guest fits (§7).
    participation: Literal["none", "helps", "works", "formal"] = "none"
    guest_fit: str | None = None


class Uncertainty(_Model):
    """What the sources do not say (§3.1), with a stable id (WP-119 §10e.2): the reply
    provider cites ``u1``, never a list index. Stored dossiers written before phase 6 hold
    plain strings; :class:`EditorialDossier` normalises them on load (``u1``, ``u2``… by
    position), so neither the stored JSON nor the weekly/evergreen files need a rewrite."""

    id: str = Field(min_length=1)
    fr: str = Field(min_length=1)

    def __str__(self) -> str:  # the French, wherever a consumer formats it as text
        return self.fr


def normalise_uncertainties(value: Any) -> list[dict[str, str]]:
    """Plain strings and ``{id, fr}`` dicts → ``[{id, fr}]``; a missing id becomes ``u<position>``."""

    rows: list[dict[str, str]] = []
    for index, item in enumerate(value or []):
        if isinstance(item, Uncertainty):
            rows.append(item.model_dump())
        elif isinstance(item, dict):
            fr = str(item.get("fr") or item.get("text") or "").strip()
            if fr:
                rows.append({"id": str(item.get("id") or f"u{index + 1}"), "fr": fr})
        elif str(item or "").strip():
            rows.append({"id": f"u{index + 1}", "fr": str(item).strip()})
    return rows


class Geo(_Model):
    """Where a place is on the map (WP-120 §3.1); resolved by ``geo.py``, checked by ``check_geo``."""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    precision: Literal["exact", "city", "region"]
    label_fr: str = Field(min_length=1)


class Place(_Model):
    """Where the story happens. ``known``: a season location with a plate already (§8.1)."""

    id: str = Field(min_length=1)
    name_fr: str = Field(min_length=1)
    brief: str = ""
    known: bool = False
    #: WP-120 §3: optional, so a dossier without coordinates stays valid (no pin).
    geo: Geo | None = None


class VisualWord(_Model):
    """A word the story picture shows: the French with its article (it appears in a claim, so
    the session's vocabulary can carry it) and, in English for the painter, what shows it."""

    fr: str = Field(min_length=1, max_length=60)
    shows: str = Field(min_length=1, max_length=200)


class StoryVisual(_Model):
    """The story picture's brief (WP-119 §8.4): the one moment that says what happened,
    painted once on the site (``places[0]``) and shared by every learner.

    English for the painter (``moment``, ``symbol``, ``viewpoint``, ``light``, each word's
    ``shows``), where people appear by their role and never by name; French for the learner
    (``caption_fr``, which names them, ``look_fr``, Romy pointing at the picture, and
    ``decoys_fr``, the wrong captions of the A1–A2 caption choice).
    """

    #: v2 (owner, 2026-10-14): ``scene`` paints the real moment at the site; ``editorial`` paints
    #: one bold visual idea (``symbol``, large in the frame) for news that is said, decided or
    #: counted rather than seen. Rows built before v2 read as ``scene``.
    kind: Literal["scene", "editorial"] = "scene"
    moment: str = Field(min_length=1, max_length=400)
    symbol: str | None = Field(None, max_length=240)
    viewpoint: str = Field(min_length=1, max_length=200)
    light: str = Field(min_length=1, max_length=160)
    words: list[VisualWord] = Field(default_factory=list, max_length=3)
    caption_fr: str = Field(min_length=1, max_length=200)
    look_fr: str | None = Field(None, max_length=240)
    #: «La légende» at A1–A2: two captions in the same style that the picture plainly
    #: contradicts (one visible detail wrong: the place, who acts, what they do).
    decoys_fr: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(default_factory=list, max_length=2)

    def painter_text(self) -> str:
        """Everything the painter reads, for the staging checks (names, forbidden words)."""

        return " ".join(
            part for part in (self.moment, self.symbol or "", self.viewpoint, self.light, *[w.shows for w in self.words]) if part
        )


class StoryLead(_Model):
    """What happened, told for one band (owner, 2026-10-18: «it's not clear what happened»):
    plain French the learner reads before anyone talks, and its translations for the
    translate button (``leads.py`` keeps the French short and checks it)."""

    fr: str = Field(min_length=1)
    en: str | None = None
    de: str | None = None

    def translation(self, language: str) -> str | None:
        return {"en": self.en, "de": self.de}.get(language)


class StoryLeads(_Model):
    """«La une en trois phrases»: ``a1`` (three short present-tense sentences, at most 30
    words) and ``a2`` tell the story at those bands; B1 and up read ``summary_fr``.
    ``headline_fr`` (six words or fewer) is what Home's news card says."""

    headline_fr: str | None = Field(None, max_length=80)
    a1: StoryLead | None = None
    a2: StoryLead | None = None


#: «Au comptoir» (WP-119, 2026-10-19): the three sides of the question of the day.
ComptoirStance = Literal["pour", "contre", "nuance"]
COMPTOIR_STANCES: tuple[str, ...] = ("pour", "contre", "nuance")
#: The bands a take is written for; B2 reads ``b1``.
ComptoirBand = Literal["a1", "a2", "b1"]


def comptoir_band(band: str) -> str:
    """``"A1"`` → ``"a1"``, ``"A2"`` → ``"a2"``, B1 and up → ``"b1"`` (the takes' bands)."""

    return {"A1": "a1", "A2": "a2"}.get(str(band or "").upper()[:2], "b1")


class ComptoirText(_Model):
    """One line of «Au comptoir»: the French and its translations for the translate chip
    (``comptoir.py`` keeps the French short and checks it; every band has the chip)."""

    fr: str = Field(min_length=1)
    en: str | None = None
    de: str | None = None

    def translation(self, language: str) -> str | None:
        return {"en": self.en, "de": self.de}.get(language)


class ComptoirTake(_Model):
    """One guest's take on the question, written for each band (B2 reads ``b1``)."""

    a1: ComptoirText
    a2: ComptoirText
    b1: ComptoirText

    def for_band(self, band: str) -> ComptoirText:
        return getattr(self, comptoir_band(band))


class ComptoirGuest(_Model):
    """A regular at the counter: their side, their take, and the quote «La page» prints."""

    id: str = Field(min_length=1)
    stance: ComptoirStance
    take: ComptoirTake
    quote: ComptoirText


class ComptoirIntox(_Model):
    """The one false detail a guest slips into their take («un million de personnes»), the
    true value as the claim ``claim_id`` writes it, and another true value of the same kind
    for the A1–A2 pick. ``bands``: where the check found ``wrong_fr`` in the take."""

    by: str = Field(min_length=1)
    wrong_fr: str = Field(min_length=1)
    right_fr: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    distractor_fr: str = Field(min_length=1)
    ask: ComptoirText
    caught: ComptoirText
    bands: list[ComptoirBand] = Field(min_length=1)


class ComptoirReply(_Model):
    """What a guest who disagrees answers a learner on one side, and the comeback chip."""

    by: str = Field(min_length=1)
    line: ComptoirText
    comeback: ComptoirText


class ComptoirPhrase(_Model):
    """The phrase of the day per band («Je suis pour / contre…», «À mon avis…, parce que…»)."""

    a1: ComptoirText
    a2: ComptoirText
    b1: ComptoirText
    b2: ComptoirText

    def for_band(self, band: str) -> ComptoirText:
        return self.b2 if str(band or "").upper().startswith("B2") else getattr(self, comptoir_band(band))


class ComptoirTakes(_Model):
    """«Au comptoir» (WP-119, owner 2026-10-19): the regulars of Le Mistral argue about the
    story. Written once per story by the takes desk (``comptoir.py``), shared by every
    learner; ``None`` on a dossier the desk has not written or refused (it stays chat-only)."""

    question: ComptoirText
    guests: list[ComptoirGuest] = Field(min_length=3, max_length=3)
    intox: ComptoirIntox | None = None
    #: A1 tiles: each completes «… parce que …» (five words at most).
    reasons: dict[ComptoirStance, list[ComptoirText]] = Field(default_factory=dict)
    #: A2 frames, ending before the reason («À mon avis, c'est une bonne nouvelle, parce que»).
    frames: dict[ComptoirStance, ComptoirText] = Field(default_factory=dict)
    bank: list[ComptoirText] = Field(default_factory=list, max_length=6)
    phrase: ComptoirPhrase
    #: The counter-line when the learner takes that side; a side without one reads the
    #: authored line of ``comptoir.AUTHORED_REPLIES``.
    replies: dict[ComptoirStance, ComptoirReply] = Field(default_factory=dict)
    model: str = ""
    written_at: datetime | None = None
    prompt_version: str = ""

    @model_validator(mode="after")
    def _sides(self) -> ComptoirTakes:
        if sorted(guest.stance for guest in self.guests) != sorted(COMPTOIR_STANCES):
            raise ValueError("the three guests take the three sides: pour, contre, nuance")
        if self.intox is not None and self.intox.by not in {guest.id for guest in self.guests}:
            raise ValueError(f"intox.by {self.intox.by!r} is not at the counter")
        return self

    def guest(self, cast_id: str) -> ComptoirGuest | None:
        return next((guest for guest in self.guests if guest.id == cast_id), None)

    def by_stance(self, stance: str) -> ComptoirGuest:
        return next(guest for guest in self.guests if guest.stance == stance)

    def intox_for(self, band: str) -> ComptoirIntox | None:
        """The intox, when the learner's band reads a take that carries it."""

        intox = self.intox
        return intox if intox is not None and comptoir_band(band) in intox.bands else None


class TimeScope(_Model):
    """When the story happens (``happening``, an ISO interval) and until when it matters."""

    happening: str
    relevant_until: date

    _relevant = field_validator("relevant_until", mode="before")(_as_date)

    @field_validator("happening")
    @classmethod
    def _interval(cls, value: str) -> str:
        match = _INTERVAL.match(str(value or "").strip())
        if not match:
            raise ValueError("happening must be an ISO interval YYYY-MM-DD/YYYY-MM-DD")
        start, end = date.fromisoformat(match.group(1)), date.fromisoformat(match.group(2))
        if end < start:
            raise ValueError("happening ends before it starts")
        return f"{start.isoformat()}/{end.isoformat()}"

    @property
    def start(self) -> date:
        return date.fromisoformat(self.happening.split("/", 1)[0])

    @property
    def end(self) -> date:
        return date.fromisoformat(self.happening.split("/", 1)[1])


class Source(_Model):
    """A publication a claim is quoted from."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    published_at: date

    _published = field_validator("published_at", mode="before")(_as_date)


class EditorialDossier(_Model):
    """One sourced story for one week (§3.1)."""

    id: str = Field(min_length=1)
    dossier_version: Literal["revue-v1"] = DOSSIER_VERSION
    week: str
    topic: str
    title_fr: str = Field(min_length=1)
    summary_fr: str = Field(min_length=1)
    claims: list[Claim] = Field(min_length=2)
    entities: list[Entity] = Field(default_factory=list)
    uncertainties: list[Uncertainty] = Field(default_factory=list)
    angles: list[Angle] = Field(min_length=1)
    places: list[Place] = Field(min_length=1)
    time_scope: TimeScope
    sources: list[Source] = Field(min_length=1)
    evergreen: bool = False
    #: WP-120 §4.1: the one object the vignette's pictogram draws («une urne»); chosen by the builder.
    vignette_object_fr: str | None = None
    #: WP-119 §8.4: the story picture's brief; ``None`` on dossiers built before it (they keep
    #: the place plate) and when the builder's brief was refused.
    visual: StoryVisual | None = None
    #: «La une en trois phrases» (2026-10-18); ``None`` until the builder or the lead desk
    #: (``leads.py``) wrote them — every band then reads ``summary_fr``.
    leads: StoryLeads | None = None
    #: «Au comptoir» (2026-10-19): the regulars' takes on the question of the day; ``None``
    #: until the takes desk (``comptoir.py``) wrote them. Read only while
    #: ``REVUE_COMPTOIR_ENABLED`` is on.
    comptoir: ComptoirTakes | None = None

    @field_validator("week")
    @classmethod
    def _week(cls, value: str) -> str:
        parse_week(value)
        return value

    @field_validator("uncertainties", mode="before")
    @classmethod
    def _uncertainties(cls, value: Any) -> list[dict[str, str]]:
        return normalise_uncertainties(value)

    @field_validator("topic")
    @classmethod
    def _topic(cls, value: str) -> str:
        if value not in TOPICS:
            raise ValueError(f"topic must be one of {', '.join(TOPICS)}")
        return value

    @model_validator(mode="after")
    def _references(self) -> EditorialDossier:
        for label, rows in (
            ("claim", self.claims),
            ("angle", self.angles),
            ("place", self.places),
            ("source", self.sources),
            ("uncertainty", self.uncertainties),
        ):
            ids = [row.id for row in rows]
            duplicates = sorted({row_id for row_id in ids if ids.count(row_id) > 1})
            if duplicates:
                raise ValueError(f"duplicate {label} ids: {', '.join(duplicates)}")
        source_ids = {source.id for source in self.sources}
        for claim in self.claims:
            if claim.source_id not in source_ids:
                raise ValueError(f"claim {claim.id}: source_id {claim.source_id!r} is not in sources")
        return self

    def claims_by_id(self) -> dict[str, Claim]:
        return {claim.id: claim for claim in self.claims}

    def facts(self) -> list[Claim]:
        return [claim for claim in self.claims if claim.kind == "fact"]

    def interpretations(self) -> list[Claim]:
        """Claims of kind ``interpretation`` only (see :meth:`forecasts`)."""

        return [claim for claim in self.claims if claim.kind == "interpretation"]

    def forecasts(self) -> list[Claim]:
        return [claim for claim in self.claims if claim.kind == "forecast"]

    def person_names(self) -> list[str]:
        """Names of person entities — the staging rule keeps them off plates (§8.1)."""

        return [entity.name for entity in self.entities if entity.kind == "person"]

    def uncertainty_texts(self) -> list[str]:
        """The uncertainties' French, in order."""

        return [u.fr for u in self.uncertainties]

    def uncertainty_by_id(self, uncertainty_id: str) -> Uncertainty | None:
        return next((u for u in self.uncertainties if u.id == str(uncertainty_id)), None)

    def angle_by_id(self, angle_id: str) -> Angle | None:
        return next((angle for angle in self.angles if angle.id == angle_id), None)

    def source_by_id(self, source_id: str) -> Source | None:
        return next((source for source in self.sources if source.id == source_id), None)

    def lead_for(self, band: str) -> StoryLead:
        """What happened, for ``band``: A1 its lead (else A2's), A2 its lead (else A1's), B1
        and up — or a dossier without leads — the summary."""

        leads = self.leads
        if leads is not None:
            for lead in {"A1": (leads.a1, leads.a2), "A2": (leads.a2, leads.a1)}.get(band, ()):
                if lead is not None:
                    return lead
        return StoryLead(fr=self.summary_fr)

    def simpler_lead(self, band: str) -> StoryLead:
        """The lead a step below ``band`` (A1 stays A1): Romy retells it when the learner is lost."""

        return self.lead_for("A1" if band in {"A1", "A2"} else "A2")
