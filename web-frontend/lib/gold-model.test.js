// Package O-2 — l'or on screen: what the counter, the grain and the day's seal read.
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const {
  grainBetween,
  rimFraction,
  tirageLine,
  todayNote,
  entryLine,
  voidLine,
  entriesByDay,
  previousWeek,
  isoWeekOf,
  GOLD_REMEMBERED_FR,
} = require('./gold-model.ts');
const { isGoldAnswerRequest } = require('./gold-events.ts');

const entry = (over = {}) => ({
  id: 'e1', amount: 2, state: 'settled', entry_kind: 'earn', source_kind: 'word_card', category: 'typed',
  reason_fr: 'Rappel écrit', subject: null, delayed_recall: false, plafond_cut: false, local_date: '2026-11-03',
  ...over,
});

const view = (today = {}, week = {}, entries = []) => ({
  visible: true,
  balance: 40,
  today: {
    local_date: '2026-11-03', settled: 12, earn_settled: 12, pending: 0, earned_before_plafond: 12,
    plafond: 'open', plafond_full_rate_up_to: 90, plafond_stops_at: 150, rhythm: 'regulier', mark: 20, pleine: false,
    ...today,
  },
  week: { week_id: '2026-W45', settled: 40, journees_pleines: 3, journees_pleines_goal: 5, days: [], ...week },
  entries,
});

test('a grain is the entries the counter had not seen, never the first read', () => {
  const seen = new Set(['e1']);
  const next = view({}, {}, [entry({ id: 'e2', amount: 4, delayed_recall: true }), entry({ id: 'e1' })]);
  assert.deepEqual(grainBetween(seen, next, 7), { id: 7, amount: 4, delayed: true, pending: false });
  assert.equal(grainBetween(new Set(['e1', 'e2']), next, 8), null);
  assert.equal(grainBetween(seen, { visible: false }, 9), null);
});

test('a pulped or empty entry lifts no square; pending gold lifts a dashed one', () => {
  const seen = new Set();
  assert.equal(grainBetween(seen, view({}, {}, [entry({ state: 'void' }), entry({ id: 'z', amount: 0 })]), 1), null);
  assert.equal(grainBetween(seen, view({}, {}, [entry({ state: 'pending', amount: 5 })]), 2).pending, true);
});

test('the rim gilds toward the mark and stops there', () => {
  assert.equal(rimFraction(view({ earn_settled: 10, mark: 20 })), 0.5);
  assert.equal(rimFraction(view({ earn_settled: 50, mark: 20 })), 1);
  assert.equal(rimFraction(null), 0);
});

test('le tirage du jour says the day and the week', () => {
  assert.equal(tirageLine(view()), 'Or +12 · 12 / 20 vers la journée pleine');
  assert.equal(
    tirageLine(view({ settled: 48, earn_settled: 38, pleine: true }, { journees_pleines: 4 })),
    'Or +48 · Journée pleine (4 / 5)',
  );
  assert.equal(tirageLine({ visible: false }), null);
});

test('the pill notes the plafond and gold still à l’épreuve', () => {
  assert.equal(todayNote(view()), null);
  assert.equal(todayNote(view({ pending: 5 })), '5 à l’épreuve');
  assert.equal(todayNote(view({ plafond: 'half' })), 'Plafond : demi-tarif');
  assert.equal(todayNote(view({ plafond: 'closed' })), 'Plafond du jour atteint');
});

test('«D’où vient ton or» names the word and the reason, and why a leaf was pulped', () => {
  assert.equal(entryLine(entry({ subject: 'la clé', reason_fr: 'Rappel écrit · rappel différé ×2' })),
    '«\u202fla clé\u202f» · Rappel écrit · rappel différé ×2');
  assert.equal(voidLine(entry()), null);
  assert.equal(voidLine(entry({ state: 'void', void_reason: 'not_yet' })), 'pas encore');
  assert.equal(voidLine(entry({ state: 'void', void_reason: 'injection' })), 'pilonné');
  const days = entriesByDay([entry({ id: 'a' }), entry({ id: 'b' }), entry({ id: 'c', local_date: '2026-11-02' })]);
  assert.deepEqual(days.map((d) => [d.day, d.entries.length]), [['2026-11-03', 2], ['2026-11-02', 1]]);
});

test('the week before, across a year', () => {
  assert.equal(previousWeek('2026-W45'), '2026-W44');
  assert.equal(previousWeek('2026-W01'), '2025-W52');
  assert.equal(previousWeek('2027-W01'), '2026-W53');
  assert.equal(previousWeek('nope'), null);
  assert.equal(isoWeekOf(new Date(Date.UTC(2026, 10, 2))), '2026-W45');
  assert.equal(isoWeekOf(new Date(Date.UTC(2027, 0, 1))), '2026-W53');
});

test('only an answer route reads the ledger again', () => {
  assert.ok(isGoldAnswerRequest('post', '/anki/review'));
  assert.ok(isGoldAnswerRequest('POST', '/daily-journeys/j1/steps/s1/attempts'));
  assert.ok(isGoldAnswerRequest('post', '/atelier/sessions/abc/attempts'));
  assert.ok(isGoldAnswerRequest('post', '/missions/m1/complete'));
  assert.ok(!isGoldAnswerRequest('get', '/anki/review'));
  assert.ok(!isGoldAnswerRequest('post', '/daily-journeys/j1/steps/s1/help'));
  assert.ok(!isGoldAnswerRequest('post', '/analytics/client-error'));
});

test('the ×2 line is the spec’s', () => {
  assert.equal(GOLD_REMEMBERED_FR, 'Tu t’en souvenais.');
});
