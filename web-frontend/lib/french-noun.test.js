// node --test lib/french-noun.test.js
//
// Owner request, 1 Nov: a French noun always shows its article — elided «l’» before a
// vowel or a mute h, with the gender said when «l’» hides it; a noun with no known
// gender is shown as it is.
const assert = require('node:assert/strict');
const test = require('node:test');
require('sucrase/register/ts');
const { frenchHeadword, articleFor } = require('./french-noun.ts');
const wordToken = require('./word-token.ts');

const noun = (word, gender) => frenchHeadword({ word, gender, partOfSpeech: 'noun' });

test('a noun with a known gender carries le / la', () => {
  assert.equal(noun('serrure', 'f'), 'la serrure');
  assert.equal(noun('grenier', 'm'), 'le grenier');
  assert.equal(noun('haricot', 'm'), 'le haricot'); // h aspiré: no elision
  assert.equal(noun('honte', 'f'), 'la honte');
  assert.equal(noun('yaourt', 'm'), 'le yaourt'); // y before a vowel is a consonant
});

test('before a vowel or a mute h the article is elided and the gender said', () => {
  assert.equal(noun('horloge', 'f'), 'l’horloge (f.)');
  assert.equal(noun('arbre', 'm'), 'l’arbre (m.)');
  assert.equal(noun('homme', 'm'), 'l’homme (m.)');
  assert.equal(noun('école', 'f'), 'l’école (f.)');
  assert.equal(noun('œuf', 'm'), 'l’œuf (m.)');
});

test('an article the entry already carries is kept, never doubled', () => {
  assert.equal(noun('la gare', 'f'), 'la gare');
  assert.equal(noun('le frère', 'm'), 'le frère');
  assert.equal(noun("l'addition", 'f'), 'l’addition (f.)');
  assert.equal(noun('l’hiver', 'm'), 'l’hiver (m.)');
});

test('no gender, no article: nothing is guessed', () => {
  assert.equal(noun('artiste', null), 'artiste'); // epicene: no one article
  assert.equal(noun('artiste', 'mf'), 'artiste');
  assert.equal(frenchHeadword({ word: 'serrure' }), 'serrure');
  // A gender with no part of speech is a noun's (the server only genders nouns).
  assert.equal(frenchHeadword({ word: 'serrure', gender: 'f' }), 'la serrure');
  // A row that says it is not a noun is not given one.
  assert.equal(frenchHeadword({ word: 'aller', gender: 'm', partOfSpeech: 'verb' }), 'aller');
});

test('the word token draws the same article (one rule)', () => {
  assert.equal(wordToken.articleFor, articleFor);
  assert.equal(wordToken.wordTokenModel({ word: 'yaourt', gender: 'm' }).article, 'le');
});
