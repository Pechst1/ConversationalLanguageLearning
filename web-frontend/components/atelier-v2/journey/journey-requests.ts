/**
 * Request identity and contract-failure policy for the daily journey (WP-07).
 *
 * Deliberately framework-free so the node harness can prove the behaviour that
 * matters most and is hardest to see in a rendered component:
 *
 *   * a retry of the same intent reuses the SAME `mutation_id`;
 *   * a double tap awaits the first request instead of sending a second;
 *   * a 202 `processing` replays the identical request, honouring the server's
 *     `retry_after_seconds`, and never mints a fresh key;
 *   * a transport or provider failure is routed to a retryable state, never to
 *     a wrong-answer verdict.
 *
 * `useDailyJourney` composes these; the later visual renderer inherits them
 * unchanged because it reuses the same hook.
 */

import { journeyErrorCode, journeyErrorDetail, mutationId } from '@/services/daily-journey';
import type { JourneyErrorCode, JourneyErrorDetail } from '@/types/daily-journey';

import { detailOfPayload, isReconcileCode } from './journey-state';

/** Bounded replay of one `processing` request before the learner is asked. */
export const PROCESSING_MAX_RETRIES = 4;

// ---------------------------------------------------------------------------
// Stable idempotency keys
// ---------------------------------------------------------------------------

export type MutationKeyring = {
  /** The key for this logical intent, minted once and reused for every replay. */
  idFor: (intent: string) => string;
  /**
   * Take a key back from somewhere else — a mutation that was recovered from
   * disk after an interruption (WP-10). The recovered request is the *same*
   * request, so it must go out under its original id: minting a fresh one would
   * turn the server's dedup receipt into a second learning record.
   */
  adopt: (intent: string, id: string) => void;
  /** Drop a key once its intent is genuinely finished (a new intent follows). */
  release: (intent: string) => void;
  size: () => number;
};

export function createMutationKeyring(mint: () => string = mutationId): MutationKeyring {
  const keys = new Map<string, string>();
  return {
    idFor(intent) {
      const existing = keys.get(intent);
      if (existing) return existing;
      const created = mint();
      keys.set(intent, created);
      return created;
    },
    adopt(intent, id) {
      if (!intent || !id) return;
      keys.set(intent, id);
    },
    release(intent) {
      keys.delete(intent);
    },
    size() {
      return keys.size;
    },
  };
}

// ---------------------------------------------------------------------------
// Double-tap gate
// ---------------------------------------------------------------------------

export type RequestGate = {
  /** Runs `fn` unless the same intent is already in flight, then awaits that one. */
  run: <T>(intent: string, fn: () => Promise<T>) => Promise<T>;
  inFlight: (intent: string) => boolean;
};

export function createRequestGate(): RequestGate {
  const pending = new Map<string, Promise<unknown>>();
  return {
    run<T>(intent: string, fn: () => Promise<T>): Promise<T> {
      const existing = pending.get(intent) as Promise<T> | undefined;
      if (existing) return existing;
      const promise = fn().finally(() => {
        pending.delete(intent);
      });
      pending.set(intent, promise);
      return promise;
    },
    inFlight(intent) {
      return pending.has(intent);
    },
  };
}

// ---------------------------------------------------------------------------
// One mutation, with the frozen `processing` policy
// ---------------------------------------------------------------------------

export type MutationOutcome<T> =
  | { ok: true; value: T }
  | { ok: false; detail: JourneyErrorDetail | null; error: unknown };

export type RunMutationOptions<T> = {
  /** The stable key. The same value must be passed on every replay. */
  mutationId: string;
  invoke: (id: string) => Promise<T>;
  maxRetries?: number;
  /** Told about each replay so the renderer can show a distinct "retrying" state. */
  onRetry?: (attempt: number, afterSeconds: number) => void;
  /** Injected for tests; defaults to a real timer. */
  sleep?: (ms: number) => Promise<void>;
};

const realSleep = (ms: number): Promise<void> =>
  new Promise((resolve) => {
    setTimeout(resolve, Math.max(0, ms));
  });

/**
 * FastAPI raises `HTTPException(202, detail={...})` for `processing`, and axios
 * resolves every 2xx, so a mutation can *resolve* with an error-shaped body
 * instead of its declared model. Both routes are handled here.
 */
export async function runMutation<T>(options: RunMutationOptions<T>): Promise<MutationOutcome<T>> {
  const { mutationId: id, invoke, onRetry } = options;
  const maxRetries = options.maxRetries ?? PROCESSING_MAX_RETRIES;
  const sleep = options.sleep ?? realSleep;
  let attempt = 0;

  for (;;) {
    try {
      const value = await invoke(id);
      const detail =
        detailOfPayload(value) ?? detailOfPayload((value as { data?: unknown } | null)?.data);
      if (detail?.code === 'processing') {
        if (attempt >= maxRetries) return { ok: false, detail, error: null };
        attempt += 1;
        const wait = detail.retry_after_seconds ?? 2;
        onRetry?.(attempt, wait);
        await sleep(wait * 1000);
        continue;
      }
      if (detail) return { ok: false, detail, error: null };
      return { ok: true, value };
    } catch (error) {
      const detail = journeyErrorDetail(error);
      if (detail?.code === 'processing' && attempt < maxRetries) {
        attempt += 1;
        const wait = detail.retry_after_seconds ?? 2;
        onRetry?.(attempt, wait);
        await sleep(wait * 1000);
        continue;
      }
      return { ok: false, detail, error };
    }
  }
}

// ---------------------------------------------------------------------------
// Failure policy
// ---------------------------------------------------------------------------

export type FailurePlan =
  /** 403: the capability is off. Fall through to legacy behaviour. */
  | { kind: 'disabled' }
  /** 422 `empty_answer`: an inline prompt, explicitly not a wrong answer. */
  | { kind: 'empty'; message: string }
  /** 409 family: refetch the journey and tell the learner it was refreshed. */
  | { kind: 'reconcile'; code: JourneyErrorCode; message: string }
  /** Refetch quietly (the snapshot itself carries the new state). */
  | { kind: 'refetch' }
  /** Anything else, including an exhausted `processing` replay. */
  | { kind: 'error'; message: string; retryable: boolean };

/**
 * Maps a failed mutation onto exactly one renderable state.
 *
 * The 422 that FastAPI produces for a malformed body carries a **list** in
 * `detail`, not a structured object, so `detail.code` may legitimately be
 * absent — that lands in `error`, never in a verdict.
 */
export function planFailure(
  detail: JourneyErrorDetail | null,
  error: unknown,
  fallbackMessage = 'transport_error',
): FailurePlan {
  const code = detail?.code ?? journeyErrorCode(error);
  const message = detail?.message || journeyErrorDetail(error)?.message || fallbackMessage;

  if (code === 'journey_disabled') return { kind: 'disabled' };
  if (code === 'empty_answer') return { kind: 'empty', message };
  if (isReconcileCode(code ?? null)) {
    return { kind: 'reconcile', code: code as JourneyErrorCode, message };
  }
  if (code === 'generation_unavailable') return { kind: 'refetch' };
  // An exhausted `processing` replay has produced no `AttemptResult`, so it is
  // a retryable transport state rather than a grade.
  return { kind: 'error', message, retryable: true };
}
