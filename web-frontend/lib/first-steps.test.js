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

test('the first day runs story, then La Forge, then the words (the server plan’s order)', () => {
  assert.deepEqual([...steps.ROUTE_STAGES], ['story', 'forge', 'words']);
  assert.equal(steps.nextRouteStage([]), 'story');
  assert.equal(steps.nextRouteStage(['story']), 'forge');
  assert.equal(steps.nextRouteStage(['story', 'forge']), 'words');
  // The words done before La Forge still send the learner to La Forge next.
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
  assert.match(source, /<FirstStepSticker key=\{stickerFor\(step\) \?\? step\.kind\} stepKey=\{stickerFor\(step\)\}/);
  // A day ended early is not the story done (Codex review, #95).
  assert.match(source, /const storyCompleted = dayFinished && journey\?\.status === 'completed'/);
  assert.match(source, /firstDay && storyCompleted && firstDayRoute/);
  // The recap's own forge button would double the route's on the first day.
  // Round 3: with the day as one sequence, the scene's ending hands on itself.
  assert.match(source, /forgeAfterDay=\{\(firstDay && storyCompleted && firstDayRoute\) \|\| daySession \? null : forgeAfterDay\}/);
});

test('without localStorage the device store keeps the route in memory for the page', () => {
  const previous = global.window;
  global.window = {
    get localStorage() {
      return { getItem: () => null, setItem: () => { throw new Error('QuotaExceededError'); }, removeItem: () => {} };
    },
  };
  try {
    const store = steps.deviceStore();
    assert.ok(store, 'a store, not null');
    steps.beginFirstDay(store, '2026-10-12');
    steps.markRouteStage(store, 'story', '2026-10-12');
    steps.markRouteStage(steps.deviceStore(), 'forge', '2026-10-12');
    assert.equal(steps.onFirstDay(steps.deviceStore(), '2026-10-12'), true);
    assert.deepEqual(steps.routeDone(steps.deviceStore()), ['story', 'forge']);
  } finally {
    if (previous === undefined) delete global.window;
    else global.window = previous;
  }
});

test('#127: the rule sticker never claims the card quotes the scene', () => {
  // The sticker is static, but the card's example is only sometimes a scene line;
  // the card says so itself, with its own «in today’s scene» anchor.
  for (const language of ['de', 'en', 'fr']) {
    const { body } = steps.firstStepsCopy(language).stickers.rule;
    assert.doesNotMatch(body, /\bscene\b|Szene|sc[eè]ne/i, `${language}: ${body}`);
  }
});

test('#123: the episode-end sticker does not say the day is done, and names what follows', () => {
  // Owner, 1 Nov 2026: after the scene comes the grammar, then the words.
  const expected = { de: /Grammatik.*Wörter/, en: /grammar.*words/, fr: /grammaire.*mots/ };
  for (const language of ['de', 'en', 'fr']) {
    const { title, body } = steps.firstStepsCopy(language).stickers.resolution;
    assert.doesNotMatch(`${title} ${body}`, /Tag ist geschafft|Ende des Tages|day is done|end of the day|journée est faite|fin du jour/);
    assert.match(body, expected[language]);
    // The walkthrough's «your first day» card says the same order.
    const { day_body: dayBody } = steps.firstStepsCopy(language).walkthrough;
    assert.match(dayBody, expected[language], `${language}: ${dayBody}`);
  }
});

test('#469 a drill’s sticker is named by its place in the day order, not by its kind', () => {
  const order = require('./day-order.ts');
  const wordDrill = { kind: 'recall', prompt: { target: { kind: 'word' } } };
  const ruleDrill = { kind: 'recall', prompt: { target: { kind: 'grammar' } } };
  // (`?.`: a missing helper fails these as assertions, not as a crash.)
  assert.equal(order.dayStepOf?.(ruleDrill), 'grammar', 'the drill on the rule is the grammar step');
  assert.equal(order.dayStepOf?.(wordDrill), 'words', 'a word drill is the words step');
  assert.ok(order.WORK_STEPS.includes(order.dayStepOf?.(ruleDrill)));
  const named = {
    de: { rule: /Regel/, words: /Wörter/ },
    en: { rule: /rule/i, words: /words/i },
    fr: { rule: /règle/i, words: /mots/i },
  };
  for (const language of ['de', 'en', 'fr']) {
    const copy = steps.firstStepsCopy(language);
    const stickerOf = (step) => {
      const key = steps.stickerFor(step);
      return key ? copy.stickers[key] : null;
    };
    const rule = stickerOf(ruleDrill);
    const words = stickerOf(wordDrill);
    assert.ok(rule, `${language}: the drill after the rule has a sticker`);
    assert.ok(words, `${language}: the word drill has a sticker`);
    // Before: both said «Die Wörter · Kurze Wortübungen» because both are `recall`.
    assert.doesNotMatch(rule.title, named[language].words, `${language}: «${rule.title}» names the words`);
    assert.match(`${rule.title} ${rule.body}`, named[language].rule, `${language}: «${rule.title}» does not name the rule`);
    assert.match(words.title, named[language].words);
    assert.notEqual(steps.stickerFor(ruleDrill), steps.stickerFor(wordDrill), 'one sticker per place, so one does not hide the other');
  }
});
