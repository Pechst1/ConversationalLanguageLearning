/**
 * P11 · «Erneut versuchen» after a failed «Weiter» re-sends the same advance.
 *
 * 17 Nov walk (a1-part3): offline at the scene's last panel, «Weiter» failed;
 * back online, «Erneut versuchen» re-sent the last ANSWER (the warm-up item before
 * the scene). Its stored receipt replayed the journey as it stood then: the screen
 * jumped back to «Vor der Szene · Schritt 3 von 6» and the panels restarted at 1/5.
 *
 * Run: `node --test components/atelier-v2/journey/p11-retry-same-advance.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// The transport is never exercised here (as in journey-latency.test.js).
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { default: new Proxy({}, { get: () => () => Promise.resolve({ data: {} }) }) },
};

const { retryPlan } = require(path.join(HERE, 'journey-requests.ts'));

const onEnding = { id: 'j1', current_step_id: 'resolution' };

test('a failed advance at the last panel is retried as the same advance, not the last answer', () => {
  const failed = { kind: 'advance', journeyId: 'j1', stepId: 'resolution', skipToScene: false };
  // An answer was given earlier (the warm-up item): it must not be re-sent.
  assert.deepEqual(retryPlan(failed, true, onEnding), { kind: 'advance', skipToScene: false });
});

test('a failed skip to the scene is retried as the skip', () => {
  const failed = { kind: 'advance', journeyId: 'j1', stepId: 'rule', skipToScene: true };
  assert.deepEqual(retryPlan(failed, false, { id: 'j1', current_step_id: 'rule' }), {
    kind: 'advance',
    skipToScene: true,
  });
});

test('once the journey stands elsewhere, the card clears: the screen is the journey', () => {
  const failed = { kind: 'advance', journeyId: 'j1', stepId: 'resolution', skipToScene: false };
  assert.deepEqual(retryPlan(failed, true, { id: 'j1', current_step_id: 'next' }), { kind: 'clear' });
});

test('a failed answer re-sends the answer; a failed finish the finish', () => {
  assert.deepEqual(retryPlan({ kind: 'attempt' }, true, onEnding), { kind: 'attempt' });
  assert.deepEqual(retryPlan({ kind: 'finish', finishKind: 'complete' }, true, null), {
    kind: 'finish',
    finishKind: 'complete',
  });
  assert.deepEqual(retryPlan(null, false, onEnding), { kind: 'clear' });
});

test('the hook routes «Erneut versuchen» through the plan and records every failed advance', () => {
  const hook = fs.readFileSync(path.join(HERE, 'useDailyJourney.ts'), 'utf8');
  assert.match(hook, /retryPlan\(lastFailedRef\.current/);
  assert.match(hook, /kind: 'advance', journeyId: target\.id, stepId: step\.id, skipToScene/);
});
