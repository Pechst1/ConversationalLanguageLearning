import { captureClientError, newRequestId } from '@/lib/observability';
import type { StoryEpisode, StoryEpisodePage } from "@/types/daily-journey";
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import toast from 'react-hot-toast';

import { getAppAccessToken } from '@/lib/app-auth';
import { audioUploadFilename } from '@/lib/audio-recording';
import { recoverNativeAccessToken } from '@/lib/native-auth';
import { isNativePlatform } from '@/lib/native-platform';
import type {
  AdvanceBody,
  AttemptBody,
  AttemptResult,
  CapabilityProgress,
  CreateJourneyBody,
  FinishBody,
  HelpBody,
  HelpResult,
  JourneyHttpResult,
  JourneySnapshot,
  RetryBody,
  RevisionBody,
  TodayEnvelope,
} from '@/types/daily-journey';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

/**
 * WP-32 — the radio episode's manifest.
 *
 * `status` is the whole contract: `disabled` (the flag is off — read the scene
 * as text), `absent` (nothing synthesized yet), `empty` (no speakable line),
 * `ready`, or `failed`. A `failed` manifest carries no clips on purpose: half a
 * scene played aloud is a comprehension test nobody can pass.
 */
export interface EpisodeAudioClipRef {
  id: string;
  line_key: string;
  ordinal: number;
  character_id: string;
  voice: string;
  content_type: string;
  char_count: number;
  text_fr: string;
}

export interface EpisodeAudioManifest {
  status: 'disabled' | 'absent' | 'empty' | 'ready' | 'failed';
  revision: string;
  clips: EpisodeAudioClipRef[];
  truncated: boolean;
  reason: string;
}

export interface EpisodePredictionRecord {
  guess: string;
  verdict: string;
  supported: string | null;
}

/**
 * How the story engine addresses the reader in French. 'neutral' is the default
 * and asks the récit to avoid gendered forms and endearments altogether.
 */
export type AddressPreference = 'feminine' | 'masculine' | 'neutral';

export interface LiveStory {
  id: string;
  title: string;
  url: string;
  source: string;
  summary?: string | null;
  language: string;
}

export interface LiveStoryListResponse {
  items: LiveStory[];
  topics_used: string[];
}

export interface LibraryBook {
  id: string;
  title: string;
  author?: string | null;
  source_filename?: string | null;
  source_type: string;
  source_hash: string;
  target_level: string;
  status: string;
  status_message?: string | null;
  error_message?: string | null;
  progress_percent: number;
  total_episodes: number;
  current_episode_index: number;
  completed_episode_indices: number[];
  completion_percentage: number;
  estimated_total_words: number;
  task_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  ready_at?: string | null;
  episodes?: LibraryEpisode[];
}

export interface LibraryEpisode {
  id: string;
  book_id: string;
  order_index: number;
  title: string;
  est_reading_minutes: number;
  cefr_level: string;
  word_count: number;
  vocab_seed: Array<Record<string, any>>;
  grammar_seed: Array<Record<string, any>>;
  exercise_payload: Record<string, any>;
  status: string;
  is_completed: boolean;
  passage_text?: string;
  passage_preview?: string;
}

export interface AtelierConcept {
  id: number;
  external_id?: string | null;
  name: string;
  /** French publication title (grammar_concept_localizations fr row). */
  title_fr?: string | null;
  level: string;
  category?: string | null;
  subskill?: string | null;
  core_rule?: string | null;
  main_traps: string[];
  anchor_examples: string[];
  exercise_tags: string[];
  is_foundation: boolean;
  role?: string | null;
  mastery: number;
  next_review?: string | null;
  due_errata?: AtelierErratum[];
  atelier_blueprint?: Record<string, any> | null;
}

export interface AtelierErratum {
  id?: string;
  item_id?: string | null;
  concept_id?: number | null;
  source_attempt_id?: string | null;
  display_label: string;
  task_error_type?: string;
  error_category?: string;
  review_mode?: string;
  source_type?: string;
  source_label?: string;
  memory_key?: string;
  linked_word_id?: number | null;
  reason?: string;
  metadata?: Record<string, any>;
  learner_text?: string | null;
  corrected_target?: string | null;
  why_wrong?: string | null;
  repair_hint?: string | null;
  next_review_date?: string | null;
  last_review_date?: string | null;
  occurrences?: number;
  lapses?: number;
  state?: string;
  recurring?: boolean;
  severity?: number;
}

export interface AtelierToday {
  concepts: AtelierConcept[];
  quote: Record<string, any>;
  summary: Record<string, any>;
  atlas: Array<Record<string, any>>;
  due_errata: AtelierErratum[];
  progress?: AtelierDayProgress | null;
  cefr?: CEFRProgress | null;
  onboarding?: {
    serial_seen?: boolean;
    serial_edition_notifications?: boolean;
  } | null;
  serial_episode?: Record<string, any> | null;
  serial?: Record<string, any> | null;
  library_episode?: Record<string, any> | null;
  phrase_of_day?: {
    text: string;
    byline: string;
    session_date: string;
    paru: boolean;
  } | null;
}

export interface AtelierDayProgress {
  errataDue: number;
  vocabularyDue: number;
  missionDone: boolean;
  missionSuggested?: boolean;
  libraryDone?: boolean;
  librarySuggested?: boolean;
  feuilletonDone: boolean;
  sessionDone?: boolean;
  timeBudgetMinutes?: number;
  estimatedTotalMinutes?: number;
  estimatedRemainingMinutes?: number;
  filed?: boolean;
  nodes?: Array<{
    id: string;
    label: string;
    estimatedMinutes: number;
    done?: boolean;
    suggested?: boolean;
  }>;
}

/** WP-25 — the placement result the level payload carries, when there is one. */
export interface PlacementPrior {
  level: string;
  confidence: number;
  taken_at?: string | null;
  graded_turns?: number;
  version?: string;
}

/* ---- WP-25 placement (POST /placement/*) ---------------------------------- */

export interface PlacementPromptView {
  index: number;
  band: string;
  prompt_fr: string;
  hint_fr: string;
  turns_so_far: number;
  max_turns: number;
}

export interface PlacementEnvelope {
  version: string;
  session_id?: string | null;
  /** 'none' | 'in_progress' | 'complete' | 'unassessed' | 'skipped' | 'abandoned' */
  status: string;
  /** True only while the learner has neither taken nor declined a placement. */
  offer: boolean;
  prompt?: PlacementPromptView | null;
  estimate?: {
    status: string;
    level: string | null;
    confidence: number;
    graded_turns: number;
    dimensions: Record<string, number>;
    dimension_labels: Record<string, string>;
    evidence: Array<Record<string, any>>;
  } | null;
  level?: string | null;
  confidence: number;
  prior?: PlacementPrior | null;
}

/* ---- WP-30 «Le journal de bord» (GET/POST /journal/*) ---------------------
   The learner writes the recap from memory. The envelope's one load-bearing
   omission: while `status` is 'offered' the entry carries `cue` — who, where,
   how long ago — and NO scene text. `reveal` only ever arrives once the entry
   has been written, which is why it is a separate object rather than fields on
   the cue. Do not merge the two. */

export interface JournalCue {
  character_name?: string | null;
  location_name?: string | null;
  scene_date?: string | null;
  days_ago?: number | null;
}

export interface JournalReveal {
  title_fr?: string | null;
  setup_fr?: string | null;
  character_line_fr?: string | null;
  callback_fr?: string | null;
}

export interface JournalCorrectionItem {
  label: string;
  span_fr: string;
  corrected_fr: string;
  note_native: string;
  repair_hint?: string;
  task_error_type?: string;
}

export interface JournalCorrection {
  /** 'checked' — a real verdict. 'unavailable' — nobody graded it, and it says so. */
  assessment_status: string;
  assessment_truncated: boolean;
  verdict?: string | null;
  corrected_answer: string;
  explanation_language?: string | null;
  /** The one correction shown up front, chosen by the journey's own policy. */
  foreground?: JournalCorrectionItem | null;
  /** Every correction, for the "tout voir" disclosure. Never silently trimmed. */
  errata: JournalCorrectionItem[];
}

export interface JournalContentRecall {
  version: string;
  /** 'scored' | 'no_facts' — a scene with nothing stored scores null, not zero. */
  status: string;
  score: number | null;
  matched: Array<{ key?: string; kind?: string; text_fr?: string; cues_hit?: string[] }>;
  missed: Array<{ key?: string; kind?: string; text_fr?: string; cues_hit?: string[] }>;
  facts_total: number;
}

export interface JournalEntryView {
  id: string;
  /** 'offered' | 'written' | 'unavailable' | 'skipped' */
  status: string;
  scene_date: string;
  offered_on: string;
  followup_due_on: string;
  cue: JournalCue;
  prompt_fr: string;
  entry_text?: string | null;
  correction?: JournalCorrection | null;
  content_recall?: JournalContentRecall | null;
  reaction_fr?: string | null;
  reveal?: JournalReveal | null;
  vocabulary_credit?: { status?: string; credited?: string[]; skipped_flagged?: string[]; reason?: string } | null;
  errata_recorded: number;
}

export interface JournalFollowup {
  entry_id: string;
  prompt_fr: string;
  due_on: string;
  answered: boolean;
  text?: string | null;
  /** 'used_again_later' | 'not_recalled' | null */
  signal?: string | null;
}

export interface JournalEnvelope {
  version: string;
  /** 'none' | 'offered' | 'written' | 'unavailable' | 'skipped' */
  status: string;
  entry?: JournalEntryView | null;
  followup?: JournalFollowup | null;
  recall_offset_days: number;
  followup_offset_days: number;
  min_entry_words: number;
}

/* ---- WP-31 rehearsal (POST /rehearsals/*) ---------------------------------
   «Répétition»: the learner's own real upcoming situation, rehearsed once and
   then debriefed. Not story canon — the server keeps it in its own table and
   never writes it into serial memory, and nothing here carries a story id. */

export interface RehearsalBriefView {
  goal_fr: string;
  goal_native: string;
  counterpart: string;
  /** 'tu' | 'vous', decided by the server from who the counterpart is. */
  register: string;
  date_text: string;
  date_iso?: string | null;
  facts: string[];
}

export interface RehearsalSceneView {
  title_fr: string;
  place_fr: string;
  setup_fr: string;
  setup_native: string;
  objective_fr: string;
  objective_native: string;
  opening_line_fr: string;
  register: string;
  level_band: string;
  turns_total: number;
  /** Empty until the learner asks for them: help is a request, not a panel. */
  phrases: Array<{ fr: string; native: string }>;
  phrases_revealed: boolean;
  /** Null while the rehearsal is live — the private rubric is never a spoiler. */
  rubric_native?: string | null;
}

export interface RehearsalTurnView {
  index: number;
  learner_text: string;
  mode: string;
  reply_fr?: string | null;
  reply_source?: string | null;
  correction?: { span_fr: string; corrected_fr: string; note_native: string } | null;
  outcome?: string | null;
  evidence_kind?: string | null;
  assistance?: string | null;
}

export interface RehearsalView {
  version: string;
  id: string;
  /** declared | ready | not_prepared | rehearsing | rehearsed | debriefed | abandoned */
  status: string;
  declaration: string;
  brief: RehearsalBriefView;
  scene?: RehearsalSceneView | null;
  turns: RehearsalTurnView[];
  turns_used: number;
  turns_total: number;
  result?: {
    outcome: string;
    points_total: number;
    points_covered: number;
    ending_key?: string | null;
    ending_line_fr?: string | null;
    ending_summary_fr?: string | null;
  } | null;
  event_date?: string | null;
  debrief?: {
    outcome: string;
    free_line: string;
    corrected_fr?: string | null;
    note_fr?: string | null;
    already_correct?: boolean | null;
    /** False means the line was NOT checked — never that it was correct. */
    correction_available: boolean;
    recorded_at: string;
  } | null;
  outcome?: string | null;
  debrief_available: boolean;
}

export interface RehearsalEnvelope {
  version: string;
  rehearsal?: RehearsalView | null;
  debrief_due?: RehearsalView | null;
  cap: { limit: number; used: number; remaining: number; next_slot_at?: string | null };
  min_turns: number;
  max_turns: number;
}

/* ---- WP-35 «Votre dossier» — the inspectable learner model ----------------
   Every section carries the evidence that produced it (a journey id, a date),
   because the page's whole claim is that the model can be checked. */

export interface DossierEvidence {
  /** journey | placement | declaration | in_app_counters | erratum | vocabulary_schedule */
  kind: string;
  on?: string | null;
  journey_id?: string | null;
  reference?: string | null;
  detail?: string | null;
}

export interface DossierLevel {
  available: boolean;
  estimate?: string | null;
  /** 'declared' | 'placement' | 'measured' — WP-25's own field, unchanged. */
  estimate_source?: string | null;
  declared_level?: string | null;
  /** True only when in-app counters back the level; a placement does not. */
  verified?: boolean;
  status?: string | null;
  /** `null` for a declaration: a dropdown has no confidence. */
  confidence?: number | null;
  breakdown?: Record<string, any>;
  placement?: {
    id: string;
    level?: string | null;
    confidence: number;
    taken_at?: string | null;
    graded_turns: number;
    dimensions: Record<string, number>;
    dimension_labels: Record<string, string>;
  } | null;
  target?: string | null;
  next_level?: string | null;
  evidence?: DossierEvidence | null;
  reason?: string | null;
}

export interface DossierCapabilityEvidence {
  on: string;
  modality: string;
  state: string;
  context: string;
  journey_id?: string | null;
}

export interface DossierCapability {
  key: string;
  title: string;
  /** The CONTRACTS §8 rubric, produced by `build_capability_summary` alone. */
  state: string;
  rubric_version: string;
  modalities: string[];
  latest_qualifying_on?: string | null;
  evidence: DossierCapabilityEvidence[];
}

export interface DossierErratum {
  id: string;
  label: string;
  /** WP-24: open | repairing | mastered. */
  state: string;
  learner_text?: string | null;
  corrected_target?: string | null;
  why_wrong?: string | null;
  occurrences: number;
  lapses: number;
  mastery_streak: number;
  mastery_target: number;
  next_review_date?: string | null;
  claimable: boolean;
  evidence?: DossierEvidence | null;
}

export interface DossierErrata {
  available: boolean;
  mastery_target?: number;
  counts?: Record<string, number>;
  by_state?: Record<string, DossierErratum[]>;
  reason?: string | null;
}

export interface DossierWord {
  word_id: number;
  word: string;
  translation?: string | null;
  bucket?: string | null;
  claimable: boolean;
  evidence?: DossierEvidence | null;
}

export interface DossierVocabulary {
  available: boolean;
  known?: {
    version: string;
    band: string;
    estimate_level: string;
    estimate_source: string;
    nailed_words: number;
    core_words: number;
    known_lemmas: number;
  } | null;
  nailed_rule?: { retrievability: number };
  words: DossierWord[];
}

export interface DossierBecause {
  kind: string;
  reason?: string | null;
  label: string;
  example?: string | null;
}

export interface DossierToday {
  has_journey: boolean;
  journey_id?: string | null;
  local_date?: string | null;
  status?: string | null;
  /** Read from the plan that produced today's scene, never recomputed. */
  because?: DossierBecause | null;
  evidence?: DossierEvidence | null;
}

export interface DossierClaim {
  kind?: string | null;
  target_id?: string | null;
  stage?: string | null;
  verdict?: string | null;
  label?: string | null;
  on?: string | null;
}

export interface DossierPayload {
  version: string;
  level: DossierLevel;
  capabilities: DossierCapability[];
  errata: DossierErrata;
  vocabulary: DossierVocabulary;
  today: DossierToday;
  claims: DossierClaim[];
}

export interface DossierClaimItem {
  index: number;
  /** repair | cloze | production | meaning */
  kind: string;
  instruction_fr: string;
  prompt_fr: string;
  placeholder_fr: string;
}

export interface DossierClaimCheck {
  kind: string;
  target_id: string;
  label: string;
  verifiable: boolean;
  items_required: number;
  items: DossierClaimItem[];
  reason?: string | null;
  message_fr?: string | null;
}

export interface DossierClaimVerdict {
  kind: string;
  target_id: string;
  /** verified | not_yet | unverifiable */
  verdict: string;
  items_correct: number;
  items_total: number;
  advanced: boolean;
  message_fr: string;
  next_review_date?: string | null;
  state?: string | null;
  results: { index: number; kind: string; is_correct: boolean }[];
}

export interface DossierEnvelope {
  version: string;
  dossier?: DossierPayload | null;
  check?: DossierClaimCheck | null;
  verdict?: DossierClaimVerdict | null;
  items_required: number;
  claim_kinds: string[];
}

export interface CEFRProgress {
  version: string;
  estimate: string;
  /**
   * 'declared'  — the learner stated this level and nothing has verified it.
   * 'placement' — a graded five-minute placement measured it (WP-25).
   * 'measured'  — enough in-app work exists to measure it directly.
   */
  estimate_source?: 'declared' | 'placement' | 'measured' | null;
  declared_level?: string | null;
  placement?: PlacementPrior | null;
  computed_estimate?: string | null;
  target: string;
  next_level?: string | null;
  daily_minutes?: number | null;
  signals: Record<string, any>;
  thresholds: Record<string, Record<string, number>>;
  breakdown: Record<string, any>;
  forecast?: Record<string, any> | null;
  today_delta?: Record<string, any>;
  generated_at?: string | null;
}

/** GET /analytics/summary — headline counters, all scoped to the signed-in learner. */
export interface LearnerAnalyticsSummary {
  sessions_completed: number;
  total_minutes: number;
  average_minutes: number;
  xp_earned: number;
  accuracy_rate?: number | null;
  current_streak: number;
  longest_streak: number;
  words_learning: number;
  words_mastered: number;
  reviews_due_today: number;
  reviews_due_week: number;
  last_session_at?: string | null;
}

/** GET /grammar/summary — the learner's own UserGrammarProgress rows.
 *  `state_counts` keys are the German SRS machine keys (neu / ausbaufähig /
 *  in_arbeit / gefestigt / gemeistert) and must be mapped before display. */
export interface GrammarProgressSummary {
  total_concepts: number;
  started: number;
  due_today: number;
  new_available: number;
  state_counts: Record<string, number>;
  level_counts: Record<string, number>;
}

/** GET /achievements/my — unlocked achievements unless `include_locked` is set.
 *  `name`/`description` are seeded in English; publication surfaces map
 *  `achievement_key` to French copy instead of printing them. */
export interface UserAchievementProgress {
  achievement_id: number;
  achievement_key: string;
  name: string;
  description?: string | null;
  tier: string;
  xp_reward: number;
  icon_url?: string | null;
  current_progress: number;
  target_progress: number;
  completed: boolean;
  unlocked_at?: string | null;
}

export interface UnifiedSRSItem {
  id: string;
  item_type: 'vocab' | 'grammar' | 'error' | string;
  priority_score: number;
  display_title: string;
  display_subtitle: string;
  level: string;
  due_since_days: number;
  estimated_seconds: number;
  original_id?: string | number | null;
  metadata: Record<string, any>;
}

export interface UnifiedSRSQueue {
  summary: {
    total_due: number;
    total_new: number;
    estimated_minutes: number;
    by_type: Record<string, { due: number; new: number; minutes: number }>;
  };
  queue: UnifiedSRSItem[];
  interleaving_mode: string;
  time_budget_minutes?: number | null;
}

export interface VocabularyRecommendationSummary {
  due: number;
  fragile: number;
  new: number;
  total: number;
}

export interface VocabularyRecommendationItem {
  bucket: 'due' | 'fragile' | 'new' | 'linked' | 'topic' | 'topic_compatible' | string;
  recommendation_reason?: { text: string; signals: Record<string, any> };
  episodic_anchor?: {
    character_name?: string;
    portrait_url?: string;
    accent_colour?: string;
    source?: string;
  };
  word_id: number;
  progress_id?: string | null;
  word: string;
  translation?: string | null;
  language: string;
  direction?: string | null;
  scheduler?: string | null;
  state: string;
  phase?: string | null;
  due_at?: string | null;
  next_review?: string | null;
  scheduled_days?: number | null;
  interval_days?: number | null;
  stability?: number | null;
  difficulty?: number | null;
  retrievability?: number | null;
  proficiency_score: number;
  lapses: number;
  priority_score: number;
  is_new: boolean;
  deck_name?: string | null;
  part_of_speech?: string | null;
  topic_tags?: string[];
  translations: {
    de?: string | null;
    en?: string | null;
    fr?: string | null;
  };
  example_sentence?: string | null;
  example_translation?: string | null;
}

export interface VocabularyRecommendations {
  summary: VocabularyRecommendationSummary;
  items: VocabularyRecommendationItem[];
  algorithm: string;
}

export interface VocabularyRecommendationParams {
  limit?: number;
  due_limit?: number;
  fragile_limit?: number;
  new_limit?: number;
  direction?: string;
}

export interface VocabularyDueContextSummary extends VocabularyRecommendationSummary {
  topic_compatible: number;
  linked: number;
  /** Total due before the endpoint's own limit is applied (see progress.py). */
  due_total?: number;
}

export interface VocabularyDueContext {
  summary: VocabularyDueContextSummary;
  due_words: VocabularyRecommendationItem[];
  fragile_words: VocabularyRecommendationItem[];
  new_words: VocabularyRecommendationItem[];
  topic_compatible_words: VocabularyRecommendationItem[];
  linked_words: VocabularyRecommendationItem[];
  algorithm: string;
}

export interface DailyWordEntry {
  word_id: number;
  word: string;
  translation?: string | null;
  bucket?: string;
  example_sentence?: string | null;
  example_translation?: string | null;
  anchor?: string | null;
  stamps?: Partial<Record<'lu' | 'retrouve' | 'place', string | null>>;
  triple?: boolean;
}

export interface DailyWordSlate {
  date: string;
  words: DailyWordEntry[];
  triples: number;
  version?: string;
}

export interface VocabularyDueContextParams extends VocabularyRecommendationParams {
  topic_limit?: number;
  linked_limit?: number;
  topic_tags?: string[] | string;
  linked_word_ids?: number[] | string;
  mission_id?: string;
  feuilleton_scene_id?: string;
}

export interface VocabularyWord {
  id: number;
  language: string;
  word: string;
  normalized_word: string;
  part_of_speech?: string | null;
  gender?: string | null;
  frequency_rank?: number | null;
  english_translation?: string | null;
  definition?: string | null;
  example_sentence?: string | null;
  example_translation?: string | null;
  usage_notes?: string | null;
  difficulty_level?: number | null;
  german_translation?: string | null;
  french_translation?: string | null;
  topic_tags: string[];
  /** Resolved server-side for the signed-in learner — render this, not the raw
   * columns above (see lib/glosses.ts). */
  translation?: string | null;
  translation_language?: string | null;
}

export interface VocabularyBiographyOrigin {
  label: string;
  source_type: string;
  deck_name?: string | null;
  imported: boolean;
  frequency_rank?: number | null;
  created_at?: string | null;
}

export interface VocabularyBiographyProgress {
  progress_id?: string | null;
  scheduler?: string | null;
  state: string;
  phase?: string | null;
  due_at?: string | null;
  next_review?: string | null;
  last_review?: string | null;
  scheduled_days?: number | null;
  interval_days?: number | null;
  stability?: number | null;
  difficulty?: number | null;
  retrievability?: number | null;
  proficiency_score: number;
  reps: number;
  lapses: number;
  times_seen: number;
  times_used_correctly: number;
  times_used_incorrectly: number;
  fragility_level: string;
  fragility_label: string;
  fragility_reason?: string | null;
}

export interface VocabularyBiographyExample {
  sentence: string;
  translation?: string | null;
  source: string;
  occurred_at?: string | null;
}

export interface VocabularyBiographyEvent {
  id: string;
  event_type: string;
  label: string;
  description?: string | null;
  occurred_at?: string | null;
  source_type: string;
  source_id?: string | null;
  metadata: Record<string, any>;
}

export interface VocabularyBiography {
  word: VocabularyWord;
  origin: VocabularyBiographyOrigin;
  progress: VocabularyBiographyProgress;
  examples: VocabularyBiographyExample[];
  linked_errata_count: number;
  context_event_count: number;
  timeline: VocabularyBiographyEvent[];
}

export interface VocabularyMasteryMapCell {
  word_id: number;
  word: string;
  frequency_rank?: number | null;
  mastery_state: 'new' | 'due' | 'fragile' | 'building' | 'solid' | 'mastered' | string;
  proficiency_score: number;
  is_due: boolean;
  lapses: number;
}

export interface VocabularyMasteryMapSummary {
  total: number;
  new: number;
  due: number;
  fragile: number;
  building: number;
  solid: number;
  mastered: number;
}

export interface VocabularyMasteryMap {
  summary: VocabularyMasteryMapSummary;
  cells: VocabularyMasteryMapCell[];
  deck_label: string;
}

export interface CoverageBand {
  band: string;
  label?: string;
  nailed: number;
  total: number;
  percent: number;
}

export interface CoverageTrack {
  id: string;
  label: string;
  track: string;
  unit?: string;
  nailed: number;
  total: number;
  percent: number;
  cefr_bands?: CoverageBand[];
  href?: string;
  example_words?: string[];
  [key: string]: any;
}

export interface VocabularyCoverage {
  cefr_bar: CoverageBand[];
  categories: CoverageTrack[];
  verb_tracks: CoverageTrack[];
  grammar_tracks: CoverageTrack[];
  next_best_set: Record<string, any>;
  nailed_rule: Record<string, any>;
}

export interface ConjugationReviewItem {
  id: string;
  lemma: string;
  normalized_lemma: string;
  tense: string;
  tense_label: string;
  person: string;
  prompt: string;
  answer: string;
  cefr_band: string;
  is_irregular: boolean;
  progress_id?: string | null;
  state: string;
  reps: number;
  lapses: number;
  due_at?: string | null;
  table: Array<{ person: string; form: string; tense: string; tense_label: string; auxiliary?: string | null }>;
}

export interface ConjugationReviewQueue {
  items: ConjugationReviewItem[];
  summary: { total: number; due: number; new: number; due_total?: number };
  algorithm: string;
}

export interface ConjugationReviewResponse {
  lemma: string;
  tense: string;
  state: string;
  proficiency_score: number;
  reps: number;
  lapses: number;
  next_review?: string | null;
}

export interface WeeklyDossierStats {
  repairs_filed: number;
  vocabulary_reviews: number;
  words_seen: number;
  words_produced: number;
  missions_completed: number;
  feuilleton_scenes_completed: number;
}

export interface WeeklyDossierThread {
  title: string;
  subtitle?: string | null;
  tone: string;
  count: number;
}

export interface WeeklyDossier {
  period_start: string;
  period_end: string;
  headline: string;
  stats: WeeklyDossierStats;
  strengths: WeeklyDossierThread[];
  fragile_threads: WeeklyDossierThread[];
  next_actions: WeeklyDossierThread[];
}

export interface VocabularyListResponse {
  total: number;
  items: VocabularyWord[];
}

export interface AtelierAttemptRead {
  attempt_id: string;
  session_id: string;
  concept_id?: number | null;
  round: 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation';
  mode: string;
  exercise_id: string;
  prompt_payload: Record<string, any>;
  answer_payload: Record<string, any>;
  correction: Record<string, any>;
  ai_review?: Record<string, any>;
  verdict: string;
  score_0_4: number;
  submitted_key: string;
  submitted_keys?: string[];
  created_at?: string | null;
}

export interface AtelierSessionStart {
  session_id: string;
  status: string;
  concepts: AtelierConcept[];
  quote: Record<string, any>;
  target_vocabulary_ids: number[];
  target_vocabulary: VocabularyRecommendationItem[];
  exercise_sets: Array<{
    id: string;
    concept_id: number;
    generator_version: string;
    source: string;
    payload: Record<string, any>;
  }>;
  attempts: AtelierAttemptRead[];
  submitted_map: Record<string, boolean>;
  current_position: {
    round?: 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation' | 'complete';
    mode?: string;
    concept_id?: number | null;
    concept_index?: number;
    item_id?: string | null;
    item_index?: number;
    item_count?: number;
  };
  due_errata: AtelierErratum[];
  recap: Record<string, any>;
  learning_moments?: {
    adaptive_locks?: Record<string, Record<string, any>>;
  };
}

export interface AtelierAttemptResult {
  attempt_id: string;
  verdict: string;
  score_0_4: number;
  correction: Record<string, any>;
  ai_review?: Record<string, any>;
  minted_collectibles?: AtelierCollectible[];
}

export interface AtelierErrataReviewTask {
  error_id: string;
  display_label: string;
  review_mode: string;
  source_type?: string;
  source_label?: string;
  reason?: string;
  instruction: string;
  prompt: string;
  placeholder: string;
  learner_text?: string | null;
  why_wrong?: string | null;
  repair_hint?: string | null;
  /** The pre-attempt task deliberately carries no target_answer -- it would be
   *  the answer to the exercise. It is returned by the attempt result instead. */
  review_mode_label?: string;
  occurrences?: number;
  lapses?: number;
  next_review_date?: string | null;
}

export interface AtelierErrataAttemptResult {
  verdict: string;
  score_0_4: number;
  is_correct: boolean;
  answer_text: string;
  target_answer: string;
  feedback: string;
  closure?: {
    label: string;
    detail?: string | null;
    filed_at?: string | null;
    next_review_date?: string | null;
    state?: string | null;
  } | null;
  erratum: AtelierErratum;
  task: AtelierErrataReviewTask;
}

export interface GrammarNotebookProgress {
  score: number;
  reps: number;
  state: string;
  state_label: string;
  notes?: string | null;
  last_review?: string | null;
  next_review?: string | null;
}

export interface GrammarNotebookItem {
  id: number;
  external_id?: string | null;
  language: string;
  name: string;
  display_title: string;
  localized_title?: string | null;
  localized_category?: string | null;
  title_fr?: string | null;
  category_label_fr?: string | null;
  localized_subskill?: string | null;
  level: string;
  category?: string | null;
  subskill?: string | null;
  catalog_version?: string | null;
  source_refs?: Record<string, any>;
  is_foundation: boolean;
  active: boolean;
  mastery: number;
  state: string;
  state_label: string;
  next_review?: string | null;
  due_errata_count: number;
  recent_errata_count: number;
  motif?: Record<string, any>;
  blueprint_status?: string | null;
  blueprint_quality?: Record<string, any>;
}

export interface GrammarNotebookDetail extends GrammarNotebookItem {
  core_rule?: string | null;
  main_traps: string[];
  anchor_examples: string[];
  exercise_tags: string[];
  description?: string | null;
  examples?: string | null;
  atelier_blueprint?: Record<string, any>;
  progress?: GrammarNotebookProgress | null;
  due_errata: AtelierErratum[];
  recent_errata: AtelierErratum[];
  personal_notes?: string | null;
}

export interface DueGrammarConcept {
  id: number;
  name: string;
  level: string;
  category?: string | null;
  description?: string | null;
  current_score?: number | null;
  current_state: string;
  reps: number;
}

export interface MissionTargetVocabulary {
  word_id: number;
  word: string;
  translation?: string | null;
  bucket?: string | null;
  scheduler?: string | null;
  priority_score?: number | null;
  example_sentence?: string | null;
  example_translation?: string | null;
}

export interface VocabularyCreditSummary {
  seen_context: number;
  recognized: number;
  produced_correct: number;
  produced_incorrect: number;
  missed_target: number;
  [key: string]: number;
}

export interface VocabularyEvent {
  word_id: number;
  event_type: 'seen_context' | 'recognized' | 'produced_correct' | 'produced_incorrect' | 'missed_target' | string;
  reason?: string | null;
  [key: string]: any;
}

export interface LinkedVocabularyErratum extends AtelierErratum {
  linked_word_id?: number | null;
  error_category?: string;
  review_mode?: string;
  task_error_type?: string;
}

export interface VocabularyCorrectionPayload extends Record<string, any> {
  errata: LinkedVocabularyErratum[];
  vocabulary_events: VocabularyEvent[];
}

export interface VocabularyRecapPayload extends Record<string, any> {
  vocabulary_credit: VocabularyCreditSummary;
}

export interface SessionTargetWord {
  word_id: number;
  word: string;
  translation?: string | null;
  is_new: boolean;
  familiarity?: 'new' | 'learning' | 'familiar' | null;
  hint_sentence?: string | null;
  hint_translation?: string | null;
}

export interface SessionLearningFocus {
  kind: 'vocabulary' | 'grammar' | 'error';
  key: string;
  title: string;
  subtitle?: string | null;
  state?: string | null;
  priority: number;
  metadata: Record<string, any>;
}

export interface SessionDetectedError {
  code: string;
  message: string;
  span: string;
  suggestion?: string | null;
  category: string;
  severity: string;
  confidence: number;
  occurrence_count?: number;
  last_seen?: string | null;
  is_recurring?: boolean;
}

export interface SessionErrorFeedback {
  summary: string;
  errors: SessionDetectedError[];
  review_vocabulary: string[];
  metadata: Record<string, any>;
  error_stats?: Array<Record<string, any>>;
}

export interface SessionMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  sequence_number: number;
  created_at: string;
  xp_earned: number;
  target_words: number[];
  words_used: number[];
  suggested_words_used: number[];
  error_feedback?: SessionErrorFeedback | null;
  target_details: SessionTargetWord[];
  learning_focus: SessionLearningFocus[];
  pending_moment?: Record<string, any> | null;
}

export interface SessionOverview {
  id: string;
  status: string;
  topic?: string | null;
  conversation_style?: string | null;
  anki_direction?: string | null;
  planned_duration_minutes: number;
  xp_earned: number;
  words_practiced: number;
  accuracy_rate?: number | null;
  started_at: string;
  completed_at?: string | null;
}

export interface AssistantTurn {
  message: SessionMessage;
  targets: SessionTargetWord[];
  targeted_errors: Array<Record<string, any>>;
  learning_focus: SessionLearningFocus[];
  pending_moment?: Record<string, any> | null;
}

export interface SessionTurnWordFeedback {
  word_id: number;
  word: string;
  translation?: string | null;
  is_new: boolean;
  was_used: boolean;
  rating?: number | null;
  had_error: boolean;
  error?: SessionDetectedError | null;
}

export interface SessionStartResult {
  session: SessionOverview;
  assistant_turn?: AssistantTurn | null;
}

export interface SessionTurnResult {
  session: SessionOverview;
  user_message: SessionMessage;
  assistant_turn: AssistantTurn;
  xp_awarded: number;
  combo_count: number;
  error_feedback: SessionErrorFeedback;
  word_feedback: SessionTurnWordFeedback[];
}

export interface SessionMessageList {
  items: SessionMessage[];
  total: number;
}

/* WP-64 → WP-65 — a letter is a fact in the story, so a mission now carries the
   person on the other end of it. `serialize_mission` mirrors every field flat
   *and* inside `courrier`; `outcome` lives only in the block, because the
   top-level key is already the legacy serial state delta. */
export type MissionLetterOutcome = 'kept' | 'partial' | 'missed' | 'ignored' | string;
export type MissionLetterOrigin = 'courrier' | 'chain' | 'story_born' | string;

export interface MissionCorrespondent {
  id: string;
  name: string;
  role?: string | null;
  initials?: string | null;
  /** WP-61's feeling as one French line — absent when the story has no opinion. */
  mood_line?: string | null;
}

export interface MissionChain {
  id: string;
  index: number;
  total: number;
}

export interface MissionThreadLetter {
  mission_id: string;
  title?: string | null;
  summary_fr?: string | null;
  outcome?: MissionLetterOutcome | null;
  stakes_level?: number | null;
  chain_index?: number | null;
  at?: string | null;
}

export interface MissionCourrier {
  correspondent: MissionCorrespondent | null;
  chain: MissionChain | null;
  expires_at?: string | null;
  thread_history?: MissionThreadLetter[];
  outcome?: MissionLetterOutcome | null;
  origin?: MissionLetterOrigin;
}

/** `recap.measured` — every figure counted, none of them a formula over word
 *  count. It replaced `recap.readiness`, which is gone from the payload. */
export interface MissionMeasured {
  objectives_met: number;
  objectives_total: number;
  objectives_met_all: number;
  objectives_all: number;
  repairs: number;
  phrases_saved: number;
  replies: number;
  words_written: number;
}

export interface RealWorldMission {
  id: string;
  /** `lapsed`: an overdue letter that stopped waiting (WP-64). Never a failure. */
  status: 'available' | 'in_progress' | 'completed' | 'lapsed' | string;
  cadence: 'weekly' | 'post_session' | 'ad_hoc' | string;
  mission_type: 'message' | 'explain_plan' | 'news_summary' | 'travel_work' | 'conversation' | string;
  mission_format?: 'chat_message' | 'voicemail_reply' | 'email_formal' | 'admin_form' | 'phone_call' | string;
  stakes_level?: number;
  atelier_session_id?: string | null;
  serial_thread_id?: string | null;
  episode_index?: number | null;
  iso_year?: number | null;
  iso_week?: number | null;
  title: string;
  brief: string;
  selected_concept_ids: number[];
  target_errata_ids: string[];
  target_vocabulary_ids: number[];
  target_vocabulary?: MissionTargetVocabulary[];
  source_snapshot: Record<string, any>;
  objectives: Array<Record<string, any>>;
  prompt_payload: Record<string, any>;
  recap: VocabularyRecapPayload;
  outcome?: Record<string, any> | null;
  correspondent?: MissionCorrespondent | null;
  chain?: MissionChain | null;
  expires_at?: string | null;
  thread_history?: MissionThreadLetter[];
  courrier?: MissionCourrier | null;
  recommendation_reason?: { text: string; signals: Record<string, any> };
  attempts?: Array<Record<string, any>>;
  turns?: Array<Record<string, any>>;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface MissionToday {
  weekly_mission: RealWorldMission | null;
  post_session_recommendation: RealWorldMission | null;
  active_mission: RealWorldMission | null;
  recent_completed: RealWorldMission[];
}

/* WP-34 — «Apportez votre français». One envelope for every intake route, so
   the page renders one state machine rather than five screens. An `unread`
   artefact carries no `artefact` payload and no `task`: that is the honest
   «non lu» state, not a rendering bug. */
export interface IntakeGlossedWord {
  word: string;
  lemma?: string;
  gloss?: string;
  gloss_language?: string | null;
  gloss_source?: 'vocabulary' | 'model' | 'none' | string;
  example_fr?: string;
  word_id?: number | null;
}

export interface IntakeArtefactPayload {
  type?: string;
  type_label_fr?: string;
  title_fr?: string;
  summary_fr?: string;
  summary_bounded?: boolean;
  key_facts?: Array<{ label_fr: string; value_fr: string }>;
  glossed_words?: IntakeGlossedWord[];
  band?: string;
  gloss_language?: string;
}

export interface IntakeArtefactTask {
  kind?: 'reply' | 'decide' | 'ask' | string;
  kind_label_fr?: string;
  instruction_fr?: string;
  counterpart_fr?: string;
  register?: 'tu' | 'vous' | string;
  success_fr?: string;
}

export interface IntakeArtefact {
  id: string;
  version: string;
  status: 'read' | 'unread' | string;
  source_kind: 'text' | 'image' | string;
  source_text: string;
  artefact: IntakeArtefactPayload;
  task: IntakeArtefactTask;
  mission_id: string | null;
  queued_word_count: number;
  created_at?: string | null;
}

export interface IntakeCap {
  limit: number;
  used: number;
  remaining: number;
  spent_usd: number;
  ceiling_usd: number;
  enabled: boolean;
}

export interface IntakeEnvelope {
  version: string;
  artefact: IntakeArtefact | null;
  mission: RealWorldMission | null;
  artefacts: IntakeArtefact[];
  cap: IntakeCap;
  max_text_chars: number;
  max_image_bytes: number;
  max_unknown_words: number;
}

export interface SerialToday {
  id?: string;
  thread_id: string;
  episode_index: number;
  episode_label?: string;
  beat?: 'act' | 'see' | string;
  kind: 'mission' | 'feuilleton' | string;
  status?: string;
  mission_id?: string | null;
  scene_id?: string | null;
  previously?: string | null;
  hook_from_previous?: Record<string, any> | null;
  hook?: Record<string, any> | null;
  brief_payload?: Record<string, any> | null;
  location_id?: string | null;
  thread?: Record<string, any>;
}

export interface SerialArchiveEpisode {
  id: string;
  episode_index: number;
  episode_label: string;
  kind: 'mission' | 'feuilleton' | string;
  title: string;
  mission_id?: string | null;
  scene_id?: string | null;
  thumbnail_url?: string | null;
  hook_text?: string | null;
  completed_at?: string | null;
  status: string;
  required_cast?: string[];
  brief_payload?: Record<string, any>;
}

export interface SerialCastMember {
  id: string;
  name: string;
  role?: string | null;
  dynamic_with_user?: string | null;
  model_sheet_url?: string | null;
  accent_colour?: string | null;
  relationship: {
    closeness: number;
    register: string;
    register_switch_episode?: number | null;
    last_summary?: string;
    callbacks?: string[];
    /** WP-61: -2..2, how the character feels about the learner; null before any exchange. */
    mood?: number | null;
  };
  episodes?: Array<{
    episode_index: number;
    episode_label: string;
    kind: string;
    title: string;
    href: string;
  }>;
}

export interface SerialAvatarPayload {
  mode: 'avatar' | 'pov';
  description?: string;
  reference_images?: string[];
  avatar_builder?: Record<string, any>;
}

export interface AtelierCollectible {
  id: string;
  kind: string;
  minted_at?: string | null;
  source_kind: string;
  source_ref: string;
  metadata?: Record<string, any>;
  composed?: boolean;
  composed_into_id?: string | null;
  members?: AtelierCollectible[];
}

export interface AtelierWorkshopProgress {
  target: string;
  member_kind: string;
  required: number;
  available: number;
  progress: number;
  shortfall: number;
}

/** WP-D5 · «Vos sceaux»: one learner-local day of the streak calendar. */
export type StreakDayState = 'completed' | 'relache' | 'missed' | 'today' | 'future';

export interface StreakCalendarDay {
  date: string;
  state: StreakDayState;
  completed: number;
  is_today: boolean;
  /** The day's journey was completed (an early stop presses no seal). */
  sealed: boolean;
  edition_no: number | null;
  seal_variant: string | null;
}

/** `GET /analytics/streak`: the number and the grid, read from the same rows. */
export interface StreakCalendar {
  current_streak: number;
  longest_streak: number;
  today_done: boolean;
  freeze_available: boolean;
  today: string | null;
  timezone: string | null;
  calendar: StreakCalendarDay[];
}

export interface AtelierAlmanac {
  collectibles: Record<string, AtelierCollectible[]>;
  progress: Record<string, AtelierWorkshopProgress>;
  plates: AtelierCollectible[];
  totals: Record<string, number>;
}

export type AtelierWorkshopTarget = 'plate_semaine' | 'plate_chapter' | 'colophon';

export interface AtelierWorkshopComposeResult {
  plate: AtelierCollectible;
  members: AtelierCollectible[];
  progress: Record<string, AtelierWorkshopProgress>;
  minted_collectibles: AtelierCollectible[];
}

export interface MissionAttemptResult {
  attempt: Record<string, any>;
  correction: VocabularyCorrectionPayload;
  errata: LinkedVocabularyErratum[];
  mission: RealWorldMission;
}

export interface MissionTurnResult {
  user_turn: Record<string, any>;
  assistant_turn: Record<string, any>;
  correction: VocabularyCorrectionPayload;
  errata: LinkedVocabularyErratum[];
  mission: RealWorldMission;
  outcome?: Record<string, any>;
}

export interface GraphicNovelPanel {
  id: string;
  panel_index: number;
  title: string;
  beat: string;
  image_prompt: string;
  image_url?: string | null;
  image_payload: Record<string, any>;
  audio_payload?: Record<string, any>;
  overlay_payload: Record<string, any>;
  generation_metadata: Record<string, any>;
  created_at?: string | null;
}

export interface GraphicNovelScene {
  id: string;
  status: 'available' | 'in_progress' | 'completed' | string;
  cadence: 'ad_hoc' | 'post_session' | 'weekly' | string;
  atelier_session_id?: string | null;
  mission_id?: string | null;
  serial_thread_id?: string | null;
  episode_index?: number | null;
  personal_input_item_id?: string | null;
  title: string;
  brief: string;
  selected_concept_ids: number[];
  target_errata_ids: string[];
  target_vocabulary_ids: number[];
  target_vocabulary?: MissionTargetVocabulary[];
  source_snapshot: Record<string, any>;
  script_payload: Record<string, any>;
  hook?: Record<string, any>;
  recap: VocabularyRecapPayload;
  cache_key: string;
  prompt_version: string;
  image_model: string;
  image_quality: string;
  panels?: GraphicNovelPanel[];
  attempts?: Array<Record<string, any>>;
  created_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface GraphicNovelToday {
  active_scene: GraphicNovelScene | null;
  available_scene: GraphicNovelScene | null;
  recent_completed: GraphicNovelScene[];
  recommendation: Record<string, any>;
}

export interface GraphicNovelAttemptResult {
  attempt: Record<string, any>;
  correction: VocabularyCorrectionPayload;
  errata: LinkedVocabularyErratum[];
  scene: GraphicNovelScene;
}

export interface GraphicNovelCompleteResult {
  scene: GraphicNovelScene;
  recap: VocabularyRecapPayload;
  next_serial?: SerialToday | null;
}

export interface MissionCompleteResult {
  mission: RealWorldMission;
  recap: VocabularyRecapPayload;
  next_serial?: SerialToday | null;
}

export interface PasswordResetRequestResponse {
  message: string;
  // Dev/test only; production never returns these.
  reset_token?: string | null;
  reset_url?: string | null;
  reset_code?: string | null;
}

/** A reset is confirmed with the emailed six-digit code, or an older link token. */
export type PasswordResetConfirmPayload =
  | { token: string; new_password: string }
  | { email: string; code: string; new_password: string };

export type FeedbackCategory =
  | 'bug'
  | 'broken_link'
  | 'content'
  | 'layout'
  | 'slow_loading'
  | 'suggestion'
  | 'other';

export interface FeedbackReportPayload {
  category: FeedbackCategory;
  message?: string;
  route: string;
  url?: string;
  screen?: string;
  viewport?: Record<string, any>;
  user_agent?: string;
  context_payload?: Record<string, any>;
}

export interface FeedbackReport {
  id: string;
  user_id: string;
  category: FeedbackCategory;
  message?: string | null;
  route: string;
  url?: string | null;
  screen?: string | null;
  viewport: Record<string, any>;
  user_agent?: string | null;
  context_payload: Record<string, any>;
  created_at: string;
}

function apiErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    if (typeof detail.message === 'string') return detail.message;
    if (typeof detail.code === 'string') return detail.code.replaceAll('_', ' ');
  }
  if (typeof error?.message === 'string') return error.message;
  return 'An error occurred';
}

type SilentRequestConfig = AxiosRequestConfig & {
  suppressGlobalError?: boolean;
  skipAuth?: boolean;
  _retryAuth?: boolean;
  _retry429?: boolean;
};

function isUnauthorized(error: any): boolean {
  return error?.response?.status === 401;
}

/**
 * Same-origin route to the backend, rewritten by next.config.js when API_URL is
 * set. It is the fallback for an unconfigured browser bundle: the old default,
 * http://localhost:8000/api/v1, sent credentialed requests to whatever owned
 * that port on the developer's machine.
 */
const SAME_ORIGIN_API_PROXY = '/api/backend';

export function resolveBrowserApiBaseUrl() {
  const configured = normalizeApiBaseUrl(
    process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || '',
  );
  if (!configured) return SAME_ORIGIN_API_PROXY;
  if (typeof window === 'undefined') return configured;
  if (isNativePlatform()) return configured;

  try {
    const url = new URL(configured);
    const localApiHost = (url.hostname === 'localhost' || url.hostname === '127.0.0.1') && url.port === '8000';
    if (localApiHost && url.pathname.replace(/\/$/, '') === '/api/v1') {
      return SAME_ORIGIN_API_PROXY;
    }
  } catch {
    // Relative or otherwise non-URL values should pass through unchanged.
  }

  return configured;
}

function normalizeApiBaseUrl(value: string) {
  const trimmed = value.replace(/\/+$/, '');
  if (!trimmed || trimmed.startsWith('/') || trimmed.endsWith('/api/v1')) return trimmed;
  return `${trimmed}/api/v1`;
}

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: resolveBrowserApiBaseUrl(),
      timeout: 90000, // Increased for LLM-heavy operations like grammar exercise generation
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      async (config) => {
        const requestConfig = config as SilentRequestConfig;
        const token = requestConfig.skipAuth ? null : await getAppAccessToken();
        if (!requestConfig.skipAuth && token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        // WP-73: one id per call, echoed by the API and bound into its logs and Sentry.
        if (!config.headers['X-Request-ID']) config.headers['X-Request-ID'] = newRequestId();
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for error handling
    this.api.interceptors.response.use(
      (response: AxiosResponse) => response,
      async (error) => {
        const detail = error.response?.data?.detail;
        const message = apiErrorMessage(error);
        const requestConfig = error.config as SilentRequestConfig | undefined;
        if ((error.response?.status ?? 0) >= 500) {
          // WP-73: a server failure is findable from both sides by its request id.
          captureClientError(error, {
            requestId: error.response?.headers?.['x-request-id'] || requestConfig?.headers?.['X-Request-ID'],
            route: requestConfig?.url,
          });
        }

        if (isUnauthorized(error) && isNativePlatform() && requestConfig && !requestConfig.skipAuth && !requestConfig._retryAuth) {
          requestConfig._retryAuth = true;
          // WP-71: one shared refresh for every request that got this 401, and
          // the keychain is cleared only when the server refuses the refresh
          // token itself — never because the network dropped mid-refresh.
          const sent = String(requestConfig.headers?.Authorization || '').replace(/^Bearer\s+/i, '');
          const recovered = await recoverNativeAccessToken(sent || null);
          if (recovered.status === 'refreshed') {
            requestConfig.headers = {
              ...(requestConfig.headers || {}),
              Authorization: `Bearer ${recovered.accessToken}`,
            };
            return this.api.request(requestConfig);
          }
          if (recovered.status === 'signed-out') {
            if (typeof window !== 'undefined' && window.location.pathname !== '/auth/signin') {
              window.location.assign('/auth/signin');
            }
          }
          return Promise.reject(error);
        }

        if (detail?.code === 'feuilleton_generation_failed') {
          return Promise.reject(error);
        }

        // WP-70: a 429 is never an auth problem — no refresh, no sign-out.
        if (error.response?.status === 429) {
          const code = detail?.code;
          const waitSeconds = Math.max(1, Number(error.response?.headers?.['retry-after']) || 5);
          const method = String(requestConfig?.method || 'get').toLowerCase();
          if (code === 'rate_limited' && method === 'get' && requestConfig && !requestConfig._retry429 && waitSeconds <= 10) {
            requestConfig._retry429 = true;
            await new Promise((resolve) => setTimeout(resolve, waitSeconds * 1000));
            return this.api.request(requestConfig);
          }
          if (!requestConfig?.suppressGlobalError) {
            toast(
              code === 'daily_budget_reached'
                ? 'C’est tout pour aujourd’hui. À demain !'
                : `Doucement — réessayez dans ${waitSeconds} s.`,
              { id: code || 'rate_limited' },
            );
          }
          return Promise.reject(error);
        }

        if ((error.config as SilentRequestConfig)?.suppressGlobalError) {
          return Promise.reject(error);
        }

        switch (error.response?.status) {
          case 401:
            toast.error('Authentication required. Please log in.');
            // Redirect to login or refresh token
            break;
          case 403:
            toast.error('Access denied.');
            break;
          case 404:
            toast.error('Resource not found.');
            break;
          case 422:
            if (detail && typeof detail === 'object') {
              // Handle validation errors
              const validationErrors = detail.detail || detail;
              if (Array.isArray(validationErrors)) {
                validationErrors.forEach((err: any) => {
                  toast.error(`${err.loc?.join(' -> ')}: ${err.msg}`);
                });
              }
            } else {
              toast.error(message);
            }
            break;
          case 500:
            toast.error('Server error. Please try again later.');
            break;
          default:
            toast.error(message);
        }

        return Promise.reject(error);
      }
    );
  }

  // Generic HTTP methods
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.api.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.api.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.api.put<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.api.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.api.delete<T>(url, config);
    return response.data;
  }

  private async atelierGet<T>(url: string, config: SilentRequestConfig = {}): Promise<T> {
    const requestConfig: SilentRequestConfig = { suppressGlobalError: true, ...config };
    try {
      return await this.get<T>(url, requestConfig);
    } catch (error) {
      if (isUnauthorized(error) && !requestConfig.skipAuth) {
        const retryConfig: SilentRequestConfig = { ...requestConfig, skipAuth: true };
        return this.get<T>(url, retryConfig);
      }
      throw error;
    }
  }

  private async atelierPost<T>(url: string, data?: any, config: SilentRequestConfig = {}): Promise<T> {
    const requestConfig: SilentRequestConfig = { suppressGlobalError: true, ...config };
    try {
      return await this.post<T>(url, data, requestConfig);
    } catch (error) {
      if (isUnauthorized(error) && !requestConfig.skipAuth) {
        const retryConfig: SilentRequestConfig = { ...requestConfig, skipAuth: true };
        return this.post<T>(url, data, retryConfig);
      }
      throw error;
    }
  }

  /** French → the learner's own language (the server reads `native_language`). */
  async translateForLearner(text: string): Promise<string> {
    const trimmed = (text || '').trim();
    if (!trimmed) return '';
    const response = await this.atelierPost<{ translation: string; language?: string }>('/atelier/translate', { text: trimmed });
    return response.translation || '';
  }

  /**
   * WP-78 «Garder»: keep a word tapped in the story, with the sentence it was
   * in, in the learner's own Lexique. A 422 carries a French `detail.message`
   * (no entry, no meaning in the learner's language) the sheet shows as is.
   */
  async keepWord(payload: {
    term: string;
    sentence: string;
    surface?: string;
    journey_id?: string | null;
  }): Promise<{ word_id: number; word: string; gloss: string; example_fr: string; already_kept: boolean }> {
    return this.post('/vocabulary/keep', payload, { suppressGlobalError: true } as SilentRequestConfig);
  }

  /** @deprecated the server no longer targets English; kept for old call sites. */
  async translateToEnglish(text: string): Promise<string> {
    return this.translateForLearner(text);
  }

  // Authentication endpoints
  async register(userData: {
    email: string;
    password: string;
    full_name?: string;
    name?: string;
    native_language?: string;
    target_language?: string;
    proficiency_level?: string;
    interests?: string;
    learning_motivation?: string;
    speaking_comfort?: 'warming_up' | 'ready' | 'confident';
    grammar_correction_level?: 'strict' | 'moderate' | 'lenient';
    daily_goal_minutes?: number;
  }) {
    const { name, ...rest } = userData;
    return this.post('/auth/register', {
      ...rest,
      full_name: rest.full_name || name,
    });
  }

  async login(credentials: { email: string; password: string }) {
    return this.post('/auth/login', credentials);
  }

  async refreshSession(refreshToken: string) {
    return this.post('/auth/refresh', { refresh_token: refreshToken });
  }

  async logout(refreshToken?: string | null) {
    return this.post('/auth/logout', refreshToken ? { refresh_token: refreshToken } : {});
  }

  async requestPasswordReset(data: { email: string }) {
    return this.post<PasswordResetRequestResponse>('/auth/password-reset/request', data, {
      skipAuth: true,
      suppressGlobalError: true,
    } as SilentRequestConfig);
  }

  async confirmPasswordReset(data: PasswordResetConfirmPayload) {
    return this.post<void>('/auth/password-reset/confirm', data, {
      skipAuth: true,
      suppressGlobalError: true,
    } as SilentRequestConfig);
  }

  // User endpoints
  async getCurrentUser() {
    return this.get('/users/me');
  }

  async getSettings() {
    return this.get('/users/me/settings');
  }

  async updateSettings(data: Record<string, unknown> & { address_preference?: AddressPreference }) {
    return this.patch('/users/me/settings', data);
  }

  async updateProfile(data: any) {
    return this.patch('/users/me', data);
  }

  async changePassword(data: { current_password: string; new_password: string }) {
    return this.patch('/users/me/password', data);
  }

  async changeEmail(data: { current_password: string; new_email: string }) {
    return this.patch('/users/me/email', data);
  }

  async exportUserData() {
    return this.get('/users/me/export');
  }

  async signOutAllDevices() {
    return this.post('/users/me/sign-out-all');
  }

  async deleteAccount() {
    return this.delete('/users/me');
  }

  async getVapidPublicKey() {
    return this.get<{ publicKey: string | null }>('/notifications/vapid-public-key');
  }

  async subscribeToNotifications(subscription: any) {
    return this.post('/notifications/subscribe', subscription);
  }

  async subscribeToNativeNotifications(token: string) {
    return this.post('/notifications/native/subscribe', {
      token,
      platform: 'ios',
      environment: process.env.NEXT_PUBLIC_APNS_ENVIRONMENT === 'production'
        ? 'production'
        : 'sandbox',
    });
  }

  async recordNotificationTap(data: { route: string; kind?: string; notification_id?: string }) {
    return this.post('/notifications/tap', data, { suppressGlobalError: true } as SilentRequestConfig);
  }

  async recordClientError(data: { message: string; stack?: string; route?: string; source?: string }) {
    return this.post('/analytics/client-error', data, { suppressGlobalError: true } as SilentRequestConfig);
  }

  // Session endpoints
  async createSession(data: {
    topic?: string;
    planned_duration_minutes: number;
    conversation_style?: string;
    difficulty_preference?: string;
    generate_greeting?: boolean;
  }): Promise<SessionStartResult> {
    return this.post<SessionStartResult>('/sessions', data);
  }

  async quickStartSession(data?: {
    story_title?: string;
    story_url?: string;
    story_source?: string;
    story_summary?: string;
  }): Promise<SessionStartResult> {
    return this.post<SessionStartResult>('/sessions/quick-start', data || {});
  }

  async getLiveStories(params?: { limit?: number; topics?: string }) {
    return this.get<LiveStoryListResponse>('/sessions/live-stories', { params });
  }

  async getSession(sessionId: string): Promise<SessionOverview> {
    return this.get<SessionOverview>(`/sessions/${sessionId}`);
  }

  async getSessions(params?: { limit?: number; offset?: number }): Promise<SessionOverview[]> {
    return this.get<SessionOverview[]>('/sessions', { params });
  }

  async sendMessage(sessionId: string, data: { content: string; suggested_word_ids?: number[] }): Promise<SessionTurnResult> {
    return this.post<SessionTurnResult>(`/sessions/${sessionId}/messages`, data);
  }

  async getSessionMessages(sessionId: string, params?: { limit?: number; offset?: number }): Promise<SessionMessageList> {
    return this.get<SessionMessageList>(`/sessions/${sessionId}/messages`, { params });
  }

  async submitSessionMoment(
    sessionId: string,
    momentId: string,
    data: { answer_text?: string; selected_choice?: string; skipped?: boolean },
  ) {
    return this.post(`/sessions/${sessionId}/moments/${momentId}/submit`, data);
  }

  async skipSessionMoment(sessionId: string, momentId: string) {
    return this.post(`/sessions/${sessionId}/moments/${momentId}/skip`, {});
  }

  async logExposure(sessionId: string, data: { word_id: number; exposure_type: 'hint' | 'translation' }) {
    return this.post(`/sessions/${sessionId}/exposures`, data);
  }

  async updateSessionStatus(sessionId: string, status: 'in_progress' | 'paused' | 'completed' | 'abandoned'): Promise<SessionOverview> {
    return this.patch<SessionOverview>(`/sessions/${sessionId}`, { status });
  }

  async getSessionSummary(sessionId: string) {
    return this.get(`/sessions/${sessionId}/summary`);
  }

  async markWordDifficult(sessionId: string, data: { word_id: number }) {
    return this.post(`/sessions/${sessionId}/difficult_words`, { word_id: data.word_id, exposure_type: 'flag' });
  }

  async lookupVocabulary(word: string, language?: string) {
    const params = new URLSearchParams({ word });
    if (language) params.set('language', language);
    // 404 is the ordinary answer for a word outside the catalogue: the caller
    // falls back to the sentence, and no global toast may interrupt the sheet.
    const config: SilentRequestConfig = { suppressGlobalError: true };
    return this.get(`/vocabulary/lookup?${params.toString()}`, config);
  }

  async listVocabulary(params?: { language?: string; limit?: number; offset?: number }) {
    return this.get('/vocabulary/', { params });
  }

  // Progress endpoints
  async getProgressQueue(params?: { direction?: string; limit?: number }) {
    return this.get('/progress/queue', { params });
  }

  async getUnifiedSRSQueue(params?: {
    limit?: number;
    time_budget_minutes?: number;
    interleaving_mode?: 'random' | 'blocks' | 'priority';
  }): Promise<UnifiedSRSQueue> {
    return this.get('/progress/unified-queue', { params });
  }

  async getVocabularyRecommendations(params?: VocabularyRecommendationParams): Promise<VocabularyRecommendations> {
    return this.atelierGet('/progress/vocabulary/recommendations', { params });
  }

  async getVocabularyDueContext(params?: VocabularyDueContextParams): Promise<VocabularyDueContext> {
    return this.atelierGet('/vocabulary/due-context', { params });
  }

  async getVocabularyCoverage(): Promise<VocabularyCoverage> {
    return this.atelierGet('/vocabulary/coverage');
  }

  async getWordsOfTheDay(): Promise<DailyWordSlate> {
    return this.atelierGet('/vocabulary/words-of-the-day');
  }

  async getConjugationReview(params?: { limit?: number; cefr_band?: string }): Promise<ConjugationReviewQueue> {
    return this.atelierGet('/vocabulary/conjugation/review', { params });
  }

  async submitConjugationReview(data: {
    lemma: string;
    tense: string;
    rating: number;
    response_time_ms?: number;
  }): Promise<ConjugationReviewResponse> {
    return this.atelierPost('/vocabulary/conjugation/review', data);
  }

  async getVocabularyMasteryMap(params?: { limit?: number; direction?: string }): Promise<VocabularyMasteryMap> {
    return this.atelierGet('/progress/vocabulary/map', { params });
  }

  async getWeeklyDossier(params?: { period_days?: number }): Promise<WeeklyDossier> {
    return this.atelierGet('/progress/weekly-dossier', { params });
  }

  async getAnkiProgress(params?: { direction?: string }) {
    return this.get('/progress/anki', { params });
  }

  async getAnkiSummary() {
    return this.get('/progress/anki/summary');
  }

  async submitReview(data: { word_id: number; rating: number; response_time_ms?: number }): Promise<ReviewResponse> {
    return this.post('/progress/review', data);
  }

  async submitAnkiReview(data: { word_id: number; rating: number; response_time_ms?: number }): Promise<AnkiReviewResponse> {
    return this.atelierPost('/anki/review', data);
  }

  async getWordProgress(wordId: number) {
    return this.get(`/progress/${wordId}`);
  }

  // Analytics endpoints
  async getAnalyticsSummary(): Promise<LearnerAnalyticsSummary> {
    return this.get<LearnerAnalyticsSummary>('/analytics/summary');
  }

  async getAnalyticsStatistics(params?: { days?: number }) {
    return this.get('/analytics/statistics', { params });
  }

  async getStreakData(windowDays = 28): Promise<StreakCalendar> {
    return this.get('/analytics/streak', { params: { window_days: windowDays } });
  }

  async getVocabularyProgress() {
    return this.get('/analytics/vocabulary');
  }

  async getErrorAnalysis() {
    return this.get('/analytics/errors');
  }

  async getErrorSummary() {
    return this.get('/analytics/errors/summary');
  }

  async getPilotOperations(weeks = 4) {
    return this.get('/analytics/pilot-ops', { params: { weeks } });
  }

  // Achievement endpoints
  async getAchievements() {
    return this.get('/achievements');
  }

  async getUserAchievements(): Promise<UserAchievementProgress[]> {
    return this.get<UserAchievementProgress[]>('/achievements/my');
  }

  async checkAchievements() {
    return this.post('/achievements/check');
  }

  // Vocabulary endpoints
  async getVocabulary(params?: { language?: string; limit?: number; offset?: number; search?: string }): Promise<VocabularyListResponse> {
    return this.get('/vocabulary', {
      params,
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
  }

  async getVocabularyItem(wordId: number): Promise<VocabularyWord> {
    return this.get(`/vocabulary/${wordId}`);
  }

  async getVocabularyBiography(wordId: number): Promise<VocabularyBiography> {
    return this.atelierGet(`/vocabulary/${wordId}/biography`);
  }

  // Grammar endpoints
  async getGrammarSummary() {
    return this.get('/grammar/summary');
  }

  async getGrammarConcepts(params?: { level?: string; category?: string; limit?: number; offset?: number }) {
    return this.get('/grammar/concepts', { params });
  }

  async getGrammarNotebook(params?: { level?: string; category?: string; q?: string; locale?: string; limit?: number; offset?: number }) {
    return this.get<GrammarNotebookItem[]>('/grammar/notebook', { params });
  }

  async getGrammarNotebookConcept(conceptId: number, params?: { locale?: string }) {
    return this.get<GrammarNotebookDetail>(`/grammar/notebook/${conceptId}`, { params });
  }

  async updateGrammarNotebookNotes(conceptId: number, data: { notes: string }) {
    return this.patch<GrammarNotebookDetail>(`/grammar/notebook/${conceptId}/notes`, data);
  }

  async getGrammarConceptsByLevel() {
    return this.get('/grammar/by-level');
  }

  async getDueGrammarConcepts(params?: { level?: string; limit?: number }) {
    return this.get<DueGrammarConcept[]>('/grammar/due', { params });
  }

  async getGrammarProgress(params?: { level?: string }) {
    return this.get('/grammar/progress', { params });
  }

  async recordGrammarReview(data: { concept_id: number; score: number; notes?: string }) {
    return this.post('/grammar/review', data);
  }

  async recordGrammarReviewWithAchievements(data: { concept_id: number; score: number; notes?: string }) {
    return this.post('/grammar/review-with-achievements', data);
  }

  async getGrammarAchievements(category?: string) {
    return this.get('/grammar/achievements', { params: { category } });
  }

  async getGrammarStreak() {
    return this.get('/grammar/streak');
  }

  async getGrammarGraph(level?: string) {
    return this.get('/grammar/graph', { params: { level } });
  }

  async getGrammarForChapter(chapterId: string) {
    return this.get(`/grammar/for-chapter/${chapterId}`);
  }

  async markGrammarPracticedInContext(conceptIds: number[]) {
    return this.post('/grammar/mark-practiced-in-context', conceptIds);
  }

  // Atelier grammar practice endpoints
  async getAtelierToday() {
    return this.atelierGet<AtelierToday>('/atelier/today');
  }

  async getCefrProgress() {
    return this.atelierGet<CEFRProgress>('/progress/cefr');
  }

  async startAtelierSession(data?: { concept_ids?: number[]; preferred_concept_id?: number; preferred_vocabulary_ids?: number[] }) {
    return this.atelierPost<AtelierSessionStart>('/atelier/sessions', data || {});
  }

  async getActiveAtelierSession() {
    return this.atelierGet<{ session: AtelierSessionStart | null }>('/atelier/sessions/active');
  }

  async getAtelierSession(sessionId: string) {
    return this.atelierGet<AtelierSessionStart>(`/atelier/sessions/${sessionId}`);
  }

  async submitAtelierAttempt(
    sessionId: string,
    data: {
      concept_id?: number | null;
      round: 'recognize' | 'transform' | 'sentence' | 'produce' | 'speak' | 'conversation';
      mode: string;
      exercise_id: string;
      answer_payload: Record<string, any>;
      confidence?: 'sure' | 'unsure' | null;
      retest_source_attempt_id?: string | null;
      resubmit?: boolean;
    }
  ) {
    return this.atelierPost<AtelierAttemptResult>(`/atelier/sessions/${sessionId}/attempts`, data);
  }

  async getAtelierAttempt(attemptId: string) {
    return this.atelierGet<AtelierAttemptResult>(`/atelier/attempts/${attemptId}`);
  }

  async repairAtelierAttempt(attemptId: string, data: { text: string; erratum_index: number }) {
    return this.atelierPost<AtelierAttemptResult>(`/atelier/attempts/${attemptId}/repair`, data);
  }

  async requestAtelierAttemptAiReview(attemptId: string) {
    return this.atelierPost<AtelierAttemptResult>(`/atelier/attempts/${attemptId}/ai-review`, {});
  }

  async reportAtelierExercise(data: {
    session_id?: string | null;
    concept_id?: number | null;
    exercise_set_id?: string | null;
    round?: string | null;
    mode?: string | null;
    exercise_id?: string | null;
    item_id?: string | null;
    reason: string;
  }) {
    return this.atelierPost<{ ok: boolean; event_id: string }>('/atelier/exercises/report', data);
  }

  async getAtelierAlmanac() {
    return this.atelierGet<AtelierAlmanac>('/atelier/almanac');
  }

  async composeAtelierWorkshop(target: AtelierWorkshopTarget) {
    return this.atelierPost<AtelierWorkshopComposeResult>('/atelier/workshop/compose', { target });
  }

  async completeAtelierSession(sessionId: string) {
    return this.atelierPost<{ session_id: string; recap: Record<string, any>; minted_collectibles?: AtelierCollectible[] }>(`/atelier/sessions/${sessionId}/complete`);
  }

  async reviewAtelierErratum(errorId: string, data?: { rating?: number; repaired?: boolean }) {
    return this.atelierPost<{ erratum: AtelierErratum }>(`/atelier/errata/${errorId}/review`, data || {});
  }

  async getAtelierErratumTask(errorId: string) {
    return this.atelierGet<{ task: AtelierErrataReviewTask }>(`/atelier/errata/${errorId}/task`);
  }

  async submitAtelierErratumAttempt(errorId: string, data: { answer_text: string }) {
    return this.post<AtelierErrataAttemptResult>(`/atelier/errata/${errorId}/attempt`, data);
  }

  // Real-world scenario missions
  async getMissionsToday() {
    return this.atelierGet<MissionToday>('/missions/today');
  }

  async createMission(data: {
    mission_type?: string;
    cadence?: string;
    atelier_session_id?: string;
    serial_thread_id?: string;
    episode_index?: number;
    preferred_concept_ids?: number[];
    preferred_errata_ids?: string[];
    preferred_vocabulary_ids?: number[];
    use_news?: boolean;
    custom_scenario?: string;
    desired_outcome?: string;
    relationship?: string;
    register?: string;
    stakes_level?: number;
  }) {
    const response = await this.atelierPost<{ mission: RealWorldMission }>('/missions', data);
    return response.mission;
  }

  async getMission(missionId: string) {
    const response = await this.atelierGet<{ mission: RealWorldMission }>(`/missions/${missionId}`);
    return response.mission;
  }

  async submitMission(missionId: string, data: { text: string; mode?: 'writing' | 'chat' | 'voice' }) {
    return this.atelierPost<MissionAttemptResult>(`/missions/${missionId}/submit`, data);
  }

  async submitMissionTurn(missionId: string, data: { text: string; mode?: 'chat' | 'voice'; transcript_metadata?: Record<string, any> }) {
    return this.atelierPost<MissionTurnResult>(`/missions/${missionId}/turns`, data);
  }

  async completeMission(missionId: string) {
    const response = await this.atelierPost<MissionCompleteResult>(`/missions/${missionId}/complete`);
    return response;
  }

  // WP-34 — «Apportez votre français»: a real document the learner brought in.
  // Every route answers the same envelope, so the page renders one state machine
  // and never has to reconcile two shapes.
  async getIntakeArtefacts() {
    return this.atelierGet<IntakeEnvelope>('/intake');
  }

  async readIntakeText(text: string) {
    return this.atelierPost<IntakeEnvelope>('/intake/text', { text });
  }

  async readIntakePhoto(photo: File | Blob, filename = 'document.jpg') {
    const formData = new FormData();
    formData.append('file', photo, filename);
    return this.atelierPost<IntakeEnvelope>('/intake/photo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  async getIntakeArtefact(artefactId: string) {
    return this.atelierGet<IntakeEnvelope>(`/intake/${artefactId}`);
  }

  /** Deletes the document AND the Courrier task derived from it. */
  async deleteIntakeArtefact(artefactId: string) {
    return this.delete<void>(`/intake/${artefactId}`);
  }

  async getSerialToday() {
    return this.atelierGet<SerialToday>('/serial/today');
  }

  async getSerialEpisodes() {
    return this.atelierGet<{
      thread_id: string;
      season_number?: number;
      current_episode_index?: number;
      current_episode?: SerialToday | null;
      episodes: SerialArchiveEpisode[];
    }>('/serial/threads/current/episodes');
  }

  async getSerialCast() {
    return this.atelierGet<{ thread_id: string; cast: SerialCastMember[] }>('/serial/threads/current/cast');
  }

  async setSerialAvatar(payload: SerialAvatarPayload) {
    return this.atelierPost<{
      thread_id: string;
      protagonist_mode: 'avatar' | 'pov' | string;
      user_character?: Record<string, any> | null;
    }>('/serial/threads/current/avatar', payload);
  }

  async markSerialOnboardingSeen() {
    return this.atelierPost<{ serial_onboarding_seen: boolean }>('/serial/onboarding/seen');
  }

  async transcribeMissionAudio(audioBlob: Blob): Promise<string> {
    const formData = new FormData();
    formData.append('file', audioBlob, audioUploadFilename(audioBlob, 'mission-audio'));

    const response = await this.atelierPost<{ text: string }>('/missions/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.text;
  }

  // Graphic Novel / Feuilleton practice
  async getGraphicNovelToday() {
    return this.atelierGet<GraphicNovelToday>('/graphic-novel/today');
  }

  async createGraphicNovelScene(data?: {
    cadence?: 'ad_hoc' | 'post_session' | 'weekly';
    atelier_session_id?: string;
    mission_id?: string;
    serial_thread_id?: string;
    episode_index?: number;
    personal_input_item_id?: string;
    preferred_concept_ids?: number[];
    preferred_errata_ids?: string[];
    target_vocabulary_ids?: number[];
    use_news?: boolean;
    panel_count?: 4 | 6 | 8;
    story_quality?: 'standard' | 'premium';
    humor_style?: 'dry' | 'satirical' | 'absurd';
    experience_mode?: 'study' | 'reward';
    render_mode?: 'page' | 'panels';
    image_quality?: 'low' | 'medium' | 'high';
    public_figure_mode?: 'off' | 'named_context' | 'editorial_caricature';
    force_new?: boolean;
    refresh_news?: boolean;
    async_generation?: boolean;
  }) {
    const response = await this.atelierPost<{ scene: GraphicNovelScene }>('/graphic-novel/scenes', data || {}, {
      timeout: 30000,
    });
    return response.scene;
  }

  async getGraphicNovelScene(sceneId: string) {
    const response = await this.atelierGet<{ scene: GraphicNovelScene }>(`/graphic-novel/scenes/${sceneId}`);
    return response.scene;
  }

  async submitGraphicNovelAttempt(sceneId: string, data: { task_id: string; answer_payload: Record<string, any> }) {
    return this.atelierPost<GraphicNovelAttemptResult>(`/graphic-novel/scenes/${sceneId}/attempts`, data);
  }

  async completeGraphicNovelScene(sceneId: string) {
    const response = await this.atelierPost<GraphicNovelCompleteResult>(`/graphic-novel/scenes/${sceneId}/complete`);
    return response;
  }

  // ─────────────────────────────────────────────────────────────────
  // Audio Session API
  // ─────────────────────────────────────────────────────────────────

  async getAudioScenarios(): Promise<Array<{
    id: string;
    title: string;
    description: string;
    difficulty: string;
    objectives: string[];
  }>> {
    return this.get('/audio-session/scenarios');
  }

  async startAudioSession(scenarioId?: string): Promise<{
    session_id: string;
    opening_message: string;
    opening_audio_text: string;
    context: {
      topic?: string;
      style?: string;
      cast_member?: SerialCastMember | null;
      serial_thread_id?: string | null;
    };
  }> {
    return this.post<any>('/audio-session/start', { scenario_id: scenarioId });
  }

  // ─────────────────────────────────────────────────────────────────
  // Story Importer
  // ─────────────────────────────────────────────────────────────────

  async getLibraryBooks(): Promise<LibraryBook[]> {
    return this.get<LibraryBook[]>('/stories/library');
  }

  async getLibraryBook(bookId: string): Promise<LibraryBook> {
    return this.get<LibraryBook>(`/stories/library/${bookId}`);
  }

  async getLibraryEpisode(bookId: string, orderIndex: number): Promise<LibraryEpisode> {
    return this.get<LibraryEpisode>(`/stories/library/${bookId}/episodes/${orderIndex}`);
  }

  async completeLibraryEpisode(bookId: string, orderIndex: number): Promise<LibraryBook> {
    return this.post<LibraryBook>(`/stories/library/${bookId}/episodes/${orderIndex}/complete`);
  }

  async importContent(url: string): Promise<{ story_id: string; title: string }> {
    return this.post('/stories/import', { url });
  }

  async startStoryDiscussion(storyId: string): Promise<{ session_id: string }> {
    return this.post<{ session_id: string }>(`/stories/${storyId}/discuss`);
  }

  async respondToAudioSession(data: {
    session_id: string;
    user_text: string;
    conversation_history?: Array<any>;
  }): Promise<{
    ai_response: string;
    ai_audio_text: string;
    detected_errors: Array<{
      original: string;
      correction: string;
      explanation: string;
      concept_id?: number | null;
      concept_name?: string | null;
    }>;
    xp_awarded: number;
    should_show_text: boolean;
    vocabulary_credit: {
      produced_correct?: number;
      word_ids?: number[];
      words?: string[];
    };
    minted_collectibles: AtelierCollectible[];
  }> {
    const response = await this.post<any>('/audio-session/respond', data);

    // Map backend response to frontend format
    // Backend returns: detected_errors: [{ code, message, span, correction, concept_id, concept_name }]
    const errors = response.detected_errors?.map((err: any) => ({
      original: err.span,
      correction: err.correction,
      explanation: err.message,
      concept_id: err.concept_id,
      concept_name: err.concept_name,
    })) || [];

    return {
      ai_response: response.ai_response,
      ai_audio_text: response.ai_audio_text,
      detected_errors: errors,
      xp_awarded: response.xp_awarded,
      should_show_text: response.should_show_text,
      vocabulary_credit: response.vocabulary_credit || {},
      minted_collectibles: response.minted_collectibles || [],
    };
  }

  async endAudioSession(data: { session_id: string }): Promise<{
    session_id: string;
    duration_seconds: number;
    total_xp: number;
    errors_practiced: number;
    turns: number;
    produced_words: number;
    due_words_reused: string[];
    longest_answer_words: number;
    longest_answer: string;
    tomorrow_focus: string;
    cast_memory?: Record<string, any> | null;
    message: string;
  }> {
    return this.post<any>('/audio-session/end', data);
  }

  /**
   * `surface` names where the learner was speaking (WP-27: `journey_respond`
   * for the daily journey's default output). It is cost attribution only —
   * nothing about the transcription itself changes with it.
   */
  async transcribeAudio(audioBlob: Blob, surface?: string): Promise<string> {
    const formData = new FormData();
    formData.append('file', audioBlob, audioUploadFilename(audioBlob));
    if (surface) formData.append('surface', surface);

    const response = await this.api.post<{ text: string }>('/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.text;
  }

  async synthesizeSpeech(text: string, provider?: string): Promise<ArrayBuffer> {
    const response = await this.api.post('/audio/speak',
      { text, voice: 'nova', provider },
      { responseType: 'arraybuffer' }
    );
    return response.data;
  }

  async submitFeedbackReport(data: FeedbackReportPayload): Promise<FeedbackReport> {
    return this.post<FeedbackReport>(
      '/feedback/reports',
      data,
      { suppressGlobalError: true } as SilentRequestConfig,
    );
  }

  // ---------------------------------------------------------------------
  // Atelier V2 daily journey (WP-02)
  //
  // These reuse the transport above, so the native token refresh in
  // `setupInterceptors` still applies. Global error toasts are suppressed:
  // 409 conflicts, 202 processing and 422 empty answers are contract states
  // the daily-journey facade handles, not failures to shout about.
  // ---------------------------------------------------------------------

  private journeyConfig(): SilentRequestConfig {
    return { suppressGlobalError: true } as SilentRequestConfig;
  }

  private async journeyPost<T>(url: string, data: unknown): Promise<JourneyHttpResult<T>> {
    const response = await this.api.post<T>(url, data, this.journeyConfig());
    return { data: response.data, status: response.status };
  }

  async getStoryEpisodes(before?: string): Promise<StoryEpisodePage> {
    return this.get<StoryEpisodePage>(`/story-engine/episodes${before ? `?before=${encodeURIComponent(before)}` : ''}`, this.journeyConfig());
  }

  async getStoryEpisode(sceneId: string): Promise<StoryEpisode> {
    return this.get<StoryEpisode>(`/story-engine/episodes/${encodeURIComponent(sceneId)}`, this.journeyConfig());
  }

  async getStoryEpisodeForJourney(journeyId: string): Promise<StoryEpisode | null> {
    const page = await this.get<StoryEpisodePage>(`/story-engine/episodes?journey_id=${encodeURIComponent(journeyId)}`, this.journeyConfig());
    return page.episodes[0] ?? null;
  }

  async saveStoryReadingPosition(sceneId: string, panelIndex: number): Promise<{ scene_id: string; panel_index: number }> {
    const response = await this.api.put<{ scene_id: string; panel_index: number }>(`/story-engine/episodes/${encodeURIComponent(sceneId)}/position`, { panel_index: panelIndex }, this.journeyConfig());
    return response.data;
  }

  // WP-32 «Écouter d'abord» — the radio episode. Four additive calls; nothing
  // below is reached unless the learner has switched listening-first on.

  /** What is already spoken. Never starts a paid synthesis call. */
  async getEpisodeAudio(sceneId: string): Promise<EpisodeAudioManifest> {
    return this.get<EpisodeAudioManifest>(
      `/story-engine/episodes/${encodeURIComponent(sceneId)}/audio`,
      this.journeyConfig(),
    );
  }

  /** Synthesize the episode, or hear honestly that it is not spoken. */
  async synthesizeEpisodeAudio(sceneId: string): Promise<EpisodeAudioManifest> {
    const response = await this.api.post<EpisodeAudioManifest>(
      `/story-engine/episodes/${encodeURIComponent(sceneId)}/audio`,
      {},
      this.journeyConfig(),
    );
    return response.data;
  }

  /**
   * One spoken line, as bytes.
   *
   * Fetched rather than handed to `<audio src>`: the clip route is
   * authenticated with a bearer token and an audio element cannot carry a
   * header. The caller owns the object URL it makes from this and must revoke
   * it.
   */
  async getEpisodeAudioClip(sceneId: string, clipId: string): Promise<Blob> {
    const response = await this.api.get<Blob>(
      `/story-engine/episodes/${encodeURIComponent(sceneId)}/audio/${encodeURIComponent(clipId)}`,
      { ...this.journeyConfig(), responseType: 'blob' },
    );
    return response.data;
  }

  /** Record the prediction check. Measurement, not marking: no score comes back. */
  async recordEpisodePrediction(
    sceneId: string,
    body: { guess: string; verdict: string; supported?: string | null },
  ): Promise<{ scene_id: string; prediction: EpisodePredictionRecord }> {
    const response = await this.api.post<{
      scene_id: string;
      prediction: EpisodePredictionRecord;
    }>(
      `/story-engine/episodes/${encodeURIComponent(sceneId)}/audio/prediction`,
      body,
      this.journeyConfig(),
    );
    return response.data;
  }

  async getDailyJourneyToday(timezone?: string): Promise<TodayEnvelope> {
    const query = timezone ? `?timezone=${encodeURIComponent(timezone)}` : '';
    return this.get<TodayEnvelope>(`/daily-journeys/today${query}`, this.journeyConfig());
  }

  async getDailyJourney(journeyId: string): Promise<JourneySnapshot> {
    return this.get<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}`,
      this.journeyConfig(),
    );
  }

  async getDailyJourneyCapabilityProgress(): Promise<CapabilityProgress> {
    return this.get<CapabilityProgress>(
      '/daily-journeys/capabilities/progress',
      this.journeyConfig(),
    );
  }

  async createDailyJourney(body: CreateJourneyBody): Promise<JourneyHttpResult<JourneySnapshot>> {
    return this.journeyPost<JourneySnapshot>('/daily-journeys', body);
  }

  async useDailyJourneyHelp(
    journeyId: string,
    stepId: string,
    body: HelpBody,
  ): Promise<HelpResult> {
    const result = await this.journeyPost<HelpResult>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/steps/${encodeURIComponent(stepId)}/help`,
      body,
    );
    return result.data;
  }

  async submitDailyJourneyAttempt(
    journeyId: string,
    stepId: string,
    body: AttemptBody,
  ): Promise<AttemptResult> {
    const result = await this.journeyPost<AttemptResult>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/steps/${encodeURIComponent(stepId)}/attempts`,
      body,
    );
    return result.data;
  }

  async advanceDailyJourney(journeyId: string, body: AdvanceBody): Promise<JourneySnapshot> {
    const result = await this.journeyPost<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/advance`,
      body,
    );
    return result.data;
  }

  async pauseDailyJourney(journeyId: string, body: RevisionBody): Promise<JourneySnapshot> {
    const result = await this.journeyPost<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/pause`,
      body,
    );
    return result.data;
  }

  async resumeDailyJourney(journeyId: string, body: RevisionBody): Promise<JourneySnapshot> {
    const result = await this.journeyPost<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/resume`,
      body,
    );
    return result.data;
  }

  async finishDailyJourney(journeyId: string, body: FinishBody): Promise<JourneySnapshot> {
    const result = await this.journeyPost<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/finish`,
      body,
    );
    return result.data;
  }

  async retryDailyJourney(
    journeyId: string,
    body: RetryBody,
  ): Promise<JourneyHttpResult<JourneySnapshot>> {
    return this.journeyPost<JourneySnapshot>(
      `/daily-journeys/${encodeURIComponent(journeyId)}/retry`,
      body,
    );
  }

  /* ---- WP-25 placement --------------------------------------------------
     Every call answers the same envelope, so the screen renders one state
     machine. `respondToPlacement` carries the turn index: replaying it is a
     no-op server-side, so a retried request never buys a second paid grading. */

  async getPlacementState(): Promise<PlacementEnvelope> {
    return this.atelierGet<PlacementEnvelope>('/placement/state');
  }

  async startPlacement(restart = false): Promise<PlacementEnvelope> {
    return this.atelierPost<PlacementEnvelope>('/placement/start', { restart });
  }

  async respondToPlacement(
    sessionId: string,
    answer: string,
    turnIndex: number,
  ): Promise<PlacementEnvelope> {
    return this.atelierPost<PlacementEnvelope>(
      `/placement/${encodeURIComponent(sessionId)}/respond`,
      { answer, turn_index: turnIndex },
    );
  }

  async finishPlacement(sessionId: string): Promise<PlacementEnvelope> {
    return this.atelierPost<PlacementEnvelope>(
      `/placement/${encodeURIComponent(sessionId)}/finish`,
    );
  }

  async skipPlacement(): Promise<PlacementEnvelope> {
    return this.atelierPost<PlacementEnvelope>('/placement/skip');
  }

  /* ---- WP-30 «Le journal de bord» ---------------------------------------
     `getJournalState` is a GET that may create today's offer: idempotent, and
     it stores no learner content, so an empty tab never becomes a mutation.
     `writeJournalEntry` is a no-op server-side once the entry carries text, so
     a retried request never buys a second paid correction. */

  async getJournalState(): Promise<JournalEnvelope> {
    return this.atelierGet<JournalEnvelope>('/journal/state');
  }

  async listJournalEntries(limit = 20): Promise<JournalEntryView[]> {
    return this.atelierGet<JournalEntryView[]>(`/journal/entries?limit=${encodeURIComponent(String(limit))}`);
  }

  async writeJournalEntry(entryId: string, text: string): Promise<JournalEnvelope> {
    return this.atelierPost<JournalEnvelope>(
      `/journal/${encodeURIComponent(entryId)}/write`,
      { text },
    );
  }

  async skipJournalEntry(entryId: string): Promise<JournalEnvelope> {
    return this.atelierPost<JournalEnvelope>(`/journal/${encodeURIComponent(entryId)}/skip`);
  }

  async answerJournalFollowup(entryId: string, text: string): Promise<JournalEnvelope> {
    return this.atelierPost<JournalEnvelope>(
      `/journal/${encodeURIComponent(entryId)}/followup`,
      { text },
    );
  }
  /* ---- WP-31 rehearsal --------------------------------------------------
     One envelope per route, like the placement, so the page renders one state
     machine. `sendRehearsalTurn` carries the turn index: replaying it is a
     no-op server-side and buys no second grading. */

  async getRehearsalState(): Promise<RehearsalEnvelope> {
    return this.atelierGet<RehearsalEnvelope>('/rehearsals/state');
  }

  async declareRehearsal(declaration: string): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>('/rehearsals', { declaration });
  }

  async prepareRehearsal(rehearsalId: string): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>(
      `/rehearsals/${encodeURIComponent(rehearsalId)}/prepare`,
    );
  }

  async revealRehearsalPhrases(rehearsalId: string): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>(
      `/rehearsals/${encodeURIComponent(rehearsalId)}/phrases`,
    );
  }

  async sendRehearsalTurn(
    rehearsalId: string,
    text: string,
    turnIndex: number,
    mode: 'text' | 'voice' = 'text',
  ): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>(
      `/rehearsals/${encodeURIComponent(rehearsalId)}/turns`,
      { text, turn_index: turnIndex, mode },
    );
  }

  async debriefRehearsal(
    rehearsalId: string,
    outcome: 'done' | 'partly' | 'not_yet',
    freeLine: string,
  ): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>(
      `/rehearsals/${encodeURIComponent(rehearsalId)}/debrief`,
      { outcome, free_line: freeLine },
    );
  }

  async abandonRehearsal(rehearsalId: string): Promise<RehearsalEnvelope> {
    return this.atelierPost<RehearsalEnvelope>(
      `/rehearsals/${encodeURIComponent(rehearsalId)}/abandon`,
    );
  }
  /* ---- WP-35 «Votre dossier» ---------------------------------------------
     Three routes, one envelope. `openDossierClaim` records the claim and
     returns its two questions; `verifyDossierClaim` grades them and returns the
     refreshed model, so a verified claim needs no second read. */

  async getDossier(): Promise<DossierEnvelope> {
    return this.atelierGet<DossierEnvelope>('/dossier/state');
  }

  async openDossierClaim(kind: string, targetId: string): Promise<DossierEnvelope> {
    return this.atelierPost<DossierEnvelope>('/dossier/claims', {
      kind,
      target_id: targetId,
    });
  }

  async verifyDossierClaim(
    kind: string,
    targetId: string,
    answers: string[],
  ): Promise<DossierEnvelope> {
    return this.atelierPost<DossierEnvelope>('/dossier/claims/verify', {
      kind,
      target_id: targetId,
      answers,
    });
  }
}

export const apiService = new ApiService();
export default apiService;
