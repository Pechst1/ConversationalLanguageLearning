// node --test e2e/lib/forge-miss-measure.test.mjs
//
// Run 43073091897 (main, fr day 3): `forge-miss-correction-above-the-sheet` measured the
// rafale's whole result list as the correction card, so a right fourth row under the sheet
// read as a correction hidden behind it. The rafale's correction card is its first missed row.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { measureForgeMiss } from './learner-walk.mjs';

const box = (top, bottom) => ({ getBoundingClientRect: () => ({ top, bottom }) });

function withPage({ feedback, header }, run) {
  globalThis.document = { querySelector: (sel) => (sel.startsWith('.ep-feedback') ? feedback : sel === '.ep-top' ? header : null) };
  globalThis.window = { innerHeight: 812, scrollY: 0 };
  try {
    return run();
  } finally {
    delete globalThis.document;
    delete globalThis.window;
  }
}

function feedbackOf({ list, foot, miss = null }) {
  return {
    children: [Object.assign(list, { classList: { contains: () => false } }), Object.assign(foot, { classList: { contains: (c) => c === 'ep-foot' } })],
    querySelector: (sel) => (sel === '.ep-foot' ? foot : sel.includes('forge-rafale__rows') ? miss : null),
    getAttribute: () => 'settled',
  };
}

test('the rafale: the first missed row is the card, not the whole list (the 11 Nov fr screen)', () => {
  const list = Object.assign(box(193, 626), { innerText: 'Je suis au Mistral, Margaux. … Elles sont occupées, Lila.' });
  const miss = Object.assign(box(193, 372), { innerText: 'Je suis au Mistral, Margaux. Tu as dit « À corriger »' });
  const got = withPage({ feedback: feedbackOf({ list, foot: box(607, 812), miss }), header: box(0, 66) }, measureForgeMiss);
  assert.equal(got.cardTop, 193);
  assert.equal(got.cardBottom, 372, 'the missed row ends above the sheet');
  assert.equal(got.sheetTop, 607);
});

test('a single miss (no rafale) still measures the feedback\'s first card', () => {
  const card = Object.assign(box(200, 480), { innerText: 'Pas encore' });
  const got = withPage({ feedback: feedbackOf({ list: card, foot: box(560, 812) }), header: box(0, 70) }, measureForgeMiss);
  assert.equal(got.cardBottom, 480);
  assert.equal(got.headerBottom, 70);
});
