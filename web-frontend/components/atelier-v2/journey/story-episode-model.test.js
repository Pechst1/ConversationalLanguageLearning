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

// ---------------------------------------------------------------------------
// WP-44 — the reader artboards
// ---------------------------------------------------------------------------

const fs = require('node:fs');

const bubblePanel = {
  kind: 'panel',
  key: 'panel:p1',
  ordinal: 1,
  panelId: 'p1',
  panelIndex: 0,
  title: '',
  beat: '',
  imageUrl: '/assets/serial/mistral.jpg',
  artStatus: 'ready',
  character: 'gus',
  lines: [{ key: 'p1-l0', who: 'Augustin', fr: 'Je peux aider.', en: '', character: 'gus' }],
  caption: 'Augustin sourit.',
  tasks: [],
};

test('one line from a named speaker over real art is a bubble; everything else is a card', () => {
  // The rule is tested under `'auto'` explicitly: the shipped constant is
  // `'line'` (owner's choice, 2026-09-17), which makes every panel a card.
  const auto = (stage) => model.panelReaderVariant(stage, 'auto');
  assert.equal(auto(bubblePanel), 'bubble');
  assert.equal(model.panelReaderVariant(bubblePanel), 'line', 'shipped: the line in a card under the art');

  // narration only
  assert.equal(model.panelReaderVariant({ ...bubblePanel, lines: [] }), 'line');
  // two or more lines
  assert.equal(
    model.panelReaderVariant({
      ...bubblePanel,
      lines: [...bubblePanel.lines, { key: 'p1-l1', who: 'Lila', fr: 'Merci.', en: '', character: 'lila' }],
    }),
    'line',
  );
  // a line whose speaker the server could not name
  assert.equal(
    model.panelReaderVariant({ ...bubblePanel, lines: [{ ...bubblePanel.lines[0], who: '' }] }),
    'line',
  );
  // no art to put a bubble on
  assert.equal(
    model.panelReaderVariant({ ...bubblePanel, artStatus: 'missing', imageUrl: '' }),
    'line',
  );
  // the resolution stage is not a panel
  assert.equal(model.panelReaderVariant({ kind: 'resolution', key: 'r', ordinal: 2, tasks: [] }), 'line');
  assert.equal(model.panelReaderVariant(null), 'line');
});

test('the variant is one constant, and flipping it flips the whole reader', () => {
  assert.equal(model.READER_VARIANT, 'line', 'variant B — the line in a card under the art — is the owner’s choice (2026-09-17)');
  // forced B: even the panel that qualifies for a bubble becomes a card
  assert.equal(model.panelReaderVariant(bubblePanel, 'line'), 'line');
  // forced A: a two-line panel over art becomes a bubble
  assert.equal(
    model.panelReaderVariant(
      { ...bubblePanel, lines: [...bubblePanel.lines, { key: 'x', who: 'Lila', fr: 'Merci.', en: '', character: 'lila' }] },
      'bubble',
    ),
    'bubble',
  );
  // …but never over art that does not exist
  assert.equal(model.panelReaderVariant({ ...bubblePanel, artStatus: 'missing' }, 'bubble'), 'line');
});

test('the production prefix «Panneau N :» never reaches the learner', () => {
  assert.equal(model.stripPanelPrefix('Panneau 1 : La pluie a inondé la cave.'), 'La pluie a inondé la cave.');
  assert.equal(model.stripPanelPrefix('Panneau 3 — un silence.'), 'un silence.');
  assert.equal(model.stripPanelPrefix('panneau 12: la suite'), 'la suite');
  // a sentence that merely talks about a sign is not a prefix
  assert.equal(
    model.stripPanelPrefix('Le panneau indique la sortie.'),
    'Le panneau indique la sortie.',
  );
  assert.equal(model.stripPanelPrefix(null), '');

  const prefixed = {
    ...episode,
    panels: [
      {
        id: 'p9', index: 0, narration_fr: 'Panneau 1 : Le lendemain, au marché.',
        dialogue: [{ character_id: 'romy', text_fr: 'Bonjour !' }],
        image_url: null, image_status: 'unavailable',
      },
    ],
  };
  assert.equal(model.buildStoryStages(prefixed)[0].caption, 'Le lendemain, au marché.');
  assert.equal(model.episodeListenLines(prefixed)[0].fr, 'Le lendemain, au marché.');
});

test('the «Décor de référence» banner is gone, and the fact is kept for telemetry', () => {
  const reader = fs.readFileSync(require('node:path').join(__dirname, 'StoryEpisodeReader.tsx'), 'utf8');
  // The sentence itself, not the comment that records why it went.
  assert.ok(!reader.includes('montre le lieu'), 'the disclaimer sentence is not rendered');
  assert.ok(!reader.includes('planche inédite'));
  assert.ok(!reader.includes('className="fr-state"'), 'no banner element is passed to the reader');
  assert.ok(
    reader.includes("artProvenance={storyUsesSettingArt(episode) ? 'setting_reference' : null}"),
    'the provenance still reaches the DOM for telemetry',
  );
});

test("a panel's own drawing is shown, and a panel still being drawn shows its plate", () => {
  const drawn = {
    ...episode,
    panels: [
      { ...episode.panels[1], image_url: '/media/graphic-novel/scenes/s/panel-0.webp', image_status: 'panel_art' },
      { ...episode.panels[0], image_url: '/assets/serial/locations/le_mistral-counter.webp', image_status: 'rendering' },
    ],
  };
  const stages = model.buildStoryStages(drawn);
  assert.deepEqual(stages.map((s) => s.artStatus), ['ready', 'ready']);
  assert.equal(stages[0].imageUrl, '/media/graphic-novel/scenes/s/panel-0.webp');
  assert.equal(stages[1].imageUrl, '/assets/serial/locations/le_mistral-counter.webp');
  assert.equal(model.storyArtRendering(drawn), true, 'the step polls while a panel is rendering');
  assert.equal(model.storyUsesSettingArt(drawn), true, 'the plate on a rendering panel is still a plate');

  const done = { ...drawn, panels: drawn.panels.map((p) => ({ ...p, image_status: 'panel_art' })) };
  assert.equal(model.storyArtRendering(done), false);
  assert.equal(model.storyUsesSettingArt(done), false, 'drawn panels are not setting art');
});

test("an authored scene's page reads like an episode and saves nothing", () => {
  assert.equal(model.authoredPageEpisode('j', 's', null), null);
  assert.equal(model.authoredPageEpisode('j', 's', []), null);
  const page = model.authoredPageEpisode('j', 's', [
    { id: 'a0', index: 0, narration_fr: 'Il pleut.', dialogue: [], image_url: '/assets/serial/scenes/order_at_cafe/panel-1.webp', image_status: 'panel_art' },
  ]);
  assert.equal(page.id, 'authored:s');
  assert.equal(page.resolution, null);
  const [stage] = model.buildStoryStages(page);
  assert.equal(stage.artStatus, 'ready');
  assert.equal(stage.caption, 'Il pleut.');
});

// ---------------------------------------------------------------------------
// WP-90 «La planche»
// ---------------------------------------------------------------------------

const planche = {
  ...episode,
  panels: [
    {
      id: 'q1', index: 0, narration_fr: 'Au Mistral.',
      alt_native: 'Margaux behind the counter.',
      dialogue: [
        { character_id: 'toi', text_fr: '' },
        { character_id: 'margaux_barman', character_name: 'Margaux', text_fr: 'Bonjour !', mood: 'happy', text_native: 'Hello!' },
        { character_id: 'marin_leveque', text_fr: 'Pardon !', mood: 'cross', text_native: null },
      ],
      image_url: '/assets/serial/locations/le_mistral-counter.webp', image_status: 'rendering',
    },
    {
      id: 'q2', index: 1, narration_fr: 'Panneau 2 : Il pleut.',
      overlay_payload: { alt_native: 'Rain on the terrace.' },
      dialogue: [], image_url: '/media/p2.webp', image_status: 'panel_art',
    },
    {
      id: 'q3', index: 2, narration_fr: 'La nuit tombe.',
      dialogue: [], image_url: '/assets/serial/locations/le_mistral-booth.webp', image_status: 'setting_reference',
    },
  ],
};

test('WP-90: faces act — each line wears its own mood', () => {
  const [first] = model.buildStoryStages(planche);
  assert.deepEqual(first.lines.map((line) => line.faceMood), ['happy', 'cross']);
  assert.equal(first.lines[0].faceId, 'margaux_barman');
});

test('WP-90: text_native brings back «Traduire la case»; a line without one stays French-only', () => {
  const [first] = model.buildStoryStages(planche);
  assert.equal(first.lines[0].en, 'Hello!');
  assert.equal(first.lines[1].en, '');
  assert.equal(model.storyLineNative({ text_native: '  Hi  ' }), 'Hi');
  assert.equal(model.storyLineNative({}), '', 'an older payload has no translation');
});

test('WP-90: a line keeps its raw-index audio key and its speaker id', () => {
  const [first] = model.buildStoryStages(planche);
  // The empty learner line at index 0 is dropped, but the keys still count it —
  // exactly as app/services/episode_audio.py does.
  assert.deepEqual(first.lines.map((line) => line.audioKey), ['q1:l1', 'q1:l2']);
  assert.deepEqual(first.lines.map((line) => line.key), ['q1-l0', 'q1-l1']);
  assert.equal(first.lines[1].speakerId, 'marin_leveque');
});

test('WP-90: a plate standing in for a drawing is marked pending; alt comes from alt_native, then narration', () => {
  const stages = model.buildStoryStages(planche);
  assert.deepEqual(stages.map((stage) => stage.artPending), [true, false, false],
    'a setting_reference plate is simply the plate — it never renders');
  assert.deepEqual(stages.map((stage) => stage.imageAlt), [
    'Margaux behind the counter.',
    'Rain on the terrace.',
    'La nuit tombe.',
  ]);
  assert.equal(model.storyPanelAlt({ narration_fr: 'Panneau 3 : Il pleut.' }), 'Il pleut.');
  assert.equal(model.storyPanelAlt(null), '');
});

test('WP-90: the art poll runs only while a panel renders, and stops at a ceiling', () => {
  assert.equal(model.shouldPollStoryArt(planche, 0), true);
  assert.equal(model.shouldPollStoryArt(planche, model.STORY_ART_POLL_LIMIT), false);
  const drawn = { ...planche, panels: planche.panels.map((p) => ({ ...p, image_status: 'panel_art' })) };
  assert.equal(model.shouldPollStoryArt(drawn, 0), false);
  assert.equal(model.shouldPollStoryArt(null, 0), false);
  assert.ok(model.STORY_ART_POLL_MS * model.STORY_ART_POLL_LIMIT >= 4 * 60_000, 'minutes, not seconds');
  assert.equal(model.stepReadsStoryEpisode('scene'), true);
  assert.equal(model.stepReadsStoryEpisode('resolution'), true);
  assert.equal(model.stepReadsStoryEpisode('recall'), false);
});

test('WP-90: the ending is the page’s last panel', () => {
  const finale = model.storyFinaleStage(
    'res-1',
    { character_line_fr: 'À demain !', summary_native: 'She remembered you.', image_url: '/r.webp', mood: 'moved' },
    { id: 'margaux_barman', name: 'Margaux' },
  );
  assert.equal(finale.kind, 'resolution');
  assert.equal(finale.finale.line.fr, 'À demain !');
  assert.equal(finale.finale.line.faceId, 'margaux_barman');
  assert.equal(finale.finale.line.faceMood, 'moved');
  assert.equal(finale.finale.imageAlt, 'She remembered you.', 'the summary describes the picture when nothing else does');
  assert.equal(finale.finale.waiting, false);

  const stages = model.storyStagesWithFinale({ ...planche, resolution: { text_fr: 'Fin.', summary_native: 'End.' } }, finale);
  assert.deepEqual(stages.map((stage) => stage.kind), ['panel', 'panel', 'panel', 'resolution']);
  assert.equal(stages[3].key, 'finale:res-1', 'the episode’s own «À suivre» gives way to the finale');
  assert.equal(stages[3].ordinal, 4);

  const waiting = model.storyFinaleStage('res-1', { story_pending: true }, null);
  assert.equal(waiting.finale.waiting, true);
  assert.equal(waiting.finale.line, null, 'no line, no face invented');
});

test('WP-90: the finale closes the page the learner read — the engine’s, else the authored one', () => {
  const journey = {
    id: 'j',
    steps: [
      { id: 's1', kind: 'scene', prompt: { panels: [{ id: 'a0', index: 0, narration_fr: 'Il pleut.', dialogue: [], image_url: '/x.webp', image_status: 'panel_art' }] } },
      { id: 'r1', kind: 'resolution', prompt: {} },
    ],
  };
  assert.equal(model.journeyStoryPage(journey, planche), planche);
  assert.equal(model.journeyStoryPage(journey, null).id, 'authored:s1');
  assert.equal(model.journeyStoryPage({ id: 'j', steps: [] }, null), null);
  assert.equal(model.journeyStoryPage(null, null), null);
  const alone = model.finaleOnlyEpisode('j', 'r1');
  assert.deepEqual(alone.panels, []);
});

test('WP-90: the episode cache — one request at a time, and a failed re-read keeps the page', async () => {
  const store = require('./story-episode-store.ts');
  store.clearStoryEpisodes();
  let calls = 0;
  let fail = false;
  const fetcher = async () => {
    calls += 1;
    if (fail) throw new Error('offline');
    return planche;
  };
  const [a, b] = await Promise.all([store.loadStoryEpisode('j1', fetcher), store.loadStoryEpisode('j1', fetcher)]);
  assert.equal(calls, 1, 'a second caller awaits the first request');
  assert.equal(a, b);
  assert.equal(store.getStoryEpisodeEntry('j1').kind, 'episode');
  fail = true;
  const again = await store.loadStoryEpisode('j1', fetcher);
  assert.equal(again.kind, 'episode', 'a poll that fails does not blank the reader');
  assert.equal((await store.loadStoryEpisode('j2', fetcher)).kind, 'none', 'no page: the plain scene');
  assert.equal((await store.loadStoryEpisode('j3', async () => null)).kind, 'none');
  store.clearStoryEpisodes();
  assert.equal(store.getStoryEpisodeEntry('j1'), undefined);
});

// ---------------------------------------------------------------------------
// WP-110 «La planche vivante»
// ---------------------------------------------------------------------------

const finished = {
  ...episode,
  status: 'completed',
  resolution: { text_fr: 'Deux clés pour la même porte.', summary_native: 'Two keys.' },
  page: {
    a_suivre_fr: 'Demain, Camille.',
    rows: [
      {
        id: 'act:a.p1:0', movement: 'act', narration_fr: 'Paris. Il pleut.',
        dialogue: [], image_url: '/assets/serial/locations/marche_canal.webp', image_status: 'setting_reference',
      },
      {
        id: 'turn:a.p6:1', movement: 'turn', narration_fr: '',
        dialogue: [
          { character_id: 'gus', character_name: 'Augustin « Gus » de Roncourt', text_fr: 'Vous êtes qui, exactement ?', kind: 'speech', you: false },
          { character_id: 'toi', character_name: null, text_fr: "Odile, c'est ma grand-mère.", kind: 'you', you: true },
        ],
        image_url: '/assets/serial/locations/le_mistral-counter.webp', image_status: 'setting_reference',
      },
      {
        id: 'reaction:r1:2', movement: 'reaction', narration_fr: '',
        dialogue: [{ character_id: 'margaux', character_name: 'Margaux', text_fr: 'Elle prenait ça.', kind: 'speech', you: false }],
        image_url: '/assets/serial/locations/le_mistral-counter.webp', image_status: 'setting_reference',
      },
    ],
  },
};

test('WP-110: a finished day reads as its page — the scene, your line, the reactions, then the ending', () => {
  const stages = model.buildStoryStages(finished);
  assert.deepEqual(stages.map((stage) => stage.movement ?? stage.kind), ['act', 'turn', 'reaction', 'resolution']);
  const turn = stages[1];
  const mine = turn.lines.filter((line) => line.you);
  assert.equal(mine.length, 1);
  assert.equal(mine[0].fr, "Odile, c'est ma grand-mère.");
  assert.equal(mine[0].faceId, null, 'the learner has no drawn face');
  assert.equal(model.panelReaderVariant(turn, 'auto'), 'bubble', 'your line is the balloon in its panel');
  assert.equal(model.panelReaderVariant(turn), 'bubble', 'even with the owner’s captions switch (variant B)');
  assert.equal(model.panelReaderVariant(stages[2]), 'line', 'a character keeps a caption');
  assert.equal(stages[3].aSuivre, 'Demain, Camille.');
});

test('WP-110: an unfinished day keeps its scene panels (no page, nothing said yet)', () => {
  const stages = model.buildStoryStages({ ...finished, status: 'available', resolution: null, page: null });
  assert.deepEqual(stages.map((stage) => stage.panelId), ['p1', 'p2']);
});

test('WP-110: the ending step closes the finished page on «À suivre…»', () => {
  const finale = model.storyFinaleStage('res-1', { character_line_fr: 'Deux clés.' }, { id: 'margaux', name: 'Margaux' });
  const stages = model.storyStagesWithFinale(finished, finale);
  assert.deepEqual(stages.map((stage) => stage.kind), ['panel', 'panel', 'panel', 'resolution']);
  assert.equal(stages[3].aSuivre, 'Demain, Camille.');
});
