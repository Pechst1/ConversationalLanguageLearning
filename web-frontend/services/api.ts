import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import toast from 'react-hot-toast';

import { getAppAccessToken } from '@/lib/app-auth';
import { clearNativeAuthSession, refreshNativeAccessToken } from '@/lib/native-auth';
import { isNativePlatform } from '@/lib/native-platform';
import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

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

export interface CEFRProgress {
  version: string;
  estimate: string;
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
  };
  due_errata: AtelierErratum[];
  recap: Record<string, any>;
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
  target_answer: string;
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

export interface RealWorldMission {
  id: string;
  status: 'available' | 'in_progress' | 'completed' | string;
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

export interface SerialToday {
  thread_id: string;
  episode_index: number;
  kind: 'mission' | 'feuilleton' | string;
  status?: string;
  mission_id?: string | null;
  scene_id?: string | null;
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
};

function isUnauthorized(error: any): boolean {
  return error?.response?.status === 401;
}

export function resolveBrowserApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
  if (typeof window === 'undefined') return configured;
  if (isNativePlatform()) return configured;

  try {
    const url = new URL(configured);
    const localApiHost = (url.hostname === 'localhost' || url.hostname === '127.0.0.1') && url.port === '8000';
    if (localApiHost && url.pathname.replace(/\/$/, '') === '/api/v1') {
      return '/api/backend';
    }
  } catch {
    // Relative or otherwise non-URL values should pass through unchanged.
  }

  return configured;
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

        if (isUnauthorized(error) && isNativePlatform() && requestConfig && !requestConfig.skipAuth && !requestConfig._retryAuth) {
          requestConfig._retryAuth = true;
          const token = await refreshNativeAccessToken();
          if (token) {
            requestConfig.headers = {
              ...(requestConfig.headers || {}),
              Authorization: `Bearer ${token}`,
            };
            return this.api.request(requestConfig);
          }
          await clearNativeAuthSession();
          if (typeof window !== 'undefined' && window.location.pathname !== '/auth/signin') {
            window.location.assign('/auth/signin');
          }
          return Promise.reject(error);
        }

        if (detail?.code === 'feuilleton_generation_failed') {
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

  // User endpoints
  async getCurrentUser() {
    return this.get('/users/me');
  }

  async getSettings() {
    return this.get('/users/me/settings');
  }

  async updateSettings(data: any) {
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
    return this.get<{ publicKey: string }>('/notifications/vapid-public-key');
  }

  async subscribeToNotifications(subscription: any) {
    return this.post('/notifications/subscribe', subscription);
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
    return this.get(`/vocabulary/lookup?${params.toString()}`);
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
    return this.get('/progress/vocabulary/recommendations', {
      params,
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
  }

  async getVocabularyDueContext(params?: VocabularyDueContextParams): Promise<VocabularyDueContext> {
    return this.get('/vocabulary/due-context', {
      params,
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
  }

  async getVocabularyMasteryMap(params?: { limit?: number; direction?: string }): Promise<VocabularyMasteryMap> {
    return this.get('/progress/vocabulary/map', {
      params,
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
  }

  async getWeeklyDossier(params?: { period_days?: number }): Promise<WeeklyDossier> {
    return this.get('/progress/weekly-dossier', {
      params,
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
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
    return this.post('/anki/review', data);
  }

  async getWordProgress(wordId: number) {
    return this.get(`/progress/${wordId}`);
  }

  // Analytics endpoints
  async getAnalyticsSummary() {
    return this.get('/analytics/summary');
  }

  async getAnalyticsStatistics(params?: { days?: number }) {
    return this.get('/analytics/statistics', { params });
  }

  async getStreakData() {
    return this.get('/analytics/streak');
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

  // Achievement endpoints
  async getAchievements() {
    return this.get('/achievements');
  }

  async getUserAchievements() {
    return this.get('/achievements/my');
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
    return this.get(`/vocabulary/${wordId}/biography`, {
      suppressGlobalError: true,
    } as AxiosRequestConfig & { suppressGlobalError: boolean });
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
    return this.get<CEFRProgress>('/progress/cefr');
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
      resubmit?: boolean;
    }
  ) {
    return this.atelierPost<AtelierAttemptResult>(`/atelier/sessions/${sessionId}/attempts`, data);
  }

  async getAtelierAttempt(attemptId: string) {
    return this.atelierGet<AtelierAttemptResult>(`/atelier/attempts/${attemptId}`);
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
    const response = await this.atelierPost<{ mission: RealWorldMission; recap: VocabularyRecapPayload }>(`/missions/${missionId}/complete`);
    return response;
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
    formData.append('file', audioBlob, 'mission-audio.webm');

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
  }) {
    const response = await this.atelierPost<{ scene: GraphicNovelScene }>('/graphic-novel/scenes', data || {}, {
      timeout: 720000,
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
    const response = await this.atelierPost<{ scene: GraphicNovelScene; recap: VocabularyRecapPayload }>(`/graphic-novel/scenes/${sceneId}/complete`);
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
      system_prompt?: string;
      topic?: string;
      style?: string;
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
    system_prompt?: string;
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
    };
  }

  async endAudioSession(data: { session_id: string }): Promise<{
    session_id: string;
    duration_seconds: number;
    total_xp: number;
    errors_practiced: number;
    message: string;
  }> {
    return this.post<any>('/audio-session/end', data);
  }

  async transcribeAudio(audioBlob: Blob): Promise<string> {
    const formData = new FormData();
    formData.append('file', audioBlob, 'audio.webm');

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
}

export const apiService = new ApiService();
export default apiService;
