/**
 * `useJourneyRecovery` — the typed integration surface WP-07 consumes (WP-10).
 *
 * The controller in `components/atelier-v2/journey/useDailyJourney.ts` belongs
 * to WP-07 and is not edited here. This hook takes what that controller already
 * returns — structurally, so a `DailyJourneyController` satisfies it verbatim —
 * and adds the recovery behaviour around it: an account- and journey-scoped
 * cache, a resume decision, a replay plan for whatever was in flight when the
 * app went away, and an honest connection state.
 *
 * Nothing here issues a request. It decides *what* should be replayed and hands
 * the decision back; the controller owns the transport, the keyring and the
 * auth refresh, and there is deliberately no second copy of any of the three.
 *
 * What it persists: the last public snapshot, the learner's draft text, the
 * active step, the reading position, and the pending mutation's key. Never
 * audio, never a token, never a parallel transcript log.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAppSession } from '@/lib/app-auth';
import {
  accountScopeKey,
  syncAccountScope,
  type StorageOutcome,
} from '@/lib/pilot-resilience';
import {
  connectionView,
  createJourneyRecoveryStore,
  localDateFor,
  planPendingReplay,
  putDraft,
  putEnvelope,
  putPending,
  putReading,
  putSnapshot,
  readDraft,
  readReading,
  reconcileResume,
  type ConnectionView,
  type JourneyRecoveryRecord,
  type JourneyRecoveryStore,
  type PendingMutation,
  type PendingPlan,
  type ReplayableKind,
  type ResumeDecision,
} from '@/lib/journey-recovery';
import { installAppLifecycle, installConnectivityWatch, isOnline } from '@/lib/journey-lifecycle';
import type { JourneySnapshot, TodayEnvelope } from '@/types/daily-journey';

/**
 * Structurally satisfied by WP-07's `DailyJourneyController`, so wiring it is
 * `useJourneyRecovery(journey)` with no adapter and no prop drilling.
 */
export type JourneyRecoverySource = {
  envelope: TodayEnvelope | null;
  journey: JourneySnapshot | null;
  /** A mutation is in flight (`controller.busy`). */
  busy?: boolean;
};

export type BeginMutationInput = {
  intent: string;
  mutationId: string;
  kind: ReplayableKind;
  journeyId?: string | null;
  stepId?: string | null;
  expectedRevision?: number | null;
  body?: unknown;
};

export type JourneyRecoveryController = {
  /** Honest connectivity/sync state. Never a grade, never a completion. */
  connection: ConnectionView;
  /** What this mount decided to show. `null` until the first reconcile. */
  resume: ResumeDecision | null;
  /**
   * What to do with a mutation that was in flight when the app went away.
   * `action: 'replay'` carries the ORIGINAL `mutationId` — the caller must pass
   * that exact value back to its keyring rather than minting a new one.
   */
  replayPlan: PendingPlan | null;
  /** Acknowledge a replay plan so it is offered once, not on every render. */
  clearReplayPlan: () => void;

  /** The draft the learner had typed for this step, or `''`. */
  draftFor: (stepId: string | null | undefined) => string;
  saveDraft: (stepId: string, text: string) => void;
  clearDraft: (stepId: string) => void;
  /** True when some step still holds text the server has not received. */
  hasUnsentDraft: boolean;

  /** Reading position for a step, in pixels. */
  scrollFor: (stepId: string | null | undefined) => number;
  saveScroll: (stepId: string, scrollY: number) => void;

  /** Record an intent before it is sent. */
  beginMutation: (input: BeginMutationInput) => void;
  /** The request actually left the device. Only a dispatched intent is replayed. */
  markDispatched: () => void;
  /** The server answered, one way or another. Nothing left to replay. */
  settleMutation: () => void;

  /** True once the device has proven it cannot persist anything. */
  storageDegraded: boolean;
  lastWrite: StorageOutcome;
};

const DRAFT_FLUSH_MS = 400;

/**
 * The account this device is currently showing.
 *
 * A digest of the learner's own id or address — never the address itself, which
 * has no business sitting in a cache key on disk.
 */
export function useAccountScope(): string {
  const session = useAppSession();
  const identity = session.data?.user?.id || session.data?.user?.email || '';
  return useMemo(() => accountScopeKey(identity), [identity]);
}

export function useJourneyRecovery(source: JourneyRecoverySource): JourneyRecoveryController {
  const { envelope, journey } = source;
  const scope = useAccountScope();
  const timezone = envelope?.timezone || 'UTC';
  const localDate = envelope?.local_date || localDateFor(timezone);

  const [online, setOnline] = useState<boolean>(() => isOnline());
  const [resume, setResume] = useState<ResumeDecision | null>(null);
  const [replayPlan, setReplayPlan] = useState<PendingPlan | null>(null);
  const [lastWrite, setLastWrite] = useState<StorageOutcome>('ok');
  const [degraded, setDegraded] = useState(false);
  const [hasUnsentDraft, setHasUnsentDraft] = useState(false);

  const storeRef = useRef<JourneyRecoveryStore | null>(null);
  const reconciledRef = useRef<string | null>(null);
  const flushRef = useRef<{ stepId: string; text: string } | null>(null);
  const timerRef = useRef<number | null>(null);

  // A scope change wipes the previous learner's caches before anything paints.
  useEffect(() => {
    syncAccountScope(scope);
    storeRef.current = null;
    reconciledRef.current = null;
    setResume(null);
    setReplayPlan(null);
  }, [scope]);

  const store = useMemo(() => {
    const created = createJourneyRecoveryStore({ scope, localDate });
    storeRef.current = created;
    return created;
  }, [scope, localDate]);

  const commit = useCallback(
    (mutate: (record: JourneyRecoveryRecord) => JourneyRecoveryRecord) => {
      store.update(mutate);
      setLastWrite(store.lastWrite());
      setDegraded(store.degraded());
    },
    [store],
  );

  // --- connectivity -------------------------------------------------------

  useEffect(() => installConnectivityWatch(setOnline), []);

  // --- reconcile once per journey identity --------------------------------

  useEffect(() => {
    const identity = `${scope}:${journey?.id ?? 'none'}:${journey?.revision ?? -1}`;
    if (reconciledRef.current === identity) return;
    const record = store.read();
    const decision = reconcileResume({
      record,
      server: journey,
      scope,
      localDate,
    });
    // Only the FIRST reconcile for a journey offers a replay; later revisions
    // are ordinary progress, not a recovered interruption.
    const first = reconciledRef.current === null || !reconciledRef.current.startsWith(
      `${scope}:${journey?.id ?? 'none'}:`,
    );
    reconciledRef.current = identity;
    setResume(decision);

    if (decision.discardCache) {
      store.clear();
      setReplayPlan(null);
      setHasUnsentDraft(false);
      return;
    }
    if (first && record?.pending) {
      setReplayPlan(planPendingReplay({ pending: record.pending, server: journey, online }));
    }
    setHasUnsentDraft(Boolean(record && Object.keys(record.drafts).length > 0));
  }, [journey, localDate, online, scope, store]);

  // --- fold server answers into the cache ---------------------------------

  useEffect(() => {
    if (!envelope) return;
    commit((record) => putEnvelope(record, envelope));
  }, [commit, envelope]);

  useEffect(() => {
    if (!journey) return;
    commit((record) => putSnapshot(record, journey));
    // `putSnapshot` drops drafts the server has since completed, so recompute
    // rather than assume the flag still holds.
    const held = storeRef.current?.read();
    setHasUnsentDraft(Boolean(held && Object.keys(held.drafts).length > 0));
  }, [commit, journey]);

  // --- drafts -------------------------------------------------------------

  const flushDraft = useCallback(() => {
    const queued = flushRef.current;
    if (!queued) return;
    flushRef.current = null;
    if (timerRef.current !== null && typeof window !== 'undefined') {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    commit((record) => putDraft(record, queued.stepId, queued.text));
  }, [commit]);

  const saveDraft = useCallback(
    (stepId: string, text: string) => {
      if (!stepId) return;
      flushRef.current = { stepId, text };
      setHasUnsentDraft(text.trim().length > 0);
      if (typeof window === 'undefined') {
        flushDraft();
        return;
      }
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
      timerRef.current = window.setTimeout(flushDraft, DRAFT_FLUSH_MS);
    },
    [flushDraft],
  );

  const clearDraft = useCallback(
    (stepId: string) => {
      flushRef.current = null;
      commit((record) => putDraft(record, stepId, ''));
      const record = storeRef.current?.read();
      setHasUnsentDraft(Boolean(record && Object.keys(record.drafts).length > 0));
    },
    [commit],
  );

  const draftFor = useCallback(
    (stepId: string | null | undefined) => {
      if (flushRef.current && flushRef.current.stepId === stepId) return flushRef.current.text;
      return readDraft(store.read(), stepId ?? null);
    },
    [store],
  );

  const scrollFor = useCallback(
    (stepId: string | null | undefined) => readReading(store.read(), stepId ?? null),
    [store],
  );

  const saveScroll = useCallback(
    (stepId: string, scrollY: number) => {
      commit((record) => putReading(record, stepId, scrollY));
    },
    [commit],
  );

  // A backgrounded WebView may never run another timer: write the draft now.
  useEffect(
    () =>
      installAppLifecycle({
        onSuspend: flushDraft,
        onResume: (reason) => {
          if (reason === 'online') setOnline(true);
        },
      }),
    [flushDraft],
  );

  // --- pending mutation ---------------------------------------------------

  const beginMutation = useCallback(
    (input: BeginMutationInput) => {
      const pending: PendingMutation = {
        intent: input.intent,
        mutationId: input.mutationId,
        kind: input.kind,
        journeyId: input.journeyId ?? journey?.id ?? null,
        stepId: input.stepId ?? null,
        expectedRevision: input.expectedRevision ?? journey?.revision ?? null,
        body: input.body ?? null,
        startedAt: new Date().toISOString(),
        dispatched: false,
      };
      commit((record) => putPending(record, pending));
    },
    [commit, journey],
  );

  const markDispatched = useCallback(() => {
    commit((record) =>
      record.pending ? putPending(record, { ...record.pending, dispatched: true }) : record,
    );
  }, [commit]);

  const settleMutation = useCallback(() => {
    commit((record) => putPending(record, null));
    setReplayPlan(null);
  }, [commit]);

  const clearReplayPlan = useCallback(() => setReplayPlan(null), []);

  // --- derived ------------------------------------------------------------

  const record = store.read();
  const connection = useMemo<ConnectionView>(
    () =>
      connectionView({
        online,
        source: resume?.source ?? (journey ? 'server' : 'none'),
        pending: record?.pending ?? null,
        unsentDraft: hasUnsentDraft,
        stale: resume?.stale ?? false,
        lastSyncedAt: record?.syncedAt ?? null,
        inFlight: Boolean(source.busy),
      }),
    [hasUnsentDraft, journey, online, record, resume, source.busy],
  );

  return {
    connection,
    resume,
    replayPlan,
    clearReplayPlan,
    draftFor,
    saveDraft,
    clearDraft,
    hasUnsentDraft,
    scrollFor,
    saveScroll,
    beginMutation,
    markDispatched,
    settleMutation,
    storageDegraded: degraded,
    lastWrite,
  };
}

export default useJourneyRecovery;

/** Re-exported so a consumer needs one import rather than three. */
export type { ConnectionView, PendingPlan, ResumeDecision };
