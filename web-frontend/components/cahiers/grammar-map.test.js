// node --test components/cahiers/grammar-map.test.js
//
// WP-S7 — the grammar map, the combo tokens, Éclair's entry and the Seal's rings.
//   1. the map draws each rule in one of four states — ghost, tint, half, ink —
//      as flat filled shapes (never an outline or a stroke);
//   2. the chrome follows the language rule (A1 en, A2 de, B1 fr) while rule
//      titles stay French; the copy tables are complete and sentence case;
//   3. a tapped rule opens its sheet: card, coach, «Forge», «Test out»;
//   4. Éclair appears once a pair is open, and not with the flag off;
//   5. the Seal gains one filled ring per rule held today (capped, named);
//   6. the new CSS is tokens only (no hex) and draws no strokes.

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
const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const GM = require('./GrammarMap.tsx');
const M = require('@/lib/grammar-map.ts');
const { MOMENTUM_COPY, momentumCopy, fillMomentum, comboLabel, bestComboLine, sealRingsLabel } = require('@/lib/momentum-copy.ts');
const { chromeLanguage } = require('@/lib/language-rule.ts');
const Forge = require('@/components/epreuve/Forge.tsx');
const { Seal, sealRingPaths, SEAL_MAX_RINGS } = require('@/components/ui/Seal.tsx');
const { rewardView, heldToday } = require('@/components/atelier-v2/journey/journey-recap-model.ts');

const h = React.createElement;

const card = {
  speaker: 'margaux_barman',
  example: { fr: '[Le] café est chaud.', tr: { en: 'The coffee is hot.' } },
  rule: { en: 'Le before a masculine noun.', de: 'Le vor maskulinen Nomen.', fr: 'Le devant un nom masculin.' },
};

function payload(extra = {}) {
  return {
    catalog: 'v2',
    bands: [
      {
        band: 'A1.1',
        rules: [
          { concept_id: 1, title_fr: 'Le, la, les', category: 'Articles', stage: 'ghost', rung: 0 },
          { concept_id: 2, title_fr: 'Un, une, des', category: 'Articles', stage: 'introduced', rung: 1, due: true, rule_card: card },
          { concept_id: 3, title_fr: 'Le présent de être', category: 'Verbs', stage: 'proficient', rung: 4 },
          { concept_id: 4, title_fr: 'La négation', category: 'Negation', stage: 'held', rung: 5, tested_out: true },
        ],
      },
      { band: 'A1.2', rules: [{ concept_id: 5, title_fr: 'Le futur proche', category: 'Verbs', stage: 'ghost', rung: 0 }] },
      { band: 'A2.1', rules: [{ concept_id: 6, title_fr: 'Le passé composé', category: 'Verbs', stage: 'ghost', rung: 0 }] },
    ],
    eclair: {
      unlocked: true,
      pairs: [{ pair: '1-2', concept_ids: [1, 2], rules: [{ concept_id: 1, title_fr: 'Le, la, les' }, { concept_id: 2, title_fr: 'Un, une, des' }], best: 7, plays: 2 }],
    },
    features: { combo: true, eclair: true, grammar_map: true, mastery_rewards: true },
    ...extra,
  };
}

function renderMap(language, { selectedId = null, data = payload() } = {}) {
  return renderToStaticMarkup(
    h('div', { className: 'av2' },
      h(GM.GrammarMapView, { payload: data, language, selectedId, onSelect: () => undefined, onOpenPage: () => undefined }),
    ),
  );
}

// ---------------------------------------------------------------------------
// 1 · four states, flat fills
// ---------------------------------------------------------------------------

test('each rule is its shape in one of four fills: ghost, tint, half, ink', () => {
  assert.equal(M.mapFill('ghost'), 'ghost');
  assert.equal(M.mapFill('introduced'), 'tint');
  assert.equal(M.mapFill('proficient'), 'half');
  assert.equal(M.mapFill('held'), 'ink');
  assert.equal(M.mapStageOf({ stage: 'bogus' }), 'ghost');

  const html = renderMap('en');
  const buttons = [...html.matchAll(/<button type="button" class="gm-rule" data-stage="(\w+)"[^>]*>([\s\S]*?)<\/button>/g)];
  // The first visible bands: A1.1 (met) and A1.2 (the next); A2.1 waits behind «All levels».
  assert.deepEqual(buttons.map((m) => m[1]), ['ghost', 'introduced', 'proficient', 'held', 'ghost']);
  const fills = buttons.map((m) => (m[2].match(/data-fill="(\w+)"/) || [])[1]);
  assert.deepEqual(fills, ['ghost', 'tint', 'half', 'ink', 'ghost']);
  // Half is a clip of the same shape, not a second colour or an outline.
  assert.match(buttons[2][2], /<clipPath id="gm-half-[^"]+"><rect x="0" y="12"/);
  assert.equal((buttons[2][2].match(/<path /g) || []).length, 2);
  assert.equal((buttons[0][2].match(/<path /g) || []).length, 1);
  // The rule's shape: articles are squares, verbs triangles, negation a circle.
  assert.match(buttons[1][2], /data-shape="square"/);
  assert.match(buttons[2][2], /data-shape="triangle"/);
  assert.match(buttons[3][2], /data-shape="circle"/);
  assert.doesNotMatch(html, /stroke=/, 'no stroke attribute on any shape');
  assert.match(html, /class="gm-more"[^>]*>All levels</);
  assert.match(buttons[1][0], /data-due="true"/);
});

test('the bands open up to the furthest met band, plus the next', () => {
  const bands = payload().bands;
  assert.deepEqual(M.visibleBands(bands, false).map((b) => b.band), ['A1.1', 'A1.2']);
  assert.deepEqual(M.visibleBands(bands, true).map((b) => b.band), ['A1.1', 'A1.2', 'A2.1']);
  const fresh = bands.map((b) => ({ ...b, rules: b.rules.map((r) => ({ ...r, stage: 'ghost' })) }));
  assert.deepEqual(M.visibleBands(fresh, false).map((b) => b.band), ['A1.1']);
  assert.deepEqual(M.mapCounts(payload()), { ghost: 3, introduced: 1, proficient: 1, held: 1 });
});

// ---------------------------------------------------------------------------
// 2 · the language rule
// ---------------------------------------------------------------------------

test('momentum copy: three complete tables, sentence case, no empty string', () => {
  const leaves = (value, prefix = '') => (value && typeof value === 'object'
    ? Object.entries(value).flatMap(([key, inner]) => leaves(inner, prefix ? `${prefix}.${key}` : key))
    : [[prefix, value]]);
  const keys = (table) => leaves(table).map(([key]) => key).sort();
  for (const language of ['en', 'de', 'fr']) {
    assert.deepEqual(keys(MOMENTUM_COPY[language]), keys(MOMENTUM_COPY.en), language);
    for (const [key, value] of leaves(MOMENTUM_COPY[language])) {
      assert.ok(typeof value === 'string' && value.trim(), `${language}.${key}`);
      assert.notEqual(value, value.toUpperCase(), `${language}.${key} is sentence case`);
    }
  }
  assert.equal(momentumCopy('xx').map_title, 'Your grammar map');
  assert.equal(comboLabel(momentumCopy('en'), 0), 'No run yet');
  assert.equal(comboLabel(momentumCopy('en'), 1), 'One right answer in a row');
  assert.equal(comboLabel(momentumCopy('de'), 4), '4 richtige Antworten in Folge');
  assert.equal(bestComboLine(momentumCopy('fr'), 0), null);
  assert.equal(bestComboLine(momentumCopy('fr'), 6), 'Meilleure série : 6 d’affilée');
});

test('the map speaks the chrome language by level (A1 en, A2 de, B1 fr); titles stay French', () => {
  const cases = [
    [chromeLanguage('en', 'A1.1'), 'Your grammar map', 'Un, une, des: introduced · Review due'],
    [chromeLanguage('de', 'A2.1'), 'Deine Grammatikkarte', 'Un, une, des: eingeführt · Wiederholung fällig'],
    [chromeLanguage('de', 'B1.1'), 'Votre carte de grammaire', 'Un, une, des : découverte · Révision prévue'],
  ];
  for (const [language, title, aria] of cases) {
    const html = renderMap(language);
    assert.match(html, new RegExp(`<p class="gm-title">${title}</p>`), language);
    assert.ok(html.includes(`aria-label="${aria}"`), `${language}: ${aria}`);
  }
  // A1 English chrome never carries French chrome words around the French title.
  const en = renderMap('en');
  assert.doesNotMatch(en.replace(/lang="fr"[^>]*>[^<]*/g, ''), /Forger|Épreuve réussie|découverte/);
});

// ---------------------------------------------------------------------------
// 3 · the rule's sheet
// ---------------------------------------------------------------------------

test('a tapped rule opens its card, its coach, «Forge this rule» and «Test out this rule»', () => {
  const html = renderMap('en', { selectedId: 2 });
  const start = html.indexOf('<section class="gm-sheet"');
  const sheet = start >= 0 ? [html.slice(start, html.indexOf('class="gm-eclair"') > start ? html.indexOf('class="gm-eclair"') : undefined)] : null;
  assert.ok(sheet, 'the sheet renders');
  assert.match(sheet[0], /<p class="gm-sheet__title" id="gm-sheet-2" lang="fr">Un, une, des<\/p>/);
  assert.match(sheet[0], /Taught by Margaux/);
  assert.match(sheet[0], /class="rc"/, 'the rule card');
  assert.match(sheet[0], /<a class="av2-btn av2-btn--primary gm-sheet__forge" href="\/atelier\?mode=practice&amp;concept=2">Forge this rule<\/a>/);
  assert.match(sheet[0], /Test out this rule/);
  assert.match(sheet[0], /Open the rule’s page/);
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, 'one 3D primary on the screen');
  assert.match(html, /aria-pressed="true"/);
  // No Garamond headline inside the map: the Cahier's head is the one line.
  assert.doesNotMatch(html, /av2-headline/);
});

// ---------------------------------------------------------------------------
// 4 · Éclair's entry
// ---------------------------------------------------------------------------

test('Éclair appears once a pair is open, with its best, and not with the flag off', () => {
  const html = renderMap('en');
  assert.match(html, /<a class="gm-eclair__pair" href="\/eclair\?pair=1-2">/);
  assert.match(html, /Le, la, les or Un, une, des/);
  assert.match(html, /Best: 7/);
  assert.match(html, /Éclair · 60 s/);
  const off = renderMap('en', { data: payload({ features: { eclair: false } }) });
  assert.doesNotMatch(off, /gm-eclair/);
  const locked = renderMap('en', { data: payload({ eclair: { unlocked: false, pairs: [] } }) });
  assert.doesNotMatch(locked, /gm-eclair/);
  assert.equal(M.grammarMapEnabled({ features: { grammar_map: false } }), false);
  assert.equal(M.eclairHref('3-9'), '/eclair?pair=3-9');
});

test('Éclair grades locally, folding typography, and keeps its clock', () => {
  const E = require('@/lib/eclair.ts');
  const item = { id: 'a', concept_id: 1, labels: ['J’aime le café.', 'J’aime la café.'], correct_answer: 'J’aime le café.' };
  assert.equal(E.gradeEclair(item, "J'aime le café"), true);
  assert.equal(E.gradeEclair(item, 'J’aime la café.'), false);
  assert.equal(E.eclairScore([{ correct: true }, { correct: false }, { correct: true }]), 2);
  assert.equal(E.secondsLeft(0, 59_100), 1);
  assert.equal(E.secondsLeft(0, 61_000), 0);
  assert.equal(E.roundOver(0, 30_000, 3, 40), false);
  assert.equal(E.roundOver(0, 60_000, 3, 40), true);
  assert.equal(E.roundOver(0, 1_000, 40, 40), true);
  assert.equal(E.eclairCue({ prompt: 'Which sentence says: "x"', prompt_l10n: { de: 'Welcher Satz sagt: „x“' } }, 'de'), 'Welcher Satz sagt: „x“');
});

// ---------------------------------------------------------------------------
// The combo tokens in the forge
// ---------------------------------------------------------------------------

test('the combo is five tokens in the rule’s shape, lit from the left, named for screen readers', () => {
  const html = renderToStaticMarkup(h(Forge.ForgeCombo, { shape: 'triangle', run: 3, label: comboLabel(momentumCopy('en'), 3) }));
  assert.match(html, /role="img" aria-label="3 right answers in a row" data-shape="triangle"/);
  const tokens = [...html.matchAll(/class="forge-combo__token"( data-lit="true")?( data-new="true")?/g)];
  assert.equal(tokens.length, 5);
  assert.deepEqual(tokens.map((m) => Boolean(m[1])), [true, true, true, false, false]);
  assert.deepEqual(tokens.map((m) => Boolean(m[2])), [false, false, true, false, false], 'the newest lit token pops');
  assert.match(html, /class="forge-combo__n" aria-hidden="true">3</);
  const none = renderToStaticMarkup(h(Forge.ForgeCombo, { shape: 'circle', run: 0, label: 'No run yet' }));
  assert.doesNotMatch(none, /data-lit|forge-combo__n/);
});

test('the staircase steps are each readable: ≥ 12 units, with a gap between neighbours', () => {
  const html = renderToStaticMarkup(h(Forge.ForgeStair, { shape: 'square', rung: 2, label: 'x' }));
  assert.match(html, /viewBox="0 0 102 28"/);
  const rects = [...html.matchAll(/<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"/g)].map((m) => [Number(m[1]), Number(m[2])]);
  assert.equal(rects.length, 6);
  for (const [, width] of rects) assert.ok(width >= 12 && width <= 14, `step size ${width}`);
  for (let i = 1; i < rects.length; i += 1) {
    const gap = rects[i][0] - (rects[i - 1][0] + rects[i - 1][1]);
    assert.ok(gap >= 2.5, `gap ${gap} between step ${i} and ${i + 1}`);
  }
});

// ---------------------------------------------------------------------------
// 5 · the Seal's rings and the rare token
// ---------------------------------------------------------------------------

test('the Seal gains one filled ring per rule held today, capped, and says so', () => {
  assert.equal(sealRingPaths(0).length, 0);
  assert.equal(sealRingPaths(2).length, 2);
  assert.equal(sealRingPaths(9).length, SEAL_MAX_RINGS);
  const label = sealRingsLabel(momentumCopy('en'), 2);
  const html = renderToStaticMarkup(h(Seal, { variant: 'quad', no: 12, date: '24 sept.', rings: 2, ringsLabel: label }));
  assert.match(html, /data-rings="2"/);
  assert.equal((html.match(/class="av2-seal__ring"/g) || []).length, 2);
  assert.match(html, /fill-rule="evenodd"/, 'rings are filled annuli, not strokes');
  assert.doesNotMatch(html.match(/<svg class="av2-seal__rings"[\s\S]*?<\/svg>/)[0], /stroke/);
  assert.match(html, /aria-label="Sceau Nº 12 · 24 sept\. · 2 rings: rules held today"/);
  const plain = renderToStaticMarkup(h(Seal, { variant: 'quad', no: 12 }));
  assert.doesNotMatch(plain, /av2-seal__rings|data-rings/);

  const journey = { status: 'completed', edition_no: 12, local_date: '2026-09-24', mastery_today: { held_concept_ids: [4, 9, 4], tested_out_concept_ids: [9] }, steps: [] };
  assert.equal(heldToday(journey), 2);
  const view = rewardView(journey, { completion_kind: 'complete' }, 'de');
  assert.equal(view.seal.rings, 2);
  assert.equal(view.seal.ringsLabel, '2 Ringe: Regeln heute gefestigt');
  assert.equal(heldToday({ status: 'completed' }), 0);
});

test('a passed test-out shows its rare token as a reward square on its press', () => {
  const html = renderToStaticMarkup(h(Forge.ForgeRareToken, { title: momentumCopy('fr').test_out_token, sub: momentumCopy('fr').test_out_token_sub }));
  assert.match(html, /class="forge-token" role="status"/);
  assert.match(html, /Un jeton rare pour cette règle/);
});

// ---------------------------------------------------------------------------
// 6 · CSS: tokens only, no strokes
// ---------------------------------------------------------------------------

function styleBlock(file) {
  const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  return [...source.matchAll(/<style jsx global>\{`([\s\S]*?)`\}<\/style>/g)].map((m) => m[1]).join('\n');
}

test('the new CSS is tokens only and draws no strokes', () => {
  const blocks = {
    'components/cahiers/GrammarMap.tsx': styleBlock('components/cahiers/GrammarMap.tsx'),
    'pages/eclair.tsx': styleBlock('pages/eclair.tsx'),
    'components/epreuve/Forge.tsx': styleBlock('components/epreuve/Forge.tsx'),
  };
  const seal = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  blocks['styles/atelier-v2.css (rings)'] = seal.slice(seal.indexOf('WP-S7: one ring per rule'), seal.indexOf('SealMini: the collection'));
  for (const [name, css] of Object.entries(blocks)) {
    assert.ok(css.length > 100, `${name} has CSS`);
    assert.doesNotMatch(css, /#[0-9a-fA-F]{3,8}\b/, `${name}: no hex colour`);
    assert.doesNotMatch(css, /rgba?\(|hsla?\(/, `${name}: no raw colour`);
    for (const match of css.matchAll(/\bstroke(?:-width)?\s*:\s*([^;]+);/g)) assert.equal(match[1].trim(), 'none', `${name}: stroke`);
    for (const match of css.matchAll(/\boutline\s*:\s*([^;]+);/g)) assert.equal(match[1].trim(), 'none', `${name}: no outline`);
    for (const match of css.matchAll(/\bborder\s*:\s*([^;]+);/g)) assert.equal(match[1].trim(), '0', `${name}: no border`);
  }
  const map = blocks['components/cahiers/GrammarMap.tsx'];
  assert.match(map, /\.gm-shape\[data-fill='ghost'\] \.gm-shape__base \{ fill: var\(--av2-line\); \}/);
  assert.match(map, /\.gm-shape\[data-fill='ink'\] \.gm-shape__base \{ fill: var\(--av2-ink\); \}/);
  // Reduce Motion: the combo's pop and the rings' pop sit under no-preference.
  const forge = blocks['components/epreuve/Forge.tsx'];
  assert.match(forge, /@media \(prefers-reduced-motion: no-preference\) \{\s*\.av2 \.forge-combo__token\[data-new='true'\] \{ animation: av2-pop/);
  assert.match(blocks['styles/atelier-v2.css (rings)'], /prefers-reduced-motion: no-preference/);
});

test('wiring: the séance draws the combo and feels it, the Cahier shows the map, the day recap rings the Seal', () => {
  const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  const atelier = read('pages/atelier.tsx');
  assert.match(atelier, /runSlot=\{showCombo\s*\?\s*<ForgeCombo shape=\{ruleShape\(activeConcept\)\} run=\{combo\.run\}/);
  assert.match(atelier, /comboFeel\(comboStep\(before, after\), after\)/);
  assert.match(atelier, /if \(feltCombo\.tone\) playComboTone\(after\);/);
  assert.match(atelier, /<ForgeBestCombo/);
  assert.match(atelier, /recap\.forge\?\.eclair\?\.pair/);
  assert.match(atelier, /forge\.result\.passed && forge\.result\.token/);
  assert.match(read('pages/grammar.tsx'), /<GrammarMap language=\{language\} onOpenPage=\{selectConcept\} \/>/);
  assert.match(read('components/atelier-v2/journey/JourneyRecap.tsx'), /rings=\{seal\.rings\}/);
  assert.match(read('lib/product-shell.ts'), /'\/eclair'/);
});

test('fillMomentum fills placeholders', () => {
  assert.equal(fillMomentum('{a} or {b}', { a: 'le', b: 'la' }), 'le or la');
});
