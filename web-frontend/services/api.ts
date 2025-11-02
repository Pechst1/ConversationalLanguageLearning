// API augmentation for review-on-click
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { getSession } from 'next-auth/react';
import toast from 'react-hot-toast';

class ApiService {
  private api: AxiosInstance;
  constructor() {
    this.api = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
    this.setupInterceptors();
  }
  private setupInterceptors() {
    this.api.interceptors.request.use(async (config) => {
      const session = await getSession();
      if (session?.accessToken) config.headers.Authorization = `Bearer ${session.accessToken}`;
      return config;
    });
    this.api.interceptors.response.use((r: AxiosResponse) => r, (error) => {
      const message = error.response?.data?.detail || error.message || 'An error occurred';
      toast.error(typeof message === 'string' ? message : 'Validation error');
      return Promise.reject(error);
    });
  }
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return (await this.api.get<T>(url, config)).data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return (await this.api.post<T>(url, data, config)).data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return (await this.api.patch<T>(url, data, config)).data;
  }

  async register(data: { name: string; email: string; password: string }) {
    const payload = {
      email: data.email,
      password: data.password,
      full_name: data.name,
    };
    return this.post('/auth/register', payload);
  }

  async createSession(data: {
    topic?: string;
    planned_duration_minutes: number;
    conversation_style?: string;
    difficulty_preference?: string;
    generate_greeting?: boolean;
    anki_direction?: 'fr_to_de' | 'de_to_fr' | 'both';
  }) {
    const response = await this.post<{
      session: any;
      assistant_turn?: any;
    }>('/sessions', data);

    const session = response?.session ?? {};
    const assistantTurn = response?.assistant_turn ?? {};
    const assistantMessage = assistantTurn?.message ?? {};
    const targets = assistantTurn?.targets ?? assistantMessage?.target_details ?? [];

    return {
      ...response,
      id: session.id,
      status: session.status,
      created_at: session.started_at,
      ended_at: session.completed_at,
      xp_earned: session.xp_earned ?? 0,
      words_practiced: session.words_practiced ?? 0,
      greeting: assistantMessage.content,
      greeting_targets: targets,
    };
  }

  async sendMessage(
    sessionId: string,
    data: { content: string; suggested_word_ids?: number[] }
  ) {
    const response = await this.post<{
      session: any;
      assistant_turn: any;
      xp_awarded: number;
      word_feedback: Array<{ rating?: number | null }>;
    }>(`/sessions/${sessionId}/messages`, data);

    const assistantTurn = response?.assistant_turn ?? {};
    const assistantMessage = assistantTurn?.message ?? {};
    const targets = assistantTurn?.targets ?? assistantMessage?.target_details ?? [];
    const sessionOverview = response?.session ?? {};
    const ratings = response?.word_feedback ?? [];
    const correctAnswers = ratings.filter((item) => (item.rating ?? 0) >= 2).length;

    return {
      ...response,
      role: 'assistant',
      content: assistantMessage.content ?? '',
      timestamp: assistantMessage.created_at ?? new Date().toISOString(),
      xp: assistantMessage.xp_earned ?? response?.xp_awarded ?? 0,
      targets,
      session_stats: {
        xpEarned: sessionOverview.xp_earned ?? 0,
        wordsPracticed: sessionOverview.words_practiced ?? 0,
        correctAnswers,
        totalReviews: ratings.length,
      },
    };
  }

  async logExposure(
    sessionId: string,
    data: { word_id: number; exposure_type: 'hint' | 'translation' | 'flag' }
  ) {
    return this.post(`/sessions/${sessionId}/exposures`, data);
  }

  // New endpoint to resolve-or-create vocabulary by string
  async resolveVocabulary(data: { word: string; language: string }) {
    return this.post('/vocabulary/resolve', data);
  }

  // Existing used by ConversationHistory
  async lookupVocabulary(word: string, language?: string) {
    const params = new URLSearchParams({ word });
    if (language) params.set('language', language);
    return this.get(`/vocabulary/lookup?${params.toString()}`);
  }

  // Submit SRS rating: 0=Again, 1=Hard
  async submitReview(data: { word_id: number; rating: 0 | 1 | 2 | 3 }) {
    return this.post('/progress/review', data);
  }

  async updateSessionStatus(
    sessionId: string,
    status: 'in_progress' | 'paused' | 'completed' | 'abandoned'
  ) {
    return this.patch(`/sessions/${sessionId}`, { status });
  }

  async getSession(sessionId: string) {
    const [overview, messagesResponse, summary] = await Promise.all([
      this.get<any>(`/sessions/${sessionId}`),
      this.get<{ items: any[] }>(`/sessions/${sessionId}/messages`),
      this.get<any>(`/sessions/${sessionId}/summary`).catch(() => null),
    ]);

    const messages = messagesResponse?.items ?? [];
    const formattedMessages = messages.map((message) => ({
      id: message.id,
      role: message.sender ?? message.role ?? 'assistant',
      content: message.content ?? '',
      timestamp: message.created_at ?? new Date().toISOString(),
      xp: message.xp_earned ?? 0,
      targets: message.target_details ?? message.target_words ?? [],
    }));

    const stats = summary
      ? {
          xpEarned: summary.xp_earned ?? 0,
          wordsReviewed: summary.words_reviewed ?? 0,
          newCards: summary.new_words_introduced ?? 0,
          correctAnswers: summary.correct_responses ?? 0,
          incorrectAnswers: summary.incorrect_responses ?? 0,
          totalReviews: summary.words_reviewed ?? 0,
          accuracyRate: summary.accuracy_rate ?? 0,
          sessionDuration: summary.session_duration ?? undefined,
          sessionStartTime: summary.session_start ?? undefined,
          sessionEndTime: summary.session_end ?? undefined,
        }
      : {
          xpEarned: overview?.xp_earned ?? 0,
          wordsReviewed: overview?.words_practiced ?? 0,
          totalReviews: overview?.words_practiced ?? 0,
          correctAnswers: 0,
          incorrectAnswers: 0,
        };

    return {
      ...overview,
      id: overview?.id,
      status: overview?.status,
      created_at: overview?.started_at,
      ended_at: overview?.completed_at,
      stats,
      messages: formattedMessages,
      target_words: summary?.flashcard_words ?? [],
    };
  }

  async markWordDifficult(sessionId: string, data: { word_id: number }) {
    return this.post(`/sessions/${sessionId}/difficult_words`, { word_id: data.word_id, exposure_type: 'flag' });
  }
}

export const apiService = new ApiService();
export default apiService;
