// node --test components/atelier-v2/home/quartier-door-engine.test.js
//
// P12 round 2 · «Im Quartier spielen» on Home, as Home is drawn for a learner with the story
// engine on. Observed 17 Nov (walk-integration-a1/b1, shots a1-d1-home.png, b1-d1-home.png): in six
// days at A1 and six at B1 the day's card showed «Heute starten» / «Commencer» alone, also on day 1,
// whose scene the A1 learner then played in Le Quartier through the chip without trouble.
//
// Why: the card on Home is `JourneyTodayCard` (pages/atelier.tsx hands it to `HomeScreen` as the
// hero), in its `offer` phase. The offer is the story engine's invitation
// (`living_story.describe_next`: «Votre prochain chapitre», `location_id: ""`), so the door's
// check (`stageOf(scenario.location_id)`) never knew where the day plays. PR 881's test used the
// authored first-day fixture (`location_id: "le_mistral"`), which an engine learner never gets.
//
// The envelopes here are what `GET /daily-journeys/today` answers for a fresh A1 learner with the
// season on (dumped from the backend under tests/test_r2_quartier_round_two.py's setup).

delete process.env.NEXT_PUBLIC_QUARTIER_VISIBLE;

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = { id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} } };

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { HomeScreen } = require('./HomeScreen.tsx');
const { JourneyTodayCard } = require('../journey/JourneyTodayCard.tsx');
const state = require('../journey/journey-state.ts');
const { dayMarkState } = require('../journey/day-mark.ts');

const h = React.createElement;
const ENVELOPES = require('./quartier-door-engine.fixture.json');
const SECOND = { en: 'Play in the Quartier', de: 'Im Quartier spielen', fr: 'Jouer dans le Quartier' };
const START = { en: 'Start today', de: 'Heute starten', fr: 'Commencer' };

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

/** Home as `pages/atelier.tsx` draws it before Start: `HomeScreen` with the journey card as its hero. */
function home(day, language) {
  const envelope = { ...ENVELOPES[day], control_language: language };
  const card = h(JourneyTodayCard, { controller: controllerFor(envelope, language), onOpen: () => {}, restOfDayOpen: false });
  return renderToStaticMarkup(
    h(HomeScreen, {
      hero: card,
      dateLabel: 'Mittwoch, 18. Nov.',
      editionLabel: 'Édition Nº 1 · A1.1',
      streak: 0,
      language,
      tiles: [],
      day: dayMarkState(null, language),
    }),
  );
}

test('the envelope is the engine’s: the offer names no place, the headline says where the page plays', () => {
  const day1 = ENVELOPES.day1;
  assert.equal(day1.journey, null, 'before Start');
  assert.equal(day1.available.scenario_key, 'story_next');
  assert.equal(day1.available.location_id, '', 'the walk’s offer: no place');
  assert.equal(day1.headline.stage.key, 't1.a');
});

test('day 1 at Le Mistral: Home offers the scene both ways, the page first and «Im Quartier spielen» beside it', () => {
  for (const language of ['de', 'en', 'fr']) {
    const html = home('day1', language);
    assert.ok(html.includes(START[language]), `${language}: the day’s press`);
    const second = html.match(/<a[^>]*data-scene-way="quartier"[^>]*>[\s\S]*?<\/a>/);
    assert.ok(second, `${language}: the second action is on Home`);
    assert.match(second[0], /href="\/quartier"/);
    assert.ok(second[0].includes(SECOND[language]), second[0]);
    assert.equal((html.match(/av2-btn--primary/g) || []).length, 1, 'one press, the page’s');
  }
});

test('day 2 goes up the stairwell, a place not finished: no second action', () => {
  for (const language of ['de', 'en', 'fr']) {
    const html = home('day2', language);
    assert.ok(html.includes(START[language]), `${language}: the day’s press`);
    assert.doesNotMatch(html, /data-scene-way="quartier"/, language);
    assert.ok(!html.includes(SECOND[language]), language);
  }
});

test('a day whose page is not known before Start (a gap day) is offered as a page only', () => {
  const gap = { ...ENVELOPES.day1, headline: { ...ENVELOPES.day1.headline, title_fr: null, stage: null } };
  const html = renderToStaticMarkup(h(JourneyTodayCard, { controller: controllerFor({ ...gap, control_language: 'de' }, 'de'), onOpen: () => {} }));
  assert.doesNotMatch(html, /data-scene-way="quartier"/);
});
