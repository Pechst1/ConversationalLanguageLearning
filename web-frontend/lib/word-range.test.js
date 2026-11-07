const assert = require('node:assert/strict');
require('sucrase/register/ts');
const { withinWordRange, wordsOf } = require('./word-range.ts');

const words = (n) => Array.from({ length: n }, () => 'mot').join(' ');
assert.equal(wordsOf('  un   deux '), 2);
assert.equal(withinWordRange(words(17), 16), false, '17 words for a 7–16 word item');
assert.equal(withinWordRange(words(16), 16), true);
assert.equal(withinWordRange(words(3), 16), true, 'the floor is a hint, not a rule');
assert.equal(withinWordRange(words(40), undefined), true, 'no ceiling, any length');
console.log('Word range checks passed');
