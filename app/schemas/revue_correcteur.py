"""Wire schemas for Le Correcteur (WP-122 §4): ``/revue/correcteur/*``.

The draft the learner sees never carries the key: ``CrDraftView`` has the seeded
sentences, the tappable units (with three options each at A1–A2) and how many
mistakes Romy left, but not where. The key comes back only in ``CrResult``, after
«Bon à tirer». Spans are ``[start, end)`` character offsets inside one sentence.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CrOutcome = Literal["repaired", "noticed", "missed"]
CrSource = Literal["errata", "classique"]


class _CrModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _span(value: list[int]) -> list[int]:
    if len(value) != 2 or value[0] < 0 or value[1] <= value[0]:
        raise ValueError("span must be [start, end) with 0 <= start < end")
    return value


class CrWeekDossier(_CrModel):
    id: str
    title_fr: str
    topic: str
    evergreen: bool


class CrWeek(_CrModel):
    #: ISO week, ``"2026-W40"``.
    week: str
    label: str
    #: The week's dossiers the learner has not corrected yet (the chip rotates through them).
    dossiers: list[CrWeekDossier]
    corrected: list[str]


class CrUnit(_CrModel):
    """One tappable unit (a word, or a contraction pair like «de le»)."""

    sentence_index: int
    span: list[int]
    text: str
    #: A1–A2 only: three forms to pick from (the unit's own, and forms the rules make), else null.
    options: list[str] | None = None


class CrDraftView(_CrModel):
    id: str
    dossier_id: str
    band: str
    kicker_fr: str
    title_fr: str
    byline_fr: str
    sentences: list[str]
    units: list[CrUnit]
    #: How many mistakes Romy left (never where).
    errors_count: int
    options_enabled: bool
    #: Set once graded: reopening a corrected draft shows its result.
    result: CrResult | None = None


class CrMark(_CrModel):
    sentence_index: int = Field(ge=0)
    span: list[int]
    fix_fr: str | None = Field(default=None, max_length=120)
    #: The fix was picked from the options (A1–A2): a repair with help.
    picked: bool = False

    _check_span = field_validator("span")(_span)


class CrMarksRequest(_CrModel):
    marks: list[CrMark] = Field(default_factory=list, max_length=40)


class CrSeedOutcome(_CrModel):
    sentence_index: int
    span: list[int]
    wrong_fr: str
    correct_fr: str
    grammar_point: str
    source: CrSource
    outcome: CrOutcome
    fix_fr: str | None = None


class CrFalseAlarm(_CrModel):
    sentence_index: int
    span: list[int]
    text_fr: str
    fix_fr: str | None = None


class CrCounts(_CrModel):
    seeded: int
    repaired: int
    noticed: int
    missed: int
    false_alarms: int


class CrResult(_CrModel):
    id: str
    dossier_id: str
    sentences: list[str]
    outcomes: list[CrSeedOutcome]
    false_alarms: list[CrFalseAlarm]
    counts: CrCounts
    romy_line_fr: str
    releve_href: str


CrDraftView.model_rebuild()
