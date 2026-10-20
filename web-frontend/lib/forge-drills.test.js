// node --test lib/forge-drills.test.js
//
// La Forge's formats (owner, 2026-10-18: more varied, more fun, faster
// learning). The pure half, read by the page and the drills:
//   1. how the item on screen is posed: the forge's word while it serves it,
//      the answer's own record after (an older server: the classic way);
//   2. «Rafale»: its four judgements, its exercise key, its marks, its time;
//   3. «Trouve l'erreur»: a sentence as tappable words and the fixed sentence;
//   4. «Tape la forme»: the accent bar types at the caret;
//   5. «Dictée»: the sentence heard is the word bank's answer;
//   6. the cheer under a right answer and the recap's épreuve offer.

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

const D = require('./forge-drills.ts');
const { forgeCopy } = require('./forge-copy.ts');

// ---------------------------------------------------------------------------
// 1 · how the item on screen is posed
// ---------------------------------------------------------------------------

test('only the eleven drills are drills; five of them name themselves', () => {
  assert.equal(D.asDrill('spot'), 'spot');
  assert.equal(D.asDrill(' rafale '), 'rafale');
  assert.equal(D.asDrill('karaoke'), null);
  assert.equal(D.asDrill(null), null);
  assert.deepEqual([...D.NAMED_DRILLS], ['typed', 'dictation', 'spot', 'mine', 'rafale']);
  assert.equal(D.isNamedDrill('dictation'), true);
  assert.equal(D.isNamedDrill('choice'), false);
  assert.equal(D.isNamedDrill(null), false);
});

test('the drill on screen is the forge’s word while served, the answer’s record after', () => {
  const next = { concept_id: 4, round: 'recognize', mode: 'fill', item_id: 'fill-1', drill: 'typed' };
  const here = { conceptId: 4, round: 'recognize', mode: 'fill', itemId: 'fill-1' };
  assert.equal(D.isServed(next, here), true);
  assert.equal(D.drillOnScreen(next, null, here), 'typed');
  // Answered: the forge already names the next item; the record says how this one was posed.
  const moved = { ...next, item_id: 'fill-2', drill: 'choice' };
  assert.equal(D.drillOnScreen(moved, { forge: { drill: 'typed' } }, here), 'typed');
  // Another mode of the same id is another item.
  assert.equal(D.isServed({ ...next, mode: 'word_bank' }, here), false);
  // A transform is matched without its mode.
  assert.equal(D.isServed({ concept_id: 4, round: 'transform', mode: 'rewrite', item_id: 't-1' }, { conceptId: 4, round: 'transform', mode: 'fill', itemId: 't-1' }), true);
  // An older server sends no drill: the classic way.
  assert.equal(D.drillOnScreen({ ...next, drill: undefined }, null, here), null);
  assert.equal(D.drillOnScreen(null, null, here), null);
  assert.equal(D.isServed(next, { ...here, itemId: null }), false);
});

// ---------------------------------------------------------------------------
// 2 · «Rafale»
// ---------------------------------------------------------------------------

const BURST = [
  { id: 'j-1', prompt: 'Il a mangé une pomme.', labels: ['Correct', 'À corriger'] },
  { id: 'j-2', prompt: 'Elle a allé au marché.', labels: ['Correct', 'À corriger'] },
  { id: 'j-3', prompt: 'Nous avons fini.', labels: ['Correct', 'À corriger'] },
  { id: 'j-4', prompt: 'Tu as venu hier.', labels: ['Correct', 'À corriger'] },
];

test('a burst is two or more judgements, the lead first, keyed by their ids', () => {
  assert.deepEqual(D.burstItems({ items: BURST }).map((item) => item.id), ['j-1', 'j-2', 'j-3', 'j-4']);
  assert.deepEqual(D.burstItems({ items: [BURST[0]] }), [], 'one judgement is no burst');
  assert.deepEqual(D.burstItems({ items: [BURST[0], null, { prompt: 'no id' }] }), []);
  assert.deepEqual(D.burstItems({}), []);
  assert.deepEqual(D.burstItems(null), []);
  assert.equal(D.burstItemKey(BURST), 'j-1+j-2+j-3+j-4');
});

test('the burst’s marks read in the order posed, each with its sentence and its fix', () => {
  const correction = {
    burst: [
      { item_id: 'j-1', sentence: 'Il a mangé une pomme.', answer: 'Correct', expected: 'Correct', correct: true },
      { item_id: 'j-2', answer: 'Correct', expected: 'À corriger', correct: false, corrected_fr: 'Elle est allée au marché.' },
      { item_id: 'j-3', sentence: 'Nous avons fini.', answer: 'Correct', expected: 'Correct', correct: true, corrected_fr: '  ' },
      { answer: 'Correct' },
    ],
  };
  const rows = D.burstRows(correction, BURST);
  assert.equal(rows.length, 3);
  assert.deepEqual(rows.map((row) => row.correct), [true, false, true]);
  assert.equal(rows[1].sentence, 'Elle a allé au marché.', 'the item’s own sentence when the row has none');
  assert.equal(rows[1].correctedFr, 'Elle est allée au marché.');
  assert.equal(rows[2].correctedFr, null);
  assert.deepEqual(D.burstRows({}, BURST), []);
  assert.deepEqual(D.burstRows(null), []);
});

test('the burst’s time reads «7.4 s» in English, «7,4 s» in French and German', () => {
  assert.equal(D.burstSeconds(7420, 'en'), '7.4');
  assert.equal(D.burstSeconds(7420, 'fr'), '7,4');
  assert.equal(D.burstSeconds(7420, 'de'), '7,4');
  assert.equal(D.burstSeconds(20, 'en'), '0.1');
  assert.equal(D.burstSeconds(0, 'en'), null);
  assert.equal(D.burstSeconds(undefined, 'en'), null);
});

// ---------------------------------------------------------------------------
// 3 · «Trouve l'erreur»
// ---------------------------------------------------------------------------

test('a sentence becomes tappable words; punctuation rides along and is never a word', () => {
  const tokens = D.spotTokens('« Elle n’a pas une idée », dit-il.');
  assert.deepEqual(tokens.map((token) => token.word), ['', 'Elle', 'n’a', 'pas', 'une', 'idée', '', 'dit-il']);
  assert.equal(tokens[5].trail, '');
  assert.equal(tokens[6].trail, '»,');
  assert.equal(tokens[7].trail, '.');
  // French spacing: the «?» on its own is punctuation, not a word to tap.
  const question = D.spotTokens('Tu vient ?');
  assert.deepEqual(question.map((token) => token.word), ['Tu', 'vient', '']);
  assert.deepEqual(D.spotTokens(''), []);
});

test('the answer is the sentence with the fixes in it', () => {
  const tokens = D.spotTokens('Elle n’a pas une idée.');
  assert.equal(D.spotAnswer(tokens, {}), 'Elle n’a pas une idée.');
  // An elided fix joins the next word.
  assert.equal(D.spotAnswer(tokens, { 3: 'd’' }), 'Elle n’a pas d’idée.');
  assert.equal(D.spotAnswer(tokens, { 3: "d'" }), "Elle n’a pas d'idée.");
  // An emptied word is dropped; a fix may be two words.
  assert.equal(D.spotAnswer(tokens, { 3: '' }), 'Elle n’a pas idée.');
  assert.equal(D.spotAnswer(D.spotTokens('Je pas mangé.'), { 1: 'n’ai pas' }), 'Je n’ai pas mangé.');
  // French spacing before «?» is kept.
  assert.equal(D.spotAnswer(D.spotTokens('Tu vient ?'), { 1: 'viens' }), 'Tu viens ?');
  assert.equal(D.spotChanged(tokens, { 3: 'une' }), false, 'retyping a word as it was is no fix');
  assert.equal(D.spotChanged(tokens, { 3: 'une ' }), false);
  assert.equal(D.spotChanged(tokens, { 3: 'aucune' }), true);
  assert.equal(D.spotChanged(tokens, { 9: 'x' }), false);
});

// ---------------------------------------------------------------------------
// 4 · «Tape la forme»
// ---------------------------------------------------------------------------

test('the accent bar types at the caret, over a selection, and moves the caret after', () => {
  assert.deepEqual(D.insertAt('mang', 4, 4, 'é'), { value: 'mangé', caret: 5 });
  assert.deepEqual(D.insertAt('mange', 4, 5, 'é'), { value: 'mangé', caret: 5 });
  assert.deepEqual(D.insertAt('lve', 1, 1, 'è'), { value: 'lève', caret: 2 });
  assert.deepEqual(D.insertAt('a', null, null, 'ç'), { value: 'aç', caret: 2 });
  assert.deepEqual(D.insertAt('ab', 9, 9, 'ô'), { value: 'abô', caret: 3 });
  assert.equal(D.ACCENTS[0], 'é');
  assert.ok(D.ACCENTS.includes('ç') && D.ACCENTS.includes('œ'));
});

// ---------------------------------------------------------------------------
// 5 · «Dictée»
// ---------------------------------------------------------------------------

test('a dictation speaks the word bank’s own answer', () => {
  assert.equal(D.dictationText({ correct_answer: ' J’ai fini. ', answer_tokens: ['x'] }), 'J’ai fini.');
  assert.equal(D.dictationText({ answer_tokens: ['Hier', ',', 'il', 'est', 'venu', '.'] }), 'Hier, il est venu.');
  assert.equal(D.dictationText({}), '');
  assert.equal(D.dictationText(null), '');
});

// ---------------------------------------------------------------------------
// 6 · the cheer and the offer
// ---------------------------------------------------------------------------

test('a right answer is cheered from the second in a row, or when it climbs a level', () => {
  const fc = forgeCopy('fr');
  assert.equal(D.RUN_CHEER_FROM, 2);
  assert.equal(D.forgeCheer({ forge: { rung: 2, new_rung: 3, run: 3 } }, fc), 'Niveau 4 ↑ · 3 d’affilée');
  assert.equal(D.forgeCheer({ forge: { rung: 4, new_rung: 5, run: 1, held: true } }, fc), 'Règle acquise !');
  assert.equal(D.forgeCheer({ forge: { rung: 4, new_rung: 4, run: 1 } }, fc), null);
  assert.equal(D.forgeCheer({}, fc), null);
  assert.equal(D.levelText(fc, 3), 'Niveau 4');
});

test('the recap’s épreuve offer is one rule and a few questions, or nothing', () => {
  assert.deepEqual(D.testOutOffer({ forge: { test_out_offer: { concept_id: 7, rung: 3, short: true, items: 3 } } }), { conceptId: 7, items: 3 });
  assert.deepEqual(D.testOutOffer({ forge: { test_out_offer: { concept_id: '7' } } }), { conceptId: 7, items: 3 });
  assert.equal(D.testOutOffer({ forge: { test_out_offer: { concept_id: 0 } } }), null);
  assert.equal(D.testOutOffer({ forge: { test_out_offer: null } }), null);
  assert.equal(D.testOutOffer({ forge: {} }), null);
  assert.equal(D.testOutOffer(null), null);
});
