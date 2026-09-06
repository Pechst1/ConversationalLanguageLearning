/**
 * Interruption recovery for the Atelier V2 daily journey (WP-10).
 *
 * Pure and framework-free on purpose: everything that decides whether a learner
 * loses work lives here, so the node harness can drive a kill, a refresh, a
 * midnight rollover and a two-device race without a DOM or a renderer.
 * `useJourneyRecovery` is the thin React shell over it.
 *
 * Three rules the rest of the file exists to enforce:
 *
 *   1. **The server is the truth.** A cached snapshot is a picture of what the
 *      server last said. It is never merged into a newer server state and never
 *      written back — a stale local revision cannot overwrite a completion that
 *      happened on another device.
 *   2. **Replay, never re-issue.** Every journey mutation carries a receipt
 *      keyed by its `mutation_id`. Verified against the live API on 2026-09-05:
 *      replaying the identical body under the identical key returns the stored
 *      result with the same `evidence_ref` and the same revision, even after the
 *      journey has finished. So the recovery path re-sends the *stored* key and
 *      never mints a new one. A mutation whose kind is not one of the journey's
 *      receipted operations is dropped rather than guessed at.
 *   3. **Offline is readable, never inventive.** The cache can repaint the last
 *      scene and hand back an unsent draft. It cannot grade, complete, award SRS
 *      credit, or present an authored line as a live reply, so no field here
 *      carries an outcome the server did not produce.
 *
 * What is persisted is deliberately narrow: the last public snapshot, the
 * learner's own draft text, the active step, the reading position, and the
 * pending mutation's key. Never audio, never a token, never a second transcript
 * log (CONTRACT-FREEZE contract revision 1).
 */

import {
  safeReadJson,
  safeRemove,
  safeWriteJson,
  type StorageLike,
  type StorageOutcome,
} from '@/lib/pilot-resilience';
import type { JourneySnapshot, JourneyStatus, TodayEnvelope } from '@/types/daily-journey';

/** Bumping this invalidates every cached record rather than migrating it. */
export const JOURNEY_RECOVERY_VERSION = 1;

/** Under the `pilot:` prefix, so the existing sign-out sweep already clears it. */
export const JOURNEY_RECOVERY_PREFIX = 'pilot:journey-recovery:v1';

/** One learner sentence, not an essay. Bounds the record against quota. */
export const MAX_DRAFT_CHARS = 2000;
/** Drafts are kept per step; a five-step plan never needs more than this. */
export const MAX_DRAFTS = 8;
/** Yesterday's active journey must survive a night; a week-old one must not. */
export const CACHE_MAX_AGE_MS = 48 * 60 * 60 * 1000;
/** A mutation nobody could confirm within a day is not worth replaying blind. */
export const PENDING_MAX_AGE_MS = 24 * 60 * 60 * 1000;

export function journeyRecoveryKey(scope: string): string {
  return `${JOURNEY_RECOVERY_PREFIX}:${scope}`;
}

// ---------------------------------------------------------------------------
// Shapes
// ---------------------------------------------------------------------------

/**
 * The journey mutations that carry an idempotency receipt, and are therefore
 * safe to replay under their original key. Anything outside this set — every
 * legacy Atelier operation included — is never auto-retried.
 */
export const REPLAYABLE_KINDS = [
  'create',
  'retry',
  'help',
  'attempt',
  'advance',
  'pause',
  'resume',
  'finish',
] as const;

export type ReplayableKind = (typeof REPLAYABLE_KINDS)[number];

export function isReplayableKind(value: unknown): value is ReplayableKind {
  return (REPLAYABLE_KINDS as readonly string[]).indexOf(String(value)) >= 0;
}

/**
 * One in-flight intent, recorded before the request goes out.
 *
 * `intent` is WP-07's own key (`attempt:{journeyId}:{stepId}:{revision}:{body}`)
 * stored verbatim, so a resumed session hands the identical string back to the
 * keyring and the keyring hands back the identical `mutationId`.
 */
export type PendingMutation = {
  intent: string;
  mutationId: string;
  kind: ReplayableKind;
  journeyId: string | null;
  stepId: string | null;
  expectedRevision: number | null;
  /** The request body, text only. Never audio, never a credential. */
  body: unknown;
  startedAt: string;
  /** False until the request actually left the device. */
  dispatched: boolean;
};

export type JourneyDraft = { text: string; updatedAt: string };
export type ReadingPosition = { scrollY: number; updatedAt: string };

export type JourneyRecoveryRecord = {
  version: typeof JOURNEY_RECOVERY_VERSION;
  /** The account this record belongs to. A mismatch discards, never merges. */
  scope: string;
  /** Learner-local date the snapshot was taken on, for the midnight rule. */
  localDate: string;
  journeyId: string | null;
  /** Highest server revision ever seen. Monotonic; never walked backwards. */
  revision: number;
  status: JourneyStatus | null;
  activeStepId: string | null;
  snapshot: JourneySnapshot | null;
  /** Enough of the envelope to repaint honestly offline. No learner content. */
  envelope: {
    enabled: boolean;
    control_language: TodayEnvelope['control_language'];
    timezone: string;
    local_date: string;
  } | null;
  drafts: { [stepId: string]: JourneyDraft };
  reading: { [stepId: string]: ReadingPosition };
  pending: PendingMutation | null;
  cachedAt: string;
  /** Last time a server response was actually applied. Drives honest sync copy. */
  syncedAt: string | null;
};

export function emptyRecord(
  scope: string,
  localDate: string,
  now: number = Date.now(),
): JourneyRecoveryRecord {
  return {
    version: JOURNEY_RECOVERY_VERSION,
    scope,
    localDate,
    journeyId: null,
    revision: -1,
    status: null,
    activeStepId: null,
    snapshot: null,
    envelope: null,
    drafts: {},
    reading: {},
    pending: null,
    cachedAt: new Date(now).toISOString(),
    syncedAt: null,
  };
}

// ---------------------------------------------------------------------------
// What may be persisted
// ---------------------------------------------------------------------------

const CREDENTIAL_HINT = /^(bearer\s|eyj[a-z0-9_-]{8,}\.)/i;
const BINARY_URL_HINT = /^(data:|blob:)/i;

/**
 * True when a value is plain, small, learner-authored data.
 *
 * The contract's voice attempts already submit *text* from the stateless
 * transcription endpoint, so nothing legitimate in a journey body is binary.
 * Anything that looks like a blob URL, a data URI or a token is refused rather
 * than trimmed, because a body we cannot fully vouch for is one we should not
 * be replaying from disk.
 */
export function isPersistableBody(value: unknown, depth = 0): boolean {
  if (depth > 6) return false;
  if (value === null || value === undefined) return true;
  const kind = typeof value;
  if (kind === 'number' || kind === 'boolean') return true;
  if (kind === 'string') {
    const text = value as string;
    if (text.length > MAX_DRAFT_CHARS * 2) return false;
    return !BINARY_URL_HINT.test(text) && !CREDENTIAL_HINT.test(text);
  }
  if (Array.isArray(value)) {
    return value.length <= 64 && value.every((item) => isPersistableBody(item, depth + 1));
  }
  if (kind !== 'object') return false;
  const proto = Object.getPrototypeOf(value as object);
  // Blob, File, ArrayBuffer, typed arrays and class instances all fail this.
  if (proto !== Object.prototype && proto !== null) return false;
  const record = value as { [key: string]: unknown };
  const keys = Object.keys(record);
  if (keys.length > 32) return false;
  for (let index = 0; index < keys.length; index += 1) {
    const key = keys[index];
    if (/token|secret|password|authorization/i.test(key)) return false;
    if (!isPersistableBody(record[key], depth + 1)) return false;
  }
  return true;
}

export function sanitizeDraft(text: string): string {
  return String(text ?? '').slice(0, MAX_DRAFT_CHARS);
}

/** A pending record that is safe to keep, or `null` to keep nothing. */
export function sanitizePending(pending: PendingMutation | null): PendingMutation | null {
  if (!pending) return null;
  if (!isReplayableKind(pending.kind)) return null;
  if (!pending.intent || !pending.mutationId) return null;
  if (!isPersistableBody(pending.body)) return null;
  return {
    intent: String(pending.intent),
    mutationId: String(pending.mutationId),
    kind: pending.kind,
    journeyId: pending.journeyId ?? null,
    stepId: pending.stepId ?? null,
    expectedRevision:
      typeof pending.expectedRevision === 'number' ? pending.expectedRevision : null,
    body: pending.body,
    startedAt: pending.startedAt || new Date().toISOString(),
    dispatched: Boolean(pending.dispatched),
  };
}

/** Keep the record small enough that a full origin cannot orphan it. */
export function capRecord(record: JourneyRecoveryRecord): JourneyRecoveryRecord {
  const draftIds = Object.keys(record.drafts);
  if (draftIds.length <= MAX_DRAFTS) return record;
  const newest = draftIds
    .slice()
    .sort((a, b) => (record.drafts[b].updatedAt > record.drafts[a].updatedAt ? 1 : -1))
    .slice(0, MAX_DRAFTS);
  const drafts: { [stepId: string]: JourneyDraft } = {};
  newest.forEach((id) => {
    drafts[id] = record.drafts[id];
  });
  return { ...record, drafts };
}

/** A stored value that is not a record of this version is treated as a miss. */
export function isRecord(value: unknown): value is JourneyRecoveryRecord {
  const candidate = value as JourneyRecoveryRecord | null;
  return Boolean(
    candidate &&
      typeof candidate === 'object' &&
      candidate.version === JOURNEY_RECOVERY_VERSION &&
      typeof candidate.scope === 'string' &&
      typeof candidate.revision === 'number' &&
      candidate.drafts &&
      typeof candidate.drafts === 'object',
  );
}

// ---------------------------------------------------------------------------
// Mutating the record — every one of these is pure
// ---------------------------------------------------------------------------

const TERMINAL: JourneyStatus[] = ['completed', 'ended_early'];

export function isTerminal(status: JourneyStatus | null | undefined): boolean {
  return Boolean(status && TERMINAL.indexOf(status) >= 0);
}

/**
 * Fold a server snapshot into the record.
 *
 * Monotonic in the journey's own revision: an older snapshot for the same
 * journey is ignored outright. That is what stops a slow response that was
 * already superseded — or a resumed tab holding an old view — from rewriting a
 * newer state. A different journey id replaces the record wholesale, because
 * drafts and pending work belong to the journey they were written against.
 */
export function putSnapshot(
  record: JourneyRecoveryRecord,
  snapshot: JourneySnapshot,
  now: number = Date.now(),
): JourneyRecoveryRecord {
  const stamp = new Date(now).toISOString();
  if (record.journeyId && record.journeyId !== snapshot.id) {
    return {
      ...emptyRecord(record.scope, snapshot.local_date, now),
      envelope: record.envelope,
      journeyId: snapshot.id,
      revision: snapshot.revision,
      status: snapshot.status,
      activeStepId: snapshot.current_step_id,
      snapshot,
      cachedAt: stamp,
      syncedAt: stamp,
    };
  }
  if (record.journeyId === snapshot.id && snapshot.revision < record.revision) {
    // Older than what we already hold: keep the newer picture, note the touch.
    return { ...record, syncedAt: stamp };
  }
  const next: JourneyRecoveryRecord = {
    ...record,
    journeyId: snapshot.id,
    localDate: snapshot.local_date,
    revision: snapshot.revision,
    status: snapshot.status,
    activeStepId: snapshot.current_step_id,
    snapshot,
    cachedAt: stamp,
    syncedAt: stamp,
  };
  return capRecord(pruneAgainstSnapshot(next, snapshot));
}

/**
 * The step a draft belongs to.
 *
 * Recall drafts are keyed by the step id; respond drafts append `:${turnIndex}`.
 * Step ids are UUIDs and carry no colon, so the first segment is the step id.
 */
export function stepIdOfDraftKey(draftKey: string): string {
  const separator = draftKey.indexOf(':');
  return separator === -1 ? draftKey : draftKey.slice(0, separator);
}

/**
 * Drop work the server says is finished.
 *
 * A draft for a step the server has completed was submitted; keeping it would
 * repaint an answer the learner already sent. A terminal journey keeps no draft
 * and no pending mutation at all.
 */
export function pruneAgainstSnapshot(
  record: JourneyRecoveryRecord,
  snapshot: JourneySnapshot,
): JourneyRecoveryRecord {
  if (isTerminal(snapshot.status)) {
    return { ...record, drafts: {}, reading: {}, pending: null };
  }
  const open: { [stepId: string]: true } = {};
  snapshot.steps.forEach((step) => {
    if (step.status === 'pending' || step.status === 'active') open[step.id] = true;
  });
  const drafts: { [draftKey: string]: JourneyDraft } = {};
  Object.keys(record.drafts).forEach((draftKey) => {
    // A respond draft is keyed `${stepId}:${turnIndex}` so a new turn starts
    // clean, while a recall draft is keyed by the step id alone. Compare on the
    // step id in both cases: matching the whole key dropped every respond draft
    // on the next snapshot write, losing text the learner had typed.
    if (open[stepIdOfDraftKey(draftKey)]) drafts[draftKey] = record.drafts[draftKey];
  });
  return { ...record, drafts };
}

export function putEnvelope(
  record: JourneyRecoveryRecord,
  envelope: TodayEnvelope,
  now: number = Date.now(),
): JourneyRecoveryRecord {
  return {
    ...record,
    localDate: envelope.local_date || record.localDate,
    envelope: {
      enabled: envelope.enabled,
      control_language: envelope.control_language,
      timezone: envelope.timezone,
      local_date: envelope.local_date,
    },
    cachedAt: new Date(now).toISOString(),
  };
}

export function putDraft(
  record: JourneyRecoveryRecord,
  stepId: string,
  text: string,
  now: number = Date.now(),
): JourneyRecoveryRecord {
  const value = sanitizeDraft(text);
  if (!stepId) return record;
  const drafts = { ...record.drafts };
  if (!value) delete drafts[stepId];
  else drafts[stepId] = { text: value, updatedAt: new Date(now).toISOString() };
  return capRecord({ ...record, drafts });
}

export function readDraft(record: JourneyRecoveryRecord | null, stepId: string | null): string {
  if (!record || !stepId) return '';
  return record.drafts[stepId]?.text ?? '';
}

export function putReading(
  record: JourneyRecoveryRecord,
  stepId: string,
  scrollY: number,
  now: number = Date.now(),
): JourneyRecoveryRecord {
  if (!stepId || !Number.isFinite(scrollY)) return record;
  return {
    ...record,
    reading: {
      ...record.reading,
      [stepId]: { scrollY: Math.max(0, Math.round(scrollY)), updatedAt: new Date(now).toISOString() },
    },
  };
}

export function readReading(record: JourneyRecoveryRecord | null, stepId: string | null): number {
  if (!record || !stepId) return 0;
  return record.reading[stepId]?.scrollY ?? 0;
}

export function putPending(
  record: JourneyRecoveryRecord,
  pending: PendingMutation | null,
): JourneyRecoveryRecord {
  return { ...record, pending: sanitizePending(pending) };
}

// ---------------------------------------------------------------------------
// Resume
// ---------------------------------------------------------------------------

export type ResumeSource = 'server' | 'cache' | 'none';

export type ResumeDecision = {
  /** What the shell should paint. `cache` only ever happens without a server view. */
  source: ResumeSource;
  /** True when the cached record must be thrown away rather than shown. */
  discardCache: boolean;
  journeyId: string | null;
  stepId: string | null;
  draft: string;
  scrollY: number;
  /** The cached picture is from an earlier learner-local day. */
  stale: boolean;
  reason:
    | 'server'
    | 'offline_cache'
    | 'foreign_account'
    | 'cache_expired'
    | 'different_journey'
    | 'nothing_cached'
    | 'no_view';
};

export type ReconcileInput = {
  record: JourneyRecoveryRecord | null;
  /** The snapshot `/today` (or `/{id}`) just returned, or `null` when offline. */
  server: JourneySnapshot | null;
  scope: string;
  localDate: string;
  now?: number;
};

/**
 * Decide what a resumed session shows, and whether the cache survives.
 *
 * The server always wins when it answered. The cache is only ever *painted*
 * when there is no server view at all, and even then it is labelled stale once
 * the learner-local date has moved on — an old scene may be read, never
 * presented as today's work.
 */
export function reconcileResume(input: ReconcileInput): ResumeDecision {
  const { record, server, scope, localDate } = input;
  const now = input.now ?? Date.now();

  const fromServer = (reason: ResumeDecision['reason'], discardCache: boolean): ResumeDecision => {
    const stepId = server ? server.current_step_id : null;
    return {
      source: server ? 'server' : 'none',
      discardCache,
      journeyId: server ? server.id : null,
      stepId,
      draft: discardCache ? '' : readDraft(record, stepId),
      scrollY: discardCache ? 0 : readReading(record, stepId),
      stale: false,
      reason,
    };
  };

  if (!record) return server ? fromServer('server', false) : {
    source: 'none',
    discardCache: false,
    journeyId: null,
    stepId: null,
    draft: '',
    scrollY: 0,
    stale: false,
    reason: server ? 'server' : 'nothing_cached',
  };

  // A record written by another learner is never merged, shown, or trusted.
  if (record.scope !== scope) return fromServer('foreign_account', true);

  const age = now - new Date(record.cachedAt).getTime();
  if (!Number.isFinite(age) || age > CACHE_MAX_AGE_MS) {
    return fromServer('cache_expired', true);
  }

  if (server) {
    if (record.journeyId && record.journeyId !== server.id) {
      // The day moved to a different journey; yesterday's drafts are not this
      // journey's answers.
      return fromServer('different_journey', true);
    }
    return fromServer('server', false);
  }

  // No server view: repaint what we own, honestly labelled.
  if (!record.snapshot) {
    return {
      source: 'none',
      discardCache: false,
      journeyId: record.journeyId,
      stepId: null,
      draft: '',
      scrollY: 0,
      stale: record.localDate !== localDate,
      reason: 'no_view',
    };
  }
  return {
    source: 'cache',
    discardCache: false,
    journeyId: record.journeyId,
    stepId: record.activeStepId,
    draft: readDraft(record, record.activeStepId),
    scrollY: readReading(record, record.activeStepId),
    stale: record.localDate !== localDate,
    reason: 'offline_cache',
  };
}

// ---------------------------------------------------------------------------
// Pending mutation policy
// ---------------------------------------------------------------------------

export type PendingPlan =
  /** Re-send the identical body under the stored key. The receipt dedups it. */
  | { action: 'replay'; mutationId: string; intent: string; reason: 'unconfirmed' }
  /** Keep it; there is no connection to settle it against. */
  | { action: 'hold'; reason: 'offline' }
  /** Forget it without sending anything. */
  | {
      action: 'drop';
      reason: 'unsafe_kind' | 'foreign_journey' | 'expired' | 'never_dispatched' | 'malformed';
    };

export type PendingPlanInput = {
  pending: PendingMutation | null;
  server: JourneySnapshot | null;
  online: boolean;
  now?: number;
};

/**
 * What to do with the mutation that was in flight when the app went away.
 *
 * Verified against the live API on 2026-09-05: replaying a journey mutation
 * under its original `mutation_id` returns the stored receipt — same
 * `evidence_ref`, same revision — and does so even once the journey has
 * finished. Replay is therefore the *safe* action, and the one that hands the
 * learner back the feedback they never saw. What must never be replayed is a
 * mutation we cannot vouch for: a kind outside the receipted journey set (every
 * legacy Atelier operation), a body that failed the persistence check, or one
 * aimed at a journey this account no longer has.
 *
 * A mutation that was recorded but never dispatched is dropped rather than
 * sent: the learner did not see it leave, and re-sending it on their behalf
 * after a restart would submit an answer they may have abandoned.
 */
export function planPendingReplay(input: PendingPlanInput): PendingPlan {
  const { pending, server, online } = input;
  const now = input.now ?? Date.now();
  if (!pending) return { action: 'drop', reason: 'malformed' };
  if (!sanitizePending(pending)) {
    return { action: 'drop', reason: isReplayableKind(pending.kind) ? 'malformed' : 'unsafe_kind' };
  }
  const startedAt = new Date(pending.startedAt).getTime();
  if (!Number.isFinite(startedAt) || now - startedAt > PENDING_MAX_AGE_MS) {
    return { action: 'drop', reason: 'expired' };
  }
  if (!pending.dispatched) return { action: 'drop', reason: 'never_dispatched' };
  if (!online) return { action: 'hold', reason: 'offline' };
  if (pending.journeyId && server && pending.journeyId !== server.id) {
    return { action: 'drop', reason: 'foreign_journey' };
  }
  return {
    action: 'replay',
    mutationId: pending.mutationId,
    intent: pending.intent,
    reason: 'unconfirmed',
  };
}

// ---------------------------------------------------------------------------
// Connection state — described, never dramatised
// ---------------------------------------------------------------------------

export type ConnectionStateKind =
  /** Connected and the local view came from the server. */
  | 'live'
  /** Connected, one intent is on the wire and not yet confirmed. */
  | 'syncing'
  /** No connection; what is on screen is a cached copy the learner owns. */
  | 'offline_cached'
  /** No connection and nothing cached to read. */
  | 'offline_empty'
  /** Connected again with work still waiting to be settled. */
  | 'pending_sync';

export type ConnectionView = {
  state: ConnectionStateKind;
  online: boolean;
  /** True when what is painted is a cached copy rather than a server answer. */
  readingCache: boolean;
  /** True when a draft or a mutation is still waiting on the server. */
  unsent: boolean;
  /** The cached copy is from an earlier learner-local day. */
  stale: boolean;
  lastSyncedAt: string | null;
};

export function connectionView(input: {
  online: boolean;
  source: ResumeSource;
  pending: PendingMutation | null;
  unsentDraft: boolean;
  stale: boolean;
  lastSyncedAt: string | null;
  inFlight?: boolean;
}): ConnectionView {
  const unsent = Boolean(input.pending) || input.unsentDraft;
  const readingCache = input.source === 'cache';
  let state: ConnectionStateKind;
  if (!input.online) {
    state = readingCache || input.source === 'server' ? 'offline_cached' : 'offline_empty';
  } else if (input.inFlight) {
    state = 'syncing';
  } else if (unsent) {
    state = 'pending_sync';
  } else {
    state = 'live';
  }
  return {
    state,
    online: input.online,
    readingCache,
    unsent,
    stale: input.stale,
    lastSyncedAt: input.lastSyncedAt,
  };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export type JourneyRecoveryStore = {
  scope: string;
  read(): JourneyRecoveryRecord | null;
  /** Apply a pure update and persist it. Returns the record actually held. */
  update(
    mutate: (record: JourneyRecoveryRecord) => JourneyRecoveryRecord,
  ): JourneyRecoveryRecord;
  clear(): void;
  /** The outcome of the last write: `quota` and `denied` are both survivable. */
  lastWrite(): StorageOutcome;
  /** True once the store has proven it cannot persist anything. */
  degraded(): boolean;
};

export type CreateStoreOptions = {
  scope: string;
  localDate: string;
  storage?: StorageLike | null;
  now?: () => number;
};

/**
 * A cache that fails soft.
 *
 * Storage denial (private mode, a locked-down WKWebView) and a full origin are
 * both normal conditions on a phone, so neither is allowed to throw: the store
 * keeps serving an in-memory record and reports itself degraded. On quota it
 * sheds the snapshot first — the draft is the learner's own work and is the
 * last thing to go.
 */
export function createJourneyRecoveryStore(options: CreateStoreOptions): JourneyRecoveryStore {
  const { scope, localDate } = options;
  const storage = options.storage;
  const clock = options.now ?? (() => Date.now());
  const key = journeyRecoveryKey(scope);
  let outcome: StorageOutcome = 'ok';
  let memory: JourneyRecoveryRecord | null = null;

  const load = (): JourneyRecoveryRecord | null => {
    if (memory) return memory;
    const stored = safeReadJson<unknown>(key, null, storage);
    if (!stored) return null;
    if (!isRecord(stored)) {
      // A record from another version, or a corrupted one, is not repaired.
      safeRemove(key, storage);
      return null;
    }
    if (stored.scope !== scope) {
      safeRemove(key, storage);
      return null;
    }
    memory = stored;
    return memory;
  };

  const persist = (record: JourneyRecoveryRecord): JourneyRecoveryRecord => {
    memory = record;
    outcome = safeWriteJson(key, record, storage);
    if (outcome === 'quota') {
      // Shed the biggest field, keep the learner's own words.
      const lean: JourneyRecoveryRecord = { ...record, snapshot: null, reading: {} };
      outcome = safeWriteJson(key, lean, storage);
      if (outcome === 'ok') memory = lean;
    }
    return memory;
  };

  return {
    scope,
    read: load,
    update(mutate) {
      const current = load() ?? emptyRecord(scope, localDate, clock());
      let next: JourneyRecoveryRecord;
      try {
        next = mutate(current);
      } catch {
        // A recovery bug must not take the render path down with it.
        return current;
      }
      return persist({ ...next, scope, version: JOURNEY_RECOVERY_VERSION });
    },
    clear() {
      memory = null;
      outcome = safeRemove(key, storage);
    },
    lastWrite() {
      return outcome;
    },
    degraded() {
      return outcome === 'denied' || outcome === 'absent';
    },
  };
}

/** The learner-local date, from the same zone the journey contract uses. */
export function localDateFor(timezone: string, at: Date = new Date()): string {
  try {
    // en-CA yields ISO-shaped YYYY-MM-DD.
    return new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(at);
  } catch {
    return at.toISOString().slice(0, 10);
  }
}
