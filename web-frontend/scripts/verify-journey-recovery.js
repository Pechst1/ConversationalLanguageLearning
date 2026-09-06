/**
 * Live interruption-recovery verification for the daily journey (WP-10).
 *
 * Drives a real authenticated backend with the real recovery module — no mocks,
 * no service-layer shortcuts, and no fabricated responses. `lib/journey-recovery.ts`
 * makes every decision here; this file only executes what it decides and checks
 * the server's own answers.
 *
 * The interruptions it reproduces:
 *
 *   1. the app is killed after the server accepts an attempt but before the
 *      response is received — the cold start must land on the correct step and
 *      must not take credit twice;
 *   2. an expired token: 401, refresh, retry — one attempt, not two;
 *   3. two devices, one journey: the device that was offline must not walk a
 *      completion back;
 *   4. a second account must see none of the first account's content;
 *   5. airplane mode: the cached scene and the unsent draft are still there.
 *
 * Usage (a throwaway database only — never a learner's):
 *   node scripts/verify-journey-recovery.js [http://127.0.0.1:8010]
 */

const path = require('node:path');
const Module = require('node:module');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const recovery = require(path.join(WEB_ROOT, 'lib/journey-recovery.ts'));
const resilience = require(path.join(WEB_ROOT, 'lib/pilot-resilience.ts'));

const ROOT = (process.argv[2] || 'http://127.0.0.1:8010').replace(/\/+$/, '');
const BASE = `${ROOT}/api/v1`;
const PASSWORD = 'Wp10Passw0rd!';

let checks = 0;
let failures = 0;

function check(label, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  ok   ${label}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${label}${detail === undefined ? '' : ` — ${JSON.stringify(detail)}`}`);
  }
}

async function call(method, endpoint, token, body) {
  const response = await fetch(BASE + endpoint, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  return { status: response.status, body: text ? JSON.parse(text) : null };
}

async function account(tag) {
  const email = `wp10-${tag}-${Math.random().toString(36).slice(2, 10)}@example.com`;
  const registered = await call('POST', '/auth/register', null, {
    email,
    password: PASSWORD,
    full_name: `WP10 ${tag}`,
    native_language: 'en',
    cefr_estimate: 'A2',
  });
  if (registered.status !== 201) throw new Error(`register failed: ${registered.status}`);
  const logged = await call('POST', '/auth/login', null, { email, password: PASSWORD });
  if (logged.status !== 200) throw new Error(`login failed: ${logged.status}`);
  return { email, token: logged.body.access_token };
}

/** A device: a real recovery store over an in-memory localStorage stand-in. */
function device(scope, localDate) {
  const map = new Map();
  const storage = {
    get length() {
      return map.size;
    },
    key: (index) => Array.from(map.keys())[index] ?? null,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
  return {
    storage,
    map,
    /** A cold start: a brand-new store reading the same persisted bytes. */
    restart: () => recovery.createJourneyRecoveryStore({ scope, localDate, storage }),
  };
}

function key() {
  return globalThis.crypto.randomUUID();
}

function stepOf(journey) {
  return journey.steps.find((step) => step.id === journey.current_step_id) || null;
}

/** Walk to the next `respond` step, advancing through scenes and recalls. */
async function walkToRespond(token, journeyId, journey) {
  let current = journey;
  for (let guard = 0; guard < 8; guard += 1) {
    const step = stepOf(current);
    if (!step) return current;
    if (step.kind === 'respond') return current;
    const advanced = await call('POST', `/daily-journeys/${journeyId}/advance`, token, {
      mutation_id: key(),
      expected_revision: current.revision,
      current_step_id: step.id,
    });
    if (advanced.status >= 400) return current;
    current = advanced.body;
  }
  return current;
}

async function main() {
  console.log(`WP-10 live interruption recovery against ${BASE}\n`);

  const learner = await account('learner');
  const other = await account('other');
  const scopeA = resilience.accountScopeKey(learner.email);
  const scopeB = resilience.accountScopeKey(other.email);
  console.log(`learner ${learner.email}`);
  console.log(`other   ${other.email}\n`);

  const today = await call('GET', '/daily-journeys/today?timezone=Europe/Berlin', learner.token);
  if (today.status !== 200 || !today.body.enabled) {
    throw new Error(`daily journeys are not enabled on this server: ${today.status}`);
  }
  const localDate = today.body.local_date;

  // =======================================================================
  console.log('\n1. App killed after an accepted attempt, before the response');
  // =======================================================================

  const phone = device(scopeA, localDate);
  let store = phone.restart();

  const createIntent = 'create';
  const createKey = key();
  store.update((record) => recovery.putPending(record, {
    intent: createIntent,
    mutationId: createKey,
    kind: 'create',
    journeyId: null,
    stepId: null,
    expectedRevision: null,
    body: { timezone: 'Europe/Berlin', budget_seconds: 300, preferred_input_mode: 'text' },
    startedAt: new Date().toISOString(),
    dispatched: true,
  }));
  const created = await call('POST', '/daily-journeys', learner.token, {
    mutation_id: createKey,
    timezone: 'Europe/Berlin',
    budget_seconds: 300,
    preferred_input_mode: 'text',
  });
  check('journey created', created.status === 201 || created.status === 200, created.status);
  const journeyId = created.body.id;
  store.update((record) => recovery.putPending(recovery.putSnapshot(record, created.body), null));

  const atRespond = await walkToRespond(learner.token, journeyId, created.body);
  const respondStep = stepOf(atRespond);
  check('reached a respond step', Boolean(respondStep) && respondStep.kind === 'respond', respondStep && respondStep.kind);
  store.update((record) => recovery.putSnapshot(record, atRespond));

  // The learner types. The draft is persisted before anything is sent.
  const answer = "Bonjour Margaux, je voudrais un cafe en terrasse s'il vous plait.";
  store.update((record) => recovery.putDraft(record, respondStep.id, answer));

  const attemptBody = { mode: 'text', text: answer };
  const attemptIntent = `attempt:${journeyId}:${respondStep.id}:${atRespond.revision}:${JSON.stringify(attemptBody)}`;
  const attemptKey = key();
  store.update((record) => recovery.putPending(record, {
    intent: attemptIntent,
    mutationId: attemptKey,
    kind: 'attempt',
    journeyId,
    stepId: respondStep.id,
    expectedRevision: atRespond.revision,
    body: attemptBody,
    startedAt: new Date().toISOString(),
    dispatched: false,
  }));
  store.update((record) => recovery.putPending(record, { ...record.pending, dispatched: true }));

  // The request goes out and IS accepted. The client never sees the answer.
  const accepted = await call(
    'POST',
    `/daily-journeys/${journeyId}/steps/${respondStep.id}/attempts`,
    learner.token,
    { mutation_id: attemptKey, expected_revision: atRespond.revision, input: attemptBody },
  );
  check('the server accepted the attempt', accepted.status === 200, accepted.status);
  const hiddenResult = accepted.body; // the client is killed before reading this

  // ---- cold start --------------------------------------------------------
  store = phone.restart();
  const restored = store.read();
  check('the cache survived the kill', Boolean(restored && restored.pending), restored && restored.pending);
  check(
    'the draft survived the kill',
    recovery.readDraft(restored, respondStep.id) === answer,
    recovery.readDraft(restored, respondStep.id),
  );

  const serverView = await call('GET', `/daily-journeys/${journeyId}`, learner.token);
  check('the server is reachable again', serverView.status === 200, serverView.status);

  const resume = recovery.reconcileResume({
    record: restored,
    server: serverView.body,
    scope: scopeA,
    localDate,
  });
  check('the resume takes the server view', resume.source === 'server', resume.reason);
  check(
    'and lands on the step the server says is current',
    resume.stepId === serverView.body.current_step_id,
    { decided: resume.stepId, server: serverView.body.current_step_id },
  );

  const plan = recovery.planPendingReplay({
    pending: restored.pending,
    server: serverView.body,
    online: true,
  });
  check('the pending attempt is replayed', plan.action === 'replay', plan);
  check('under its ORIGINAL key, not a fresh one', plan.mutationId === attemptKey, plan.mutationId);

  const revisionBeforeReplay = serverView.body.revision;
  const replayed = await call(
    'POST',
    `/daily-journeys/${journeyId}/steps/${respondStep.id}/attempts`,
    learner.token,
    { mutation_id: plan.mutationId, expected_revision: atRespond.revision, input: attemptBody },
  );
  check('the replay is accepted', replayed.status === 200, replayed.status);
  check(
    'and returns the SAME evidence record',
    replayed.body.evidence_ref === hiddenResult.evidence_ref,
    { replay: replayed.body.evidence_ref, original: hiddenResult.evidence_ref },
  );
  check(
    'the revision did not move: no second application',
    replayed.body.journey.revision === revisionBeforeReplay,
    { before: revisionBeforeReplay, after: replayed.body.journey.revision },
  );
  check(
    'the outcome is the stored one, not a re-grade',
    replayed.body.task_outcome === hiddenResult.task_outcome,
    { replay: replayed.body.task_outcome, original: hiddenResult.task_outcome },
  );

  // Three more replays: still no drift.
  let drifted = false;
  for (let index = 0; index < 3; index += 1) {
    const again = await call(
      'POST',
      `/daily-journeys/${journeyId}/steps/${respondStep.id}/attempts`,
      learner.token,
      { mutation_id: plan.mutationId, expected_revision: atRespond.revision, input: attemptBody },
    );
    if (again.status !== 200 || again.body.journey.revision !== revisionBeforeReplay) drifted = true;
  }
  check('four replays in total still leave one application', !drifted);

  // The same key with a DIFFERENT answer is refused rather than silently applied.
  const swapped = await call(
    'POST',
    `/daily-journeys/${journeyId}/steps/${respondStep.id}/attempts`,
    learner.token,
    {
      mutation_id: plan.mutationId,
      expected_revision: atRespond.revision,
      input: { mode: 'text', text: 'Un the, merci.' },
    },
  );
  check(
    'the same key with a different answer is refused',
    swapped.status === 409 && swapped.body.detail.code === 'idempotency_conflict',
    { status: swapped.status, detail: swapped.body && swapped.body.detail },
  );

  store.update((record) => recovery.putPending(recovery.putSnapshot(record, replayed.body.journey), null));
  store.update((record) => recovery.putDraft(record, respondStep.id, ''));

  // =======================================================================
  console.log('\n2. Expired auth: 401, refresh, retry — one attempt, not two');
  // =======================================================================

  let live = replayed.body.journey;
  live = await walkToRespond(learner.token, journeyId, live);
  const secondStep = stepOf(live);
  if (!secondStep || secondStep.kind !== 'respond') {
    console.log('  skip — the plan has no second respond turn on this server');
  } else {
    const body2 = { mode: 'text', text: 'Oui, avec un croissant, merci beaucoup.' };
    const key2 = key();
    const revisionBefore = live.revision;

    const unauthorized = await call(
      'POST',
      `/daily-journeys/${journeyId}/steps/${secondStep.id}/attempts`,
      'not-a-valid-token',
      { mutation_id: key2, expected_revision: revisionBefore, input: body2 },
    );
    check('an expired token is rejected', unauthorized.status === 401, unauthorized.status);

    const afterRejection = await call('GET', `/daily-journeys/${journeyId}`, learner.token);
    check(
      'and changed nothing',
      afterRejection.body.revision === revisionBefore,
      { before: revisionBefore, after: afterRejection.body.revision },
    );

    // The interceptor refreshes and re-issues THE SAME request, same key.
    const retried = await call(
      'POST',
      `/daily-journeys/${journeyId}/steps/${secondStep.id}/attempts`,
      learner.token,
      { mutation_id: key2, expected_revision: revisionBefore, input: body2 },
    );
    check('the refreshed retry succeeds', retried.status === 200, retried.status);
    const appliedRevision = retried.body.journey.revision;

    const thirdSend = await call(
      'POST',
      `/daily-journeys/${journeyId}/steps/${secondStep.id}/attempts`,
      learner.token,
      { mutation_id: key2, expected_revision: revisionBefore, input: body2 },
    );
    check(
      'a refresh cannot produce a second attempt',
      thirdSend.status === 200 &&
        thirdSend.body.evidence_ref === retried.body.evidence_ref &&
        thirdSend.body.journey.revision === appliedRevision,
      { first: retried.body.evidence_ref, second: thirdSend.body.evidence_ref },
    );
    live = retried.body.journey;
  }

  // =======================================================================
  console.log('\n3. Airplane mode: an owned cached scene and a kept draft');
  // =======================================================================

  const offlineStore = phone.restart();
  offlineStore.update((record) => recovery.putSnapshot(record, live));
  const offlineDraft = 'un chocolat chaud, please';
  const openStep = stepOf(live);
  if (openStep) offlineStore.update((record) => recovery.putDraft(record, openStep.id, offlineDraft));

  const coldOffline = recovery.reconcileResume({
    record: phone.restart().read(),
    server: null, // the request never leaves the device
    scope: scopeA,
    localDate,
  });
  check('an airplane-mode cold start shows a cached scene', coldOffline.source === 'cache', coldOffline.reason);
  check('owned by this account', coldOffline.journeyId === journeyId, coldOffline.journeyId);
  if (openStep) check('with the draft intact', coldOffline.draft === offlineDraft, coldOffline.draft);
  const offlineView = recovery.connectionView({
    online: false,
    source: coldOffline.source,
    pending: null,
    unsentDraft: Boolean(openStep),
    stale: coldOffline.stale,
    lastSyncedAt: null,
  });
  check('and says it is offline rather than inventing a result', offlineView.state === 'offline_cached', offlineView.state);

  // =======================================================================
  console.log('\n4. Two devices, one journey: no walking a completion back');
  // =======================================================================

  const tablet = device(scopeA, localDate);
  const tabletStore = tablet.restart();
  tabletStore.update((record) => recovery.putSnapshot(record, live));
  const staleRevision = live.revision;
  if (openStep) tabletStore.update((record) => recovery.putDraft(record, openStep.id, 'typed on the tablet'));

  // The phone drives the journey to the end and finishes it.
  let driving = live;
  for (let guard = 0; guard < 8 && driving.current_step_id; guard += 1) {
    const step = stepOf(driving);
    if (step.kind === 'respond' && step.status === 'active') {
      const sent = await call(
        'POST',
        `/daily-journeys/${journeyId}/steps/${step.id}/attempts`,
        learner.token,
        {
          mutation_id: key(),
          expected_revision: driving.revision,
          input: { mode: 'text', text: 'Merci beaucoup, bonne soiree.' },
        },
      );
      if (sent.status >= 400) break;
      driving = sent.body.journey;
      continue;
    }
    const advanced = await call('POST', `/daily-journeys/${journeyId}/advance`, learner.token, {
      mutation_id: key(),
      expected_revision: driving.revision,
      current_step_id: step.id,
    });
    if (advanced.status >= 400) break;
    driving = advanced.body;
  }
  const finished = await call('POST', `/daily-journeys/${journeyId}/finish`, learner.token, {
    mutation_id: key(),
    expected_revision: driving.revision,
    finish_kind: 'complete',
  });
  check('the phone finished the journey', finished.status === 200 && finished.body.status === 'completed', {
    status: finished.status,
    journeyStatus: finished.body && finished.body.status,
  });

  // The tablet, still holding the old revision, tries to submit.
  const tabletAttempt = openStep
    ? await call(
        'POST',
        `/daily-journeys/${journeyId}/steps/${openStep.id}/attempts`,
        learner.token,
        {
          mutation_id: key(),
          expected_revision: staleRevision,
          input: { mode: 'text', text: 'typed on the tablet' },
        },
      )
    : null;
  if (tabletAttempt) {
    check(
      'a stale device is refused, not merged',
      tabletAttempt.status === 409,
      { status: tabletAttempt.status, detail: tabletAttempt.body && tabletAttempt.body.detail },
    );
  }

  // The tablet reconnects and reconciles.
  const serverFinal = await call('GET', `/daily-journeys/${journeyId}`, learner.token);
  const tabletAfter = tabletStore.update((record) => recovery.putSnapshot(record, serverFinal.body));
  check('the tablet adopts the completion', tabletAfter.status === 'completed', tabletAfter.status);
  check('and drops the draft it can no longer send', Object.keys(tabletAfter.drafts).length === 0, tabletAfter.drafts);

  // The tablet's own stale snapshot arrives late — it must not win.
  const afterLate = tabletStore.update((record) => recovery.putSnapshot(record, live));
  check(
    'a late stale snapshot cannot overwrite the completion',
    afterLate.status === 'completed' && afterLate.revision === serverFinal.body.revision,
    { status: afterLate.status, revision: afterLate.revision, server: serverFinal.body.revision },
  );

  // =======================================================================
  console.log('\n5. Another account sees none of this');
  // =======================================================================

  const foreignGet = await call('GET', `/daily-journeys/${journeyId}`, other.token);
  check('the other account cannot read the journey', foreignGet.status === 404, foreignGet.status);
  const foreignToday = await call('GET', '/daily-journeys/today?timezone=Europe/Berlin', other.token);
  check('and has no journey of its own yet', foreignToday.body.journey === null, foreignToday.body.journey);

  // Same device, second learner: the sweep runs before anything can paint.
  const switched = resilience.syncAccountScope(scopeA, phone.storage);
  check('the first scope is recorded', switched.switched === false, switched);
  const switchedB = resilience.syncAccountScope(scopeB, phone.storage);
  check('a scope change is detected', switchedB.switched === true, switchedB);
  const foreignStore = recovery.createJourneyRecoveryStore({
    scope: scopeB,
    localDate,
    storage: phone.storage,
  });
  check('and the second account starts from nothing', foreignStore.read() === null, foreignStore.read());
  const leftovers = resilience
    .pilotKeys(phone.storage)
    .filter((entry) => entry.indexOf(recovery.JOURNEY_RECOVERY_PREFIX) === 0);
  check('no journey cache from the previous learner remains', leftovers.length === 0, leftovers);

  console.log(`\n${checks - failures}/${checks} checks passed`);
  if (failures > 0) process.exitCode = 1;
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
