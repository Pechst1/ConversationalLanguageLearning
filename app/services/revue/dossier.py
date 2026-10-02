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
from typing import Any, Literal

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


class Place(_Model):
    """Where the story happens. ``known``: a season location with a plate already (§8.1)."""

    id: str = Field(min_length=1)
    name_fr: str = Field(min_length=1)
    brief: str = ""
    known: bool = False


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
    uncertainties: list[str] = Field(default_factory=list)
    angles: list[Angle] = Field(min_length=1)
    places: list[Place] = Field(min_length=1)
    time_scope: TimeScope
    sources: list[Source] = Field(min_length=1)
    evergreen: bool = False

    @field_validator("week")
    @classmethod
    def _week(cls, value: str) -> str:
        parse_week(value)
        return value

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

    def angle_by_id(self, angle_id: str) -> Angle | None:
        return next((angle for angle in self.angles if angle.id == angle_id), None)

    def source_by_id(self, source_id: str) -> Source | None:
        return next((source for source in self.sources if source.id == source_id), None)
