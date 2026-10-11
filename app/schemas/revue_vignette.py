"""Wire schemas for the Revue's vignettes (WP-120 §4): ``GET /revue/vignettes``.

A vignette is composed client-side (``RvVignette``): the frame is authored, the
pictogram is the dossier's validated SVG (house grammar, ``revue/pictogram.py``), the
ring and the kept mark are what the learner did. Nothing private is on the wire.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

VignetteRing = Literal["headline", "question", "report"]


class VignetteView(BaseModel):
    """One minted vignette with everything the stamp needs."""

    model_config = ConfigDict(extra="forbid")

    id: str
    session_id: str
    dossier_id: str
    #: ISO week, ``"2026-W40"``; the stamp prints its number.
    week: str
    place_label_fr: str
    ring: VignetteRing
    kept_contribution: bool
    #: The normalised pictogram (``<svg viewBox="0 0 100 100">``, house grammar).
    pictogram_svg: str
    #: The dispatch's headline as filed, else the dossier's title.
    headline_fr: str
    minted_at: datetime


class VignettesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vignettes: list[VignetteView]
