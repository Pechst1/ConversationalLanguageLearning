// node --test components/epreuve/forge-reading.test.js
//
// Owner, 2026-11-13 — a calmer reading design for La Forge's free-sentence and miss
// screens, inside av2 (no new font, no new colour):
//
//   1. one voice per level: the situation and the instruction are quiet sans; only
//      the quoted line is Garamond italic, set as speech from its speaker
//      (lib/prompt-parts.ts, EpScenePrompt), on the free-sentence and produce items;
//   2. the miss card: one reason on the card, the rest behind «More», the task as one
//      quiet line (never a third card);
//   3. the counter is sentence case and emphatic only when out of range;
//   4. tokens only, and prose held to a reading measure.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const Ep = require('./Epreuve.tsx');
const { promptParts } = require('@/lib/prompt-parts.ts');
const { epreuveCopy } = require('./epreuve-copy.ts');
const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
const EPREUVE = fs.readFileSync(path.join(WEB_ROOT, 'components/epreuve/Epreuve.tsx'), 'utf8');

const slice = (src, from, to) => src.slice(src.indexOf(from), src.indexOf(to, src.indexOf(from)));

test('the free-sentence and produce items cut their prompt at its quote', () => {
  const ladder = slice(PAGE, 'function OutputLadderPanel(', 'function ProducePanel(');
  assert.match(ladder, /const split = promptParts\(promptText\)/);
  assert.match(ladder, /<EpScenePrompt[\s\S]*split=\{split\}/);
  // The speaker is named once: in the speech figure when the line is split.
  assert.match(ladder, /character\.name && !speakerInFigure/);
  // The prompt's own instruction replaces the generic round cue.
  assert.match(ladder, /split\?\.instruction \? item\.instruction \|\| undefined/);
  const produce = slice(PAGE, 'function ProducePanel(', '\n}\n');
  assert.match(produce, /<EpScenePrompt[\s\S]*split=\{promptParts\(promptText\)\}/);
});

test('only the quoted line is Garamond; the situation and instruction are sans prose', () => {
  const component = slice(EPREUVE, 'export function EpScenePrompt(', 'export function Blank(');
  assert.match(component, /if \(!split\) return <EpPrompt/);
  assert.match(component, /<figure className="ep-speech">/);
  assert.match(component, /<blockquote className="ep-speech__line av2-fr" lang="fr">/);
  const css = (selector) => {
    const at = EPREUVE.indexOf(`${selector} {`);
    assert.ok(at > 0, `${selector} is styled`);
    return EPREUVE.slice(at, EPREUVE.indexOf('}', at));
  };
  assert.match(css('.av2 .ep-speech__line'), /font-family: var\(--av2-serif\)/);
  assert.match(css('.av2 .ep-speech__line'), /font-style: italic/);
  assert.match(EPREUVE, /\.av2 \.ep-situation,\n\.av2 \.ep-instruction \{[^}]*font-family: var\(--av2-sans\)[^}]*font-style: normal/);
  assert.match(css('.av2 .ep-prompt--scene'), /max-width: 36em/);
});

test('French speech is in guillemets with French spacing in every chrome language', () => {
  const NNBSP = ' ';
  const prompts = {
    de: 'Auf dem Markt fragt dich die Verkäuferin: „Tu peux payer par carte ?“ Antworte mit dem Infinitiv.',
    en: 'At the market the stallholder asks you: “Tu peux payer par carte ?” Answer with the infinitive.',
    fr: 'Au marché, la vendeuse te demande : « Tu peux payer par carte ? » Réponds avec l’infinitif.',
  };
  for (const [lang, prompt] of Object.entries(prompts)) {
    const html = renderToStaticMarkup(React.createElement(Ep.EpScenePrompt, { text: prompt, split: promptParts(prompt), lang }));
    const line = /<blockquote[^>]*>([^<]*)<\/blockquote>/.exec(html);
    assert.ok(line, `${lang}: the quoted line is set as speech`);
    assert.equal(line[1], `«${NNBSP}Tu peux payer par carte${NNBSP}?${NNBSP}»`, `${lang}: ${line[1]}`);
    assert.doesNotMatch(line[1], /[„“”"]/);
  }
});

test('the button under a repair line says it checks, as the item screen does', () => {
  for (const lang of ['de', 'en', 'fr']) {
    const t = epreuveCopy(lang);
    assert.equal(t.repair_submit, t.check, lang);
    assert.equal(t.repair_submitting, t.checking, lang);
  }
});

test('the card counts only the corrections it shows, never the task note', () => {
  const free = slice(PAGE, 'export function feedbackFromFreeformCorrection(', 'function feedbackForExercise(');
  assert.match(free, /const lineErrata = errata\.filter\(\(item\) => item\.task_error_type !== 'task_compliance'\)/);
  assert.match(free, /shownCount > 1\s*\? fill\(t\.corrections_n, \{ n: shownCount \}\)/);
  assert.doesNotMatch(free, /n: whyLines\.length/);
});

test('the counter is sentence case, emphatic only when out of range', () => {
  assert.match(PAGE, /className="word-count" data-state=\{wordRangeState\(wordCount\(answer\), item\.min_words, item\.max_words\)\}/);
  assert.match(PAGE, /className="word-count" data-state=\{wordRangeState\(wordCount\(answer\), produce\.min_words, produce\.max_words\)\}/);
  const at = EPREUVE.indexOf('.av2 .word-count {');
  const rule = EPREUVE.slice(at, EPREUVE.indexOf('}', at));
  assert.match(rule, /text-transform: none/);
  assert.match(rule, /letter-spacing: normal/);
  assert.match(rule, /font-weight: 400/);
  assert.match(EPREUVE, /\.av2 \.word-count\[data-state='over'\] \{[^}]*font-weight: 700/);
});

test('the miss card: one reason, the rest behind «More», the task as one quiet line', () => {
  const moment = slice(PAGE, 'export function ExerciseFeedbackMoment(', 'function ConceptRulePanel(');
  // No «Task» card any more: the av2-surface with the task label is gone.
  assert.doesNotMatch(moment, /<p className="av2-label">\{t\.task\}<\/p>/);
  assert.match(moment, /<EpTaskLine label=\{t\.task\}>\{taskNote\}<\/EpTaskLine>/);
  // The reason and the repair hint are deduplicated; the first is the card's line.
  assert.match(moment, /const \[reason, \.\.\.rest\] = dedupeNotes\(\[\.\.\.whyText\.split\('\\n'\), hintText\]\)\s*\.filter\(\(note\) => !taskSaid\.has\(note\.trim\(\)\)\)/);
  // With the solution on screen the hint waits behind «More»; while a repair is open it
  // is the next action and stays on the card.
  assert.match(moment, /const repairHint = solutionOnScreen \? '' : rest\.join\(' '\)/);
  assert.match(moment, /more=\{solutionOnScreen && rest\.length \? <EpMore label=\{t\.more\}>/);
  assert.doesNotMatch(moment, /repair=\{display\(printableWhy\(issue\.repair_hint/);
});

test('the new CSS uses tokens only', () => {
  const start = EPREUVE.indexOf('/* Owner 2026-11-13: one voice per level. The situation');
  const block = EPREUVE.slice(start, EPREUVE.indexOf('.av2 .ep-opts', start));
  assert.doesNotMatch(block, /#[0-9a-f]{3,6}\b/i);
  assert.doesNotMatch(block, /text-transform: uppercase/);
});
