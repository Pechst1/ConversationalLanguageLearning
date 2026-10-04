// node --test components/atelier-v2/rule/rule-card-review.test.js
//
// WP-129 (content program D7) — the rule card as a *review*: after a tentpole's
// ending, a rule the learner met earlier, seen in a line of the page. It says
// so in the learner's language and its one action is «Continue», never
// «Essayer»: nothing is introduced, nothing is asked.

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

const CARD = {
  example: { fr: "Tu [as laissé] ton parapluie ici." },
  rule: { en: 'avoir + past participle', de: 'avoir + Partizip', fr: 'avoir + participe passé' },
  from_scene: true,
};

function render(language, review) {
  return renderToStaticMarkup(
    React.createElement(RuleCard, {
      card: CARD,
      language,
      variant: 'intro',
      review,
      onDone: () => {},
      sceneAnchor: { fr: CARD.example.fr, castId: null, name: null },
    }),
  );
}

for (const language of ['en', 'de', 'fr']) {
  test(`a review says it is one, in ${language}, and asks nothing`, () => {
    const copy = RULE_CARD_COPY[language];
    const html = render(language, true);
    assert.ok(copy.reviewEyebrow && copy.reviewDone);
    assert.ok(html.includes(copy.reviewEyebrow.replace(/’/g, '&#x27;')) || html.includes(copy.reviewEyebrow));
    assert.ok(!html.includes(copy.eyebrow), 'never «the rule of today»');
    assert.ok(html.includes(`>${copy.reviewDone}<`));
    assert.ok(!html.includes('>Essayer<'));
    assert.match(html, /data-review="true"/);
  });
}

test('the day’s new rule is unchanged', () => {
  const html = render('en', false);
  assert.ok(html.includes(RULE_CARD_COPY.en.eyebrow.replace(/'/g, '&#x27;')));
  assert.ok(html.includes('>Essayer<'));
  assert.doesNotMatch(html, /data-review/);
});
