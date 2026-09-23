// node --test lib/rule-card.test.js
//
// WP-L10 — the rule card v2:
//   1. the markup: [x] carries the rule (red), {x} is silent (grey);
//   2. the learner's language is picked, English is the floor;
//   3. the intro card has exactly one Garamond headline, and it is French;
//   4. the inline card has none (the exercise prompt is the headline);
//   5. the stylesheet draws the card with --av2 tokens only.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { parseMarked, plainText, pick, usableCard } = require('./rule-card');
const { RuleCard } = require('@/components/atelier-v2/rule/RuleCard');

const cards = JSON.parse(
  fs.readFileSync(path.join(WEB_ROOT, '..', 'app', 'data', 'grammar_rule_cards.json'), 'utf8'),
).cards;

test('the markup splits rule, silent and plain parts', () => {
  assert.deepEqual(parseMarked('habit{e}'), [
    { text: 'habit', tone: 'plain' },
    { text: 'e', tone: 'silent' },
  ]);
  assert.deepEqual(parseMarked('[le] café'), [
    { text: 'le', tone: 'mark' },
    { text: ' café', tone: 'plain' },
  ]);
  assert.equal(plainText('Une petit[e] table blanch[e].'), 'Une petite table blanche.');
});

test("the learner's language is picked, English is the floor", () => {
  assert.equal(pick({ en: 'A', de: 'B' }, 'de'), 'B');
  assert.equal(pick({ en: 'A' }, 'fr'), 'A');
  assert.equal(usableCard(cards.FR_A1_NOUN_001), true);
  assert.equal(usableCard({ example: { fr: '' }, rule: {} }), false);
});

const render = (props) => renderToStaticMarkup(React.createElement(RuleCard, props));

test('the intro card has one Garamond headline, and it is the French example', () => {
  const html = render({ card: cards.FR_A1_NOUN_001, language: 'en', variant: 'intro', conceptId: 1, onDone: () => {} });
  assert.equal((html.match(/av2-headline/g) || []).length, 1);
  assert.match(html, /<h2 class="av2-headline rc-example" lang="fr">Une petit<span class="rc-mark">e<\/span>/);
  assert.match(html, /The noun decides\./);
  assert.match(html, /Essayer/);
  assert.doesNotMatch(html, /Le schéma|Le contrôle|Avoid:/);
});

test('a German learner reads the rule in German, with a silent-ending table', () => {
  const html = render({ card: cards.FR_A1_VERB_001, language: 'de', variant: 'intro', conceptId: 2, onDone: () => {} });
  assert.match(html, /Streiche -er/);
  assert.match(html, /habit<span class="rc-silent">ent<\/span>/);
  assert.match(html, /habit<span class="rc-mark">ez<\/span>/);
  assert.match(html, /Übersetzen/);
});

test('the inline card sets no headline (the exercise prompt is the one headline)', () => {
  const html = render({ card: cards.FR_A1_NOUN_001, language: 'en', variant: 'inline', conceptId: 1 });
  assert.doesNotMatch(html, /av2-headline/);
  assert.doesNotMatch(html, /Essayer/);
});

test('the card is drawn with av2 tokens only', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles', 'atelier-v2.css'), 'utf8');
  const block = css.slice(css.indexOf('WP-L10 — the rule card v2'), css.indexOf('.av2 .rc-done'));
  assert.ok(block.length > 200);
  assert.doesNotMatch(block, /#[0-9a-f]{3,6}\b/i, 'no raw hex colours');
  assert.doesNotMatch(block, /stroke:/, 'shapes are never outlined');
});
