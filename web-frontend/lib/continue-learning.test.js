// node --test lib/continue-learning.test.js
//
// CONTINUE (owner, 2026-10-12): Home's one button — the story, La Forge, the
// words, then more — and the target it moves towards.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const cont = require('./continue-learning.ts');

const FORGE = { href: '/atelier?mode=forge&concept=7', folded: false, blocksToday: 0 };
const base = { storyDone: true, forge: FORGE, wordsDue: 12, wordsDoneToday: false, firstDay: false };

// #152: the order is the server plan's (scene, words, grammar), not the old one.
test('after the story the button goes to the words, then La Forge, then more', () => {
  let plan = cont.continuePlan(base);
  assert.deepEqual(plan.done, ['story']);
  assert.equal(plan.next, 'words');
  assert.equal(plan.href, '/vocabulary/review');

  plan = cont.continuePlan({ ...base, wordsDoneToday: true });
  assert.equal(plan.next, 'forge');
  assert.equal(plan.href, FORGE.href);

  plan = cont.continuePlan({ ...base, forge: { ...FORGE, blocksToday: 1 }, wordsDoneToday: true });
  assert.deepEqual(plan.done, ['story', 'words', 'forge']);
  assert.equal(plan.next, 'more');
  assert.equal(plan.href, FORGE.href, 'more is another La Forge round');
});

test('the story comes first, and the journey card opens it', () => {
  const plan = cont.continuePlan({ ...base, storyDone: false });
  assert.equal(plan.next, 'story');
  assert.equal(plan.href, null);
});

test('a folded forge is part of the story; no words due is words done, except on the first day', () => {
  const folded = cont.continuePlan({ ...base, forge: { ...FORGE, folded: true }, wordsDue: 0 });
  assert.deepEqual(folded.done, ['story', 'words', 'forge']);
  assert.equal(folded.next, 'more');

  const firstDay = cont.continuePlan({ ...base, firstDay: true, wordsDue: 0, routeDone: ['story', 'forge'] });
  assert.equal(firstDay.next, 'words', 'the first day has new words to learn');
  const ticked = cont.continuePlan({ ...base, firstDay: true, wordsDue: 0, routeDone: ['story', 'forge', 'words'] });
  assert.equal(ticked.next, 'more');
});

test('without a forge entry the practice loop stands in', () => {
  const plan = cont.continuePlan({ ...base, forge: null, wordsDoneToday: true, practiceHref: '/atelier?mode=practice&concept=3' });
  assert.equal(plan.next, 'forge');
  assert.equal(plan.href, '/atelier?mode=practice&concept=3');
  const none = cont.continuePlan({ ...base, forge: null, wordsDoneToday: true });
  assert.equal(none.next, 'more');
  assert.equal(none.href, null);
});

test('the words are ticked on the device for today only', () => {
  const map = new Map();
  const store = { getItem: (k) => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)) };
  assert.equal(cont.wordsDoneToday(store, '2026-10-12'), false);
  cont.markWordsDoneToday(store, '2026-10-12');
  assert.equal(cont.wordsDoneToday(store, '2026-10-12'), true);
  assert.equal(cont.wordsDoneToday(store, '2026-10-13'), false);
  assert.equal(cont.wordsDoneToday(null, '2026-10-12'), false);
});

test('the target names the next band, what is missing and when', () => {
  const cefr = {
    next_level: 'A1.2',
    coverage: { band: 'A1.1', percent: 42.4, words: { known: 60, required: 200 }, units: { held: 2, required: 6 } },
    forecast: { target: 'A1.2', projected_dates: ['2026-11-20', '2026-12-28'], capped: false },
  };
  const view = cont.targetView(cefr, 'de');
  assert.deepEqual(view, { band: 'A1.2', percent: 42, wordsLeft: 140, rulesLeft: 4, when: 'November–Dezember' });
  const lines = cont.targetLines(view, 'de');
  assert.equal(lines.goal, 'Ziel A1.2: noch 140 Wörter und 4 Regeln');
  assert.equal(lines.when, 'bei deinem Tempo etwa im November–Dezember');
  assert.equal(cont.moreHint(view, 'de'), 'Noch eine Runde La Forge bringt dich schneller zu A1.2.');
  assert.equal(cont.targetView({ ...cefr, coverage: null }, 'de'), null);
  const capped = cont.targetView({ ...cefr, forecast: { ...cefr.forecast, capped: true } }, 'en');
  assert.equal(capped.when, null, 'a capped forecast is no date');
  for (const language of ['de', 'en', 'fr']) {
    const copy = cont.continueCopy(language);
    for (const key of Object.keys(copy)) assert.ok(copy[key], `${language}.${key}`);
  }
  assert.doesNotMatch(JSON.stringify(cont.continueCopy('de')), /\bSie\b|\bIhre?\b/);
});

test('Home draws the route every day once the story is completed, and no chip doubles it', () => {
  const source = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(source, /const storyCompleted = journey\.phase\.kind === 'finished' && journey\.journey\?\.status === 'completed'/);
  // Round 3: with the day as one sequence, its programme replaces the route.
  assert.match(source, /\{continueRoute && !journey\.envelope\?\.session && \(\s*\/\/ CONTINUE/);
  assert.match(source, /vocabularyReviewDue > 0 && !afterDayRoute/);
});
