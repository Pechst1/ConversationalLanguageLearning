/* Render-level guarantees for the Feuilleton reader.
 *   node --test components/feuilleton/reader/reader-render.test.js
 *
 * These are the properties that must never regress silently:
 *   · a filed episode offers no way to file it again
 *   · revisiting an answered panel shows the record, not the controls
 *   · the panel a learner is being asked to act on is marked differently from
 *     one they are merely re-reading
 *   · exactly one tactile 3D press is on screen at a time
 *
 * The scene body is a captured real response from
 * GET /api/v1/graphic-novel/scenes/{id}.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');

require('../../../node_modules/sucrase/register/ts');
require('../../../node_modules/sucrase/register/tsx');

const ROOT = path.resolve(__dirname, '../../..');

/* `@/…` aliases and next/link are resolved by the bundler in the app; map them
   here so the component can be rendered outside Next. */
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(ROOT, request.slice(2)), ...rest);
  if (request === 'next/link') return originalResolve.call(this, path.join(__dirname, '__fixtures__/next-link-stub.js'), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const React = require(path.join(ROOT, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(ROOT, 'node_modules/react-dom/server'));

// Sucrase compiles JSX to the classic React.createElement runtime; the app uses
// Next's automatic runtime, so React is not imported in the component files.
global.React = React;

const { FeuilletonReader } = require('./FeuilletonReader.tsx');
const { attemptsByTaskId, buildReaderStages, liveTaskId } = require('./panel-model.ts');
const capturedScene = require('./__fixtures__/generated-scene.json');

function sceneWithEveryTaskAnswered(base) {
  const scene = JSON.parse(JSON.stringify(base));
  const ids = [];
  scene.panels.forEach((panel) => {
    ((panel.overlay_payload || {}).tasks || []).forEach((task) => ids.push(String(task.id)));
  });
  if (scene.script_payload?.final_prompt?.id) ids.push(String(scene.script_payload.final_prompt.id));
  scene.attempts = ids.map((id, index) => ({
    task_id: id,
    answer_payload: { answer: index === 0 ? 'Option A' : 'Une phrase courte.' },
    correction: index === 0
      ? { verdict: 'branch', why: 'L’histoire suit ce choix.' }
      : { verdict: 'correct', why: 'Phrase claire.' },
  }));
  return scene;
}

function render(scene, overrides = {}) {
  const stages = buildReaderStages(scene);
  const attempts = attemptsByTaskId(scene);
  const calls = { submits: 0, completes: 0, indexChanges: 0 };
  const markup = renderToStaticMarkup(React.createElement(FeuilletonReader, {
    episodeLabel: 'Édition du jour',
    title: scene.title,
    location: '',
    previously: '',
    stages,
    index: 0,
    furthest: 0,
    onIndexChange: () => { calls.indexChanges += 1; },
    answers: {},
    setAnswer: () => {},
    onSubmit: () => { calls.submits += 1; },
    submittingTask: null,
    attemptsByTask: attempts,
    submitError: null,
    liveTaskId: liveTaskId(stages, attempts),
    onExit: () => {},
    onComplete: () => { calls.completes += 1; },
    completing: false,
    filed: false,
    nextHref: null,
    nextLabel: 'Lire le prochain épisode',
    banner: null,
    ...overrides,
  }));
  return { markup, stages, attempts, calls };
}

test('the captured real scene produces the panels the server sent', () => {
  const stages = buildReaderStages(capturedScene);
  assert.equal(stages.length, capturedScene.panels.length + 1);
  assert.equal(stages[stages.length - 1].kind, 'resolution');
});

test('rendering sends nothing: no submit and no completion happen on their own', () => {
  const { calls } = render(capturedScene, { index: 2, furthest: 3 });
  assert.deepEqual(calls, { submits: 0, completes: 0, indexChanges: 0 });
});

test('a filed episode offers no way to file it again', () => {
  const scene = sceneWithEveryTaskAnswered(capturedScene);
  const stages = buildReaderStages(scene);
  const { markup } = render(scene, {
    index: stages.length - 1,
    furthest: stages.length - 1,
    filed: true,
    onComplete: null,
    nextHref: '/graphic-novel?serial_thread_id=abc',
  });
  assert.ok(!/Terminer l’épisode/.test(markup), 'no completion control on a filed episode');
  assert.ok(/Épisode classé/.test(markup), 'the filed state is stated');
  assert.ok(/href="\/graphic-novel\?serial_thread_id=abc"/.test(markup), 'the next beat uses the server reference');
});

test('revisiting an answered panel shows the record, never the controls', () => {
  const scene = sceneWithEveryTaskAnswered(capturedScene);
  const stages = buildReaderStages(scene);
  const choiceIndex = stages.findIndex((stage) => stage.tasks.length);
  assert.ok(choiceIndex >= 0, 'the captured scene has a task panel');
  const { markup } = render(scene, { index: choiceIndex, furthest: stages.length - 1, filed: true });
  assert.ok(/Déjà lu/.test(markup), 'the revisit is stated');
  assert.ok(/class="fr-act is-read"/.test(markup), 'the action is rendered read-only');
  assert.ok(/Votre réponse, déjà envoyée/.test(markup), 'the recorded answer is shown');
  assert.ok(!/Envoyer/.test(markup), 'no submit control on a revisited panel');
  assert.ok(!/class="fr-option"/.test(markup), 'no choice options to re-pick');
});

test('the live panel is marked in the action colour, a revisit in ink', () => {
  const stages = buildReaderStages(capturedScene);
  const attempts = {};
  const live = liveTaskId(stages, attempts);
  const liveIndex = stages.findIndex((stage) => stage.tasks.some((task) => String(task.id) === live));
  const onLive = render(capturedScene, { index: liveIndex, furthest: liveIndex });
  assert.ok(/class="fr-state is-live"/.test(onLive.markup));
  assert.ok(/À vous de répondre/.test(onLive.markup));

  const onRevisit = render(capturedScene, { index: 0, furthest: liveIndex });
  assert.ok(/class="fr-state"/.test(onRevisit.markup));
  assert.ok(/Déjà lu/.test(onRevisit.markup));
  assert.ok(!/is-live/.test(onRevisit.markup));
});

test('exactly one tactile 3D press is on screen', () => {
  const stages = buildReaderStages(capturedScene);
  const presses = (markup) => (markup.match(/data-press="3d"/g) || []).length;

  // a reading panel: the press belongs to Suivant
  assert.equal(presses(render(capturedScene, { index: 0, furthest: 0 }).markup), 1);
  // the panel carrying the live task: the press moves to Envoyer
  const live = liveTaskId(stages, {});
  const liveIndex = stages.findIndex((stage) => stage.tasks.some((task) => String(task.id) === live));
  const liveMarkup = render(capturedScene, { index: liveIndex, furthest: liveIndex }).markup;
  assert.equal(presses(liveMarkup), 1);
  assert.ok(/class="fr-btn is-action" data-press="3d"/.test(liveMarkup));
  // a filed last stage: the press belongs to the next-beat link
  const filed = sceneWithEveryTaskAnswered(capturedScene);
  assert.equal(
    presses(render(filed, {
      index: stages.length - 1,
      furthest: stages.length - 1,
      filed: true,
      onComplete: null,
      nextHref: '/serial',
    }).markup),
    1,
  );
});

test('Suivant is never disabled by an unanswered task', () => {
  const stages = buildReaderStages(capturedScene);
  const live = liveTaskId(stages, {});
  const liveIndex = stages.findIndex((stage) => stage.tasks.some((task) => String(task.id) === live));
  const { markup } = render(capturedScene, { index: liveIndex, furthest: liveIndex });
  const nextButton = markup.match(/<button[^>]*class="fr-btn fr-next"[^>]*>/);
  assert.ok(nextButton, 'the Suivant button is rendered');
  assert.ok(!/disabled/.test(nextButton[0]), 'reading forward is never gated on the exercise');
});

test('art states are stated, never faked', () => {
  const printing = JSON.parse(JSON.stringify(capturedScene));
  printing.panels[0].image_url = null;
  printing.panels[0].image_payload = { url: null };
  printing.panels[0].generation_metadata = { image_status: 'queued' };
  const printingMarkup = render(printing, { index: 0, furthest: 0 }).markup;
  assert.ok(/fr-plate is-printing/.test(printingMarkup));
  assert.ok(/sous presse/.test(printingMarkup));
  assert.ok(!/<img/.test(printingMarkup.split('</figure>')[0]), 'no image element is promised');

  const missing = JSON.parse(JSON.stringify(capturedScene));
  missing.panels[0].image_url = null;
  missing.panels[0].image_payload = { url: null };
  missing.panels[0].generation_metadata = {};
  const missingMarkup = render(missing, { index: 0, furthest: 0 }).markup;
  assert.ok(/fr-plate is-missing/.test(missingMarkup));
  assert.ok(/sans illustration/.test(missingMarkup));
});

test('every French line is tappable for help, and the panel is announced', () => {
  const { markup } = render(capturedScene, { index: 0, furthest: 0 });
  assert.ok(/aria-roledescription="planche"/.test(markup));
  assert.ok(/aria-label="Planche 1 sur 5"/.test(markup));
  assert.ok(/class="fr-word"/.test(markup));
  assert.ok(/aria-label="Aide pour « /.test(markup));
  assert.ok(/role="progressbar"/.test(markup));
});
