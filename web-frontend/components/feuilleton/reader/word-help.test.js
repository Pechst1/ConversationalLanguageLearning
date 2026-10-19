/* Word help: where a tapped word's meaning comes from, in order.
 *   node --test components/feuilleton/reader/word-help.test.js
 *
 *   1. a meaning the surface already knows (Le Papier's target words) — no request at all;
 *   2. the catalogue entry;
 *   3. the word read in its sentence (`/atelier/gloss`), the sentence's translation under it;
 *   4. the line's translation (supplied, else `/atelier/translate`);
 *   5. nothing, said plainly.
 * And the sheet: a known meaning paints at once, «Garder» is offered for it, and the
 * footnote is the surface's (Le Papier has no episode to «not move on»).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

require('../../../node_modules/sucrase/register/ts');
require('../../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../../..');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
// The sheet's API client is never reached here: the order is tested through a fake.
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const { resolveWordHelp, shownLemma } = require('./word-help.ts');
const { WordHelpSheet } = require('./WordHelpSheet.tsx');

const SENTENCE = 'Elles suivent des règles : un préavis, une déclaration des grévistes.';

/** A fake API that records what was asked, in order. */
function fakeApi({ entry = null, context = null, translation = '', contextFails = false, translateFails = false } = {}) {
  const asked = [];
  return {
    asked,
    lookupVocabulary: async (term) => {
      asked.push(['lookup', term]);
      if (!entry) throw Object.assign(new Error('404'), { response: { status: 404 } });
      return entry;
    },
    glossInContext: async (word, sentence) => {
      asked.push(['gloss', word, sentence]);
      if (contextFails) throw new Error('down');
      return context ?? { lemma: '', gloss: '', language: '', translation: '' };
    },
    translateForLearner: async (text) => {
      asked.push(['translate', text]);
      if (translateFails) throw new Error('down');
      return translation;
    },
  };
}

test('a meaning the surface already knows is shown with no request', async () => {
  const api = fakeApi({ entry: { translation: 'Streik' } });
  const answer = await resolveWordHelp({ term: 'grève', sentence: SENTENCE, knownGloss: 'der Streik', knownGlossLanguage: 'de' }, api);
  assert.deepEqual(answer.gloss, { kind: 'gloss', text: 'der Streik', language: 'de' });
  assert.deepEqual(api.asked, []);
});

test('the catalogue answers first; the sentence is not read when it does', async () => {
  const api = fakeApi({ entry: { translation: 'Regel', translation_language: 'de' } });
  const answer = await resolveWordHelp({ term: 'règles', surface: 'règles', sentence: SENTENCE }, api);
  assert.deepEqual(answer.gloss, { kind: 'gloss', text: 'Regel', language: 'de' });
  assert.deepEqual(api.asked.map((row) => row[0]), ['lookup']);
});

test('a catalogue miss reads the word in its sentence: its meaning, its lemma, the line underneath', async () => {
  const api = fakeApi({ context: { lemma: 'gréviste', gloss: 'die Streikenden', language: 'de', translation: 'Eine Erklärung der Streikenden.' } });
  const answer = await resolveWordHelp({ term: 'grévistes', surface: 'grévistes', sentence: SENTENCE }, api);
  assert.deepEqual(answer.gloss, { kind: 'context', text: 'die Streikenden', lemma: 'gréviste', language: 'de' });
  assert.equal(answer.sentenceEn, 'Eine Erklärung der Streikenden.');
  assert.deepEqual(api.asked, [['lookup', 'grévistes'], ['gloss', 'grévistes', SENTENCE]], 'the line is never translated on its own');
  // A line that came with its translation keeps it.
  const supplied = await resolveWordHelp({ term: 'grévistes', surface: 'grévistes', sentence: SENTENCE, sentenceEn: 'Supplied.' }, fakeApi({ context: { lemma: 'gréviste', gloss: 'strikers', language: 'en', translation: 'Other.' } }));
  assert.equal(supplied.sentenceEn, 'Supplied.');
  // The lemma only when it says something the printed word does not.
  assert.equal(shownLemma('Grévistes', 'grévistes'), null);
  assert.equal(shownLemma('revenir', 'reviennent'), 'revenir');
  assert.equal(shownLemma('', 'reviennent'), null);
});

test('the sentence reading fails: today\'s fallback (the supplied line, else the translated line, else nothing)', async () => {
  const supplied = fakeApi({ contextFails: true });
  assert.deepEqual((await resolveWordHelp({ term: 'plagiat', sentence: SENTENCE, sentenceEn: 'A declaration.' }, supplied)).gloss, { kind: 'sentence', text: 'A declaration.' });
  assert.deepEqual(supplied.asked.map((row) => row[0]), ['lookup', 'gloss']);

  const translated = fakeApi({ contextFails: true, translation: 'Eine Erklärung.' });
  const answer = await resolveWordHelp({ term: 'plagiat', sentence: SENTENCE }, translated);
  assert.deepEqual(answer, { gloss: { kind: 'sentence', text: 'Eine Erklärung.' }, sentenceEn: 'Eine Erklärung.' });
  assert.deepEqual(translated.asked.map((row) => row[0]), ['lookup', 'gloss', 'translate']);

  // An empty gloss with a translation: the line, without asking for it twice.
  const halfway = fakeApi({ context: { lemma: '', gloss: '', language: 'de', translation: 'Eine Erklärung.' } });
  assert.deepEqual((await resolveWordHelp({ term: 'plagiat', sentence: SENTENCE }, halfway)).gloss, { kind: 'sentence', text: 'Eine Erklärung.' });
  assert.deepEqual(halfway.asked.map((row) => row[0]), ['lookup', 'gloss']);

  const nothing = fakeApi({ contextFails: true, translateFails: true });
  assert.deepEqual((await resolveWordHelp({ term: 'plagiat', sentence: SENTENCE }, nothing)).gloss, { kind: 'none' });
  // No sentence: nothing to read the word in.
  const bare = fakeApi();
  assert.deepEqual((await resolveWordHelp({ term: 'plagiat' }, bare)).gloss, { kind: 'none' });
  assert.deepEqual(bare.asked.map((row) => row[0]), ['lookup']);
});

test('an API without the sentence reading keeps the old order (catalogue, then the line)', async () => {
  const api = fakeApi({ translation: 'Eine Erklärung.' });
  delete api.glossInContext;
  assert.deepEqual((await resolveWordHelp({ term: 'plagiat', sentence: SENTENCE }, api)).gloss, { kind: 'sentence', text: 'Eine Erklärung.' });
  assert.deepEqual(api.asked.map((row) => row[0]), ['lookup', 'translate']);
});

test('the sheet: a known meaning paints at once with «Garder»; the footnote and the quote label are the surface\'s', () => {
  const request = { surface: 'grève', term: 'grève', sentence: 'La grève continue.', knownGloss: 'strike', knownGlossLanguage: 'en' };
  const papier = renderToStaticMarkup(React.createElement(WordHelpSheet, { request, onClose: () => {}, language: 'en', note: null, quoteLabel: 'In the text' }));
  assert.match(papier, /<p class="fr-gloss" aria-live="polite">strike<\/p>/);
  assert.doesNotMatch(papier, /Looking it up/);
  assert.match(papier, /class="fr-keep-btn"/, '«Garder» is offered for a known meaning');
  assert.doesNotMatch(papier, /fr-sheet-note/, 'Le Papier has no episode to mention');
  assert.match(papier, /<p class="fr-quote-k">In the text<\/p>/);

  // The reader keeps its own footnote and label.
  const reader = renderToStaticMarkup(React.createElement(WordHelpSheet, { request: { surface: 'grève', term: 'grève', sentence: 'La grève continue.' }, onClose: () => {}, language: 'de' }));
  assert.match(reader, /Nachschlagen zählt nicht als Antwort und bringt die Folge nicht weiter\./);
  assert.match(reader, /<p class="fr-quote-k">Im Bild<\/p>/);
  assert.match(reader, /Wird gesucht…/);
});
