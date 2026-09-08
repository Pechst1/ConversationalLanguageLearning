// node --test components/atelier-v2/journey/story-episode-model.test.js
//
// The story-engine projection → reader stages mapping (WP-14E). Pure module,
// no React, no network.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

// Resolve the `@/` alias the way tsconfig does.
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const model = require('./story-episode-model.ts');

const episode = {
  id: 'scene-1',
  scene_id: 'scene-1',
  serial_thread_id: 't',
  serial_episode_id: null,
  journey_id: 'j',
  title_fr: 'Une lettre attend ta réponse.',
  status: 'available',
  chapter: { id: 'c1', title_fr: 'Chapitre 1 · La fête du quartier' },
  panel_index: 1,
  panels: [
    {
      id: 'p2', index: 1, narration_fr: 'Le lendemain, au marché.',
      dialogue: [{ character_id: 'romy', text_fr: 'Tu viens samedi ?' }],
      image_url: null, image_status: 'unavailable',
    },
    {
      id: 'p1', index: 0, narration_fr: '',
      dialogue: [{ character_id: 'marchand', text_fr: 'Bonjour !' }, { character_id: 'toi', text_fr: '' }],
      image_url: '/assets/serial/lyon-market.jpg', image_status: 'setting_reference',
    },
  ],
  resolution: null,
};

test('panels are ordered by index and every stage comes from a server panel', () => {
  const stages = model.buildStoryStages(episode);
  assert.equal(stages.length, 2, 'no resolution stage until the server exposes one');
  assert.deepEqual(stages.map((s) => s.panelId), ['p1', 'p2']);
  assert.equal(stages[0].kind, 'panel');
  assert.equal(stages[0].lines.length, 1, 'an empty line is not a line');
  assert.equal(stages[0].lines[0].who, 'Monsieur Marchand');
  assert.equal(stages[0].lines[0].character, 'marchand');
  assert.equal(stages[1].caption, 'Le lendemain, au marché.');
  assert.equal(stages[1].character, 'romy');
});

test('art is honest: setting reference reads as ready, absent art is missing, never a placeholder', () => {
  const stages = model.buildStoryStages(episode);
  assert.equal(stages[0].artStatus, 'ready');
  assert.equal(stages[0].imageUrl, '/assets/serial/lyon-market.jpg');
  assert.equal(stages[1].artStatus, 'missing');
  assert.equal(stages[1].imageUrl, '');
  assert.equal(model.storyUsesSettingArt(episode), true);
  assert.equal(model.storyUsesSettingArt({ ...episode, panels: [episode.panels[0]] }), false);
});

test('the generated ending appears only once the server exposes a resolution', () => {
  const settled = {
    ...episode,
    status: 'completed',
    resolution: { text_fr: 'Romy sourit.', summary_native: 'Romy accepted.' },
  };
  const stages = model.buildStoryStages(settled);
  assert.equal(stages.length, 3);
  assert.equal(stages[2].kind, 'resolution');
  assert.equal(stages[2].hookQuestion, 'Romy sourit.');
  const empty = model.buildStoryStages({ ...settled, resolution: { text_fr: null, summary_native: null } });
  assert.equal(empty.length, 2, 'an empty resolution is no resolution');
});

test('the server position is restored and clamped to real panels', () => {
  assert.equal(model.storyStartIndex(episode, 2), 1);
  assert.equal(model.storyStartIndex({ ...episode, panel_index: 9 }, 2), 1);
  assert.equal(model.storyStartIndex({ ...episode, panel_index: -3 }, 2), 0);
  assert.equal(model.storyStartIndex(episode, 0), 0);
  assert.equal(model.storyStartIndex(null, 5), 0);
});

test('labels come from the engine, with plain fallbacks', () => {
  assert.equal(model.storyEpisodeLabel(episode), 'Chapitre 1 · La fête du quartier');
  assert.equal(model.storyEpisodeLabel({ ...episode, chapter: null }), 'Le feuilleton');
  assert.equal(model.storyCharacterName('gus'), 'Gus');
  assert.equal(model.storyCharacterName('Clerk'), 'Clerk');
  assert.equal(model.storyCharacterName(''), '');
});

// --- `character_name` (additive, 2026-09-06) --------------------------------

test('the server’s character_name is what the reader prints', () => {
  // A generated id the local table cannot know. Before the field existed this
  // reached the reader as "Marin_leveque".
  const generated = {
    ...episode,
    panels: [
      {
        id: 'p1', index: 0, narration_fr: 'Au comptoir.',
        dialogue: [
          { character_id: 'marin_leveque', character_name: 'Marin Lévêque', text_fr: 'Tu veux quoi ?' },
          { character_id: 'unknown_47', character_name: 'La voisine', text_fr: 'Bonsoir.' },
        ],
        image_url: null, image_status: 'unavailable',
      },
    ],
  };
  const [stage] = model.buildStoryStages(generated);
  assert.equal(stage.lines[0].who, 'Marin Lévêque');
  assert.equal(stage.lines[1].who, 'La voisine');
  // The canonical id still drives the visual accent, so a display name never
  // silently re-colours a known character.
  assert.equal(stage.lines[0].character, 'marin');
  assert.equal(model.storyCharacterName('marin_leveque', 'Marin Lévêque'), 'Marin Lévêque');
});

test('a null, blank or absent character_name falls back to the existing table', () => {
  const mixed = {
    ...episode,
    panels: [
      {
        id: 'p1', index: 0, narration_fr: '',
        dialogue: [
          { character_id: 'marchand', character_name: null, text_fr: 'Bonjour !' },
          { character_id: 'romy', character_name: '   ', text_fr: 'Tu viens ?' },
          // A server built before the field sends no `character_name` at all.
          { character_id: 'gus', text_fr: 'Salut.' },
        ],
        image_url: null, image_status: 'unavailable',
      },
    ],
  };
  const [stage] = model.buildStoryStages(mixed);
  assert.deepEqual(stage.lines.map((line) => line.who), ['Monsieur Marchand', 'Romy', 'Gus']);
  assert.equal(model.storyCharacterName('gus', null), 'Gus');
  assert.equal(model.storyCharacterName('gus', undefined), 'Gus');
  // A name with no id at all is still a name.
  assert.equal(model.storyCharacterName('', 'Lila Bernard'), 'Lila Bernard');
});
