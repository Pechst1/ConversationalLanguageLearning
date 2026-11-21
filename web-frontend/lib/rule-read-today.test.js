// R2 item 1: the day's rule card read → the Forge from the day does not open on it again.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
require('../node_modules/sucrase/register/ts');

function memoryStore() {
  const data = new Map();
  return { getItem: (k) => (data.has(k) ? data.get(k) : null), setItem: (k, v) => data.set(k, String(v)) };
}

test('a card read today is remembered for that rule, today only', () => {
  const { markRuleRead, ruleReadToday } = require('./rule-read-today.ts');
  const store = memoryStore();
  const day = new Date(2026, 10, 18, 9);
  assert.equal(ruleReadToday(7, day, store), false);
  markRuleRead(7, day, store);
  assert.equal(ruleReadToday(7, day, store), true);
  assert.equal(ruleReadToday(8, day, store), false, 'another rule');
  assert.equal(ruleReadToday(7, new Date(2026, 10, 19, 9), store), false, 'tomorrow');
  assert.equal(ruleReadToday(7, day, null), false, 'no storage: the Forge shows its card');
});

test('the journey marks the card; the Forge from the day reads it', () => {
  const steps = fs.readFileSync(path.join(__dirname, '../components/atelier-v2/journey/JourneySteps.tsx'), 'utf8');
  assert.match(steps, /markRuleRead\(step\.prompt\.concept_id\)/);
  const atelier = fs.readFileSync(path.join(__dirname, '../pages/atelier.tsx'), 'utf8');
  assert.match(atelier, /ruleReadToday\(/);
});
