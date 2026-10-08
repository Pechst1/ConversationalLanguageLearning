// node --test lib/french-typography.test.js
//
// WP-82 — French «!» and «?» never wrap onto their own line: a narrow
// no-break space (U+202F) before « ; : ! ? » and inside « ».

const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const { frenchSpacing, frenchQuote, NNBSP } = require('./french-typography.ts');

const N = NNBSP;

test('an ordinary space before ; : ! ? becomes a narrow no-break space', () => {
  assert.equal(frenchSpacing('Tu viens ?'), `Tu viens${N}?`);
  assert.equal(frenchSpacing('Bonjour !'), `Bonjour${N}!`);
  assert.equal(frenchSpacing('Voilà : un café'), `Voilà${N}: un café`);
  assert.equal(frenchSpacing('Oui ; non'), `Oui${N}; non`);
  // A no-break space or a run of spaces collapses to one narrow one.
  assert.equal(frenchSpacing('Quoi ?'), `Quoi${N}?`);
  assert.equal(frenchSpacing('Quoi   ?'), `Quoi${N}?`);
});

test('a glued ! ? ; gets its space; a glued colon is left alone', () => {
  assert.equal(frenchSpacing('Bonjour!'), `Bonjour${N}!`);
  assert.equal(frenchSpacing('Vraiment?!'), `Vraiment${N}?!`);
  assert.equal(frenchSpacing('à 10:30'), 'à 10:30');
  assert.equal(frenchSpacing('https://atelier.app'), 'https://atelier.app');
});

test('guillemets hold their words: « text », glued or spaced', () => {
  assert.equal(frenchSpacing('« Bonjour »'), `«${N}Bonjour${N}»`);
  assert.equal(frenchSpacing('«Bonjour»'), `«${N}Bonjour${N}»`);
  assert.equal(frenchSpacing('Il dit « oui ! »'), `Il dit «${N}oui${N}!${N}»`);
});

test('idempotent, and safe on empty or missing text', () => {
  const once = frenchSpacing('« Tu viens ? » Oui !');
  assert.equal(frenchSpacing(once), once);
  assert.equal(frenchSpacing(''), '');
  assert.equal(frenchSpacing(null), '');
  assert.equal(frenchSpacing(undefined), '');
  // No ordinary space is left in front of high punctuation.
  assert.doesNotMatch(once, / [!?;:»]|« /);
});

test('frenchQuote wraps a line in guillemets that cannot come apart', () => {
  assert.equal(frenchQuote('Tu viens ?'), `«${N}Tu viens${N}?${N}»`);
  assert.equal(frenchQuote('  '), '');
  assert.equal(frenchQuote(null), '');
});
