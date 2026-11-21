// node --test components/atelier-v2/home/quartier-door.test.js
//
// P12 · Le Quartier switched on (owner, 17 Nov). The door is open in the build every learner gets:
// launch-flags.json has it, a production build serves /quartier, Home draws one quiet chip to it
// for roaming, and the day's card offers today's scene both ways (owner decision 9, proposal (b):
// a choice beside the page, not the default) on the days the quarter can stage it, and only then.

delete process.env.NEXT_PUBLIC_QUARTIER_VISIBLE;

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
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

const { HomeScreen } = require('./HomeScreen.tsx');
const { JourneyTodayCard } = require('../journey/JourneyTodayCard.tsx');
const state = require('../journey/journey-state.ts');
const { dayMarkState } = require('../journey/day-mark.ts');
const { QUARTIER_VISIBLE } = require('@/lib/launch-flags.ts');
const door = require('@/lib/quartier/home-door.ts');

const h = React.createElement;
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');
const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8')).response;

const home = (language, props = {}) =>
  renderToStaticMarkup(
    h(HomeScreen, {
      dateLabel: 'mardi 23 septembre',
      editionLabel: 'Édition Nº 4 · A1.1',
      streak: 4,
      language,
      tiles: [],
      ...props,
    }),
  );

function controllerFor(envelope, language) {
  return {
    phase: state.phaseFromEnvelope(envelope),
    feedback: { kind: 'idle' },
    envelope,
    journey: envelope.journey ?? null,
    step: null,
    respondPrompt: null,
    controlLanguage: language,
    legacyResume: envelope.legacy_resume ?? null,
    progress: state.journeyProgress(envelope.journey ?? null),
    busy: false,
    help: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
}

const card = (envelope, language) =>
  renderToStaticMarkup(h(JourneyTodayCard, { controller: controllerFor({ ...envelope, control_language: language }, language), onOpen: () => {} }));

const SECOND = { en: 'Play in the Quartier', de: 'Im Quartier spielen', fr: 'Jouer dans le Quartier' };

/** The first day, offered at a place the quarter has built (Le Mistral), or one it has not. */
const offerAt = (location_id) => {
  const envelope = fixture('first_day');
  return { ...envelope, available: { ...envelope.available, location_id } };
};

/** A day under way whose scene (an authored page) is set at `location`. */
function dayAt(location) {
  const line = { who: 'caption', kind: 'caption', text_fr: 'Il pleut.' };
  const stage = {
    key: 't3.b',
    number: 2,
    title_fr: 'Là-haut',
    location_id: location,
    movements: [
      { kind: 'panel', id: 'b.p1', location_id: location, lines: [line] },
      { kind: 'turn', id: 'b.turn1', to: 'lila_moreau', to_name: 'Lila', task_native: 'Say what you know.', panel: { kind: 'panel', id: 'b.p2', lines: [] } },
    ],
  };
  const created = fixture('cafe_journey_created');
  const journey = created.journey ?? created;
  return {
    ...fixture('first_day'),
    journey: {
      ...journey,
      steps: journey.steps.map((s) => (s.kind === 'scene' ? { ...s, prompt: { ...s.prompt, stage } } : s)),
    },
  };
}

test('the door is open in the build every learner gets: launch-flags.json, and a production /quartier', async () => {
  const flags = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, 'launch-flags.json'), 'utf8'));
  assert.equal(flags.quartierVisible, true);
  assert.equal(QUARTIER_VISIBLE, true, 'no NEXT_PUBLIC_QUARTIER_VISIBLE needed');
  const env = process.env.NODE_ENV;
  process.env.NODE_ENV = 'production';
  try {
    const { getStaticProps } = require('../../../pages/quartier.tsx');
    const served = await getStaticProps();
    assert.equal(served.notFound, undefined, 'a production build serves the page');
    assert.deepEqual(served, { props: {} });
  } finally {
    process.env.NODE_ENV = env;
  }
});

test('Home has one quiet door to Le Quartier for roaming, with the day plan or without it', () => {
  for (const language of ['en', 'de', 'fr']) {
    for (const html of [home(language, { day: dayMarkState(null, language) }), home(language)]) {
      assert.equal((html.match(/href="\/quartier"/g) || []).length, 1, `${language}: one door`);
      assert.match(html, /data-chip="quartier"/);
      assert.match(html, /aria-label="(Entrer dans|Enter|Le Quartier betreten)/);
      assert.doesNotMatch(html, /av2-chip[^"]*av2-btn--primary/, 'the chip is never a press');
    }
  }
  // in the day's own row of chips, never one of its two
  const chips = [
    { id: 'courrier', label: 'New letter', href: '/missions' },
    { id: 'lexique', label: '3 words', href: '/vocabulary/review' },
  ];
  const html = home('en', { day: dayMarkState(null, 'en'), chips });
  assert.equal((html.match(/class="av2-home__section av2-home__chips"/g) || []).length, 1, 'one row');
  assert.match(html, /data-chip="courrier"[\s\S]*data-chip="lexique"[\s\S]*data-chip="quartier"/);
});

test('a day the quarter can stage offers the scene both ways: the page first, the quarter quieter beside it', () => {
  for (const language of ['en', 'de', 'fr']) {
    for (const [what, envelope] of [
      ['offered at Le Mistral', offerAt('le_mistral')],
      ['under way, set on the quai', dayAt('quai_de_valmy')],
    ]) {
      const html = card(envelope, language);
      const second = html.match(/<a[^>]*data-scene-way="quartier"[^>]*>[\s\S]*?<\/a>/);
      assert.ok(second, `${language} ${what}: the second action`);
      assert.match(second[0], /href="\/quartier"/);
      assert.match(second[0], /av2-btn--secondary/, 'quieter than the day’s press');
      assert.ok(second[0].includes(SECOND[language]), `${language}: ${second[0]}`);
      assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, `${language} ${what}: one press, the page’s`);
      assert.match(html, /<button[^>]*data-scene-way="page"/);
    }
  }
});

test('a day the quarter cannot stage shows no second action', () => {
  for (const language of ['en', 'de', 'fr']) {
    for (const [what, envelope] of [
      ['offered at the gare de l’Est (not built)', offerAt('gare_de_lest')],
      ['under way at the gare de l’Est (not built)', dayAt('gare_de_lest')],
      ['finished', fixture('completed')],
    ]) {
      const html = card(envelope, language);
      assert.doesNotMatch(html, /data-scene-way="quartier"/, `${language}: ${what}`);
      assert.ok(!html.includes(SECOND[language]), `${language}: ${what}`);
    }
  }
  // and a build without the quarter offers it on no day
  assert.equal(door.quartierCanStage(state.phaseFromEnvelope(offerAt('le_mistral')), false), false);
});

test('the learner’s last way in is remembered on the device and is the primary one next time', () => {
  const kept = new Map();
  const storage = { getItem: (k) => (kept.has(k) ? kept.get(k) : null), setItem: (k, v) => kept.set(k, String(v)) };
  assert.equal(door.readSceneWay(storage), 'page', 'the page until the quarter is taken');
  door.writeSceneWay('quartier', storage);
  assert.equal(kept.get(door.SCENE_WAY_KEY), 'quartier');
  assert.equal(door.readSceneWay(storage), 'quartier');
  door.writeSceneWay('page', storage);
  assert.equal(door.readSceneWay(storage), 'page');
  const refusing = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
  assert.equal(door.readSceneWay(refusing), 'page');
  assert.doesNotThrow(() => door.writeSceneWay('quartier', refusing));
  // the swap itself (the remembered way drawn red, the page as «Read as a page») happens after
  // mount, so the static render cannot see it: the card reads the way in an effect
  const src = fs.readFileSync(path.join(__dirname, '../journey/JourneyTodayCard.tsx'), 'utf8');
  assert.match(src, /setWay\(readSceneWay\(\)\)/);
  assert.match(src, /copy\.read_as_page/);
});
