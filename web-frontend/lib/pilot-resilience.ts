const RESUME_KEY = 'pilot:resume:v1';
const EDITION_KEY = 'pilot:atelier-edition:v1';

/* ---------------------------------------------------------------------------
   Storage access (WP-10).

   Every pilot cache renders before the network answers, so a storage fault has
   to behave like a cache miss and never like an exception in the render path.
   Three real faults are handled here rather than at each call site:

     * denial      — Safari private mode and a locked-down WKWebView throw on
                     the very first `getItem`/`setItem`;
     * quota       — `QuotaExceededError` on write once the origin is full;
     * corruption  — a half-written or hand-edited value that will not parse.

   The pilot caches all live under the `pilot:` prefix, which is what
   `clearPilotResilience` sweeps at sign-out. Anything added below keeps that
   prefix so the existing sign-out policy keeps covering it.
--------------------------------------------------------------------------- */

/** The subset of `Storage` the pilot caches use, so tests can inject a fake. */
export type StorageLike = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
  key(index: number): string | null;
  readonly length: number;
};

export type StorageOutcome = 'ok' | 'quota' | 'denied' | 'absent';

/** `window.localStorage`, or `null` when the browser refuses to hand it over. */
export function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage ?? null;
  } catch {
    // Accessing the property itself throws when site data is blocked.
    return null;
  }
}

function storageOf(storage?: StorageLike | null): StorageLike | null {
  return storage === undefined ? browserStorage() : storage;
}

/** `QuotaExceededError` under either its modern name or its legacy code. */
function isQuotaError(error: unknown): boolean {
  const name = (error as { name?: unknown } | null)?.name;
  const code = (error as { code?: unknown } | null)?.code;
  return (
    name === 'QuotaExceededError' ||
    name === 'NS_ERROR_DOM_QUOTA_REACHED' ||
    code === 22 ||
    code === 1014
  );
}

/**
 * Parse a stored value, treating corruption as a miss.
 *
 * A value that will not parse is removed, so one bad write cannot make a cache
 * permanently unreadable.
 */
export function safeReadJson<T>(key: string, fallback: T, storage?: StorageLike | null): T {
  const store = storageOf(storage);
  if (!store) return fallback;
  let raw: string | null = null;
  try {
    raw = store.getItem(key);
  } catch {
    return fallback;
  }
  if (raw === null || raw === '') return fallback;
  try {
    const value = JSON.parse(raw);
    return (value ?? fallback) as T;
  } catch {
    safeRemove(key, store);
    return fallback;
  }
}

/** Write, reporting the fault instead of throwing it into the render path. */
export function safeWriteJson(
  key: string,
  value: unknown,
  storage?: StorageLike | null,
): StorageOutcome {
  const store = storageOf(storage);
  if (!store) return 'absent';
  let serialized: string;
  try {
    serialized = JSON.stringify(value);
  } catch {
    // A cyclic or non-serializable value is a caller bug, not a storage fault.
    return 'denied';
  }
  try {
    store.setItem(key, serialized);
    return 'ok';
  } catch (error) {
    return isQuotaError(error) ? 'quota' : 'denied';
  }
}

export function safeRemove(key: string, storage?: StorageLike | null): StorageOutcome {
  const store = storageOf(storage);
  if (!store) return 'absent';
  try {
    store.removeItem(key);
    return 'ok';
  } catch {
    return 'denied';
  }
}

/** Every `pilot:`-prefixed key currently held, tolerant of a hostile store. */
export function pilotKeys(storage?: StorageLike | null): string[] {
  const store = storageOf(storage);
  if (!store) return [];
  const found: string[] = [];
  try {
    for (let index = 0; index < store.length; index += 1) {
      const key = store.key(index);
      if (key && key.indexOf('pilot:') === 0) found.push(key);
    }
  } catch {
    return found;
  }
  return found;
}

export type ResumeActivity = {
  href: string;
  kind: 'atelier' | 'mission' | 'review' | 'reader';
  entityId?: string | number | null;
  updatedAt: string;
};

export function saveResumeActivity(activity: Omit<ResumeActivity, 'updatedAt'>) {
  safeWriteJson(RESUME_KEY, {
    ...activity,
    updatedAt: new Date().toISOString(),
  });
}

export function readResumeActivity(storage?: StorageLike | null): ResumeActivity | null {
  const value = safeReadJson<ResumeActivity | null>(RESUME_KEY, null, storage);
  if (!value?.href || !String(value.href).startsWith('/')) return null;
  return value;
}

export function clearResumeActivity(kind?: ResumeActivity['kind']) {
  const current = readResumeActivity();
  if (!kind || current?.kind === kind) safeRemove(RESUME_KEY);
}

export type CachedAtelierEdition<T = unknown> = {
  today: T;
  vocabularyDue: number;
  cachedAt: string;
};

export function readCachedAtelierEdition<T>(): CachedAtelierEdition<T> | null {
  const value = safeReadJson<CachedAtelierEdition<T> | null>(EDITION_KEY, null);
  return value?.today && value?.cachedAt ? value : null;
}

export function cacheAtelierEdition<T>(today: T, vocabularyDue: number) {
  safeWriteJson(EDITION_KEY, {
    today,
    vocabularyDue,
    cachedAt: new Date().toISOString(),
  });
}

export function readLocalJson<T>(key: string, fallback: T): T {
  return safeReadJson<T>(key, fallback);
}

export function writeLocalJson(key: string, value: unknown) {
  safeWriteJson(key, value);
}

export function clearLocalJson(key: string) {
  safeRemove(key);
}

/* ---------------------------------------------------------------------------
   Le Lexique — the review deck's offline copy.

   The deck paints its last known queue before the network answers. Two rules
   keep that honest: a cache older than the SRS day is not a deck any more
   (it lists cards that have since come due, moved, or been rated elsewhere),
   and a deck the learner finished must not be re-served from cache on the next
   visit — finishing clears it.
--------------------------------------------------------------------------- */

export const REVIEW_CONTEXT_KEY = 'pilot:review-context:v1';
export const REVIEW_WORD_KEY = 'pilot:review-word:v1';
export const REVIEW_CONTEXT_MAX_AGE_MS = 6 * 60 * 60 * 1000;

export type CachedReviewContext<C, S> = {
  context: C;
  wordSlate: S | null;
  cachedAt: string;
};

export function readReviewContextCache<C, S>(
  now: number = Date.now(),
): CachedReviewContext<C, S> | null {
  const cached = readLocalJson<CachedReviewContext<C, S> | null>(REVIEW_CONTEXT_KEY, null);
  if (!cached?.context || !cached.cachedAt) return null;
  const cachedAt = new Date(cached.cachedAt).getTime();
  if (Number.isNaN(cachedAt) || now - cachedAt > REVIEW_CONTEXT_MAX_AGE_MS) {
    clearLocalJson(REVIEW_CONTEXT_KEY);
    return null;
  }
  return cached;
}

export function writeReviewContextCache<C, S>(context: C, wordSlate: S | null) {
  writeLocalJson(REVIEW_CONTEXT_KEY, {
    context,
    wordSlate,
    cachedAt: new Date().toISOString(),
  });
}

/** Called when the deck runs out: no stale queue, no stale resume card. */
export function clearReviewProgress() {
  clearLocalJson(REVIEW_CONTEXT_KEY);
  clearLocalJson(REVIEW_WORD_KEY);
  clearResumeActivity('review');
}

/**
 * Remove learner-specific offline state when the account changes.
 *
 * Pilot caches render before network revalidation, so keeping them after
 * sign-out could briefly expose the previous learner's edition or draft.
 * Device preferences use other namespaces and remain intact.
 */
export function clearPilotResilience(storage?: StorageLike | null) {
  const store = storageOf(storage);
  if (!store) return;
  pilotKeys(store).forEach((key) => safeRemove(key, store));
}

/* ---------------------------------------------------------------------------
   Account scope (WP-10).

   Sign-out already sweeps every `pilot:` key. That covers the deliberate case,
   but not the ones where the app never sees a sign-out: a cold start holding a
   restored token for a different learner, a native reinstall-from-backup, or a
   session swapped underneath a suspended app. The scope marker below closes
   that hole — the first read after the identity changes wipes the previous
   learner's caches before anything can render them.

   The marker holds a digest, not the address: a device-local cache key has no
   business carrying a plaintext identity. It is not a security boundary (the
   data it guards is already on the learner's own device); it is a switch
   detector, and it must be stable across restarts, which rules out a random id.
--------------------------------------------------------------------------- */

export const ACCOUNT_SCOPE_KEY = 'pilot:account-scope:v1';
export const ANONYMOUS_SCOPE = 'anon';

/** FNV-1a/32 as unsigned hex. Stable, dependency-free, and not reversible by eye. */
export function accountScopeKey(identity: string | null | undefined): string {
  const value = String(identity ?? '').trim().toLowerCase();
  if (!value) return ANONYMOUS_SCOPE;
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    // hash *= 16777619, kept in 32-bit range without Math.imul (ES5 target).
    hash = (hash + ((hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24))) >>> 0;
  }
  return `a${hash.toString(16)}`;
}

export function readAccountScope(storage?: StorageLike | null): string | null {
  const store = storageOf(storage);
  if (!store) return null;
  try {
    return store.getItem(ACCOUNT_SCOPE_KEY);
  } catch {
    return null;
  }
}

/**
 * Record the current learner scope, clearing every pilot cache when it changed.
 *
 * Returns whether a switch was detected so a caller can also drop in-memory
 * state. A first-ever scope is not a switch: there is nothing to leak yet.
 */
export function syncAccountScope(
  scope: string,
  storage?: StorageLike | null,
): { switched: boolean; previous: string | null } {
  const store = storageOf(storage);
  if (!store) return { switched: false, previous: null };
  const previous = readAccountScope(store);
  if (previous === scope) return { switched: false, previous };
  if (previous !== null) clearPilotResilience(store);
  try {
    // Stored raw, not JSON: the marker is read before anything else and must
    // survive a store that has started rejecting writes mid-session.
    store.setItem(ACCOUNT_SCOPE_KEY, scope);
  } catch {
    // A scope we cannot persist simply re-detects on the next start.
  }
  return { switched: previous !== null, previous };
}

/* ---------------------------------------------------------------------------
   Deep-link arbitration (WP-10).

   A push tap or a universal link is an explicit destination. The native resume
   redirect in `_app` is a guess. When both fire in the same tick the explicit
   one has to win, or the learner taps a notification and lands somewhere else.

   In-memory on purpose: it describes one navigation, not a stored preference.
--------------------------------------------------------------------------- */

let resumeSuppressed = false;

export function suppressResumeRedirectOnce() {
  resumeSuppressed = true;
}

/** True exactly once after a deep link asked to own the next navigation. */
export function consumeResumeSuppression(): boolean {
  const value = resumeSuppressed;
  resumeSuppressed = false;
  return value;
}
