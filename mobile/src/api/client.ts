import Constants from 'expo-constants';
import {
  AuthTokens,
  TokenResponse,
  AnkiProgressSummary,
  AnkiReviewResponse,
  AnkiWordProgress,
  QueueWord,
  UserProfile,
} from '../types/api';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

class ApiClient {
  private accessToken: string | null = null;
  private baseUrl: string;

  constructor() {
    const expoApiUrl = (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl;
    const envApiUrl = process.env.EXPO_PUBLIC_API_URL;
    const fallback = 'http://localhost:8000/api/v1';
    this.baseUrl = this.normalizeBaseUrl(expoApiUrl || envApiUrl || fallback);
  }

  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  private normalizeBaseUrl(url: string) {
    const trimmed = url.replace(/\/+$/, '');
    return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
  }

  private buildUrl(path: string) {
    if (path.startsWith('http://') || path.startsWith('https://')) {
      return path;
    }
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.baseUrl}${normalizedPath}`;
  }

  private async request<T>(
    path: string,
    { skipAuth = false, headers, body, ...init }: RequestOptions = {}
  ): Promise<T> {
    const url = this.buildUrl(path);
    const requestHeaders = new Headers(headers);
    if (body && !(body instanceof FormData) && !requestHeaders.has('Content-Type')) {
      requestHeaders.set('Content-Type', 'application/json');
    }
    requestHeaders.set('Accept', 'application/json');
    if (!skipAuth && this.accessToken) {
      requestHeaders.set('Authorization', `Bearer ${this.accessToken}`);
    }

    const response = await fetch(url, {
      ...init,
      headers: requestHeaders,
      body,
    });

    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;
      try {
        const errorPayload = await response.json();
        if (typeof errorPayload?.detail === 'string') {
          message = errorPayload.detail;
        } else if (typeof errorPayload?.message === 'string') {
          message = errorPayload.message;
        }
      } catch (error) {
        // Ignore JSON parsing errors and use the default message
      }
      throw new ApiError(message, response.status);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch (error) {
      throw new ApiError('Failed to parse server response', response.status);
    }
  }

  async login(credentials: { email: string; password: string }): Promise<AuthTokens> {
    const payload = JSON.stringify(credentials);
    const tokens = await this.request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: payload,
      skipAuth: true,
    });

    const mapped: AuthTokens = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      tokenType: tokens.token_type,
    };

    return mapped;
  }

  async getCurrentUser(): Promise<UserProfile> {
    return this.request<UserProfile>('/users/me');
  }

  async getAnkiProgress(direction?: string): Promise<AnkiWordProgress[]> {
    const query = direction ? `?direction=${encodeURIComponent(direction)}` : '';
    return this.request<AnkiWordProgress[]>(`/progress/anki${query}`);
  }

  async getAnkiSummary(): Promise<AnkiProgressSummary> {
    return this.request<AnkiProgressSummary>('/progress/anki/summary');
  }

  async getReviewQueue(limit = 10, direction?: string): Promise<QueueWord[]> {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (direction) {
      params.set('direction', direction);
    }
    return this.request<QueueWord[]>(`/progress/queue?${params.toString()}`);
  }

  async submitAnkiReview(
    payload: { word_id: number; rating: number; response_time_ms?: number }
  ): Promise<AnkiReviewResponse> {
    return this.request<AnkiReviewResponse>('/anki/review', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const apiClient = new ApiClient();
