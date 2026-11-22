// node --test components/lexique/card-direction-cue.test.js
//
// Walk finding #725 (live walk 12 Nov): two cards of the A1 base list showed «school» and
// «forty» on the front with only «Tap to turn» under them. Every other card of the deck
// had the French on the front, so nothing told the learner that this one goes the other
// way. A card front in the learner's language now carries a line that asks for the
// French, in the chrome language; a French front carries none.
//   1. `cardTexts` says which language its front is in and, when it is not French, the
//      line that asks for the French;
//   2. the front the review page draws (CardFront) prints that line, and marks the
//      French front as French.
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { cardTexts } = require('../../lib/card-word.ts');
const { lexiqueCopy } = require('./lexique-copy.ts');

// The two cards of the walk, as the A1 base list stores them.
const ECOLE = {
  word: 'école',
  gender: 'f',
  part_of_speech: 'noun',
  translation: 'school',
  translations: { fr: 'école', en: 'school', de: 'Schule' },
};
const QUARANTE = {
  word: 'quarante',
  part_of_speech: 'number',
  translation: 'forty',
  translations: { fr: 'quarante', en: 'forty', de: 'vierzig' },
};
const FRENCH = { 'école': 'l’école (f.)', quarante: 'quarante' };

// Every way the deck can deal them: the meaning asked (production, a line card with no
// line), or a recognition card stored the other way round (en_to_fr / de_to_fr).
const DEALS = [
  { mode: 'production', direction: 'fr_to_en' },
  { mode: 'production', direction: null },
  { mode: 'recognition', direction: 'en_to_fr' },
  { mode: 'recognition', direction: 'de_to_fr' },
  { mode: 'scene', direction: 'fr_to_en' },
  { mode: 'rescue', direction: 'fr_to_en' },
];

function front(item, mode, language = 'en') {
  const t = lexiqueCopy(language);
  return cardTexts({ item, mode, cue: null, listenPrompt: t.listen_prompt, askPrompt: t.ask_in_french });
}

test('a front in the learner’s language says that the French is asked', () => {
  for (const word of [ECOLE, QUARANTE]) {
    for (const { mode, direction } of DEALS) {
      const item = { ...word, direction };
      const texts = front(item, mode);
      const label = `${word.word} ${mode} ${direction}`;
      if (texts.prompt === FRENCH[word.word]) continue;
      // The front is the gloss («school», «forty»): it must not stand alone.
      assert.ok(
        typeof texts.ask === 'string' && texts.ask.trim().length > 0,
        `${label}: the front shows «${texts.prompt}» with no line that asks for the French`,
      );
      assert.equal(texts.ask, 'How do you say it in French?', label);
      assert.equal(texts.promptIsFrench, false, label);
      assert.equal(texts.answer, FRENCH[word.word], `${label}: the back is the French`);
    }
  }
});

test('the line is in the chrome language', () => {
  const item = { ...ECOLE, direction: 'fr_to_de' };
  assert.equal(front(item, 'production', 'de').ask, 'Wie heißt das auf Französisch?');
  assert.equal(front(item, 'production', 'fr').ask, 'Comment dit-on en français ?');
});

test('a French front carries no cue, and the ear asks by itself', () => {
  for (const word of [ECOLE, QUARANTE]) {
    const recognition = front({ ...word, direction: 'fr_to_en' }, 'recognition');
    assert.equal(recognition.prompt, FRENCH[word.word]);
    assert.equal(recognition.promptIsFrench, true);
    assert.equal(recognition.ask, '');
    const audio = front({ ...word, direction: 'fr_to_en' }, 'audio');
    assert.equal(audio.ask, '');
    // A word with no gloss falls back to its French: no cue on a French front.
    const bare = front({ word: word.word, part_of_speech: word.part_of_speech, gender: word.gender }, 'production');
    assert.equal(bare.prompt, FRENCH[word.word]);
    assert.equal(bare.promptIsFrench, true);
    assert.equal(bare.ask, '');
  }
});

test('the review card’s front prints the cue under English chrome («school», «forty»)', () => {
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { CardFront } = require('./CardFront.tsx');
  const t = lexiqueCopy('en');
  for (const word of [ECOLE, QUARANTE]) {
    for (const { mode, direction } of [{ mode: 'production', direction: 'fr_to_en' }, { mode: 'recognition', direction: 'en_to_fr' }]) {
      const texts = front({ ...word, direction }, mode);
      const html = renderToStaticMarkup(React.createElement(CardFront, { texts, hint: '', listen: null }));
      assert.ok(html.includes(`>${word.translation}<`), html);
      assert.ok(html.includes(t.ask_in_french), `${word.word} ${mode}: no cue on the front: ${html}`);
      assert.ok(!html.includes('lang="fr"'), 'the gloss is not marked as French');
    }
    const texts = front({ ...word, direction: 'fr_to_en' }, 'recognition');
    const html = renderToStaticMarkup(React.createElement(CardFront, { texts, hint: '', listen: null }));
    assert.ok(html.includes('lang="fr"'), 'the French front is marked as French');
    assert.ok(!html.includes(t.ask_in_french), 'a French front carries no cue');
  }
});
