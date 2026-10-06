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
