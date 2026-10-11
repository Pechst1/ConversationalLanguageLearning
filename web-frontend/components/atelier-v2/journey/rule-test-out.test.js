// node --test components/atelier-v2/journey/rule-test-out.test.js
//
// SPEED-3 — «Je connais déjà — vérifier» in the Règle step.
//
//   1. the card offers the check as a quiet second action, in the learner's
//      language, never a second primary;
//   2. an item is drawn with the journey's inputs and answered as the forge's
//      attempt (round, mode, exercise id, payload shape);
//   3. a pass confirms and continues; a fail (or a check that could not run)
//      shows the card with one line and no second offer;
//   4. the check never leaves the journey: it starts the short épreuve with
//      `source: 'journey'` and posts to the séance's attempts.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { RuleStepView } = require('./JourneySteps.tsx');
const { RuleTestOutItem } = require('./RuleTestOut.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const model = require('./rule-test-out.ts');

const h = React.createElement;
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ').trim();

const STEP = {
  id: 'rule-1',
  ordinal: 3,
  kind: 'rule',
  status: 'active',
  estimated_seconds: 33,
  assistance_used: [],
  prompt: {
    concept_id: 15,
    title_native: 'Negation with de',
    title_fr: 'La négation : pas de',
    rule_card: {
      example: { fr: 'Je [ne bois pas de] café.' },
      rule: { en: 'After a negation, du/de la/des become de.', de: 'Nach einer Verneinung wird du/de la/des zu de.' },
      pattern: { kind: 'rows', rows: [{ shape: 'none', label: '', fr: 'Je n’ai pas de voiture.' }] },
      contrast: { wrong: 'Je ne bois pas du café.', right: 'Je ne bois pas de café.' },
    },
  },
};

function renderStep(language, initialCheck) {
  return renderToStaticMarkup(
    h(RuleStepView, { step: STEP, copy: journeyCopy(language), busy: false, language, onContinue: () => {}, initialCheck }),
  );
}

const CLASSIFY = {
  position: 0, concept_id: 15, rung: 1, rung_name: 'discriminate', role: 'today', round: 'recognize', mode: 'classify',
  item_id: 'neg-classify-1', item_index: 0,
  item: {
    id: 'neg-classify-1', prompt: 'Je ne pas me lève tôt.', labels: ['Correct', 'À corriger'],
    goal_native: 'Is this sentence right, or does it need correcting?',
    goal_l10n: { en: 'Is this sentence right, or does it need correcting?', de: 'Ist dieser Satz richtig, oder muss er korrigiert werden?' },
  },
};
const REWRITE = {
  position: 1, concept_id: 15, rung: 3, rung_name: 'transform', role: 'today', round: 'transform', mode: 'rewrite',
  item_id: 'neg-repair-1', item_index: 0,
  item: { id: 'neg-repair-1', source_fr: 'Margaux ne pas se prépare pour la fête.', expected_answer: 'Margaux ne se prépare pas pour la fête.',
    goal_l10n: { en: 'Correct it.' } },
};
const CONVERSATION = {
  position: 2, concept_id: 15, rung: 5, rung_name: 'free_use', role: 'today', round: 'conversation', mode: 'conversation',
  item_id: 'neg-conversation', item_index: 0,
  item: { id: 'neg-conversation', prompt: 'Message received: « Tu as encore du café ? » Reply with a negated quantity.' },
};
const BANK = {
  position: 0, concept_id: 15, rung: 2, rung_name: 'build', role: 'today', round: 'recognize', mode: 'word_bank',
  item_id: 'neg-build-1', item_index: 0,
  item: { id: 'neg-build-1', prompt: 'Build the sentence with the chips.', tokens: ['pas', 'Je', 'ne', 'dis', '.'] },
};
const VIEW = { mode: 'test_out', length: 3, answered: 1, counted: 1, finished: false, next: REWRITE, result: null, rules: [] };

test('the card offers the check quietly, in the learner’s language', () => {
  const de = renderStep('de');
  assert.match(de, /Kenne ich schon — kurz prüfen/);
  assert.match(de, /data-tone="quiet"[^>]*><span>Kenne ich schon/, 'a quiet action, not a second primary');
  assert.equal((de.match(/data-tone="primary"/g) || []).length, 0, 'the card’s «Essayer» stays the one primary');
  assert.match(renderStep('en'), /Already know this\? Check in 3 items/);
  assert.match(renderStep('fr'), /Je connais déjà — vérifier/);
  assert.doesNotMatch(de, /text-transform:\s*uppercase/);
});

test('a pass confirms the unit is held and continues the day', () => {
  const html = renderStep('en', 'passed');
  assert.match(html, /data-check="passed"/);
  assert.match(html, /The rule is yours/);
  assert.match(html, /data-tone="primary"[^>]*><span>Continue/);
  assert.doesNotMatch(html, /Check in 3 items/);
  assert.doesNotMatch(html, /data-variant="intro"/, 'no card to read after a pass');
});

test('a fail falls back to the card, says so once, and is not re-offered', () => {
  const html = renderStep('de', 'failed');
  assert.match(html, /data-variant="intro"/, 'the rule card is read as usual');
  assert.match(html, /Deine Antworten zählen trotzdem/);
  assert.doesNotMatch(html, /Kenne ich schon/);
  const broke = renderStep('en', 'unavailable');
  assert.match(broke, /could not start\. Here is the rule/);
  assert.match(broke, /data-variant="intro"/);
});

test('items map onto the journey’s inputs', () => {
  assert.deepEqual(model.testOutInput(CLASSIFY), { kind: 'choice', options: ['Correct', 'À corriger'] });
  assert.deepEqual(model.testOutInput(BANK), { kind: 'tiles', tokens: ['pas', 'Je', 'ne', 'dis', '.'] });
  assert.deepEqual(model.testOutInput(REWRITE), { kind: 'text', sourceFr: 'Margaux ne pas se prépare pour la fête.' });
  assert.deepEqual(model.testOutInput(CONVERSATION), { kind: 'text', sourceFr: null });
  assert.deepEqual(model.testOutPrompt(CLASSIFY, 'de'), {
    goal: 'Ist dieser Satz richtig, oder muss er korrigiert werden?',
    lineFr: 'Je ne pas me lève tôt.',
  });
  assert.equal(model.testOutPrompt(BANK, 'en').lineFr, null, 'a word bank’s generic prompt is not a French line');
  assert.match(model.testOutPrompt(CONVERSATION, 'en').goal, /Reply with a negated quantity/);
});

test('answers are the forge’s attempts', () => {
  assert.deepEqual(model.testOutSubmission(CLASSIFY, 'À corriger'), {
    concept_id: 15, round: 'recognize', mode: 'classify', exercise_id: 'forge:15:recognize:neg-classify-1',
    answer_payload: { answers: { 'neg-classify-1': 'À corriger' } },
  });
  assert.deepEqual(model.testOutSubmission(BANK, ['Je', 'ne', 'dis', 'pas', '.']).answer_payload, {
    answers: { 'neg-build-1': ['Je', 'ne', 'dis', 'pas', '.'] },
  });
  const rewrite = model.testOutSubmission(REWRITE, 'Margaux ne se prépare pas pour la fête.');
  assert.equal(rewrite.mode, 'rewrite');
  assert.deepEqual(rewrite.answer_payload, { answers: { 'neg-repair-1': 'Margaux ne se prépare pas pour la fête.' } });
  assert.deepEqual(model.testOutSubmission(CONVERSATION, 'Non, je n’ai plus de café.').answer_payload, {
    text: 'Non, je n’ai plus de café.',
  });
  assert.equal(model.testOutAnswerReady({ kind: 'text', sourceFr: null }, '  '), false);
  assert.equal(model.testOutAnswerReady({ kind: 'tiles', tokens: ['a'] }, ['t0']), true);
});

test('the outcome and the count come from the forge view', () => {
  assert.equal(model.testOutOutcome(VIEW), 'running');
  const passed = { ...VIEW, finished: true, next: null, result: { passed: true, correct: 3, total: 3 } };
  assert.equal(model.testOutOutcome(passed), 'passed');
  assert.equal(model.testOutOutcome({ ...passed, result: { passed: false } }), 'failed');
  assert.deepEqual(model.testOutProgress(VIEW), { position: 2, length: 3 });
  assert.equal(model.testOutView({}), null);
  assert.equal(model.testOutView(VIEW), VIEW);
});

test('an item renders one French line, the input, and one primary; a verdict says why', () => {
  const copy = model.ruleTestOutCopy('en');
  const item = (next, extra = {}) =>
    renderToStaticMarkup(
      h(RuleTestOutItem, {
        next, view: { ...VIEW, answered: next.position }, copy, language: 'en', answer: '', feedback: null, pending: false,
        onAnswer: () => {}, onCheck: () => {}, onNext: () => {}, ...extra,
      }),
    );
  const classify = item(CLASSIFY);
  assert.match(text(classify), /Quick check · 1 of 3/);
  assert.equal((classify.match(/av2-headline/g) || []).length, 1);
  assert.match(classify, /role="radiogroup"/);
  assert.equal((classify.match(/data-tone="primary"/g) || []).length, 1);
  assert.match(classify, /disabled=""[^>]*data-tone="primary"[^>]*><span>Check/);
  const rewrite = item(REWRITE, { answer: 'x', feedback: { correct: false, expected: 'Margaux ne se prépare pas pour la fête.' } });
  assert.match(rewrite, /textarea/);
  assert.match(text(rewrite), /Not quite/);
  assert.match(text(rewrite), /Expected: Margaux ne se prépare pas/);
  assert.match(rewrite, /data-tone="primary"[^>]*><span>Next/);
  const last = item(CONVERSATION, { answer: 'x', feedback: { correct: true, expected: null } });
  assert.match(last, /><span>See the result</);
  assert.match(item(BANK), /Tap the words in order/);
});

test('the check runs inside the journey: short épreuve, journey source, séance attempts', () => {
  const source = fs.readFileSync(path.join(__dirname, 'RuleTestOut.tsx'), 'utf8');
  assert.match(source, /startForgeTestOut\(conceptId, \{ short: true, source: 'journey' \}\)/);
  assert.match(source, /submitAtelierAttempt\(/);
  assert.doesNotMatch(source, /router\.push|window\.location|href=/, 'never leaves the journey');
  const api = fs.readFileSync(path.join(WEB_ROOT, 'services/api.ts'), 'utf8');
  assert.match(api, /startForgeTestOut\(\s*conceptId: number,\s*options: \{ short\?: boolean; source\?:/);
  const cahier = fs.readFileSync(path.join(WEB_ROOT, 'pages/grammar.tsx'), 'utf8');
  assert.match(cahier, /startForgeTestOut\(concept\.id\)/, 'the Cahier offers the test-out for every unit');
});
