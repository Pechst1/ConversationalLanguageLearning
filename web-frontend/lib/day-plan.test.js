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

// The server's plan (`TodayEnvelope.session`) for [scene, grammar, words] states:
// the day's order (owner, 1 Nov 2026: La Forge before the words), which
// `day-order.test.js` holds to the server's.
function plan(states) {
  const all = states.every((state) => state === 'done');
  const first = states.findIndex((state) => state !== 'done');
  const withNext = states.map((state, index) => (index === first ? 'next' : state === 'done' ? 'done' : 'todo'));
  return {
    pace: 'normal',
    steps: [
      { kind: 'scene', state: withNext[0], minutes: 8, href: null },
      { kind: 'grammar', state: withNext[1], minutes: 5, href: FORGE, count: 12 },
      { kind: 'words', state: withNext[2], minutes: 6, href: WORDS, count: 17 },
      { kind: 'finish', state: all ? 'done' : 'todo', minutes: 0, href: '/fertig' },
    ],
    next_kind: ['scene', 'grammar', 'words'][first] ?? null,
    minutes_left: 19,
    done: all,
    tally: { scenes: 0, words: 0, exercises: 0 },
  };
}

// The plan as it stands while the learner is on each step: earlier steps done,
// the step itself next, later ones still to come.
const START = {
  scene: ['next', 'todo', 'todo'],
  grammar: ['done', 'next', 'todo'],
  words: ['done', 'done', 'next'],
};

// What the plan itself says must come next when the exit finishes the step.
const AFTER_FINISH = {
  scene: { kind: 'grammar', href: FORGE, dayDone: false },
  grammar: { kind: 'words', href: WORDS, dayDone: false },
  words: { kind: 'finish', href: '/fertig', dayDone: true },
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
  assert.equal(stopped.next.kind, 'grammar');
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
        const all = [scene, grammar, words];
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

test('owner, 1 Nov: after the scene La Forge is next, after La Forge the words', () => {
  assert.equal(dp.handOnAfterScene(plan(START.scene), 'en').kind, 'grammar');
  assert.equal(dp.handOnAfterGrammar(plan(START.grammar), 'en').kind, 'words');
  assert.equal(dp.handOnAfterWords(plan(START.words), 'en').kind, 'finish');
  // Words done first (from the Cahier, say): the scene's end still names La Forge,
  // and La Forge's recap goes to the seal.
  assert.equal(dp.handOnAfterScene(plan(['next', 'todo', 'done']), 'en').kind, 'grammar');
  assert.equal(dp.handOnAfterGrammar(plan(['done', 'next', 'done']), 'en').kind, 'finish');
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
  const p = plan(['done', 'todo', 'done']);
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
  const last = dp.handOnAfterRuleCheck(plan(['done', 'todo', 'done']), true, 'en');
  assert.equal(last.kind, 'finish');
  assert.equal(last.href, '/fertig');
  assert.equal(dp.handOnAfterRuleCheck(null, false, 'en'), null);
});

test('review of #221: a rule check from the day never offers the Cahier, even before the plan is read', () => {
  const early = dp.ruleCheckExitFromDay(undefined, false, 'de');
  assert.equal(early.href, '/fertig', 'a reloaded result page stays in the day');
  assert.doesNotMatch(early.href, /^\/grammar/);
  assert.equal(dp.ruleCheckExitFromDay(plan(['done', 'todo', 'done']), false, 'de').href, FORGE);
  assert.equal(dp.ruleCheckExitFromDay(plan(['done', 'todo', 'todo']), true, 'en').href, WORDS);
  // The page reads the live forge view (where the result lands after the last answer),
  // not the session's copy from the start, and asks this helper for the exit.
  const page = require('node:fs').readFileSync(require('node:path').join(__dirname, '..', 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /const ruleCheckResult = \(forge \?\? forgeViewOf\(session\?\.forge\)\)\?\.result;/);
  assert.match(page, /ruleCheckExitFromDay\(journey\.envelope\?\.session/);
});

test('#175: the rule check carries from=day from the day’s La Forge, and only from there', () => {
  assert.equal(dp.ruleCheckPath('abc', true), '/atelier?testout=abc&from=day');
  assert.equal(dp.ruleCheckPath('abc', false), '/atelier?testout=abc');
  assert.equal(dp.ruleCheckIsFromDay({ testout: 'abc', from: 'day' }), true);
  assert.equal(dp.ruleCheckIsFromDay({ testout: 'abc' }), false, 'from the Cahier it keeps its own exit');
  assert.equal(dp.ruleCheckIsFromDay({ mode: 'forge', from: 'day' }), false, 'La Forge itself is not a rule check');
});

test('#175: the whole exit — start from the day, fail, and La Forge is the next step', () => {
  // The rule check opens at its own address with from=day …
  const address = new URL(dp.ruleCheckPath('s1', true), 'https://x.test');
  const query = Object.fromEntries(address.searchParams.entries());
  assert.equal(dp.ruleCheckIsFromDay(query), true);
  // … fails, and its only button names the day's open grammar step: La Forge from=day, not /grammar.
  const exit = dp.handOnAfterRuleCheck(plan(['done', 'todo', 'todo']), false, 'de');
  assert.equal(exit.href, FORGE);
  assert.doesNotMatch(exit.href, /^\/grammar/);
  assert.match(exit.label, /Grammatik/);
});

test('#997: a failed rule check offered after the grammar step is done hands on to the words, not a second séance', () => {
  // The day's La Forge is finished (Home: «Grammatik — erledigt»); its end sheet offered
  // the optional Regelprüfung on a due rule, and the learner missed it.
  const grammarDone = plan(['done', 'done', 'todo']);
  const failed = dp.ruleCheckExitFromDay(grammarDone, false, 'de');
  assert.equal(failed.kind, 'words', `a failed optional check reopened «${failed.label}» (${failed.href})`);
  assert.equal(failed.href, WORDS);
  assert.match(failed.label, /Wörter/);
  assert.equal(dp.handOnAfterRuleCheck(grammarDone, false, 'de').href, WORDS);
  // Words done too: the day's seal, never La Forge again.
  const allDone = dp.ruleCheckExitFromDay(plan(['done', 'done', 'done']), false, 'de');
  assert.equal(allDone.kind, 'finish');
  assert.equal(allDone.href, '/fertig');
  // While the grammar step is still open, a failed check keeps handing back to it.
  assert.equal(dp.ruleCheckExitFromDay(plan(['done', 'todo', 'todo']), false, 'de').href, FORGE);
});

// ---------------------------------------------------------------------------
// The session header reads the day's plan, not the scene's own steps.
//
// Walks 16 Oct – 24 Nov: «Szene · Schritt 2 von 4» jumped to «Regel · Schritt 4
// von 4» (the scene's ending is read full-screen, without the header), and day 2
// ran «Schritt 6 von 7», «7 von 7», then «Szene · Schritt 7 von 7 · Szene beendet»
// with La Forge and the words still ahead. The header counted the journey's
// steps; Home counts the plan's (Szene, Grammatik, Wörter, Fertig). Two counters,
// two answers. The header's number is now the plan's: the scene is step 1 of the
// day's 4 on every screen of the scene, whatever the scene holds.
// ---------------------------------------------------------------------------

function dayTwoJourney(current, { ended = false } = {}) {
  // Day 2 of a1-de-fresh, 24 Nov: page, scene, a drill from a mistake, a rule to
  // review, the missed drill once more (`_queue_retry`), the new rule's card, the ending.
  const ids = ['s-read', 's-scene', 's-mistake', 's-review', 's-mistake-again', 's-rule', 's-end'];
  const kinds = ['read', 'scene', 'recall', 'recall', 'recall', 'rule', 'resolution'];
  const at = ids.indexOf(current);
  return {
    id: 'j-day2',
    status: ended ? 'completed' : 'active',
    current_step_id: ended ? null : current,
    steps: ids.map((id, index) => ({
      id,
      kind: kinds[index],
      status: ended || index < at ? 'completed' : index === at ? 'active' : 'pending',
      prompt: id === 's-mistake-again' ? { retry: true } : {},
    })),
  };
}

test('#143: every screen of the scene says «step 1 of 4», the plan’s count, never the scene’s', () => {
  const { journeyHeaderCaption } = require('../components/atelier-v2/journey/journey-state.ts');
  const stepOf = (n, total) => `Schritt ${n} von ${total}`;
  const during = plan(START.scene);
  // The rule card is the day's grammar, not the scene: its own test follows.
  const order = ['s-read', 's-scene', 's-mistake', 's-review', 's-mistake-again', 's-end'];
  const captions = order.map((id) => journeyHeaderCaption(dayTwoJourney(id), stepOf, 'Szene', during));
  for (const [index, caption] of captions.entries()) {
    assert.equal(
      caption,
      'Szene · Schritt 1 von 4',
      `on ${order[index]} the header read «${caption}»: the scene's own steps, not the day's (captions: ${captions.join(' > ')})`,
    );
  }
  // The ending's card, with the plan read again (scene done, La Forge next): still the
  // day's first step, so «N von N» never shows before La Forge and the words.
  const after = journeyHeaderCaption(dayTwoJourney(null, { ended: true }), stepOf, 'Szene', plan(['done', 'todo', 'todo']));
  assert.equal(after, 'Szene · Schritt 1 von 4', `the ending read «${after}» with La Forge and the words ahead`);
  // Without a plan (an older server), the scene's own count stands.
  assert.equal(journeyHeaderCaption(dayTwoJourney('s-scene'), stepOf, 'Szene'), 'Szene · Schritt 2 von 6');
});

test('#143: the header’s count is the same number Home’s programme and mark count', () => {
  const { journeyHeaderCaption } = require('../components/atelier-v2/journey/journey-state.ts');
  const { sessionMarkState, sessionRows } = require('./day-session.ts');
  const p = plan(START.scene);
  for (const [id, kind] of [['s-scene', 'scene'], ['s-rule', 'grammar']]) {
    const caption = journeyHeaderCaption(dayTwoJourney(id), (n, total) => `${n}/${total}`, undefined, p);
    const [position, total] = caption.split('/').map(Number);
    assert.equal(total, sessionRows(p, 'de').length, `the header read «${caption}»; Home lists ${sessionRows(p, 'de').length} steps`);
    assert.equal(total, sessionMarkState(p, 'de').total);
    assert.equal(p.steps[position - 1].kind, kind, `on ${id} the header names the plan step «${p.steps[position - 1].kind}»`);
    assert.ok(position < total, 'never «N of N» while the plan has steps after this one');
  }
});

// ---------------------------------------------------------------------------
// The rule card is the day's grammar step, in the header as on Home.
//
// Walk 25 Nov (a2-en, after #1051): the rule card read «Rule · Step 1 of 4»
// while Home lists grammar as step 2 (Scene, Grammar, 15 words, Done). The
// header named the block from the step («Rule») but counted every screen of the
// journey player as the plan's scene step, so name and number disagreed. The
// number now comes from the plan step the screen belongs to, the same mapping
// that names it (`day-order.ts`: a rule card, a drill on today's rule and a
// folded La Forge are the grammar).
// ---------------------------------------------------------------------------

function withSteps(journey, prompts) {
  return { ...journey, steps: journey.steps.map((step) => ({ ...step, prompt: { ...step.prompt, ...(prompts[step.id] || {}) } })) };
}

test('#143: the rule card and the drills on today’s rule read Home’s grammar step, not the scene’s', () => {
  const { journeyHeaderCaption } = require('../components/atelier-v2/journey/journey-state.ts');
  const { sessionRows } = require('./day-session.ts');
  const stepOf = (n, total) => `Schritt ${n} von ${total}`;
  const p = plan(START.scene);
  const grammarRow = sessionRows(p, 'de').findIndex((row) => row.kind === 'grammar') + 1;
  assert.equal(grammarRow, 2, 'Home lists the grammar second');
  const rule = journeyHeaderCaption(dayTwoJourney('s-rule'), stepOf, 'Regel', p);
  assert.equal(rule, `Regel · Schritt ${grammarRow} von 4`, `the rule card read «${rule}» while Home calls grammar step ${grammarRow}`);
  // A drill on the day's rule is the rule in use (`drillRoleOf` → day_rule): the grammar too.
  const ruleDrill = withSteps(dayTwoJourney('s-review'), { 's-review': { role: 'day_rule', target: { kind: 'grammar' } } });
  assert.equal(journeyHeaderCaption(ruleDrill, stepOf, 'Regel', p), `Regel · Schritt ${grammarRow} von 4`);
  // A rule to review and the learner's own slip stay the scene's (the review around it).
  const review = withSteps(dayTwoJourney('s-review'), { 's-review': { role: 'review', target: { kind: 'grammar' } } });
  assert.equal(journeyHeaderCaption(review, stepOf, 'Wiederholung', p), 'Wiederholung · Schritt 1 von 4');
  const slip = withSteps(dayTwoJourney('s-mistake'), { 's-mistake': { role: 'mistake', target: { kind: 'error' } } });
  assert.equal(journeyHeaderCaption(slip, stepOf, 'Aus deinen Fehlern', p), 'Aus deinen Fehlern · Schritt 1 von 4');
  // Without a plan, the scene's own count stands, as before.
  assert.equal(journeyHeaderCaption(dayTwoJourney('s-rule'), stepOf, 'Regel'), 'Regel · Schritt 5 von 6');
});

// ---------------------------------------------------------------------------
// The onboarding's «Your first day» lists the plan's steps, the ones the header counts.
//
// Walk 25 Nov: the walkthrough listed three steps («The story, La Forge, Your
// words», the device route) over a header that read «Step 1 of 4» (the plan's
// four: Scene, Grammar, 15 words, Done). Two lists of the day on one screen.
// ---------------------------------------------------------------------------

test('#143: the walkthrough’s day lists the same steps Home lists and the header counts', () => {
  require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { Walkthrough } = require('../components/onboarding/Walkthrough.tsx');
  const { sessionRows } = require('./day-session.ts');
  const p = plan(START.scene);
  for (const language of ['en', 'de', 'fr']) {
    // The second card («Your first day»), rendered as the learner sees it after «Next».
    const realUseState = React.useState;
    let first = true;
    React.useState = (initial) => {
      if (first) {
        first = false;
        return [1, () => {}];
      }
      return realUseState(initial);
    };
    let html;
    try {
      html = renderToStaticMarkup(React.createElement(Walkthrough, { language, plan: p, onDone: () => {} }));
    } finally {
      React.useState = realUseState;
    }
    const route = (html.match(/<ol class="walkthrough__route"[^>]*>([\s\S]*?)<\/ol>/) || [])[1] || '';
    const listed = [...route.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)].map((m) => m[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim());
    const home = sessionRows(p, language).map((row) => row.label);
    const total = dp.dayStepOf(p, 'scene').total;
    assert.equal(listed.length, total, `${language}: the walkthrough lists ${listed.length} steps («${listed.join(', ')}») under a header that counts ${total}`);
    assert.deepEqual(listed, home.map((label, i) => `${i + 1} ${label}`), `${language}: the walkthrough's day is not Home's`);
  }
});

test('#143: the session header’s mark is the plan’s mark — no «day done» from the scene’s ending', () => {
  const read = (file) => fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
  const session = read('components/atelier-v2/journey/JourneySession.tsx');
  // The mark beside the counter filled its ink square («Tag geschafft», «day done»)
  // from the scene's resolution step, while Home's read the plan.
  assert.doesNotMatch(
    session,
    /dayMarkState\(journey/,
    'the session header draws the mark from the scene’s steps: «Heute: 4 von 4 … Tag geschafft» before La Forge and the words',
  );
  assert.match(session, /journeyHeaderCaption\([\s\S]{0,600}envelope\?\.session/, 'the header’s count is handed the plan');
  const { dayMarkOf } = require('./day-plan.ts');
  const ended = dayTwoJourney(null, { ended: true });
  const mark = dayMarkOf(plan(['done', 'todo', 'todo']), ended, 'de');
  assert.equal(mark.groups.resolution, 'todo', `the mark read «${mark.label}» after the scene`);
  assert.doesNotMatch(mark.label, /Tag geschafft/);
  assert.equal(mark.done, 1);
  // Home's mark and the header's are one function of one plan.
  const { sessionMarkState, withScenePlayed } = require('./day-session.ts');
  assert.deepEqual(mark, sessionMarkState(withScenePlayed(plan(['done', 'todo', 'todo']), ended), 'de'));
  // No plan: the scene's own mark, as before.
  const { dayMarkState } = require('../components/atelier-v2/journey/day-mark.ts');
  assert.deepEqual(dayMarkOf(null, ended, 'de'), dayMarkState(ended, 'de'));
});
