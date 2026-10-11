// WP-S8 — the Dossier's measured line: «Your rules: n held, median x days to hold».
// Hidden under three held rules; measured, never promised; en/de/fr.
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

const { rulesSpeedSentence, RULES_SPEED_MIN_HELD } = require('./dossier-state.ts');

const level = (speed) => ({ available: true, estimate: 'A1.2', rules_speed: speed });

test('hidden under three held rules, or without the section', () => {
  assert.equal(RULES_SPEED_MIN_HELD, 3);
  assert.equal(rulesSpeedSentence(level({ held: 0, median_days_to_held: null, show: false }), 'en'), null);
  assert.equal(rulesSpeedSentence(level({ held: 2, median_days_to_held: 15, show: false }), 'en'), null);
  // Even if the server said show, fewer than three held rules stay silent.
  assert.equal(rulesSpeedSentence(level({ held: 2, median_days_to_held: 15, show: true }), 'en'), null);
  assert.equal(rulesSpeedSentence(level(undefined), 'en'), null);
  assert.equal(rulesSpeedSentence(null, 'en'), null);
});

test('shown from three held rules, in the chrome language', () => {
  const speed = { held: 3, held_by_practice: 3, median_days_to_held: 17, show: true, minimum: 3 };
  assert.equal(
    rulesSpeedSentence(level(speed), 'en'),
    'Your rules: 3 held, a median of 17 days to hold one. Measured on your own practice.',
  );
  assert.equal(
    rulesSpeedSentence(level(speed), 'fr'),
    'Vos règles : 3 tenues, 17 jours en médiane pour en tenir une. Mesuré sur votre propre pratique.',
  );
  assert.equal(
    rulesSpeedSentence(level(speed), 'de'),
    'Ihre Regeln: 3 sitzen, im Median 17 Tage bis eine sitzt. Gemessen an Ihrer eigenen Übung.',
  );
  assert.match(rulesSpeedSentence(level({ ...speed, median_days_to_held: 1 }), 'en'), /a median of 1 day to/);
});

test('all held by test-out: the count only, never an invented median', () => {
  const speed = { held: 4, held_by_practice: 0, median_days_to_held: null, show: true };
  assert.equal(rulesSpeedSentence(level(speed), 'en'), 'Your rules: 4 held. Measured on your own practice.');
});

test('the line is measured, never a promise, and the screen renders it', () => {
  for (const language of ['en', 'fr', 'de']) {
    const line = rulesSpeedSentence(level({ held: 5, median_days_to_held: 20, show: true }), language);
    assert.doesNotMatch(line, /will|guarantee|garanti|werden Sie|vous allez/i);
  }
  const screen = fs.readFileSync(path.join(HERE, 'DossierScreen.tsx'), 'utf8');
  assert.match(screen, /rulesSpeedSentence\(/);
});
