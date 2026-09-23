// node --test components/releve/seal-collection.test.js
//
// WP-D4 / WP-D5 — the Seal in the av2 language, and the streak as a
// collection of seals.
//
//   1. the Seal: a card-face disc on the large press, no ink border, no offset
//      shadow, no stroke on any shape; the logo's four shapes, each on its
//      *-deep press; sentence-case words; Reduce Motion removes the press;
//   2. SealMini discs sit on the small press, no strokes;
//   3. «Vos sceaux»: the server's states become discs (earned / done /
//      relache / today / future / missed), Monday first, seven columns, days
//      before the first recorded day are blank, and the grid fits 320 px;
//   4. the number printed is the server's, never recounted here.

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

const { Seal, SealMini, sealForEdition } = require('@/components/ui/Seal.tsx');
const { SealCollectionBody } = require('./SealCollection.tsx');
const { sealCollectionView } = require('./seal-collection-model.ts');

const CSS = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
const SEAL_CSS = CSS.slice(CSS.indexOf('WP-D4 · The Seal (components/ui/Seal.tsx)'));

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const match = SEAL_CSS.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`));
  assert.ok(match, `missing rule ${selector}`);
  return match[1];
}

// ---------------------------------------------------------------------------
// 1-2. The Seal and its minis
// ---------------------------------------------------------------------------

test('the Seal is the av2 disc: large press, no ink border, no offset shadow', () => {
  const disc = rule('.av2 .av2-seal__disc');
  assert.match(disc, /background:\s*var\(--av2-card\)/);
  assert.match(disc, /box-shadow:\s*0 var\(--av2-press-lg\) 0 var\(--av2-line-2\)/);
  assert.doesNotMatch(disc, /border:/);
  assert.match(rule('.av2 .av2-seal__well'), /background:\s*var\(--av2-paper\)/);
  const words = rule('.av2 .av2-seal__line');
  assert.match(words, /font-family:\s*var\(--av2-sans\)/);
  assert.match(words, /font-weight:\s*600/);
  assert.match(words, /fill:\s*var\(--av2-muted\)/);
  assert.match(words, /letter-spacing:\s*normal/);
  assert.match(words, /text-transform:\s*none/);
  // Only tokens: no raw colour anywhere in the seal's styles.
  assert.doesNotMatch(SEAL_CSS, /#[0-9a-f]{3,8}\b|rgb\(|hsl\(/i);
  assert.doesNotMatch(SEAL_CSS, /uppercase/);
  // SealMini sits on the small press.
  assert.match(rule('.av2 .av2-seal-mini__disc'), /box-shadow:\s*0 var\(--av2-press-sm\) 0 var\(--av2-line-2\)/);
});

test('the Seal holds the logo four shapes, filled, each on its deep press, no strokes', () => {
  const html = renderToStaticMarkup(React.createElement(Seal, { variant: 'quad', no: 47, date: '22 sept.' }));
  assert.doesNotMatch(html, /stroke/);
  for (const tone of ['circle', 'square', 'tri', 'block']) {
    assert.equal((html.match(new RegExp(`av2-seal__form--${tone}"`, 'g')) || []).length, 1, `${tone} face`);
    assert.equal((html.match(new RegExp(`av2-seal__form--${tone} is-press"`, 'g')) || []).length, 1, `${tone} press`);
  }
  assert.match(html, /Atelier · le feuilleton/);
  assert.match(html, /Nº 47 · 22 sept\./);
  assert.match(html, /aria-label="Sceau Nº 47 · 22 sept\."/);
  assert.match(rule('.av2 .av2-seal__form'), /stroke:\s*none/);
  assert.match(rule('.av2 .av2-seal__form--tri.is-press'), /var\(--av2-red-deep\)/);
  // Every variant is the same four shapes.
  for (let no = 0; no < 6; no += 1) {
    const { variant } = sealForEdition(no);
    const markup = renderToStaticMarkup(React.createElement(Seal, { variant, no }));
    assert.equal((markup.match(/class="av2-seal__form /g) || []).length, 8, `${variant}: 4 faces + 4 presses`);
  }
});

test('the press is one animation, and Reduce Motion removes it', () => {
  const stamped = renderToStaticMarkup(React.createElement(Seal, { stamp: true, variant: 'row' }));
  assert.match(stamped, /data-stamp="true"/);
  assert.match(rule(".av2 .av2-seal[data-stamp='true'] .av2-seal__disc"), /animation:\s*av2-seal-press/);
  const reduce = SEAL_CSS.slice(SEAL_CSS.indexOf('@media (prefers-reduced-motion: reduce)'));
  assert.match(reduce, /\.av2-seal\[data-stamp='true'\] \.av2-seal__disc\s*\{\s*animation:\s*none;/);
});

test('SealMini: every state is a disc, no strokes', () => {
  for (const state of ['earned', 'done', 'relache', 'today', 'future', 'missed']) {
    const html = renderToStaticMarkup(React.createElement(SealMini, { state, no: 3, variant: 'row' }));
    assert.match(html, new RegExp(`data-state="${state}"`));
    assert.doesNotMatch(html, /stroke/);
  }
  assert.match(renderToStaticMarkup(React.createElement(SealMini, { state: 'empty' })), /data-state="missed"/);
  assert.match(renderToStaticMarkup(React.createElement(SealMini, { state: 'relache' })), /av2-seal__form--square/);
  assert.match(rule(".av2 .av2-seal-mini[data-state='today'] .av2-seal-mini__disc"), /var\(--av2-red\)/);
  assert.match(SEAL_CSS, /\[data-state='future'\] \.av2-seal-mini__disc \{\s*border-style: dotted;/);
  assert.match(SEAL_CSS, /\[data-state='relache'\] \.av2-seal-mini__disc,[^{]*\{[^}]*dashed/);
});

// ---------------------------------------------------------------------------
// 3-4. «Vos sceaux»
// ---------------------------------------------------------------------------

// Wednesday 23 Sept 2026 is today; the learner's first day was Tuesday 8 Sept.
function payload() {
  const days = [];
  const push = (date, state, extra = {}) =>
    days.push({ date, state, completed: state === 'completed' ? 1 : 0, is_today: false, sealed: false, edition_no: null, seal_variant: null, ...extra });
  push('2026-09-08', 'completed', { sealed: true, edition_no: 1, seal_variant: 'stack' });
  push('2026-09-09', 'completed', { sealed: true, edition_no: 2, seal_variant: 'nested' });
  push('2026-09-10', 'missed');
  for (let d = 11; d <= 20; d += 1) push(`2026-09-${d}`, 'completed', { sealed: true, edition_no: d - 8, seal_variant: 'quad' });
  push('2026-09-21', 'relache');
  push('2026-09-22', 'completed'); // an early stop: practised, no seal
  push('2026-09-23', 'today', { is_today: true });
  for (let d = 24; d <= 27; d += 1) push(`2026-09-${d}`, 'future');
  return {
    current_streak: 11,
    longest_streak: 11,
    today_done: false,
    freeze_available: false,
    today: '2026-09-23',
    timezone: 'Europe/Paris',
    calendar: days,
  };
}

test('the grid: Monday first, seven columns, the server states as discs', () => {
  const view = sealCollectionView(payload());
  assert.equal(view.weeks.length, 3, 'the week before the first day is not drawn');
  for (const week of view.weeks) assert.equal(week.length, 7);
  const cells = view.weeks.flat();
  assert.equal(cells[0].kind, 'blank', 'Monday 7 Sept is before the first day');
  const by = Object.fromEntries(cells.filter((c) => c.kind === 'day').map((c) => [c.date, c]));
  assert.equal(by['2026-09-08'].state, 'earned');
  assert.equal(by['2026-09-08'].variant, 'stack');
  assert.equal(by['2026-09-10'].state, 'missed');
  assert.equal(by['2026-09-21'].state, 'relache');
  assert.equal(by['2026-09-22'].state, 'done', 'an early stop presses no seal');
  assert.equal(by['2026-09-23'].state, 'today');
  assert.equal(by['2026-09-27'].state, 'future');
  assert.match(by['2026-09-08'].label, /mardi 8 septembre · sceau Nº 1/);
  assert.match(by['2026-09-21'].label, /jour de relâche/);
  assert.equal(view.today.date, '2026-09-23');
  // The number is the server's, not a recount of the grid.
  assert.equal(view.streak, 11);
});

test('the rendered collection: one disc per day, the record, fits 320 px', () => {
  const html = renderToStaticMarkup(React.createElement(SealCollectionBody, { payload: payload() }));
  assert.equal((html.match(/class="av2-seal-mini"/g) || []).length, 20 + 1, '20 days in the grid + today');
  assert.match(html, /aria-label="Vos sceaux · série de 11 jours"/);
  assert.match(html, /Le sceau du jour attend sa scène\./);
  assert.match(html, /Série · 11 jours · record · 11 jours/);
  assert.match(
    renderToStaticMarkup(React.createElement(SealCollectionBody, { payload: payload(), formsLeft: 2 })),
    /encore 2 formes/,
  );
  // 7 shrinkable columns and a capped, fluid disc: no horizontal scroll at 320.
  assert.match(rule('.av2 .av2-seals__week-days,\n.av2 .av2-seals__grid'), /repeat\(7, minmax\(0, 1fr\)\)/);
  const disc = rule('.av2 .av2-seal-mini__disc');
  assert.match(disc, /width:\s*100%/);
  assert.match(disc, /max-width:\s*44px/);
  // 320 − 2×20 gutter − 2×16 card padding = 248 px; 7 columns + 6×4 px gaps.
  assert.ok((248 - 6 * 4) / 7 >= 30, 'each disc still has room at 320 px');
});

test('a relâche in reserve is said; no payload, no section body', () => {
  const html = renderToStaticMarkup(
    React.createElement(SealCollectionBody, { payload: { ...payload(), freeze_available: true } }),
  );
  assert.match(html, /Un jour de relâche en réserve\./);
  assert.equal(sealCollectionView(null), null);
});
