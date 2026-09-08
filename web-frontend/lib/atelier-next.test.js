const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');

const {
  buildDayProgress,
  dayProgressStorageKey,
  dayQueryString,
  legacyResumeEntry,
  resolveJourneyNext,
  resolveLegacyRecommendedNext,
  resolveRecommendedNext,
  resolvePracticeEntry,
  practiceHref,
  PRACTICE_LABEL,
  serialQueryString,
} = require('./atelier-next.ts');

const today = {
  concepts: [{ id: 42 }],
  quote: {},
  summary: { due_errata: 0 },
  atlas: [],
  due_errata: [],
};

const session = {
  session_id: 'atelier-1',
  status: 'active',
  concepts: [{ id: 7 }],
  quote: {},
  target_vocabulary_ids: [],
  target_vocabulary: [],
  exercise_sets: [],
  attempts: [],
  submitted_map: {},
  current_position: { concept_index: 2, concept_id: 7, round: 'sentence', mode: 'write' },
  due_errata: [],
  recap: {},
};

assert.deepEqual(
  resolveRecommendedNext(today, session, {
    sessionStatus: 'active',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: false,
    libraryDone: true,
    feuilletonDone: false,
  }),
  { kind: 'resume_session', conceptIndex: 2, round: 'sentence', mode: 'write', itemIndex: 0 },
);

assert.deepEqual(
  resolveRecommendedNext(today, null, {
    sessionStatus: 'none',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: false,
    libraryDone: true,
    feuilletonDone: false,
  }),
  { kind: 'start_session' },
);

assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, {
    sessionStatus: 'completed',
    errataDue: 1,
    vocabularyDue: 2,
    missionDone: false,
    libraryDone: true,
    feuilletonDone: false,
  }),
  { kind: 'review', errataDue: 1, vocabularyDue: 2 },
);

assert.deepEqual(
  resolveRecommendedNext(
    { ...today, serial_episode: { thread_id: 'thread-1', kind: 'mission', episode_index: 0, mission_id: 'mission-1' } },
    { ...session, status: 'completed' },
    {
      sessionStatus: 'completed',
      errataDue: 1,
      vocabularyDue: 2,
      missionDone: false,
      libraryDone: true,
      feuilletonDone: false,
    },
  ),
  {
    kind: 'serial',
    threadId: 'thread-1',
    episodeKind: 'mission',
    query: '?serial_thread_id=thread-1&episode_index=0&mission=mission-1',
  },
);

assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, {
    sessionStatus: 'completed',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: false,
    missionSuggested: true,
    libraryDone: true,
    feuilletonDone: false,
  }),
  { kind: 'mission', query: '?concept_id=7&atelier_session_id=atelier-1' },
);

assert.deepEqual(
  resolveRecommendedNext(
    {
      ...today,
      library_episode: {
        book_id: 'book-1',
        episode_index: 2,
        href: '/notebook?mode=library&book=book-1&episode=2',
        title: 'The letter',
        book_title: 'Petit Test',
      },
    },
    { ...session, status: 'completed' },
    {
      sessionStatus: 'completed',
      errataDue: 0,
      vocabularyDue: 0,
      missionDone: false,
      missionSuggested: false,
      libraryDone: false,
      librarySuggested: true,
      feuilletonDone: false,
    },
  ),
  { kind: 'feuilleton', query: '?concept_id=7&atelier_session_id=atelier-1' },
);

assert.deepEqual(
  resolveRecommendedNext(
    {
      ...today,
      library_episode: {
        book_id: 'book-1',
        episode_index: 2,
        href: '/notebook?mode=library&book=book-1&episode=2',
        title: 'The letter',
        book_title: 'Petit Test',
      },
    },
    { ...session, status: 'completed' },
    {
      sessionStatus: 'completed',
      errataDue: 0,
      vocabularyDue: 0,
      missionDone: false,
      missionSuggested: false,
      libraryDone: true,
      librarySuggested: false,
      feuilletonDone: false,
    },
  ),
  { kind: 'feuilleton', query: '?concept_id=7&atelier_session_id=atelier-1' },
);

assert.deepEqual(
  resolveRecommendedNext(
    { ...today, serial_episode: { thread_id: 'thread-1', kind: 'feuilleton', episode_index: 3, scene_id: 'scene-1' } },
    { ...session, status: 'completed' },
    {
      sessionStatus: 'completed',
      errataDue: 0,
      vocabularyDue: 0,
      missionDone: false,
      libraryDone: true,
      feuilletonDone: false,
    },
  ),
  {
    kind: 'serial',
    threadId: 'thread-1',
    episodeKind: 'feuilleton',
    query: '?serial_thread_id=thread-1&episode_index=3&scene=scene-1',
  },
);

assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, {
    sessionStatus: 'completed',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: true,
    libraryDone: true,
    feuilletonDone: false,
  }),
  { kind: 'feuilleton', query: '?concept_id=7&atelier_session_id=atelier-1' },
);

assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, {
    sessionStatus: 'completed',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: true,
    libraryDone: true,
    feuilletonDone: true,
  }),
  { kind: 'rest' },
);

assert.equal(dayQueryString(null, today), '?concept_id=42');
assert.equal(
  serialQueryString({ thread_id: 'thread-2', kind: 'mission', episode_index: 1, mission_id: 'mission-1' }),
  '?serial_thread_id=thread-2&episode_index=1&mission=mission-1',
);
assert.equal(dayProgressStorageKey(new Date('2026-05-30T12:00:00Z')), 'atelier:progress:2026-05-30');
assert.deepEqual(
  buildDayProgress({
    today: {
      ...today,
      summary: { due_errata: 3 },
      progress: {
        errataDue: 2,
        vocabularyDue: 5,
        missionDone: false,
        feuilletonDone: true,
      },
    },
    session: { ...session, status: 'completed', current_position: { round: 'complete' } },
    vocabularyDue: 4,
  }),
  {
    sessionStatus: 'completed',
    errataDue: 2,
    vocabularyDue: 5,
    missionDone: false,
    missionSuggested: false,
    libraryDone: true,
    librarySuggested: false,
    feuilletonDone: true,
    studioDone: false,
    studioSuggested: false,
    sessionDone: true,
    timeBudgetMinutes: 20,
    estimatedTotalMinutes: 24,
    estimatedRemainingMinutes: 24,
    filed: false,
    nodes: [
      {
        id: 'vocabulary',
        label: 'Vocabulary',
        estimatedMinutes: 4,
        done: false,
        suggested: true,
      },
    ],
  },
);

global.window = {
  localStorage: {
    getItem: () => JSON.stringify({ missionDone: true, feuilletonDone: true }),
  },
};
assert.equal(buildDayProgress({ today, session: null }).missionDone, true);
assert.equal(buildDayProgress({ today, session: null }).feuilletonDone, true);
delete global.window;

const recoveredVocabularyProgress = buildDayProgress({
  today: {
    ...today,
    progress: {
      errataDue: 0,
      vocabularyDue: 0,
      missionDone: false,
      feuilletonDone: false,
    },
  },
  session: { ...session, status: 'completed', current_position: { round: 'complete' } },
  vocabularyDue: 6,
});

assert.equal(recoveredVocabularyProgress.vocabularyDue, 6);
assert.deepEqual(recoveredVocabularyProgress.nodes[0], {
  id: 'vocabulary',
  label: 'Vocabulary',
  estimatedMinutes: 4,
  done: false,
  suggested: true,
});

assert.deepEqual(
  buildDayProgress({
    today,
    session: { ...session, status: 'in_progress' },
    vocabularyDue: 0,
  }),
  {
    sessionStatus: 'active',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: false,
    missionSuggested: false,
    libraryDone: true,
    librarySuggested: false,
    feuilletonDone: false,
    studioDone: false,
    studioSuggested: false,
    sessionDone: false,
    timeBudgetMinutes: 20,
    estimatedTotalMinutes: 20,
    estimatedRemainingMinutes: 20,
    filed: false,
    nodes: [],
  },
);


// ---------------------------------------------------------------------------
// Atelier V2 — capability-aware precedence (WP-07)
//
// Frozen in CONTRACT-FREEZE.md, "Frontend recommendation precedence".
// Every case above this block is the pre-V2 behaviour and must keep passing
// unchanged: that is the `enabled === false` guarantee.
// ---------------------------------------------------------------------------

const journeyScenario = {
  scenario_key: 'order_at_cafe',
  content_version: 'journey-content-v1',
  title_fr: 'Un café au Mistral',
  objective_key: 'order_at_cafe.counter_drink',
  objective_native: 'Order a hot drink at the counter.',
  level_band: 'A1',
  character_id: 'margaux_barman',
  character_name: 'Margaux',
  location_id: 'le_mistral',
  location_name: 'Le Mistral',
  image_url: null,
  serial_thread_id: null,
  serial_episode_id: null,
  estimated_seconds: 264,
};

function journeySnapshot(overrides = {}) {
  return {
    id: 'journey-1',
    contract_version: 1,
    revision: 3,
    status: 'active',
    local_date: '2026-09-05',
    timezone: 'Europe/Paris',
    budget_seconds: 300,
    estimated_active_seconds: 264,
    current_step_id: null,
    scenario: journeyScenario,
    steps: [],
    recap: null,
    retry: null,
    ...overrides,
  };
}

function envelope(overrides = {}) {
  return {
    contract_version: 1,
    enabled: true,
    control_language: 'en',
    local_date: '2026-09-05',
    timezone: 'Europe/Paris',
    journey: null,
    available: null,
    legacy_resume: null,
    ...overrides,
  };
}

const idleProgress = {
  sessionStatus: 'completed',
  errataDue: 0,
  vocabularyDue: 0,
  missionDone: true,
  libraryDone: true,
  feuilletonDone: true,
};

const startableProgress = {
  sessionStatus: 'none',
  errataDue: 0,
  vocabularyDue: 0,
  missionDone: false,
  libraryDone: true,
  feuilletonDone: false,
};

// enabled === false returns EXACTLY the legacy answer, for every progress shape.
for (const progress of [idleProgress, startableProgress]) {
  assert.deepEqual(
    resolveRecommendedNext(today, { ...session, status: 'completed' }, progress, envelope({ enabled: false })),
    resolveLegacyRecommendedNext(today, { ...session, status: 'completed' }, progress),
  );
  // A missing envelope is identical to a disabled one.
  assert.deepEqual(
    resolveRecommendedNext(today, { ...session, status: 'completed' }, progress, null),
    resolveRecommendedNext(today, { ...session, status: 'completed' }, progress),
  );
}

// A disabled envelope carrying a journey still yields the legacy chain: the
// server response is authoritative and `enabled` is the only gate.
assert.deepEqual(
  resolveRecommendedNext(today, null, startableProgress, envelope({
    enabled: false,
    journey: journeySnapshot(),
    available: journeyScenario,
  })),
  { kind: 'start_session' },
);

// 1. Active journey -> resume, ahead of "start_session".
assert.deepEqual(
  resolveRecommendedNext(today, null, startableProgress, envelope({ journey: journeySnapshot() })),
  {
    kind: 'journey_resume',
    journeyId: 'journey-1',
    status: 'active',
    scenarioKey: 'order_at_cafe',
    titleFr: 'Un café au Mistral',
  },
);

// 1b. Paused counts as open too.
assert.equal(
  resolveRecommendedNext(today, null, startableProgress, envelope({
    journey: journeySnapshot({ status: 'paused' }),
  })).kind,
  'journey_resume',
);

// 2. Preparing carries the server's retry hint and never starts a second one.
assert.deepEqual(
  resolveRecommendedNext(today, null, startableProgress, envelope({
    journey: journeySnapshot({ status: 'preparing', retry: { allowed: true, after_seconds: 3 } }),
    available: journeyScenario,
  })),
  { kind: 'journey_preparing', journeyId: 'journey-1', retryAllowed: true, retryAfterSeconds: 3 },
);

// 3. Unavailable offers retry AND carries the legacy chain's own answer.
const unavailable = resolveRecommendedNext(today, { ...session, status: 'completed' }, idleProgress, envelope({
  journey: journeySnapshot({ status: 'unavailable', retry: { allowed: true, after_seconds: 30 } }),
}));
assert.equal(unavailable.kind, 'journey_unavailable');
assert.equal(unavailable.retryAllowed, true);
assert.equal(unavailable.retryAfterSeconds, 30);
assert.deepEqual(
  unavailable.fallback,
  resolveLegacyRecommendedNext(today, { ...session, status: 'completed' }, idleProgress),
);

// 4. completed / ended_early fall through: the day's journey is done, and
//    re-entering it must not inflate progress, so no journey branch is returned.
for (const status of ['completed', 'ended_early']) {
  assert.equal(resolveJourneyNext(envelope({ journey: journeySnapshot({ status }) }), { kind: 'rest' }), null);
  assert.deepEqual(
    resolveRecommendedNext(today, { ...session, status: 'completed' }, idleProgress, envelope({
      journey: journeySnapshot({ status }),
    })),
    { kind: 'rest' },
  );
}

// 5. No journey but a scenario on offer -> start today's journey.
assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, idleProgress, envelope({
    available: journeyScenario,
  })),
  {
    kind: 'journey_start',
    scenarioKey: 'order_at_cafe',
    titleFr: 'Un café au Mistral',
    estimatedSeconds: 264,
  },
);

// 6. Enabled but nothing offered -> the legacy chain, unchanged.
assert.deepEqual(
  resolveRecommendedNext(today, { ...session, status: 'completed' }, idleProgress, envelope()),
  { kind: 'rest' },
);

// `legacy_resume` is orthogonal to all six branches: it survives every one of
// them, including the branch that resumes a V2 journey.
const withLegacy = envelope({
  journey: journeySnapshot(),
  legacy_resume: { href: '/atelier?session=abc', session_id: 'abc' },
});
assert.equal(resolveRecommendedNext(today, null, startableProgress, withLegacy).kind, 'journey_resume');
assert.deepEqual(legacyResumeEntry(withLegacy), { href: '/atelier?session=abc', sessionId: 'abc' });
assert.equal(legacyResumeEntry(envelope()), null);
assert.equal(legacyResumeEntry(null), null);
// Even a disabled envelope keeps the legacy resume readable.
assert.deepEqual(
  legacyResumeEntry(envelope({ enabled: false, legacy_resume: { href: '/atelier?session=z', session_id: 'z' } })),
  { href: '/atelier?session=z', sessionId: 'z' },
);

// ---------------------------------------------------------------------------
// WP-16 / decision D-0 — one daily Séance
// ---------------------------------------------------------------------------

// The drill loop's href is entered by concept, never by "today".
assert.equal(practiceHref(), '/atelier?mode=practice');
assert.equal(practiceHref(12), '/atelier?mode=practice&concept=12');
assert.equal(practiceHref(''), '/atelier?mode=practice');
assert.equal(practiceHref(null), '/atelier?mode=practice');

// Flag off: no «Plus de pratique» secondary at all — the legacy Séance is then
// the day's own primary action, and must not also appear as a secondary line.
assert.equal(resolvePracticeEntry(null), null);
assert.equal(resolvePracticeEntry(undefined), null);
assert.equal(resolvePracticeEntry(envelope({ enabled: false, practice_href: '/atelier?mode=practice&concept=3' })), null);

// Flag on, no recap: the envelope's own practice href.
assert.deepEqual(
  resolvePracticeEntry(envelope({ practice_href: '/atelier?mode=practice&concept=3' })),
  { label: PRACTICE_LABEL, href: '/atelier?mode=practice&concept=3', conceptId: null },
);
// Flag on and the server sent no href at all: the bare practice entry, never a
// guessed concept.
assert.deepEqual(
  resolvePracticeEntry(envelope()),
  { label: PRACTICE_LABEL, href: '/atelier?mode=practice', conceptId: null },
);

// Flag on with a finished journey: the recap's own grammar target wins, so the
// drill loop opens on what today's scene actually practised.
const recapEnvelope = envelope({
  practice_href: '/atelier?mode=practice&concept=3',
  journey: journeySnapshot({
    status: 'completed',
    recap: {
      completion_kind: 'complete',
      objective_outcome: 'met',
      practiced_targets: [
        {
          target: { kind: 'vocabulary', id: '900', label_fr: 'la note' },
          evidence_kind: 'recognized',
          assistance_level: 'none',
          practice_href: null,
        },
        {
          target: { kind: 'grammar', id: '77', label_fr: 'le passé composé' },
          evidence_kind: 'produced_independent',
          assistance_level: 'none',
          practice_href: '/atelier?mode=practice&concept=77',
        },
      ],
      capability_evidence: [],
      next_focus: null,
      collectible_ids: [],
      story_outcome: null,
      active_seconds: null,
    },
  }),
});
assert.deepEqual(resolvePracticeEntry(recapEnvelope), {
  label: PRACTICE_LABEL,
  href: '/atelier?mode=practice&concept=77',
  conceptId: '77',
});

// The one primary action. A learner who has NOT started the legacy session and
// whose journey is finished used to be sent straight back into the legacy
// Séance as the day's recommendation; under D-0 the drill loop is never the
// primary, so the chain answers with the rest of the day instead.
const finishedJourney = envelope({ journey: journeySnapshot({ status: 'completed' }) });
assert.equal(
  resolveLegacyRecommendedNext(today, null, startableProgress).kind,
  'start_session',
);
assert.notEqual(
  resolveRecommendedNext(today, null, startableProgress, finishedJourney).kind,
  'start_session',
);
assert.equal(
  resolveRecommendedNext(today, null, startableProgress, finishedJourney).kind,
  resolveLegacyRecommendedNext(today, null, startableProgress, { skipSession: true }).kind,
);
// An ACTIVE legacy session is likewise not resumed as the day's primary action.
assert.notEqual(
  resolveRecommendedNext(today, session, { ...startableProgress, sessionStatus: 'active' }, finishedJourney).kind,
  'resume_session',
);

// `skipSession` is opt-in only: without it the chain is byte-for-byte the old
// one, for every progress shape.
for (const progress of [idleProgress, startableProgress, { ...startableProgress, sessionStatus: 'active' }]) {
  assert.deepEqual(
    resolveLegacyRecommendedNext(today, session, progress, undefined),
    resolveLegacyRecommendedNext(today, session, progress),
  );
}

// An unavailable journey is an infrastructure failure, not a finished day: it
// keeps the FULL legacy chain in its fallback, session included, so a broken
// generator never also removes the learner's practice.
const unavailableWithSession = resolveRecommendedNext(today, null, startableProgress, envelope({
  journey: journeySnapshot({ status: 'unavailable', retry: { allowed: false, after_seconds: 30 } }),
}));
assert.equal(unavailableWithSession.kind, 'journey_unavailable');
assert.equal(unavailableWithSession.fallback.kind, 'start_session');

console.log('atelier-next resolver tests passed');
