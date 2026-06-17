import { SecureStoragePlugin } from 'capacitor-secure-storage-plugin';

export type NativeAuthUser = {
  id?: string;
  email?: string;
  name?: string;
};

export type NativeAuthSession = {
  user: NativeAuthUser;
  accessToken: string;
  refreshToken: string;
};

type TokenResponse = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
};

const ACCESS_TOKEN_KEY = 'atelier.accessToken';
const REFRESH_TOKEN_KEY = 'atelier.refreshToken';
const USER_KEY = 'atelier.user';
const EXPIRY_SKEW_MS = 30_000;

function normalizeApiBaseUrl(value: string) {
  const trimmed = value.replace(/\/+$/, '');
  return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}

export function nativeApiBaseUrl() {
  return normalizeApiBaseUrl(
    process.env.NEXT_PUBLIC_API_BASE_URL
      || process.env.NEXT_PUBLIC_API_URL
      || 'http://localhost:8000/api/v1',
  );
}

async function readSecureValue(key: string) {
  try {
    const result = await SecureStoragePlugin.get({ key });
    return result.value || null;
  } catch {
    return null;
  }
}

async function writeSecureValue(key: string, value: string) {
  await SecureStoragePlugin.set({ key, value });
}

async function removeSecureValue(key: string) {
  try {
    await SecureStoragePlugin.remove({ key });
  } catch {
    // Already gone is a successful logout/hydration state.
  }
}

function decodeJwtExpiry(token?: string | null) {
  if (!token) return 0;
  try {
    const payload = token.split('.')[1];
    if (!payload) return 0;
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(base64.length + ((4 - base64.length % 4) % 4), '=');
    const decoded = JSON.parse(window.atob(padded));
    return typeof decoded.exp === 'number' ? decoded.exp * 1000 : 0;
  } catch {
    return 0;
  }
}

function tokenNeedsRefresh(token?: string | null) {
  const expiry = decodeJwtExpiry(token);
  return !expiry || Date.now() >= expiry - EXPIRY_SKEW_MS;
}

async function storeNativeTokens(tokens: TokenResponse, fallbackRefresh?: string | null) {
  const refreshToken = tokens.refresh_token || fallbackRefresh;
  if (!tokens.access_token || !refreshToken) {
    throw new Error('Auth response did not include usable tokens.');
  }
  await writeSecureValue(ACCESS_TOKEN_KEY, tokens.access_token);
  await writeSecureValue(REFRESH_TOKEN_KEY, refreshToken);
  return {
    accessToken: tokens.access_token,
    refreshToken,
  };
}

async function storeNativeUser(user: NativeAuthUser) {
  await writeSecureValue(USER_KEY, JSON.stringify(user));
}

async function loadNativeUser(): Promise<NativeAuthUser> {
  const raw = await readSecureValue(USER_KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as NativeAuthUser;
  } catch {
    return {};
  }
}

export async function clearNativeAuthSession() {
  await Promise.all([
    removeSecureValue(ACCESS_TOKEN_KEY),
    removeSecureValue(REFRESH_TOKEN_KEY),
    removeSecureValue(USER_KEY),
  ]);
}

export async function refreshNativeAccessToken() {
  const refreshToken = await readSecureValue(REFRESH_TOKEN_KEY);
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${nativeApiBaseUrl()}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) throw new Error('Refresh token rejected.');
    const tokens = await response.json() as TokenResponse;
    const stored = await storeNativeTokens(tokens, refreshToken);
    return stored.accessToken;
  } catch {
    await clearNativeAuthSession();
    return null;
  }
}

export async function getNativeAccessToken({ refresh = true }: { refresh?: boolean } = {}) {
  const accessToken = await readSecureValue(ACCESS_TOKEN_KEY);
  if (accessToken && !tokenNeedsRefresh(accessToken)) return accessToken;
  return refresh ? refreshNativeAccessToken() : accessToken;
}

export async function loadNativeAuthSession(): Promise<NativeAuthSession | null> {
  const accessToken = await getNativeAccessToken();
  const refreshToken = await readSecureValue(REFRESH_TOKEN_KEY);
  if (!accessToken || !refreshToken) return null;
  return {
    accessToken,
    refreshToken,
    user: await loadNativeUser(),
  };
}

export async function nativeSignInWithCredentials(email: string, password: string): Promise<NativeAuthSession> {
  const response = await fetch(`${nativeApiBaseUrl()}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    throw new Error('Invalid credentials.');
  }

  const tokens = await response.json() as TokenResponse;
  const stored = await storeNativeTokens(tokens);
  const userResponse = await fetch(`${nativeApiBaseUrl()}/users/me`, {
    headers: { Authorization: `Bearer ${stored.accessToken}` },
  });
  if (!userResponse.ok) {
    await clearNativeAuthSession();
    throw new Error('Could not load user profile.');
  }

  const profile = await userResponse.json();
  const user = {
    id: profile.id,
    email: profile.email,
    name: profile.full_name || profile.email,
  };
  await storeNativeUser(user);
  return { ...stored, user };
}

export async function nativeLogout() {
  const refreshToken = await readSecureValue(REFRESH_TOKEN_KEY);
  if (refreshToken) {
    try {
      await fetch(`${nativeApiBaseUrl()}/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
    } catch {
      // Local secure storage cleanup is the source of truth for signing out on device.
    }
  }
  await clearNativeAuthSession();
}
