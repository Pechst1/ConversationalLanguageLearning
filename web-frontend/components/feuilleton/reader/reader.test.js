/* Reader unit tests — run with:  node --test components/feuilleton/reader/reader.test.js
 *
 * These cover the three properties the reader must not lose:
 *   1. the stage list is exactly what the server sent (no invented panels)
 *   2. reading position survives a reload and a word-help round trip
 *   3. browsing is separable from acting, and only one task is ever live
 */

const test = require('node:test');
const assert = require('node:assert/strict');

require('../../../node_modules/sucrase/register/ts');

const {
  allTasksAnswered,
  attemptsByTaskId,
  buildReaderStages,
  choiceOptions,
  correctionIsBranch,
  correctionIsPositive,
  liveTaskId,
  panelArtStatus,
  panelCaption,
  panelLines,
  readerCharacterKey,
  readerEpisodeLabel,
  readerTaskOrder,
  shortSpeakerName,
  speakerAccentKey,
  stageIsRevisit,
  stageReadState,
} = require('./panel-model.ts');

const {
  clampStageIndex,
  emptyReaderPosition,
  normalizeReaderPosition,
  readerStorageKey,
  resolveFurthest,
  resolveStartIndex,
  withAnswers,
  withStage,
} = require('./reader-position.ts');

const { lookupTerm, sentenceAround, tokenizeFrench } = require('./french-text.ts');

function panel(index, extra = {}) {
  return {
    id: `p${index}`,
    panel_index: index,
    title: `Planche ${index}`,
    beat: `beat ${index}`,
    image_url: `/media/p${index}.png`,
    overlay_payload: {
      bubbles: [{ speaker: 'Romane « Romy » Tremblay', speaker_id: 'romy', fr: `Réplique ${index}.`, en: `Line ${index}.` }],
      caption: { fr: `Légende ${index}`, en: `Caption ${index}` },
      tasks: [],
    },
    generation_metadata: {},
    ...extra,
  };
}

const SCENE = {
  id: 'scene-1',
  status: 'in_progress',
  title: 'Une lettre attend ta réponse.',
  episode_index: 2,
  serial_thread_id: 'thread-1',
  panels: [
    panel(1),
    panel(2, {
      overlay_payload: {
        bubbles: [{ speaker: 'Marin', speaker_id: 'marin', fr: 'Tu viens ?', en: 'Coming?' }],
        caption: { fr: 'Légende 2', en: '' },
        tasks: [{ id: 'task-a', task_type: 'choice', prompt: 'Que répondez-vous ?', options: ['A: Oui', 'B: Non'] }],
      },
    }),
    panel(3, { image_url: null, generation_metadata: { image_status: 'queued' } }),
  ],
  script_payload: {
    final_prompt: { id: 'task-final', task_type: 'short_sentence', prompt: 'Écrivez la dernière réplique.' },
    serial_context: { location: 'Lyon' },
  },
  hook: { unresolved_question: 'Qui a écrit la lettre ?', text: 'Romy garde l’enveloppe.' },
  attempts: [],
};

/* ---------------------------------------------------------------- 1. model */

test('stages are exactly the panels the server sent, plus one resolution', () => {
  const stages = buildReaderStages(SCENE);
  assert.equal(stages.length, 4);
  assert.deepEqual(stages.map((s) => s.kind), ['panel', 'panel', 'panel', 'resolution']);
  assert.deepEqual(stages.map((s) => s.key), ['panel:p1', 'panel:p2', 'panel:p3', 'resolution:scene-1']);
  assert.deepEqual(stages.map((s) => s.ordinal), [1, 2, 3, 4]);
});

test('an empty scene produces no stages — nothing is invented', () => {
  assert.deepEqual(buildReaderStages(null), []);
  assert.deepEqual(buildReaderStages({ id: 'x', panels: [], script_payload: {} }), []);
});

test('a reward edition surfaces no learner tasks', () => {
  const stages = buildReaderStages({
    ...SCENE,
    script_payload: { ...SCENE.script_payload, experience_mode: 'reward' },
  });
  assert.deepEqual(readerTaskOrder(stages), []);
});

test('art status is honest about printing versus simply absent', () => {
  assert.equal(panelArtStatus(panel(1)), 'ready');
  assert.equal(panelArtStatus({ id: 'q', image_url: null, generation_metadata: { image_status: 'queued' } }), 'printing');
  assert.equal(panelArtStatus({ id: 'q', image_url: null, generation_metadata: {} }), 'missing');
});

test('speaker identity resolves to a world-bible accent key', () => {
  assert.equal(readerCharacterKey('romy'), 'romy');
  assert.equal(readerCharacterKey('Romane « Romy » Tremblay'), 'romy');
  assert.equal(readerCharacterKey('Monsieur Marchand'), 'marchand');
  assert.equal(readerCharacterKey('Augustin'), 'gus');
  assert.equal(readerCharacterKey('quelqu’un'), '');
  assert.equal(shortSpeakerName('Romane « Romy » Tremblay'), 'Romy');
  const lines = panelLines(SCENE.panels[0]);
  assert.equal(lines.length, 1);
  assert.equal(lines[0].character, 'romy');
  assert.equal(lines[0].who, 'Romy');
});

test('an unnamed speaker still gets a stable, distinct accent', () => {
  // standalone editions come back with generic speakers and no speaker_id
  const clerk = speakerAccentKey('', 'Clerk');
  const supervisor = speakerAccentKey('', 'Supervisor');
  assert.ok(clerk, 'an unknown speaker is still given an accent');
  assert.notEqual(clerk, supervisor, 'two different speakers are not the same colour');
  assert.equal(speakerAccentKey('', 'Clerk'), clerk, 'the same speaker keeps its colour');
  // a world-bible speaker always wins over the fallback
  assert.equal(speakerAccentKey('romy', 'Clerk'), 'romy');
  // the learner is always ink
  assert.equal(speakerAccentKey('', 'Protagonist'), 'toi');
  assert.equal(speakerAccentKey('', ''), '');
});

test('a caption that only repeats the dialogue is not printed twice', () => {
  const echo = {
    id: 'e',
    overlay_payload: { bubbles: [{ fr: 'Bonjour.' }], caption: { fr: 'Bonjour.' } },
  };
  assert.equal(panelCaption(echo, panelLines(echo)), '');
  assert.equal(panelCaption(SCENE.panels[0], panelLines(SCENE.panels[0])), 'Légende 1');
});

test('episode label comes from the server index, never from a counter', () => {
  assert.equal(readerEpisodeLabel(SCENE), 'Épisode 3');
  assert.equal(readerEpisodeLabel({ id: 'x' }), 'Édition du jour');
});

test('choice options are parsed from both string and object payloads', () => {
  assert.deepEqual(
    choiceOptions({ options: ['A: Oui', { value: 'B', fr: 'Non', en: 'No' }] }),
    [
      { value: 'A', label: 'A', text: 'Oui', en: '' },
      { value: 'B', label: 'B', text: 'Non', en: 'No' },
    ],
  );
});

test('a branch is read as authorship, not as a wrong answer', () => {
  assert.equal(correctionIsBranch({ verdict: 'branch' }), true);
  assert.equal(correctionIsPositive({ verdict: 'branch' }), true);
  assert.equal(correctionIsPositive({ verdict: 'incorrect' }), false);
});

/* --------------------------------------------------- 2. browse versus act */

test('exactly one task is live, in reading order', () => {
  const stages = buildReaderStages(SCENE);
  assert.deepEqual(readerTaskOrder(stages), ['task-a', 'task-final']);
  assert.equal(liveTaskId(stages, {}), 'task-a');
  assert.equal(liveTaskId(stages, { 'task-a': { task_id: 'task-a' } }), 'task-final');
  assert.equal(
    liveTaskId(stages, { 'task-a': {}, 'task-final': {} }),
    null,
    'no task is live once every one has an attempt',
  );
});

test('attempts index by task id from the scene payload only', () => {
  const attempts = attemptsByTaskId({ attempts: [{ task_id: 'task-a', correction: { verdict: 'branch' } }] });
  assert.equal(attempts['task-a'].correction.verdict, 'branch');
  assert.deepEqual(attemptsByTaskId(null), {});
});

test('a passed stage reads as a revisit; the live one does not', () => {
  const stages = buildReaderStages(SCENE);
  const options = { furthestOrdinal: 3, liveTaskId: 'task-a' };
  assert.equal(stageReadState(stages[0], options), 'read');
  assert.equal(stageIsRevisit(stages[0], options), true);
  // panel 2 carries the live task, so it is where the learner is asked to act
  assert.equal(stageReadState(stages[1], options), 'current');
  assert.equal(stageIsRevisit(stages[1], options), false);
  assert.equal(stageReadState(stages[3], options), 'ahead');
});

test('all-answered is a fact about attempts, never about navigation', () => {
  const stages = buildReaderStages(SCENE);
  assert.equal(allTasksAnswered(stages, {}), false);
  assert.equal(allTasksAnswered(stages, { 'task-a': {} }), false);
  assert.equal(allTasksAnswered(stages, { 'task-a': {}, 'task-final': {} }), true);
});

/* ------------------------------------------------------------ 3. position */

test('the storage key is the one the reader has always used', () => {
  assert.equal(readerStorageKey('scene-1'), 'pilot:reader:scene-1');
});

test('a legacy {answers, scrollY} record still restores its draft', () => {
  const restored = normalizeReaderPosition({ answers: { 'task-a': 'Oui' }, scrollY: 240 });
  assert.deepEqual(restored.answers, { 'task-a': 'Oui' });
  assert.equal(restored.scrollY, 240);
  assert.equal(restored.stageIndex, 0);
  assert.equal(restored.furthest, 0);
});

test('garbage in storage degrades to a clean start', () => {
  assert.deepEqual(normalizeReaderPosition(null), emptyReaderPosition());
  assert.deepEqual(normalizeReaderPosition('nope'), emptyReaderPosition());
  assert.deepEqual(normalizeReaderPosition({ answers: { a: 3 }, stageIndex: 'x' }), emptyReaderPosition());
});

test('position survives a reload by stage identity, not by index', () => {
  const keys = ['panel:p1', 'panel:p2', 'panel:p3', 'resolution:scene-1'];
  const saved = normalizeReaderPosition({ stageKey: 'panel:p3', stageIndex: 2, furthest: 2 });
  assert.equal(resolveStartIndex(saved, keys), 2);
  // a panel arrived before the saved one; the identity still wins
  const grown = ['panel:p0', 'panel:p1', 'panel:p2', 'panel:p3', 'resolution:scene-1'];
  assert.equal(resolveStartIndex(saved, grown), 3);
  // the saved stage is gone: fall back to the index, clamped to what exists
  assert.equal(resolveStartIndex(saved, ['panel:pX']), 0);
});

test('restored progress can shrink to the real stage list but never inflate', () => {
  const saved = normalizeReaderPosition({ stageIndex: 5, furthest: 9 });
  assert.equal(resolveFurthest(saved, ['a', 'b'], 1), 1);
  assert.equal(resolveFurthest(saved, ['a', 'b', 'c', 'd', 'e', 'f'], 2), 5);
});

test('moving stage records the place and raises the furthest mark only forward', () => {
  const keys = ['a', 'b', 'c'];
  let position = emptyReaderPosition();
  position = withStage(position, 2, keys);
  assert.equal(position.stageIndex, 2);
  assert.equal(position.stageKey, 'c');
  assert.equal(position.furthest, 2);
  position = withStage(position, 0, keys);
  assert.equal(position.stageIndex, 0, 'the learner is back on the first stage');
  assert.equal(position.furthest, 2, 'but the furthest point read is unchanged');
});

test('a word-help round trip changes no position field', () => {
  const keys = ['a', 'b', 'c'];
  const before = withStage(withAnswers(emptyReaderPosition(), { t: 'brouillon' }), 1, keys);
  // opening and closing the sheet touches nothing in the record
  const after = { ...before };
  assert.deepEqual(after, before);
  assert.equal(after.stageIndex, 1);
  assert.deepEqual(after.answers, { t: 'brouillon' });
});

test('stage index is clamped to what the server actually sent', () => {
  assert.equal(clampStageIndex(-3, 4), 0);
  assert.equal(clampStageIndex(9, 4), 3);
  assert.equal(clampStageIndex(2, 0), 0);
});

/* --------------------------------------------------------- 4. word tokens */

test('words are tappable, punctuation is not', () => {
  const tokens = tokenizeFrench('Bonjour, Romy !');
  assert.deepEqual(tokens.map((t) => [t.text, t.word]), [
    ['Bonjour', true],
    [', ', false],
    ['Romy', true],
    [' !', false],
  ]);
});

test('élision keeps the content word tappable, not the article', () => {
  const tokens = tokenizeFrench("L'arrivée qu'il attend");
  const words = tokens.filter((t) => t.word).map((t) => t.term);
  // "L'" and "qu'" are clitics and stay inert; "il" is a real word and stays tappable.
  assert.deepEqual(words, ['arrivée', 'il', 'attend']);
  assert.equal(tokens.find((t) => t.text === 'L').word, false);
  assert.equal(tokens.find((t) => t.text === 'qu').word, false);
});

test('hyphenated compounds stay one lookup', () => {
  const tokens = tokenizeFrench('un rendez-vous demain');
  assert.deepEqual(tokens.filter((t) => t.word).map((t) => t.term), ['un', 'rendez-vous', 'demain']);
});

test('tokenizing is lossless', () => {
  const source = "Est-ce que l'on part ? Oui — demain, à 8h.";
  assert.equal(tokenizeFrench(source).map((t) => t.text).join(''), source);
});

test('lookup terms drop surrounding punctuation and case', () => {
  assert.equal(lookupTerm('« Bonjour ! »'), 'bonjour');
  assert.equal(lookupTerm('rendez-vous,'), 'rendez-vous');
});

test('the quoted context is the clause the word came from', () => {
  const line = 'Il pleut. Tu viens quand même ?';
  assert.equal(sentenceAround(line, 'viens'), 'Tu viens quand même ?');
  assert.equal(sentenceAround(line, 'pleut'), 'Il pleut.');
});
