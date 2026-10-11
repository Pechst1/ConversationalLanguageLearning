// node --test components/atelier-v2/band-check/band-check.test.js
//
// SPEED-1 «Vérification du lexique»: the check's state logic and what the
// screen says.
//
//   1. sequencing (WP-127, top-down) — the highest uncredited band first; a
//      pass stops the ladder, a miss steps down; a visit is two checks;
//   2. answering — one tap records and advances; «je ne sais pas» is a real
//      answer, sent as null, and never shown as a failure; undo; keyboard;
//   3. scoring display — the result card's numbers and words, in en/de/fr;
//   4. the copy tables are complete and fill the same placeholders;
//   5. the entry points render only while the ladder has a band to check now;
//   6. stop and resume: a stopped run comes back on the same words (attempt id).

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

test('top-down: the highest uncredited band is checked first', () => {
  assert.deepEqual(S.uncreditedBands(BANDS).map((row) => row.sub_band), ['A2.1', 'A1.2']);
  assert.equal(S.nextBand(BANDS), 'A2.1');
  assert.equal(S.hasUncreditedBand(BANDS), true);
  assert.equal(S.hasUncreditedBand(BANDS.map((row) => ({ ...row, credited: true }))), false);
  assert.equal(S.hasUncreditedBand([]), false);
  assert.equal(S.hasUncreditedBand(null), false);
});

test('a miss steps down one band; a pass stops the ladder', () => {
  const missed = S.markMissed(BANDS, 'A2.1');
  assert.equal(missed.find((row) => row.sub_band === 'A2.1').missed, true);
  assert.equal(S.nextBand(missed), 'A1.2');
  assert.equal(S.nextBand(BANDS, 'A2.1'), 'A1.2');
  // A pass at A1.2 after the miss: nothing above the floor is left unmissed.
  assert.equal(S.nextBand(S.markCredited(missed, 'A1.2')), null);
  // A pass at the top stops everything below it.
  assert.equal(S.nextBand(S.markCredited(BANDS, 'A2.1')), null);
  assert.equal(S.MAX_CHECKS_PER_VISIT, 2);
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

const PASS = {
  sub_band: 'A2.1', correct: 23, total: 24, passed: true, credited_words: 420, credited_sampled: 22,
  credited_inferred: 398, inferred_bands: ['A1.2'], missed: ['lent'], pass_correct: 21,
  ladder_status: 'done', next: null,
};
const MISS = {
  sub_band: 'A2.1', correct: 17, total: 24, passed: false, credited_words: 0, credited_sampled: 0,
  credited_inferred: 0, inferred_bands: [], missed: Array(7).fill('x'), pass_correct: 21,
  ladder_status: 'open', next: 'A1.2',
};

test('a pass separates what was recognised on the check from what was inferred, and stops', () => {
  const summary = S.summarize(PASS, BANDS);
  assert.deepEqual(summary, {
    tone: 'passed',
    subBand: 'A2.1',
    correct: 23,
    total: 24,
    needed: 21,
    credited: 420,
    sampled: 22,
    inferred: 398,
    inferredBands: ['A1.2'],
    missed: 1,
    next: null,
    ladder: 'done',
    resumeBand: null,
  });
});

test('a miss credits nothing, says how many were needed, and steps down', () => {
  const summary = S.summarize(MISS, BANDS);
  assert.equal(summary.tone, 'failed');
  assert.equal(summary.credited, 0);
  assert.equal(summary.inferred, 0);
  assert.equal(summary.needed, 21);
  assert.equal(summary.next, 'A1.2');
  assert.equal(summary.ladder, 'open');
  assert.equal(S.neededToPass(24), 21);
  assert.equal(S.neededToPass(24, 0.9), 22);
});

test('the second miss of a visit pauses the ladder: no third check, a band to resume with', () => {
  const summary = S.summarize({ ...MISS, sub_band: 'A1.2', ladder_status: 'paused', next: null, resume_band: 'A1.1' }, BANDS);
  assert.equal(summary.next, null);
  assert.equal(summary.ladder, 'paused');
  assert.equal(summary.resumeBand, 'A1.1');
});

test('an older server without a ladder: the same rule, computed here', () => {
  const legacy = { sub_band: 'A2.1', correct: 17, total: 24, passed: false, credited_words: 0, missed: ['x'] };
  assert.equal(S.summarize(legacy, BANDS, 0.9).next, 'A1.2');
  assert.equal(S.summarize({ ...legacy, passed: true, correct: 24 }, BANDS, 0.9).next, null);
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
    for (const word of ['fail', 'wrong', 'oops', 'échec', 'raté', 'falsch', 'leider', 'c1+']) {
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

test('the result card says the score honestly, and inferred credit as inferred', () => {
  const html = view({ phase: 'result', summary: S.summarize(PASS, BANDS) }, 'de');
  // Mostly inferred: the headline names the level, not a count of «known» words.
  assert.ok(html.includes('Niveau A2.1 bestätigt'));
  assert.ok(!html.includes('420 Wörter schon bekannt'));
  assert.ok(html.includes('22 im Check erkannt, 398 aus dem Ergebnis abgeleitet.'));
  assert.ok(html.includes('data-credit="inferred"'));
  assert.ok(html.includes('A2.1 · A1.2'));
  assert.ok(html.includes('23 von 24 erkannt.'));
  // A pass stops the ladder: no next check is offered.
  assert.ok(!html.includes('prüfen</span>'));

  const fhtml = view({ phase: 'result', summary: S.summarize(MISS, BANDS) }, 'en', 'placement');
  assert.ok(fhtml.includes('17 of 24 recognised'));
  assert.ok(fhtml.includes('it needed 21'));
  assert.ok(fhtml.includes('normal flow'));
  assert.ok(fhtml.includes('One level down: A1.2.'));
  assert.ok(fhtml.includes('Check A1.2'));
  assert.ok(fhtml.includes('Stop here'));
  // one primary per state
  assert.equal((fhtml.match(/av2-btn--primary/g) || []).length, 1);
});

test('a paused visit says so and offers no third check', () => {
  const summary = S.summarize({ ...MISS, sub_band: 'A1.2', ladder_status: 'paused', next: null, resume_band: 'A1.1' }, BANDS);
  const html = view({ phase: 'result', summary }, 'fr');
  assert.ok(html.includes('Reprenez avec A1.1 un autre jour'));
  assert.ok(!html.includes('Vérifier A1.1'));
  const screen = view({ phase: 'paused', band: 'A1.1' }, 'en');
  assert.ok(screen.includes('That’s enough for today'));
  assert.ok(screen.includes('Carry on with A1.1 another day'));
});

test('the intro names the item count, the candidate threshold, the top-down rule and the levels', () => {
  const run = { ...S.startRun('A2.1', ITEMS, 21 / 24, 'A2.1:0:abc'), passCorrect: 3 };
  const bands = [...S.markMissed(BANDS, 'B1.1')];
  const html = view({ phase: 'intro', run, bands: [{ sub_band: 'A1.1', words: 180, credited: true, credit_kind: 'inferred' }, ...bands] }, 'fr');
  assert.ok(html.includes('3 mots du niveau A2.1'));
  assert.ok(html.includes('Il faut en reconnaître 3 sur 3'));
  assert.ok(html.includes('à l’essai'));
  assert.ok(html.includes('le niveau le plus haut sous le vôtre'));
  assert.ok(html.includes('Niveaux à vérifier'));
  assert.ok(html.includes('déduit'));
});

test('a question can always be stopped', () => {
  const html = view({ phase: 'question', run: S.startRun('A1.2', ITEMS) }, 'de');
  assert.ok(html.includes('Hier aufhören'));
});

test('the entry renders only while the ladder has a band to check now', () => {
  const open = { status: 'open', next: 'A2.1' };
  const html = renderToStaticMarkup(h(BandCheckEntryView, { origin: 'lexique', language: 'en', bands: BANDS, ladder: open }));
  assert.ok(html.includes('Check my vocabulary (2 min)'));
  assert.ok(html.includes('Start with A2.1'));
  assert.ok(html.includes('href="/vocabulary/verification?from=lexique"'));
  const resumed = renderToStaticMarkup(
    h(BandCheckEntryView, { origin: 'lexique', language: 'en', bands: S.markMissed(BANDS, 'A2.1'), ladder: { status: 'open', next: 'A1.2' } }),
  );
  assert.ok(resumed.includes('Your check picks up at A1.2.'));
  for (const status of ['paused', 'done', 'none']) {
    const quiet = renderToStaticMarkup(
      h(BandCheckEntryView, { origin: 'placement', language: 'en', bands: BANDS, ladder: { status, next: null } }),
    );
    assert.equal(quiet, '', status);
  }
  assert.equal(bandCheckHref('placement', 'A2.1'), '/vocabulary/verification?from=placement&band=A2.1');
});

// --- stop and resume ---------------------------------------------------------

test('a stopped run resumes on the same attempt with its answers, never on another', () => {
  let run = S.startRun('A1.2', ITEMS, 21 / 24, 'A1.2:0:abc');
  run = S.answer(S.answer(run, 1), null);
  const saved = S.savedRunOf(run);
  assert.deepEqual(saved, { attemptId: 'A1.2:0:abc', answers: { fenêtre: 1, oublier: null } });
  const back = S.resumeRun(S.startRun('A1.2', ITEMS, 21 / 24, 'A1.2:0:abc'), saved);
  assert.equal(back.index, 2);
  assert.equal(S.currentItem(back).id, 'lent');
  // Another attempt (new words, new key) starts clean.
  const other = S.resumeRun(S.startRun('A1.2', ITEMS, 21 / 24, 'A1.2:1:def'), saved);
  assert.equal(other.index, 0);
  // A corrupted saved answer stops the restore there.
  const bad = S.resumeRun(S.startRun('A1.2', ITEMS, 21 / 24, 'A1.2:0:abc'), { attemptId: 'A1.2:0:abc', answers: { fenêtre: 9 } });
  assert.equal(bad.index, 0);
  assert.equal(S.savedRunOf(S.startRun('A1.2', ITEMS)), null);
  assert.equal(S.savedRunKey('A1.2:0:abc'), 'atelier.band-check.A1.2:0:abc');
});
