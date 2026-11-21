// node --test components/atelier-v2/journey/r3-day-total.test.js
//
// Round 3 (walk 2, 17 Nov 2026): Home's day card printed «8 Min. · + Wörter ≈ 1 Min.»
// over a step list «Szene 8 / Grammatik 2 / Wörter 1»: the headline left La Forge
// out. The card's one figure is now the sum of the step minutes it shows.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { dayTotalLabel } = require('./time-estimate.ts');

const steps = [
  { kind: 'scene', state: 'next', minutes: 8 },
  { kind: 'grammar', state: 'todo', minutes: 4 },
  { kind: 'words', state: 'todo', minutes: 5 },
  { kind: 'finish', state: 'todo', minutes: 0 },
];
const session = { steps, minutes_left: 17 };

test('the day figure is the sum of the steps shown under it', () => {
  const shown = steps.filter((step) => step.state !== 'done').reduce((sum, step) => sum + step.minutes, 0);
  assert.equal(dayTotalLabel(session, null, 'de'), `${shown} Min.`);
  assert.equal(dayTotalLabel(session, null, 'fr'), `${shown} min`);
});

test('a longer day keeps its words around the sum', () => {
  assert.equal(dayTotalLabel(session, { core_seconds: 600, extensions: [], longer_day: true }, 'de'), 'Ein längerer Tag · ≈ 17 Min.');
});

test('without a day session the card keeps its own line', () => {
  assert.equal(dayTotalLabel(null, null, 'en'), null);
  assert.equal(dayTotalLabel({ minutes_left: 0 }, null, 'en'), null);
});

test('the day card prints that figure', () => {
  const source = fs.readFileSync(path.join(__dirname, 'JourneyTodayCard.tsx'), 'utf8');
  assert.match(source, /dayTotalLabel\(phase\.envelope\.session/);
});
