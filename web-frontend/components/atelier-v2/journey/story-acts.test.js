// node --test components/atelier-v2/journey/story-acts.test.js
//
// Phase 2 «Folge in Akten», the app: a day may play up to three acts, each its scene,
// its reply and its ending, back to back. Every step carries its `act` (1 to 3, else 1),
// and so does every page. These tests walk a three-act day through each place that used
// to assume one scene a day — and a day of one act, or one saved before the field
// existed, stays exactly the day it was.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

// The service layer reaches the network through `@/services/api`: a stub, installed
// before anything loads it (nothing here goes to the network).
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: {}, apiService: {} },
};

const model = require('./story-episode-model.ts');
const store = require('./story-episode-store.ts');
const { chapterReached, dayCast } = require('./day-cast.ts');
const { dayMarkState } = require('./day-mark.ts');
const { journeySpeaker } = require('./journey-faces.ts');
const { firstSceneStepId, gradedInteractions } = require('./practice-formats.ts');
const { premierePoster } = require('./season-return-model.ts');
const { respondStep, stepAct } = require('@/services/daily-journey');

const part = { season_id: 's1', segment: 'g1', kind: 'gap', day_in_segment: 3 };

/** A three-act day on an Intensif rhythm, the learner in act `at` (`stepId` current). */
function threeActDay(stepId = 'reply2') {
  const steps = [
    ['rule', 'rule', 1, {}],
    ['scene1', 'scene', 1, { season_part: part, image_url: 'https://img.test/act1.png' }],
    ['reply1', 'respond', 1, { character_id: 'margaux_barman', character_name: 'Margaux' }],
    ['end1', 'resolution', 1, {}],
    ['scene2', 'scene', 2, { image_url: 'https://img.test/act2.png' }],
    ['reply2', 'respond', 2, { character_id: 'marin_leveque', character_name: 'Marin' }],
    ['end2', 'resolution', 2, {}],
    ['scene3', 'scene', 3, {}],
    ['reply3', 'respond', 3, { character_id: 'lila_bonnet', character_name: 'Lila' }],
    ['end3', 'resolution', 3, {}],
    ['recall', 'recall', 1, {}],
  ];
  const at = steps.findIndex(([id]) => id === stepId);
  return {
    id: 'journey-acts',
    status: 'active',
    current_step_id: stepId,
    scenario: { character_id: 'margaux_barman', character_name: 'Margaux', image_url: null },
    steps: steps.map(([id, kind, act, prompt], index) => ({
      id,
      kind,
      act,
      ordinal: index,
      status: at < 0 || index < at ? 'completed' : index === at ? 'active' : 'pending',
      estimated_seconds: 60,
      assistance_used: [],
      prompt,
    })),
  };
}

/** The same day as a client saved it before steps carried their act. */
function withoutActs(journey) {
  return { ...journey, steps: journey.steps.map(({ act, ...step }) => step) };
}

// ---------------------------------------------------------------------------
// Which act the day is on
// ---------------------------------------------------------------------------

test('the day is on the act of its current scene, reply or ending, and stays on it through the practice after', () => {
  assert.equal(model.storyActOf(threeActDay('scene1')), 1);
  assert.equal(model.storyActOf(threeActDay('end1')), 1);
  assert.equal(model.storyActOf(threeActDay('scene2')), 2);
  assert.equal(model.storyActOf(threeActDay('end3')), 3);
  assert.equal(model.storyActOf(threeActDay('recall')), 3, 'the practice after the acts keeps the last page');
  assert.equal(model.storyActOf(threeActDay('rule')), 1, 'before the first scene: act 1');
  assert.equal(model.journeyActCount(threeActDay()), 3);
});

test('a day of one act, and a day saved without the field, is act 1 throughout', () => {
  const saved = withoutActs(threeActDay('reply2'));
  assert.equal(model.storyActOf(saved), 1);
  assert.equal(model.journeyActCount(saved), 1);
  assert.equal(model.openActLine(saved), null);
  assert.equal(model.storyActOf(null), 1);
});

test('Home says which act is waiting, only while the day is in act 2 or 3', () => {
  assert.equal(model.openActLine(threeActDay('scene2')), 'Acte 2 t’attend');
  assert.equal(model.openActLine(threeActDay('end3')), 'Acte 3 t’attend');
  assert.equal(model.openActLine(threeActDay('reply1')), null);
  assert.equal(model.openActLine(threeActDay('recall')), null, 'the practice after the acts is not an act');
});

test('acts 2 and 3 open on a title card; act 1 and a card already read have none', () => {
  assert.deepEqual(model.actTitleCard({ act: 2, role: 'soir', title: ' La radio du soir ' }), {
    act: 2,
    heading: 'Acte 2 · Plus tard',
    title: 'La radio du soir',
  });
  assert.deepEqual(model.actTitleCard({ act: 3, role: 'cote', title: null }), {
    act: 3,
    heading: 'Acte 3 · Pendant ce temps',
    title: null,
  });
  assert.equal(model.actTitleCard({ act: 2, role: 'inconnu' }).heading, 'Acte 2');
  assert.equal(model.actTitleCard({ act: 1, role: 'fil', title: 'La boîte' }), null);
  assert.equal(model.actTitleCard({ act: 2, role: 'soir', title: 'x', dismissed: true }), null);
});

// ---------------------------------------------------------------------------
// One page per act
// ---------------------------------------------------------------------------

test('each act keeps its own page in the cache; act 1 keeps the key every one-act day has', async () => {
  store.clearStoryEpisodes();
  assert.equal(store.storyEpisodeKey('j', 1), 'j');
  assert.equal(store.storyEpisodeKey('j', 2), 'j#act2');
  assert.equal(store.storyEpisodeKey(null, 2), null);
  const page = (id, act) => ({ id, act, panels: [{ index: 0, dialogue: [] }] });
  await store.loadStoryEpisode(store.storyEpisodeKey('j', 1), async () => page('first', 1));
  await store.loadStoryEpisode(store.storyEpisodeKey('j', 2), async () => page('second', 2));
  assert.equal(store.getStoryEpisodeEntry('j').episode.id, 'first');
  assert.equal(store.getStoryEpisodeEntry('j#act2').episode.id, 'second');
  store.clearStoryEpisodes();
});

test('the finale closes its own act’s page', () => {
  const journey = threeActDay('end2');
  const second = { id: 'second', act: 2, panels: [{ index: 0, dialogue: [] }] };
  assert.equal(model.journeyStoryPage(journey, second, 2), second);
  // No engine page: an authored scene's own panels, of that act only.
  const authored = {
    ...journey,
    steps: journey.steps.map((step) =>
      step.id === 'scene1' ? { ...step, prompt: { panels: [{ index: 0, image_url: 'a.png', dialogue: [] }] } } : step,
    ),
  };
  assert.ok(model.journeyStoryPage(authored, null, 1), 'act 1 finds its authored page');
  assert.equal(model.journeyStoryPage(authored, null, 2), null, 'act 2 never closes act 1’s page');
});

// ---------------------------------------------------------------------------
// The places that assumed one scene a day
// ---------------------------------------------------------------------------

test('a later act’s scene and ending show that act’s character; act 1’s show the day’s', () => {
  const journey = threeActDay('scene2');
  const step = (id) => journey.steps.find((item) => item.id === id);
  assert.equal(journeySpeaker(journey, step('scene1')).name, 'Margaux');
  assert.equal(journeySpeaker(journey, step('scene2')).name, 'Marin');
  assert.equal(journeySpeaker(journey, step('end2')).name, 'Marin');
  assert.equal(journeySpeaker(journey, step('reply3')).name, 'Lila');
  assert.equal(journeySpeaker(journey, step('end3')).name, 'Lila');
  // A caller that only knows the scenario still gets the day's face.
  assert.equal(journeySpeaker({ scenario: journey.scenario }, step('scene2')).name, 'Margaux');
});

test('the day’s walk-ons are the people of every act’s page', () => {
  const page = (...ids) => ({ panels: [{ dialogue: ids.map((id) => ({ character_id: id, character_name: null })) }] });
  const cast = dayCast(threeActDay(), [page('augustin_de_roncourt'), page('marin_leveque'), null]);
  assert.deepEqual(cast.slice(0, 2), ['augustin_de_roncourt', 'marin_leveque']);
  assert.ok(cast.includes('lila_bonnet'), 'act 3’s character, from its reply');
  // One page, as before.
  assert.deepEqual(dayCast(threeActDay(), page('augustin_de_roncourt'))[0], 'augustin_de_roncourt');
});

test('the season part is reached with the day’s first scene, act 1’s', () => {
  assert.deepEqual(chapterReached(threeActDay('scene2')), part);
  assert.equal(chapterReached(threeActDay('scene1')), null, 'not before act 1’s page is read');
});

test('the day mark: every act’s scene, reply and ending count; the practice after the last ending closes the day', () => {
  const inAct2 = dayMarkState(threeActDay('reply2'));
  // The one recall comes after the last ending: it closes the day («Bouclé»), so there is no words group.
  assert.deepEqual(inAct2.groups, { scene: 'todo', recall: 'absent', respond: 'active', resolution: 'todo' });
  const atTheEnd = dayMarkState(threeActDay('recall'));
  assert.deepEqual(atTheEnd.groups, { scene: 'done', recall: 'absent', respond: 'done', resolution: 'active' });
});

test('the first scene is act 1’s, and every act’s reply is answered today', () => {
  assert.equal(firstSceneStepId(threeActDay()), 'scene1');
  assert.equal(gradedInteractions(threeActDay()), 4, 'three replies and one recall');
});

test('the premiere poster is the day’s first panel: act 1’s', () => {
  assert.equal(premierePoster(threeActDay()), 'https://img.test/act1.png');
});

test('a step’s act is 1 unless it says otherwise; each act has its own reply', () => {
  assert.equal(stepAct({ act: 3 }), 3);
  assert.equal(stepAct({}), 1);
  assert.equal(stepAct({ act: 0 }), 1);
  assert.equal(stepAct(null), 1);
  const journey = threeActDay();
  assert.equal(respondStep(journey).id, 'reply1', 'the day’s reply is its first act’s');
  assert.equal(respondStep(journey, 3).id, 'reply3');
  assert.equal(respondStep(withoutActs(journey)).id, 'reply1');
});
