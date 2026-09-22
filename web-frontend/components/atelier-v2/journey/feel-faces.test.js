// node --test components/atelier-v2/journey/feel-faces.test.js
//
// WP-76 (instant, physical feedback) and WP-77 (faces).
//
//   1. the hashed key: the client's recipe is the server's, a pick is coloured
//      well inside 100 ms, and the server's verdict wins a disagreement;
//   2. the recall renderer: coloured options/tiles, one word bank, locked pick;
//   3. every journey state has a haptic, felt once;
//   4. faces: names → cast ids, moods → expressions, faces on scene, verdict,
//      reader lines and the byline disc; the narrator and strangers get none;
//   5. the dark wrong-answer title clears 4.5:1; sounds are small and defaulted.

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
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

// The API transport is never reached by these renderers; stub it so axios is not loaded.
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
const faces = require('@/lib/cast-faces.ts');
const feelLib = require('@/lib/feel.ts');
const sound = require('@/lib/sound.ts');
const steps = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { feelForTransition } = require('./useJourneyFeel.ts');
const { journeySpeaker } = require('./journey-faces.ts');
const episodeModel = require('./story-episode-model.ts');
const panelModel = require('@/components/feuilleton/reader/panel-model.ts');
const ui = require('@/components/atelier-v2/ui');

const EN = journeyCopy('en');

// --- the server's recipe, re-implemented independently -------------------
const SALT = '0123456789abcdef0123456789abcdef';
const sha = (text) => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
const keyFor = (material, salt = SALT) => ({ version: 1, salt, digests: [sha(`${salt}:${material}`)] });

const TARGET = { kind: 'vocabulary', id: '41', label_fr: 'addition' };
function recallStep(prompt) {
  return {
    id: `step-${Math.random().toString(16).slice(2)}`,
    ordinal: 1,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 30,
    assistance_used: [],
    prompt: {
      instruction_native: 'Pick the bill.',
      prompt_fr: null,
      target: TARGET,
      optional: false,
      help_available: [],
      ...prompt,
    },
  };
}
const CHOICE = [
  { id: 'opt-a', text_fr: 'la carte' },
  { id: 'opt-b', text_fr: 'l’addition' },
  { id: 'opt-c', text_fr: 'la table' },
];

// ===========================================================================
// 1. The key
// ===========================================================================

test('the pinned vector matches the backend test (salt + ":" + material)', async () => {
  // Same vector as tests/test_journey_answer_key.py.
  assert.equal(await answerKey.sha256Hex(`${SALT}:opt-b`), sha(`${SALT}:opt-b`));
  assert.equal(answerKey.answerMaterial('tiles', { tileIds: ['a', 'b'] }), 'a\u001fb');
  assert.equal(answerKey.answerMaterial('choice', { optionId: 'opt-b' }), 'opt-b');
  assert.equal(answerKey.answerMaterial('short_answer', { optionId: 'x' }), null);
});

test('normalisation folds iOS smart quotes like the server', () => {
  assert.equal(answerKey.normalizeKeyPart('l’addition'), "l'addition");
  assert.equal(answerKey.normalizeKeyPart('  a   b '), 'a b');
  assert.equal(answerKey.normalizeKeyPart(null), '');
});

test('a pick is graded locally, correctly, and well inside 100 ms', async () => {
  const prompt = { task_type: 'choice', options: CHOICE, answer_key: keyFor('opt-b') };
  const started = performance.now();
  const right = await answerKey.checkAnswerLocally(prompt, { optionId: 'opt-b' });
  const elapsed = performance.now() - started;
  assert.equal(right, 'correct');
  assert.ok(elapsed < 100, `local grading took ${elapsed.toFixed(1)} ms`);
  assert.equal(await answerKey.checkAnswerLocally(prompt, { optionId: 'opt-a' }), 'wrong');
  assert.equal(await answerKey.correctOptionLocally(prompt), 'opt-b');

  const tiles = { task_type: 'word_bank', options: [], answer_key: keyFor('t1\u001ft2') };
  assert.equal(await answerKey.checkAnswerLocally(tiles, { tileIds: ['t1', 't2'] }), 'correct');
  assert.equal(await answerKey.checkAnswerLocally(tiles, { tileIds: ['t2', 't1'] }), 'wrong');
});

test('no key, an unknown version or a written format means "wait for the server"', async () => {
  assert.equal(await answerKey.checkAnswerLocally({ task_type: 'choice' }, { optionId: 'x' }), null);
  assert.equal(
    await answerKey.checkAnswerLocally(
      { task_type: 'choice', answer_key: { ...keyFor('x'), version: 2 } },
      { optionId: 'x' },
    ),
    null,
  );
  assert.equal(
    await answerKey.checkAnswerLocally({ task_type: 'short_answer', answer_key: keyFor('x') }, { optionId: 'x' }),
    null,
  );
});

test('the server wins a disagreement', () => {
  assert.equal(answerKey.shownVerdict('correct', null), 'correct');
  assert.equal(answerKey.shownVerdict('correct', 'wrong'), 'wrong');
  assert.equal(answerKey.shownVerdict('wrong', 'supported'), 'correct');
  assert.equal(answerKey.shownVerdict(null, null), null);
});

// ===========================================================================
// 2. The recall renderer, driven with its real hooks
// ===========================================================================

/** A minimal hook host: the real component function, our scheduler. */
function mount(Component, initialProps) {
  const cells = [];
  const queue = [];
  let props = initialProps;
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
    useMemo(factory, deps) {
      const slot = cell();
      if (!('value' in slot) || !same(slot.deps, deps)) {
        slot.value = factory();
        slot.deps = deps;
      }
      return slot.value;
    },
    useCallback(fn, deps) {
      return fake.useMemo(() => fn, deps);
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
      tree = Component(props);
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
    rerender(next) {
      props = next;
      render();
    },
  };
}

function find(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const hit = find(child, predicate);
      if (hit) return hit;
    }
    return null;
  }
  if (!node.props) return null;
  if (predicate(node)) return node;
  return find(node.props.children, predicate);
}
const byType = (type) => (element) => element.type === type;
const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) await new Promise((resolve) => setImmediate(resolve));
};

function baseProps(step, extra = {}) {
  return {
    step,
    copy: EN,
    busy: false,
    feedback: { kind: 'idle' },
    help: null,
    onHelp: () => {},
    onSubmit: () => {},
    onContinue: () => {},
    ...extra,
  };
}

test('a choice pick turns red on the device, the right card green, and the server corrects quietly', async () => {
  feelLib.resetFeltVerdicts();
  const step = recallStep({ task_type: 'choice', options: CHOICE, answer_key: keyFor('opt-b') });
  const sent = [];
  const props = baseProps(step, { onSubmit: (input) => sent.push(input) });
  const view = mount(steps.RecallStepView, props);

  find(view.tree, byType(ui.ChoiceList)).props.onSelect('opt-a');
  const check = find(view.tree, (el) => el.type === ui.Action && el.props.children === EN.check);
  const tapped = performance.now();
  check.props.onClick();
  await settle();
  const coloured = performance.now() - tapped;

  assert.deepEqual(sent, [{ mode: 'choice', option_id: 'opt-a' }], 'the attempt is still posted, once');
  const states = () =>
    Object.fromEntries(find(view.tree, byType(ui.ChoiceList)).props.options.map((o) => [o.id, o.state]));
  assert.deepEqual(states(), { 'opt-a': 'wrong', 'opt-b': 'correct', 'opt-c': undefined });
  assert.ok(coloured < 100, `coloured after ${coloured.toFixed(1)} ms`);
  assert.equal(find(view.tree, byType(ui.ChoiceList)).props.disabled, true, 'a graded pick is committed');
  assert.equal(feelLib.verdictAlreadyFelt(step.id), true, 'the verdict was felt on the device');

  // The server disagrees: it accepted the pick. The colours follow it.
  view.rerender({
    ...props,
    feedback: { kind: 'graded', verdict: 'correct', result: { character_reply_fr: null }, replySource: 'unknown' },
  });
  assert.deepEqual(states(), { 'opt-a': 'correct', 'opt-b': undefined, 'opt-c': undefined });
  // …without a second buzz.
  assert.equal(
    feelForTransition(
      { phase: 'session', stepId: step.id, result: null },
      { phase: 'session', stepId: step.id, feedback: { kind: 'graded', verdict: 'correct', result: {} } },
    ),
    null,
  );
});

test('a word bank sentence is coloured on the device', async () => {
  const step = recallStep({
    task_type: 'word_bank',
    options: [
      { id: 't1', text_fr: 'l’addition' },
      { id: 'x1', text_fr: 'café' },
      { id: 't2', text_fr: 's’il vous plaît' },
    ],
    answer_key: keyFor('t1\u001ft2'),
  });
  const view = mount(steps.RecallStepView, baseProps(step));
  const tiles = () => find(view.tree, byType(ui.WordTiles));
  tiles().props.onPlace('t1');
  tiles().props.onPlace('t2');
  find(view.tree, (el) => el.type === ui.Action && el.props.children === EN.check).props.onClick();
  await settle();
  assert.equal(tiles().props.verdict, 'correct');
  assert.equal(tiles().props.disabled, true);
  const html = renderToStaticMarkup(React.createElement(ui.WordTiles, tiles().props));
  assert.ok(html.includes('data-verdict="correct"'));
  assert.ok(html.includes(EN.status_correct || 'Correct'), 'the verdict is also a word, not colour alone');
});

test('there is exactly one word bank, for tiles and for word_bank', () => {
  for (const task_type of ['tiles', 'word_bank']) {
    const html = renderToStaticMarkup(
      React.createElement(
        steps.RecallStepView,
        baseProps(recallStep({ task_type, options: [{ id: 'a', text_fr: 'bonjour' }, { id: 'b', text_fr: 'madame' }] })),
      ),
    );
    assert.equal(html.split('av2-tiles__bank').length - 1, 1, `${task_type} renders one bank`);
  }
});

test('the verdict band is focusable and carries the character’s reacting face', () => {
  const graded = (verdict) =>
    renderToStaticMarkup(
      React.createElement(steps.JourneyFeedbackView, {
        feedback: { kind: 'graded', verdict, result: { character_reply_fr: 'Parfait !', correction: null }, replySource: 'unknown' },
        copy: EN,
        onContinue() {},
        onRetry() {},
        onDismiss() {},
        speaker: { id: 'marin', name: 'Marin' },
      }),
    );
  const right = graded('correct');
  assert.ok(right.includes('tabindex="-1"'), 'the band can take focus for a screen reader');
  assert.ok(right.includes('marin_leveque/portrait-happy.webp'), 'pleased when it lands');
  assert.ok(graded('wrong').includes('marin_leveque/portrait-cross.webp'), 'cross when it misses');
  const stranger = renderToStaticMarkup(
    React.createElement(steps.JourneyFeedbackView, {
      feedback: { kind: 'graded', verdict: 'correct', result: { character_reply_fr: null, correction: null }, replySource: 'unknown' },
      copy: EN,
      onContinue() {},
      onRetry() {},
      onDismiss() {},
      speaker: { id: 'clerk', name: 'Clerk' },
    }),
  );
  assert.ok(!stranger.includes('portrait-'), 'nobody borrows a cast face');
});

// ===========================================================================
// 3. Every state has a haptic, once
// ===========================================================================

test('transitions: verdict, next step, finished day — and nothing on a reload', () => {
  feelLib.resetFeltVerdicts();
  const graded = (verdict) => ({ kind: 'graded', verdict, result: { id: verdict } });
  const idle = { kind: 'idle' };
  const t = feelForTransition;
  assert.equal(t({ phase: 'session', stepId: 's1', result: null }, { phase: 'session', stepId: 's1', feedback: graded('wrong') }), 'wrong');
  assert.equal(t({ phase: 'session', stepId: 's1', result: null }, { phase: 'session', stepId: 's1', feedback: graded('supported') }), 'correct');
  assert.equal(t({ phase: 'session', stepId: 's1', result: null }, { phase: 'session', stepId: 's2', feedback: idle }), 'step');
  assert.equal(t({ phase: 'awaiting_finish', stepId: null, result: null }, { phase: 'finished', stepId: null, feedback: idle }), 'complete');
  assert.equal(t({ phase: 'loading', stepId: null, result: null }, { phase: 'finished', stepId: null, feedback: idle }), null, 'opening a finished day is not news');
  const same = graded('correct');
  assert.equal(t({ phase: 'session', stepId: 's1', result: same.result }, { phase: 'session', stepId: 's1', feedback: same }), null, 'one verdict, one buzz');
});

// ===========================================================================
// 4. Faces
// ===========================================================================

test('every way a payload names a cast member resolves to one face, strangers to none', () => {
  const cases = {
    Marin: 'marin_leveque',
    marin_leveque: 'marin_leveque',
    'Augustin « Gus » de Roncourt': 'augustin_de_roncourt',
    Gus: 'augustin_de_roncourt',
    'Romane « Romy » Tremblay': 'romy_tremblay',
    Margaux: 'margaux_barman',
    'Monsieur Marchand': 'landlord_marchand',
    landlord_marchand: 'landlord_marchand',
    'Lila Bonnet': 'lila_bonnet',
    'Marin Lévêque': 'marin_leveque',
  };
  for (const [seed, id] of Object.entries(cases)) assert.equal(faces.castIdFor(seed), id, seed);
  for (const seed of ['Clerk', 'Samira', 'Vous', 'toi', 'user', '', null, 'Marine']) {
    assert.equal(faces.castIdFor(seed), null, String(seed));
  }
  assert.equal(faces.castIdFor(null, 'Lila'), 'lila_bonnet', 'the name stands in for a missing id');
});

test('moods and verdicts map onto the three drawn expressions', () => {
  assert.equal(faces.expressionForMood(2), 'happy');
  assert.equal(faces.expressionForMood(1), 'happy');
  assert.equal(faces.expressionForMood(0), 'neutral');
  assert.equal(faces.expressionForMood(-1), 'cross');
  assert.equal(faces.expressionForMood('warmer'), 'happy');
  assert.equal(faces.expressionForMood('colder'), 'cross');
  assert.equal(faces.expressionForMood(undefined), 'neutral');
  assert.equal(faces.expressionForVerdict('correct'), 'happy');
  assert.equal(faces.expressionForVerdict('supported'), 'happy');
  assert.equal(faces.expressionForVerdict('wrong'), 'cross');
});

test('reader lines carry faces; the narrator and an unknown speaker do not', () => {
  const episode = {
    id: 'e1',
    panels: [
      {
        id: 'p1',
        index: 0,
        narration_fr: 'Le café est plein.',
        dialogue: [
          { character_id: 'marin', character_name: 'Marin', text_fr: 'Bonjour !' },
          { character_id: 'waiter_7', character_name: 'Serveur', text_fr: 'Oui ?' },
        ],
        image_url: null,
        image_status: 'unavailable',
      },
    ],
    moods: { marin: { mood: 2 } },
  };
  const [panel] = episodeModel.buildStoryStages(episode);
  assert.equal(panel.lines[0].faceId, 'marin_leveque');
  assert.equal(panel.lines[0].faceMood, 'happy', 'the live mood picks the face when the payload has it');
  assert.equal(panel.lines[1].faceId, null);
  assert.equal(panel.caption, 'Le café est plein.', 'narration stays a caption, with no face');

  const feuilleton = panelModel.panelLines({
    id: 'q',
    overlay_payload: {
      bubbles: [
        { speaker: 'Augustin « Gus » de Roncourt', speaker_id: 'gus', fr: 'Salut.' },
        { speaker: 'Clerk', fr: 'Suivant !' },
      ],
    },
  });
  assert.equal(feuilleton[0].faceId, 'augustin_de_roncourt');
  assert.equal(feuilleton[1].faceId, null, 'the accent may be hashed; the face never is');
});

test('the scene line shows its speaker’s face; the byline disc shows faces too', () => {
  const scene = {
    id: 's',
    ordinal: 0,
    kind: 'scene',
    status: 'active',
    estimated_seconds: 30,
    assistance_used: [],
    prompt: {
      setup_fr: 'Au café.',
      setup_native: 'At the café.',
      objective_native: 'Order.',
      character_line_fr: 'Qu’est-ce que je vous sers ?',
      image_url: null,
    },
  };
  const html = renderToStaticMarkup(
    React.createElement(steps.SceneStepView, {
      step: scene,
      copy: EN,
      busy: false,
      onContinue() {},
      speaker: journeySpeaker({ scenario: { character_id: 'margaux', character_name: 'Margaux' } }, scene),
    }),
  );
  assert.ok(html.includes('margaux_barman/portrait-neutral.webp'));
  const byline = renderToStaticMarkup(React.createElement(ui.Byline, { name: 'Marin' }));
  assert.ok(byline.includes('marin_leveque/portrait-neutral.webp'));

  // A letter day's speaker is the correspondent, not the scenario character.
  const respond = { kind: 'respond', prompt: { character_id: 'marin', character_name: 'Marin', letter: { correspondent_id: 'lila', correspondent_name: 'Lila' } } };
  assert.deepEqual(journeySpeaker({ scenario: { character_id: 'marin', character_name: 'Marin' } }, respond), { id: 'lila', name: 'Lila' });
});

// ===========================================================================
// 5. Contrast, inputs, sounds
// ===========================================================================

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test('the dark wrong-answer title uses the lifted red and clears 4.5:1', () => {
  const css = fs.readFileSync(path.join(WEB_ROOT, 'styles/atelier-v2.css'), 'utf8');
  const dark = css.slice(css.indexOf(":root[data-theme='dark'] .av2:not(.av2--light),"));
  const token = (name) => dark.match(new RegExp(`${name}:\\s*(#[0-9a-f]{6})`, 'i'))[1];
  const red = token('--av2-red');
  const tint = token('--av2-tint-wrong');
  const paper = token('--av2-paper');
  assert.ok(contrast(red, tint) >= 4.5, `red on the wrong tint: ${contrast(red, tint).toFixed(2)}`);
  assert.ok(contrast(red, paper) >= 4.5);
  assert.ok(contrast(token('--av2-red-deep'), tint) < 4.5, 'the old colour really was the problem');
  const block = css.slice(css.indexOf('WP-76 / WP-77'));
  assert.match(block, /\.av2--dark \.av2-feedback\[data-tone='wrong'\] \.av2-feedback__title \{\s*color: var\(--av2-red\);/);
  assert.match(block, /prefers-color-scheme: dark/);
});

test('French answer fields turn off autocorrect, autocapitalise and spellcheck', () => {
  const html = renderToStaticMarkup(ui.textAnswerField({ label: 'Réponse', value: '', onChange() {} }));
  assert.ok(html.includes('autoCorrect="off"') && html.includes('autoCapitalize="off"') && html.includes('spellcheck="false"'));
  for (const file of ['components/feuilleton/reader/FeuilletonReader.tsx', 'pages/missions.tsx']) {
    const source = fs.readFileSync(path.join(WEB_ROOT, file), 'utf8');
    assert.ok(source.includes('autoCorrect="off"'), file);
  }
});

test('the three sounds exist, are small, and default on in the app, off on the web', () => {
  for (const name of sound.FEEL_SOUNDS) {
    const file = path.join(WEB_ROOT, 'public/sounds', `${name}.wav`);
    const size = fs.statSync(file).size;
    assert.ok(size > 1000 && size < 20000, `${name}.wav is ${size} bytes`);
    assert.equal(fs.readFileSync(file).slice(0, 4).toString(), 'RIFF');
  }
  assert.equal(sound.defaultSoundsEnabled(true), true);
  assert.equal(sound.defaultSoundsEnabled(false), false);
  assert.equal(sound.soundsEnabled(), false, 'no window, no sound');
  // Playing without a window is a no-op, never a throw.
  sound.playFeelSound('correct');
  feelLib.feel('complete');
});
