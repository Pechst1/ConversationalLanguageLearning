// node --test lib/day-session.test.js
//
// Round 3 (owner, 2026-10-14): the day as one sequence — Szene, Wörter,
// Grammatik, Fertig — and the Tempo sheet's rows.

const assert = require('node:assert/strict');
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

const ds = require('./day-session.ts');
const dp = require('./day-plan.ts');

// The server's plan, its states in the day's order: [scene, grammar, words, finish]
// (owner, 1 Nov 2026: La Forge before the words; `day-order.test.js`).
function session(states, overrides = {}) {
  const [scene, grammar, words, finish] = states;
  return {
    pace: 'normal',
    steps: [
      { kind: 'scene', state: scene, minutes: scene === 'done' ? 0 : 8, href: null },
      { kind: 'grammar', state: grammar, minutes: grammar === 'done' ? 0 : 5, href: '/atelier?mode=forge&from=day', count: 12 },
      { kind: 'words', state: words, minutes: words === 'done' ? 0 : 8, href: '/vocabulary/review?day=1', count: 32, new_left: 20, reviews: 12 },
      { kind: 'finish', state: finish, minutes: 0, href: '/fertig' },
    ],
    next_kind: ['scene', 'grammar', 'words'].find((kind, index) => states[index] === 'next') ?? null,
    minutes_left: 21,
    done: finish === 'done',
    tally: { scenes: 1, words: 20, exercises: 12 },
    more_words: 5,
    more_minutes: 2,
    more_href: '/vocabulary/review?more=5',
    ...overrides,
  };
}

test('the programme is four rows with their minutes, in the learner’s language', () => {
  const rows = ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'de');
  assert.deepEqual(rows.map((row) => [row.label, row.meta]), [
    ['Szene', '8 Min.'],
    ['Grammatik', '5 Min.'],
    ['32 Wörter', '20 neu · 12 zum Wiederholen · 8 Min.'],
    ['Fertig', ''],
  ]);
  assert.deepEqual(rows.map((row) => row.shape), ['story', 'action', 'reward', 'done']);
  assert.equal(ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'fr')[2].label, '32 mots');
});

test('a news day opens with Le Papier', () => {
  const rows = ds.sessionRows(session(['next', 'todo', 'todo', 'todo']), 'de', { papier: true });
  assert.equal(rows[0].label, 'Le Papier');
});

test('a done step drops its minutes', () => {
  const rows = ds.sessionRows(session(['done', 'next', 'todo', 'todo']), 'de');
  assert.equal(rows[0].meta, '');
});

test('the journey card starts the scene; after it the one button names the next step', () => {
  assert.equal(ds.sessionNextAction(session(['next', 'todo', 'todo', 'todo']), 'de'), null);
  assert.deepEqual(ds.sessionNextAction(session(['done', 'next', 'todo', 'todo']), 'de'), {
    kind: 'grammar',
    label: 'Weiter: Grammatik',
    meta: '5 Min.',
    href: '/atelier?mode=forge&from=day',
  });
  assert.deepEqual(ds.sessionNextAction(session(['done', 'done', 'next', 'todo']), 'de'), {
    kind: 'words',
    label: 'Weiter: 32 Wörter',
    meta: '20 neu · 12 zum Wiederholen · 8 Min.',
    href: '/vocabulary/review?day=1',
  });
  assert.equal(ds.sessionNextAction(session(['done', 'next', 'todo', 'todo']), 'en').label, 'Next: grammar');
  assert.equal(ds.sessionNextAction(session(['done', 'done', 'done', 'done']), 'de'), null);
});

test('only a finished day offers five more words', () => {
  assert.equal(ds.sessionMore(session(['done', 'next', 'todo', 'todo']), 'de'), null);
  assert.deepEqual(ds.sessionMore(session(['done', 'done', 'done', 'done']), 'de'), {
    label: 'Noch 5 neue Wörter',
    meta: '2 Min.',
    href: '/vocabulary/review?more=5',
  });
});

// #783: «Noch 1 neue Wörter» on the words end screen. Every count in the day's
// copy says one word in the singular, in the three chrome languages.
test('one more word is one word, not «1 neue Wörter» (#783)', () => {
  const finished = (n) => session(['done', 'done', 'done', 'done'], { more_words: n, more_href: `/vocabulary/review?more=${n}` });
  const expected = {
    de: ['Noch 1 neues Wort', 'Noch 5 neue Wörter'],
    fr: ['Encore 1 nouveau mot', 'Encore 5 nouveaux mots'],
    en: ['1 more new word', '5 more new words'],
  };
  for (const [language, [one, five]] of Object.entries(expected)) {
    assert.equal(ds.sessionMore(finished(1), language).label, one, language);
    assert.equal(ds.sessionMore(finished(5), language).label, five, language);
  }
});

test('a deck of one word reads «1 Wort» on the row and the button (#783)', () => {
  const one = session(['done', 'done', 'next', 'todo']);
  one.steps[2] = { ...one.steps[2], count: 1, new_left: 1, reviews: 1 };
  const expected = {
    de: ['1 Wort', 'Weiter: 1 Wort', '1 neu · 1 zum Wiederholen · 8 Min.'],
    fr: ['1 mot', 'Suite : 1 mot', '1 nouveau · 1 à revoir · 8 min'],
    en: ['1 word', 'Next: 1 word', '1 new · 1 to review · 8 min'],
  };
  for (const [language, [row, button, meta]] of Object.entries(expected)) {
    assert.equal(ds.sessionRows(one, language)[2].label, row, language);
    const next = ds.sessionNextAction(one, language);
    assert.equal(next.label, button, language);
    assert.equal(next.meta, meta, language);
  }
  // Five stays plural.
  const five = session(['done', 'done', 'next', 'todo']);
  five.steps[2] = { ...five.steps[2], count: 5, new_left: 5, reviews: 5 };
  assert.equal(ds.sessionNextAction(five, 'de').label, 'Weiter: 5 Wörter');
  assert.equal(ds.sessionNextAction(five, 'fr').meta, '5 nouveaux · 5 à revoir · 8 min');
  assert.equal(ds.sessionRows(five, 'en')[2].label, '5 words');
});

test('a goal one week away reads «≈ 1 Woche» (#783)', () => {
  assert.equal(ds.etaLabel(1, 'de'), '≈ 1 Woche');
  assert.equal(ds.etaLabel(1, 'fr'), '≈ 1 semaine');
  assert.equal(ds.etaLabel(1, 'en'), '≈ 1 week');
  assert.equal(ds.etaLabel(5, 'de'), '≈ 5 Wochen');
  assert.equal(ds.etaLabel(5, 'fr'), '≈ 5 semaines');
  assert.equal(ds.etaLabel(5, 'en'), '≈ 5 weeks');
});

test('the mark’s four shapes are the four steps', () => {
  const mark = ds.sessionMarkState(session(['done', 'next', 'todo', 'todo']), 'de');
  // The mark's groups follow the step's kind: La Forge (respond) is active now.
  assert.deepEqual(mark.groups, { scene: 'done', recall: 'todo', respond: 'active', resolution: 'todo' });
  assert.equal(mark.done, 1);
  assert.equal(mark.total, 4);
});

test('the Tempo sheet says what each pace holds, costs and reaches', () => {
  const options = [
    { pace: 'ruhig', words: 10, rules_per_week: 3, exercises: 12, minutes_today: 18, minutes_week_8: 21, reviews_week_8: 28, goal_weeks: 15.1 },
    { pace: 'normal', words: 20, rules_per_week: 5, exercises: 12, minutes_today: 23, minutes_week_8: 28, reviews_week_8: 57, goal_weeks: 10.5 },
    { pace: 'schnell', words: 40, rules_per_week: 8, exercises: 17, minutes_today: 35, minutes_week_8: 43, reviews_week_8: 114, goal_weeks: 8.1 },
  ];
  const rows = ds.paceRows(options, 'A1.2', 'de');
  assert.deepEqual(rows.map((row) => row.name), ['Ruhig', 'Normal', 'Schnell']);
  assert.equal(rows[1].detail, '20 Wörter · 5 Regeln pro Woche');
  assert.equal(rows[1].minutes, '≈ 23 Min.');
  assert.equal(rows[0].goal, 'A1 in ≈ 3½ Monaten');
  assert.equal(rows[1].goal, 'A1 in ≈ 11 Wochen');
  assert.equal(rows[2].goal, 'A1 in ≈ 8 Wochen');
  assert.equal(ds.paceNote(options, 'de'), 'Wörter kommen zur Wiederholung zurück. Nach 8 Wochen dauert ein Tag etwa 3 bis 8 Min. länger.');
});

test('the scene’s ending hands on to La Forge, La Forge’s recap to the words, the words to Fertig', () => {
  const afterScene = dp.handOnAfterScene(session(['next', 'todo', 'todo', 'todo']), 'de');
  assert.equal(afterScene.label, 'Weiter: Grammatik');
  assert.equal(afterScene.href, '/atelier?mode=forge&from=day');
  // Words done first (from the Cahier, say): the scene still hands on to La Forge.
  assert.equal(dp.handOnAfterScene(session(['next', 'todo', 'done', 'todo']), 'de').label, 'Weiter: Grammatik');
  const afterGrammar = dp.handOnAfterGrammar(session(['done', 'next', 'todo', 'todo']), 'de');
  assert.deepEqual([afterGrammar.kind, afterGrammar.label], ['words', 'Weiter: 32 Wörter']);
  const finish = dp.handOnAfterWords(session(['done', 'done', 'next', 'todo']), 'de');
  assert.deepEqual([finish.kind, finish.label, finish.href], ['finish', 'Fertig für heute', '/fertig']);
  // La Forge skipped: the words' end sends the learner back to it, not to Fertig.
  assert.equal(dp.handOnAfterWords(session(['done', 'todo', 'next', 'todo']), 'de').kind, 'grammar');
});

test('#279 · a deck of new words and reviews names its two halves; one half alone needs no split', () => {
  const both = ds.sessionRows(session(['done', 'done', 'next', 'todo']), 'en')[2];
  assert.equal(both.label, '32 words');
  assert.equal(both.meta, '20 new · 12 to review · 8 min');
  const only = (words) => {
    const base = session(['done', 'done', 'next', 'todo']);
    base.steps[2] = { ...base.steps[2], ...words };
    return ds.sessionRows(base, 'fr')[2].meta;
  };
  assert.equal(only({ count: 12, new_left: 0, reviews: 12 }), '8 min');
  assert.equal(only({ count: 20, new_left: 20, reviews: 0 }), '8 min');
});

test('#396 · the day chip counts today only once the day is done, not at the first practice', () => {
  // The server counts today from the first practice: 19 -> 20 once La Forge is done.
  const words = session(['done', 'done', 'next', 'todo']);
  assert.deepEqual(ds.homeDayChip(20, true, words), { streak: 19, dayDone: false });
  // Nothing practised yet: the number is the morning's.
  assert.deepEqual(ds.homeDayChip(19, false, session(['next', 'todo', 'todo', 'todo'])), { streak: 19, dayDone: false });
  // Everything done: the day is done, and today is in the count.
  const done = session(['done', 'done', 'done', 'done']);
  assert.deepEqual(ds.homeDayChip(20, true, done), { streak: 20, dayDone: true });
  // A first day never shows less than nothing.
  assert.deepEqual(ds.homeDayChip(1, true, words), { streak: 0, dayDone: false });
  // No session today (no journey): the server's own flag stands.
  assert.deepEqual(ds.homeDayChip(20, true, null), { streak: 20, dayDone: true });
  assert.deepEqual(ds.homeDayChip(19, false, undefined), { streak: 19, dayDone: false });
});

test('#559 · the recap prints the streak Home prints, and the arrow only when the day moved it', () => {
  // Live 6 Nov: end sheet «26», Home chip «25». The server counted today at the séance's end.
  const words = session(['done', 'done', 'next', 'todo']);
  assert.deepEqual(ds.recapStreak(25, 26, words), { was: 25, now: 25 });
  assert.equal(ds.recapStreak(25, 26, words).now, ds.homeDayChip(26, true, words).streak);
  // The day is done: today is in the count, and the chain moved 25 -> 26.
  const done = session(['done', 'done', 'done', 'done']);
  assert.deepEqual(ds.recapStreak(25, 26, done), { was: 25, now: 26 });
  // Today was already counted before this séance (a second one): no arrow either way.
  assert.deepEqual(ds.recapStreak(26, 26, done), { was: 26, now: 26 });
  assert.deepEqual(ds.recapStreak(26, 26, words), { was: 25, now: 25 });
  // No journey today: the server's number stands.
  assert.deepEqual(ds.recapStreak(25, 26, null), { was: 25, now: 26 });
  // Nothing readable is zero, never NaN.
  assert.deepEqual(ds.recapStreak(undefined, undefined, null), { was: 0, now: 0 });
});

test('Phase 2 · Fertig says «2 Akte» on a day of acts, and the scene on a day of one', () => {
  assert.deepEqual(ds.tallyStory({ scenes: 1, words: 20, exercises: 12, acts: 2, story_words: 640 }, 'de'), { n: 2, label: 'Akte' });
  assert.deepEqual(ds.tallyStory({ scenes: 1, words: 20, exercises: 12, acts: 3, story_words: 1030 }, 'fr'), { n: 3, label: 'Actes' });
  assert.deepEqual(ds.tallyStory({ scenes: 1, words: 20, exercises: 12, acts: 1, story_words: 290 }, 'en'), { n: 1, label: 'Scene' });
  // An older server sends no acts: the tile is the scene, as it always was.
  assert.deepEqual(ds.tallyStory({ scenes: 1, words: 20, exercises: 12 }, 'de'), { n: 1, label: 'Szene' });
});

test('Phase 2 · under the tally, the story’s words read, in the learner’s own number format', () => {
  assert.equal(ds.storyReadLine({ scenes: 1, words: 20, exercises: 12, acts: 3, story_words: 1030 }, 'de'), '1.030 Wörter Geschichte gelesen');
  assert.equal(ds.storyReadLine({ scenes: 1, words: 20, exercises: 12, acts: 3, story_words: 1030 }, 'en'), '1,030 words of story read');
  assert.match(ds.storyReadLine({ scenes: 1, words: 20, exercises: 12, acts: 3, story_words: 1030 }, 'fr'), /^1\s030 mots d’histoire lus$/u);
  assert.equal(ds.storyReadLine({ scenes: 1, words: 20, exercises: 12, acts: 1, story_words: 290 }, 'de'), '290 Wörter Geschichte gelesen');
  // A day that read none of the story, or an older server, prints no line.
  assert.equal(ds.storyReadLine({ scenes: 0, words: 20, exercises: 12, acts: 0, story_words: 0 }, 'de'), null);
  assert.equal(ds.storyReadLine({ scenes: 1, words: 20, exercises: 12 }, 'de'), null);
});
