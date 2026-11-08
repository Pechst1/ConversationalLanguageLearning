// node --test components/atelier-v2/journey/block-names.test.js
//
// #540 — the scene's last step must not promise the end of the day, and the
// header above a rule card or a recall drill must not call it «Scene».
//
// Root cause (#143): each screen named the day's blocks by itself. The header
// hard-coded «Scene» for every step of the journey, and the awaiting-finish
// screen said «Finish today» for what is only the scene's save. The names now
// come from the same copy Home and the drill frame use.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
const FIXTURES = path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};
const stub = (request, exports) => {
  const resolved = Module._resolveFilename(request, module, false);
  require.cache[resolved] = { id: resolved, filename: resolved, loaded: true, exports };
};
const apiStub = new Proxy({}, { get: (_t, method) => (method === 'then' ? undefined : () => Promise.resolve({})) });
stub('@/services/api', { __esModule: true, default: apiStub, apiService: apiStub });
stub('@/lib/app-auth', {
  __esModule: true,
  useAppSession: () => ({ data: { user: { id: 'learner-1' } }, status: 'authenticated', isNative: false }),
});

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const realConsoleError = console.error;
console.error = (...args) => {
  if (String(args[0] || '').includes('non-boolean attribute')) return;
  realConsoleError(...args);
};

const state = require('./journey-state.ts');
const { journeyCopy } = require('./journey-copy.ts');
const { JourneySession } = require('./JourneySession.tsx');
const { dayState } = require('@/lib/day-plan.ts');

const fixture = (name) => JSON.parse(fs.readFileSync(path.join(FIXTURES, `${name}.json`), 'utf8'));
const decode = (html) => html.replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, '&').replace(/[  ]/g, ' ');

function controller(journey, step, phase) {
  return {
    phase,
    feedback: { kind: 'idle' },
    envelope: null,
    journey,
    step,
    respondPrompt: null,
    controlLanguage: 'en',
    legacyResume: null,
    progress: state.journeyProgress(journey),
    busy: false,
    help: null,
    voice: { kind: 'idle' },
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
}

/** The scene's journey with the step of `kind` open (the way a rule day lays it out). */
function journeyAt(kind) {
  const base = fixture('returning_due').response;
  const steps = [
    { ...base.steps[0], status: 'completed' },
    { ...base.steps[2], status: kind === 'respond' ? 'active' : 'completed' },
    {
      ...base.steps[1],
      id: 'step-rule',
      kind: 'rule',
      status: kind === 'rule' ? 'active' : kind === 'respond' ? 'pending' : 'completed',
      prompt: { concept_id: 1, title_native: 'Possessives', title_fr: 'Les possessifs' },
    },
    { ...base.steps[1], id: 'step-recall', kind: 'recall', status: kind === 'recall' ? 'active' : 'pending' },
    { ...base.steps[3], status: 'pending' },
  ];
  const current = steps.find((s) => s.status === 'active');
  return { ...base, current_step_id: current.id, steps };
}

function headerCaption(kind) {
  const journey = journeyAt(kind);
  const step = journey.steps.find((s) => s.id === journey.current_step_id);
  const html = decode(
    renderToStaticMarkup(
      React.createElement(JourneySession, { controller: controller(journey, step, { kind: 'session', journey, step }) }),
    ),
  );
  const head = html.match(/<header class="av2-session__head"[\s\S]*?<\/header>/);
  assert.ok(head, 'the session header renders');
  return head[0].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
}

test('the step header names the block, as Home and the drill frame do', () => {
  assert.match(headerCaption('rule'), /Rule · Step 3 of 5/);
  assert.match(headerCaption('recall'), /Recall · Step 4 of 5/);
  assert.doesNotMatch(headerCaption('recall'), /Scene/, 'a recall drill is not «Scene»');
});

test('the scene keeps «Scene» for its own steps', () => {
  assert.match(headerCaption('respond'), /Scene · Step 2 of 5/);
});

test('after the last step the button saves the scene; it does not end the day', () => {
  // The day still holds La Forge, the words and the Done screen.
  const plan = {
    steps: [
      { kind: 'scene', state: 'next' },
      { kind: 'grammar', state: 'todo' },
      { kind: 'words', state: 'todo' },
      { kind: 'finish', state: 'todo' },
    ],
  };
  assert.deepEqual(dayState(plan).open, ['scene', 'grammar', 'words']);
  const expected = { en: 'Save the scene', de: 'Szene speichern', fr: 'Enregistrer la scène' };
  for (const language of ['en', 'de', 'fr']) {
    const copy = journeyCopy(language);
    assert.equal(copy.awaiting_finish_action, expected[language], `${language} names what the button saves`);
    assert.doesNotMatch(
      `${copy.awaiting_finish_title} ${copy.awaiting_finish_body}`,
      /Every step is done|Alle Schritte|Toutes les étapes/,
      `${language}: the scene is done, not «every step»`,
    );
  }
});
