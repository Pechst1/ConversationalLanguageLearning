// node --test components/atelier-v2/journey/revue-day.test.js
//
// WP-119 phase 3 · the Revue day inside the journey player.
//
//   1. a finished Revue day (`day_shape: 'revue'`) mounts the Papier
//      (RvJourneyPapier → the ONE RvEncounter) in place of the recap;
//   2. a standard day shows the recap and no Papier; so does a Revue day ended
//      early, and a Revue day still in session shows its step;
//   3. `papierEntryAction`: nothing to do → done, a session in progress →
//      resume, already filed → done, else start;
//   4. the hero on La Une opens the day until it is done (`revueHeroOpensDay`).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..', '..');
const REPO_ROOT = path.resolve(WEB_ROOT, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (typeof request === 'string' && request.startsWith('@/')) {
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

const { JourneySession } = require('./JourneySession.tsx');
const { RvJourneyPapier, papierEntryAction, papierReleveHref } = require('@/components/revue/RvJourneyPapier.tsx');
const { revueHeroOpensDay } = require('@/lib/revue-une.ts');

const h = React.createElement;
const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/completed.json'), 'utf8'),
).response;

function finished(journeyOverrides = {}) {
  const journey = { ...FIXTURE, day_shape: 'standard', ...journeyOverrides };
  return {
    phase: { kind: 'finished', journey, recap: journey.recap ?? null },
    feedback: { kind: 'idle' },
    envelope: null,
    journey,
    step: null,
    respondPrompt: null,
    controlLanguage: 'en',
    legacyResume: null,
    progress: { done: journey.steps.length, total: journey.steps.length },
    busy: false,
    help: null,
    voice: { kind: 'idle' },
    recovery: null,
    actions: new Proxy({}, { get: () => () => Promise.resolve() }),
  };
}

const RECAP = /class="journey-recap /;
const PAPIER = /data-revue-journey="loading"/;

test('a finished Revue day mounts the Papier, not the recap', () => {
  const html = renderToStaticMarkup(h(JourneySession, { controller: finished({ day_shape: 'revue' }) }));
  assert.match(html, PAPIER);
  assert.match(html, /class="av2 rv-page"/);
  assert.doesNotMatch(html, RECAP);
});

test('a standard day shows the recap and no Papier', () => {
  const html = renderToStaticMarkup(h(JourneySession, { controller: finished({ day_shape: 'standard' }) }));
  assert.match(html, RECAP);
  assert.doesNotMatch(html, /data-revue-journey/);
});

test('a Revue day ended early goes straight to its recap', () => {
  const html = renderToStaticMarkup(
    h(JourneySession, { controller: finished({ day_shape: 'revue', status: 'ended_early' }) }),
  );
  assert.match(html, RECAP);
  assert.doesNotMatch(html, /data-revue-journey/);
});

test('the Papier mount: its loading line, before the week is read', () => {
  const html = renderToStaticMarkup(h(RvJourneyPapier, { language: 'fr', onDone: () => {} }));
  assert.match(html, PAPIER);
  assert.match(html, /Romy rassemble ses notes/);
  assert.match(html, /role="status"/);
});

const card = { dossierId: 'd1' };
const offer = (extra = {}) => ({
  week: { iso: '2026-W40', label: 'Semaine 40', range: '' },
  recommended: card,
  recommendedReason: 'first',
  alternatives: [],
  evergreenOnly: false,
  resume: null,
  filed: null,
  ...extra,
});

test('papierEntryAction: done / resume / start', () => {
  assert.equal(papierEntryAction(null), 'done');
  assert.equal(papierEntryAction({ enabled: false }), 'done');
  assert.equal(papierEntryAction({ enabled: true, offer: offer({ recommended: null }) }), 'done');
  assert.equal(papierEntryAction({ enabled: true, offer: offer({ filed: { sessionId: 's' } }) }), 'done');
  assert.equal(papierEntryAction({ enabled: true, offer: offer({ resume: { sessionId: 's' } }) }), 'resume');
  // A session in progress wins even without a recommendation.
  assert.equal(papierEntryAction({ enabled: true, offer: offer({ recommended: null, resume: { sessionId: 's' } }) }), 'resume');
  assert.equal(papierEntryAction({ enabled: true, offer: offer() }), 'start');
  assert.equal(papierReleveHref('2026-W40'), '/notebook?mode=releve#revue-2026-W40');
});

test('the Revue hero opens the day until it is done', () => {
  assert.equal(revueHeroOpensDay(false, true), true);
  assert.equal(revueHeroOpensDay(true, true), false);
  assert.equal(revueHeroOpensDay(false, false), false);
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'atelier.tsx'), 'utf8');
  assert.match(page, /revueHeroOpensDay\(revueDayDone, Boolean\(onOpenDay\)\)/);
  assert.match(page, /onOpenDay=\{\(\) => \{/);
});

// --- REVUE_PLANNED_STEP_ENABLED: the Papier as the day's last step ---------------

const deskModel = require('./desk-step-model.ts');

const PAPIER_STEP = {
  id: 'papier-1',
  ordinal: 5,
  kind: 'desk',
  status: 'active',
  estimated_seconds: 360,
  assistance_used: [],
  act: 1,
  prompt: { desk: 'papier', title_fr: 'Le Papier', dossier_id: null, relecture: null, seconds: 360 },
};

test('the step model knows the Papier step, and the after-ending mount stands down for it', () => {
  assert.equal(deskModel.isPapierStep(PAPIER_STEP), true);
  assert.equal(deskModel.isPapierStep({ ...PAPIER_STEP, prompt: { ...PAPIER_STEP.prompt, desk: 'radio' } }), false);
  assert.equal(deskModel.isPapierStep({ kind: 'recall', prompt: { desk: 'papier' } }), false);
  assert.equal(deskModel.isPapierStep(null), false);
  assert.equal(deskModel.planHoldsPapier([{ kind: 'scene' }, PAPIER_STEP]), true);
  assert.equal(deskModel.planHoldsPapier([{ kind: 'scene' }]), false);
  assert.equal(deskModel.planHoldsPapier(undefined), false);
  const base = { revueDay: true, finished: true, endedEarly: false, left: false, steps: [{ kind: 'resolution' }] };
  assert.equal(deskModel.showsPapierAfterEnding(base), true, 'switch off: the old mount, exactly');
  assert.equal(deskModel.showsPapierAfterEnding({ ...base, steps: [{ kind: 'resolution' }, PAPIER_STEP] }), false);
  assert.equal(deskModel.showsPapierAfterEnding({ ...base, endedEarly: true }), false);
  assert.equal(deskModel.showsPapierAfterEnding({ ...base, left: true }), false);
  assert.equal(deskModel.showsPapierAfterEnding({ ...base, revueDay: false }), false);
  assert.equal(deskModel.showsPapierAfterEnding({ ...base, finished: false }), false);
  assert.deepEqual(deskModel.deskStepView(PAPIER_STEP), { desk: 'papier', titleFr: 'Le Papier' });
  for (const language of ['fr', 'en', 'de']) {
    assert.ok(deskModel.deskCopy(language).lead.papier.length > 10, language);
    assert.equal(deskModel.deskKicker(deskModel.deskStepView(PAPIER_STEP), language), 'Le Papier');
  }
});

test('a finished Revue day that held the Papier as a step shows its recap, not the Papier again', () => {
  const steps = [...FIXTURE.steps, { ...PAPIER_STEP, status: 'completed' }];
  const html = renderToStaticMarkup(h(JourneySession, { controller: finished({ day_shape: 'revue', steps }) }));
  assert.match(html, RECAP);
  assert.doesNotMatch(html, /data-revue-journey/);
});

test('at the Papier step the player mounts the Papier through the step machinery', () => {
  const journey = { ...FIXTURE, status: 'active', day_shape: 'revue', current_step_id: PAPIER_STEP.id, steps: [...FIXTURE.steps, PAPIER_STEP] };
  const controller = {
    ...finished(),
    phase: { kind: 'session', journey },
    journey,
    step: PAPIER_STEP,
    progress: { done: journey.steps.length - 1, total: journey.steps.length },
  };
  const html = renderToStaticMarkup(h(JourneySession, { controller }));
  assert.match(html, PAPIER);
  assert.doesNotMatch(html, /data-desk=/, 'not the desk card');
  assert.doesNotMatch(html, RECAP);
  const source = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  // Finishing, leaving or nothing to do: the day continues like after any step.
  assert.match(source, /<RvJourneyPapier\s+key=\{step\.id\}[\s\S]*?void continueRef\.current\(\)/);
});
