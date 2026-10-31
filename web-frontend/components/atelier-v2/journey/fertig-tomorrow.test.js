// node --test components/atelier-v2/journey/fertig-tomorrow.test.js
//
// #359 (root cause #143): the day ended on three screens that each said its own
// closing. Home's «Tomorrow · Deux promesses» came from the recap's teaser, the
// «Fertig für heute» screen the learner actually lands on printed counts and a
// curtain call and no teaser at all. The teaser is now ONE line, read through
// `tomorrowLine`, and both screens print it.

const assert = require('node:assert/strict');
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
const stub = (request, exports) => {
  const file = Module._resolveFilename(request, module, false);
  require.cache[file] = { id: file, filename: file, loaded: true, exports };
};
stub('@/services/api', { __esModule: true, default: {}, apiService: {} });
stub('next/router', { __esModule: true, useRouter: () => ({ push: () => {}, replace: () => {}, query: {}, pathname: '/fertig' }) });
stub('next/head', { __esModule: true, default: () => null });

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// `FertigPage` loads the day in an effect, which a static render never runs:
// hand it the envelope as its first state instead, so the page itself is what
// is under test.
const seed = { envelope: null, used: false };
const realUseState = React.useState;
React.useState = (initial) => {
  if (seed.envelope && !seed.used && initial === null) {
    seed.used = true;
    return [seed.envelope, () => {}];
  }
  return realUseState(initial);
};
const FertigPage = require('../../../pages/fertig.tsx').default;

const { JourneyTodayCard } = require('./JourneyTodayCard.tsx');
const state = require('./journey-state.ts');

const h = React.createElement;
const quiet = (fn) => {
  const original = console.error;
  console.error = () => {};
  try {
    return fn();
  } finally {
    console.error = original;
  }
};
const textOf = (html) =>
  html
    .replace(/<[^>]+>/g, ' ')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();

const SCENARIO = {
  scenario_key: 'k',
  content_version: '1',
  title_fr: 'Une lettre sans timbre',
  objective_key: 'o',
  objective_native: 'Ask Romy.',
  level_band: 'A1',
  character_id: 'romy_tremblay',
  character_name: 'Romy',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: '/scenario.webp',
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 300,
};

const TEASER_LINE = 'Toi, tu me caches quelque chose… Demain, peut-être, on saura : « Deux promesses : laquelle tenir ? »';

function recapOf(overrides = {}) {
  return {
    completion_kind: 'complete',
    objective_outcome: 'met',
    practiced_targets: [],
    capability_evidence: [],
    next_focus: null,
    collectible_ids: [],
    story_outcome: null,
    active_seconds: 300,
    teaser: { text_fr: 'Authored.', character_id: null, character_name: 'Romy', source: 'authored' },
    next_teaser_fr: TEASER_LINE,
    ...overrides,
  };
}

function envelopeOf(language, recap) {
  return {
    contract_version: 1,
    enabled: true,
    control_language: language,
    local_date: '2026-10-28',
    timezone: 'Europe/Paris',
    available: null,
    legacy_resume: null,
    practice_href: '/atelier?mode=practice',
    because: null,
    is_warm: false,
    missed_days: 0,
    journey: {
      id: 'j-16',
      contract_version: 1,
      revision: 3,
      status: 'completed',
      local_date: '2026-10-28',
      timezone: 'Europe/Paris',
      budget_seconds: 600,
      estimated_active_seconds: 300,
      current_step_id: null,
      scenario: SCENARIO,
      steps: [],
      recap,
      retry: null,
    },
    session: {
      pace: 'normal',
      steps: [
        { kind: 'scene', state: 'done', minutes: 0, href: null },
        { kind: 'words', state: 'done', minutes: 0, href: '/vocabulary/review?day=1', count: 13, new_left: 0, reviews: 0 },
        { kind: 'grammar', state: 'done', minutes: 0, href: '/atelier?mode=forge&from=day', count: 15 },
        { kind: 'finish', state: 'done', minutes: 0, href: '/fertig' },
      ],
      next_kind: null,
      minutes_left: 0,
      done: true,
      tally: { scenes: 1, words: 13, exercises: 15 },
      more_words: 10,
      more_minutes: 4,
      more_href: '/vocabulary/review?more=10',
    },
  };
}

function homeCard(envelope) {
  return quiet(() =>
    renderToStaticMarkup(
      h(JourneyTodayCard, {
        controller: {
          phase: state.phaseFromEnvelope(envelope),
          feedback: { kind: 'idle' },
          envelope,
          journey: envelope.journey,
          step: null,
          respondPrompt: null,
          controlLanguage: envelope.control_language,
          legacyResume: null,
          progress: state.journeyProgress(envelope.journey),
          busy: false,
          help: null,
          actions: new Proxy({}, { get: () => () => Promise.resolve() }),
        },
        onOpen: () => {},
      }),
    ),
  );
}

function fertig(envelope) {
  seed.envelope = envelope;
  seed.used = false;
  try {
    return quiet(() => renderToStaticMarkup(h(FertigPage)));
  } finally {
    seed.envelope = null;
  }
}

const hintOf = (html) => {
  const found = html.match(/<span class="av2-fr journey-today-card__hint" lang="fr">([^<]*)<\/span>/);
  return found ? textOf(found[1]) : null;
};

test('«Done for today» names tomorrow’s open question, the same words Home’s «Tomorrow» line prints', () => {
  for (const language of ['en', 'de', 'fr']) {
    const envelope = envelopeOf(language, recapOf());
    const onHome = hintOf(homeCard(envelope));
    assert.ok(onHome && onHome.includes('Deux promesses'), `${language}: Home prints the open question («${onHome}»)`);

    const html = fertig(envelope);
    assert.match(html, /data-fertig="done"/, `${language}: the page is the finished day`);
    const text = textOf(html);
    assert.ok(
      text.includes(onHome),
      `${language}: the Done screen has no «${onHome}» (tomorrow's open question); it reads «${text.slice(0, 160)}»`,
    );
    assert.match(html, /data-tomorrow/, `${language}: the line is marked as tomorrow's`);
  }
});

test('after an early stop the Done screen promises nothing for tomorrow', () => {
  const envelope = envelopeOf('en', recapOf({ completion_kind: 'early' }));
  envelope.journey.status = 'ended_early';
  assert.equal(hintOf(homeCard(envelope)), null, 'Home prints no teaser after an early stop');
  assert.doesNotMatch(fertig(envelope), /data-tomorrow/);
});

test('with no teaser the Done screen shows no empty «Tomorrow» label', () => {
  const envelope = envelopeOf('en', recapOf({ teaser: null, next_teaser_fr: null }));
  assert.doesNotMatch(fertig(envelope), /data-tomorrow/);
});
