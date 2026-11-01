// node --test components/lexique/no-cloze-card.test.js
//
// Owner decision 2026-11-01: «the example-sentence cards where the word is missing mostly
// don't work — translate the word, and get the example sentence along with it». The daily
// review deals no cloze card, the server's rung decides the card, and a card without one
// falls back to the server's own table (app/services/recall_ladder.py; the backend test
// tests/test_vocab_cards_no_cloze.py holds the two tables together).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

require(path.resolve(__dirname, '../../node_modules/sucrase/register/ts'));
const ladder = require('./recall-ladder.ts');
const { cardFaces, markExample } = require('../../lib/card-example.ts');

const STABILITIES = [0, 0.5, 1, 2, 3, 4, 5, 7, 9.99, 10, 14, 20, 21, 29.9, 30, 45, 90, 365, 4000];
const LEVELS = [null, '', 'A1', 'A2', 'B1', 'B1.1', 'B2', 'C1', 'C2', 'x'];

test('no stability, band or server rung ever deals a cloze card', () => {
  for (const stability of STABILITIES) {
    for (const level of LEVELS) {
      for (const isNew of [true, false]) {
        const rung = ladder.fallbackRung({ stability, isNew, level });
        assert.ok(['recognition', 'production', 'audio'].includes(rung), `${stability}/${level}: ${rung}`);
      }
    }
    for (const proficiency_score of [0, 55, 72, 90, 100]) {
      const item = { stability, proficiency_score, bucket: 'due', example_sentence: 'Il change la serrure de la porte.', word: 'serrure' };
      assert.notEqual(ladder.cardMode(item), 'cloze', `fallback at ${stability} / ${proficiency_score}`);
    }
  }
  for (const rung of ['recognition', 'production', 'audio', 'cloze', 'scene', 'rescue', 'other', null]) {
    const item = { ladder: rung, scene_cue: { sentence_fr: 'Tu as vu la _____ ?' }, rescue_cue: { first_letter: 's', length: 7 } };
    assert.notEqual(ladder.cardMode(item), 'cloze', `server rung ${rung}`);
  }
  assert.ok(!ladder.LADDER_RUNGS.includes('cloze'));
});

test('the fallback is the server’s table, not proficiency points', () => {
  // A2 (the server’s default band): production from 3 days, audio from 10, production from 30.
  const at = (stability, extra = {}) => ladder.cardMode({ stability, bucket: 'due', ...extra });
  assert.equal(at(1), 'recognition');
  assert.equal(at(3), 'production');
  assert.equal(at(10), 'audio');
  assert.equal(at(30), 'production', 'the top rung: translate the word, with its example');
  assert.equal(at(1, { proficiency_score: 95 }), 'recognition', 'a points streak no longer moves the card');
  assert.equal(at(50, { bucket: 'new' }), 'recognition');
  assert.equal(at(50, { is_new: true }), 'recognition');
  assert.equal(ladder.cardMode({ ladder: 'audio', stability: 0 }), 'audio', 'the server’s rung wins');
  assert.equal(ladder.ladderBand('C2'), 'C1');
  assert.equal(ladder.ladderBand(null), 'A2');
});

test('a blanked line also says what the word means; the rescue keeps its letter cue', () => {
  const rescue = { sentence_fr: 'Il change la _____ de la porte.', first_letter: 's', length: 7 };
  assert.equal(ladder.lineMeaning('rescue', rescue, 'lock'), 'lock');
  assert.equal(ladder.lineMeaning('scene', { sentence_fr: 'Tu as vu la _____ ?' }, 'lock'), 'lock');
  assert.equal(ladder.lineMeaning('rescue', { sentence_fr: null, first_letter: 's' }, 'lock'), '', 'asked by the meaning already');
  assert.equal(ladder.lineMeaning('production', rescue, 'lock'), '');
});

const CARD = {
  french: 'la serrure',
  meaning: 'Schloss',
  example: 'Il change la serrure de la porte.',
  exampleTranslation: 'Er wechselt das Türschloss.',
};
const text = (marked) => (marked ? `${marked.before}${marked.word}${marked.after}` : '');

test('a recognition card shows the example on its front, the word marked', () => {
  const faces = cardFaces({ ...CARD, mode: 'recognition', promptIsFrench: true });
  assert.deepEqual(faces.frontExample, { before: 'Il change la ', word: 'serrure', after: ' de la porte.' });
  assert.equal(faces.frontTranslation, '', 'the translation would give the answer away');
  assert.equal(text(faces.backExample), CARD.example);
  assert.equal(faces.backTranslation, CARD.exampleTranslation);
  // Asked from the learner's side, the French sentence holds the answer: back only.
  const reverse = cardFaces({ ...CARD, mode: 'recognition', promptIsFrench: false });
  assert.equal(reverse.frontExample, null);
  assert.equal(text(reverse.backExample), CARD.example);
});

test('a production card never shows the French word before it is turned', () => {
  for (const example of [CARD.example, 'Nous allons au marché.', 'La séance finale commence.']) {
    for (const french of ['la serrure', 'aller', 'final']) {
      const faces = cardFaces({ ...CARD, french, example, mode: 'production', promptIsFrench: true });
      assert.equal(faces.frontExample, null, `${french}: ${example}`);
      assert.ok(!faces.frontTranslation.includes(french.replace(/^la /, '')));
      assert.equal(text(faces.backExample), example, 'turned: the example');
      assert.equal(faces.backTranslation, CARD.exampleTranslation, 'turned: its translation');
    }
  }
  const faces = cardFaces({ ...CARD, mode: 'production', promptIsFrench: true });
  assert.equal(faces.frontTranslation, CARD.exampleTranslation, 'the learner-language sentence is a cue, not the answer');
  assert.equal(cardFaces({ ...CARD, exampleTranslation: '', mode: 'production', promptIsFrench: true }).frontTranslation, '');
});

test('audio cards are unchanged; a card with no example quotes nothing', () => {
  assert.deepEqual(cardFaces({ ...CARD, mode: 'audio', promptIsFrench: true }), {
    frontExample: null, frontTranslation: '', backExample: null, backTranslation: '',
  });
  for (const mode of ['recognition', 'production', 'scene', 'rescue']) {
    const faces = cardFaces({ ...CARD, example: '', mode, promptIsFrench: true });
    assert.equal(faces.frontExample, null);
    assert.equal(faces.backExample, null);
    assert.equal(faces.frontTranslation, '', 'no sentence, no sentence translation');
    assert.equal(faces.backTranslation, '');
  }
});

test('an inflected example is quoted whole with nothing marked', () => {
  assert.deepEqual(markExample('La séance finale commence.', 'final'), { before: 'La séance finale commence.', word: '', after: '' });
  assert.equal(markExample('', 'final'), null);
});

test('the review page takes its card from these and keeps no cloze of its own', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  assert.match(page, /cardMode,\n/);
  assert.match(page, /cardFaces\(/);
  assert.doesNotMatch(page, /function cardMode\(/, 'one rule: the ladder module’s');
  assert.doesNotMatch(page, /clozePrompt|clozeIsBlanked|proficiency_score \|\| 0\) >= /);
  assert.doesNotMatch(page, /mode === 'cloze'/);
});
