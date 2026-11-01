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

// Codex review on #465: «le gens», «la vacances». A noun used in the plural only takes
// «les»; the server says which (`number: "pl"`, app/data/lexical/fr_pluralia_tantum.json).
const fs = require('node:fs');
const path = require('node:path');
const DATA = path.join(__dirname, '..', '..', 'app', 'data', 'lexical');
const LEXICON = JSON.parse(fs.readFileSync(path.join(DATA, 'fr_core_lexicon.json'), 'utf8')).lemmas;
const PLURALIA = new Set(JSON.parse(fs.readFileSync(path.join(DATA, 'fr_pluralia_tantum.json'), 'utf8')).lemmas);

test('«gens» and «vacances», as the catalogue has them, take «les»', () => {
  for (const lemma of ['gens', 'vacances']) {
    const entry = LEXICON[lemma];
    assert.equal(entry.pos, 'noun');
    const shown = frenchHeadword({ word: lemma, gender: entry.gender, partOfSpeech: entry.pos, number: 'pl' });
    assert.equal(shown, `les ${lemma}`);
    assert.equal(articleFor(lemma, entry.gender, 'pl'), 'les');
    assert.equal(wordToken.wordTokenModel({ word: lemma, gender: entry.gender, number: 'pl' }).article, 'les');
  }
  // A written «les» is kept, never doubled.
  assert.equal(frenchHeadword({ word: 'les vacances', gender: 'f', partOfSpeech: 'noun', number: 'pl' }), 'les vacances');
});

test('no noun of the lexicon used in the plural only gets le, la or l’', () => {
  let swept = 0;
  for (const [lemma, entry] of Object.entries(LEXICON)) {
    if (entry.pos !== 'noun') continue;
    // The server's number for this lemma (lexicon_grammar.word_number reads the same file).
    const number = PLURALIA.has(lemma) ? 'pl' : null;
    const shown = frenchHeadword({ word: lemma, gender: entry.gender, partOfSpeech: 'noun', number });
    if (PLURALIA.has(lemma)) {
      swept += 1;
      assert.equal(shown, `les ${lemma}`, lemma);
      assert.doesNotMatch(shown, /^(le |la |l’)/, lemma);
    } else {
      assert.doesNotMatch(shown, /^les /, lemma);
    }
  }
  assert.ok(swept >= 2, `${swept} plural-only nouns swept`);
});

test('a final -s or -x says nothing: le bras, le prix, le temps', () => {
  for (const lemma of ['bras', 'prix', 'temps']) {
    assert.equal(frenchHeadword({ word: lemma, gender: LEXICON[lemma].gender, partOfSpeech: 'noun' }), `le ${lemma}`);
  }
});
