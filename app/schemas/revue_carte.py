"""Wire schemas for La Carte (WP-120 §5): ``GET /revue/carte``.

A pin is one closed Papier with a place on the map; it carries what its card opens
on in French (the headline, the kept words, the learner's part, the plate) and the
vignette's parts when one was minted. ``quartier`` is the season's «Mon quartier»
layer: only places the learner has already been to in the story, so it never spoils.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

CartePrecision = Literal["exact", "city", "region"]
CarteRing = Literal["headline", "question", "report"]
CarteLevel = Literal["france", "idf", "paris"]


class _CarteModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CarteVignette(_CarteModel):
    ring: CarteRing
    kept_contribution: bool
    #: The dossier's validated pictogram (house grammar), sanitised again client-side.
    pictogram_svg: str


class CartePin(_CarteModel):
    session_id: str
    dossier_id: str
    #: ISO week, ``"2026-W40"``.
    week: str
    closed_at: str | None = None
    place_label_fr: str
    lat: float
    lon: float
    precision: CartePrecision
    #: The innermost drawing the pin sits on (``paris`` ⊂ ``idf`` ⊂ ``france``).
    level: CarteLevel
    headline_fr: str
    kept_words: list[str]
    #: What the learner made (``headline_choice`` · ``headline_write`` · ``reader_question`` · ``short_report``).
    contribution_kind: str | None = None
    contribution_fr: str | None = None
    #: Character spans of the learner's own words inside ``contribution_fr``.
    contribution_spans: list[tuple[int, int]] = []
    question_fr: str | None = None
    plate_url: str | None = None
    vignette: CarteVignette | None = None


class CarteQuartierPlace(_CarteModel):
    id: str
    name_fr: str
    label_fr: str
    lat: float
    lon: float
    plate_url: str | None = None


class CarteCounts(_CarteModel):
    france: int
    idf: int
    paris: int
    #: Closed Papiers whose place has no coordinates (no pin).
    unplaced: int


class CarteView(_CarteModel):
    pins: list[CartePin]
    quartier: list[CarteQuartierPlace]
    counts: CarteCounts
