import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { getSession } from 'next-auth/react';
import toast from 'react-hot-toast';

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

export interface RealWorldMission {
  id: string;
  status: 'available' | 'in_progress' | 'completed' | string;
  cadence: 'weekly' | 'post_session' | 'ad_hoc' | string;
  mission_type: 'message' | 'explain_plan' | 'news_summary' | 'travel_work' | 'conversation' | string;
  atelier_session_id?: string | null;
  iso_year?: number | null;
  iso_week?: number | null;
  title: string;
  brief: string;
  selected_concept_ids: number[];
  target_errata_ids: string[];
  target_vocabulary_ids: number[];
  source_snapshot: Record<string, any>;
  objectives: Array<Record<string, any>>;
  prompt_payload: Record<string, any>;
  recap: Record<string, any>;
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

export interface MissionAttemptResult {
  attempt: Record<string, any>;
  correction: Record<string, any>;
  errata: Array<Record<string, any>>;
  mission: RealWorldMission;
}

export interface MissionTurnResult {
  user_turn: Record<string, any>;
  assistant_turn: Record<string, any>;
  correction: Record<string, any>;
  errata: Array<Record<string, any>>;
  mission: RealWorldMission;
}

export interface GraphicNovelPanel {
  id: string;
  panel_index: number;
  title: string;
  beat: string;
  image_prompt: string;
  image_url?: string | null;
  image_payload: Record<string, any>;
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
  personal_input_item_id?: string | null;
  title: string;
  brief: string;
  selected_concept_ids: number[];
  target_errata_ids: string[];
  target_vocabulary_ids: number[];
  source_snapshot: Record<string, any>;
  script_payload: Record<string, any>;
  recap: Record<string, any>;
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
  correction: Record<string, any>;
  errata: Array<Record<string, any>>;
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

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
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
        const session = await getSession();
        if (session?.accessToken) {
          config.headers.Authorization = `Bearer ${session.accessToken}`;
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
      (error) => {
        const detail = error.response?.data?.detail;
        const message = apiErrorMessage(error);

        if (detail?.code === 'feuilleton_generation_failed') {
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

  // User endpoints
  async getCurrentUser() {
    return this.get('/users/me');
  }

  async updateProfile(data: any) {
    return this.patch('/users/me', data);
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
  }) {
    return this.post('/sessions', data);
  }

  async quickStartSession(data?: {
    story_title?: string;
    story_url?: string;
    story_source?: string;
    story_summary?: string;
  }) {
    return this.post('/sessions/quick-start', data || {});
  }

  async getLiveStories(params?: { limit?: number; topics?: string }) {
    return this.get<LiveStoryListResponse>('/sessions/live-stories', { params });
  }

  async getSession(sessionId: string) {
    return this.get(`/sessions/${sessionId}`);
  }

  async getSessions(params?: { limit?: number; offset?: number }) {
    return this.get('/sessions', { params });
  }

  async sendMessage(sessionId: string, data: { content: string; suggested_word_ids?: number[] }) {
    return this.post(`/sessions/${sessionId}/messages`, data);
  }

  async getSessionMessages(sessionId: string, params?: { limit?: number; offset?: number }) {
    return this.get(`/sessions/${sessionId}/messages`, { params });
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

  async updateSessionStatus(sessionId: string, status: 'in_progress' | 'paused' | 'completed' | 'abandoned') {
    return this.patch(`/sessions/${sessionId}`, { status });
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
  async getVocabulary(params?: { limit?: number; offset?: number; search?: string }) {
    return this.get('/vocabulary', { params });
  }

  async getVocabularyItem(wordId: number) {
    return this.get(`/vocabulary/${wordId}`);
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
    return this.get('/grammar/due', { params });
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
    return this.get<AtelierToday>('/atelier/today');
  }

  async startAtelierSession(data?: { concept_ids?: number[]; preferred_concept_id?: number }) {
    return this.post<AtelierSessionStart>('/atelier/sessions', data || {});
  }

  async getActiveAtelierSession() {
    return this.get<{ session: AtelierSessionStart | null }>('/atelier/sessions/active');
  }

  async getAtelierSession(sessionId: string) {
    return this.get<AtelierSessionStart>(`/atelier/sessions/${sessionId}`);
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
    return this.post<AtelierAttemptResult>(`/atelier/sessions/${sessionId}/attempts`, data);
  }

  async completeAtelierSession(sessionId: string) {
    return this.post<{ session_id: string; recap: Record<string, any> }>(`/atelier/sessions/${sessionId}/complete`);
  }

  async reviewAtelierErratum(errorId: string, data?: { rating?: number; repaired?: boolean }) {
    return this.post<{ erratum: AtelierErratum }>(`/atelier/errata/${errorId}/review`, data || {});
  }

  async getAtelierErratumTask(errorId: string) {
    return this.get<{ task: AtelierErrataReviewTask }>(`/atelier/errata/${errorId}/task`);
  }

  async submitAtelierErratumAttempt(errorId: string, data: { answer_text: string }) {
    return this.post<AtelierErrataAttemptResult>(`/atelier/errata/${errorId}/attempt`, data);
  }

  // Real-world scenario missions
  async getMissionsToday() {
    return this.get<MissionToday>('/missions/today');
  }

  async createMission(data: {
    mission_type?: string;
    cadence?: string;
    atelier_session_id?: string;
    preferred_concept_ids?: number[];
    preferred_errata_ids?: string[];
    use_news?: boolean;
    custom_scenario?: string;
    desired_outcome?: string;
    relationship?: string;
    register?: string;
  }) {
    const response = await this.post<{ mission: RealWorldMission }>('/missions', data);
    return response.mission;
  }

  async getMission(missionId: string) {
    const response = await this.get<{ mission: RealWorldMission }>(`/missions/${missionId}`);
    return response.mission;
  }

  async submitMission(missionId: string, data: { text: string; mode?: 'writing' | 'chat' | 'voice' }) {
    return this.post<MissionAttemptResult>(`/missions/${missionId}/submit`, data);
  }

  async submitMissionTurn(missionId: string, data: { text: string; mode?: 'chat' | 'voice'; transcript_metadata?: Record<string, any> }) {
    return this.post<MissionTurnResult>(`/missions/${missionId}/turns`, data);
  }

  async completeMission(missionId: string) {
    const response = await this.post<{ mission: RealWorldMission; recap: Record<string, any> }>(`/missions/${missionId}/complete`);
    return response;
  }

  async transcribeMissionAudio(audioBlob: Blob): Promise<string> {
    const formData = new FormData();
    formData.append('file', audioBlob, 'mission-audio.webm');

    const response = await this.api.post<{ text: string }>('/missions/audio/transcribe', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data.text;
  }

  // Graphic Novel / Feuilleton practice
  async getGraphicNovelToday() {
    return this.get<GraphicNovelToday>('/graphic-novel/today');
  }

  async createGraphicNovelScene(data?: {
    cadence?: 'ad_hoc' | 'post_session' | 'weekly';
    atelier_session_id?: string;
    mission_id?: string;
    personal_input_item_id?: string;
    preferred_concept_ids?: number[];
    preferred_errata_ids?: string[];
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
    const response = await this.post<{ scene: GraphicNovelScene }>('/graphic-novel/scenes', data || {}, {
      timeout: 720000,
    });
    return response.scene;
  }

  async getGraphicNovelScene(sceneId: string) {
    const response = await this.get<{ scene: GraphicNovelScene }>(`/graphic-novel/scenes/${sceneId}`);
    return response.scene;
  }

  async submitGraphicNovelAttempt(sceneId: string, data: { task_id: string; answer_payload: Record<string, any> }) {
    return this.post<GraphicNovelAttemptResult>(`/graphic-novel/scenes/${sceneId}/attempts`, data);
  }

  async completeGraphicNovelScene(sceneId: string) {
    const response = await this.post<{ scene: GraphicNovelScene; recap: Record<string, any> }>(`/graphic-novel/scenes/${sceneId}/complete`);
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
