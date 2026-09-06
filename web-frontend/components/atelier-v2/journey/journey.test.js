/**
 * Behavioural coverage for the Atelier V2 daily-journey frontend (WP-07).
 *
 * Same harness as `lib/atelier-next.test.js`: a plain node script with
 * `node:assert/strict` and sucrase, so it needs no new test framework.
 *
 * It covers the four things the acceptance criteria actually turn on:
 *   1. every frozen public fixture maps to exactly one renderable state;
 *   2. request identity — a replay reuses the key, a double tap sends once;
 *   3. contract failures never become a wrong-answer verdict;
 *   4. the step renderers show the right thing for each state.
 *
 * Run: `node components/atelier-v2/journey/journey.test.js`
 */

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

// --- `@/…` path alias, plus a stub for the heavy axios transport -----------
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

/** Records every call so the tests can assert on request identity. */
const apiCalls = [];
let apiHandler = () => {
  throw new Error('no api handler installed');
};
const apiStub = new Proxy(
  {},
  {
    get(_target, method) {
      if (method === 'then') return undefined;
      return (...args) => {
        apiCalls.push({ method, args });
        return apiHandler(String(method), args);
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

/**
 * The signed-in learner. `useAppSession` deliberately throws outside its
 * provider, and the recovery layer scopes its cache to the account, so the
 * identity is stubbed here — before anything that reaches it is loaded.
 */
const TEST_LEARNER_ID = 'learner-1';
const authPath = Module._resolveFilename('@/lib/app-auth', module, false);
require.cache[authPath] = {
  id: authPath,
  filename: authPath,
  loaded: true,
  exports: {
    __esModule: true,
    useAppSession: () => ({
      data: { user: { id: TEST_LEARNER_ID } },
      status: 'authenticated',
      isNative: false,
    }),
  },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// styled-jsx's `jsx` / `global` props are compiled away by next/babel in the
// real build; sucrase leaves them, and React warns. Silence only that.
const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

/** React escapes text nodes, so assertions must compare against escaped copy. */
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}
const htmlHas = (html, text) => html.includes(escapeHtml(text));

const state = require('./journey-state.ts');
const requests = require('./journey-requests.ts');
const { journeyCopy } = require('./journey-copy.ts');
const steps = require('./JourneySteps.tsx');
const { JourneySession } = require('./JourneySession.tsx');
const { JourneyTodayCard } = require('./JourneyTodayCard.tsx');
const { dailyJourneyService } = require('@/services/daily-journey');

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8'));
const EN = journeyCopy('en');

// ===========================================================================
// 1. Every frozen public fixture maps to exactly one renderable state
// ===========================================================================

const allFixtures = fs
  .readdirSync(FIXTURES)
  .filter((name) => name.endsWith('.json'))
  .map((name) => name.replace(/\.json$/, ''));
assert.equal(allFixtures.length, 26, 'the frozen bundle has 26 public fixtures');

const KNOWN_PHASES = new Set([
  'loading',
  'load_failed',
  'disabled',
  'offer',
  'preparing',
  'unavailable',
  'session',
  'paused',
  'finished',
]);

let envelopeFixtures = 0;
let snapshotFixtures = 0;
for (const name of allFixtures) {
  const body = fixture(name).response;
  if (body && typeof body === 'object' && 'enabled' in body) {
    envelopeFixtures += 1;
    const phase = state.phaseFromEnvelope(body);
    assert.ok(KNOWN_PHASES.has(phase.kind), `${name}: unknown phase ${phase.kind}`);
  } else if (body && typeof body === 'object' && 'status' in body && 'steps' in body) {
    snapshotFixtures += 1;
    const phase = state.phaseFromJourney(body);
    assert.ok(KNOWN_PHASES.has(phase.kind), `${name}: unknown phase ${phase.kind}`);
  }
}
assert.ok(envelopeFixtures >= 4 && snapshotFixtures >= 8, 'fixtures cover both payload shapes');

assert.equal(state.phaseFromEnvelope(fixture('first_day').response).kind, 'offer');
assert.equal(state.phaseFromEnvelope(fixture('flag_disabled').response).kind, 'disabled');
assert.equal(state.phaseFromEnvelope(fixture('active_legacy').response).kind, 'offer');
assert.equal(state.phaseFromEnvelope(fixture('midnight_resume').response).kind, 'session');
assert.equal(state.phaseFromJourney(fixture('returning_due').response).kind, 'session');
assert.equal(state.phaseFromJourney(fixture('preparing').response).kind, 'preparing');
assert.equal(state.phaseFromJourney(fixture('generation_unavailable').response).kind, 'unavailable');
assert.equal(state.phaseFromJourney(fixture('completed').response).kind, 'finished');
assert.equal(state.phaseFromJourney(fixture('ended_early').response).kind, 'finished');

// A disabled envelope never yields a session, whatever it carries.
assert.equal(
  state.phaseFromEnvelope({ ...fixture('midnight_resume').response, enabled: false }).kind,
  'disabled',
);

// The preparing/unavailable retry hints come from the server, not a default.
assert.equal(state.phaseFromJourney(fixture('preparing').response).retryAfterSeconds, 3);
assert.equal(state.phaseFromJourney(fixture('generation_unavailable').response).retryAfterSeconds, 30);
assert.equal(state.phaseFromJourney(fixture('generation_unavailable').response).retryAllowed, true);

// --- Progress comes from the plan, never from a demo value ------------------
const returning = fixture('returning_due').response;
const progress = state.journeyProgress(returning);
assert.deepEqual(
  { done: progress.done, total: progress.total, percent: progress.percent },
  { done: 2, total: 4, percent: 50 },
);
// 120 (active respond) + 59 (pending resolution) — the steps' own estimates.
assert.equal(progress.remainingSeconds, 179);
assert.equal(progress.plannedSeconds, returning.estimated_active_seconds);
// An unplanned journey reports no progress rather than a fabricated one.
assert.deepEqual(state.journeyProgress(fixture('preparing').response), {
  done: 0,
  total: 0,
  percent: 0,
  remainingSeconds: null,
  plannedSeconds: null,
});
assert.equal(state.journeyProgress(null).percent, 0);
assert.equal(state.formatDuration(null), null);
assert.equal(state.formatDuration(0), null);
assert.equal(state.formatDuration(264), '4 min');
assert.equal(state.formatDuration(40), '40 s');

// --- Voice/text availability is the server's word ---------------------------
const voiceless = fixture('voice_unavailable').response;
const voicelessRespond = voiceless.steps.find((step) => step.kind === 'respond');
assert.deepEqual(voicelessRespond.prompt.input_modes, ['text']);
assert.equal(state.voiceOffered(voicelessRespond.prompt), false);
assert.equal(state.textOffered(voicelessRespond.prompt), true);
const withVoice = returning.steps.find((step) => step.kind === 'respond');
assert.equal(state.voiceOffered(withVoice.prompt), true);
assert.equal(state.textOffered(withVoice.prompt), true);
// A malformed payload still leaves the learner a way to answer.
assert.equal(state.textOffered({ input_modes: [] }), true);

// ===========================================================================
// 2. Verdicts — a failure is never a wrong answer
// ===========================================================================

assert.equal(state.attemptVerdict('met', 'none'), 'correct');
assert.equal(state.attemptVerdict('met', 'hint'), 'supported');
assert.equal(state.attemptVerdict('partially_met', 'none'), 'supported');
assert.equal(state.attemptVerdict('partially_met', 'solution'), 'supported');
assert.equal(state.attemptVerdict('not_yet', 'none'), 'wrong');
assert.equal(state.attemptVerdict('unscored', 'none'), 'unscored');

const supported = fixture('wrong_then_supported').response;
const supportedFeedback = state.feedbackFromAttempt(supported);
assert.equal(supportedFeedback.kind, 'graded');
assert.equal(supportedFeedback.verdict, 'supported');
assert.ok(supportedFeedback.result.correction, 'the one foreground correction survives');

const clean = fixture('unassisted_success').response;
const cleanFeedback = state.feedbackFromAttempt(clean);
assert.equal(cleanFeedback.kind, 'graded');
assert.equal(cleanFeedback.verdict, 'correct');
assert.equal(cleanFeedback.result.correction, null);

// `pending` is a retryable "still grading", never a verdict.
const pending = { ...clean, pending: true, task_outcome: 'unscored', evidence_ref: '' };
const pendingFeedback = state.feedbackFromAttempt(pending);
assert.equal(pendingFeedback.kind, 'unscored');
assert.equal(pendingFeedback.result.task_outcome, 'unscored');

// Contract revision 2: an authored reply is labelled, a live one is not, and a
// payload without the field claims nothing at all.
assert.equal(state.replySourceOf(clean), 'model', 'the frozen fixture reports a live reply');
assert.equal(state.replySourceOf({ ...clean, reply_source: 'authored' }), 'authored');
assert.equal(state.replySourceOf({ ...clean, reply_source: 'none' }), 'none');
const noProvenance = { ...clean };
delete noProvenance.reply_source;
assert.equal(state.replySourceOf(noProvenance), 'unknown', 'an older payload claims nothing');
assert.equal(state.replySourceOf(null), 'unknown');

// ===========================================================================
// 3. Contract signals hidden inside successful HTTP statuses
// ===========================================================================

const duplicateSubmit = fixture('duplicate_submit');
assert.equal(duplicateSubmit.http_status, 202);
assert.equal(state.detailOfPayload(duplicateSubmit.response).code, 'processing');
assert.equal(state.detailOfPayload(duplicateSubmit.response).retry_after_seconds, 2);
assert.equal(state.payloadIsDetail(duplicateSubmit.response), true);
// A real result is not mistaken for a signal.
assert.equal(state.detailOfPayload(clean), null);
// FastAPI's plain 422 carries a LIST in `detail`; `detail.code` does not exist.
assert.equal(state.detailOfPayload({ detail: [{ loc: ['body'], msg: 'field required' }] }), null);
assert.equal(state.detailOfPayload(null), null);

assert.deepEqual(state.RECONCILE_CODES.slice().sort(), [
  'idempotency_conflict',
  'journey_not_active',
  'journey_version_conflict',
  'step_not_active',
]);
assert.equal(state.isReconcileCode('journey_version_conflict'), true);
assert.equal(state.isReconcileCode('empty_answer'), false);
assert.equal(state.isReconcileCode(null), false);

// --- planFailure routes every contract code to exactly one state ------------
const asError = (status, detail) => ({ response: { status, data: { detail } } });

assert.deepEqual(requests.planFailure(fixture('stale_revision').response.detail, null), {
  kind: 'reconcile',
  code: 'journey_version_conflict',
  message: 'This journey moved on. Refresh to continue.',
});
assert.deepEqual(requests.planFailure(fixture('step_not_active').response.detail, null), {
  kind: 'reconcile',
  code: 'step_not_active',
  message: 'That step is not the current one.',
});
assert.deepEqual(requests.planFailure(fixture('empty_answer_rejected').response.detail, null), {
  kind: 'empty',
  message: 'Write or say something first.',
});
assert.deepEqual(
  requests.planFailure(null, asError(403, { code: 'journey_disabled', message: 'off' })),
  { kind: 'disabled' },
);
assert.deepEqual(
  requests.planFailure(null, asError(409, { code: 'idempotency_conflict', message: 'reused' })),
  { kind: 'reconcile', code: 'idempotency_conflict', message: 'reused' },
);
assert.deepEqual(
  requests.planFailure(null, asError(503, { code: 'generation_unavailable', message: 'x' })),
  { kind: 'refetch' },
);
// A network error and FastAPI's list-shaped 422 both land in `error`, and both
// are retryable — never a wrong answer.
assert.deepEqual(requests.planFailure(null, new Error('Network Error')), {
  kind: 'error',
  message: 'transport_error',
  retryable: true,
});
assert.deepEqual(
  requests.planFailure(null, { response: { status: 422, data: { detail: [{ msg: 'bad' }] } } }),
  { kind: 'error', message: 'transport_error', retryable: true },
);
// An exhausted `processing` replay is retryable transport, not a grade.
assert.deepEqual(
  requests.planFailure({ code: 'processing', message: 'still grading', retry_after_seconds: 2 }, null),
  { kind: 'error', message: 'still grading', retryable: true },
);

// ===========================================================================
// 4. Request identity — stable keys, bounded replay, one request per tap
// ===========================================================================

let minted = 0;
const keyring = requests.createMutationKeyring(() => `mid-${++minted}`);
const attemptIntent = 'attempt:j1:s1:3:{"mode":"text","text":"un café"}';
assert.equal(keyring.idFor(attemptIntent), 'mid-1');
assert.equal(keyring.idFor(attemptIntent), 'mid-1', 'a replay reuses the same key');
assert.equal(keyring.idFor('attempt:j1:s1:3:{"mode":"text","text":"autre"}'), 'mid-2');
assert.equal(keyring.size(), 2);
keyring.release(attemptIntent);
assert.equal(keyring.idFor(attemptIntent), 'mid-3', 'a released intent mints a fresh key');

const noSleep = () => Promise.resolve();

(async () => {
  // --- 202 processing: the identical request is replayed under the same key --
  const seen = [];
  let call = 0;
  const replayed = await requests.runMutation({
    mutationId: 'mid-stable',
    sleep: noSleep,
    onRetry: (attempt, afterSeconds) => seen.push([attempt, afterSeconds]),
    invoke: async (id) => {
      call += 1;
      if (call < 3) {
        // Exactly what the server sends: a 2xx whose body is an error envelope.
        return { detail: { code: 'processing', message: 'still', retry_after_seconds: 2 }, sentWith: id };
      }
      return { ok: 'graded', sentWith: id };
    },
  });
  assert.equal(call, 3);
  assert.deepEqual(seen, [[1, 2], [2, 2]], 'each replay is announced with the server\'s delay');
  assert.equal(replayed.ok, true);
  assert.equal(replayed.value.sentWith, 'mid-stable', 'never a fresh key on retry');

  // The same policy applies when `processing` arrives as a rejection.
  let rejectCalls = 0;
  const viaRejection = await requests.runMutation({
    mutationId: 'mid-reject',
    sleep: noSleep,
    invoke: async () => {
      rejectCalls += 1;
      if (rejectCalls < 2) {
        throw asError(202, { code: 'processing', message: 'still', retry_after_seconds: 1 });
      }
      return { ok: true };
    },
  });
  assert.equal(rejectCalls, 2);
  assert.equal(viaRejection.ok, true);

  // --- The replay is bounded, and exhaustion is honest ----------------------
  let forever = 0;
  const exhausted = await requests.runMutation({
    mutationId: 'mid-forever',
    sleep: noSleep,
    maxRetries: 2,
    invoke: async () => {
      forever += 1;
      return { detail: { code: 'processing', message: 'still', retry_after_seconds: 1 } };
    },
  });
  assert.equal(forever, 3, 'first attempt plus two bounded replays');
  assert.equal(exhausted.ok, false);
  assert.equal(exhausted.detail.code, 'processing');
  assert.equal(requests.planFailure(exhausted.detail, exhausted.error).kind, 'error');

  // --- A non-processing detail is surfaced, not retried ---------------------
  let conflictCalls = 0;
  const conflicted = await requests.runMutation({
    mutationId: 'mid-conflict',
    sleep: noSleep,
    invoke: async () => {
      conflictCalls += 1;
      throw asError(409, fixture('stale_revision').response.detail);
    },
  });
  assert.equal(conflictCalls, 1, 'a conflict is never replayed blindly');
  assert.equal(conflicted.ok, false);
  assert.equal(requests.planFailure(conflicted.detail, conflicted.error).kind, 'reconcile');

  // --- Double tap: one request, both callers get the same answer ------------
  const gate = requests.createRequestGate();
  let gated = 0;
  let release;
  const blocked = new Promise((resolve) => {
    release = resolve;
  });
  const run = () =>
    gate.run('attempt:j1:s1', async () => {
      gated += 1;
      await blocked;
      return 'once';
    });
  const first = run();
  const second = run();
  assert.equal(gate.inFlight('attempt:j1:s1'), true);
  release();
  assert.deepEqual(await Promise.all([first, second]), ['once', 'once']);
  assert.equal(gated, 1, 'a double tap reuses the in-flight request');
  assert.equal(gate.inFlight('attempt:j1:s1'), false);
  // Once settled, a genuinely new tap runs again.
  await gate.run('attempt:j1:s1', async () => {
    gated += 1;
    return 'again';
  });
  assert.equal(gated, 2);

  // A failing request must not wedge the gate.
  await gate
    .run('attempt:j1:s2', async () => {
      throw new Error('boom');
    })
    .catch(() => undefined);
  assert.equal(gate.inFlight('attempt:j1:s2'), false);

  // =========================================================================
  // 5. The typed facade issues the frozen bodies
  // =========================================================================

  apiCalls.length = 0;
  apiHandler = (method) => {
    if (method === 'submitDailyJourneyAttempt') return Promise.resolve(clean);
    if (method === 'getDailyJourneyToday') return Promise.resolve(fixture('first_day').response);
    if (method === 'createDailyJourney') return Promise.resolve({ data: fixture('preparing').response, status: 202 });
    if (method === 'advanceDailyJourney') return Promise.resolve(returning);
    if (method === 'finishDailyJourney') return Promise.resolve(fixture('completed').response);
    return Promise.resolve({});
  };

  await dailyJourneyService.attempt('j1', 's1', {
    expectedRevision: 4,
    input: { mode: 'voice', text: 'Je voudrais un café.' },
    mutationId: 'mid-voice',
  });
  const attemptCall = apiCalls.find((entry) => entry.method === 'submitDailyJourneyAttempt');
  assert.deepEqual(attemptCall.args, [
    'j1',
    's1',
    {
      mutation_id: 'mid-voice',
      expected_revision: 4,
      // Contract revision 1: no `transcript_ref` — the endpoint is stateless.
      input: { mode: 'voice', text: 'Je voudrais un café.' },
    },
  ]);
  assert.equal('transcript_ref' in attemptCall.args[2].input, false);

  const created = await dailyJourneyService.create({ mutationId: 'mid-create', timezone: 'Europe/Paris' });
  assert.equal(created.status, 202);
  assert.deepEqual(apiCalls.find((e) => e.method === 'createDailyJourney').args[0], {
    mutation_id: 'mid-create',
    timezone: 'Europe/Paris',
    budget_seconds: 300,
    preferred_input_mode: 'text',
  });

  await dailyJourneyService.advance('j1', {
    expectedRevision: 5,
    currentStepId: 's-completed',
    mutationId: 'mid-advance',
  });
  // The acknowledgement model: `advance` names the step the learner just
  // finished, which is still `current_step_id` after an accepted attempt.
  assert.deepEqual(apiCalls.find((e) => e.method === 'advanceDailyJourney').args[1], {
    mutation_id: 'mid-advance',
    expected_revision: 5,
    current_step_id: 's-completed',
  });

  await dailyJourneyService.finish('j1', {
    expectedRevision: 8,
    finishKind: 'early',
    mutationId: 'mid-finish',
  });
  assert.deepEqual(apiCalls.find((e) => e.method === 'finishDailyJourney').args[1], {
    mutation_id: 'mid-finish',
    expected_revision: 8,
    finish_kind: 'early',
  });

  // =========================================================================
  // 6. The renderers show the right thing for each state
  // =========================================================================

  const baseStepProps = {
    copy: EN,
    busy: false,
    feedback: { kind: 'idle' },
    help: null,
    onHelp: () => {},
    onSubmit: () => {},
    onContinue: () => {},
  };

  const sceneStep = returning.steps.find((step) => step.kind === 'scene');
  const sceneHtml = renderToStaticMarkup(
    React.createElement(steps.SceneStepView, { step: sceneStep, ...baseStepProps }),
  );
  assert.ok(htmlHas(sceneHtml, sceneStep.prompt.setup_fr), 'the French scene is shown');
  assert.ok(htmlHas(sceneHtml, sceneStep.prompt.setup_native), 'and its control-language gloss');
  assert.ok(htmlHas(sceneHtml, EN.scene_continue), 'with one clear main action');

  const recallStep = returning.steps.find((step) => step.kind === 'recall');
  const recallHtml = renderToStaticMarkup(
    React.createElement(steps.RecallStepView, { step: recallStep, ...baseStepProps }),
  );
  for (const option of recallStep.prompt.options) {
    assert.ok(htmlHas(recallHtml, option.text_fr), `option ${option.id} is rendered`);
  }
  assert.ok(recallHtml.includes('role="radiogroup"'), 'choices are a real radio group');
  assert.ok(recallHtml.includes('aria-checked="false"'), 'selection is exposed, not only coloured');
  assert.ok(!recallHtml.includes('correct_option_id'), 'no answer key reaches the client');
  // Help is available but on demand, never in front of the prompt.
  assert.ok(htmlHas(recallHtml, EN.help_hint) && htmlHas(recallHtml, EN.help_translation));
  assert.ok(
    recallHtml.indexOf(escapeHtml(recallStep.prompt.options[0].text_fr)) <
      recallHtml.indexOf(escapeHtml(EN.help_hint)),
  );

  // Locked after grading: still readable, and still announced as a choice.
  const lockedRecallHtml = renderToStaticMarkup(
    React.createElement(steps.RecallStepView, {
      step: recallStep,
      ...baseStepProps,
      feedback: cleanFeedback,
    }),
  );
  assert.ok(lockedRecallHtml.includes('disabled=""'), 'choices lock after grading');
  for (const option of recallStep.prompt.options) {
    assert.ok(htmlHas(lockedRecallHtml, option.text_fr), 'a disabled option stays legible');
  }
  assert.ok(lockedRecallHtml.includes('aria-checked'), 'and keeps its selection semantics');

  // Respond: voice only when the server offers it; text always.
  const respondHtml = renderToStaticMarkup(
    React.createElement(steps.RespondStepView, {
      step: withVoice,
      ...baseStepProps,
      voice: { kind: 'idle' },
      onStartRecording: () => {},
      onStopRecording: () => {},
      onResetVoice: () => {},
    }),
  );
  assert.ok(respondHtml.includes('<textarea'), 'text is always a full path');
  assert.ok(htmlHas(respondHtml, EN.use_voice), 'voice is offered for a voice-capable step');
  assert.ok(htmlHas(respondHtml, withVoice.prompt.character_line_fr));
  assert.ok(htmlHas(respondHtml, 'un café'), 'the elicited targets are shown');

  const respondTextOnlyHtml = renderToStaticMarkup(
    React.createElement(steps.RespondStepView, {
      step: voicelessRespond,
      ...baseStepProps,
      voice: { kind: 'idle' },
      onStartRecording: () => {},
      onStopRecording: () => {},
      onResetVoice: () => {},
    }),
  );
  assert.ok(respondTextOnlyHtml.includes('<textarea'), 'text stays a full path without voice');
  assert.ok(!htmlHas(respondTextOnlyHtml, EN.use_voice), 'no voice control when voice is unavailable');
  assert.ok(!htmlHas(respondTextOnlyHtml, EN.record));

  // A transcription failure keeps the turn open and is never a wrong answer.
  const voiceFailedHtml = renderToStaticMarkup(
    React.createElement(steps.RespondStepView, {
      step: withVoice,
      ...baseStepProps,
      voice: { kind: 'failed', message: 'voice_failed' },
      onStartRecording: () => {},
      onStopRecording: () => {},
      onResetVoice: () => {},
    }),
  );
  assert.ok(htmlHas(voiceFailedHtml, EN.voice_failed));
  assert.ok(voiceFailedHtml.includes('<textarea'), 'the learner still holds the turn');
  assert.ok(!htmlHas(voiceFailedHtml, EN.wrong));

  // A double tap can never send twice: the primary action is disabled while a
  // request is in flight, and the gate above reuses the first request anyway.
  const busyRespondHtml = renderToStaticMarkup(
    React.createElement(steps.RespondStepView, {
      step: withVoice,
      ...baseStepProps,
      busy: true,
      feedback: { kind: 'submitting' },
      voice: { kind: 'idle' },
      onStartRecording: () => {},
      onStopRecording: () => {},
      onResetVoice: () => {},
    }),
  );
  assert.ok(busyRespondHtml.includes('disabled=""'), 'the primary action locks while submitting');
  assert.ok(htmlHas(busyRespondHtml, EN.sending), 'and says so');

  // A graded turn stays closed until the learner continues.
  const gradedRespondHtml = renderToStaticMarkup(
    React.createElement(steps.RespondStepView, {
      step: withVoice,
      ...baseStepProps,
      feedback: cleanFeedback,
      voice: { kind: 'idle' },
      onStartRecording: () => {},
      onStopRecording: () => {},
      onResetVoice: () => {},
    }),
  );
  assert.ok(
    gradedRespondHtml.includes('<textarea') && gradedRespondHtml.includes('disabled=""'),
    'a graded turn keeps the answer visible but closed',
  );

  const resolutionStep = returning.steps.find((step) => step.kind === 'resolution');
  const resolutionHtml = renderToStaticMarkup(
    React.createElement(steps.ResolutionStepView, { step: resolutionStep, ...baseStepProps }),
  );
  assert.ok(htmlHas(resolutionHtml, resolutionStep.prompt.character_line_fr));
  assert.ok(htmlHas(resolutionHtml, resolutionStep.prompt.summary_native));

  // --- Every feedback state renders distinctly -----------------------------
  const renderFeedback = (feedback) =>
    renderToStaticMarkup(
      React.createElement(steps.JourneyFeedbackView, {
        feedback,
        copy: EN,
        onContinue: () => {},
        onRetry: () => {},
        onDismiss: () => {},
      }),
    );

  assert.equal(renderFeedback({ kind: 'idle' }), '');
  assert.equal(renderFeedback({ kind: 'submitting' }), '', 'in-flight is shown on the button, not as a verdict');

  const retryingHtml = renderFeedback({ kind: 'retrying', attempt: 1, afterSeconds: 2 });
  assert.ok(retryingHtml.includes('data-state="retrying"') && htmlHas(retryingHtml, EN.retrying));

  const emptyHtml = renderFeedback({ kind: 'empty', message: 'empty_answer' });
  assert.ok(emptyHtml.includes('data-state="empty"'));
  assert.ok(htmlHas(emptyHtml, EN.empty_answer));
  assert.ok(!htmlHas(emptyHtml, EN.wrong), 'an empty answer is not a wrong answer');
  assert.ok(emptyHtml.includes('role="alert"'));

  const unscoredHtml = renderFeedback(pendingFeedback);
  assert.ok(unscoredHtml.includes('data-state="unscored"'));
  assert.ok(htmlHas(unscoredHtml, EN.still_grading) && htmlHas(unscoredHtml, EN.try_grading_again));
  assert.ok(!htmlHas(unscoredHtml, EN.wrong), 'unscored never reads as wrong');

  const reconciledHtml = renderFeedback({
    kind: 'reconciled',
    code: 'journey_version_conflict',
    message: 'moved on',
  });
  assert.ok(reconciledHtml.includes('data-state="reconciled"') && htmlHas(reconciledHtml, EN.reconciled));
  assert.ok(!htmlHas(reconciledHtml, EN.wrong), 'a version conflict is not a wrong answer');

  const errorHtml = renderFeedback({ kind: 'error', message: 'boom', retryable: true });
  assert.ok(errorHtml.includes('data-state="error"') && htmlHas(errorHtml, EN.transport_error));
  assert.ok(htmlHas(errorHtml, EN.retry));
  assert.ok(!htmlHas(errorHtml, EN.wrong), 'a transport error is never a red wrong-answer card');

  const correctHtml = renderFeedback(cleanFeedback);
  assert.ok(correctHtml.includes('data-state="correct"') && htmlHas(correctHtml, EN.correct));
  assert.ok(htmlHas(correctHtml, clean.character_reply_fr));

  const supportedHtml = renderFeedback(supportedFeedback);
  assert.ok(supportedHtml.includes('data-state="supported"') && htmlHas(supportedHtml, EN.supported));
  assert.ok(htmlHas(supportedHtml, supported.correction.corrected_fr));
  assert.ok(htmlHas(supportedHtml, EN.correction));

  const wrongHtml = renderFeedback(
    state.feedbackFromAttempt({ ...clean, task_outcome: 'not_yet', character_reply_fr: null }),
  );
  assert.ok(wrongHtml.includes('data-state="wrong"') && htmlHas(wrongHtml, EN.wrong));

  // An authored reply is labelled as authored; an unknown source claims nothing.
  const authoredHtml = renderFeedback(
    state.feedbackFromAttempt({ ...clean, reply_source: 'authored' }),
  );
  assert.ok(htmlHas(authoredHtml, EN.reply_authored_note), 'an authored reply says so');
  assert.ok(!htmlHas(correctHtml, EN.reply_authored_note), 'and a live one does not');
  const unknownSourceHtml = renderFeedback(state.feedbackFromAttempt(noProvenance));
  assert.ok(
    !htmlHas(unknownSourceHtml, EN.reply_authored_note),
    'and an unlabelled payload claims nothing either way',
  );

  // =========================================================================
  // 7. Completion recap — the server's evidence, nothing invented
  // =========================================================================

  const completeRecap = state.recapView(fixture('completed').response.recap);
  assert.equal(completeRecap.partial, false);
  assert.equal(completeRecap.outcome, 'met');
  assert.equal(completeRecap.practiced.length, 2);
  assert.ok(completeRecap.headline, 'exactly one focus headline');
  assert.equal(completeRecap.headline.labelFr, 'en terrasse');

  const earlyRecap = state.recapView(fixture('ended_early').response.recap);
  assert.equal(earlyRecap.partial, true);
  assert.equal(earlyRecap.headline, null);
  assert.equal(earlyRecap.capabilities.length, 0);
  assert.equal(state.recapView(null), null);

  // WP-11 owns duration; until then `active_seconds` is null and must read as
  // "not measured" rather than a substituted number.
  const unmeasured = state.recapView({
    ...fixture('completed').response.recap,
    active_seconds: null,
  });
  assert.equal(unmeasured.activeSeconds, null);
  assert.equal(state.formatDuration(unmeasured.activeSeconds), null);

  const controller = (overrides = {}) => ({
    phase: { kind: 'loading' },
    feedback: { kind: 'idle' },
    envelope: null,
    journey: null,
    step: null,
    respondPrompt: null,
    controlLanguage: 'en',
    legacyResume: null,
    progress: state.journeyProgress(null),
    busy: false,
    help: null,
    voice: { kind: 'idle' },
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
    ...overrides,
  });

  const finishedJourney = { ...fixture('completed').response, recap: { ...fixture('completed').response.recap, active_seconds: null } };
  const recapHtml = renderToStaticMarkup(
    React.createElement(JourneySession, {
      controller: controller({
        phase: { kind: 'finished', journey: finishedJourney, recap: finishedJourney.recap },
        journey: finishedJourney,
        progress: state.journeyProgress(finishedJourney),
      }),
    }),
  );
  assert.ok(htmlHas(recapHtml, EN.finished_title));
  assert.ok(htmlHas(recapHtml, EN.duration_not_measured), 'an unmeasured duration is stated, not invented');
  assert.ok(htmlHas(recapHtml, 'en terrasse'), 'the single focus headline is shown');
  assert.ok(htmlHas(recapHtml, EN.next_focus));
  // Server-recorded capability evidence, in the server's own words.
  const capability = finishedJourney.recap.capability_evidence[0];
  assert.ok(htmlHas(recapHtml, EN.capability_shown));
  assert.ok(htmlHas(recapHtml, capability.context_native));
  assert.ok(htmlHas(recapHtml, EN[`capability_state_${capability.state}`]));
  // Practised targets use readable labels, not raw enum text.
  assert.ok(htmlHas(recapHtml, EN.evidence_produced_independent));
  assert.ok(!recapHtml.includes('produced_independent'), 'no raw enum leaks into the recap');
  // A story callback is attributed to the character, not left as a bare fragment.
  assert.ok(
    htmlHas(recapHtml, finishedJourney.scenario.character_name)
      && htmlHas(recapHtml, finishedJourney.recap.story_outcome.callback_fr),
  );
  assert.ok(!/\b\d+\s?min\b/.test(recapHtml.split(escapeHtml(EN.practiced))[0]), 'no fabricated duration');

  const partialJourney = fixture('ended_early').response;
  const partialHtml = renderToStaticMarkup(
    React.createElement(JourneySession, {
      controller: controller({
        phase: { kind: 'finished', journey: partialJourney, recap: partialJourney.recap },
        journey: partialJourney,
        progress: state.journeyProgress(partialJourney),
      }),
    }),
  );
  assert.ok(partialHtml.includes('data-state="partial"'), 'a partial stop looks partial');
  assert.ok(htmlHas(partialHtml, EN.finished_partial_title));
  assert.ok(htmlHas(partialHtml, EN.finished_partial_body));

  // =========================================================================
  // 8. Today entry — one action, and a separately labelled legacy resume
  // =========================================================================

  const todayHtml = renderToStaticMarkup(
    React.createElement(JourneyTodayCard, {
      controller: controller({
        phase: state.phaseFromEnvelope(fixture('first_day').response),
        envelope: fixture('first_day').response,
      }),
      onOpen: () => {},
    }),
  );
  assert.ok(htmlHas(todayHtml, EN.start), 'one clear start action');
  assert.ok(htmlHas(todayHtml, 'Un café au Mistral'));
  assert.ok(htmlHas(todayHtml, '4 min'), 'the estimate is the plan\'s own number');
  assert.ok(!htmlHas(todayHtml, EN.legacy_resume_title));

  const legacyEnvelope = fixture('active_legacy').response;
  const legacyHtml = renderToStaticMarkup(
    React.createElement(JourneyTodayCard, {
      controller: controller({
        phase: state.phaseFromEnvelope(legacyEnvelope),
        envelope: legacyEnvelope,
        legacyResume: legacyEnvelope.legacy_resume,
      }),
      onOpen: () => {},
      onOpenLegacy: () => {},
    }),
  );
  assert.ok(htmlHas(legacyHtml, EN.start), 'the journey still offers its own start');
  assert.ok(htmlHas(legacyHtml, EN.legacy_resume_title), 'and the old session is labelled separately');
  assert.ok(htmlHas(legacyHtml, EN.legacy_resume_action));

  // Preparing shows the retry hint instead of a second start action.
  const preparingHtml = renderToStaticMarkup(
    React.createElement(JourneyTodayCard, {
      controller: controller({
        phase: state.phaseFromJourney(fixture('preparing').response),
        journey: fixture('preparing').response,
      }),
      onOpen: () => {},
    }),
  );
  assert.ok(htmlHas(preparingHtml, EN.preparing_title) && htmlHas(preparingHtml, EN.preparing_retry));
  assert.ok(!htmlHas(preparingHtml, EN.start), 'never a second start while one is preparing');

  // A finished day is a read: no start, no restart.
  const doneHtml = renderToStaticMarkup(
    React.createElement(JourneyTodayCard, {
      controller: controller({
        phase: state.phaseFromJourney(fixture('completed').response),
        journey: fixture('completed').response,
      }),
      onOpen: () => {},
    }),
  );
  assert.ok(htmlHas(doneHtml, EN.done_today));
  assert.ok(!htmlHas(doneHtml, EN.start), 'a finished day is never restartable from here');

  // The capability being off renders nothing at all.
  assert.equal(
    renderToStaticMarkup(
      React.createElement(JourneyTodayCard, {
        controller: controller({
          phase: state.phaseFromEnvelope(fixture('flag_disabled').response),
          envelope: fixture('flag_disabled').response,
        }),
        onOpen: () => {},
      }),
    ),
    '',
  );

  // =========================================================================
  // 9. Control-language chrome — no product jargon, all three languages
  // =========================================================================

  for (const language of ['en', 'de', 'fr']) {
    const table = journeyCopy(language);
    const keys = Object.keys(table);
    assert.ok(keys.length > 40, `${language} copy is complete`);
    for (const key of keys) {
      assert.equal(typeof table[key], 'string');
      assert.ok(table[key].trim().length > 0, `${language}.${key} is not empty`);
      for (const jargon of ['La Une', 'Épreuve', 'Relevé', 'Feuilleton']) {
        assert.ok(!table[key].includes(jargon), `${language}.${key} avoids "${jargon}"`);
      }
    }
  }
  assert.deepEqual(Object.keys(journeyCopy('de')), Object.keys(journeyCopy('en')));
  assert.deepEqual(Object.keys(journeyCopy('fr')), Object.keys(journeyCopy('en')));
  // An unknown control language falls back rather than rendering blanks.
  assert.equal(journeyCopy('pt').start, journeyCopy('en').start);
  assert.equal(journeyCopy(null).start, journeyCopy('en').start);


  // =========================================================================
  // 10. WP-10 interruption recovery is WIRED IN, not merely available
  // =========================================================================
  //
  // The recovery layer was fully tested on its own before this; what is proved
  // here is the join: a recovered key really is adopted by the controller's
  // keyring, and a draft really does travel through the textarea a learner
  // types into. Nothing below fabricates a grade, a completion or a sync.

  // --- a recovered key is adopted, never re-minted --------------------------

  let adoptMints = 0;
  const adoptRing = requests.createMutationKeyring(() => `fresh-${(adoptMints += 1)}`);
  const recoveredIntent = 'attempt:j9:s9:4:{"mode":"text","text":"un cafe"}';
  adoptRing.adopt(recoveredIntent, 'the-original-key');
  assert.equal(adoptRing.idFor(recoveredIntent), 'the-original-key');
  assert.equal(adoptMints, 0, 'a recovered intent mints nothing');
  assert.equal(adoptRing.idFor(recoveredIntent), 'the-original-key', 'and stays adopted');
  assert.equal(
    adoptRing.idFor('attempt:j9:s9:4:{"mode":"text","text":"autre"}'),
    'fresh-1',
    'a genuinely different answer is still a new intent with a new key',
  );
  adoptRing.adopt('', 'nothing');
  adoptRing.adopt('something', '');
  assert.equal(adoptRing.size(), 2, 'a half-empty adoption is refused, not stored');

  // --- the intent really carries the interrupted request --------------------

  const { parseAttemptIntent } = require('./useDailyJourney.ts');
  const bodyWithColons = { mode: 'text', text: 'Margaux: un cafe, 9:30, s’il vous plait' };
  const roundTrip = parseAttemptIntent(
    `attempt:00000000-0000-4000-8000-000000000008:00000000-0000-4000-9000-000008000002:5:${JSON.stringify(bodyWithColons)}`,
  );
  assert.deepEqual(roundTrip.input, bodyWithColons, 'a colon in the answer does not break the key');
  assert.equal(roundTrip.expectedRevision, 5);
  assert.equal(roundTrip.stepId, '00000000-0000-4000-9000-000008000002');
  // Only an attempt is ever re-sent on the learner's behalf.
  assert.equal(parseAttemptIntent('advance:j1:s1:3'), null);
  assert.equal(parseAttemptIntent('attempt:j1:s1:3:not json'), null);
  assert.equal(parseAttemptIntent('attempt:j1:s1:notanumber:{"mode":"text"}'), null);
  assert.equal(parseAttemptIntent(''), null);

  // --- a minimal hook runner, so the REAL fields can be typed into ----------
  //
  // There is no DOM and no React test renderer in this repo (see the WP-10
  // harness note), so the component is driven directly with a hook
  // implementation swapped in for the duration. It is the real component
  // function, the real props and the real element tree — only the scheduler is
  // ours.

  function mountView(Component, initialProps) {
    const cells = [];
    const queue = [];
    const saved = {};
    let props = initialProps;
    let cursor = 0;
    let tree = null;
    let depth = 0;

    const sameDeps = (a, b) =>
      Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
    const cell = () => {
      const slot = cells[cursor] || (cells[cursor] = {});
      cursor += 1;
      return slot;
    };

    const fake = {
      useState(initial) {
        const slot = cell();
        if (!('value' in slot)) slot.value = typeof initial === 'function' ? initial() : initial;
        return [
          slot.value,
          (next) => {
            const value = typeof next === 'function' ? next(slot.value) : next;
            if (Object.is(value, slot.value)) return;
            slot.value = value;
            render();
          },
        ];
      },
      useRef(initial) {
        const slot = cell();
        if (!('ref' in slot)) slot.ref = { current: initial };
        return slot.ref;
      },
      useMemo(factory, deps) {
        const slot = cell();
        if (!('value' in slot) || !sameDeps(slot.deps, deps)) {
          slot.value = factory();
          slot.deps = deps;
        }
        return slot.value;
      },
      useCallback(fn, deps) {
        return fake.useMemo(() => fn, deps);
      },
      useEffect(fn, deps) {
        const slot = cell();
        if (!('deps' in slot) || !sameDeps(slot.deps, deps)) {
          slot.deps = deps;
          if (typeof slot.cleanup === 'function') slot.cleanup();
          slot.cleanup = undefined;
          queue.push(() => {
            const cleanup = fn();
            slot.cleanup = typeof cleanup === 'function' ? cleanup : undefined;
          });
        }
      },
    };
    const names = Object.keys(fake);

    function withHooks(run) {
      if (depth === 0) {
        names.forEach((name) => {
          saved[name] = React[name];
          React[name] = fake[name];
        });
      }
      depth += 1;
      try {
        return run();
      } finally {
        depth -= 1;
        if (depth === 0) names.forEach((name) => { React[name] = saved[name]; });
      }
    }

    function render() {
      return withHooks(() => {
        cursor = 0;
        tree = Component(props);
        let guard = 0;
        while (queue.length) {
          if ((guard += 1) > 200) throw new Error('effects never settled');
          queue.shift()();
        }
        return tree;
      });
    }

    render();
    return {
      get tree() { return tree; },
      rerender(next) {
        props = next;
        return render();
      },
      settle: async () => {
        for (let turn = 0; turn < 12; turn += 1) await Promise.resolve();
        withHooks(() => {
          let guard = 0;
          while (queue.length) {
            if ((guard += 1) > 200) throw new Error('effects never settled');
            queue.shift()();
          }
        });
      },
    };
  }

  function findIn(node, predicate) {
    if (!node || typeof node !== 'object') return null;
    if (Array.isArray(node)) {
      for (let index = 0; index < node.length; index += 1) {
        const hit = findIn(node[index], predicate);
        if (hit) return hit;
      }
      return null;
    }
    if (!node.props) return null;
    if (predicate(node)) return node;
    return findIn(node.props.children, predicate);
  }
  const textareaIn = (tree) => findIn(tree, (element) => element.type === 'textarea');

  /** A draft store with exactly the surface the renderers are given. */
  function draftStore(seed) {
    const map = new Map(Object.entries(seed || {}));
    return {
      map,
      get: (key) => map.get(key) ?? '',
      set: (key, text) => {
        if (text) map.set(key, text);
        else map.delete(key);
      },
    };
  }

  const stepProps = {
    copy: EN,
    busy: false,
    feedback: { kind: 'idle' },
    help: null,
    onHelp: () => {},
    onSubmit: () => {},
    onContinue: () => {},
  };

  // --- a recall draft round-trips through the real textarea ----------------

  const repairJourney = fixture('explain_delay_repair').response;
  const shortAnswerStep = {
    ...repairJourney.steps.find((entry) => entry.kind === 'recall'),
    status: 'active',
  };
  assert.equal(shortAnswerStep.prompt.task_type, 'short_answer', 'a real written recall step');

  const recallDrafts = draftStore();
  const recall = mountView(steps.RecallStepView, {
    ...stepProps,
    step: shortAnswerStep,
    draft: recallDrafts,
  });
  const recallField = textareaIn(recall.tree);
  assert.ok(recallField, 'the written recall step renders a textarea');
  assert.equal(recallField.props.value, '', 'nothing typed yet, nothing shown');

  recallField.props.onChange({ target: { value: 'Le train a du retard' } });
  assert.equal(
    recallDrafts.map.get(shortAnswerStep.id),
    'Le train a du retard',
    'what the learner typed is persisted under the step id',
  );
  assert.equal(recallDrafts.map.size, 1, 'one step, one draft — nothing else is written');
  assert.equal(textareaIn(recall.tree).props.value, 'Le train a du retard');

  // A cold start: a brand-new mount reading the same store.
  const recallAgain = mountView(steps.RecallStepView, {
    ...stepProps,
    step: shortAnswerStep,
    draft: recallDrafts,
  });
  assert.equal(
    textareaIn(recallAgain.tree).props.value,
    'Le train a du retard',
    'the draft comes back after an interruption',
  );
  // A draft is a draft: it is not presented as a checked answer.
  const recallDraftHtml = renderToStaticMarkup(
    React.createElement(steps.RecallStepView, {
      ...stepProps,
      step: shortAnswerStep,
      draft: recallDrafts,
    }),
  );
  assert.ok(!htmlHas(recallDraftHtml, EN.correct) && !htmlHas(recallDraftHtml, EN.wrong));

  // A renderer given no store still works; it simply keeps nothing.
  const noStore = mountView(steps.RecallStepView, { ...stepProps, step: shortAnswerStep });
  textareaIn(noStore.tree).props.onChange({ target: { value: 'sans magasin' } });
  assert.equal(textareaIn(noStore.tree).props.value, 'sans magasin');

  // --- a respond draft is per TURN: a new turn starts clean ----------------

  const respondJourney = fixture('wrong_then_supported').response.journey;
  const respondStep = {
    ...respondJourney.steps.find((entry) => entry.kind === 'respond'),
    status: 'active',
  };
  const turnOne = { ...respondStep, prompt: { ...respondStep.prompt, turn_index: 1 } };
  const turnTwo = { ...respondStep, prompt: { ...respondStep.prompt, turn_index: 2 } };

  const respondDrafts = draftStore();
  const respondProps = {
    ...stepProps,
    voice: { kind: 'idle' },
    onStartRecording: () => {},
    onStopRecording: () => {},
    onResetVoice: () => {},
    draft: respondDrafts,
  };
  const respond = mountView(steps.RespondStepView, { ...respondProps, step: turnOne });
  assert.equal(textareaIn(respond.tree).props.value, '');
  textareaIn(respond.tree).props.onChange({ target: { value: 'Je suis desole du retard' } });
  assert.equal(
    respondDrafts.map.get(`${respondStep.id}:1`),
    'Je suis desole du retard',
    'the draft is keyed by step AND turn',
  );
  assert.equal(textareaIn(respond.tree).props.value, 'Je suis desole du retard');

  // The server hands back another turn on the same step.
  respond.rerender({ ...respondProps, step: turnTwo });
  assert.equal(
    textareaIn(respond.tree).props.value,
    '',
    'a new turn starts with an empty field, never the sentence already sent',
  );
  assert.equal(
    respondDrafts.map.get(`${respondStep.id}:1`),
    'Je suis desole du retard',
    'and the previous turn is not silently rewritten by the new one',
  );
  textareaIn(respond.tree).props.onChange({ target: { value: 'Le metro etait bloque' } });
  assert.equal(respondDrafts.map.get(`${respondStep.id}:2`), 'Le metro etait bloque');

  // Coming back to the interrupted turn restores exactly that turn's words.
  respond.rerender({ ...respondProps, step: turnOne });
  assert.equal(textareaIn(respond.tree).props.value, 'Je suis desole du retard');

  // --- the connection state is visible, and never reads as a result --------

  const connectionOf = (state, extra) => ({
    connection: {
      state,
      online: state !== 'offline_cached' && state !== 'offline_empty',
      readingCache: state === 'offline_cached',
      unsent: state === 'pending_sync',
      stale: false,
      lastSyncedAt: null,
      ...(extra || {}),
    },
    draftFor: () => '',
    saveDraft: () => {},
  });

  const shellHtml = (recovery, phase, journey) =>
    renderToStaticMarkup(
      React.createElement(JourneySession, {
        controller: controller({ recovery, phase, journey }),
      }),
    );

  const activeJourney = fixture('wrong_then_supported').response.journey;
  const sessionPhase = state.phaseFromJourney(activeJourney);

  for (const [kind, line] of [
    ['offline_cached', EN.offline_cached],
    ['offline_empty', EN.offline_empty],
    ['pending_sync', EN.pending_sync],
    ['syncing', EN.syncing],
  ]) {
    const html = shellHtml(connectionOf(kind), sessionPhase, activeJourney);
    assert.ok(htmlHas(html, line), `${kind} is stated to the learner`);
    // An unsynced state is never dressed up as a verdict or a finished day.
    for (const forbidden of [EN.correct, EN.wrong, EN.supported, EN.finished_title, EN.done_today]) {
      assert.ok(!htmlHas(html, forbidden), `${kind} never reads as "${forbidden}"`);
    }
  }

  // Connected, settled and current: no banner at all.
  const liveHtml = shellHtml(connectionOf('live'), sessionPhase, activeJourney);
  for (const line of [EN.offline_cached, EN.offline_empty, EN.pending_sync, EN.syncing]) {
    assert.ok(!htmlHas(liveHtml, line), 'a live session says nothing about the connection');
  }

  // A cached copy from an earlier day says so.
  const staleHtml = shellHtml(
    connectionOf('offline_cached', { stale: true }),
    sessionPhase,
    activeJourney,
  );
  assert.ok(htmlHas(staleHtml, EN.stale_from_earlier_day));

  // A controller without a recovery layer still renders (the WP-07 contract).
  assert.ok(
    renderToStaticMarkup(
      React.createElement(JourneySession, {
        controller: controller({ phase: sessionPhase, journey: activeJourney }),
      }),
    ).length > 0,
  );


  // --- the controller itself: a recovered mutation is REPLAYED under its own
  //     key, and no second learning record is created ------------------------
  //
  // This runs the real `useDailyJourney` against the real `useJourneyRecovery`
  // and the real store, over an in-memory `localStorage`. Only the scheduler,
  // the signed-in identity and the HTTP transport are stand-ins.

  const memoryStorage = (() => {
    const map = new Map();
    return {
      map,
      get length() { return map.size; },
      key: (index) => Array.from(map.keys())[index] ?? null,
      getItem: (key) => (map.has(key) ? map.get(key) : null),
      setItem: (key, value) => map.set(key, String(value)),
      removeItem: (key) => map.delete(key),
    };
  })();
  const inertEvents = { addEventListener: () => {}, removeEventListener: () => {} };
  global.window = { localStorage: memoryStorage, setTimeout, clearTimeout, ...inertEvents };
  global.document = { visibilityState: 'visible', ...inertEvents };

  const recoveryLib = require('@/lib/journey-recovery');
  const resilience = require('@/lib/pilot-resilience');
  const { useDailyJourney } = require('./useDailyJourney.ts');

  const serverJourney = fixture('explain_delay_repair').response;
  const interruptedStep = serverJourney.steps.find((entry) => entry.id === serverJourney.current_step_id);
  assert.equal(interruptedStep.kind, 'respond', 'the interrupted step is a written reply');

  const interruptedBody = { mode: 'text', text: 'Je suis desole, le metro etait bloque.' };
  const interruptedIntent = `attempt:${serverJourney.id}:${interruptedStep.id}:${serverJourney.revision}:${JSON.stringify(interruptedBody)}`;
  const ORIGINAL_KEY = 'mutation-from-the-previous-run';

  // The previous run of the app: the request went out and was never answered.
  const learnerScope = resilience.accountScopeKey(TEST_LEARNER_ID);
  resilience.syncAccountScope(learnerScope, memoryStorage);
  const seeded = recoveryLib.createJourneyRecoveryStore({
    scope: learnerScope,
    localDate: serverJourney.local_date,
    storage: memoryStorage,
  });
  seeded.update((record) =>
    recoveryLib.putDraft(
      recoveryLib.putSnapshot(record, serverJourney),
      interruptedStep.id,
      interruptedBody.text,
    ),
  );
  seeded.update((record) =>
    recoveryLib.putPending(record, {
      intent: interruptedIntent,
      mutationId: ORIGINAL_KEY,
      kind: 'attempt',
      journeyId: serverJourney.id,
      stepId: interruptedStep.id,
      expectedRevision: serverJourney.revision,
      body: interruptedBody,
      startedAt: new Date().toISOString(),
      dispatched: true,
    }),
  );

  const replayEnvelope = {
    contract_version: 1,
    enabled: true,
    control_language: 'en',
    local_date: serverJourney.local_date,
    timezone: serverJourney.timezone,
    journey: serverJourney,
    available: null,
    legacy_resume: null,
  };
  // The server's stored receipt for that exact mutation id.
  const storedReceipt = {
    ...fixture('unassisted_success').response,
    journey: serverJourney,
  };

  apiCalls.length = 0;
  apiHandler = (method, args) => {
    if (method === 'getDailyJourneyToday') return Promise.resolve(replayEnvelope);
    if (method === 'getDailyJourney') return Promise.resolve(serverJourney);
    if (method === 'submitDailyJourneyAttempt') {
      assert.equal(
        args[2].mutation_id,
        ORIGINAL_KEY,
        'the replay carries the key the interrupted request went out under',
      );
      return Promise.resolve(storedReceipt);
    }
    throw new Error(`unexpected request: ${method}`);
  };

  let live = null;
  const host = mountView(() => {
    live = useDailyJourney({});
    return null;
  }, {});
  await host.settle();
  await host.settle();

  const attempts = apiCalls.filter((entry) => entry.method === 'submitDailyJourneyAttempt');
  assert.equal(attempts.length, 1, 'the interrupted attempt is replayed exactly once');
  assert.equal(attempts[0].args[0], serverJourney.id);
  assert.equal(attempts[0].args[1], interruptedStep.id);
  assert.equal(
    attempts[0].args[2].mutation_id,
    ORIGINAL_KEY,
    'a recovered key is adopted, never re-minted',
  );
  assert.deepEqual(attempts[0].args[2].input, interruptedBody, 'and the body is the one that was typed');
  assert.equal(attempts[0].args[2].expected_revision, serverJourney.revision);

  // The learner sees the feedback they never got — built from the server's own
  // AttemptResult, not invented locally.
  assert.equal(live.feedback.kind, 'graded');
  assert.equal(live.feedback.result.evidence_ref, storedReceipt.evidence_ref);

  // The recovery layer is exposed on the controller and has settled.
  assert.ok(live.recovery, 'the controller exposes the recovery layer');
  assert.equal(
    recoveryLib.createJourneyRecoveryStore({
      scope: learnerScope,
      localDate: serverJourney.local_date,
      storage: memoryStorage,
    }).read().pending,
    null,
    'nothing is left pending once the server has answered',
  );
  assert.equal(live.recovery.replayPlan, null, 'the plan is offered once, not on every render');
  // The step the learner was answering is still open, so their words are still
  // held on the device — and the connection state says exactly that rather than
  // claiming everything is synced.
  assert.equal(live.recovery.draftFor(interruptedStep.id), interruptedBody.text);
  assert.equal(live.recovery.connection.state, 'pending_sync');
  assert.equal(live.recovery.connection.online, true);
  assert.equal(live.recovery.connection.readingCache, false, 'a served snapshot is not a cached one');

  // Nothing that must never be persisted was persisted. Contract revision 1:
  // `/audio/transcribe` is stateless, so there is no transcript to cache and no
  // captured audio to keep — only the text the learner drafted or was shown.
  const persisted = memoryStorage.getItem(recoveryLib.journeyRecoveryKey(learnerScope)) || '';
  for (const forbidden of ['blob:', 'data:audio', 'access_token', 'refresh_token', 'Bearer ', 'transcript_ref']) {
    assert.ok(!persisted.includes(forbidden), `the cache never holds "${forbidden}"`);
  }

  apiHandler = () => {
    throw new Error('no api handler installed');
  };
  delete global.window;
  delete global.document;

  console.error = realConsoleError;
  console.log('daily journey frontend tests passed');
})().catch((error) => {
  console.error = realConsoleError;
  console.error(error);
  process.exit(1);
});
