// node --test components/atelier-v2/band-check/band-check.test.js
//
// SPEED-1 «Vérification du lexique»: the check's state logic and what the
// screen says.
//
//   1. sequencing — uncredited sub-bands from the lowest upward; after a pass
//      the next one up, after a miss the next one up offered «anyway»;
//   2. answering — one tap records and advances; «je ne sais pas» is a real
//      answer, sent as null, and never shown as a failure; undo; keyboard;
//   3. scoring display — the result card's numbers and words, in en/de/fr;
//   4. the copy tables are complete and fill the same placeholders;
//   5. the entry points render only while an uncredited sub-band remains.

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

const realConsoleError = console.error;
console.error = (...args) => {
  const first = String(args[0] || '');
  if (first.includes('non-boolean attribute') || first.includes('useLayoutEffect')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const S = require('./band-check-state.ts');
const { bandCheckCopy, bandCheckFill, passedTitle } = require('./band-check-copy.ts');
const { BandCheckView } = require('./BandCheck.tsx');
const { BandCheckEntryView, bandCheckHref } = require('./BandCheckEntry.tsx');

const h = React.createElement;

const BANDS = [
  { sub_band: 'A2.1', words: 240, credited: false },
  { sub_band: 'A1.1', words: 180, credited: true },
  { sub_band: 'A1.2', words: 210, credited: false },
];

const ITEMS = [
  { id: 'fenêtre', fr: 'la fenêtre', options: ['the door', 'the window', 'the wall', 'the floor'] },
  { id: 'oublier', fr: 'oublier', options: ['to forget', 'to borrow', 'to follow', 'to offer'] },
  { id: 'lent', fr: 'lent', options: ['light', 'long', 'slow', 'late'] },
];

// --- sequencing ------------------------------------------------------------

test('the uncredited sub-bands are offered from the lowest upward', () => {
  assert.deepEqual(S.uncreditedBands(BANDS).map((row) => row.sub_band), ['A1.2', 'A2.1']);
  assert.equal(S.nextBand(BANDS), 'A1.2');
  assert.equal(S.nextBand(BANDS, 'A1.2'), 'A2.1');
  assert.equal(S.nextBand(BANDS, 'A2.1'), null);
  assert.equal(S.hasUncreditedBand(BANDS), true);
  assert.equal(S.hasUncreditedBand(BANDS.map((row) => ({ ...row, credited: true }))), false);
  assert.equal(S.hasUncreditedBand([]), false);
  assert.equal(S.hasUncreditedBand(null), false);
});

test('a band just checked is never offered again straight away', () => {
  const credited = S.markCredited(BANDS, 'A1.2');
  assert.equal(credited.find((row) => row.sub_band === 'A1.2').credited, true);
  assert.equal(S.nextBand(credited), 'A2.1');
  // after a miss the band stays uncredited, but «next» still moves up
  assert.equal(S.nextBand(BANDS, 'A1.2'), 'A2.1');
});

// --- answering --------------------------------------------------------------

test('one tap records the answer and advances; the run completes on the last item', () => {
  let run = S.startRun('A1.2', ITEMS, 0.9);
  assert.equal(S.currentItem(run).id, 'fenêtre');
  run = S.answer(run, 1);
  assert.equal(S.currentItem(run).id, 'oublier');
  assert.deepEqual(S.progressOf(run), { done: 1, total: 3 });
  run = S.answer(run, 0);
  assert.equal(S.isComplete(run), false);
  run = S.answer(run, 2);
  assert.equal(S.isComplete(run), true);
  assert.equal(S.currentItem(run), null);
  // a complete run does not change
  assert.equal(S.answer(run, 0), run);
});

test('«je ne sais pas» is a real answer: recorded as null, advancing like a choice', () => {
  let run = S.startRun('A1.2', ITEMS);
  run = S.answer(run, null);
  assert.equal(run.index, 1);
  assert.ok('fenêtre' in run.answers);
  assert.equal(run.answers['fenêtre'], null);
  run = S.answer(S.answer(run, 0), null);
  assert.deepEqual(S.answersPayload(run), { fenêtre: null, oublier: 0, lent: null });
});

test('the payload names every item, an unanswered one as «je ne sais pas»', () => {
  const run = S.answer(S.startRun('A1.2', ITEMS), 1);
  assert.deepEqual(S.answersPayload(run), { fenêtre: 1, oublier: null, lent: null });
});

test('an out-of-range choice is ignored; undo steps back and forgets the answer', () => {
  let run = S.startRun('A1.2', ITEMS);
  assert.equal(S.answer(run, 4), run);
  assert.equal(S.answer(run, -1), run);
  assert.equal(S.answer(run, 1.5), run);
  assert.equal(S.undo(run), run);
  run = S.answer(S.answer(run, 1), 2);
  run = S.undo(run);
  assert.equal(run.index, 1);
  assert.deepEqual(run.answers, { fenêtre: 1 });
});

test('the keyboard: 1–4 choose, 0 / ? / n say «je ne sais pas», Backspace undoes', () => {
  assert.deepEqual(S.keyToChoice('1', 4), { kind: 'choice', choice: 0 });
  assert.deepEqual(S.keyToChoice('4', 4), { kind: 'choice', choice: 3 });
  assert.equal(S.keyToChoice('5', 4), null);
  for (const key of ['0', '?', 'n', 'N']) assert.deepEqual(S.keyToChoice(key, 4), { kind: 'choice', choice: null });
  assert.deepEqual(S.keyToChoice('Backspace', 4), { kind: 'undo' });
  assert.equal(S.keyToChoice('a', 4), null);
  assert.equal(S.keyToChoice('Enter', 4), null);
});

// --- scoring display --------------------------------------------------------

test('a pass names the credited words and offers the next band up', () => {
  const summary = S.summarize(
    { sub_band: 'A1.2', correct: 23, total: 24, passed: true, credited_words: 196, missed: ['lent'] },
    BANDS,
    0.9,
  );
  assert.deepEqual(summary, {
    tone: 'passed',
    subBand: 'A1.2',
    correct: 23,
    total: 24,
    needed: 22,
    credited: 196,
    missed: 1,
    next: 'A2.1',
  });
});

test('a miss credits nothing, says how many were needed, and still offers the next band', () => {
  const summary = S.summarize(
    { sub_band: 'A1.2', correct: 17, total: 24, passed: false, credited_words: 0, missed: Array(7).fill('x') },
    BANDS,
    0.9,
  );
  assert.equal(summary.tone, 'failed');
  assert.equal(summary.credited, 0);
  assert.equal(summary.needed, 22);
  assert.equal(summary.next, 'A2.1');
  assert.equal(S.neededToPass(24, 0.9), 22);
  assert.equal(S.neededToPass(10, 0.9), 9);
  assert.equal(S.neededToPass(20, 0.9), 18);
});

test('the top band of the learner\'s range offers no next check', () => {
  const summary = S.summarize(
    { sub_band: 'A2.1', correct: 24, total: 24, passed: true, credited_words: 3, missed: [] },
    BANDS,
  );
  assert.equal(summary.next, null);
});

test('the passed headline: plural, singular, and nothing new to card', () => {
  const en = bandCheckCopy('en');
  assert.equal(passedTitle(en, 196, 'A1.2'), '196 words already known');
  assert.equal(passedTitle(en, 1, 'A1.2'), '1 word already known');
  assert.equal(passedTitle(en, 0, 'A1.2'), 'Level A1.2 confirmed');
  assert.equal(passedTitle(bandCheckCopy('fr'), 196, 'A1.2'), '196 mots déjà acquis');
  assert.equal(passedTitle(bandCheckCopy('de'), 196, 'A1.2'), '196 Wörter schon bekannt');
});

// --- copy -------------------------------------------------------------------

test('the three tables are complete, non-empty, and fill the same placeholders', () => {
  const fr = bandCheckCopy('fr');
  const holes = (value) => (value.match(/\{\w+\}/g) || []).sort().join(',');
  for (const language of ['en', 'de']) {
    const table = bandCheckCopy(language);
    assert.deepEqual(Object.keys(table).sort(), Object.keys(fr).sort());
    for (const [key, value] of Object.entries(table)) {
      assert.ok(value.trim(), `${language}.${key} is empty`);
      assert.equal(holes(value), holes(fr[key]), `${language}.${key}`);
      assert.notEqual(value, value.toUpperCase(), `${language}.${key} is shouted`);
    }
  }
  assert.equal(bandCheckFill('{n} / {total}', { n: 7, total: 24 }), '7 / 24');
});

test('no copy shames «je ne sais pas» or calls a miss a failure', () => {
  for (const language of ['en', 'de', 'fr']) {
    const text = Object.values(bandCheckCopy(language)).join(' ').toLowerCase();
    for (const word of ['fail', 'wrong', 'oops', 'échec', 'raté', 'falsch', 'leider']) {
      assert.ok(!text.includes(word), `${language}: ${word}`);
    }
  }
});

// --- the screen -------------------------------------------------------------

const noop = () => {};
function view(state, language = 'en', origin = 'lexique') {
  return renderToStaticMarkup(
    h(BandCheckView, {
      state,
      language,
      origin,
      keyboard: false,
      onBegin: noop,
      onChoose: noop,
      onUndo: noop,
      onResend: noop,
      onRetryOpen: noop,
      onCheckBand: noop,
      onLeave: noop,
    }),
  );
}

test('a question shows the French word, four meanings in the learner\'s language, and «I don’t know»', () => {
  const run = S.answer(S.startRun('A1.2', ITEMS), 0);
  const html = view({ phase: 'question', run });
  assert.match(html, /<h1[^>]*lang="fr"[^>]*>oublier<\/h1>/);
  for (const option of ITEMS[1].options) assert.ok(html.includes(option), option);
  assert.equal((html.match(/role="radio"/g) || []).length, 4);
  assert.ok(html.includes('I don’t know'));
  assert.ok(html.includes('1 / 3'));
  assert.ok(html.includes('Previous word'));
  // nothing is marked right or wrong during the run
  assert.ok(!html.includes('data-state="correct"') && !html.includes('data-state="wrong"'));
});

test('the result card says the score honestly, in the learner\'s language', () => {
  const passed = S.summarize(
    { sub_band: 'A1.2', correct: 23, total: 24, passed: true, credited_words: 196, missed: ['lent'] },
    BANDS,
  );
  const html = view({ phase: 'result', summary: passed }, 'de');
  assert.ok(html.includes('196 Wörter schon bekannt'));
  assert.ok(html.includes('kurzen Kontrolle'));
  assert.ok(html.includes('23 von 24 erkannt.'));
  assert.ok(html.includes('A2.1 prüfen'));

  const failed = S.summarize(
    { sub_band: 'A1.2', correct: 17, total: 24, passed: false, credited_words: 0, missed: Array(7).fill('x') },
    BANDS,
  );
  const fhtml = view({ phase: 'result', summary: failed }, 'en', 'placement');
  assert.ok(fhtml.includes('17 of 24 recognised'));
  assert.ok(fhtml.includes('it needed 22'));
  assert.ok(fhtml.includes('normal flow'));
  assert.ok(fhtml.includes('Check A2.1 anyway'));
  assert.ok(fhtml.includes('Continue'));
  // one primary per state
  assert.equal((fhtml.match(/av2-btn--primary/g) || []).length, 1);
});

test('the intro names the item count, the pass share and the levels left', () => {
  const html = view({ phase: 'intro', run: S.startRun('A1.2', ITEMS, 0.9), bands: BANDS }, 'fr');
  assert.ok(html.includes('3 mots du niveau A1.2'));
  assert.ok(html.includes('90 %'));
  assert.ok(html.includes('Niveaux à vérifier'));
});

test('the entry renders only while an uncredited sub-band remains', () => {
  const html = renderToStaticMarkup(h(BandCheckEntryView, { origin: 'lexique', language: 'en', bands: BANDS }));
  assert.ok(html.includes('Check my vocabulary (2 min per level)'));
  assert.ok(html.includes('A1.2 · A2.1'));
  assert.ok(html.includes('href="/vocabulary/verification?from=lexique"'));
  const none = renderToStaticMarkup(
    h(BandCheckEntryView, { origin: 'placement', language: 'en', bands: BANDS.map((row) => ({ ...row, credited: true })) }),
  );
  assert.equal(none, '');
  assert.equal(bandCheckHref('placement', 'A2.1'), '/vocabulary/verification?from=placement&band=A2.1');
});
