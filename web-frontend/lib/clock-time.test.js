// #316 — Courrier message times are the learner's clock, not the server's.
// TZ is set before any Date is built so the device is «in Berlin».
process.env.TZ = 'Europe/Berlin';

const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');

test('a UTC stamp prints in the device time zone (02:06Z is 04 h 06 in Berlin)', () => {
  const { clockTime } = require('./clock-time.ts');
  assert.equal(clockTime('2026-10-24T02:06:00Z'), '04 h 06');
  assert.equal(clockTime('2026-10-24T02:06:00+00:00'), '04 h 06');
  assert.equal(clockTime('2026-10-24T04:06:00+02:00'), '04 h 06');
});

test('a zoneless stamp is UTC, not the device clock', () => {
  const { clockTime } = require('./clock-time.ts');
  assert.equal(clockTime('2026-10-24T02:06:00'), '04 h 06');
  assert.equal(clockTime('2026-10-24T02:06:00.123456'), '04 h 06');
  assert.equal(clockTime('2026-10-24 02:07:00'), '04 h 07');
});

test('winter time follows the device too', () => {
  const { clockTime } = require('./clock-time.ts');
  assert.equal(clockTime('2026-12-24T02:06:00'), '03 h 06');
});

test('no stamp is never invented', () => {
  const { clockTime } = require('./clock-time.ts');
  assert.equal(clockTime(null), undefined);
  assert.equal(clockTime(''), undefined);
  assert.equal(clockTime('not a date'), undefined);
});

test('the Courrier slip uses it', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const page = fs.readFileSync(path.join(__dirname, '..', 'pages', 'missions.tsx'), 'utf8');
  assert.match(page, /clockTime\(turn\?\.created_at/);
  assert.doesNotMatch(page, /date\.getHours\(\)/);
});
