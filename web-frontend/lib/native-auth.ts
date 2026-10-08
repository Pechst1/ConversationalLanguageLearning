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

/**
 * The backend a native build authenticates against.
 *
 * This used to default to `http://localhost:8000/api/v1`. A device or simulator
 * build that shipped without an explicit host would then post the learner's
 * email and password to whatever owns port 8000 — on a developer machine, a
 * different application entirely; on a device, nothing at all. The value is
 * required, and the check runs at CALL time so `next build` (which compiles
 * this module without invoking it) keeps working without the variable.
 * `scripts/native-api-env.mjs` is what supplies it for real native builds.
 */
export function nativeApiBaseUrl() {
  const configured = (
    process.env.NEXT_PUBLIC_API_BASE_URL
    || process.env.NEXT_PUBLIC_API_URL
    || ''
  ).trim();
  if (!configured) {
    throw new Error(
      'NEXT_PUBLIC_API_BASE_URL is not set, so native authentication has no '
      + 'backend to talk to. Set it to the API origin (for example '
      + 'http://localhost:8010/api/v1) before building the native app. It is '
      + 'deliberately not defaulted: guessing a port risks sending credentials '
      + 'to an unrelated service.',
    );
  }
  return normalizeApiBaseUrl(configured);
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

/**
 * What a refresh attempt established.
 *
 * - `refreshed`: a new pair is stored.
 * - `signed-out`: the server definitively refused the refresh token (401/403),
 *   or there is none. Only this clears the keychain.
 * - `unreachable`: offline, timed out, or the server failed (5xx). The tokens
 *   stay; the learner stays in the app and the next request tries again.
 */
export type NativeRefreshResult =
  | { status: 'refreshed'; accessToken: string }
  | { status: 'signed-out' }
  | { status: 'unreachable' };

const REFRESH_TIMEOUT_MS = 15_000;

/**
 * The one refresh in flight (WP-71).
 *
 * The backend rotates the refresh token on every use. Ten requests waking
 * together after the access token expired used to send ten refreshes with the
 * same token: one won, nine got 401, and each 401 wiped the keychain — the
 * learner was "signed out at random". Every caller now shares this promise.
 */
let inFlightRefresh: Promise<NativeRefreshResult> | null = null;

async function performNativeRefresh(): Promise<NativeRefreshResult> {
  const refreshToken = await readSecureValue(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    // Nothing to refresh with: whatever else is stored cannot be renewed.
    await clearNativeAuthSession();
    return { status: 'signed-out' };
  }

  let response: Response;
  const controller = typeof AbortController === 'undefined' ? null : new AbortController();
  const timer = controller ? setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS) : null;
  try {
    response = await fetch(`${nativeApiBaseUrl()}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
      signal: controller?.signal,
    });
  } catch {
    // Offline, DNS, TLS, timeout: nothing was decided about the session.
    return { status: 'unreachable' };
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (response.status === 401 || response.status === 403) {
    // Only another rotation that landed while ours was on the wire can make a
    // stored token newer than the one we sent; then the session is fine.
    const current = await readSecureValue(REFRESH_TOKEN_KEY);
    if (current && current !== refreshToken) {
      const access = await readSecureValue(ACCESS_TOKEN_KEY);
      if (access) return { status: 'refreshed', accessToken: access };
    }
    await clearNativeAuthSession();
    return { status: 'signed-out' };
  }
  if (!response.ok) return { status: 'unreachable' };

  try {
    const tokens = await response.json() as TokenResponse;
    const stored = await storeNativeTokens(tokens, refreshToken);
    return { status: 'refreshed', accessToken: stored.accessToken };
  } catch {
    // A garbled body or a keychain hiccup is not a verdict on the session.
    return { status: 'unreachable' };
  }
}

/** Refresh once for everyone who asks while a refresh is already running. */
export function refreshNativeSession(): Promise<NativeRefreshResult> {
  if (!inFlightRefresh) {
    inFlightRefresh = performNativeRefresh().finally(() => {
      inFlightRefresh = null;
    });
  }
  return inFlightRefresh;
}

/** Compatibility wrapper: the new access token, or null if there is none. */
export async function refreshNativeAccessToken() {
  const result = await refreshNativeSession();
  return result.status === 'refreshed' ? result.accessToken : null;
}

/**
 * After a request came back 401: the token it carried may simply be older than
 * the one another request already refreshed to. Reuse that before rotating
 * again; refresh (single-flight) only when the stored token is the rejected one.
 */
export async function recoverNativeAccessToken(rejectedAccessToken?: string | null): Promise<NativeRefreshResult> {
  const stored = await readSecureValue(ACCESS_TOKEN_KEY);
  if (stored && rejectedAccessToken && stored !== rejectedAccessToken && !tokenNeedsRefresh(stored)) {
    return { status: 'refreshed', accessToken: stored };
  }
  return refreshNativeSession();
}

export async function getNativeAccessToken({ refresh = true }: { refresh?: boolean } = {}) {
  const accessToken = await readSecureValue(ACCESS_TOKEN_KEY);
  if (accessToken && !tokenNeedsRefresh(accessToken)) return accessToken;
  if (!refresh) return accessToken;
  const result = await refreshNativeSession();
  if (result.status === 'refreshed') return result.accessToken;
  // Unreachable: keep sending the stored token. Offline, the request fails as
  // a network error and the learner stays in the app; back online, a 401 on it
  // comes back through recoverNativeAccessToken.
  if (result.status === 'unreachable') return accessToken;
  return null;
}

export async function loadNativeAuthSession(): Promise<NativeAuthSession | null> {
  // An offline launch an hour later keeps the session: getNativeAccessToken
  // hands back the stored (expired) token when the refresh cannot be reached.
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
