// #398 — a word card's back never quotes «word - gloss» as if it were an example sentence.
const test = require('node:test');
const assert = require('node:assert/strict');

const fs = require('node:fs');
const path = require('node:path');

require('../node_modules/sucrase/register/ts');

test('the review page has no «word - gloss» fallback for the example line', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  assert.doesNotMatch(source, /\$\{french\} - \$\{meaning\}/);
});

test('a card without an example line prints no quoted context', () => {
  const { cardContextText } = require('./review-card-context.ts');
  assert.equal(cardContextText({ mode: 'recognition', french: 'lampe', meaning: 'lamp', example: '' }), '');
  assert.equal(cardContextText({ mode: 'production', french: 'quinze', meaning: 'fifteen', example: '' }), '');
  assert.equal(cardContextText({ mode: 'cloze', french: 'coopérative', meaning: 'co-operative', example: '' }), '');
});

test('a card with an example keeps it as the context', () => {
  const { cardContextText } = require('./review-card-context.ts');
  assert.equal(
    cardContextText({ mode: 'recognition', french: 'lampe', meaning: 'lamp', example: 'La lampe brille.' }),
    'La lampe brille.',
  );
});

test('an audio card shows the meaning and the example, as before', () => {
  const { cardContextText } = require('./review-card-context.ts');
  assert.equal(
    cardContextText({ mode: 'audio', french: 'lampe', meaning: 'lamp', example: 'La lampe brille.' }),
    'lamp · La lampe brille.',
  );
  assert.equal(cardContextText({ mode: 'audio', french: 'lampe', meaning: 'lamp', example: '' }), 'lamp');
});
