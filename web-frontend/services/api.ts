import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { getSession } from 'next-auth/react';
import toast from 'react-hot-toast';

import { AnkiReviewResponse, ReviewResponse } from '@/types/reviews';

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
        const message = error.response?.data?.detail || error.message || 'An error occurred';

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
            if (typeof message === 'object') {
              // Handle validation errors
              const validationErrors = message.detail || message;
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
  async register(userData: { email: string; password: string; name?: string }) {
    return this.post('/auth/register', userData);
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

  // Grammar Exercise endpoints
  async generateGrammarExercise(data: { concept_id: number; count?: number; focus_areas?: string[] }) {
    return this.post<{
      concept_id: number;
      concept_name: string;
      level: string;
      exercises: any[];
      flat_exercises: any[];
      explanation?: any | null;
    }>('/grammar/exercise/generate', data);
  }

  async checkGrammarAnswers(data: { concept_id: number; exercises: any[]; answers: string[] }) {
    return this.post('/grammar/exercise/check', data);
  }

  // Daily Practice (Unified SRS) endpoints
  async getDailyPracticeSummary() {
    return this.get('/daily-practice/summary');
  }

  async getDailyPracticeQueue(settings?: {
    time_budget_minutes?: number | null;
    new_vocab_limit?: number;
    new_grammar_limit?: number;
    interleaving_mode?: 'random' | 'blocks' | 'priority';
  }) {
    return this.post('/daily-practice/queue', settings || {});
  }

  async completePracticeItem(
    itemType: string,
    itemId: string,
    data: { rating: number; response_time_ms?: number }
  ) {
    return this.post(`/daily-practice/complete/${itemType}/${itemId}`, data);
  }

  // Brief Exercise endpoints (for interactive daily practice)
  async generateBriefGrammarExercises(conceptId: number) {
    return this.post<{
      concept_id: number;
      concept_name: string;
      level: string;
      exercises: Array<{
        id: string;
        type: string;
        difficulty: string;
        instruction: string;
        prompt: string;
        correct_answer: string;
        hint?: string;
      }>;
    }>(`/daily-practice/grammar/${conceptId}/exercises`);
  }

  async generateErrorExercise(errorId: string) {
    return this.post<{
      error_id: string;
      exercise_type: string;
      instruction: string;
      prompt: string;
      correct_answer: string;
      explanation: string;
      memory_tip?: string;
      original_text?: string;
      stored_correction?: string;
    }>(`/daily-practice/error/${errorId}/exercise`);
  }

  async checkBriefAnswer(data: {
    exercise_type: string;
    prompt: string;
    correct_answer: string;
    user_answer: string;
    concept_id?: number | null;
  }) {
    return this.post<{
      is_correct: boolean;
      feedback: string;
      explanation: string;
      score: number;
    }>('/daily-practice/check-answer', data);
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
