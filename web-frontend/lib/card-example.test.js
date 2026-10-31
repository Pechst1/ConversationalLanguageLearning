// node --test lib/card-example.test.js
//
// #398 (live walk 31 Oct): a word card with no example sentence quoted «lampe - lamp».
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
require('sucrase/register/ts');
const { cardContextText, cardExample } = require('./card-example.ts');

const CARDS = [
  { french: 'lampe', meaning: 'lamp' },
  { french: 'quinze', meaning: 'fifteen' },
  { french: 'coopérative', meaning: 'co-operative' },
];
const isWordGloss = (text, { french, meaning }) => /\s[-–—]\s/.test(text) && text.includes(french) && text.includes(meaning);

test('a card with no example quotes nothing, never «word - gloss»', () => {
  for (const card of CARDS) {
    for (const mode of ['recognition', 'production', 'scene', 'rescue']) {
      const example = cardExample({ ...card, example: '' });
      const quoted = cardContextText({ ...card, mode, example });
      assert.equal(quoted, '', `${mode}: «${quoted}»`);
      assert.ok(!isWordGloss(quoted, card));
    }
  }
});

test('an example that is only the headword and its gloss is no example', () => {
  for (const card of CARDS) {
    for (const dash of ['-', '–', '—']) {
      assert.equal(cardExample({ ...card, example: `${card.french} ${dash} ${card.meaning}` }), '');
      assert.equal(cardExample({ ...card, example: `« ${card.french} ${dash} ${card.meaning} »` }), '');
    }
  }
});

test('a real example is quoted as it is', () => {
  const card = { french: 'lampe', meaning: 'lamp' };
  const sentence = 'Sur le toit, la lampe de M. Marchand brille.';
  assert.equal(cardExample({ ...card, example: sentence }), sentence);
  assert.equal(cardContextText({ ...card, mode: 'recognition', example: sentence }), sentence);
  // By ear the card shows the meaning with the sentence, as before.
  assert.equal(cardContextText({ ...card, mode: 'audio', example: sentence }), `lamp · ${sentence}`);
  assert.equal(cardContextText({ ...card, mode: 'audio', example: '' }), 'lamp');
});

test('the review page builds its card lines from these, with no headword-gloss fallback', () => {
  const page = fs.readFileSync(path.join(__dirname, '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  assert.match(page, /cardExample\(/);
  assert.match(page, /cardContextText\(/);
  assert.doesNotMatch(page, /`\$\{french\} - \$\{meaning\}`/);
});
