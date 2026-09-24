/**
 * Home never flashes the legacy (journey-off) Home in front of a journey Home
 * — 2026-09-24 walkthrough.
 *
 * Run: node --test lib/home-loading.test.js
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
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

const home = require('./home-loading.ts');
const resilience = require('./pilot-resilience.ts');

function fakeStorage(seed = {}) {
  const map = new Map(Object.entries(seed));
  return {
    get length() { return map.size; },
    key(index) { return Array.from(map.keys())[index] ?? null; },
    getItem(key) { return map.has(key) ? map.get(key) : null; },
    setItem(key, value) { map.set(key, String(value)); },
    removeItem(key) { map.delete(key); },
  };
}

const base = {
  loading: false,
  loadError: false,
  journeyEnabled: false,
  journeyPhaseKind: 'loading',
  rememberedKind: null,
};

test('while the journey capability is unread, a journey learner sees the skeleton, never the cached legacy Home', () => {
  assert.equal(home.homeRender({ ...base, rememberedKind: 'journey' }), 'skeleton');
  assert.equal(home.homeRender({ ...base, rememberedKind: null }), 'skeleton', 'an unknown device is treated as a journey one');
});

test('the cached legacy edition still paints at once for a journey-off learner', () => {
  assert.equal(home.homeRender({ ...base, rememberedKind: 'legacy' }), 'home');
});

test('the answer settles it either way', () => {
  assert.equal(home.homeRender({ ...base, journeyEnabled: true, journeyPhaseKind: 'offer' }), 'home');
  assert.equal(home.homeRender({ ...base, journeyPhaseKind: 'disabled' }), 'home');
  assert.equal(home.resolvedHomeKind({ journeyEnabled: true, journeyPhaseKind: 'session' }), 'journey');
  assert.equal(home.resolvedHomeKind({ journeyEnabled: false, journeyPhaseKind: 'disabled' }), 'legacy');
  assert.equal(home.resolvedHomeKind({ journeyEnabled: false, journeyPhaseKind: 'loading' }), null);
  assert.equal(home.resolvedHomeKind({ journeyEnabled: false, journeyPhaseKind: 'load_failed' }), null);
});

test('the page read is still loading: skeleton; a load error is shown, never an endless skeleton', () => {
  assert.equal(home.homeRender({ ...base, loading: true, rememberedKind: 'legacy' }), 'skeleton');
  assert.equal(home.homeRender({ ...base, loadError: true }), 'home');
  assert.equal(home.homeRender({ ...base, journeyPhaseKind: 'load_failed' }), 'home');
});

test('the remembered kind is account-scoped cache: read back, validated, swept on sign-out', () => {
  const storage = fakeStorage();
  assert.equal(home.readHomeKind(storage), null);
  home.rememberHomeKind('journey', storage);
  assert.equal(home.readHomeKind(storage), 'journey');
  assert.ok(home.HOME_KIND_KEY.startsWith('pilot:'));
  resilience.clearPilotResilience(storage);
  assert.equal(home.readHomeKind(storage), null);
  const junk = fakeStorage({ [home.HOME_KIND_KEY]: JSON.stringify('legacy-ish') });
  assert.equal(home.readHomeKind(junk), null);
});

test('the Atelier page gates Home and its cache note on the settled kind', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.ok(page.includes('const homePending = homeRender({'));
  assert.ok(page.includes("(view === 'today' || view === 'journey' || !session) && homePending ? ("));
  assert.ok(page.includes('{cachedEditionAt && !homePending && !journeyEnabled && ('), 'the cache note is the legacy Home\'s');
  assert.ok(page.includes('rememberHomeKind(settledHomeKind)'));
  const screen = fs.readFileSync(path.join(WEB_ROOT, 'components/atelier-v2/home/HomeScreen.tsx'), 'utf8');
  assert.ok(!screen.includes('{overrunMinutes} minutes demandées'), 'the pre-rhythm overrun clause is gone');
  assert.ok(!page.includes('overrunMinutes='));
  const skeleton = screen.slice(screen.indexOf('export function HomeSkeleton'));
  assert.ok(skeleton.includes("atelierChrome(language ?? 'fr').loading"), 'the loader is labelled in the chrome language');
  assert.ok(!skeleton.includes('av2-home__tiles'), 'the loader never draws the legacy tiles');
});
