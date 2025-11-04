import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { getSession } from 'next-auth/react';
import toast from 'react-hot-toast';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
      timeout: 30000,
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
    return this.put('/users/me', data);
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

  async submitReview(data: { word_id: number; rating: number }) {
    return this.post('/progress/review', data);
  }

  async submitAnkiReview(data: { word_id: number; rating: number; response_time_ms?: number }) {
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
}

export const apiService = new ApiService();
export default apiService;
