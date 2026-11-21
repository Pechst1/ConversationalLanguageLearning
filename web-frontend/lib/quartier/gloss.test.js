// node --test lib/quartier/gloss.test.js
//
// P12 · a beginner can read the quarter (review of 17 Nov, finding 17): the line in the learner's
// language is on by default below B1 and remembered once switched; the first time, a note beside
// the chip says what it does; «Un exemple» (the full sentence) only after a try; and no English
// stage direction on a card for a learner whose language is not English.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const resolve = Module._resolveFilename;
Module._resolveFilename = function alias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) return resolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return resolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const gloss = require('./gloss.ts');
const { helpOnOffer } = require('./stage.ts');
const { AnswerSheet, COPY, TalkSheet } = require('../../components/quartier/QuartierScreen.tsx');

const h = React.createElement;

function memoryStore() {
  const kept = new Map();
  return { kept, getItem: (k) => (kept.has(k) ? kept.get(k) : null), setItem: (k, v) => kept.set(k, String(v)) };
}

test('the line in the learner’s language is on for an A1–A2 learner, off from B1', () => {
  assert.equal(gloss.glossByDefault('a2'), true, 'an A1 learner (the quarter reads A1 and A2 as a2)');
  assert.equal(gloss.glossByDefault('b1'), false);
  assert.equal(gloss.readGloss('a2', memoryStore()), true);
  assert.equal(gloss.readGloss('b1', memoryStore()), false);
  assert.equal(gloss.readGloss('a2', null), true, 'no storage: the default');
});

test('the learner can switch it off (or on), and the device remembers', () => {
  const s = memoryStore();
  gloss.writeGloss(false, s);
  assert.equal(s.kept.get(gloss.GLOSS_KEY), 'off');
  assert.equal(gloss.readGloss('a2', s), false, 'off stays off');
  gloss.writeGloss(true, s);
  assert.equal(gloss.readGloss('b1', s), true, 'on stays on at B1');
  const refusing = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
  assert.equal(gloss.readGloss('a2', refusing), true);
  assert.doesNotThrow(() => gloss.writeGloss(false, refusing));
  // the quarter starts from it and writes the learner's switch
  const src = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/QuartierScreen.tsx'), 'utf8');
  assert.match(src, /React\.useState\(\(\) => readGloss\(level\)\)/);
  assert.match(src, /writeGloss\(on\)/);
  assert.doesNotMatch(src, /useState\(false\);\s*\n\s*const \[soundOn/, 'no longer off for everyone');
});

test('the first time, one line beside the chip says what it does, in three languages', () => {
  const s = memoryStore();
  assert.equal(gloss.takeGlossNote(s), true);
  assert.equal(gloss.takeGlossNote(s), false, 'once');
  assert.equal(gloss.takeGlossNote(null), false);
  for (const language of ['en', 'de', 'fr']) {
    for (const state of ['on', 'off']) {
      const line = gloss.GLOSS_NOTE[language][state];
      assert.ok(line && line.length <= 70, `${language} ${state}: one line`);
    }
  }
  assert.equal(gloss.noteLanguage('de', 'a2'), 'de');
  assert.equal(gloss.noteLanguage('en', 'a2'), 'en');
  assert.equal(gloss.noteLanguage('de', 'b1'), 'fr', 'the interface is French from B1');
  const src = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/QuartierScreen.tsx'), 'utf8');
  assert.match(src, /className="qz-gloss-note"/);
});

test('«Un exemple» is not offered before the learner has tried that answer', () => {
  const offered = ['hint', 'words', 'example'];
  assert.deepEqual(helpOnOffer(offered, false), ['hint', 'words']);
  assert.deepEqual(helpOnOffer(offered, true), offered, 'asked again after a try: the example too');
  const src = fs.readFileSync(path.join(WEB_ROOT, 'lib/quartier/stage.ts'), 'utf8');
  assert.match(src, /steps: helpOnOffer\(ask\.help, again\)/);
  assert.match(src, /more: helpOnOffer\(ask\.help, again\)\[0\]/);

  // the answer sheet walked up the ladder as the stage walks it (the next step after each one given)
  const sheet = (tried) => {
    const steps = helpOnOffer(offered, tried);
    const help = [];
    const html = [];
    let more = steps[0] ?? null;
    for (;;) {
      const a = { id: 'a.turn1', kind: 'turn', char: 'gus', to: 'Gus', task: 'Sag, wer du bist.', line: null, steps, help: [...help], more, busy: false, again: tried, failed: false };
      html.push(renderToStaticMarkup(h(AnswerSheet, { a, copy: COPY.de, onSend: () => {}, onHelp: () => {} })));
      if (!more) break;
      help.push(more === 'words' ? { step: 'words', text: null, native: null, words: ['vendre'] } : { step: more, text: more === 'example' ? 'Odile est ma grand-mère.' : 'Zum Beispiel: «Odile est …»', native: null, words: [] });
      more = steps[steps.indexOf(more) + 1] ?? null;
    }
    return html.join('\n');
  };
  const first = sheet(false);
  assert.match(first, /Un indice/);
  assert.match(first, /Des mots/);
  assert.doesNotMatch(first, /Un exemple/);
  assert.doesNotMatch(first, /Odile est ma grand-mère/, 'no full sentence before a try');
  const again = sheet(true);
  assert.match(again, /Un exemple/);
  assert.match(again, /Odile est ma grand-mère/);
});

test('a stage direction written in English reaches no card but an English learner’s', () => {
  assert.equal(gloss.shownDirection('to Lila, a whisper', 'de'), null);
  assert.equal(gloss.shownDirection('crying with laughter', 'de'), null);
  assert.equal(gloss.shownDirection('to Lila, a whisper', 'en'), 'to Lila, a whisper');
  assert.equal(gloss.shownDirection(null, 'en'), null);
  assert.equal(gloss.shownDirection('  ', 'en'), null);
  const talk = {
    who: 'margaux_barman',
    char: 'margaux',
    name: 'Margaux',
    lines: [{ text: 'Voilà.', native: 'Bitte.', direction: 'setting down a glass' }],
    you: 'Un verre d’eau, s’il te plaît.',
    chips: [],
  };
  const de = renderToStaticMarkup(h(TalkSheet, { t: talk, translate: true, native: 'de', copy: COPY.de, onSay: () => {}, onClose: () => {} }));
  assert.doesNotMatch(de, /setting down a glass/);
  assert.doesNotMatch(de, /qz-direction/);
  assert.match(de, /Voilà\./);
  const en = renderToStaticMarkup(h(TalkSheet, { t: talk, translate: true, native: 'en', copy: COPY.en, onSay: () => {}, onClose: () => {} }));
  assert.match(en, /setting down a glass/);
  // the speech card too: no direction on a card but through shownDirection
  const src = fs.readFileSync(path.join(WEB_ROOT, 'components/quartier/QuartierScreen.tsx'), 'utf8');
  assert.doesNotMatch(src, /\{(line|l)\.direction\}/);
  assert.equal((src.match(/shownDirection\((line|l)\.direction, native\)/g) || []).length, 4);
});
