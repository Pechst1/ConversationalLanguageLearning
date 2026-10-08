/**
 * WP-43 (WP-39 D-4) — one request per endpoint per page load.
 *
 * Several Home rows each ask the server for their own small envelope in a
 * mount effect. React's development double-invocation, a view switch that
 * remounts the composition, and effects keyed on derived state turned five
 * endpoints into ~130 requests on one load. This coalesces identical calls
 * made within a short window into one in-flight promise, so every caller
 * still gets its answer and the server sees the call once.
 *
 * It is a coalescer, not a cache: once the promise settles and the window
 * closes, the next call goes to the server again. Nothing here changes what a
 * caller receives, only how many times the network is asked.
 */

type Entry = { promise: Promise<unknown>; expiresAt: number };

const inflight = new Map<string, Entry>();

/** How long a settled answer keeps being shared with late duplicate callers. */
export const ONCE_PER_LOAD_WINDOW_MS = 1500;

export function oncePerLoad<T>(key: string, fetcher: () => Promise<T>, now = Date.now()): Promise<T> {
  const existing = inflight.get(key);
  if (existing && existing.expiresAt > now) {
    return existing.promise as Promise<T>;
  }
  const promise = Promise.resolve().then(fetcher);
  const entry: Entry = { promise, expiresAt: Number.POSITIVE_INFINITY };
  inflight.set(key, entry);
  const settle = () => {
    // Late duplicates inside the window share the settled answer; a failure
    // is shared too, so a burst of callers cannot retry a failing endpoint
    // five times in the same second.
    entry.expiresAt = Date.now() + ONCE_PER_LOAD_WINDOW_MS;
  };
  promise.then(settle, settle);
  return promise;
}

/** Test seam: forget every coalesced call. */
export function resetOncePerLoad(): void {
  inflight.clear();
}
