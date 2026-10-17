// node --test lib/day-plan.test.js
//
// #143 — the day's progress has one source of truth. This walks every step's
// exit path (finish, stop early, recap close, back) and asserts that the next
// step and the «done» flag come from the one plan, never from a screen.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const dp = require('./day-plan.ts');

const WORDS = '/vocabulary/review?day=1';
const FORGE = '/atelier?mode=forge&concept=1&budget=300&from=day';

// The server's plan (`TodayEnvelope.session`) for [scene, words, grammar] states.
function plan(states) {
  const all = states.every((state) => state === 'done');
  const first = states.findIndex((state) => state !== 'done');
  const withNext = states.map((state, index) => (index === first ? 'next' : state === 'done' ? 'done' : 'todo'));
  return {
    pace: 'normal',
    steps: [
      { kind: 'scene', state: withNext[0], minutes: 8, href: null },
      { kind: 'words', state: withNext[1], minutes: 6, href: WORDS, count: 17 },
      { kind: 'grammar', state: withNext[2], minutes: 5, href: FORGE, count: 12 },
      { kind: 'finish', state: all ? 'done' : 'todo', minutes: 0, href: '/fertig' },
    ],
    next_kind: ['scene', 'words', 'grammar'][first] ?? null,
    minutes_left: 19,
    done: all,
    tally: { scenes: 0, words: 0, exercises: 0 },
    more_words: 10,
    more_minutes: 4,
    more_href: '/vocabulary/review?more=10',
  };
}

// The plan as it stands while the learner is on each step: earlier steps done,
// the step itself next, later ones still to come.
const START = {
  scene: ['next', 'todo', 'todo'],
  words: ['done', 'next', 'todo'],
  grammar: ['done', 'done', 'next'],
};

// What the plan itself says must come next when the exit finishes the step.
const AFTER_FINISH = {
  scene: { kind: 'words', href: WORDS, dayDone: false },
  words: { kind: 'grammar', href: FORGE, dayDone: false },
  grammar: { kind: 'finish', href: '/fertig', dayDone: true },
};

for (const step of ['scene', 'words', 'grammar']) {
  test(`${step}: finish and recap close hand on to the plan's next step`, () => {
    for (const how of ['finished', 'recap_closed']) {
      const result = dp.afterExit(plan(START[step]), step, how, 'en');
      assert.equal(result.next.kind, AFTER_FINISH[step].kind, `${step}/${how}`);
      assert.equal(result.next.href, AFTER_FINISH[step].href, `${step}/${how}`);
      assert.equal(result.dayDone, AFTER_FINISH[step].dayDone, `${step}/${how}`);
      assert.ok(result.done.includes(step));
    }
  });

  test(`${step}: stop early and back never claim the day is done`, () => {
    for (const how of ['stopped', 'back']) {
      const result = dp.afterExit(plan(START[step]), step, how, 'en');
      assert.equal(result.dayDone, false, `${step}/${how}`);
      // The next button always names a step the plan still has open.
      assert.notEqual(result.next.kind, 'finish', `${step}/${how}`);
    }
  });
}

test('a stopped scene is done (the server marks any terminal status) but the day is not', () => {
  const stopped = dp.afterExit(plan(START.scene), 'scene', 'stopped', 'en');
  assert.deepEqual(stopped.done, ['scene']);
  assert.equal(stopped.dayDone, false);
  assert.equal(stopped.next.kind, 'words');
  // #153: Home reads the very same plan once the server has caught up.
  assert.equal(dp.dayIsDone(plan(['done', 'todo', 'todo'])), false);
});

test('stopping or going back in the words or the grammar leaves that step as the next one', () => {
  for (const [step, href] of [['words', WORDS], ['grammar', FORGE]]) {
    for (const how of ['stopped', 'back']) {
      const result = dp.afterExit(plan(START[step]), step, how, 'en');
      assert.equal(result.next.kind, step);
      assert.equal(result.next.href, href);
    }
  }
});

test('the hand-on never invents an address: every href is the plan’s own', () => {
  const hrefs = new Set([WORDS, FORGE, '/fertig']);
  for (const step of ['scene', 'words', 'grammar']) {
    for (const how of ['finished', 'stopped', 'recap_closed', 'back']) {
      assert.ok(hrefs.has(dp.afterExit(plan(START[step]), step, how, 'de').next.href));
    }
  }
});

test('the day is done only when every working step is done in the plan', () => {
  const states = ['done', 'todo'];
  for (const scene of states) {
    for (const words of states) {
      for (const grammar of states) {
        const all = [scene, words, grammar];
        assert.equal(dp.dayIsDone(plan(all)), all.every((state) => state === 'done'), all.join('/'));
      }
    }
  }
  assert.equal(dp.dayIsDone(null), false);
  assert.equal(dp.dayState(null).done, false);
});

test('one plan, one answer: the hand-on helpers are afterExit', () => {
  const p = plan(START.scene);
  assert.deepEqual(dp.handOnAfterScene(p, 'fr'), dp.afterExit(p, 'scene', 'finished', 'fr').next);
  const g = plan(START.grammar);
  assert.deepEqual(dp.handOnAfterGrammar(g, 'fr'), dp.afterExit(g, 'grammar', 'finished', 'fr').next);
  const w = plan(START.words);
  assert.deepEqual(dp.handOnAfterWords(w, 'fr'), dp.afterExit(w, 'words', 'finished', 'fr').next);
  assert.equal(dp.handOnAfterScene(null, 'en'), null);
});

test('#152: the onboarding route lists the steps in the plan’s order', () => {
  const steps = require('./first-steps.ts');
  const asPlan = { story: 'scene', words: 'words', forge: 'grammar' };
  const planOrder = plan(START.scene).steps.map((step) => step.kind).filter((kind) => kind !== 'finish');
  assert.deepEqual(steps.ROUTE_STAGES.map((stage) => asPlan[stage]), planOrder);
  assert.deepEqual(planOrder, [...dp.WORK_STEPS]);
});

test('screens ask the plan: no second reader of «the day is done» is left in the pages', () => {
  const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  const atelier = read('pages/atelier.tsx');
  // The hero's «done / story done» reads the plan whenever the server sent one.
  assert.match(atelier, /restOfDayOpen=\{restOfDayOpen\}/);
  assert.match(atelier, /dayIsDone\(envelopePlan\)/);
  assert.doesNotMatch(atelier, /restOfDayOpen=\{Boolean\(continueRoute/);
  // Every hand-on goes through day-plan; the old per-screen copies are gone.
  assert.doesNotMatch(read('lib/day-session.ts'), /function sessionAfter/);
  assert.match(read('components/atelier-v2/journey/JourneySession.tsx'), /handOnAfterScene/);
  assert.match(read('pages/vocabulary/review.tsx'), /handOnAfterWords/);
  assert.match(atelier, /handOnAfterGrammar/);
  // A stopped scene hands on too (#153), not only a completed one.
  assert.match(read('components/atelier-v2/journey/JourneySession.tsx'), /ended_early/);
});

test('#175: a failed rule check from the day hands back to the day’s open grammar step', () => {
  const p = plan(['done', 'done', 'todo']);
  const failed = dp.handOnAfterRuleCheck(p, false, 'de');
  assert.equal(failed.kind, 'grammar');
  assert.equal(failed.href, FORGE, 'La Forge, from=day, never the Cahier');
  assert.match(failed.label, /Grammatik/);
  // The plan still has the grammar step open: Home does not say «done».
  assert.equal(dp.dayIsDone(p), false);
});

test('#175: a passed rule check closes the grammar step and the plan’s next step follows', () => {
  const grammarFirst = plan(['done', 'todo', 'todo']);
  const passed = dp.handOnAfterRuleCheck(grammarFirst, true, 'en');
  assert.equal(passed.kind, 'words');
  assert.equal(passed.href, WORDS);
  const last = dp.handOnAfterRuleCheck(plan(['done', 'done', 'todo']), true, 'en');
  assert.equal(last.kind, 'finish');
  assert.equal(last.href, '/fertig');
  assert.equal(dp.handOnAfterRuleCheck(null, false, 'en'), null);
});

test('#175: the rule check carries from=day and leaves through the day plan, not the Cahier', () => {
  const atelier = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(atelier, /testout=\$\{started\.session_id\}\$\{forgeFromDay \? '&from=day' : ''\}/);
  assert.match(atelier, /handOnAfterRuleCheck/);
});
