// node --test components/lexique/card-own-words.test.js
//
// #851 (live walk 17 Nov): with the Lexique's first-time note open, «I know it» did nothing
// fifteen times: the card turned back to its front and the count stayed 0/15. The turned
// card is itself a control (role="button": a tap turns it back), and it carried the grade
// words as its own text (the drag stamps «Again» / «I know it» and the hint «← Again ·
// swipe · I know it →»). So the page had three things called «I know it», the first of
// them the card, which turns back instead of filing: a tap that finds «I know it» by its
// words (the walks, a voice or switch control reading the screen) was silently dropped.
// A control carries only its own words: the stamps and the hint draw theirs from an
// attribute (CSS `attr()`), so the card's text names no grade.
// The browser check of the same tap is e2e/lexique-first-visit.mjs.
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
const { lexiqueCopy } = require('./lexique-copy.ts');

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages/vocabulary/review.tsx'), 'utf8');
const CARD = '<div\n                    key={current.word_id}';

/** The JSX of the first element opened by `opening` (its tag through its matching close). */
function elementSource(source, opening) {
  const start = source.indexOf(opening);
  assert.ok(start >= 0, `review.tsx no longer renders «${opening}»: update this test with the card`);
  const tag = /^<(\w+)/.exec(opening)[1];
  const tokens = new RegExp(`<${tag}\\b|</${tag}>`, 'g');
  tokens.lastIndex = start;
  let depth = 0;
  for (let m = tokens.exec(source); m; m = tokens.exec(source)) {
    // A self-closing <div … /> opens nothing.
    if (m[0].startsWith('</')) depth -= 1;
    else if (!/^[^>]*\/>/.test(source.slice(m.index).replace(/=>/g, '=)'))) depth += 1;
    if (depth === 0) return source.slice(start, m.index + m[0].length);
  }
  throw new Error(`«${opening}» is never closed`);
}

/** The copy keys a JSX block prints as text: every `t.key` inside a `{…}` between tags. */
function printedCopyKeys(jsx) {
  const keys = new Set();
  // Text children: what stands between one tag's `>` and the next `<` (an arrow `=>` inside
  // an attribute is not a tag's end).
  for (const segment of jsx.split(/<[^<>]*(?:=>[^<>]*)*>/)) {
    for (const block of segment.matchAll(/\{([^{}]*)\}/g)) {
      for (const m of block[1].matchAll(/\bt\.(\w+)/g)) keys.add(m[1]);
    }
  }
  return [...keys];
}

test('the turned card (a control that turns the card back) names no grade in its own text', () => {
  const card = elementSource(PAGE, CARD);
  assert.match(card, /role="button"/, 'the card is a control: a tap on it turns it');
  assert.match(card, /lx-card__cta/, 'the whole card was read, down to its hint line');
  const keys = printedCopyKeys(card);
  for (const language of ['en', 'de', 'fr']) {
    const t = lexiqueCopy(language);
    const grades = [t.deck_know, t.deck_again];
    const naming = keys
      .filter((key) => typeof t[key] === 'string')
      .filter((key) => grades.some((grade) => t[key].toLowerCase().includes(grade.toLowerCase())))
      .map((key) => `t.${key} «${t[key]}»`);
    assert.deepEqual(
      naming,
      [],
      `${language}: the card's own text names a grade (${naming.join(', ')}): a tap aimed at «${t.deck_know}» / «${t.deck_again}» by its words lands on the card and turns it back instead of filing it (#851)`,
    );
  }
});

test('the drag stamps and the hint still show their words, drawn from an attribute', () => {
  const card = elementSource(PAGE, CARD);
  assert.match(card, /className="lx-stamp lx-stamp--again"[^>]*data-stamp=\{t\.deck_again\}/);
  assert.match(card, /className="lx-stamp lx-stamp--know"[^>]*data-stamp=\{t\.deck_know\}/);
  assert.match(card, /className="lx-card__cta"[^>]*data-cta=\{revealed \? t\.swipe_hint : t\.flip_front\}/);
  assert.match(PAGE, /\.lx-stamp::after\s*\{[^}]*content:\s*attr\(data-stamp\)/, 'the stamp prints its word through CSS');
  assert.match(PAGE, /\.lx-card__cta::after\s*\{[^}]*content:\s*attr\(data-cta\)/, 'the hint prints its words through CSS');
});
