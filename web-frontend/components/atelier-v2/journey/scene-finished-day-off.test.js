// node --test components/atelier-v2/journey/scene-finished-day-off.test.js
//
// #950 — «Scene finished» on a played day said «A day off kept your streak. This
// week, we consolidate.», and Home's «Next: 17 words» was the way to the words.
//
// The card read `streak.freeze_used_on` as a flag; it is the last day a freeze
// ever covered and stays for weeks, so every played day after it said «day
// off». The card after the scene is a hand-on, like Home: it says neither the
// streak's news nor the week's throttle. And Home's «Next» after the grammar
// step is the words step's own address, one tap, never the journey shell.

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
const { JourneyRecap } = require('./JourneyRecap.tsx');
const { sessionNextAction } = require('@/lib/day-session.ts');
const { handOnAfterScene } = require('@/lib/day-plan.ts');

const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/completed.json'), 'utf8'),
).response;
const DAY_OFF = /A day off kept your streak|we consolidate|Ruhetag|festigen wir|jour de relâche|on consolide/;
const textOf = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&#x27;/g, "'").replace(/\s+/g, ' ');

// Day 38 of the walk: played in full, a freeze spent weeks ago, the throttle on.
function playedDay(freezeUsedOn) {
  return {
    journey: {
      ...FIXTURE,
      local_date: '2026-11-20',
      streak: { days: 38, today_done: true, freeze_available: false, freeze_used_on: freezeUsedOn },
    },
    recap: { ...FIXTURE.recap, consolidating: true },
  };
}

// After the grammar step: the scene and La Forge are done, the words are next.
const AFTER_GRAMMAR = {
  pace: 'regular',
  done: false,
  next_kind: 'words',
  minutes_left: 3,
  steps: [
    { kind: 'scene', state: 'done', minutes: 0, href: null },
    { kind: 'grammar', state: 'done', minutes: 0, href: '/atelier?mode=forge&from=day', count: 6 },
    { kind: 'words', state: 'next', minutes: 3, href: '/vocabulary/review?day=1', count: 17, new_left: 5, reviews: 12 },
    { kind: 'finish', state: 'todo', minutes: 0, href: '/fertig' },
  ],
  tally: { scenes: 1, words: 0, exercises: 6, acts: 1, story_words: 0 },
};

function render({ journey, recap }, props = {}) {
  return renderToStaticMarkup(React.createElement(JourneyRecap, { journey, recap, language: 'en', ...props }));
}

test('«Scene finished» on a played day says no «day off» and no «we consolidate»', () => {
  const next = handOnAfterScene(AFTER_GRAMMAR, 'en');
  const sessionNext = { label: next.label, meta: next.meta, onSelect: () => {} };
  for (const covered of ['2026-10-02', '2026-11-19', null]) {
    const html = render(playedDay(covered), { sessionNext });
    assert.match(textOf(html), /Next: 17 words/);
    assert.doesNotMatch(textOf(html), DAY_OFF, `freeze_used_on ${covered}`);
  }
});

test('a freeze spent weeks ago is not today’s news, even at the day’s end', () => {
  assert.doesNotMatch(textOf(render(playedDay('2026-10-02'))), /A day off kept your streak/);
  // The day after the day it covered, it is.
  assert.match(textOf(render(playedDay('2026-11-19'))), /A day off kept your streak\./);
});

test('Home’s «Next» after the grammar step opens the words review in one tap', () => {
  const next = sessionNextAction(AFTER_GRAMMAR, 'en');
  assert.equal(next.kind, 'words');
  assert.equal(next.href, '/vocabulary/review?day=1');
  assert.match(next.label, /Next: 17 words/);
  // Home pushes that address itself; nothing on the way sends it to the journey shell.
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /<DaySessionNext next=\{sessionNext\} onNavigate=\{\(href\) => \{ void router\.push\(href\); \}\} \/>/);
  // The card after the scene names the same next step as Home, from the same plan.
  assert.equal(handOnAfterScene(AFTER_GRAMMAR, 'en').href, next.href);
});
