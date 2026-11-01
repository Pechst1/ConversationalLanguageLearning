// node --test components/epreuve/forge-repair-381.test.js
//
// #381 (live walks 30 and 31 Oct) — the part-by-part repair of a missed line.
//
//   «Je voudrais un tomate, sil te plait.»: the learner typed «une tomate» in the gap of
//   «un» and «s'il te plait» (no accent) in the other; «Not yet: the words in red still
//   need fixing.» drew BOTH red: the first was judged against «une» alone, and every gap
//   is drawn red until it is fixed. Once the line is compared, a gap that reads as its
//   fix is drawn as fixed, only the gap still wrong is red, and the line once fixed reads
//   as it was sent. (The band under it is the page's: e2e/miss-layout.mjs types the right
//   repair in a browser and asserts «Not yet» is gone.)

const assert = require('node:assert/strict');
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

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const Ep = require('./Epreuve.tsx');
const { epreuveCopy } = require('./epreuve-copy.ts');
const { repairParts } = require('@/lib/repair-parts.ts');

const h = React.createElement;
const decode = (html) => html.replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&');

const PARTS = repairParts('Je voudrais un tomate, sil te plait.', [
  { learner_text: 'un tomate', corrected_target: 'une tomate', task_error_type: 'agreement' },
  { learner_text: 'sil te plait', corrected_target: "s'il te plaît", task_error_type: 'spelling' },
]);

/** Each gap of the rendered repair: what it holds and how it is drawn (`data-state`). */
function gaps(typed, status) {
  const html = decode(renderToStaticMarkup(h(Ep.EpShell, { language: 'en' }, h(Ep.EpPartsRepair, { parts: PARTS, typed, status, onChange: () => {}, onSubmit: () => {} }))));
  const inputs = [...html.matchAll(/<input[^>]*class="ep-parts__gap"[^>]*>/g)].map((match) => match[0]);
  return {
    html,
    gaps: inputs.map((input) => ({ value: (/ value="([^"]*)"/.exec(input) || [])[1], state: (/ data-state="([^"]*)"/.exec(input) || [])[1] || null })),
  };
}

test('only the gap that is still wrong is red; the one typed right is drawn as fixed', () => {
  const { gaps: shown, html } = gaps({ 1: 'une tomate', 3: "s'il te plait" }, 'no');
  assert.deepEqual(shown, [
    { value: 'une tomate', state: 'fixed' },
    { value: "s'il te plait", state: 'wrong' },
  ]);
  assert.ok(html.includes(epreuveCopy('en').repair_parts_no));
});

test('a gap left as written is red, a gap typed as its fix is not', () => {
  const { gaps: shown } = gaps({ 3: "s'il te plaît" }, 'no');
  assert.deepEqual(shown.map((gap) => gap.state), ['wrong', 'fixed']);
  // Before the line is compared nothing is judged: every gap is a gap to fix.
  assert.deepEqual(gaps({ 1: 'une', 3: "s'il te plaît" }, null).gaps.map((gap) => gap.state), [null, null]);
});

test('a fixed gap is not drawn in the red of a gap to fix', () => {
  const css = Ep.LEpreuveStyles ? renderToStaticMarkup(h(Ep.LEpreuveStyles)) : '';
  const rule = /\.ep-parts__gap\[data-state="fixed"\]\s*\{([^}]*)\}/.exec(decode(css));
  assert.ok(rule, 'a style for a fixed gap');
  assert.doesNotMatch(rule[1], /red/);
});

test('the fixed line reads as it was sent, without the neighbouring word twice', () => {
  const { gaps: shown, html } = gaps({ 1: 'une tomate', 3: "s'il te plaît" }, 'ok');
  assert.deepEqual(shown.map((gap) => gap.value), ['une', "s'il te plaît"]);
  assert.ok(shown.every((gap) => gap.state === null));
  assert.match(html, /Line fixed\. It comes back later\./);
});
