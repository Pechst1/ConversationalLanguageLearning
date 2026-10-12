// node --test lib/first-steps.test.js
//
// GENTLE-ONBOARDING (owner, 2026-10-12): the walkthrough, the first-time
// stickers and the first day's route (story → La Forge → words).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const steps = require('./first-steps.ts');

function memory() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
  };
}

test('the first day runs story, then La Forge, then the words', () => {
  assert.deepEqual([...steps.ROUTE_STAGES], ['story', 'forge', 'words']);
  assert.equal(steps.nextRouteStage([]), 'story');
  assert.equal(steps.nextRouteStage(['story']), 'forge');
  assert.equal(steps.nextRouteStage(['story', 'forge']), 'words');
  // Words done before the forge still sends the learner to the forge next.
  assert.equal(steps.nextRouteStage(['story', 'words']), 'forge');
  assert.equal(steps.nextRouteStage(['story', 'forge', 'words']), null);
});

test('the route belongs to the first day only', () => {
  const store = memory();
  assert.equal(steps.onFirstDay(store, '2026-10-12'), false);
  steps.markRouteStage(store, 'story', '2026-10-12');
  assert.deepEqual(steps.routeDone(store), [], 'nothing is ticked before the first day begins');

  steps.beginFirstDay(store, '2026-10-12');
  assert.equal(steps.onFirstDay(store, '2026-10-12'), true);
  steps.markRouteStage(store, 'story', '2026-10-12');
  steps.markRouteStage(store, 'story', '2026-10-12');
  steps.markRouteStage(store, 'forge', '2026-10-12');
  assert.deepEqual(steps.routeDone(store), ['story', 'forge']);

  // Re-entering the first day keeps what is done; the next day ticks nothing.
  steps.beginFirstDay(store, '2026-10-12');
  assert.deepEqual(steps.routeDone(store), ['story', 'forge']);
  assert.equal(steps.onFirstDay(store, '2026-10-13'), false);
  steps.markRouteStage(store, 'words', '2026-10-13');
  assert.deepEqual(steps.routeDone(store), ['story', 'forge']);
});

test('each sticker and the walkthrough show once, and never nag without storage', () => {
  const store = memory();
  assert.equal(steps.stickerSeen(store, 'respond'), false);
  steps.rememberSticker(store, 'respond');
  assert.equal(steps.stickerSeen(store, 'respond'), true);
  assert.equal(steps.stickerSeen(store, 'recall'), false);
  assert.equal(steps.walkthroughSeen(store), false);
  steps.rememberWalkthrough(store);
  assert.equal(steps.walkthroughSeen(store), true);
  assert.equal(steps.stickerSeen(null, 'scene'), true);
  assert.equal(steps.walkthroughSeen(null), true);
});

test('every step kind the day can deal has a sticker; unknown kinds have none', () => {
  for (const kind of ['scene', 'rule', 'recall', 'respond', 'resolution', 'read', 'desk', 'forge']) {
    assert.equal(steps.stickerFor(kind), kind);
  }
  assert.equal(steps.stickerFor('papier'), null);
  assert.equal(steps.stickerFor(null), null);
});

test('the copy is complete in German, English and French, and German says du', () => {
  const keys = Object.keys(steps.FIRST_STEP_SHAPE);
  for (const language of ['de', 'en', 'fr']) {
    const copy = steps.firstStepsCopy(language);
    for (const key of keys) {
      assert.ok(copy.stickers[key].title && copy.stickers[key].body, `${language}.${key}`);
    }
    for (const shape of ['story', 'reward', 'action', 'done']) assert.ok(copy.walkthrough.shapes[shape]);
    assert.equal(copy.walkthrough.progress_points.length, 3);
    assert.ok(copy.route.next_forge && copy.route.next_words);
  }
  const german = JSON.stringify(steps.firstStepsCopy('de'));
  assert.doesNotMatch(german, /\bSie\b|\bIhre?\b/, 'German addresses the learner with du (#74)');
  assert.equal(steps.firstStepsCopy('xx'), steps.firstStepsCopy('en'));
});

test('the session shows the walkthrough before the cast, a sticker per step, and the route after the recap', () => {
  const source = fs.readFileSync(
    path.join(WEB_ROOT, 'components/atelier-v2/journey/JourneySession.tsx'),
    'utf8',
  );
  assert.match(source, /showWalkthrough && \(\s*<Walkthrough/);
  assert.match(source, /showCastIntro && !showWalkthrough/);
  assert.match(source, /<FirstStepSticker key=\{step\.kind\} stepKey=\{stickerFor\(step\.kind\)\}/);
  assert.match(source, /firstDay && dayFinished && firstDayRoute/);
  // The recap's own forge button would double the route's on the first day.
  assert.match(source, /forgeAfterDay=\{firstDay && firstDayRoute \? null : forgeAfterDay\}/);
});
