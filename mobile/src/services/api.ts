import Constants from 'expo-constants';

export interface LoginPayload {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ApiErrorShape {
  detail?: string | Record<string, unknown> | Array<Record<string, unknown>>;
  message?: string;
  error?: string;
  [key: string]: unknown;
}

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

const expoExtra = Constants?.expoConfig?.extra as { [key: string]: unknown } | undefined;

const apiBaseUrl =
  (typeof process !== 'undefined' && process.env.EXPO_PUBLIC_API_URL) ||
  (expoExtra && typeof expoExtra === 'object' && typeof expoExtra.apiUrl === 'string'
    ? expoExtra.apiUrl
    : undefined) ||
  DEFAULT_API_BASE_URL;

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      Accept: 'application/json',
      ...init.headers
    },
    ...init
  });

  const text = await response.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (error) {
    data = text;
  }

  if (!response.ok) {
    const errorPayload = (data as ApiErrorShape | undefined) ?? {};
    let detailMessage: string | undefined;
    if (typeof errorPayload.detail === 'string') {
      detailMessage = errorPayload.detail;
    } else if (Array.isArray(errorPayload.detail) && errorPayload.detail.length > 0) {
      const firstDetail = errorPayload.detail[0];
      if (firstDetail && typeof firstDetail === 'object' && 'msg' in firstDetail) {
        const maybeMsg = (firstDetail as Record<string, unknown>).msg;
        if (typeof maybeMsg === 'string') {
          detailMessage = maybeMsg;
        }
      }
    } else if (
      errorPayload.detail &&
      typeof errorPayload.detail === 'object' &&
      'msg' in errorPayload.detail &&
      typeof (errorPayload.detail as Record<string, unknown>).msg === 'string'
    ) {
      detailMessage = (errorPayload.detail as Record<string, unknown>).msg as string;
    }
    const message =
      detailMessage ||
      (typeof errorPayload.message === 'string' && errorPayload.message) ||
      (typeof errorPayload.error === 'string' && errorPayload.error) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(message, response.status, data);
  }

  return data as T;
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  return request<TokenResponse>('/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
}

export async function fetchCurrentUser(accessToken: string): Promise<unknown> {
  return request<unknown>('/api/v1/users/me', {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${accessToken}`
    }
  });
}
