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
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> { return (await this.api.get<T>(url, config)).data; }
  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> { return (await this.api.post<T>(url, data, config)).data; }

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

  async markWordDifficult(sessionId: string, data: { word_id: number }) {
    return this.post(`/sessions/${sessionId}/difficult_words`, { word_id: data.word_id, exposure_type: 'flag' });
  }
}

export const apiService = new ApiService();
export default apiService;
