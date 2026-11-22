"""Wire schemas for «Papier · la voix» (``REVUE_VOIX_ENABLED``, ``app/services/revue/voix.py``).

On their own routes (``app/api/v1/endpoints/revue_voix.py``): with the switch off no existing
payload gains a field. The line route answers the journey's own ``LineAudioResult``, so the
client's line-audio resolver is reused as is.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.revue import ComptoirMarkKind, RevueModel, RevueRequest


class RvVoixLine(RevueModel):
    kind: Literal["lead", "take", "reply", "last_word"]
    speaker_id: str
    text_fr: str


class RvVoixDictee(RevueModel):
    #: The lead's sentence (the learner has just read it; the player covers the lead while they write).
    text_fr: str
    words: int
    max_tries: int


class RvVoixManifest(RevueModel):
    #: ``ready``: clips can be made (lines are heard before they are read); ``device``: the
    #: device voice reads on request and every text shows at once.
    audio: Literal["ready", "device"]
    newsreader_id: str
    lines: list[RvVoixLine]
    #: ``None``: no sentence of the lead fits the band, or no clip can be made.
    dictee: RvVoixDictee | None = None


class RvVoixDicteeRequest(RevueRequest):
    text: str = Field(min_length=1, max_length=400)
    attempt: int = Field(default=1, ge=1, le=2)


class RvVoixMark(RevueModel):
    span_fr: str
    start: int = 0
    kind: ComptoirMarkKind


class RvVoixDicteeResult(RevueModel):
    outcome: Literal["met", "partially_met", "not_yet"]
    attempt: int
    max_tries: int
    resolved: bool
    answer_fr: str
    marks: list[RvVoixMark]
    #: The line, only once it may be shown (right, or the last try).
    expected_fr: str | None = None
    note: str | None = None
