"""Wire schemas for La Relecture (WP-121 B): the offer, the answer, the pair.

The pair carries no score and no verdict word (§4 B.2): two answers, the spans the
phase-2 rubric flagged in each (register or grammar), and Romy's one line.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RelectureKind = Literal["question", "headline"]
RelectureFlag = Literal["register", "grammar"]


class _RelectureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelectureSpan(_RelectureModel):
    start: int
    end: int
    flag: RelectureFlag


class RelectureOffer(_RelectureModel):
    session_id: str
    #: ISO week of the Papier, ``"2026-W41"``.
    week: str
    kind: RelectureKind
    dossier_title_fr: str
    #: The question as Romy proposed it (``question_kept_fr``), or the headline ask.
    prompt_fr: str
    place_label_fr: str
    plate_url: str | None = None
    closed_at: str | None = None


class RelectureOfferView(_RelectureModel):
    offer: RelectureOffer | None = None


class RelectureAnswerRequest(_RelectureModel):
    answer_fr: str = Field(min_length=1, max_length=600)
    mode: Literal["text", "voice"] = "text"


class RelectureSide(_RelectureModel):
    label_fr: str
    text_fr: str
    spans: list[RelectureSpan] = []


class RelecturePair(_RelectureModel):
    session_id: str
    offer: RelectureOffer
    then: RelectureSide
    now: RelectureSide
    romy_line_fr: str
    asked_at: str
