// node --test components/feuilleton/reader/grammar-marks.test.js
//
// WP-92 «Rayons X» — the day's rule, marked in the page.
//
//   1. offsets from the server land on the line the reader shows (trimmed,
//      typeset), and only the focus unit's marks count;
//   2. marks snap to whole words: a word button is marked whole, never split,
//      and the gap between two words of one form carries the mark;
//   3. the toggle opens only after the first full read (or on a replay), is
//      off by default, and a marked line is announced once to a screen reader;
//   4. the story model carries the marks and names the rule in the chrome
//      language.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const ROOT = path.resolve(__dirname, '../../..');
require(path.join(ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  if (request === 'next/link') return originalResolve.call(this, path.join(__dirname, '__fixtures__/next-link-stub.js'), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));
global.React = React;

const marks = require('./grammar-marks.ts');
const { FrenchLine } = require('./TappableFrench.tsx');
const { FeuilletonReader } = require('./FeuilletonReader.tsx');
const model = require('../../atelier-v2/journey/story-episode-model.ts');

const h = React.createElement;

function markedText(tokens) {
  return tokens.filter((token) => token.marked).map((token) => token.text).join('');
}

// --- 1. offsets -------------------------------------------------------------

test('offsets move onto the trimmed line, are clamped, filtered by unit and merged', () => {
  const raw = '  Je suis allé au marché.';
  // «suis allé» is [5, 14) in the raw line, [3, 12) once trimmed
  const ranges = marks.lineMarkRanges(raw, [
    { unit_id: 'passe_compose', start: 5, end: 9 },
    { unit_id: 'passe_compose', start: 9, end: 14 },
    { unit_id: 'other_unit', start: 18, end: 24 },
    { unit_id: 'passe_compose', start: 'x', end: 3 },
    { unit_id: 'passe_compose', start: 30, end: 40 },
    null,
  ], 'passe_compose');
  assert.deepEqual(ranges, [{ start: 3, end: 12 }]);
  assert.equal('Je suis allé au marché.'.slice(3, 12), 'suis allé');
  assert.deepEqual(marks.lineMarkRanges(raw, null), []);
  assert.deepEqual(marks.lineMarkRanges('', [{ start: 0, end: 2 }]), []);
  // no unit asked for: every mark counts
  assert.equal(marks.lineMarkRanges(raw, [{ unit_id: 7, start: 5, end: 9 }, { unit_id: 8, start: 18, end: 24 }]).length, 2);
  // numeric unit ids compare as strings
  assert.equal(marks.lineMarkRanges(raw, [{ unit_id: 7, start: 5, end: 9 }], '7').length, 1);
});

// --- 2. snapping to words --------------------------------------------------------

test('a mark inside a word takes the whole word; the gap of one form is marked', () => {
  const text = 'Je suis allé au marché.';
  const tokens = marks.markTokens(text, [{ start: 4, end: 10 }], 'l');
  // «uis al» → «suis allé», whole words, with the space between them
  assert.equal(markedText(tokens), 'suis allé');
  const words = tokens.filter((token) => token.word);
  assert.deepEqual(
    words.map((token) => [token.text, token.marked]),
    [['Je', false], ['suis', true], ['allé', true], ['au', false], ['marché', false]],
  );
  // the tokens are exactly the unmarked tokenizer's — no word is ever split
  const plain = marks.markTokens(text, null, 'l');
  assert.deepEqual(tokens.map((t) => t.text), plain.map((t) => t.text));
  assert.ok(plain.every((t) => !t.marked));
});

test('two marks of one line stay two: the gap between them is not marked', () => {
  const text = 'Tu es là et je suis ici.';
  const ranges = [{ start: 3, end: 5 }, { start: 15, end: 19 }];
  const tokens = marks.markTokens(text, ranges, 'l');
  assert.deepEqual(tokens.filter((t) => t.marked).map((t) => t.text), ['es', 'suis']);
  assert.deepEqual(marks.markedForms(text, ranges), ['es', 'suis']);
});

test('typesetting moves offsets, never words: «?» gets its narrow space and the mark holds', () => {
  const text = 'Tu es allé où?';
  // «es allé» is [3, 10) in the server's line; frenchSpacing adds U+202F before «?»
  const tokens = marks.markTokens(text, [{ start: 3, end: 10 }], 'l');
  assert.equal(markedText(tokens), 'es allé');
  assert.ok(tokens.map((t) => t.text).join('').includes(' ?'), 'the typeset line is what is rendered');
});

test('an élided form keeps its clitic inside the mark; punctuation alone marks nothing', () => {
  const text = 'Il s’appelle Marin.';
  const tokens = marks.markTokens(text, [{ start: 3, end: 12 }], 'l');
  assert.equal(markedText(tokens), 's’appelle');
  const appelle = tokens.find((t) => t.text === 'appelle');
  assert.equal(appelle.word, true, 'the content word is still the tappable one');
  assert.deepEqual(marks.markedForms(text, [{ start: 18, end: 19 }]), []);
  assert.deepEqual(marks.markedForms(text, [{ start: 3, end: 12 }]), ['s’appelle']);
});

// --- 3. the toggle ----------------------------------------------------------------

test('Rayons X opens after the first full read, or at once on a replay', () => {
  assert.equal(marks.rayonsUnlocked({ furthest: 0, lastPanelIndex: 3 }), false);
  assert.equal(marks.rayonsUnlocked({ furthest: 2, lastPanelIndex: 3 }), false);
  assert.equal(marks.rayonsUnlocked({ furthest: 3, lastPanelIndex: 3 }), true);
  assert.equal(marks.rayonsUnlocked({ furthest: 0, lastPanelIndex: 3, replay: true }), true);
  assert.equal(marks.rayonsUnlocked({ furthest: 5, lastPanelIndex: -1 }), false, 'no panel, no toggle');
  // off by default, and no storage is not an error
  assert.equal(marks.readRayons(), false);
  assert.doesNotThrow(() => marks.writeRayons(true));
});

test('a marked line: whole word buttons carry the mark, and the form is announced once', () => {
  const html = renderToStaticMarkup(
    h(FrenchLine, {
      text: 'Je suis allé au marché.',
      idPrefix: 'p1-l0',
      onWord: () => {},
      marks: [{ start: 4, end: 10 }],
      marksLabel: 'Today’s rule: suis allé',
      marksLang: 'en',
    }),
  );
  assert.match(html, /<button[^>]*data-mark="rule"[^>]*>suis<\/button>/);
  assert.match(html, /<button[^>]*data-mark="rule"[^>]*>allé<\/button>/);
  assert.match(html, /<span data-mark="rule"> <\/span>/, 'the gap of the form');
  assert.doesNotMatch(html, /<button[^>]*data-mark="rule"[^>]*>Je<\/button>/);
  assert.equal((html.match(/Today’s rule/g) || []).length, 1, 'announced once per line');
  assert.match(html, /aria-describedby="p1-l0-rx"/);
  assert.match(html, /<span class="fr-sr" id="p1-l0-rx" lang="en">/);
  // without marks the line is exactly what it was
  const plain = renderToStaticMarkup(h(FrenchLine, { text: 'Je suis allé au marché.', idPrefix: 'p1-l0', onWord: () => {} }));
  assert.doesNotMatch(plain, /data-mark|aria-describedby|fr-sr/);
});

// --- 4. the story model and the reader ----------------------------------------------

const EPISODE = {
  id: 'scene-rx',
  scene_id: 'scene-rx',
  serial_thread_id: 't',
  serial_episode_id: null,
  journey_id: 'j',
  title_fr: 'Le marché',
  status: 'available',
  chapter: null,
  panel_index: 0,
  grammar_focus: { unit_id: 'pc', title_fr: 'Le passé composé', title_native: 'The perfect tense', woven: true },
  panels: [
    {
      id: 'p1', index: 0, narration_fr: 'Au marché.',
      dialogue: [{ character_id: 'romy', text_fr: ' Je suis allé au marché.', grammar_marks: [{ unit_id: 'pc', start: 4, end: 13 }] }],
      image_url: null, image_status: 'unavailable',
    },
    {
      id: 'p2', index: 1, narration_fr: '',
      dialogue: [{ character_id: 'marin', text_fr: 'Et moi, non.' }],
      image_url: null, image_status: 'unavailable',
    },
  ],
  resolution: null,
};

test('the model carries the focus unit’s marks and names the rule in the chrome language', () => {
  const stages = model.buildStoryStages(EPISODE);
  assert.deepEqual(stages[0].lines[0].marks, [{ start: 3, end: 12 }]);
  assert.equal('marks' in stages[1].lines[0], false, 'an unmarked line carries nothing');
  assert.equal(model.storyRayonsTitle(EPISODE, 'en'), 'The perfect tense');
  assert.equal(model.storyRayonsTitle(EPISODE, 'fr'), 'Le passé composé');
  assert.equal(model.storyRayonsTitle(EPISODE, null), 'Le passé composé');
  const unmarked = { ...EPISODE, panels: EPISODE.panels.map((p) => ({ ...p, dialogue: p.dialogue.map(({ grammar_marks, ...d }) => d) })) };
  assert.equal(model.storyRayonsTitle(unmarked, 'en'), null, 'no marks, no toggle');
  assert.equal(model.storyRayonsTitle({ ...EPISODE, grammar_focus: undefined }, 'en'), null, 'older payloads');
});

function renderReader({ furthest, filed = false }) {
  const stages = model.buildStoryStages(EPISODE);
  return renderToStaticMarkup(
    h(FeuilletonReader, {
      episodeLabel: 'Épisode',
      title: 'Le marché',
      stages,
      index: 0,
      furthest,
      onIndexChange: () => {},
      answers: {},
      setAnswer: () => {},
      onSubmit: () => {},
      submittingTask: null,
      attemptsByTask: {},
      submitError: null,
      liveTaskId: null,
      filed,
      panelVariant: () => 'line',
      language: 'en',
      rayonsTitle: 'The perfect tense',
    }),
  );
}

test('the reader bar offers «Rayons X» only once the page has been read, off by default', () => {
  const first = renderReader({ furthest: 0 });
  assert.doesNotMatch(first, /fr-chip--rayons/, 'not during the first read');
  const read = renderReader({ furthest: 1 });
  assert.match(read, /class="fr-chip fr-chip--rayons" aria-pressed="false"/);
  assert.match(read, /aria-label="Show today’s rule in the page"/);
  assert.doesNotMatch(read, /data-mark="rule"/, 'off by default: no marks until asked');
  assert.doesNotMatch(read, /fr-rayons-legend/);
  assert.match(renderReader({ furthest: 0, filed: true }), /fr-chip--rayons/, 'a replay has it at once');
});
