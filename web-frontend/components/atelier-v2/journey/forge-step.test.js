// node --test components/atelier-v2/journey/forge-step.test.js
//
// WP-S4 — La Forge: one engine, one picker, one day.
//
//   1. The name follows the one language rule: «Forge today's rule» /
//      «Forger la règle du jour» / «Regel des Tages schmieden».
//   2. Léger and Régulier: the envelope's forge entry is the after-day chip on
//      Home and the recap's quiet button, replacing «More practice»; folded
//      (Soutenu, Intensif) it is not offered after the day.
//   3. Soutenu and Intensif: the forge step opens the block and, once forged,
//      leads back to the scene; the day mark counts it in the yellow square.
//   4. The practice entry seats the asked-for rule even when a séance is open.

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

const { ForgeStepView } = require('./JourneySteps.tsx');
const { JourneyRecap } = require('./JourneyRecap.tsx');
const { journeyCopy } = require('./journey-copy.ts');
const { dayMarkState, dayMarkGroupOf, STEP_SHAPE } = require('./day-mark.ts');
const { forgeLabel, forgeHref, forgeMinutes, resolveForgeEntry } = require('@/lib/atelier-next.ts');

const h = React.createElement;
const decode = (html) => html.replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, '&');

// ---------------------------------------------------------------------------
// 1. The name
// ---------------------------------------------------------------------------

test('the forge is named in the learner’s language', () => {
  assert.equal(forgeLabel('en'), 'Forge today’s rule');
  assert.equal(forgeLabel('fr'), 'Forger la règle du jour');
  assert.equal(forgeLabel('de'), 'Regel des Tages schmieden');
  assert.equal(forgeLabel(undefined), 'Forge today’s rule');
  for (const language of ['en', 'de', 'fr']) {
    assert.equal(journeyCopy(language).forge_today, forgeLabel(language), language);
  }
  assert.equal(forgeHref(12), '/atelier?mode=forge&concept=12');
  assert.equal(forgeHref(null), '/atelier?mode=forge');
  assert.equal(forgeMinutes(300), 5);
  assert.equal(forgeMinutes(null), 5);
});

// ---------------------------------------------------------------------------
// 2. After the day — Léger and Régulier
// ---------------------------------------------------------------------------

function envelope(forge, enabled = true) {
  return { enabled, practice_href: '/atelier?mode=practice', forge, journey: null };
}

test('Léger and Régulier get «Forge today’s rule» after the day; a folded day does not', () => {
  const entry = resolveForgeEntry(
    envelope({ href: '/atelier?mode=forge&concept=7', concept_id: 7, budget_seconds: 300, folded: false }),
    'en',
  );
  assert.deepEqual(entry, {
    label: 'Forge today’s rule',
    href: '/atelier?mode=forge&concept=7',
    minutes: 5,
    conceptId: 7,
  });
  assert.equal(
    resolveForgeEntry(envelope({ href: '/atelier?mode=forge', concept_id: null, budget_seconds: 420, folded: true })),
    null,
    'Soutenu/Intensif forge inside the day',
  );
  assert.equal(resolveForgeEntry(envelope(null)), null, 'an older server sends no forge');
  assert.equal(resolveForgeEntry(envelope({ href: '/x', budget_seconds: 300, folded: false }, false)), null);
});

test('Home’s after-day chip is the forge on Léger/Régulier, «More practice» otherwise', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  const chip = page.slice(page.indexOf('WP-S4: on Léger and Régulier that entry is La Forge'));
  assert.match(chip, /forgeEntry\s*\?\s*\{\s*id: 'forge',\s*label: forgeEntry\.label/);
  assert.match(chip, /href: forgeEntry\.href/);
  assert.match(chip, /id: 'practice',\s*label: homeCopy\.home_practice/);
  assert.match(page, /resolveForgeEntry\(journey\.envelope, journeyChromeLanguage\(journey\)\)/);
});

const FIXTURE = JSON.parse(
  fs.readFileSync(path.join(REPO_ROOT, 'tests/fixtures/daily_journey_v1/public/completed.json'), 'utf8'),
).response;

test('the recap offers the forge instead of «More practice» when it is given', () => {
  const props = {
    journey: FIXTURE,
    recap: FIXTURE.recap,
    language: 'fr',
    onExit: () => {},
    morePractice: { label: '', onSelect: () => {} },
  };
  const withForge = decode(
    renderToStaticMarkup(h(JourneyRecap, { ...props, forge: { label: forgeLabel('fr'), onSelect: () => {} } })),
  );
  assert.match(withForge, /Forger la règle du jour/);
  assert.match(withForge, /data-forge="after-day"/);
  assert.doesNotMatch(withForge, /Plus d’exercices/);
  const without = decode(renderToStaticMarkup(h(JourneyRecap, props)));
  assert.doesNotMatch(without, /Forger la règle du jour/);
  assert.match(without, /Plus d’exercices/);
});

// ---------------------------------------------------------------------------
// 3. Folded into the day — Soutenu and Intensif
// ---------------------------------------------------------------------------

function forgeStep(forged, status = 'active') {
  return {
    id: 'forge-1',
    ordinal: 9,
    kind: 'forge',
    status,
    estimated_seconds: 330,
    assistance_used: [],
    prompt: {
      concept_id: 12,
      title_native: 'Gender and number',
      title_fr: 'Genre et nombre',
      budget_seconds: 330,
      href: '/atelier?mode=forge&concept=12&budget=330&step=forge-1',
      forged,
    },
  };
}

function renderStep(step, language, handlers = {}) {
  return decode(
    renderToStaticMarkup(
      h(ForgeStepView, {
        step,
        copy: journeyCopy(language),
        busy: false,
        onContinue: handlers.onContinue || (() => {}),
        onOpen: handlers.onOpen || (() => {}),
      }),
    ),
  );
}

test('the forge step opens the block, or leads back to the scene once forged', () => {
  const before = renderStep(forgeStep(false), 'en');
  assert.match(before, /data-step="forge"/);
  assert.match(before, /Forge · 6 min/);
  assert.match(before, /Forge today’s rule/);
  assert.match(before, /Genre et nombre/);
  assert.match(before, /Not now/);
  assert.equal((before.match(/av2-headline/g) || []).length, 1, 'one Garamond line per screen');

  const after = renderStep(forgeStep(true), 'de');
  assert.match(after, /data-forged="true"/);
  assert.match(after, /Zurück zur Szene/);
  assert.doesNotMatch(after, /Regel des Tages schmieden<\/button>/);

  const fr = renderStep(forgeStep(false), 'fr');
  assert.match(fr, /Forger la règle du jour/);
});

test('the session renders the forge step and opens its href', () => {
  const session = fs.readFileSync(path.join(__dirname, 'JourneySession.tsx'), 'utf8');
  assert.match(session, /step\.kind === 'forge'/);
  assert.match(session, /<ForgeStepView/);
  assert.match(session, /onOpen=\{openForge\}/);
});

function journeyWith(steps, current) {
  return { status: 'active', current_step_id: current, steps };
}

test('the day mark’s yellow square includes the folded forge', () => {
  assert.equal(dayMarkGroupOf('forge'), 'recall');
  assert.equal(STEP_SHAPE.forge, STEP_SHAPE.recall);
  const step = (id, kind, status) => ({ id, kind, status, ordinal: 0, estimated_seconds: 1, assistance_used: [], prompt: {} });
  const recallsDone = [
    step('w', 'recall', 'completed'),
    step('s', 'scene', 'completed'),
    step('f', 'forge', 'active'),
    step('r', 'respond', 'pending'),
    step('e', 'resolution', 'pending'),
  ];
  assert.equal(dayMarkState(journeyWith(recallsDone, 'f'), 'en').groups.recall, 'active');
  const forged = recallsDone.map((item) => (item.id === 'f' ? { ...item, status: 'completed' } : item));
  assert.equal(dayMarkState(journeyWith(forged, 'r'), 'en').groups.recall, 'done');
  // A day with no recall step but a forge still draws its yellow square.
  const onlyForge = recallsDone.filter((item) => item.id !== 'w');
  assert.notEqual(dayMarkState(journeyWith(onlyForge, 'f'), 'en').groups.recall, 'absent');
});

// ---------------------------------------------------------------------------
// 4. The chosen rule is seated
// ---------------------------------------------------------------------------

test('an open séance answers only a request for the rule it leads with', () => {
  const page = fs.readFileSync(path.join(WEB_ROOT, 'pages/atelier.tsx'), 'utf8');
  assert.match(page, /const seatsAskedRule = !practiceConceptId\s*\|\| Number\(session\?\.concepts\?\.\[0\]\?\.id\) === practiceConceptId;/);
  assert.match(page, /seatsAskedRule && !forgeStepId/);
  // The forge block names its origin, length and day step to the server.
  assert.match(page, /request\.origin = forgeStepId \? 'journey' : 'after_day'/);
  assert.match(page, /request\.journey_step_id = forgeStepId/);
  // A folded block hands the learner back to the day.
  assert.match(page, /returnToForgedDay\(\)/);
});
