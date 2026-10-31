// #398 — a word card's back never quotes «word - gloss» as if it were an example sentence.
const test = require('node:test');
const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');
const { cardContextText } = require('./review-card-context.ts');

test('a card without an example line prints no quoted context', () => {
  assert.equal(cardContextText({ mode: 'recognition', french: 'lampe', meaning: 'lamp', example: '' }), '');
  assert.equal(cardContextText({ mode: 'production', french: 'quinze', meaning: 'fifteen', example: '' }), '');
  assert.equal(cardContextText({ mode: 'cloze', french: 'coopérative', meaning: 'co-operative', example: '' }), '');
});

test('a card with an example keeps it as the context', () => {
  assert.equal(
    cardContextText({ mode: 'recognition', french: 'lampe', meaning: 'lamp', example: 'La lampe brille.' }),
    'La lampe brille.',
  );
});

test('an audio card shows the meaning and the example, as before', () => {
  assert.equal(
    cardContextText({ mode: 'audio', french: 'lampe', meaning: 'lamp', example: 'La lampe brille.' }),
    'lamp · La lampe brille.',
  );
  assert.equal(cardContextText({ mode: 'audio', french: 'lampe', meaning: 'lamp', example: '' }), 'lamp');
});
