/**
 * Where a cold start lands — WP-20's fix for WP-19 defect D-1.
 *
 * WP-19's simulator walk killed the app inside the V2 journey three times and
 * came back to the **legacy** Séance three times, because `pilot:resume:v1`
 * held an unfinished practice session and nothing had ever written the journey
 * anywhere. These tests pin the rule that replaces that behaviour, and — just
 * as importantly — pin that a learner with no open journey still resumes
 * exactly what they resumed before.
 *
 * Same harness as `lib/journey-recovery.test.js`: plain node, `node:assert`,
 * sucrase, an injected storage. No DOM, no renderer.
 *
 * Run: `node lib/journey-resume.test.js`
 */

const assert = require('node:assert/strict');
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

const resume = require('./journey-resume.ts');
const resilience = require('./pilot-resilience.ts');

function fakeStorage(seed = {}) {
  const map = new Map(Object.entries(seed));
  return {
    get length() { return map.size; },
    key(index) { return Array.from(map.keys())[index] ?? null; },
    getItem(key) { return map.has(key) ? map.get(key) : null; },
    setItem(key, value) { map.set(key, String(value)); },
    removeItem(key) { map.delete(key); },
    dump() { return Object.fromEntries(map); },
  };
}

const LEGACY = JSON.stringify({
  href: '/atelier?resume=session-42',
  kind: 'atelier',
  entityId: 'session-42',
  updatedAt: '2026-09-06T08:00:00.000Z',
});

function markOf(status, updatedAt = new Date().toISOString()) {
  return JSON.stringify({
    href: resume.JOURNEY_RESUME_HREF,
    journeyId: 'journey-1',
    localDate: '2026-09-07',
    status,
    updatedAt,
  });
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

// --- the defect itself ------------------------------------------------------

test('D-1: an open journey outranks the stored legacy practice session', () => {
  for (const status of ['preparing', 'active', 'paused']) {
    const storage = fakeStorage({
      'pilot:resume:v1': LEGACY,
      [resume.JOURNEY_RESUME_KEY]: markOf(status),
    });
    assert.equal(
      resume.resolveResumeHref(new Date(), storage),
      '/atelier?view=journey',
      `an open journey (${status}) must win the cold start`,
    );
  }
});

test('with no journey mark the legacy activity resumes exactly as before', () => {
  const storage = fakeStorage({ 'pilot:resume:v1': LEGACY });
  assert.equal(resume.resolveResumeHref(new Date(), storage), '/atelier?resume=session-42');
});

test('with neither, nothing is navigated to', () => {
  assert.equal(resume.resolveResumeHref(new Date(), fakeStorage()), null);
});

// --- the journey must not win when resuming it would be a lie ---------------

test('a finished or abandoned journey never wins', () => {
  for (const status of ['completed', 'ended_early', 'unavailable']) {
    const storage = fakeStorage({
      'pilot:resume:v1': LEGACY,
      [resume.JOURNEY_RESUME_KEY]: markOf(status),
    });
    assert.equal(
      resume.resolveResumeHref(new Date(), storage),
      '/atelier?resume=session-42',
      `${status} must fall through to the legacy activity`,
    );
  }
});

test('a mark older than the 48h window is discarded, not resumed', () => {
  const stale = new Date(Date.now() - 49 * 60 * 60 * 1000).toISOString();
  const storage = fakeStorage({
    'pilot:resume:v1': LEGACY,
    [resume.JOURNEY_RESUME_KEY]: markOf('active', stale),
  });
  assert.equal(resume.resolveResumeHref(new Date(), storage), '/atelier?resume=session-42');
  assert.equal(resume.readJourneyResume(new Date(), storage), null);
});

test('a mark inside the window is kept across a night', () => {
  const lastNight = new Date(Date.now() - 10 * 60 * 60 * 1000).toISOString();
  const storage = fakeStorage({ [resume.JOURNEY_RESUME_KEY]: markOf('active', lastNight) });
  assert.equal(resume.resolveResumeHref(new Date(), storage), '/atelier?view=journey');
});

// --- the mark never invents a destination -----------------------------------

test('a foreign or corrupt href is refused rather than navigated to', () => {
  for (const bad of [
    JSON.stringify({ ...JSON.parse(markOf('active')), href: 'https://example.com/evil' }),
    JSON.stringify({ ...JSON.parse(markOf('active')), href: '/settings' }),
    '{not json',
    JSON.stringify({ status: 'active' }),
  ]) {
    const storage = fakeStorage({ [resume.JOURNEY_RESUME_KEY]: bad });
    assert.equal(resume.readJourneyResume(new Date(), storage), null);
    assert.equal(resume.resolveResumeHref(new Date(), storage), null);
  }
});

test('a mark with an unparseable timestamp is refused', () => {
  const storage = fakeStorage({ [resume.JOURNEY_RESUME_KEY]: markOf('active', 'not-a-date') });
  assert.equal(resume.readJourneyResume(new Date(), storage), null);
});

// --- writing and clearing ---------------------------------------------------

test('markJourneyResume writes the one destination and clearJourneyResume removes it', () => {
  const storage = fakeStorage();
  resume.markJourneyResume(
    { journeyId: 'journey-9', localDate: '2026-09-07', status: 'active' },
    storage,
  );
  const stored = JSON.parse(storage.getItem(resume.JOURNEY_RESUME_KEY));
  assert.equal(stored.href, '/atelier?view=journey');
  assert.equal(stored.journeyId, 'journey-9');
  assert.equal(resume.resolveResumeHref(new Date(), storage), '/atelier?view=journey');
  resume.clearJourneyResume(storage);
  assert.equal(storage.getItem(resume.JOURNEY_RESUME_KEY), null);
});

test('the mark lives under the pilot: prefix, so sign-out already sweeps it', () => {
  const storage = fakeStorage();
  resume.markJourneyResume({ journeyId: 'j', localDate: '2026-09-07', status: 'active' }, storage);
  assert.ok(resume.JOURNEY_RESUME_KEY.startsWith('pilot:'));
  assert.ok(resilience.pilotKeys(storage).includes(resume.JOURNEY_RESUME_KEY));
  resilience.clearPilotResilience(storage);
  assert.equal(storage.getItem(resume.JOURNEY_RESUME_KEY), null);
});

test('journeyIsOpen answers for every contract status', () => {
  assert.deepEqual(
    ['preparing', 'active', 'paused', 'completed', 'ended_early', 'unavailable'].map(resume.journeyIsOpen),
    [true, true, true, false, false, false],
  );
  assert.equal(resume.journeyIsOpen(null), false);
  assert.equal(resume.journeyIsOpen(undefined), false);
});

let failed = 0;
for (const [name, fn] of tests) {
  try {
    fn();
  } catch (error) {
    failed += 1;
    console.error(`FAIL ${name}\n  ${error.message}`);
  }
}
if (failed) {
  console.error(`${failed} of ${tests.length} journey-resume tests failed`);
  process.exit(1);
}
console.log(`journey resume tests passed (${tests.length})`);
