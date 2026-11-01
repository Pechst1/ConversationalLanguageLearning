// node --test lib/card-word.test.js
//
// Owner request, 1 Nov: wherever a French noun is a card's word — front or back,
// recognition or production, asked from either side — it carries its article.
//   1. every noun card whose gender is known shows its French with an article;
//   2. the typed answer is still graded without one;
//   3. no surface of the review deck renders the bare lemma: the page reads the card's
//      word from lib/card-word.ts only, never from the payload's `word` / `translations.fr`.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
require('sucrase/register/ts');
const { cardTexts, shownFrench } = require('./card-word.ts');

const MODES = ['recognition', 'production', 'audio', 'scene', 'rescue'];
const NOUNS = [
  { word: 'serrure', gender: 'f', translation: 'Schloss', shown: 'la serrure' },
  { word: 'grenier', gender: 'm', translation: 'Dachboden', shown: 'le grenier' },
  { word: 'horloge', gender: 'f', translation: 'Uhr', shown: 'l’horloge (f.)' },
  { word: 'arbre', gender: 'm', translation: 'Baum', shown: 'l’arbre (m.)' },
];
const ARTICLE = /^(la |le |les |un |une |l’)/;
const card = (noun, direction) => ({
  word: noun.word,
  gender: noun.gender,
  part_of_speech: 'noun',
  translation: noun.translation,
  translations: { fr: noun.word, de: noun.translation },
  direction,
});

test('every noun card with a known gender shows its French with an article, on either side', () => {
  for (const noun of NOUNS) {
    for (const direction of ['fr_to_de', 'de_to_fr', null]) {
      for (const mode of MODES) {
        const item = card(noun, direction);
        const { prompt, answer } = cardTexts({ item, mode, cue: null, listenPrompt: 'Écoute' });
        for (const [side, text] of [['front', prompt], ['back', answer]]) {
          if (text === noun.translation || text === 'Écoute') continue; // the learner's side, or the ear
          assert.equal(text, noun.shown, `${noun.word} ${direction} ${mode} ${side}: «${text}»`);
          assert.match(text, ARTICLE);
        }
        // The French is on the card somewhere (never only the meaning), except by ear.
        if (mode !== 'audio') assert.ok([prompt, answer].includes(noun.shown), `${noun.word} ${direction} ${mode}`);
      }
    }
  }
});

test('the typed answer is graded without the article', () => {
  const item = card(NOUNS[2], 'fr_to_de');
  const { answer, expected } = cardTexts({ item, mode: 'production', cue: null, listenPrompt: '' });
  assert.equal(answer, 'l’horloge (f.)');
  assert.equal(expected, 'horloge');
});

test('a line card answers with the form in its line, not the headword', () => {
  const item = card(NOUNS[0], 'fr_to_de');
  const cue = { sentence_fr: 'Il ouvre les _____ .', expected_fr: 'serrures', hint_fr: 'serrure' };
  const { answer, expected } = cardTexts({ item, mode: 'scene', cue, listenPrompt: '' });
  assert.equal(answer, 'serrures');
  assert.equal(expected, 'serrures');
});

test('a noun with no known gender and any other word are shown as they are', () => {
  assert.equal(shownFrench({ word: 'artiste', part_of_speech: 'noun', gender: null }), 'artiste');
  assert.equal(shownFrench({ word: 'courir', part_of_speech: 'verb', gender: null }), 'courir');
});

test('no surface of the review deck renders the bare lemma', () => {
  const source = fs.readFileSync(path.join(__dirname, '..', 'pages', 'vocabulary', 'review.tsx'), 'utf8');
  // The card's word comes from lib/card-word.ts, one function for every side.
  assert.match(source, /from '@\/lib\/card-word'/);
  assert.match(source, /cardTexts\(\{/);
  // The page never reads the headword off the payload itself …
  assert.doesNotMatch(source, /\.translations\?\.fr/);
  assert.doesNotMatch(source, /\bitem\.word\b(?!_id)/);
  assert.doesNotMatch(source, /\bcurrent\.word\b(?!_id)/);
  assert.doesNotMatch(source, /\blastItem\.word\b(?!_id)/);
  // … nor keeps a French accessor of its own.
  assert.doesNotMatch(source, /function queue(Word|French|Translation)\b/);
  // The bare French is only graded, searched in its example, spoken or matched to a cue;
  // where the card's back falls back to the French, it shows it with its article.
  assert.doesNotMatch(source, /\{answer \|\| meaning \|\| french\}/);
  assert.match(source, /\{answer \|\| meaning \|\| shownFrench\(current\)\}/);
  // The deck's last line names the last word with its article too.
  assert.match(source, /const word = lastItem \? shownFrench\(lastItem\)/);
});
