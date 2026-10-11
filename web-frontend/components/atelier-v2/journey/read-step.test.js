// node --test components/atelier-v2/journey/read-step.test.js
//
// WP-93 — the READ step («Relecture», «Coulisses»), and WP-92's scene anchor
// on the rule card.
//
//   1. the step's model: which view, when to poll, whose evening, the kicker;
//   2. the day mark counts a page to read with the Scène (blue circle), and a
//      skipped one still lets the Scène close;
//   3. every state keeps an enabled «Continuer»; `unavailable` is one quiet line;
//   4. the rule card shows the scene's own line first, with its speaker, and
//      the generic example after it — and is unchanged without one.

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

const readModel = require('./read-step-model.ts');
const { ReadStepView } = require('./ReadStep.tsx');
const { RuleStepView } = require('./JourneySteps.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { dayMarkState, dayMarkGroupOf, STEP_SHAPE } = require('./day-mark.ts');
const { journeySpeaker } = require('./journey-faces.ts');
const { ruleSceneAnchor } = require('../../../lib/rule-card.ts');

const h = React.createElement;

function readStep(prompt, extra = {}) {
  return {
    id: 'read-1',
    ordinal: 2,
    kind: 'read',
    status: 'active',
    estimated_seconds: 90,
    assistance_used: [],
    prompt: {
      variant: 'coulisses',
      title_fr: 'La soirée de Marin',
      scene_id: null,
      status: 'writing',
      audio_available: false,
      ...prompt,
    },
    ...extra,
  };
}

// --- 1. the model ---------------------------------------------------------------

test('the view follows the server’s status, and a page that cannot be had is unavailable', () => {
  const episode = { panels: [{ id: 'p1' }] };
  assert.equal(readModel.readStepView({ status: 'writing' }, { kind: 'idle' }), 'writing');
  assert.equal(readModel.readStepView({ status: 'unavailable' }, { kind: 'idle' }), 'unavailable');
  assert.equal(readModel.readStepView({ status: 'bogus' }, { kind: 'idle' }), 'unavailable');
  assert.equal(readModel.readStepView(null, { kind: 'idle' }), 'unavailable');
  assert.equal(readModel.readStepView({ status: 'ready', scene_id: null }, { kind: 'idle' }), 'unavailable');
  assert.equal(readModel.readStepView({ status: 'ready', scene_id: 's' }, { kind: 'loading' }), 'loading');
  assert.equal(readModel.readStepView({ status: 'ready', scene_id: 's' }, { kind: 'failed' }), 'unavailable');
  assert.equal(readModel.readStepView({ status: 'ready', scene_id: 's' }, { kind: 'episode', episode: { panels: [] } }), 'unavailable');
  assert.equal(readModel.readStepView({ status: 'ready', scene_id: 's' }, { kind: 'episode', episode }), 'reader');
  assert.equal(readModel.readStepWantsEpisode({ status: 'ready', scene_id: 's' }), 's');
  assert.equal(readModel.readStepWantsEpisode({ status: 'writing', scene_id: 's' }), null, 'no fetch while writing');
});

test('the journey is re-read while «Coulisses» is written — only then, gently and bounded', () => {
  const journey = (step, status = 'active') => ({ id: 'j1', status, current_step_id: step.id, steps: [step] });
  assert.equal(readModel.readPollTarget(journey(readStep({ status: 'writing' }))), 'j1');
  assert.equal(readModel.readPollTarget(journey(readStep({ status: 'writing' }), 'paused')), 'j1');
  assert.equal(readModel.readPollTarget(journey(readStep({ status: 'ready', scene_id: 's' }))), null);
  assert.equal(readModel.readPollTarget(journey(readStep({ status: 'unavailable' }))), null);
  assert.equal(readModel.readPollTarget(journey(readStep({ status: 'writing' }), 'completed')), null);
  assert.equal(readModel.readPollTarget(null), null);
  assert.ok(readModel.READ_POLL_MS >= 3000, 'gently — not the ending’s one-second poll');
  assert.ok(readModel.READ_POLL_LIMIT * readModel.READ_POLL_MS <= 5 * 60 * 1000, 'bounded');
  const hook = fs.readFileSync(path.join(__dirname, 'useDailyJourney.ts'), 'utf8');
  assert.match(hook, /readPollTarget\(journey\)/);
});

test('the kicker names the variant and whose evening, in the chrome language', () => {
  const fr = journeyCopy('fr');
  const en = journeyCopy('en');
  const de = journeyCopy('de');
  assert.equal(readModel.readStepEyebrow({ variant: 'relecture' }, fr, 'Marin'), 'Relecture · la page d’hier');
  assert.equal(readModel.readStepEyebrow({ variant: 'coulisses' }, fr, 'Marin'), 'Coulisses · la soirée de Marin');
  assert.equal(readModel.readStepEyebrow({ variant: 'coulisses' }, en, 'Marin'), 'Behind the scenes · Marin’s evening');
  assert.equal(readModel.readStepEyebrow({ variant: 'coulisses' }, de, 'Marin'), 'Hinter den Kulissen · der Abend von Marin');
  assert.equal(readModel.readStepEyebrow({ variant: 'coulisses' }, en, ''), 'Behind the scenes · the same evening');
  assert.equal(readModel.readStepWritingLine(fr, 'Marin'), 'La soirée de Marin s’écrit…');
  // whose evening: the prompt's cast member, else the day's counterpart
  const margaux = { id: 'margaux_barman', name: 'Margaux' };
  assert.deepEqual(readModel.readStepSpeaker({ variant: 'coulisses', character_name: 'Marin', character_id: 'marin_leveque' }, margaux), { id: 'marin_leveque', name: 'Marin' });
  assert.deepEqual(readModel.readStepSpeaker({ variant: 'coulisses', character_id: 'marin_leveque' }, margaux), { id: 'marin_leveque', name: 'Marin' });
  assert.deepEqual(readModel.readStepSpeaker({ variant: 'coulisses' }, margaux), margaux);
  assert.equal(readModel.readStepSpeaker({ variant: 'relecture' }, margaux), null);
  assert.deepEqual(
    journeySpeaker({ scenario: { character_name: 'Margaux', character_id: 'margaux_barman' } }, readStep({ character_name: 'Marin', character_id: 'marin_leveque' })),
    { id: 'marin_leveque', name: 'Marin' },
  );
});

// --- 2. the day mark --------------------------------------------------------------

function journeyOf(kinds, upTo, statuses = {}) {
  const steps = kinds.map((kind, index) => ({
    id: `s${index}`,
    kind,
    status: statuses[index] ?? (index < upTo ? 'completed' : index === upTo ? 'active' : 'pending'),
  }));
  return { id: 'j', status: 'active', day_shape: 'standard', current_step_id: `s${upTo}`, steps };
}

test('a page to read is a blue circle, counted with the Scène; skipping it still closes the Scène', () => {
  assert.equal(STEP_SHAPE.read, 'story');
  assert.equal(dayMarkGroupOf('read'), 'scene');
  const kinds = ['read', 'scene', 'recall', 'respond', 'resolution'];
  const reading = dayMarkState(journeyOf(kinds, 0));
  assert.equal(reading.total, 4, 'the mark keeps four shapes');
  assert.equal(reading.groups.scene, 'active');
  const skipped = dayMarkState(journeyOf(kinds, 2, { 0: 'skipped' }));
  assert.equal(skipped.groups.scene, 'done', 'optional: skipping it is not a hole in the day');
});

// --- 3. the view ------------------------------------------------------------------

function renderRead(prompt, language = 'en') {
  return renderToStaticMarkup(
    h(ReadStepView, {
      journeyId: 'j1',
      step: readStep(prompt),
      copy: { ...journeyCopy(language) },
      busy: false,
      onContinue: () => {},
      language,
      speaker: { id: 'margaux_barman', name: 'Margaux' },
    }),
  );
}

function continueButtons(html) {
  return html.match(/<button[^>]*>(?:(?!<\/button>).)*Continue(?:(?!<\/button>).)*<\/button>/g) || [];
}

test('writing: the face writes the page, and «Continuer» is enabled', () => {
  const html = renderRead({ status: 'writing', character_name: 'Marin', character_id: 'marin_leveque' });
  assert.match(html, /data-read-state="writing"/);
  assert.match(html, /Behind the scenes · Marin’s evening/);
  assert.match(html, /Marin’s evening is being written…/);
  assert.match(html, /role="status"/);
  const buttons = continueButtons(html);
  assert.equal(buttons.length, 1);
  assert.doesNotMatch(buttons[0], /disabled/);
  assert.doesNotMatch(html, /av2-btn--primary/, 'waiting is not a dead primary');
});

test('unavailable: one quiet line, and «Continuer» is the one primary', () => {
  const html = renderRead({ status: 'unavailable', variant: 'relecture', title_fr: 'Le Mistral' }, 'en');
  assert.match(html, /data-read-state="unavailable"/);
  assert.match(html, /Re-read · yesterday’s page/);
  assert.match(html, /This page won’t be ready today/);
  assert.doesNotMatch(html, /role="alert"/, 'a quiet notice, not an error');
  assert.equal((html.match(/av2-btn--primary/g) || []).length, 1);
  assert.doesNotMatch(continueButtons(html)[0], /disabled/);
});

test('ready: the page is asked for by its scene (a loading state until it arrives), skippable', () => {
  const html = renderRead({ status: 'ready', scene_id: 'scene-yesterday', variant: 'relecture' }, 'fr');
  assert.match(html, /data-read-state="loading"/);
  assert.match(html, /Relecture · la page d’hier/);
  const buttons = html.match(/<button[^>]*>(?:(?!<\/button>).)*Continuer(?:(?!<\/button>).)*<\/button>/g) || [];
  assert.equal(buttons.length, 1);
  assert.doesNotMatch(buttons[0], /disabled/);
  const source = fs.readFileSync(path.join(__dirname, 'ReadStep.tsx'), 'utf8');
  assert.match(source, /mode="reread"/, 'read-only: the reader’s reread mode');
  assert.match(source, /useStepVoice\(journeyId, step\.id\)/, 'the faces speak through the step');
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  assert.match(session, /step\.kind === 'read'/);
  assert.match(session, /<ReadStepView/);
});

// --- 4. the rule card's scene anchor ------------------------------------------------

const CARD = {
  speaker: 'margaux_barman',
  example: { fr: '[Je suis] Margaux.' },
  rule: { en: 'Être means to be.', de: 'Être heißt sein.', fr: 'Être, c’est être.' },
};

function ruleStep(extra = {}) {
  return {
    id: 'rule-1',
    ordinal: 3,
    kind: 'rule',
    status: 'active',
    estimated_seconds: 33,
    assistance_used: [],
    prompt: {
      concept_id: 12,
      title_native: 'Être',
      title_fr: 'Être',
      rule_card: CARD,
      ...extra,
    },
  };
}

function renderRule(step, language = 'en') {
  return renderToStaticMarkup(
    h(RuleStepView, { step, copy: journeyCopy(language), busy: false, language, onContinue: () => {}, journeyId: 'j1' }),
  );
}

test('the anchor reads the prompt defensively: speaker id or name, or nothing', () => {
  assert.equal(ruleSceneAnchor({}), null);
  assert.equal(ruleSceneAnchor({ scene_example_fr: '  ' }), null);
  assert.deepEqual(ruleSceneAnchor({ scene_example_fr: 'Je suis en retard !', scene_example_speaker: 'marin_leveque' }), {
    fr: 'Je suis en retard !',
    castId: 'marin_leveque',
    name: 'Marin',
  });
  assert.equal(ruleSceneAnchor({ scene_example_fr: 'Je suis là.', scene_example_speaker: 'Margaux' }).castId, 'margaux_barman');
  assert.deepEqual(ruleSceneAnchor({ scene_example_fr: 'Je suis là.', scene_example_speaker: 'le_facteur' }), {
    fr: 'Je suis là.',
    castId: null,
    name: 'Le facteur',
  });
});

test('the scene line is the first anchor, with its speaker’s face; the generic example follows', () => {
  const html = renderRule(ruleStep({ scene_example_fr: 'Je suis en retard, pardon !', scene_example_speaker: 'marin_leveque' }));
  const anchorAt = html.indexOf('data-anchor="scene"');
  const genericAt = html.indexOf('Margaux.</p>');
  assert.ok(anchorAt > 0, 'the anchor is drawn');
  assert.ok(genericAt > anchorAt, 'the generic example follows it');
  assert.match(html, /in today’s scene/);
  assert.match(html, /class="rc-scene__who">Marin</);
  assert.match(html, /data-size="xs"/, 'the speaker’s face, small');
  assert.equal((html.match(/av2-headline/g) || []).length, 1, 'still one Garamond line: the scene’s');
  assert.match(html, /<h2 class="av2-headline rc-example" lang="fr">Je suis en retard, pardon !<\/h2>/);
  assert.match(html, /<p class="rc-example rc-example--inline" lang="fr"><span class="rc-mark">Je suis<\/span> Margaux.<\/p>/);
});

test('without a scene line the card is exactly what it was', () => {
  const html = renderRule(ruleStep({ scene_example_fr: null, scene_example_speaker: null }));
  assert.doesNotMatch(html, /data-anchor|in today’s scene/);
  assert.match(html, /<h2 class="av2-headline rc-example" lang="fr"><span class="rc-mark">Je suis<\/span> Margaux.<\/h2>/);
});
