// node --test components/atelier-v2/journey/rule-step.test.js
//
// WP-L4 — the Règle step of an introduction day.
//
//   1. the rule card renders in its intro variant: the French example is the
//      screen's one Garamond line, the rule is in the learner's language, and
//      «Essayer» is the one primary;
//   2. a card the client cannot draw still lets the learner through;
//   3. the session renders it, and the day mark counts it with the scene.

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
const { journeyCopy } = require('./journey-copy.ts');
const { STEP_SHAPE } = require('./day-mark.ts');

const h = React.createElement;

function ruleStep(card) {
  return {
    id: 'rule-1',
    ordinal: 3,
    kind: 'rule',
    status: 'active',
    estimated_seconds: 33,
    assistance_used: [],
    prompt: {
      concept_id: 12,
      title_native: 'I am, you are: subject pronouns and être',
      title_fr: 'Je suis, tu es : les pronoms et être',
      rule_card: card,
    },
  };
}

const CARD = {
  example: { fr: "[Je suis] Margaux et [vous êtes] le nouveau voisin ?" },
  rule: {
    en: 'Être means to be: je suis, tu es, il est, nous sommes, vous êtes, ils sont.',
    de: 'Être heißt sein: je suis, tu es, il est, nous sommes, vous êtes, ils sont.',
  },
  pattern: { kind: 'rows', rows: [{ shape: 'none', label: '', fr: 'Je suis étudiante.' }] },
  contrast: { wrong: 'Je es français.', right: 'Je suis français.' },
};

function render(step, language) {
  return renderToStaticMarkup(
    h(RuleStepView, { step, copy: journeyCopy(language), busy: false, language, onContinue: () => {} }),
  );
}

test('the rule card is the intro variant, in the learner’s language, with one Garamond line', () => {
  const html = render(ruleStep(CARD), 'de');
  assert.match(html, /data-variant="intro"/);
  assert.match(html, /Regel des Tages/, 'chrome in the learner’s language');
  assert.match(html, /Être heißt sein/);
  assert.doesNotMatch(html, /Être means to be/);
  assert.equal((html.match(/av2-headline/g) || []).length, 1, 'one Garamond line per screen');
  assert.match(html, /<span class="rc-mark">Je suis<\/span>/);
  assert.match(html, /Je es français/);
  assert.match(html, /href="\/grammar\?concept=12"|Warum\?/);
  assert.match(html, />Essayer</, 'the one primary advances to the guided items');
});

test('a card the client cannot draw still lets the learner through', () => {
  const html = render(ruleStep({ rule: {} }), 'en');
  assert.match(html, /les pronoms et être/);
  assert.equal((html.match(/av2-headline/g) || []).length, 1);
  assert.match(html, /av2-btn/);
});

test('the session renders the rule step and the mark draws it as the scene', () => {
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  assert.match(session, /step\.kind === 'rule'/);
  assert.match(session, /<RuleStepView/);
  assert.equal(STEP_SHAPE.rule, STEP_SHAPE.scene);
});
