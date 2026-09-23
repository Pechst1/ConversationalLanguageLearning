// WP-L6 — the rhythm and the vocabulary pace, as Réglages shows them.
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const {
  RHYTHMS,
  DEFAULT_RHYTHM,
  rhythmForMinutes,
  reviewLoad,
  formatReviewLoad,
  clampNewWords,
  isRhythm,
} = require('./rhythm.ts');

test('four rhythms, Régulier by default', () => {
  assert.deepEqual(RHYTHMS.map((r) => [r.id, r.minutes]), [
    ['leger', 5], ['regulier', 10], ['soutenu', 20], ['intensif', 30],
  ]);
  assert.equal(DEFAULT_RHYTHM, 'regulier');
  assert.ok(isRhythm('soutenu'));
  assert.ok(!isRhythm('turbo'));
});

test('stored minutes map onto the same rhythm as on the server', () => {
  const cases = [[null, 'regulier'], [5, 'leger'], [7, 'leger'], [8, 'regulier'], [14, 'regulier'],
    [15, 'soutenu'], [25, 'soutenu'], [30, 'intensif'], [60, 'intensif']];
  for (const [minutes, rhythm] of cases) assert.equal(rhythmForMinutes(minutes), rhythm, String(minutes));
});

test('the review load is an estimate of 8–10 reviews per new word a day', () => {
  assert.deepEqual(reviewLoad(20), { low: 160, high: 200, minLow: 16, minHigh: 20 });
  assert.deepEqual(reviewLoad(4), { low: 32, high: 40, minLow: 3, minHigh: 4 });
  assert.equal(
    formatReviewLoad('about {low}–{high} (≈ {minLow}–{minHigh} min)', 10),
    'about 80–100 (≈ 8–10 min)',
  );
});

test('the pace stays inside 1–50', () => {
  assert.equal(clampNewWords(0), 1);
  assert.equal(clampNewWords(80), 50);
  assert.equal(clampNewWords(Number.NaN), 10);
});
