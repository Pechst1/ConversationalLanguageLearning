// node --test components/epreuve/forge-basic-fixes-855.test.js
//
// #855 (walk 17 Nov, a2-en day 2): La Forge's unread sentence «J ai cuisine pour Lila la
// semaine derniere.» listed its basic-check fixes as «J ai →» and «derniere →», an arrow
// pointing at nothing. The server blanked each replacement as if a second chance were
// coming (app/services/solution_gate.py); the unread screen has none, and drew every
// edit as a fix without looking. The server now sends them whole (tests/
// test_forge_unread_basic_check_855.py); the screen draws a fix only with both sides.

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
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const Ep = require('./Epreuve.tsx');

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
const unscoredBranch = () => {
  const from = PAGE.indexOf('if (feedback.unscored) {');
  assert.ok(from > 0, 'La Forge has an unscored (unread) feedback branch');
  return PAGE.slice(from, PAGE.indexOf('\n  }\n', from));
};

const text = (html) => html.replace(/<[^>]+>/g, '').replace(/&#x27;|&#39;/g, "'").replace(/\s+/g, ' ').trim();
const lines = (html) => [...html.matchAll(/<p\b[^>]*>([\s\S]*?)<\/p>/g)].map((m) => text(m[1]));

function renderFixes(edits) {
  assert.equal(typeof Ep.EpBasicFixes, 'function', 'the unread sheet draws its fixes through one component that knows a fix has two sides');
  return renderToStaticMarkup(React.createElement(Ep.EpBasicFixes, { edits }));
}

test('#855 · the unread sheet shows both sides of each basic-check fix', () => {
  const html = renderFixes([
    { span: 'J ai', replacement: "J'ai", start: 0 },
    { span: 'derniere', replacement: 'dernière', start: 34 },
  ]);
  assert.deepEqual(lines(html), ["J ai → J'ai", 'derniere → dernière']);
  assert.match(html, /<s>J ai<\/s>/);
  assert.match(html, /<strong>dernière<\/strong>/);
  assert.match(html, /lang="fr"/);
});

test('#855 · no fix is drawn with nothing after «→»', () => {
  const html = renderFixes([
    { span: 'J ai', replacement: '', start: 0 },
    { span: 'derniere', replacement: 'dernière', start: 34 },
    { span: 'cuisine', replacement: '   ', start: 5 },
  ]);
  assert.deepEqual(lines(html), ['derniere → dernière']);
  assert.equal(renderFixes([{ span: 'J ai', replacement: '' }]), '', 'only withheld fixes: nothing drawn');
  assert.equal(renderFixes(undefined), '');
});

test('#855 · La Forge\'s unread branch draws its fixes through EpBasicFixes, never by hand', () => {
  const branch = unscoredBranch();
  assert.match(branch, /<EpBasicFixes edits=\{correction\?\.check\?\.edits\} \/>/);
  assert.doesNotMatch(branch, /→ <strong>\{edit\.replacement\}<\/strong>/, 'an unguarded «span → replacement» is back');
});
