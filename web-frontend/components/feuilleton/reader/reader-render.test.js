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
  // WP-90 (W4): one progress indicator — the dots — and no rail or counter.
  assert.ok(!/role="progressbar"/.test(markup), 'no second progress bar');
  assert.ok(!/fr-rail|fr-count/.test(markup));
  assert.ok(/<ol class="fr-dots" aria-label="Avancement dans l’épisode"/.test(markup));
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

// ---------------------------------------------------------------------------
// WP-90 «La planche» — a page that is ready, fits, and acts
// ---------------------------------------------------------------------------

const planche = [
  {
    ...storyStages[0],
    imageAlt: 'Augustin smiles at the counter.',
    lines: [{ ...storyStages[0].lines[0], faceId: 'augustin_de_roncourt', faceMood: 'happy', en: 'I can help.', audioKey: 'p1:l0' }],
  },
  { ...storyStages[1], artPending: true, imageAlt: '' },
  {
    kind: 'resolution',
    key: 'finale:r1',
    ordinal: 3,
    character: 'gus',
    hookQuestion: '',
    hookBeat: '',
    tasks: [],
    finale: {
      imageUrl: '/assets/serial/scenes/order_at_cafe/panel-4.webp',
      imageAlt: 'You ordered politely.',
      line: { key: 'f-l0', who: 'Augustin', fr: 'À demain !', en: '', character: 'gus', faceId: 'augustin_de_roncourt', faceMood: 'moved' },
      summary: 'You ordered politely, and he remembered you.',
      waiting: false,
    },
  },
];

function renderPlanche(overrides = {}) {
  return renderStory({
    stages: planche,
    title: 'Le Mistral',
    episodeLabel: 'Le Mistral',
    panelVariant: () => 'line',
    ...overrides,
  });
}

test('WP-90: the headline folds into a running head after the first panel', () => {
  const first = renderPlanche({ index: 0 });
  assert.ok(/class="fr-title"/.test(first), 'panel 1 has its headline');
  assert.equal((first.match(/Le Mistral/g) || []).length, 1, 'no kicker repeating the title');
  const later = renderPlanche({ index: 1, furthest: 1 });
  assert.ok(!/class="fr-title"/.test(later), 'the headline has folded');
  assert.ok(/<p class="fr-running" lang="fr">Le Mistral · 2\/3<\/p>/.test(later), later.slice(0, 600));
  assert.ok(!/role="progressbar"/.test(later), 'the dots are the one progress indicator');
});

test('WP-90: a plate on the press is a duotone with a folio ribbon, in a frame that holds its size', () => {
  const markup = renderPlanche({ index: 1, furthest: 1, language: 'en' });
  assert.ok(/<figure class="fr-plate" data-variant="line" data-pending="true">/.test(markup));
  assert.ok(/class="fr-ink" aria-hidden="true" data-on="true"/.test(markup));
  assert.ok(/<figcaption class="fr-folio">Panel 2 · on the press<\/figcaption>/.test(markup));
  const drawn = renderPlanche({ index: 0, language: 'fr' });
  assert.ok(!/fr-folio/.test(drawn), 'a drawn panel has no ribbon');
  assert.ok(/alt="Augustin smiles at the counter\."/.test(drawn), 'the picture says what it shows');
});

// WP-116 phase 6: the drawn cast is the default; painted assertions pin the painted set.
const launchFlags = require(path.join(ROOT, 'launch-flags.json'));
function withArtSet(value, fn) {
  const before = launchFlags.artSet;
  launchFlags.artSet = value;
  try {
    return fn();
  } finally {
    launchFlags.artSet = before;
  }
}

test('WP-90: captions — a face that acts, a line read as one sentence, words that rove', () => {
  const painted = withArtSet('painted', () => renderPlanche({ index: 0, language: 'en' }));
  assert.ok(/alt="Augustin, pleased"/.test(painted), 'the portrait says who and how');
  // Drawn: the rig is the image, named the same way, in the same mood.
  const markup = withArtSet('drawn', () => renderPlanche({ index: 0, language: 'en' }));
  assert.ok(/role="img" aria-label="Augustin, pleased" data-cast="augustin_de_roncourt" data-mood="ravie"/.test(markup), 'the drawn face says who and how');
  assert.ok(/class="fr-speech" data-compact="true"/.test(markup));
  assert.ok(/data-mood="happy"/.test(markup), 'the face wears the line’s mood');
  assert.ok(/role="group" tabindex="0" aria-label="Je peux aider\." data-roving-line=""/.test(markup));
  assert.ok(/aria-label="Help with “aider”"/.test(markup), 'the word labels are the learner’s language');
  assert.ok(/<button type="button" class="fr-word" data-word="" tabindex="-1"/.test(markup), 'words leave the Tab order');
});

test('WP-90: a translated line brings «Translate» into the bar', () => {
  const markup = renderPlanche({ index: 0, language: 'en' });
  const bar = markup.slice(markup.indexOf('class="fr-bar"'), markup.indexOf('class="fr-head"'));
  assert.ok(/aria-label="Translate the panel"/.test(bar), 'the chip sits in the bar, fixed');
  assert.ok(!/fr-tools/.test(markup), 'and not under the panel, where it would move things');
});

test('WP-90: the ending is the last panel — the case finale', () => {
  const markup = renderPlanche({ index: 2, furthest: 2, onComplete: () => {}, completeLabel: 'Continue', language: 'en' });
  assert.ok(/class="fr-finale"/.test(markup));
  assert.ok(/The last panel/.test(markup));
  assert.ok(/À demain/.test(markup));
  assert.ok(/You ordered politely, and he remembered you\./.test(markup));
  assert.ok(/alt="You ordered politely\."/.test(markup));
  assert.ok(/data-kind="resolution"/.test(markup), 'the red triangle is its dot');
  assert.ok(/data-press="3d"[^>]*>.*Continue/.test(markup), 'one primary closes the day');

  const waiting = planche.map((stage) =>
    stage.kind === 'resolution' ? { ...stage, finale: { ...stage.finale, waiting: true } } : stage,
  );
  const wait = renderPlanche({
    stages: waiting,
    index: 2,
    furthest: 2,
    onComplete: () => {},
    finaleWait: React.createElement('p', { className: 'wait-face' }, 'Augustin écrit…'),
  });
  assert.ok(/wait-face/.test(wait), 'the wait has a face');
  assert.ok(!/fr-next/.test(wait), 'and no dead primary');
});

// ---------------------------------------------------------------------------
// WP-110 — the learner's own line is the balloon in its panel
// ---------------------------------------------------------------------------

test('WP-110: your line is the balloon on the art; the character keeps a caption', () => {
  const turn = {
    kind: 'panel', key: 'panel:turn', ordinal: 1, panelId: 'turn', panelIndex: 0, title: '', beat: '',
    imageUrl: '/assets/serial/locations/le_mistral-counter.webp', artStatus: 'ready', character: 'gus',
    caption: '', tasks: [], movement: 'turn',
    lines: [
      { key: 'l0', who: 'Gus', fr: 'Vous êtes qui, exactement ?', en: '', character: 'gus' },
      { key: 'l1', who: 'Vous', fr: 'Ma grand-mère était Odile.', en: '', character: 'toi', you: true },
    ],
  };
  const markup = renderStory({ stages: [turn], index: 0, panelVariant: () => 'bubble' });
  const bubble = markup.slice(markup.indexOf('class="fr-bubble"'), markup.indexOf('</figure>'));
  assert.ok(/data-you="true"/.test(bubble), 'the balloon is marked as yours');
  assert.ok(/grand-mère/.test(bubble), 'your words are in the balloon');
  assert.ok(!/exactement/.test(bubble), 'the character is not');
  const captions = markup.slice(markup.indexOf('</figure>'));
  assert.ok(/exactement/.test(captions), 'the character keeps a caption under the art');
});

test('WP-110: the replay closes on «À suivre…» with tomorrow’s line', () => {
  const ending = { kind: 'resolution', key: 'resolution:x', ordinal: 1, character: 'toi', hookQuestion: 'Fin.', hookBeat: '', tasks: [], aSuivre: 'Demain, Camille.' };
  const markup = renderStory({ stages: [ending], index: 0 });
  assert.ok(/data-a-suivre="true"/.test(markup));
  assert.ok(/Demain, Camille\./.test(markup));
});

// ---------------------------------------------------------------------------
// WP-137 C-5 — a silent panel is never a bare plate
// ---------------------------------------------------------------------------

test('WP-137: a silent panel carries a caption in the learner’s language and a slow pan', () => {
  const silent = {
    kind: 'panel', key: 'panel:p3', ordinal: 3, panelId: 'p3', panelIndex: 2, title: '', beat: '',
    imageUrl: '/assets/serial/locations/le_mistral-counter.webp', artStatus: 'ready', character: '',
    caption: '', tasks: [], lines: [], silent: true,
  };
  for (const [language, words] of [['de', 'Stille'], ['en', 'silence'], ['fr', 'silence']]) {
    for (const variant of ['line', null]) {
      const markup = renderStory({ stages: [silent], index: 0, language, panelVariant: () => variant });
      assert.ok(/<figure class="fr-plate"[^>]*data-pan="slow"/.test(markup), `${language} ${variant}: the plate pans`);
      assert.ok(new RegExp(`class="fr-caption fr-caption--silent">[^<]*${words}`).test(markup), `${language} ${variant}: a caption`);
    }
  }
  const spoken = renderPlanche({ index: 0 });
  assert.ok(!/data-pan=/.test(spoken) && !/fr-caption--silent/.test(spoken), 'a panel with words stays as it was');
});
