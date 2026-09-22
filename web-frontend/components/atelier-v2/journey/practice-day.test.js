// node --test components/atelier-v2/journey/practice-day.test.js
//
// WP-78 — a real day's worth of practice.
//
//   1. the three quick formats grade on the device from the same hashed key
//      the server mints (listen-and-tap by id, unscramble by order, matching
//      one digest per pair);
//   2. they post the attempt the server grades (recallAttempt);
//   3. they render: matching as two columns with no Check, listen-and-tap as
//      read-and-tap with meaning cards not marked French, unscramble as tiles;
//   4. a matching grid colours each pair, lets a wrong one go, and posts every
//      pairing once the last pair lands;
//   5. «Garder» is offered only for a real entry with its sentence, and a
//      refusal is the server's French line.

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
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
const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const answerKey = require('@/lib/answer-key.ts');
const kept = require('@/lib/kept-words.ts');
const steps = require('./JourneySteps.tsx');
const { MatchPairs } = require('./MatchPairs.tsx');
const formats = require('./practice-formats.ts');
const state = require('./journey-state.ts');
const { journeyCopy } = require('./journey-copy.ts');

const EN = journeyCopy('en');
const SALT = 'fedcba9876543210fedcba9876543210';
const sha = (text) => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
const J = '\u001f';
const keyOf = (...materials) => ({ version: 1, salt: SALT, digests: materials.map((m) => sha(`${SALT}:${m}`)) });

const TARGET = { kind: 'vocabulary', id: '7', label_fr: '' };
function recallStep(prompt) {
  return {
    id: `step-${Math.random().toString(16).slice(2)}`,
    ordinal: 0,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 10,
    assistance_used: [],
    prompt: {
      instruction_native: 'Tap the pairs that mean the same.',
      prompt_fr: null,
      target: TARGET,
      optional: false,
      help_available: [],
      options: [],
      ...prompt,
    },
  };
}
const baseProps = (step, extra = {}) => ({
  step,
  copy: EN,
  busy: false,
  feedback: { kind: 'idle' },
  help: null,
  onHelp: () => {},
  onSubmit: () => {},
  onContinue: () => {},
  ...extra,
});

const MATCH_OPTIONS = [
  { id: 'f1', text_fr: 'un café', side: 'fr' },
  { id: 'f2', text_fr: 'la clé', side: 'fr' },
  { id: 'f3', text_fr: 'brouillard', side: 'fr' },
  { id: 'f4', text_fr: 'le zinc', side: 'fr' },
  { id: 'n3', text_fr: 'fog', side: 'native' },
  { id: 'n1', text_fr: 'a coffee', side: 'native' },
  { id: 'n4', text_fr: 'the counter', side: 'native' },
  { id: 'n2', text_fr: 'the key', side: 'native' },
];
const MATCH_KEY = keyOf(`f1${J}n1`, `f2${J}n2`, `f3${J}n3`, `f4${J}n4`);

// ---------------------------------------------------------------------------
// 1. The key
// ---------------------------------------------------------------------------

test('listen-and-tap, unscramble and matching are keyed formats', async () => {
  for (const format of ['listen_tap', 'unscramble', 'match_pairs']) {
    assert.ok(answerKey.isKeyedFormat(format), format);
  }
  const listen = { task_type: 'listen_tap', answer_key: keyOf('lt_b') };
  assert.equal(await answerKey.checkAnswerLocally(listen, { optionId: 'lt_b' }), 'correct');
  assert.equal(await answerKey.checkAnswerLocally(listen, { optionId: 'lt_a' }), 'wrong');

  const unscramble = { task_type: 'unscramble', answer_key: keyOf(`t1${J}t2${J}t3`) };
  assert.equal(await answerKey.checkAnswerLocally(unscramble, { tileIds: ['t1', 't2', 't3'] }), 'correct');
  assert.equal(await answerKey.checkAnswerLocally(unscramble, { tileIds: ['t2', 't1', 't3'] }), 'wrong');

  const match = { task_type: 'match_pairs', answer_key: MATCH_KEY };
  assert.equal(await answerKey.checkAnswerLocally(match, { tileIds: ['f3', 'n3'] }), 'correct');
  assert.equal(await answerKey.checkAnswerLocally(match, { tileIds: ['f3', 'n1'] }), 'wrong');
  assert.equal(answerKey.answerMaterial('match_pairs', { tileIds: ['f1', 'n1', 'f2'] }), null, 'one pair at a time');
});

// ---------------------------------------------------------------------------
// 2. What is posted
// ---------------------------------------------------------------------------

test('each quick format posts the attempt the server grades', () => {
  assert.equal(state.recallAnswerMode('listen_tap'), 'choice');
  assert.equal(state.recallAnswerMode('unscramble'), 'tiles');
  assert.equal(state.recallAnswerMode('match_pairs'), 'tiles');
  const listen = recallStep({ task_type: 'listen_tap' }).prompt;
  assert.deepEqual(state.recallAttempt(listen, { choice: 'lt_b', tiles: [], text: '' }), {
    mode: 'choice',
    option_id: 'lt_b',
  });
  const match = recallStep({ task_type: 'match_pairs' }).prompt;
  assert.deepEqual(state.recallAttempt(match, { choice: null, tiles: ['f1', 'n1'], text: '' }), {
    mode: 'tiles',
    tile_ids: ['f1', 'n1'],
  });
});

// ---------------------------------------------------------------------------
// 3. Rendering
// ---------------------------------------------------------------------------

test('a matching item is two columns, meanings unmarked, and no Check button', () => {
  const html = renderToStaticMarkup(
    React.createElement(
      steps.RecallStepView,
      baseProps(recallStep({ task_type: 'match_pairs', options: MATCH_OPTIONS, answer_key: MATCH_KEY })),
    ),
  );
  assert.equal(html.split('av2-match__col').length - 1, 2);
  assert.ok(/<button[^>]*lang="fr"[^>]*>un café</.test(html), 'French cards are French');
  const fog = html.match(/<button[^>]*>fog</);
  assert.ok(fog && !fog[0].includes('lang='), 'a meaning is not marked French');
  assert.ok(!html.includes(`>${EN.check}<`), 'the grid posts itself');
  assert.ok(html.includes('Tap the pairs that mean the same.'));
});

test('listen-and-tap without a clip is read-and-tap: the phrase is printed, meanings not French', () => {
  const step = recallStep({
    task_type: 'listen_tap',
    instruction_native: 'What does it mean?',
    prompt_fr: 'brouillard',
    options: [
      { id: 'lt_a', text_fr: 'a coffee', side: 'native' },
      { id: 'lt_b', text_fr: 'fog', side: 'native' },
      { id: 'lt_c', text_fr: 'the key', side: 'native' },
    ],
    audio_url: null,
  });
  assert.equal(formats.listenTapHasAudio(step.prompt), false);
  const html = renderToStaticMarkup(React.createElement(steps.RecallStepView, baseProps(step)));
  assert.ok(html.includes('brouillard'), 'the phrase is the headline');
  assert.ok(!html.includes('<audio'), 'nothing speaks of audio');
  assert.ok(html.includes('role="radiogroup"'));
  assert.ok(!html.includes('<span lang="fr">fog</span>'), 'a meaning is spoken in the learner language');
  assert.ok(html.includes('<span>fog</span>'));

  const heard = recallStep({ ...step.prompt, audio_url: '/media/clip.mp3' });
  const heardHtml = renderToStaticMarkup(React.createElement(steps.RecallStepView, baseProps(heard)));
  assert.ok(heardHtml.includes('<audio'), 'a clip is played when one exists');
  assert.ok(!heardHtml.includes('brouillard'), 'and the phrase waits until the answer');
});

test('an unscramble renders the one tile bank', () => {
  const html = renderToStaticMarkup(
    React.createElement(
      steps.RecallStepView,
      baseProps(
        recallStep({
          task_type: 'unscramble',
          instruction_native: 'Put the sentence from the scene back in order.',
          options: [
            { id: 't2', text_fr: 'essuie' },
            { id: 't1', text_fr: 'Margaux' },
            { id: 't3', text_fr: 'le zinc.' },
          ],
        }),
      ),
    ),
  );
  assert.equal(html.split('av2-tiles__bank').length - 1, 1);
});

// ---------------------------------------------------------------------------
// 4. The matching grid, driven
// ---------------------------------------------------------------------------

function mount(Component, initialProps) {
  const cells = [];
  const queue = [];
  let cursor = 0;
  let tree = null;
  const same = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const cell = () => cells[cursor++] || (cells[cursor - 1] = {});
  const fake = {
    useState(initial) {
      const slot = cell();
      if (!('value' in slot)) slot.value = typeof initial === 'function' ? initial() : initial;
      return [slot.value, (next) => {
        const value = typeof next === 'function' ? next(slot.value) : next;
        if (Object.is(value, slot.value)) return;
        slot.value = value;
        render();
      }];
    },
    useRef(initial) {
      const slot = cell();
      if (!('ref' in slot)) slot.ref = { current: initial };
      return slot.ref;
    },
    useEffect(fn, deps) {
      const slot = cell();
      if (!('deps' in slot) || !same(slot.deps, deps)) {
        slot.deps = deps;
        queue.push(fn);
      }
    },
  };
  function render() {
    const saved = {};
    for (const name of Object.keys(fake)) {
      saved[name] = React[name];
      React[name] = fake[name];
    }
    try {
      cursor = 0;
      tree = Component(initialProps);
      while (queue.length) queue.shift()();
    } finally {
      for (const name of Object.keys(fake)) React[name] = saved[name];
    }
  }
  render();
  return {
    get tree() {
      return tree;
    },
  };
}
function cards(node, found = []) {
  if (!node || typeof node !== 'object') return found;
  if (Array.isArray(node)) {
    node.forEach((child) => cards(child, found));
    return found;
  }
  if (node.props && node.props.className === 'av2-match__card') found.push(node);
  if (node.props) cards(node.props.children, found);
  return found;
}
const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) await new Promise((resolve) => setImmediate(resolve));
};
const tapText = (view, text) => {
  const card = cards(view.tree).find((node) => node.props.children === text);
  assert.ok(card, `card ${text}`);
  card.props.onClick();
};

test('a keyed grid colours each pair, lets a wrong one go, and posts every pairing', async () => {
  globalThis.window = globalThis.window || { setTimeout: (fn) => setTimeout(fn, 0) };
  const posted = [];
  const view = mount(MatchPairs, {
    prompt: { task_type: 'match_pairs', options: MATCH_OPTIONS, answer_key: MATCH_KEY },
    onComplete: (pairs, clean) => posted.push({ pairs, clean }),
    flashMs: 0,
  });
  tapText(view, 'un café');
  assert.equal(cards(view.tree).find((n) => n.props.children === 'un café').props['data-state'], 'selected');
  tapText(view, 'fog'); // wrong
  await settle();
  tapText(view, 'un café');
  tapText(view, 'a coffee');
  await settle();
  assert.equal(cards(view.tree).find((n) => n.props.children === 'a coffee').props['data-state'], 'matched');
  for (const [fr, native] of [['la clé', 'the key'], ['brouillard', 'fog'], ['le zinc', 'the counter']]) {
    tapText(view, native); // either side first
    tapText(view, fr);
    // eslint-disable-next-line no-await-in-loop
    await settle();
  }
  assert.equal(posted.length, 1, 'posted once, when the last pair lands');
  assert.deepEqual(posted[0].pairs, ['f1', 'n3', 'f1', 'n1', 'f2', 'n2', 'f3', 'n3', 'f4', 'n4']);
  assert.equal(posted[0].clean, false, 'a slip waits for the server');
});

test('formats helpers: columns, completion, graded count, first scene', () => {
  const { fr, native } = formats.matchCards(MATCH_OPTIONS);
  assert.equal(fr.length, 4);
  assert.equal(native.length, 4);
  assert.equal(formats.pairsComplete(['a', 'b'], 4), false);
  assert.equal(formats.pairsComplete(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], 4), true);
  const journey = {
    steps: [
      { id: 'w1', kind: 'recall', status: 'active' },
      { id: 'w2', kind: 'recall', status: 'pending' },
      { id: 's', kind: 'scene', status: 'pending' },
      { id: 'm', kind: 'recall', status: 'skipped' },
      { id: 'r', kind: 'respond', status: 'pending' },
      { id: 'p', kind: 'recall', status: 'pending' },
      { id: 'e', kind: 'resolution', status: 'pending' },
    ],
  };
  assert.equal(formats.gradedInteractions(journey), 4);
  assert.equal(formats.firstSceneStepId(journey), 's');
});

// ---------------------------------------------------------------------------
// 5. «Garder»
// ---------------------------------------------------------------------------

test('«Garder» is offered for a real entry with its sentence, and a refusal is the server line', () => {
  assert.equal(kept.canKeep('gloss', 'Romy secoue son parapluie.'), true);
  assert.equal(kept.canKeep('sentence', 'Romy secoue son parapluie.'), false, 'no entry, nothing to keep');
  assert.equal(kept.canKeep('gloss', '  '), false, 'no sentence, no example');
  const refusal = { response: { data: { detail: { code: 'not_in_lexicon', message: 'Ce mot n’est pas encore dans le lexique.' } } } };
  assert.equal(kept.keepRefusalMessage(refusal), 'Ce mot n’est pas encore dans le lexique.');
  assert.equal(kept.keepRefusalMessage(new Error('network')), kept.KEEP_COPY.failed);
  assert.equal(kept.keepStatusLine({ kind: 'kept', already: false }), kept.KEEP_COPY.kept);
  assert.equal(kept.KEEP_COPY.action, 'Garder', 'sentence case, French chrome');
});
