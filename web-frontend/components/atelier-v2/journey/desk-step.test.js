// node --test components/atelier-v2/journey/desk-step.test.js
//
// «Le bureau» (WP-121/122 follow-up) — the DESK step, and WP-121 A.4's «vu au …» line.
//
//   1. the step's model: which desk opens on what, the kicker, fr/en/de copy;
//   2. the day mark counts a desk with the Rappel, the header stands down for it;
//   3. the step renders its kicker, a «Passer», and is mounted by the player;
//   4. a recall prompt with `met.place_label_fr` shows the muted context line.

const assert = require('node:assert/strict');
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
  if (request === 'next/link') {
    return originalResolve.call(
      this,
      path.join(WEB_ROOT, 'components/feuilleton/reader/__fixtures__/next-link-stub.js'),
      ...rest,
    );
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
global.React = React;

const model = require('./desk-step-model.ts');
const { DeskStepView } = require('./DeskStep.tsx');
const { RecallStepView } = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { dayMarkGroupOf, STEP_SHAPE } = require('./day-mark.ts');
const { recallMetLine, stepHeaderLine, stepShowsDayObjective } = require('./drill-frame.ts');

const h = React.createElement;

const RELECTURE = {
  session_id: 's-41',
  week: '2026-W34',
  kind: 'question',
  dossier_title_fr: 'La grève des éboueurs',
  prompt_fr: 'Qui paie quand la ville s’arrête ?',
  place_label_fr: 'Le marché d’Aligre',
  plate_url: null,
  closed_at: '2026-08-20T10:00:00+00:00',
};

function deskStep(prompt) {
  return {
    id: 'desk-1',
    ordinal: 6,
    kind: 'desk',
    status: 'active',
    estimated_seconds: 150,
    assistance_used: [],
    prompt: { title_fr: 'La grève des transports', dossier_id: null, relecture: null, seconds: null, ...prompt },
  };
}

// --- 1. the model ----------------------------------------------------------------

test('each desk opens on its own target; a desk without one is «none»', () => {
  const relecture = model.deskStepView(deskStep({ desk: 'relecture', title_fr: '', relecture: RELECTURE }));
  assert.equal(relecture.desk, 'relecture');
  assert.equal(relecture.offer.sessionId, 's-41');
  assert.equal(relecture.titleFr, 'La grève des éboueurs', 'the dossier title when the step names none');
  const radio = model.deskStepView(deskStep({ desk: 'radio', dossier_id: 'evergreen-greve', seconds: 50 }));
  assert.deepEqual(radio, { desk: 'radio', titleFr: 'La grève des transports', dossierId: 'evergreen-greve', seconds: 50 });
  const correcteur = model.deskStepView(deskStep({ desk: 'correcteur', dossier_id: 'evergreen-greve' }));
  assert.deepEqual(correcteur, { desk: 'correcteur', titleFr: 'La grève des transports', dossierId: 'evergreen-greve' });
  assert.equal(model.deskStepView(deskStep({ desk: 'radio' })).desk, 'none');
  assert.equal(model.deskStepView(deskStep({ desk: 'relecture' })).desk, 'none');
  assert.equal(model.deskStepView(null).desk, 'none');
});

test('the kicker names the desk in French and the lead follows the chrome', () => {
  const radio = model.deskStepView(deskStep({ desk: 'radio', dossier_id: 'd' }));
  assert.equal(model.deskKicker(radio, 'de'), 'La Radio · La grève des transports');
  for (const language of ['fr', 'en', 'de']) {
    const copy = model.deskCopy(language);
    for (const desk of ['relecture', 'radio', 'correcteur']) {
      assert.ok(copy.lead[desk].length > 10, `${language} ${desk}`);
    }
    assert.ok(copy.skip && copy.done && copy.unavailable && copy.loading);
  }
  assert.equal(model.deskCopy('en').skip, 'Skip');
  assert.equal(model.deskCopy('de').skip, 'Überspringen');
  assert.equal(model.deskCopy('xx').skip, 'Passer');
});

// --- 2. the day mark and the header -----------------------------------------------

test('a desk counts with the Rappel and carries its own kicker', () => {
  assert.equal(dayMarkGroupOf('desk'), 'recall');
  assert.equal(STEP_SHAPE.desk, 'reward');
  assert.equal(stepShowsDayObjective('desk'), false);
  const header = stepHeaderLine({ step: deskStep({ desk: 'radio', dossier_id: 'd' }), language: 'fr', copy: journeyCopy('fr'), location: 'Paris', objective: 'x' });
  assert.equal(header, '');
});

// --- 3. the step -----------------------------------------------------------------

test('the step shows the desk, its lead and a «Passer» that continues the day', () => {
  const html = renderToStaticMarkup(
    h(DeskStepView, { step: deskStep({ desk: 'correcteur', dossier_id: 'd' }), busy: false, onContinue: () => {}, language: 'fr' }),
  );
  assert.match(html, /data-desk="correcteur"/);
  assert.match(html, /Le Correcteur · La grève des transports/);
  assert.match(html, /Passer/);
  assert.match(html, /Un instant…/, 'loading until the draft comes');
});

test('the journey player mounts the desk step and the planner’s kinds are the wire’s', () => {
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  assert.match(session, /step\.kind === 'desk'/);
  assert.match(session, /<DeskStepView/);
  const source = fs.readFileSync(path.join(__dirname, 'DeskStep.tsx'), 'utf8');
  assert.match(source, /<CarteRelecture/);
  assert.match(source, /relectureAnswer/);
  assert.match(source, /<RadioBulletin/);
  assert.match(source, /<CorrecteurDesk/);
  const wire = fs.readFileSync(path.join(WEB_ROOT, 'types/generated/api.ts'), 'utf8');
  assert.match(wire, /desk: "relecture" \| "radio" \| "correcteur"/);
});

// --- 4. «vu au …» -----------------------------------------------------------------

test('a recall card kept in a Papier shows where it was met, as the muted context line', () => {
  assert.equal(recallMetLine({ met: { place_label_fr: ' vu au marché d’Aligre, semaine 41 ' } }), 'vu au marché d’Aligre, semaine 41');
  assert.equal(recallMetLine({ met: null }), null);
  assert.equal(recallMetLine({}), null);
  const step = {
    id: 'r-1',
    ordinal: 4,
    kind: 'recall',
    status: 'active',
    estimated_seconds: 20,
    assistance_used: [],
    prompt: {
      task_type: 'short_answer',
      instruction_native: 'Write it in French',
      prompt_fr: null,
      options: [],
      target: { kind: 'vocabulary', id: '41', label_fr: 'la poubelle', label_native: 'the bin' },
      optional: false,
      help_available: [],
      answer_key: null,
      goal_native: null,
      source_fr: null,
      met: { place_label_fr: 'vu au marché d’Aligre, semaine 41' },
    },
  };
  const props = { step, copy: journeyCopy('en'), busy: false, feedback: { kind: 'idle' }, help: null, onHelp() {}, onSubmit() {}, onContinue() {} };
  const html = renderToStaticMarkup(h(RecallStepView, props));
  assert.match(html, /<p class="av2-label" data-state="met-place" lang="fr">vu au marché d’Aligre, semaine 41<\/p>/);
  const plain = renderToStaticMarkup(h(RecallStepView, { ...props, step: { ...step, prompt: { ...step.prompt, met: undefined } } }));
  assert.doesNotMatch(plain, /met-place/);
});
