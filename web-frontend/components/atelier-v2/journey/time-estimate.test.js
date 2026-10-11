// node --test components/atelier-v2/journey/time-estimate.test.js
//
// WP-128 — one estimate, said the same way on Home, the chips, the plan and the
// ending: the core the rhythm budgets, each optional extension with its own
// minutes (never folded in), and a longer day said before Start. en/de/fr.

const assert = require('node:assert/strict');
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

const {
  coreEstimateLabel,
  extensionLabel,
  extensionMinutes,
  extensionSeconds,
  measuredBesidePlanned,
} = require('./time-estimate.ts');

const ESTIMATE = {
  budget_seconds: 600,
  core_seconds: 570,
  basis: 'plan',
  longer_day: false,
  extensions: [
    { kind: 'words', seconds: 234, in_day: false },
    { kind: 'letter', seconds: 300, in_day: false },
    { kind: 'forge', seconds: 300, in_day: false },
  ],
};

test('the core is the one number, in each chrome language', () => {
  assert.equal(coreEstimateLabel(ESTIMATE, 999, 'fr'), '10 min');
  assert.equal(coreEstimateLabel(ESTIMATE, 999, 'de'), '10 Min.');
  assert.equal(coreEstimateLabel(ESTIMATE, 999, 'en'), '10 min');
  // No estimate from the server: the offer's own forecast, never a guess.
  assert.equal(coreEstimateLabel(null, 480, 'fr'), '8 min');
  assert.equal(coreEstimateLabel(null, null, 'fr'), null);
});

test('an extension carries its own minutes and is never added to the core', () => {
  assert.equal(extensionLabel(ESTIMATE, 'words', 'fr'), '+ mots ≈ 4 min');
  assert.equal(extensionLabel(ESTIMATE, 'words', 'de'), '+ Wörter ≈ 4 Min.');
  assert.equal(extensionLabel(ESTIMATE, 'letter', 'en'), '+ letter ≈ 5 min');
  assert.equal(extensionMinutes(ESTIMATE, 'forge', 'fr'), '≈ 5 min');
  assert.equal(extensionSeconds(ESTIMATE, 'reading'), null);
  assert.equal(extensionLabel(ESTIMATE, 'reading', 'fr'), null);
  assert.equal(coreEstimateLabel(ESTIMATE, null, 'fr'), '10 min', 'the core stays the core');
});

test('a longer day says its estimate before Start', () => {
  const longer = { ...ESTIMATE, core_seconds: 760, longer_day: true };
  assert.equal(coreEstimateLabel(longer, null, 'fr'), 'Une journée plus longue · ≈ 13 min');
  assert.equal(coreEstimateLabel(longer, null, 'de'), 'Ein längerer Tag · ≈ 13 Min.');
  assert.equal(coreEstimateLabel(longer, null, 'en'), 'A longer day · ≈ 13 min');
});

test('the ending sets the measured minutes beside the planned core, never a verdict', () => {
  assert.equal(measuredBesidePlanned('12 min', 570, 'fr'), '12 min · prévu 10 min');
  assert.equal(measuredBesidePlanned('12 Min.', 570, 'de'), '12 Min. · geplant 10 Min.');
  assert.equal(measuredBesidePlanned('10 min', 570, 'en'), '10 min', 'the same number once');
  assert.equal(measuredBesidePlanned('9 min', null, 'en'), '9 min');
});
