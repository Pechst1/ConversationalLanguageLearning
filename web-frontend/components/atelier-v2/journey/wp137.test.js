// node --test components/atelier-v2/journey/wp137.test.js
//
// WP-137 — the day-1 walk fixes (frontend half).
//
//   C-4  «Le mauvais accueil»: all three drawn figures grinned and Lila said
//        «Non.» laughing. A cold line holds its figure's face on the level mouth,
//        and a cold beat smiles at no one the script did not make happy.
//   C-5  Panel 3 of 6 was the bare plate. A panel with nothing said and nothing
//        narrated is marked silent: it gets a caption and a slow pan (none under
//        Reduce Motion).
//   C-11 «A1.1 ·» with nothing after the dot.

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
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(WEB_ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(WEB_ROOT, 'node_modules/react-dom/server'));
global.React = React;

const { buildStoryStages } = require('./story-episode-model.ts');
const { PanelStage } = require('../../cast/PanelStage.tsx');
const { RIGS, rigFaceFor } = require('../../cast/cast-registry.ts');
const { CastRig } = require('../../cast/CastRig.tsx');
const { readerCopy } = require('../../feuilleton/reader/reader-copy.ts');

/** Mouths that smile, in every rig's own set. */
const SMILES = new Set(['smile', 'grin', 'smirk', 'soft']);

const PLATE = '/assets/serial/locations/le_mistral-counter.webp';
const line = (character_id, text_fr, mood) => ({ character_id, text_fr, ...(mood ? { mood } : {}) });

/** Day 1 of season 1 as the walk read it (A1), panels 1–6. */
const DAY_ONE = {
  id: 'ep-1',
  panels: [
    { id: 'p1', index: 0, narration_fr: 'Il pleut. Tu as une valise, une lettre, une clé.', dialogue: [], image_url: PLATE, image_status: 'setting_reference' },
    {
      id: 'p2', index: 1, narration_fr: '', image_url: PLATE, image_status: 'setting_reference',
      dialogue: [
        line('augustin_de_roncourt', '…Et il dit : « Augustin, vous êtes trop élégant ! »', 'happy'),
        line('marin_leveque', 'Il dit ça ?', 'neutral'),
        line('lila_bonnet', 'Non.', 'cold'),
      ],
    },
    { id: 'p3', index: 2, narration_fr: '', dialogue: [], image_url: PLATE, image_status: 'setting_reference' },
    {
      id: 'p4', index: 3, narration_fr: '', image_url: PLATE, image_status: 'setting_reference',
      dialogue: [
        line('augustin_de_roncourt', 'Ah ! Vous voilà. Vous venez pour M. Marchand ?', 'cold'),
        line('marin_leveque', "C'est qui ?", 'neutral'),
        line('lila_bonnet', 'La personne de la vente.', 'cold'),
      ],
    },
    {
      id: 'p5', index: 4, narration_fr: '', image_url: PLATE, image_status: 'setting_reference',
      dialogue: [line('marin_leveque', 'Prenez une chaise.', 'neutral'), line('lila_bonnet', 'Regarde ses chaussures, Marin.', 'neutral')],
    },
    {
      id: 'p6', index: 5, narration_fr: '', image_url: PLATE, image_status: 'setting_reference',
      dialogue: [line('augustin_de_roncourt', "Alors ? C'est qui, vous ? Et pourquoi ici ?", 'cold')],
    },
  ],
};

function mouthsOnStage(stage) {
  const markup = renderToStaticMarkup(React.createElement(PanelStage, { members: stage.cast || [], still: true }));
  const figures = [...markup.matchAll(/data-cast="([^"]+)"[^>]*data-mood="([^"]+)"[^>]*data-mouth="([^"]+)"/g)];
  return Object.fromEntries(figures.map(([, id, , mouth]) => [id, mouth]));
}

test('C-4 · a cold beat never renders a smile (the day-1 walk check)', () => {
  const stages = buildStoryStages(DAY_ONE).filter((stage) => stage.kind === 'panel');
  for (const stage of stages) {
    const moods = stage.lines.map((l) => l.stageMood);
    const coldBeat = moods.some((mood) => mood === 'cold' || mood === 'cross')
      && moods.every((mood) => mood === 'cold' || mood === 'cross' || mood === 'neutral');
    if (!coldBeat) continue;
    const mouths = mouthsOnStage(stage);
    assert.ok(Object.keys(mouths).length > 0, `${stage.panelId} draws its figures`);
    for (const [id, mouth] of Object.entries(mouths)) {
      assert.ok(!SMILES.has(mouth), `${stage.panelId}: ${id} smiles (${mouth}) in a cold beat`);
    }
  }
});

test('C-4 · «Non.» is dry: Lila holds the level mouth, Gus keeps the grin the script gave him', () => {
  const [, p2] = buildStoryStages(DAY_ONE);
  const mouths = mouthsOnStage(p2);
  assert.equal(mouths.lila_bonnet, 'flat');
  assert.equal(mouths.marin_leveque, 'flat', 'a neutral listener in a cold beat does not smile');
  assert.equal(mouths.augustin_de_roncourt, 'grin', 'a face the script wrote is the script’s');
});

test('C-4 · every rig has a cold face, drawn from what it already has', () => {
  const face = rigFaceFor('cold');
  assert.deepEqual(face, { mood: 'neutre', mouth: 'flat' });
  for (const rig of RIGS) {
    if (rig.faceless) continue;
    const markup = renderToStaticMarkup(React.createElement(CastRig, { id: rig.id, ...face, crop: 'head', still: true }));
    assert.match(markup, /data-mouth="flat"/, rig.id);
  }
  // The portrait moods are unchanged.
  assert.deepEqual(rigFaceFor('happy'), { mood: 'ravie', mouth: 'auto' });
  assert.deepEqual(rigFaceFor('neutral'), { mood: 'neutre', mouth: 'auto' });
});

test('C-5 · a panel with nothing said and nothing narrated is silent; the others are not', () => {
  const stages = buildStoryStages(DAY_ONE).filter((stage) => stage.kind === 'panel');
  assert.deepEqual(stages.map((stage) => Boolean(stage.silent)), [false, false, true, false, false, false]);
});

test('C-5 · the silent caption exists in all three languages; the pan stops under Reduce Motion', () => {
  for (const language of ['fr', 'en', 'de']) {
    assert.ok(readerCopy(language).silent_beat.trim(), language);
  }
  const css = fs.readFileSync(path.join(WEB_ROOT, 'components/feuilleton/reader/reader-styles.tsx'), 'utf8');
  assert.match(css, /\.fr-plate\[data-pan='slow'\] img \{\s*animation: fr-slow-pan/);
  const reduced = css.slice(css.indexOf('@media (prefers-reduced-motion: reduce)'));
  assert.match(reduced, /\.fr-plate\[data-pan='slow'\] img \{ animation: none;/);
});

// ---------------------------------------------------------------------------
// C-11 · the dateline is always legible; «A1.1 ·» never stands alone
// ---------------------------------------------------------------------------

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test('C-11 · the first-run dateline is never held at opacity 0, and its token reads ≥ 4.5:1 in both themes', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/index.tsx'), 'utf8');
  const rule = page.slice(page.indexOf('.av2 .la-une__folio {'), page.indexOf('}', page.indexOf('.av2 .la-une__folio {')));
  assert.ok(!/opacity:\s*0/.test(rule), 'the nameplate line is never invisible');
  const token = (rule.match(/color:\s*var\((--av2-[a-z0-9-]+)\)/) || [])[1];
  assert.ok(token, 'an av2 token, no new colour');
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  const values = (name) => [...css.matchAll(new RegExp(`${name}:\\s*(#[0-9a-f]{6})`, 'gi'))].map((m) => m[1]);
  const inks = values(token);
  const papers = values('--av2-paper');
  assert.ok(inks.length >= 2 && papers.length >= 2, 'light and dark values');
  for (let i = 0; i < Math.min(inks.length, papers.length); i += 1) {
    assert.ok(contrast(inks[i], papers[i]) >= 4.5, `${token} ${inks[i]} on ${papers[i]}: ${contrast(inks[i], papers[i]).toFixed(2)}`);
  }
});

test('C-11 · the home level line drops the separator when nothing follows it', () => {
  const { HomeScreen } = require('../home/HomeScreen.tsx');
  const { dayMarkState } = require('./day-mark.ts');
  const level = (nextStep) => {
    const html = renderToStaticMarkup(React.createElement(HomeScreen, {
      dateLabel: 'mardi 6 octobre',
      editionLabel: 'Édition Nº 1 · A1.1',
      streak: 0,
      level: { band: 'A1.1', percent: 0 },
      nextStep,
      language: 'de',
      day: dayMarkState(null, 'de'),
      chips: [],
    }));
    const start = html.indexOf('av2-home__level');
    return start < 0 ? '' : html.slice(start, html.indexOf('</p>', start));
  };
  const bare = level({ band: 'A1.1', line: '', ariaLabel: '', href: '/carnet' });
  assert.ok(/A1\.1/.test(bare), 'the band stays');
  assert.ok(!/ · /.test(bare), `no dangling separator: ${bare}`);
  const full = level({ band: 'A1.1', line: 'Nächster Schritt: Sagen, wer du bist', ariaLabel: 'x', href: '/carnet' });
  assert.ok(/ · <\/span><a /.test(full), 'a separator between two real parts');
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  assert.match(css, /\.av2-carnet__home-link \{ display: inline;/, 'the link wraps after the dot, never under it');
});
