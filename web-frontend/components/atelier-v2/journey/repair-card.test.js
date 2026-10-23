// node --test components/atelier-v2/journey/repair-card.test.js
//
// #278 (live walk 22 Oct): a repair drill was the bare word «Sommer» under «Write what
// you said, correctly», with no sentence and no rule. The card now prints the learner's
// own sentence with the wrong part marked, and the goal line names the rule.
//
// #282 (live walk 22 Oct): a cameo's bubble sat on the prompt and the answer box, and
// «Compare» was behind the verdict sheet. Both are pure geometry (lib/cameo-placement.ts,
// lib/sheet-clearance.ts), read by the layer and the page.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
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

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const frame = require('./drill-frame.ts');
const steps = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const placement = require('@/lib/cameo-placement.ts');
const clearance = require('@/lib/sheet-clearance.ts');

const h = React.createElement;
const decode = (html) =>
  html
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/[  ]/g, ' ');

function repairStep(extra = {}) {
  return {
    id: 'step-repair',
    ordinal: 6,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 40,
    assistance_used: [],
    prompt: {
      task_type: 'short_answer',
      instruction_native: 'Write this correctly in French.',
      prompt_fr: 'Nous Sommer contents ici.',
      options: [],
      target: { kind: 'error', id: 'e-1', label_fr: '', label_native: null },
      optional: false,
      help_available: ['hint', 'solution'],
      goal_native: 'Write what you said, correctly. Rule: Le verbe être au présent',
      source_fr: 'Nous Sommer contents ici.',
      slip_fr: 'Sommer',
      ...extra,
    },
  };
}

const props = (step) => ({
  step,
  copy: journeyCopy('en'),
  busy: false,
  feedback: { kind: 'idle' },
  help: null,
  onHelp() {},
  onSubmit() {},
  onContinue() {},
});

// ---------------------------------------------------------------------------
// #278 · the repair card
// ---------------------------------------------------------------------------

test('#278 · the sentence is cut around the slip, whole words, any case', () => {
  assert.deepEqual(frame.slipSegments('Nous Sommer contents ici.', 'sommer'), [
    { text: 'Nous ', slip: false },
    { text: 'Sommer', slip: true },
    { text: ' contents ici.', slip: false },
  ]);
  assert.deepEqual(frame.slipSegments('Sommer', 'Sommer'), [{ text: 'Sommer', slip: true }]);
  // A word inside another word is not the slip; a slip the sentence lacks marks nothing.
  assert.equal(frame.slipSegments('Nous sommerons ici.', 'sommer'), null);
  assert.equal(frame.slipSegments('Nous sommes ici.', 'sommer'), null);
  assert.equal(frame.slipSegments('Nous sommes ici.', ''), null);
  assert.equal(frame.slipSegments(null, 'sommer'), null);
});

test('#278 · a repair prints the learner’s sentence with the wrong part marked, and names the rule', () => {
  const html = decode(renderToStaticMarkup(h(steps.RecallStepView, props(repairStep()))));
  assert.match(html, /Nous <mark class="av2-slip">Sommer<\/mark> contents ici\./);
  assert.match(html, /Rule: Le verbe être au présent/);
  assert.ok(!/<h2[^>]*>Sommer<\/h2>/.test(html), 'not a bare word');
});

test('#278 · a repair without a marked slip prints its sentence plain', () => {
  const html = decode(renderToStaticMarkup(h(steps.RecallStepView, props(repairStep({ slip_fr: undefined })))));
  assert.ok(html.includes('Nous Sommer contents ici.'));
  assert.ok(!html.includes('av2-slip'));
});

// ---------------------------------------------------------------------------
// #282 · nothing over the prompt, the action above the sheet
// ---------------------------------------------------------------------------

// The miss screen of the live walk at 375 × 812: the item's prompt and options, the
// correction under them, and the verdict sheet stuck to the bottom.
const ZONES = [
  { left: 20, right: 355, top: 205, bottom: 520 },
  { left: 0, right: 375, top: 551, bottom: 794 },
];

test('#282 · a bubble stands in the free band above the prompt, not on it', () => {
  const bubble = { left: 59, right: 269, height: 100 };
  const top = placement.clearBubbleTop(bubble, ZONES, 812, 232);
  assert.notEqual(top, null);
  assert.ok(top + bubble.height <= 205, `the bubble ends at ${top + bubble.height}, on the prompt that starts at 205`);
  assert.ok(top >= 8, 'and it stays on the screen');
});

test('#282 · a bubble that fits where it stands is not moved, and with no free place it does not come', () => {
  const bubble = { left: 59, right: 269, height: 40 };
  assert.equal(placement.clearBubbleTop(bubble, [], 812, 232), 232);
  const wall = [{ left: 0, right: 375, top: 0, bottom: 812 }];
  assert.equal(placement.clearBubbleTop(bubble, wall, 812, 232), null);
});

test('#282 · the page scrolls just far enough for the action to clear the sheet', () => {
  // «Compare» ends at 1056 under a sheet that starts at 625: scroll 443 and a margin.
  assert.equal(clearance.scrollToClearSheet(1056, 625, 12), 443);
  assert.equal(clearance.scrollToClearSheet(400, 625, 12), 0, 'already clear');
  assert.equal(clearance.scrollToClearSheet(NaN, 625), 0);
});
