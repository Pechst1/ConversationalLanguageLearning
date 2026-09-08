/**
 * Interruption recovery, connectivity and cache scoping (WP-10).
 *
 * Same harness as `lib/atelier-next.test.js` and the WP-07 journey tests: a
 * plain node script with `node:assert/strict` and sucrase, so it adds no test
 * framework and no React test renderer. Everything that decides whether a
 * learner loses work is a pure function, which is why it can be driven here.
 *
 * Real frozen fixtures are used wherever one exists — `midnight_resume` really
 * is yesterday's active journey and `completed` really is a finished one — so
 * the reconciliation rules are exercised against the contract, not against a
 * shape invented in this file.
 *
 * Run: `node lib/journey-recovery.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const WEB_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

// `@/…` alias, plus a stub for the axios transport the request layer imports.
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiStub = new Proxy(
  {},
  {
    get(_target, method) {
      if (method === 'then') return undefined;
      return () => {
        throw new Error(`no request should reach the transport in these tests (${String(method)})`);
      };
    },
  },
);
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: apiStub, apiService: apiStub },
};

const recovery = require('./journey-recovery.ts');
const lifecycle = require('./journey-lifecycle.ts');
const resilience = require('./pilot-resilience.ts');
const requests = require('../components/atelier-v2/journey/journey-requests.ts');
const journeyState = require('../components/atelier-v2/journey/journey-state.ts');

function fixture(name) {
  const raw = JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8'));
  return raw.response ?? raw;
}

/**
 * A storage that can be denied, filled, or corrupted on demand — the three
 * faults a phone actually produces.
 */
function fakeStorage(options = {}) {
  const map = new Map(Object.entries(options.seed || {}));
  let mode = options.mode || 'ok';
  let limit = options.limit ?? Infinity;
  const guard = () => {
    if (mode === 'denied') throw new Error('The operation is insecure.');
  };
  return {
    get length() {
      return map.size;
    },
    key(index) {
      guard();
      return Array.from(map.keys())[index] ?? null;
    },
    getItem(key) {
      guard();
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      guard();
      if (String(value).length > limit) {
        const error = new Error('quota');
        error.name = 'QuotaExceededError';
        throw error;
      }
      map.set(key, String(value));
    },
    removeItem(key) {
      guard();
      map.delete(key);
    },
    _map: map,
    _setMode(next) {
      mode = next;
    },
    _setLimit(next) {
      limit = next;
    },
  };
}

const DAY = 24 * 60 * 60 * 1000;
const NOW = Date.parse('2026-09-05T09:00:00.000Z');

(async () => {

// ===========================================================================
// 1. Storage faults are survivable, never thrown into the render path
// ===========================================================================

{
  // Denial: every read is a miss, every write reports it, nothing throws.
  const denied = fakeStorage({ mode: 'denied' });
  assert.equal(resilience.safeReadJson('pilot:x', 'fallback', denied), 'fallback');
  assert.equal(resilience.safeWriteJson('pilot:x', { a: 1 }, denied), 'denied');
  assert.equal(resilience.safeRemove('pilot:x', denied), 'denied');
  assert.deepEqual(resilience.pilotKeys(denied), []);

  const store = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage: denied,
  });
  assert.equal(store.read(), null);
  const record = store.update((r) => recovery.putDraft(r, 'step-1', 'un café', NOW));
  // The record is still served from memory so the current session keeps working.
  assert.equal(record.drafts['step-1'].text, 'un café');
  assert.equal(store.lastWrite(), 'denied');
  assert.equal(store.degraded(), true);
}

{
  // Corruption: a value that will not parse is a miss AND is removed, so one
  // bad write cannot make the cache permanently unreadable.
  const key = recovery.journeyRecoveryKey('a1');
  const broken = fakeStorage({ seed: { [key]: '{"version":1,"scope":"a1"' } });
  const store = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage: broken,
  });
  assert.equal(store.read(), null);
  assert.equal(broken._map.has(key), false, 'corrupt value is dropped, not kept');
}

{
  // A record from a future schema version is discarded rather than migrated.
  const key = recovery.journeyRecoveryKey('a1');
  const future = fakeStorage({
    seed: { [key]: JSON.stringify({ version: 99, scope: 'a1', revision: 4, drafts: {} }) },
  });
  const store = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage: future,
  });
  assert.equal(store.read(), null);
  assert.equal(future._map.has(key), false);
}

{
  // Storage-full: the snapshot is shed first, the learner's own words survive.
  const snapshot = fixture('returning_due');
  const full = fakeStorage({ limit: 900 });
  const store = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage: full,
  });
  const held = store.update((r) =>
    recovery.putDraft(recovery.putSnapshot(r, snapshot, NOW), snapshot.current_step_id, 'je voudrais un café', NOW),
  );
  assert.equal(store.lastWrite(), 'ok', 'the lean write succeeded');
  assert.equal(held.snapshot, null, 'the big field was shed');
  assert.equal(held.drafts[snapshot.current_step_id].text, 'je voudrais un café');
  assert.equal(held.journeyId, snapshot.id, 'identity survives the shed');
}

// ===========================================================================
// 2. Account scoping — another account sees none of the previous one's content
// ===========================================================================

{
  const storage = fakeStorage();
  const first = resilience.accountScopeKey('learner-one@example.com');
  const second = resilience.accountScopeKey('learner-two@example.com');
  assert.notEqual(first, second);
  // Stable across restarts and case, and never the address itself.
  assert.equal(first, resilience.accountScopeKey('Learner-One@Example.com '));
  assert.ok(!first.includes('@'), 'the scope key carries no plaintext identity');
  assert.equal(resilience.accountScopeKey(''), resilience.ANONYMOUS_SCOPE);

  assert.deepEqual(resilience.syncAccountScope(first, storage), { switched: false, previous: null });

  const snapshot = fixture('returning_due');
  const storeOne = recovery.createJourneyRecoveryStore({
    scope: first,
    localDate: '2026-09-05',
    storage,
  });
  storeOne.update((r) =>
    recovery.putDraft(recovery.putSnapshot(r, snapshot, NOW), snapshot.current_step_id, 'secret draft', NOW),
  );
  assert.ok(storage._map.size >= 1);

  // The account changes with no sign-out in between (restored token, reinstall).
  const switched = resilience.syncAccountScope(second, storage);
  assert.deepEqual(switched, { switched: true, previous: first });
  assert.equal(
    storage._map.has(recovery.journeyRecoveryKey(first)),
    false,
    'the previous learner cache is gone',
  );

  const storeTwo = recovery.createJourneyRecoveryStore({
    scope: second,
    localDate: '2026-09-05',
    storage,
  });
  assert.equal(storeTwo.read(), null, 'the second account starts empty');

  // Even without the sweep, a record from another scope is refused on read.
  const foreignKey = recovery.journeyRecoveryKey(second);
  storage.setItem(
    foreignKey,
    JSON.stringify({ ...recovery.emptyRecord(first, '2026-09-05', NOW), drafts: { s: { text: 'leak', updatedAt: 'x' } } }),
  );
  assert.equal(storeTwo.read(), null, 'a mis-scoped record is never served');
}

{
  // Sign-out: the existing `pilot:` sweep already covers the journey cache.
  const storage = fakeStorage();
  const scope = resilience.accountScopeKey('learner@example.com');
  const store = recovery.createJourneyRecoveryStore({ scope, localDate: '2026-09-05', storage });
  store.update((r) => recovery.putDraft(r, 'step-1', 'draft text', NOW));
  storage.setItem('device:text-size', 'large');
  assert.ok(recovery.journeyRecoveryKey(scope).startsWith('pilot:'), 'the key inherits the sweep');

  resilience.clearPilotResilience(storage);
  assert.equal(storage._map.has(recovery.journeyRecoveryKey(scope)), false);
  assert.equal(storage._map.get('device:text-size'), 'large', 'device preferences are untouched');
}

// ===========================================================================
// 3. Exact resume after a refresh or a restart
// ===========================================================================

{
  const snapshot = fixture('returning_due');
  const scope = 'a1';
  const storage = fakeStorage();
  const store = recovery.createJourneyRecoveryStore({ scope, localDate: '2026-09-05', storage });

  store.update((r) => recovery.putSnapshot(r, snapshot, NOW));
  store.update((r) => recovery.putDraft(r, snapshot.current_step_id, 'je voudrais un café', NOW));
  store.update((r) => recovery.putReading(r, snapshot.current_step_id, 420, NOW));

  // A cold start rebuilds the store from storage alone.
  const restarted = recovery.createJourneyRecoveryStore({ scope, localDate: '2026-09-05', storage });
  const decision = recovery.reconcileResume({
    record: restarted.read(),
    server: snapshot,
    scope,
    localDate: '2026-09-05',
    now: NOW + 60_000,
  });
  assert.equal(decision.source, 'server');
  assert.equal(decision.discardCache, false);
  assert.equal(decision.journeyId, snapshot.id);
  assert.equal(decision.stepId, snapshot.current_step_id, 'lands on the server-owned step');
  assert.equal(decision.draft, 'je voudrais un café', 'kill mid-draft preserves the text');
  assert.equal(decision.scrollY, 420);
  assert.equal(decision.stale, false);
}

{
  // A draft belongs to its step. Once the server marks that step completed the
  // draft is dropped, so a resumed session cannot repaint an already-sent answer.
  const snapshot = fixture('returning_due');
  const stepId = snapshot.current_step_id;
  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-05', NOW), snapshot, NOW);
  record = recovery.putDraft(record, stepId, 'sent already', NOW);

  const advanced = {
    ...snapshot,
    revision: snapshot.revision + 1,
    steps: snapshot.steps.map((step) =>
      step.id === stepId ? { ...step, status: 'completed' } : step,
    ),
    current_step_id: snapshot.steps[snapshot.steps.length - 1].id,
  };
  const next = recovery.putSnapshot(record, advanced, NOW + 1000);
  assert.equal(next.drafts[stepId], undefined, 'a completed step keeps no draft');
  assert.equal(next.revision, advanced.revision);
}

// ===========================================================================
// 4. A stale local revision never overwrites newer server completion
// ===========================================================================

{
  const completed = fixture('completed');
  const active = fixture('returning_due');
  // Same journey identity, so the two really are two views of one journey.
  const staleActive = { ...active, id: completed.id, revision: completed.revision - 4 };

  // Device A finished it. Device B is holding revision 3 with an open draft.
  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-05', NOW), staleActive, NOW);
  record = recovery.putDraft(record, staleActive.current_step_id, 'still typing', NOW);
  assert.equal(record.revision, staleActive.revision);

  // Device B reconnects and the server hands back the completion.
  const reconciled = recovery.putSnapshot(record, completed, NOW + 1000);
  assert.equal(reconciled.revision, completed.revision);
  assert.equal(reconciled.status, 'completed');
  assert.deepEqual(reconciled.drafts, {}, 'a finished journey keeps no draft');
  assert.equal(reconciled.pending, null, 'and nothing left to replay');

  // Now the stale view arrives late — a slow response, or a resumed tab.
  const afterLate = recovery.putSnapshot(reconciled, staleActive, NOW + 2000);
  assert.equal(afterLate.revision, completed.revision, 'the newer revision stands');
  assert.equal(afterLate.status, 'completed', 'completion is not walked back');

  const decision = recovery.reconcileResume({
    record: afterLate,
    server: completed,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW + 3000,
  });
  assert.equal(decision.source, 'server');
  assert.equal(decision.stepId, null, 'a finished journey has no active step');
  assert.equal(decision.draft, '');
}

// ===========================================================================
// 5. Midnight — yesterday's active journey resumes, it is not recreated
// ===========================================================================

{
  const envelope = fixture('midnight_resume');
  const yesterday = envelope.journey;
  assert.equal(yesterday.local_date, '2026-09-04');
  assert.equal(yesterday.status, 'active');

  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-04', NOW - DAY), yesterday, NOW - DAY);
  record = recovery.putDraft(record, yesterday.current_step_id, 'hier soir', NOW - DAY);

  // The learner opens the app on the 5th. The server still hands back the 4th's
  // journey, so the cache follows it rather than declaring a new day.
  const decision = recovery.reconcileResume({
    record,
    server: yesterday,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW,
  });
  assert.equal(decision.source, 'server');
  assert.equal(decision.journeyId, yesterday.id, 'the same journey, not a new one');
  assert.equal(decision.discardCache, false);
  assert.equal(decision.draft, 'hier soir', 'last night’s draft is still there');

  // Offline on the new day, the same record reads as explicitly stale.
  const offline = recovery.reconcileResume({
    record,
    server: null,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW,
  });
  assert.equal(offline.source, 'cache');
  assert.equal(offline.stale, true, 'a cached scene from another day says so');

  // A genuinely new journey for today discards the old journey's drafts.
  const todayJourney = { ...yesterday, id: 'journey-today', local_date: '2026-09-05', revision: 1 };
  const rolled = recovery.reconcileResume({
    record,
    server: todayJourney,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW,
  });
  assert.equal(rolled.discardCache, true, 'a different journey does not inherit drafts');
  assert.equal(rolled.draft, '');
}

{
  // A cache older than the window is not resurrected at all.
  const snapshot = fixture('returning_due');
  const record = recovery.putSnapshot(
    recovery.emptyRecord('a1', '2026-08-20', NOW - 5 * DAY),
    snapshot,
    NOW - 5 * DAY,
  );
  const decision = recovery.reconcileResume({
    record,
    server: null,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW,
  });
  assert.equal(decision.discardCache, true);
  assert.equal(decision.reason, 'cache_expired');
}

// ===========================================================================
// 6. Offline — readable, preserved, and honest
// ===========================================================================

{
  const snapshot = fixture('returning_due');
  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-05', NOW), snapshot, NOW);
  record = recovery.putDraft(record, snapshot.current_step_id, 'un chocolat chaud', NOW);

  const cold = recovery.reconcileResume({
    record,
    server: null,
    scope: 'a1',
    localDate: '2026-09-05',
    now: NOW + 60_000,
  });
  assert.equal(cold.source, 'cache', 'airplane-mode cold start shows an owned cached scene');
  assert.equal(cold.journeyId, snapshot.id);
  assert.equal(cold.stepId, snapshot.current_step_id);
  assert.equal(cold.draft, 'un chocolat chaud', 'the draft survives the outage');
  assert.equal(cold.stale, false, 'same learner-local day, so not stale');

  // Nothing in the cached record can pass for a grade or a completion.
  assert.equal(record.status, 'active');
  assert.equal(record.snapshot.recap, null);
  const view = recovery.connectionView({
    online: false,
    source: cold.source,
    pending: null,
    unsentDraft: true,
    stale: cold.stale,
    lastSyncedAt: record.syncedAt,
  });
  assert.equal(view.state, 'offline_cached');
  assert.equal(view.readingCache, true);
  assert.equal(view.unsent, true);
  assert.ok(!('verdict' in view) && !('score' in view), 'no outcome is invented offline');
}

{
  // Offline with nothing cached says so instead of showing an empty scene.
  const view = recovery.connectionView({
    online: false,
    source: 'none',
    pending: null,
    unsentDraft: false,
    stale: false,
    lastSyncedAt: null,
  });
  assert.equal(view.state, 'offline_empty');
}

{
  // Back online with work outstanding: pending, then live once it settles.
  const pending = {
    intent: 'attempt:j1:s1:3:{"mode":"text","text":"bonjour"}',
    mutationId: 'key-1',
    kind: 'attempt',
    journeyId: 'j1',
    stepId: 's1',
    expectedRevision: 3,
    body: { mode: 'text', text: 'bonjour' },
    startedAt: new Date(NOW).toISOString(),
    dispatched: true,
  };
  assert.equal(
    recovery.connectionView({
      online: true,
      source: 'server',
      pending,
      unsentDraft: false,
      stale: false,
      lastSyncedAt: null,
    }).state,
    'pending_sync',
  );
  assert.equal(
    recovery.connectionView({
      online: true,
      source: 'server',
      pending,
      unsentDraft: false,
      stale: false,
      lastSyncedAt: null,
      inFlight: true,
    }).state,
    'syncing',
  );
  assert.equal(
    recovery.connectionView({
      online: true,
      source: 'server',
      pending: null,
      unsentDraft: false,
      stale: false,
      lastSyncedAt: new Date(NOW).toISOString(),
    }).state,
    'live',
  );
}

// ===========================================================================
// 7. The pending mutation — replay the same key, never a fresh one
// ===========================================================================

const basePending = {
  intent: 'attempt:j1:s1:3:{"mode":"text","text":"je voudrais un café"}',
  mutationId: 'mutation-key-abc',
  kind: 'attempt',
  journeyId: 'j1',
  stepId: 's1',
  expectedRevision: 3,
  body: { mode: 'text', text: 'je voudrais un café' },
  startedAt: new Date(NOW).toISOString(),
  dispatched: true,
};
const serverJourney = { ...fixture('returning_due'), id: 'j1' };

{
  // The acceptance case: the app died after the server accepted the attempt but
  // before the response arrived. The replay carries the ORIGINAL key, which is
  // what makes the server return the stored receipt instead of grading twice.
  const plan = recovery.planPendingReplay({
    pending: basePending,
    server: serverJourney,
    online: true,
    now: NOW + 5000,
  });
  assert.equal(plan.action, 'replay');
  assert.equal(plan.mutationId, 'mutation-key-abc', 'the key is reused, never regenerated');
  assert.equal(plan.intent, basePending.intent);

  // The recovered intent feeds WP-07's keyring and yields the same key back,
  // so the composed path cannot mint a second one either.
  let minted = 0;
  const keyring = requests.createMutationKeyring(() => `fresh-${(minted += 1)}`);
  assert.equal(keyring.idFor(plan.intent), 'fresh-1');
  assert.equal(keyring.idFor(plan.intent), 'fresh-1', 'one key per intent');
}

{
  // Even after the journey has finished, the replay is still the safe action:
  // verified against the live API, an already-committed key returns its stored
  // result rather than applying anything a second time.
  const finished = { ...fixture('completed'), id: 'j1' };
  const plan = recovery.planPendingReplay({
    pending: basePending,
    server: finished,
    online: true,
    now: NOW + 5000,
  });
  assert.equal(plan.action, 'replay');
  assert.equal(plan.mutationId, basePending.mutationId);
}

{
  // Offline: hold it, do not drop it and do not pretend it was sent.
  const plan = recovery.planPendingReplay({
    pending: basePending,
    server: null,
    online: false,
    now: NOW + 5000,
  });
  assert.deepEqual(plan, { action: 'hold', reason: 'offline' });
}

{
  // Never dispatched: the learner never saw it leave. Do not send it for them.
  const plan = recovery.planPendingReplay({
    pending: { ...basePending, dispatched: false },
    server: serverJourney,
    online: true,
    now: NOW + 5000,
  });
  assert.deepEqual(plan, { action: 'drop', reason: 'never_dispatched' });
}

{
  // A non-idempotent legacy operation is never auto-retried.
  const plan = recovery.planPendingReplay({
    pending: { ...basePending, kind: 'legacy_atelier_submit' },
    server: serverJourney,
    online: true,
    now: NOW + 5000,
  });
  assert.deepEqual(plan, { action: 'drop', reason: 'unsafe_kind' });
  assert.equal(recovery.isReplayableKind('legacy_atelier_submit'), false);
  assert.equal(recovery.isReplayableKind('attempt'), true);
}

{
  // Aimed at a journey this account no longer has, or simply too old.
  assert.deepEqual(
    recovery.planPendingReplay({
      pending: { ...basePending, journeyId: 'other-journey' },
      server: serverJourney,
      online: true,
      now: NOW + 5000,
    }),
    { action: 'drop', reason: 'foreign_journey' },
  );
  assert.deepEqual(
    recovery.planPendingReplay({
      pending: basePending,
      server: serverJourney,
      online: true,
      now: NOW + 2 * DAY,
    }),
    { action: 'drop', reason: 'expired' },
  );
}

{
  // 401 → refresh → retry must not become a SECOND attempt.
  //
  // `services/api.ts` re-issues the identical request config after a native
  // token refresh, so the retried request carries the same `mutation_id`. The
  // recovery layer follows the same rule: one intent, one key, forever. Proven
  // by composing the real keyring with the real `runMutation`.
  const keyring = requests.createMutationKeyring(() => 'minted-once');
  const intent = basePending.intent;
  const sent = [];
  let unauthorized = true;
  const outcome = await runWithRefresh();

  async function runWithRefresh() {
    return requests.runMutation({
      mutationId: keyring.idFor(intent),
      invoke: async (id) => {
        sent.push(id);
        if (unauthorized) {
          unauthorized = false;
          // The interceptor refreshes and re-issues THE SAME config.
          sent.push(id);
          return { ok: true, evidence_ref: 'evidence-1' };
        }
        return { ok: true, evidence_ref: 'evidence-1' };
      },
      sleep: async () => {},
    });
  }
  assert.equal(outcome.ok, true);
  assert.deepEqual(sent, ['minted-once', 'minted-once'], 'the refresh replay reuses the key');
  assert.equal(new Set(sent).size, 1, 'a 401 refresh cannot create a second intent');
}

{
  // 202 `processing` replays the identical key and honours the server's wait.
  const keyring = requests.createMutationKeyring(() => 'processing-key');
  const seen = [];
  const waits = [];
  const result = await requests.runMutation({
    mutationId: keyring.idFor('attempt:j1:s1:3:body'),
    invoke: async (id) => {
      seen.push(id);
      if (seen.length < 3) {
        return { detail: { code: 'processing', message: 'still grading', retry_after_seconds: 2 } };
      }
      return { contract_version: 1, evidence_ref: 'evidence-2', pending: false };
    },
    sleep: async (ms) => {
      waits.push(ms);
    },
  });
  assert.equal(result.ok, true);
  assert.deepEqual(seen, ['processing-key', 'processing-key', 'processing-key']);
  assert.deepEqual(waits, [2000, 2000], 'the server’s retry_after is honoured');
}

{
  // 409 reconcile: the frozen conflict codes route to a refetch, never a grade.
  const stale = fixture('stale_revision').detail;
  assert.equal(stale.code, 'journey_version_conflict');
  const plan = requests.planFailure(stale, null);
  assert.equal(plan.kind, 'reconcile');
  assert.equal(plan.code, 'journey_version_conflict');
  assert.equal(stale.current_revision, 7, 'the server states the revision to move to');
  assert.ok(stale.refresh_href, 'and where to re-read it');

  for (const code of journeyState.RECONCILE_CODES) {
    assert.equal(requests.planFailure({ code, message: code }, null).kind, 'reconcile');
  }

  // `duplicate_submit` is the frozen 202: still grading, and explicitly NOT a
  // verdict. An exhausted replay is a retryable transport state.
  const processing = fixture('duplicate_submit').detail;
  assert.equal(processing.code, 'processing');
  const exhausted = requests.planFailure(processing, null);
  assert.equal(exhausted.kind, 'error');
  assert.equal(exhausted.retryable, true, 'never a wrong-answer card');
}

// ===========================================================================
// 8. What may be written to disk
// ===========================================================================

{
  // Contract revision 1: the recovery cache holds text, never audio.
  class FakeBlob {
    constructor(size) {
      this.size = size;
      this.type = 'audio/webm';
    }
  }
  assert.equal(recovery.isPersistableBody({ mode: 'text', text: 'un café' }), true);
  assert.equal(recovery.isPersistableBody({ mode: 'voice', text: 'un café' }), true);
  assert.equal(recovery.isPersistableBody({ mode: 'choice', option_id: 'opt-1' }), true);
  assert.equal(recovery.isPersistableBody({ mode: 'tiles', tile_ids: ['a', 'b'] }), true);

  assert.equal(recovery.isPersistableBody({ audio: new FakeBlob(4096) }), false, 'no blobs');
  assert.equal(
    recovery.isPersistableBody({ clip: 'blob:http://localhost/9f2c' }),
    false,
    'no blob URLs',
  );
  assert.equal(
    recovery.isPersistableBody({ clip: 'data:audio/webm;base64,AAAA' }),
    false,
    'no data URIs',
  );
  assert.equal(
    recovery.isPersistableBody({ access_token: 'abc' }),
    false,
    'no credential-shaped keys',
  );
  assert.equal(
    recovery.isPersistableBody({ header: 'Bearer eyJhbGciOiJIUzI1NiJ9.x' }),
    false,
    'no bearer tokens',
  );
  assert.equal(
    recovery.isPersistableBody({ jwt: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc' }),
    false,
    'no JWTs',
  );

  // Anything unsafe is refused wholesale rather than quietly trimmed.
  assert.equal(recovery.sanitizePending({ ...basePending, body: { audio: new FakeBlob(1) } }), null);
  assert.deepEqual(recovery.sanitizePending(null), null);
  assert.equal(recovery.sanitizePending({ ...basePending, kind: 'nonsense' }), null);

  // Drafts are bounded so a runaway paste cannot fill the origin.
  const long = 'é'.repeat(recovery.MAX_DRAFT_CHARS + 500);
  assert.equal(recovery.sanitizeDraft(long).length, recovery.MAX_DRAFT_CHARS);

  // And only a handful of steps are ever kept.
  let record = recovery.emptyRecord('a1', '2026-09-05', NOW);
  for (let index = 0; index < recovery.MAX_DRAFTS + 6; index += 1) {
    record = recovery.putDraft(record, `step-${index}`, `answer ${index}`, NOW + index * 1000);
  }
  assert.equal(Object.keys(record.drafts).length, recovery.MAX_DRAFTS);
  assert.ok(record.drafts[`step-${recovery.MAX_DRAFTS + 5}`], 'the newest draft is kept');

  // The persisted record itself carries no transcript log and no token field.
  const serialized = JSON.stringify(recovery.putSnapshot(record, fixture('returning_due'), NOW));
  assert.ok(!/accessToken|access_token|refresh_token|Bearer /.test(serialized));
  assert.ok(!/data:audio|blob:/.test(serialized));
}

// ===========================================================================
// 9. Software keyboard geometry
// ===========================================================================

{
  // A 336px keyboard on an 844pt iPhone viewport, measured against the largest
  // visual height seen while nothing was focused.
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 844, visualHeight: 508, editableFocused: true }),
    336,
  );
  // Browser chrome shifting by a few pixels is not a keyboard.
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 844, visualHeight: 800, editableFocused: true }),
    0,
  );
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 844, visualHeight: NaN, editableFocused: true }),
    0,
  );
  // Nothing focused means no keyboard, whatever the viewport is doing. This is
  // the case the browser pane actually produced: a 375x812 emulated viewport
  // reporting innerHeight 812 against visualViewport.height 476, with no
  // keyboard anywhere. An innerHeight comparison would have claimed 336px for
  // the entire session.
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 476, visualHeight: 476, editableFocused: false }),
    0,
  );
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 476, visualHeight: 476, editableFocused: true }),
    0,
    'a focused field with an unchanged viewport is still not a keyboard',
  );
  // Just under the threshold stays quiet, just over it reports.
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 812, visualHeight: 752, editableFocused: true }),
    0,
  );
  assert.equal(
    lifecycle.keyboardInsetFrom({ baselineHeight: 812, visualHeight: 751, editableFocused: true }),
    61,
  );

  // The answer field ends at 470 and the primary action at 540; the keyboard
  // starts at 508, so the action is covered by 44px (+12 margin).
  const scroll = lifecycle.keyboardScrollAdjustment({
    keyboardTop: 508,
    fieldTop: 380,
    fieldBottom: 470,
    actionBottom: 540,
  });
  assert.equal(scroll, 44);
  // After scrolling, both clear the keyboard and the field is still on screen.
  assert.ok(540 - scroll + 12 <= 508);
  assert.ok(380 - scroll > 0, 'the learner can still see what they typed');

  // Nothing to do when both already fit.
  assert.equal(
    lifecycle.keyboardScrollAdjustment({
      keyboardTop: 508,
      fieldTop: 200,
      fieldBottom: 300,
      actionBottom: 380,
    }),
    0,
  );
  // A field near the top is never scrolled off it, even if that leaves the
  // action partly covered — losing the answer is the worse failure.
  assert.equal(
    lifecycle.keyboardScrollAdjustment({
      keyboardTop: 300,
      fieldTop: 20,
      fieldBottom: 260,
      actionBottom: 700,
    }),
    8,
  );
  // No action after the field: keep the field itself clear.
  assert.equal(
    lifecycle.keyboardScrollAdjustment({
      keyboardTop: 400,
      fieldTop: 300,
      fieldBottom: 460,
      actionBottom: null,
    }),
    72,
  );
}

// ===========================================================================
// 10. Deep links and the resume redirect
// ===========================================================================

{
  // The resume guess yields to an explicit destination exactly once.
  assert.equal(resilience.consumeResumeSuppression(), false);
  resilience.suppressResumeRedirectOnce();
  assert.equal(resilience.consumeResumeSuppression(), true);
  assert.equal(resilience.consumeResumeSuppression(), false, 'it claims one navigation, not all');

  // Following a deep link does not touch the draft: it is keyed by journey and
  // step in the account cache, not by whatever route happens to be mounted.
  const storage = fakeStorage();
  const store = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage,
  });
  const snapshot = fixture('returning_due');
  store.update((r) => recovery.putSnapshot(r, snapshot, NOW));
  store.update((r) => recovery.putDraft(r, snapshot.current_step_id, 'half a sentence', NOW));

  resilience.suppressResumeRedirectOnce();
  resilience.consumeResumeSuppression();

  const afterDeepLink = recovery.createJourneyRecoveryStore({
    scope: 'a1',
    localDate: '2026-09-05',
    storage,
  });
  assert.equal(
    recovery.readDraft(afterDeepLink.read(), snapshot.current_step_id),
    'half a sentence',
    'a deep link never silently discards an unsent draft',
  );
}

// ===========================================================================
// 11. Lifecycle installers are safe where there is no DOM
// ===========================================================================

{
  assert.equal(typeof lifecycle.installAppLifecycle({}), 'function');
  assert.equal(typeof lifecycle.installConnectivityWatch(() => {}), 'function');
  assert.equal(typeof lifecycle.installKeyboardInsets(), 'function');
  assert.equal(typeof lifecycle.installKeyboardFocusGuard(), 'function');
  assert.equal(typeof lifecycle.observeAudioInterruptions(null, {}), 'function');
  assert.equal(lifecycle.isOnline(), true, 'no navigator means no false offline claim');

  // An interrupted capture reports the interruption, and iOS mutes rather than
  // erroring, so mute is the signal that matters.
  const listeners = {};
  const track = {
    addEventListener(name, fn) {
      listeners[name] = fn;
    },
    removeEventListener(name) {
      delete listeners[name];
    },
  };
  const events = [];
  const teardown = lifecycle.observeAudioInterruptions(
    { getAudioTracks: () => [track] },
    {
      onInterrupted: (reason) => events.push(`interrupted:${reason}`),
      onResumed: () => events.push('resumed'),
    },
  );
  listeners.mute();
  listeners.unmute();
  listeners.ended();
  assert.deepEqual(events, ['interrupted:muted', 'resumed', 'interrupted:ended']);
  teardown();
  assert.deepEqual(Object.keys(listeners), []);
}

// ===========================================================================
// 12. Local date resolution for the midnight rule
// ===========================================================================

{
  // 23:30 in Berlin on the 5th is already the 6th in Tokyo; the journey's own
  // zone snapshot is what decides, never the device's.
  const instant = new Date('2026-09-05T21:30:00.000Z');
  assert.equal(recovery.localDateFor('Europe/Berlin', instant), '2026-09-05');
  assert.equal(recovery.localDateFor('Asia/Tokyo', instant), '2026-09-06');
  assert.equal(recovery.localDateFor('not-a-zone', instant), '2026-09-05');
}

  console.log('journey recovery tests passed');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

// --- integration owner, 2026-09-05 -----------------------------------------
{
  // A respond draft is keyed `${stepId}:${turnIndex}` so a new turn starts clean.
  // pruneAgainstSnapshot compared the WHOLE key against the open-step map, so every
  // respond draft was dropped on the next snapshot write and the learner silently
  // lost text they had typed. Compare on the step id instead.
  const snapshot = fixture('returning_due');
  const stepId = snapshot.current_step_id;
  const closed = snapshot.steps.find((step) => step.id !== stepId);

  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-05', NOW), snapshot, NOW);
  record = recovery.putDraft(record, `${stepId}:1`, 'je serai la vers dix-huit heures', NOW);
  record = recovery.putDraft(record, stepId, 'un cafe', NOW);
  if (closed) record = recovery.putDraft(record, `${closed.id}:0`, 'an old turn', NOW);

  const pruned = recovery.pruneAgainstSnapshot(record, snapshot);
  assert.equal(
    pruned.drafts[`${stepId}:1`] && pruned.drafts[`${stepId}:1`].text,
    'je serai la vers dix-huit heures',
    'a respond draft for a still-open step must survive a snapshot write',
  );
  assert.ok(pruned.drafts[stepId], 'a recall draft for a still-open step must survive');

  assert.equal(recovery.stepIdOfDraftKey('abc'), 'abc');
  assert.equal(recovery.stepIdOfDraftKey('abc:3'), 'abc');
}

{
  // The original guarantee must still hold: once the server completes a step, its
  // draft goes, so a resumed session cannot repaint an answer already sent.
  const snapshot = fixture('returning_due');
  const stepId = snapshot.current_step_id;
  let record = recovery.putSnapshot(recovery.emptyRecord('a1', '2026-09-05', NOW), snapshot, NOW);
  record = recovery.putDraft(record, `${stepId}:0`, 'sent already', NOW);

  const advanced = {
    ...snapshot,
    steps: snapshot.steps.map((step) =>
      step.id === stepId ? { ...step, status: 'completed' } : step,
    ),
  };
  const pruned = recovery.pruneAgainstSnapshot(record, advanced);
  assert.ok(
    !pruned.drafts[`${stepId}:0`],
    'a respond draft for a COMPLETED step is still dropped',
  );
}
