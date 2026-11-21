// node --test components/atelier-v2/rule/rule-card-explains-in-mother-tongue.test.js
//
// R4 (walk of 19 Nov 2026; owner decision 18 Nov 2026) — the rule card's chrome is
// French from B1, but what it *explains* (the rule, its note, the translation, the
// «why») is in the learner's own language at every level. A B1.1 English learner read
// «Après pour, sans et avant de, on met l'infinitif, jamais une forme en -ant.» on
// the day's rule step and in La Forge. Below B1 the chrome is the learner's language
// and nothing changes.

const assert = require('node:assert/strict');
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

const { RuleCard } = require('./RuleCard.tsx');
const { RULE_CARD_COPY } = require('../../../lib/rule-card.ts');
const { explanationLanguage } = require('../../../lib/language-rule.ts');

const RULE = {
  en: 'After pour, sans and avant de, use the infinitive, never an -ant form.',
  de: 'Nach pour, sans und avant de steht der Infinitiv, nie eine Form auf -ant.',
  fr: "Après pour, sans et avant de, on met l'infinitif, jamais une forme en -ant.",
};
const CARD = {
  example: {
    fr: 'Avant de [partir], elle a fermé la porte.',
    tr: { en: 'Before leaving, she closed the door.', de: 'Bevor sie ging, schloss sie die Tür.' },
  },
  rule: RULE,
};

function render(language, explainLanguage) {
  return renderToStaticMarkup(
    React.createElement(RuleCard, { card: CARD, language, explainLanguage, variant: 'intro', onDone: () => {} }),
  );
}

const escaped = (text) => text.replace(/'/g, '&#x27;');

test('the explanation language is the chrome below B1 and the mother tongue from B1', () => {
  assert.equal(explanationLanguage('de', 'de'), 'de');
  assert.equal(explanationLanguage('en', 'en'), 'en');
  assert.equal(explanationLanguage('fr', 'en'), 'en');
  assert.equal(explanationLanguage('fr', 'de'), 'de');
  assert.equal(explanationLanguage('fr', 'es'), 'en');
});

for (const native of ['en', 'de']) {
  test(`a B1 card has French chrome and explains in ${native}`, () => {
    const html = render('fr', explanationLanguage('fr', native));
    assert.ok(html.includes(escaped(RULE[native])), html);
    assert.ok(!html.includes(escaped(RULE.fr)), 'the rule is never explained in French to a non-French learner');
    // The chrome stays French: the card's eyebrow.
    assert.ok(html.includes(escaped(RULE_CARD_COPY.fr.eyebrow)) || html.includes(RULE_CARD_COPY.fr.eyebrow));
    assert.ok(!html.includes(RULE_CARD_COPY[native].eyebrow), 'never a second chrome language on the card');
  });
}

test('an A1 card is unchanged: chrome and explanation in the learner language', () => {
  const html = render('de', undefined);
  assert.ok(html.includes(RULE.de));
  assert.ok(html.includes(RULE_CARD_COPY.de.eyebrow) || html.includes(escaped(RULE_CARD_COPY.de.eyebrow)));
});
