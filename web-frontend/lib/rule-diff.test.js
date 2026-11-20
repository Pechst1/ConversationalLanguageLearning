// node --test lib/rule-diff.test.js
//
// Le Déclic: the letters of an answer that carry the rule, read from the drill's own options.

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

require(path.join(path.resolve(__dirname, '..'), 'node_modules/sucrase/register/ts'));
const { markedParts, ruleDiff, whyWithoutEcho } = require('./rule-diff.ts');

const marks = (text, others) => markedParts(ruleDiff(text, others));
const joined = (words) => words.map((word) => word.segments.map((s) => s.text).join('') + word.space).join('');

test('the items of the walk mark the helper and the ending', () => {
  assert.deepEqual(marks('Margaux est rentrée', ['Margaux est rentré', 'Margaux a rentré']), ['est', 'e']);
  assert.deepEqual(marks('on a dîné', ['on est dîné', 'on a dîner']), ['a', 'é']);
  assert.deepEqual(marks('je suis descendu', ["j'ai descendu"]), ['je', 'suis']);
  assert.deepEqual(marks('sont montées', ['ont monté']), ['sont', 'es']);
});

test('a word with nothing of its own is marked only when nothing else differs', () => {
  assert.deepEqual(marks('Gus est parti', ['Gus est partie']), ['parti']);
  assert.deepEqual(marks('je suis descendu', ["j'ai descendu", 'je suis descendue']), ['je', 'suis']);
});

test('a one-word choice with no shared stem is marked whole', () => {
  assert.deepEqual(marks('a', ['à']), ['a']);
  assert.deepEqual(marks('vu', ['voyé']), ['vu']);
});

test('an unclear comparison stays plain', () => {
  assert.deepEqual(marks('il y a longtemps', ['depuis trois jours']), []);
  assert.deepEqual(marks('Gus est parti', []), []);
  assert.deepEqual(marks('Gus est parti', ['gus est parti']), []);
});

test('typographic apostrophes and case do not count as differences', () => {
  assert.deepEqual(marks('j’ai mangé', ["j'ai mangés"]), ['mangé']);
  assert.deepEqual(marks('Il est parti', ['il a parti']), ['est']);
});

test('the text comes back unchanged, punctuation and spacing included', () => {
  for (const text of ["j’ai vu « Marin », hier !", 'Margaux est rentrée', "aujourd'hui, c'est fini."]) {
    assert.equal(joined(ruleDiff(text, ['autre chose'])), text);
    assert.equal(joined(ruleDiff(text)), text);
  }
});

test('punctuation stays out of the mark', () => {
  assert.deepEqual(marks('il est parti.', ['il a parti.']), ['est']);
  assert.deepEqual(marks('elle est partie.', ['elle est parti.']), ['e']);
});

test('the sentence that only repeats the two forms leaves the explanation, in any language', () => {
  const rule = 'Aller, venir et rester utilisent être.';
  assert.equal(whyWithoutEcho(`You chose “j'ai descendu”; this item needs “je suis descendu”. ${rule}`, "j'ai descendu", 'je suis descendu'), rule);
  assert.equal(whyWithoutEcho(`Du hast „a“ gewählt; hier ist „est“ nötig. ${rule}`, 'a', 'est'), rule);
  assert.equal(whyWithoutEcho(rule, "j'ai", 'je suis'), rule);
  assert.equal(whyWithoutEcho('', 'a', 'b'), '');
});

test('an unrelated option does not turn a whole word red', () => {
  assert.deepEqual(markedParts(ruleDiff('mains', ['main', 'autrement'])), ['s']);
  assert.deepEqual(markedParts(ruleDiff('Margaux est rentrée', ['Margaux est rentré', 'autrement'])), ['e']);
  // With nothing closer, the comparison stands as it was.
  assert.deepEqual(markedParts(ruleDiff('parti', ['autrement'])), ['parti']);
});
