/**
 * WP-158 slice 1 — «Parler» in the story reply.
 *
 * The control's states, through the pure machine and through the REAL
 * `RespondStepView` driven by a minimal hook runner (the same technique as
 * `journey.test.js`: no DOM, no React test renderer in this repo):
 *
 *   flag off → absent · idle → recording (30 s cap) → transcribing → confirm
 *   («C'est bien ça ?», 3 s) → submitted through the same `onSubmit` as typed,
 *   with `mode: 'voice'` · a touched field holds the send · error paths
 *   (refused turn ceiling, failed transcription) · the typed path unchanged ·
 *   one line to repeat once the conversation is closed.
 *
 * Run: `node --test components/atelier-v2/journey/spoken-reply.test.js`
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');

const HERE = __dirname;
const WEB_ROOT = path.resolve(HERE, '../../..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');

require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolveWithAlias(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const apiCalls = [];
let apiHandler = () => {
  throw new Error('no api handler installed');
};
const apiStub = new Proxy(
  {},
  {
    get(_target, method) {
      if (method === 'then') return undefined;
      return (...args) => {
        apiCalls.push({ method: String(method), args });
        return apiHandler(String(method), args);
      };
    },
  },
);
const apiPath = Module._resolveFilename('@/services/api', module, false);
require.cache[apiPath] = {
  id: apiPath,
  filename: apiPath,
  loaded: true,
  exports: { __esModule: true, default: apiStub, apiService: apiStub },
};
const authPath = Module._resolveFilename('@/lib/app-auth', module, false);
require.cache[authPath] = {
  id: authPath,
  filename: authPath,
  loaded: true,
  exports: {
    __esModule: true,
    useAppSession: () => ({ data: { user: { id: 'learner-1' } }, status: 'authenticated', isNative: false }),
  },
};

const memoryStorage = (() => {
  const map = new Map();
  return {
    map,
    get length() { return map.size; },
    key: (index) => Array.from(map.keys())[index] ?? null,
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
  };
})();
const inertEvents = { addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => true };
global.window = { localStorage: memoryStorage, setTimeout, clearTimeout, ...inertEvents };
global.document = { visibilityState: 'visible', ...inertEvents };

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const model = require('./spoken-reply.ts');
const { spokenClock } = require('./useSpokenReply.ts');
const { journeyCopy } = require('./journey-copy.ts');
const steps = require('./JourneySteps.tsx');
const { SPOKEN_REPLY_STORAGE_KEY, spokenReplyLaunched } = require('@/lib/launch-flags');
const launchFlags = require(path.join(WEB_ROOT, 'launch-flags.json'));

const FR = journeyCopy('fr');
const EN = journeyCopy('en');
const DE = journeyCopy('de');

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8'));
const baseRespond = fixture('returning_due').response.steps.find((step) => step.kind === 'respond');

function respondStep(promptExtra = {}) {
  return {
    ...baseRespond,
    status: 'active',
    prompt: { ...baseRespond.prompt, choices: [], letter: null, spoken_reply: true, ...promptExtra },
  };
}

// --- a minimal hook runner (as journey.test.js) ------------------------------

function mountView(Component, initialProps) {
  const cells = [];
  const queue = [];
  const saved = {};
  let props = initialProps;
  let cursor = 0;
  let tree = null;
  let depth = 0;
  const sameDeps = (a, b) =>
    Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const cell = () => {
    const slot = cells[cursor] || (cells[cursor] = {});
    cursor += 1;
    return slot;
  };
  const fake = {
    useState(initial) {
      const slot = cell();
      if (!('value' in slot)) slot.value = typeof initial === 'function' ? initial() : initial;
      return [
        slot.value,
        (next) => {
          const value = typeof next === 'function' ? next(slot.value) : next;
          if (Object.is(value, slot.value)) return;
          slot.value = value;
          render();
        },
      ];
    },
    useRef(initial) {
      const slot = cell();
      if (!('ref' in slot)) slot.ref = { current: initial };
      return slot.ref;
    },
    useMemo(factory, deps) {
      const slot = cell();
      if (!('value' in slot) || !sameDeps(slot.deps, deps)) {
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
      if (!('deps' in slot) || !sameDeps(slot.deps, deps)) {
        slot.deps = deps;
        if (typeof slot.cleanup === 'function') slot.cleanup();
        slot.cleanup = undefined;
        queue.push(() => {
          const cleanup = fn();
          slot.cleanup = typeof cleanup === 'function' ? cleanup : undefined;
        });
      }
    },
  };
  const names = Object.keys(fake);
  function withHooks(run) {
    if (depth === 0) {
      names.forEach((name) => {
        saved[name] = React[name];
        React[name] = fake[name];
      });
    }
    depth += 1;
    try {
      return run();
    } finally {
      depth -= 1;
      if (depth === 0) names.forEach((name) => { React[name] = saved[name]; });
    }
  }
  function render() {
    return withHooks(() => {
      cursor = 0;
      tree = Component(props);
      let guard = 0;
      while (queue.length) {
        if ((guard += 1) > 200) throw new Error('effects never settled');
        queue.shift()();
      }
      return tree;
    });
  }
  render();
  return {
    get tree() { return tree; },
    rerender(next) {
      props = next;
      return render();
    },
    act: (fn) => withHooks(fn),
    settle: async () => {
      for (let turn = 0; turn < 12; turn += 1) await Promise.resolve();
      withHooks(() => {
        let guard = 0;
        while (queue.length) {
          if ((guard += 1) > 200) throw new Error('effects never settled');
          queue.shift()();
        }
      });
    },
  };
}

function findIn(node, predicate) {
  if (!node || typeof node !== 'object') return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const hit = findIn(child, predicate);
      if (hit) return hit;
    }
    return null;
  }
  if (typeof node.type === 'function' && node.type.name && /^Spoken|^RepeatLine$/.test(node.type.name)) {
    // The WP-158 views are small and pure: expand them so the test sees their output.
    return findIn(node.type(node.props), predicate);
  }
  if (!node.props) return null;
  if (predicate(node)) return node;
  return findIn(node.props.children, predicate);
}
const textareaIn = (tree) => findIn(tree, (element) => element.type === 'textarea');
const spokenButtonIn = (tree) => findIn(tree, (element) => element.props && element.props['data-spoken-button']);
const html = (tree) => renderToStaticMarkup(tree).replace(/ /g, ' ').replace(/&#x27;|’/g, "'");

// --- a device with a microphone ---------------------------------------------

let clockNow = 1_000_000;
spokenClock.now = () => clockNow;
let currentRecorder = null;
class FakeRecorder {
  constructor() {
    this.mimeType = 'audio/webm';
    this.started = false;
  }
  start() {
    this.started = true;
  }
  stop() {
    this.ondataavailable({ data: new Blob(['x'.repeat(4000)], { type: 'audio/webm' }) });
    this.onstop();
  }
}
FakeRecorder.isTypeSupported = () => false;
global.MediaRecorder = new Proxy(FakeRecorder, {
  construct(target, args) {
    currentRecorder = new target(...args);
    return currentRecorder;
  },
});
const fakeStream = { getTracks: () => [{ stop: () => {} }] };
Object.defineProperty(global, 'navigator', {
  configurable: true,
  value: { onLine: true, mediaDevices: { getUserMedia: async () => fakeStream } },
});

function mountReply({ launched = true, step = respondStep(), onSubmit, feedback = { kind: 'idle' } } = {}) {
  memoryStorage.setItem(SPOKEN_REPLY_STORAGE_KEY, launched ? 'on' : 'off');
  // The WP-27 voice-first beat stays on its own path; this is the typed field.
  memoryStorage.setItem('atelier.journey.answer-mode', 'text');
  return mountView(steps.RespondStepView, {
    step,
    copy: FR,
    busy: false,
    feedback,
    help: null,
    onHelp: () => {},
    onSubmit: onSubmit || (() => {}),
    onContinue: () => {},
    journeyId: 'journey-1',
  });
}

// ===========================================================================
// 1. The pure machine
// ===========================================================================

test('the machine walks idle → recording → transcribing → confirm → submitted', () => {
  let state = model.SPOKEN_IDLE;
  state = model.spokenReplyReduce(state, { type: 'start' });
  assert.equal(state.kind, 'idle');
  state = model.spokenReplyReduce(state, { type: 'recording', at: 0 });
  assert.equal(state.kind, 'recording');
  assert.equal(model.recordingSecondsLeft(state, 0), 30);
  assert.equal(model.recordingSecondsLeft(state, 29_100), 1);
  assert.equal(model.recordingIsOver(state, 29_999), false);
  assert.equal(model.recordingIsOver(state, 30_000), true, 'the recorder stops itself at 30 s');
  assert.equal(model.spokenIsBusy(state), true);
  state = model.spokenReplyReduce(state, { type: 'stop' });
  assert.equal(state.kind, 'transcribing');
  assert.equal(model.spokenReplyReduce(state, { type: 'stop' }), state, 'a late stop invents nothing');
  state = model.spokenReplyReduce(state, { type: 'transcribed', text: '  Un café, merci.  ', at: 100 });
  assert.deepEqual(state, { kind: 'confirm', text: 'Un café, merci.', shownAt: 100, held: false });
  assert.equal(model.confirmSecondsLeft(state, 100), 3);
  assert.equal(model.autoSubmitDue(state, 3_099), false);
  assert.equal(model.autoSubmitDue(state, 3_100), true, 'three seconds, then it sends itself');
  assert.equal(model.spokenMode(state, 'Un café, merci.'), 'voice');
  assert.equal(model.spokenMode(state, '   '), null, 'an emptied field is no longer spoken');
  const held = model.spokenReplyReduce(state, { type: 'hold' });
  assert.equal(held.held, true);
  assert.equal(model.autoSubmitDue(held, 60_000), false, 'a touched field is never sent behind the learner');
  assert.equal(model.confirmSecondsLeft(held, 200), null);
  state = model.spokenReplyReduce(state, { type: 'submitted' });
  assert.deepEqual(state, { kind: 'submitted', text: 'Un café, merci.' });
  assert.equal(model.spokenReplyReduce(state, { type: 'reset' }).kind, 'idle');
});

test('failures are honest and leave the turn open', () => {
  const transcribing = { kind: 'transcribing' };
  assert.deepEqual(model.spokenReplyReduce(transcribing, { type: 'transcribed', text: '  ', at: 0 }), {
    kind: 'error',
    reason: 'failed',
  });
  assert.equal(model.failureFromResponse(429, 'spoken_reply_turn_ceiling'), 'ceiling');
  assert.equal(model.failureFromResponse(413, undefined), 'too_long');
  assert.equal(model.failureFromResponse(500, undefined), 'failed');
  assert.equal(model.failureFromResponse(undefined, undefined), 'failed');
  const error = { kind: 'error', reason: 'failed' };
  assert.equal(model.spokenReplyReduce(error, { type: 'start' }).kind, 'idle', 'a failure can be retried');
  for (const reason of Object.keys(model.SPOKEN_FAILURE_COPY_KEY)) {
    const key = model.SPOKEN_FAILURE_COPY_KEY[reason];
    for (const table of [EN, DE, FR]) assert.ok(table[key], `${key} is said in every language`);
  }
});

test('«Parler» is offered only when the build and the server both say so, on a free reply', () => {
  const prompt = { choices: [], letter: null, spoken_reply: true };
  assert.equal(model.spokenReplyOffered(prompt, true), true);
  assert.equal(model.spokenReplyOffered(prompt, false), false, 'launch flag off');
  assert.equal(model.spokenReplyOffered({ ...prompt, spoken_reply: false }, true), false, 'server flag off');
  assert.equal(model.spokenReplyOffered({ ...prompt, spoken_reply: undefined }, true), false, 'an older server');
  assert.equal(model.spokenReplyOffered({ ...prompt, choices: [{ id: 'a', label_fr: 'Oui' }] }, true), false);
  assert.equal(model.spokenReplyOffered({ ...prompt, letter: { subject_fr: 'x' } }, true), false);
  assert.equal(launchFlags.spokenReply, false, 'the build ships it off');
  memoryStorage.removeItem(SPOKEN_REPLY_STORAGE_KEY);
  assert.equal(spokenReplyLaunched(), false);
  memoryStorage.setItem(SPOKEN_REPLY_STORAGE_KEY, 'on');
  assert.equal(spokenReplyLaunched(), true, 'one device can switch it on for the owner');
  memoryStorage.removeItem(SPOKEN_REPLY_STORAGE_KEY);
});

test('the copy is in en/de/fr and the French asks «C’est bien ça ?»', () => {
  const keys = ['spoken_listening', 'spoken_confirm', 'spoken_confirm_countdown', 'spoken_sent',
    'spoken_ceiling', 'spoken_too_long', 'repeat_title', 'repeat_hint', 'repeat_listen'];
  for (const key of keys) {
    for (const table of [EN, DE, FR]) assert.ok(table[key], `${key} exists`);
    assert.notEqual(FR[key], EN[key], `${key} is translated`);
  }
  assert.equal(FR.spoken_confirm, 'C’est bien ça ?');
  for (const table of [EN, DE, FR]) {
    assert.ok(table.spoken_listening.includes('{seconds}'));
    assert.ok(table.spoken_confirm_countdown.includes('{seconds}'));
  }
  assert.ok(!/prononc|pronunc|Ausspr/i.test(keys.map((key) => FR[key] + EN[key] + DE[key]).join(' ')),
    'nothing here talks about how the sentence sounded');
});

// ===========================================================================
// 2. The real respond step
// ===========================================================================

test('flag off: the control is absent and the typed reply is exactly as before', async () => {
  const sent = [];
  for (const view of [
    mountReply({ launched: false, onSubmit: (input) => sent.push(input) }),
    mountReply({ launched: true, step: respondStep({ spoken_reply: false }) }),
  ]) {
    assert.equal(spokenButtonIn(view.tree), null, '«Parler» is not drawn');
    assert.ok(textareaIn(view.tree), 'the field is');
  }
  const typed = mountReply({ launched: false, onSubmit: (input) => sent.push(input) });
  textareaIn(typed.tree).props.onChange({ target: { value: 'Un café, s’il vous plaît.' } });
  await typed.settle();
  findIn(typed.tree, (node) => node.props && node.props.children === FR.send).props.onClick();
  assert.deepEqual(sent, [{ mode: 'text', text: 'Un café, s’il vous plaît.' }]);
});

test('idle → recording → (30 s) → transcribing → confirm → sent as voice through the same call', async () => {
  const sent = [];
  let release;
  apiCalls.length = 0;
  apiHandler = (method) => {
    if (method === 'transcribeAudio') return new Promise((resolve) => { release = resolve; });
    throw new Error(`unexpected ${method}`);
  };
  const view = mountReply({ onSubmit: (input) => sent.push(input) });

  // idle
  let button = spokenButtonIn(view.tree);
  assert.ok(button, '«Parler» is beside the field');
  assert.equal(button.props['data-spoken-button'], 'idle');
  assert.ok(html(view.tree).includes('Parler'));

  // recording
  await button.props.onClick();
  await view.settle();
  assert.ok(currentRecorder && currentRecorder.started, 'the microphone runs');
  button = spokenButtonIn(view.tree);
  assert.equal(button.props['data-spoken-button'], 'recording');
  assert.ok(html(view.tree).includes('Je vous écoute — encore 30 s'));
  assert.equal(textareaIn(view.tree).props.disabled, true, 'the field waits while the learner speaks');

  // the recorder stops itself at 30 s
  clockNow += 30_000;
  // The countdown's interval is real (250 ms); let one tick read the clock.
  await new Promise((resolve) => setTimeout(resolve, 300));
  await view.settle();
  button = spokenButtonIn(view.tree);
  assert.equal(button.props['data-spoken-button'], 'transcribing', 'stopped at 30 s and transcribing');
  assert.equal(button.props.pending, true);
  const upload = apiCalls.find((call) => call.method === 'transcribeAudio');
  assert.ok(upload, 'the recording is uploaded');
  assert.equal(upload.args[1], 'story_reply');
  assert.deepEqual(upload.args[2], { journeyId: 'journey-1', stepId: baseRespond.id });
  assert.equal(sent.length, 0);

  // confirm
  release('je voudrais un café');
  await view.settle();
  const field = textareaIn(view.tree);
  assert.equal(field.props.value, 'je voudrais un café', 'the transcript is in the same field, editable');
  assert.equal(field.props.disabled, false);
  const shown = html(view.tree);
  assert.ok(shown.includes("C'est bien ça ?"), 'and it asks');
  assert.ok(shown.includes('Envoi dans 3 s'));
  assert.equal(sent.length, 0, 'not sent before the three seconds');

  // submitted — by itself, three seconds later
  clockNow += 3_000;
  await new Promise((resolve) => setTimeout(resolve, 300));
  await view.settle();
  assert.deepEqual(sent, [{ mode: 'voice', text: 'je voudrais un café' }], 'the same onSubmit, as voice');
  assert.equal(spokenButtonIn(view.tree), null, 'once sent, «Parler» steps aside');
  assert.ok(html(view.tree).includes('Envoyé tel que vous'));
});

test('a touched field holds the send; the corrected sentence still goes as voice', async () => {
  const sent = [];
  apiHandler = (method) => {
    if (method === 'transcribeAudio') return Promise.resolve('je voudrai un café');
    throw new Error(`unexpected ${method}`);
  };
  const view = mountReply({ onSubmit: (input) => sent.push(input) });
  await spokenButtonIn(view.tree).props.onClick();
  await view.settle();
  spokenButtonIn(view.tree).props.onClick();
  await view.settle();
  assert.equal(textareaIn(view.tree).props.value, 'je voudrai un café');
  textareaIn(view.tree).props.onChange({ target: { value: 'Je voudrais un café.' } });
  await view.settle();
  clockNow += 10_000;
  await new Promise((resolve) => setTimeout(resolve, 300));
  await view.settle();
  assert.equal(sent.length, 0, 'held: nothing is sent behind the learner');
  assert.ok(!html(view.tree).includes('Envoi dans'), 'and the countdown is gone');
  findIn(view.tree, (node) => node.props && node.props.children === FR.send).props.onClick();
  assert.deepEqual(sent, [{ mode: 'voice', text: 'Je voudrais un café.' }]);
});

test('errors: a refused turn ceiling removes «Parler»; a failed transcription keeps it', async () => {
  apiHandler = (method) => {
    if (method === 'transcribeAudio') {
      return Promise.reject({ response: { status: 429, data: { detail: { code: 'spoken_reply_turn_ceiling' } } } });
    }
    throw new Error(`unexpected ${method}`);
  };
  const capped = mountReply();
  await spokenButtonIn(capped.tree).props.onClick();
  await capped.settle();
  spokenButtonIn(capped.tree).props.onClick();
  await capped.settle();
  assert.equal(spokenButtonIn(capped.tree), null, 'the turn’s spoken attempts are used');
  assert.ok(html(capped.tree).includes('répondez par écrit'));
  assert.equal(textareaIn(capped.tree).props.disabled, false, 'the field is the way on');

  apiHandler = (method) => {
    if (method === 'transcribeAudio') return Promise.reject(new Error('network'));
    throw new Error(`unexpected ${method}`);
  };
  const failed = mountReply();
  await spokenButtonIn(failed.tree).props.onClick();
  await failed.settle();
  spokenButtonIn(failed.tree).props.onClick();
  await failed.settle();
  assert.equal(spokenButtonIn(failed.tree).props['data-spoken-button'], 'error');
  assert.ok(html(failed.tree).includes(FR.voice_failed.replace(/’/g, "'").replace(/ /g, ' ')));
  assert.ok(!/Pas encore|wrong/.test(html(failed.tree)), 'a failure is never a wrong answer');
});

test('the closed conversation offers one line to repeat, heard only on a tap', () => {
  const closing = {
    kind: 'graded',
    verdict: 'correct',
    replySource: 'model',
    result: {
      evidence_ref: 'e',
      task_outcome: 'met',
      assistance_level: 'none',
      correction: null,
      character_reply_fr: 'Tout de suite !',
      character_lines: [],
      reply_source: 'model',
      next_turn: null,
      pending: false,
      repeat_line_fr: 'Je voudrais un café, s’il vous plaît.',
      journey: null,
    },
  };
  const view = mountReply({ feedback: closing });
  const shown = html(view.tree);
  assert.ok(shown.includes(FR.repeat_title), 'the recap names it');
  assert.ok(shown.includes("Je voudrais un café, s'il vous plaît."));
  assert.ok(shown.includes(FR.repeat_hint));
  const off = mountReply({ launched: false, feedback: closing });
  assert.ok(!html(off.tree).includes(FR.repeat_title), 'flag off: no line to repeat');
});
