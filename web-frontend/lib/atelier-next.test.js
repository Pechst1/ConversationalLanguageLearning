const assert = require('node:assert/strict');

require('../node_modules/sucrase/register/ts');

const {
  buildDayProgress,
  dayProgressStorageKey,
  dayQueryString,
  resolveRecommendedNext,
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
    feuilletonDone: false,
  }),
  { kind: 'resume_session', conceptIndex: 2, round: 'sentence', mode: 'write' },
);

assert.deepEqual(
  resolveRecommendedNext(today, null, {
    sessionStatus: 'none',
    errataDue: 0,
    vocabularyDue: 0,
    missionDone: false,
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
    feuilletonDone: false,
  }),
  { kind: 'mission', query: '?concept_id=7&atelier_session_id=atelier-1' },
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
    feuilletonDone: true,
  },
);

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
    feuilletonDone: false,
  },
);

console.log('atelier-next resolver tests passed');
