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

// #470 — Home printed the day's words twice with two roundings of one number of
// seconds: the card through `formatDuration` (round), the plan row through the
// server's `minutes()` (round up). 17 new and 5 due = 370 s: «6 Min.» and «7 Min.».
test('#470 · the day card and the plan row print the words step with the same minutes', () => {
  const { sessionRows } = require(path.join(WEB_ROOT, 'lib/day-session.ts'));
  const WORDS_SECONDS = 17 * 20 + 5 * 6;
  // The server's `daily_session.minutes()`: whole minutes, rounded up.
  const planMinutes = Math.ceil(WORDS_SECONDS / 60);
  const estimate = { ...ESTIMATE, extensions: [{ kind: 'words', seconds: WORDS_SECONDS, in_day: false }] };
  const session = {
    pace: 'normal',
    steps: [
      { kind: 'words', state: 'next', minutes: planMinutes, href: '/vocabulary/review?day=1', count: 22, new_left: 17, reviews: 5 },
      { kind: 'finish', state: 'todo', minutes: 0, href: '/fertig' },
    ],
    next_kind: 'words',
    minutes_left: planMinutes,
    done: false,
    tally: { scenes: 0, words: 0, exercises: 0 },
    more_words: 5,
    more_minutes: 2,
    more_href: '/vocabulary/review?more=5',
  };
  for (const language of ['de', 'en', 'fr']) {
    const card = extensionLabel(estimate, 'words', language).match(/(\d+)\s*(?:Min\.|min)/);
    const row = sessionRows(session, language)[0].meta.match(/(\d+)\s*(?:Min\.|min)/);
    assert.ok(card && row, `both print minutes (${language})`);
    assert.equal(card[1], row[1], `the card says ${card[1]}, the plan row ${row[1]} (${language})`);
  }
  // The chips beside the card read the same extension.
  assert.equal(extensionMinutes(estimate, 'words', 'de'), `≈ ${planMinutes} Min.`);
});

test('#470 · a planned estimate is whole minutes, rounded up, below a minute and a half too', () => {
  const short = { ...ESTIMATE, extensions: [{ kind: 'words', seconds: 40, in_day: false }] };
  assert.equal(extensionLabel(short, 'words', 'de'), '+ Wörter ≈ 1 Min.');
  assert.equal(coreEstimateLabel({ ...ESTIMATE, core_seconds: 361 }, null, 'en'), '7 min');
});
