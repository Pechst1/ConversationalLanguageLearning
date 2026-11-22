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
    assert.ok(copy.walkthrough.welcome_title && copy.walkthrough.day_title && copy.walkthrough.day_body);
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

test('#469 #975 a drill’s sticker follows its role in the day: own slip, rule to review, today’s rule, word', () => {
  // The planner says what each drill is for (`prompt.role`); the sticker reads it,
  // not the shape of the target. Walks of 21-22 Nov: day 2's own slip on être
  // opened with «Die Wörter», and a slip rule («Un, une, des», concept 4) on a day
  // whose rule is concept 40 opened with «Quick drills on today's rule».
  const ownSlip = { kind: 'recall', prompt: { role: 'mistake', target: { kind: 'error', id: 'err-1' } } };
  // A step planned before the role was sent: an error target is still the learner's own slip.
  const ownSlipUnroled = { kind: 'recall', prompt: { target: { kind: 'error', id: 'err-2' } } };
  const dueRule = { kind: 'recall', prompt: { role: 'review', target: { kind: 'grammar', id: '4' } } };
  const dayRule = { kind: 'recall', prompt: { role: 'day_rule', target: { kind: 'grammar', id: '40' } } };
  const wordDrill = { kind: 'recall', prompt: { target: { kind: 'vocabulary', id: 'w-1' } } };
  const words = { de: /Wörter/, en: /words/i, fr: /mots/i };
  const today = { de: /heute|des Tages/i, en: /today/i, fr: /du jour|aujourd/i };
  for (const language of ['de', 'en', 'fr']) {
    const copy = steps.firstStepsCopy(language);
    const text = (step) => {
      const key = steps.stickerFor(step);
      return key ? `${copy.stickers[key].title} ${copy.stickers[key].body}` : '';
    };
    for (const [name, step] of [['own slip', ownSlip], ['own slip (no role)', ownSlipUnroled], ['rule to review', dueRule]]) {
      const said = text(step);
      assert.ok(said, `${language}: the ${name} has a sticker`);
      assert.doesNotMatch(said, words[language], `${language}: the ${name} is introduced as the words: «${said}»`);
      assert.doesNotMatch(said, today[language], `${language}: the ${name} is introduced as today's rule: «${said}»`);
    }
    assert.notEqual(steps.stickerFor(ownSlip), steps.stickerFor(dueRule), 'a slip and a due rule are told apart');
    assert.match(text(dayRule), today[language], `${language}: today's rule keeps its sticker`);
    assert.match(text(wordDrill), words[language], `${language}: a word drill is the words`);
  }
});

test('#975 a drill’s header names its role: a rule to review or a slip is not headed as the day’s rule', () => {
  const frame = require('../components/atelier-v2/journey/drill-frame.ts');
  const { journeyCopy } = require('../components/atelier-v2/journey/journey-copy.ts');
  const recall = (id, role, target) => ({
    id, kind: 'recall', prompt: { role, task_type: 'choice', options: [], target },
  });
  const dayRule = recall('s2', 'day_rule', { kind: 'grammar', id: '40', label_native: 'Avoir' });
  const ownSlip = recall('s4', 'mistake', { kind: 'error', id: 'e-1' });
  const dueRule = recall('s5', 'review', { kind: 'grammar', id: '4', label_native: 'Un, une, des' });
  const day = [{ id: 's0', kind: 'scene' }, { id: 's1', kind: 'rule' }, dayRule, { id: 's3', kind: 'resolution' }, ownSlip, dueRule];
  for (const language of ['de', 'en', 'fr']) {
    const copy = journeyCopy(language);
    const review = frame.stepBlockName(dueRule, day, copy);
    const slip = frame.stepBlockName(ownSlip, day, copy);
    assert.ok(review && slip, `${language}: both are named`);
    assert.notEqual(review, copy.drill_rule, `${language}: the due rule is headed as the day's rule`);
    assert.notEqual(review, slip, `${language}: «${review}» heads a slip and a due rule alike`);
    assert.doesNotMatch(
      frame.drillHeaderLabel(dueRule, language, copy) ?? '',
      new RegExp(`^${copy.drill_recall} `),
      `${language}: the due rule's caption is the plain «${copy.drill_recall}»`,
    );
    assert.equal(frame.stepBlockName(dayRule, day, copy), copy.drill_rule, `${language}: a drill on today's rule is the rule step`);
  }
});
