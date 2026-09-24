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

// ---------------------------------------------------------------------------
// WP-44 — the two artboards, and what left the screen with them
// ---------------------------------------------------------------------------

const storyStages = [
  {
    kind: 'panel',
    key: 'panel:p1',
    ordinal: 1,
    panelId: 'p1',
    panelIndex: 0,
    title: '',
    beat: '',
    imageUrl: '/assets/serial/mistral.jpg',
    artStatus: 'ready',
    character: 'gus',
    lines: [{ key: 'p1-l0', who: 'Augustin', fr: 'Je peux aider.', en: '', character: 'gus' }],
    caption: 'Augustin sourit en découvrant la scène.',
    tasks: [],
  },
  {
    kind: 'panel',
    key: 'panel:p2',
    ordinal: 2,
    panelId: 'p2',
    panelIndex: 1,
    title: '',
    beat: '',
    imageUrl: '/assets/serial/mistral.jpg',
    artStatus: 'ready',
    character: 'gus',
    lines: [
      { key: 'p2-l0', who: 'Augustin', fr: 'Vingt euros.', en: '', character: 'gus' },
      { key: 'p2-l1', who: 'Lila', fr: 'Demain matin.', en: '', character: 'lila' },
    ],
    caption: 'Le plombier attend.',
    tasks: [],
  },
];

function renderStory(overrides = {}) {
  return renderToStaticMarkup(React.createElement(FeuilletonReader, {
    episodeLabel: 'Chapitre 1 · S’installer, avec complications',
    title: 'Un prêt théâtral',
    stages: storyStages,
    index: 0,
    furthest: 0,
    onIndexChange: () => {},
    answers: {},
    setAnswer: () => {},
    onSubmit: () => {},
    submittingTask: null,
    attemptsByTask: {},
    submitError: null,
    liveTaskId: null,
    onExit: () => {},
    onComplete: null,
    filed: false,
    panelVariant: (stage) => (stage.lines.length === 1 ? 'bubble' : 'line'),
    ...overrides,
  }));
}

test('variant A: a single reply is a bubble on the art, above the narration', () => {
  const markup = renderStory({ index: 0 });
  assert.ok(/class="fr-bubble"/.test(markup), 'the bubble is drawn');
  // TappableFrench splits the line into word buttons, so the words are
  // asserted one by one rather than as one string.
  assert.ok(/Augustin/.test(markup));
  assert.ok(/aider/.test(markup));
  // the bubble lives inside the plate, not under it
  const plate = markup.slice(markup.indexOf('class="fr-plate"'));
  assert.ok(plate.indexOf('fr-bubble') < plate.indexOf('</figure>'), 'the bubble is inside the frame');
  // narration follows the art as body copy
  assert.ok(/fr-caption/.test(markup));
  assert.ok(markup.indexOf('fr-caption') > markup.indexOf('fr-plate'));
});

test('variant B: two replies are cards under the art, after the narration', () => {
  const markup = renderStory({ index: 1 });
  assert.ok(!/class="fr-bubble"/.test(markup), 'no bubble when the panel carries two lines');
  assert.ok(/fr-speech/.test(markup));
  assert.ok(markup.indexOf('fr-caption') < markup.indexOf('fr-speech'), 'narration precedes the replies');
  assert.ok(/euros/.test(markup) && /matin/.test(markup));
});

test('the story reader is marked as such, and carries the art provenance quietly', () => {
  const markup = renderStory({ artProvenance: 'setting_reference' });
  assert.ok(/data-story="1"/.test(markup));
  assert.ok(/data-art="setting_reference"/.test(markup), 'telemetry can still read where the art came from');
  assert.ok(!/montre le lieu/.test(markup), 'the learner is told nothing about it');
});

test('the quiet foot link sits under the nav, and only when it is given', () => {
  const withLink = renderStory({ footLink: React.createElement('button', { type: 'button' }, 'Écouter d’abord') });
  assert.ok(/fr-foot-link/.test(withLink));
  assert.ok(withLink.indexOf('fr-foot-link') > withLink.indexOf('fr-nav-row'), 'under the nav row');
  assert.ok(!/fr-foot-link/.test(renderStory()));
});

test('the legacy edition keeps the layout it had', () => {
  const { markup } = render(capturedScene);
  assert.ok(!/data-story="1"/.test(markup));
  assert.ok(!/class="fr-bubble"/.test(markup));
});

// ---------------------------------------------------------------------------
// WP-82 — the reader's chrome follows the one language rule
// ---------------------------------------------------------------------------

test('an A1 English learner reads the reader chrome in English; the story stays French', () => {
  const { markup } = render(capturedScene, { index: 0, furthest: 0, language: 'en' });
  assert.ok(/aria-label="Panel 1 of 5"/.test(markup), 'the position is in English');
  assert.ok(/aria-roledescription="panel"/.test(markup));
  assert.ok(/>Next </.test(markup), 'Next, not Suivant');
  assert.ok(/<span class="fr-sr">Previous<\/span>/.test(markup), 'Previous, not Précédent');
  for (const french of ['Suivant', 'Précédent', 'Planche 1 sur', 'Lecteur du feuilleton', 'Quitter la lecture']) {
    assert.ok(!markup.includes(french), `no French chrome: ${french}`);
  }
  // The story's own words are content and still French.
  assert.ok(/lang="fr"/.test(markup));
});

test('German chrome, and French stays the default for callers that pass none', () => {
  const de = render(capturedScene, { index: 0, furthest: 0, language: 'de' }).markup;
  assert.ok(/aria-label="Bild 1 von 5"/.test(de));
  assert.ok(/>Weiter </.test(de));
  const fr = render(capturedScene, { index: 0, furthest: 0 }).markup;
  assert.ok(/>Suivant </.test(fr));
  assert.ok(/aria-label="Planche 1 sur 5"/.test(fr));
});

test('the last panel closes in the learner language too', () => {
  const stages = buildReaderStages(capturedScene);
  const last = stages.length - 1;
  const en = render(capturedScene, { index: last, furthest: last, language: 'en' }).markup;
  assert.ok(/aria-label="End of the episode, /.test(en));
  assert.ok(/Finish the episode/.test(en), 'the default closing label is English');
  assert.ok(!/Terminer l’épisode/.test(en));
});
