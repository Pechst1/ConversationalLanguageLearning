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


class CarteRelectureMark(_CarteModel):
    state: Literal["eligible", "read"]
    #: When the learner answered again (``read`` only), ISO.
    read_at: str | None = None


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
    #: WP-121: the dossier place the Papier happened at (the review's key).
    place_id: str | None = None
    #: WP-121 A.2: due words met at this place (on the place's most recent pin only).
    due_words: int = 0
    #: WP-121 B: «Relire ta question» (eligible) or «Relue le …» (read).
    relecture: CarteRelectureMark | None = None


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
    #: WP-121 A.2: every due word met in a Papier that has a pin.
    due_total: int = 0


# ---------------------------------------------------------------------------
# WP-121 A.3 · reviewing «ici»: ``GET /revue/carte/review/{place_id}`` and its grade
# ---------------------------------------------------------------------------


class CarteReviewWord(_CarteModel):
    progress_id: str
    word_id: int
    word: str
    gloss: str
    #: The claim the word was kept with (``met.sentence``).
    sentence_fr: str
    #: Who carried the word in the thread (``romy_tremblay`` or a guest's cast id) and the line.
    speaker_id: str
    speaker_name: str
    line_fr: str
    session_id: str
    week: str


class CarteReviewOption(_CarteModel):
    id: str
    text_fr: str
    side: Literal["fr", "native"] | None = None


class CarteReviewItem(_CarteModel):
    id: str
    task_type: Literal["match_pairs", "word_bank", "unscramble", "dictation"]
    progress_ids: list[str]
    prompt_fr: str | None = None
    options: list[CarteReviewOption]
    #: The journey's hashed key (``journey_answer_key``), so the device colours a pick at once.
    answer_key: dict | None = None
    audio_url: str | None = None


class CarteReview(_CarteModel):
    place_id: str
    place_label_fr: str
    plate_url: str | None = None
    week: str
    headline_fr: str | None = None
    words: list[CarteReviewWord]
    items: list[CarteReviewItem]


class CarteReviewGradeRequest(_CarteModel):
    item_id: str
    tile_ids: list[str] | None = None
    text: str | None = None
    assisted: bool = False


class CarteReviewResult(_CarteModel):
    progress_id: str
    word_id: int
    correct: bool
    rating: int
    due_at: str | None = None


class CarteReviewGrade(_CarteModel):
    item_id: str
    task_type: str
    results: list[CarteReviewResult]
    #: Due words left at this place; 0 → the dot is gone.
    remaining: int
