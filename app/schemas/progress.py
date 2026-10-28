"""Pydantic models for learner progress endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    """Payload for submitting a review."""

    word_id: int = Field(..., ge=1)
    rating: int = Field(..., ge=0, le=3, description="FSRS rating from 0 (Again) to 3 (Easy)")
    response_time_ms: int | None = Field(None, ge=0)


class ReviewResponse(BaseModel):
    """Response after scheduling a review."""

    word_id: int
    state: str
    stability: float
    difficulty: float
    scheduled_days: int
    next_review: datetime


class ProgressDetail(BaseModel):
    """Detailed view of a learner's progress for a word."""

    word_id: int
    state: str
    stability: float | None
    difficulty: float | None
    scheduled_days: int | None
    next_review: datetime | None
    last_review: datetime | None
    reps: int
    lapses: int
    correct_count: int
    incorrect_count: int
    hint_count: int
    proficiency_score: int
    reviews_logged: int


class QueueWord(BaseModel):
    """Vocabulary entry returned in the review queue."""

    word_id: int
    word: str
    language: str
    english_translation: str | None = None
    german_translation: str | None = None
    french_translation: str | None = None
    part_of_speech: str | None = None
    difficulty_level: int | None = None
    state: str
    next_review: datetime | None = None
    scheduled_days: int | None = None
    is_new: bool
    scheduler: str | None = None


class UnifiedQueueItem(BaseModel):
    """Cross-mode learning item returned by the unified SRS queue."""

    id: str
    item_type: str
    priority_score: float
    display_title: str
    display_subtitle: str
    level: str
    due_since_days: int
    estimated_seconds: int
    original_id: str | int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedQueueTypeSummary(BaseModel):
    """Due-count summary for one SRS item type."""

    due: int
    new: int = 0
    minutes: int


class UnifiedQueueSummary(BaseModel):
    """Unified workload summary across vocabulary, grammar, and errata."""

    total_due: int
    total_new: int = 0
    estimated_minutes: int
    by_type: dict[str, UnifiedQueueTypeSummary]


class UnifiedQueueResponse(BaseModel):
    """Unified SRS queue response."""

    summary: UnifiedQueueSummary
    queue: list[UnifiedQueueItem]
    interleaving_mode: str
    time_budget_minutes: int | None = None


class CEFRProgressResponse(BaseModel):
    """Visible CEFR estimate, threshold breakdown, and forecast."""

    version: str
    estimate: str
    #: WP-25. "declared" = the learner said so and nothing has verified it;
    #: "placement" = a graded five-minute placement; "measured" = in-app work.
    #: Absent from the response schema until WP-25, which meant Le Releve's
    #: unverified branch could never fire -- the field was computed and dropped.
    estimate_source: str | None = None
    declared_level: str | None = None
    placement: dict[str, Any] | None = None
    computed_estimate: str | None = None
    target: str
    next_level: str | None = None
    daily_minutes: int | None = None
    rhythm: str | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    #: WP-L7: the performance gates (no longer promotion thresholds).
    thresholds: dict[str, dict[str, float]] = Field(default_factory=dict)
    breakdown: dict[str, Any] = Field(default_factory=dict)
    #: WP-L7: «A1.1 · 60 %», the band's coverage and its épreuve.
    level_label: str | None = None
    coverage: dict[str, Any] | None = None
    checkpoint: dict[str, Any] | None = None
    release_floor: str | None = None
    #: WP-L8: an estimate (``status`` "prior" before 7 active days, "available" measured).
    forecast: dict[str, Any] | None = None
    rhythm_priors: dict[str, Any] | None = None
    today_delta: dict[str, Any] = Field(default_factory=dict)
    generated_at: str | None = None
    #: WP-95: Home's level line — the band's next can-do, and how many are pressed.
    next_can_do: dict[str, Any] | None = None
    can_dos_stamped: int | None = None
    can_dos_total: int | None = None


class LevelPlanLadderStep(BaseModel):
    band: str
    #: passed · credited · start (below the starting level) · current · ahead
    state: str
    #: The day the band closed (passed or credited).
    on: str | None = None
    goal: bool = False


class LevelPlanRule(BaseModel):
    """One grammar unit of the band in force, and what it still needs."""

    id: int
    external_id: str | None = None
    name: str
    #: The unit's title per locale (``en``, ``de``, ``fr``), when localised.
    titles: dict[str, str] = Field(default_factory=dict)
    #: new · introduced · practising · held (``concept_life.progress_stage``)
    stage: str
    #: The «Tenue» evidence still missing (``concept_life.held_missing``).
    missing: list[dict[str, Any]] = Field(default_factory=list)
    #: The opportunity today owes the unit: ``free_use`` · ``spaced`` · none.
    owed_today: str | None = None
    #: The soonest the unit can be held, every opportunity going right.
    earliest_held_on: str | None = None
    #: A unit not met yet: the soonest the plan's intake introduces it.
    introduce_from: str | None = None
    held_on: str | None = None


class LevelPlanRules(BaseModel):
    held: int
    required: int
    total: int
    to_go: int
    met: bool
    practising: int
    introduced: int
    not_started: int
    owed_today: int
    #: New units a week the plan introduces.
    per_week: float
    items: list[LevelPlanRule] = Field(default_factory=list)


class LevelPlanWords(BaseModel):
    known: int
    required: int
    total: int
    to_go: int
    met: bool
    #: Band words with a card that is not known yet: they count once their reviews settle them.
    on_the_way: int
    #: Band words with no card and not read often enough.
    not_met: int
    #: New words still to meet once every word on its way counts.
    new_needed: int
    from_reading: int
    #: New words a day the plan introduces.
    per_day: int
    days_for_new: int


class LevelPlanEpreuve(BaseModel):
    band: str
    #: locked · ready · failed · passed · credited
    state: str
    attempts: int = 0
    retry_after: str | None = None
    staged_in_story: bool = False
    can_dos: int = 0


class LevelPlanTime(BaseModel):
    """How long the band in force still takes, and what that costs a day. Always an estimate."""

    #: measured (the last 14 days) · plan (the learner's plan, before 7 active days) · none
    status: str
    range_days: list[int] | None = None
    dates: list[str] | None = None
    capped: bool = False
    #: The rules' floor: no sooner than this, however much is practised.
    earliest_days: int | None = None
    earliest_on: str | None = None
    minutes_per_day: int | None = None
    #: measured (the last 14 days' practice) · plan (the Tempo sheet's arithmetic)
    minutes_source: str | None = None
    planned_minutes_per_day: int | None = None
    hours: list[int] | None = None
    active_days: int = 0
    active_days_required: int = 7
    pace: str | None = None
    pace_chosen: bool = False
    words_per_day: int = 0
    rules_per_week: float = 0.0


class LevelPlanInvested(BaseModel):
    """Practice time measured in the band in force (scenes, La Forge, the word deck)."""

    band_since: str | None = None
    band_minutes: int = 0
    band_days: int = 0
    scenes_minutes: int = 0
    forge_minutes: int = 0
    words_minutes: int = 0
    recent_minutes_per_day: float = 0.0


class LevelPlanReach(BaseModel):
    """How far one coverage criterion alone reaches, band by band from A1.1."""

    covered: str | None = None
    working: str | None = None
    percent: int | None = None
    #: The criterion's list ends before the next band (the core lexicon stops at B1).
    list_ends: bool = False


class LevelPlanGoal(BaseModel):
    """The learner's goal level (Réglages), when it is above the band in force."""

    band: str
    bands_left: int
    #: Every band from the one in force up to the goal, counted as its coverage counts.
    words_left: int
    units_left: int
    #: The Tempo sheet's weeks to the goal at the learner's pace (an estimate).
    weeks: float


class LevelPlanEvidence(BaseModel):
    """WP-45: a declared or placed level becomes measured after this many graded answers."""

    attempts_required: int
    #: Graded answers in the last 14 days.
    attempts_counted: int = 0


class LevelPlanResponse(BaseModel):
    """``GET /api/v1/progress/level`` — where the learner stands, what is left, what it costs."""

    version: str
    generated_at: str
    band: str
    next_band: str | None = None
    percent: int
    label: str
    estimate_source: str
    verified: bool
    placement_taken_at: str | None = None
    goal: LevelPlanGoal | None = None
    ladder: list[LevelPlanLadderStep] = Field(default_factory=list)
    rules: LevelPlanRules
    words: LevelPlanWords
    epreuve: LevelPlanEpreuve
    time: LevelPlanTime
    invested: LevelPlanInvested
    skills: dict[str, LevelPlanReach] = Field(default_factory=dict)
    evidence: LevelPlanEvidence | None = None
    can_dos: dict[str, Any] = Field(default_factory=dict)


class CarnetCanDo(BaseModel):
    id: str
    title_fr: str | None = None
    title_native: str | None = None
    stamped_at: str | None = None
    #: scene | epreuve | authored
    source: str | None = None
    scene_id: str | None = None
    scene_title_fr: str | None = None
    character_id: str | None = None
    quote_fr: str | None = None


class CarnetBand(BaseModel):
    band: str
    title_native: str
    can_dos: list[CarnetCanDo] = Field(default_factory=list)


class CarnetResponse(BaseModel):
    """WP-95 «Le Carnet» — ``GET /api/v1/can-dos``."""

    current_band: str | None = None
    bands: list[CarnetBand] = Field(default_factory=list)


class LevelCheckpointResultRequest(BaseModel):
    """WP-L7: the story engine reports the band's épreuve."""

    band: str = Field(pattern=r"^(A1\.1|A1\.2|A2\.1|A2\.2|B1\.1|B1\.2|B2\.1|B2\.2)$")
    passed: bool
    episode_id: str | None = Field(default=None, max_length=80)
    #: Free-form grading detail (can-dos met, concept evidence), kept on the row.
    evidence: dict[str, Any] | None = None


class VocabularyRecommendationTranslations(BaseModel):
    """Translation hints for a recommended vocabulary item."""

    de: str | None = None
    en: str | None = None
    fr: str | None = None


class VocabularyRecommendationItem(BaseModel):
    """Vocabulary card selected for today's SRS work."""

    bucket: str
    word_id: int
    progress_id: str | None = None
    word: str
    language: str
    direction: str | None = None
    scheduler: str | None = None
    state: str
    phase: str | None = None
    due_at: datetime | None = None
    next_review: datetime | None = None
    last_review: datetime | None = None
    scheduled_days: int | None = None
    interval_days: int | None = None
    stability: float | None = None
    difficulty: float | None = None
    retrievability: float | None = None
    proficiency_score: int = 0
    lapses: int = 0
    priority_score: float
    is_new: bool = False
    deck_name: str | None = None
    part_of_speech: str | None = None
    # Stored noun gender ("m" / "f"), or None when the catalogue does not know
    # it. The Lexique draws it as a shape (WP-D6); nothing is guessed here.
    gender: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    # The server already resolves which gloss this learner should read
    # (app/services/glosses.py). The response model used to drop those two
    # fields, so every client had to guess the language again from the raw map
    # — and guessed English-first, serving English to German learners. They are
    # part of the contract now; `translations` stays for older clients.
    translation: str | None = None
    translation_language: str | None = None
    translations: VocabularyRecommendationTranslations
    example_sentence: str | None = None
    example_translation: str | None = None
    #: WP-115b — the recall ladder: recognition | production | audio | cloze, or
    #: ``scene`` (the word's own line, first two reviews) / ``rescue`` (a leech).
    ladder: str | None = None
    scene_cue: dict[str, Any] | None = None
    leech: bool = False
    rescue_cue: dict[str, Any] | None = None
    recommendation_reason: dict[str, Any] | None = None
    episodic_anchor: dict[str, Any] | None = None


class VocabularyRecommendationSummary(BaseModel):
    """Counts for each recommendation bucket."""

    due: int
    fragile: int
    new: int
    total: int


class VocabularyRecommendationResponse(BaseModel):
    """Ranked vocabulary recommendations for the daily learning loop."""

    summary: VocabularyRecommendationSummary
    items: list[VocabularyRecommendationItem]
    algorithm: str = "fsrs_retrievability_v1"


class VocabularyDueContextSummary(BaseModel):
    """Selected counts for a contextual vocabulary review bundle."""

    due: int
    # Unsliced due count; `due` is capped by due_limit.
    due_total: int | None = None
    fragile: int
    new: int
    topic_compatible: int
    linked: int
    total: int


class VocabularyDueContextResponse(BaseModel):
    """Bucketed due-context vocabulary for mobile practice surfaces."""

    summary: VocabularyDueContextSummary
    due_words: list[VocabularyRecommendationItem]
    fragile_words: list[VocabularyRecommendationItem]
    new_words: list[VocabularyRecommendationItem]
    topic_compatible_words: list[VocabularyRecommendationItem]
    linked_words: list[VocabularyRecommendationItem]
    algorithm: str = "fsrs_retrievability_v1"
    #: WP-131: new words the day's allowance still holds after this deck (the
    #: rhythm's quota, throttled, minus today's introductions and the journey's
    #: share). The drill offers them as an explicit «Encore N mots» continuation.
    #: ``None`` when not read (a review-only «Encore» deck, a demo account).
    new_words_left_today: int | None = None


class VocabularyMasteryMapCell(BaseModel):
    """One tiny cell in the French 5000 mastery map."""

    word_id: int
    word: str
    frequency_rank: int | None = None
    mastery_state: str
    proficiency_score: int = 0
    is_due: bool = False
    lapses: int = 0


class VocabularyMasteryMapSummary(BaseModel):
    """Aggregate counts for the French 5000 mastery map."""

    total: int
    new: int
    due: int
    fragile: int
    building: int
    solid: int
    mastered: int


class VocabularyMasteryMapResponse(BaseModel):
    """Typographic map of the imported French 5000 deck."""

    summary: VocabularyMasteryMapSummary
    cells: list[VocabularyMasteryMapCell]
    deck_label: str = "French 5000"


class WeeklyDossierStats(BaseModel):
    """Deterministic weekly learning stats for the editorial progress mirror."""

    repairs_filed: int = 0
    vocabulary_reviews: int = 0
    words_seen: int = 0
    words_produced: int = 0
    missions_completed: int = 0
    feuilleton_scenes_completed: int = 0


class WeeklyDossierThread(BaseModel):
    """One highlighted strength, fragile item, or suggested next action."""

    title: str
    subtitle: str | None = None
    tone: str = "neutral"
    count: int = 0


class WeeklyDossierResponse(BaseModel):
    """Editorial weekly digest generated from local learning telemetry."""

    period_start: datetime
    period_end: datetime
    headline: str
    stats: WeeklyDossierStats
    strengths: list[WeeklyDossierThread]
    fragile_threads: list[WeeklyDossierThread]
    next_actions: list[WeeklyDossierThread]


class AnkiWordProgressRead(BaseModel):
    """Overview entry for an imported Anki card and its progress."""

    word_id: int
    word: str
    language: str
    direction: str | None = None
    french_translation: str | None = None
    german_translation: str | None = None
    deck_name: str | None = None
    difficulty_level: int | None = None
    english_translation: str | None = None
    learning_stage: str
    state: str
    progress_difficulty: float | None = None
    ease_factor: float | None = None
    interval_days: int | None = None
    due_at: datetime | None = None
    next_review: datetime | None = None
    last_review: datetime | None = None
    reps: int = 0
    lapses: int = 0
    proficiency_score: int = 0
    scheduler: str | None = None


class AnkiStageSlice(BaseModel):
    """Slice element for chart visualisation."""

    stage: str
    value: int


class AnkiDirectionSummary(BaseModel):
    """Per-direction breakdown for Anki progress."""

    direction: str
    total: int
    due_today: int
    stage_counts: dict[str, int]


class AnkiProgressSummary(BaseModel):
    """Aggregate Anki progress metrics."""

    total_cards: int
    due_today: int
    stage_totals: dict[str, int]
    chart: list[AnkiStageSlice]
    directions: dict[str, AnkiDirectionSummary]
