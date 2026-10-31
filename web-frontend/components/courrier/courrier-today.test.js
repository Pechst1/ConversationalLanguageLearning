// node --test components/courrier/courrier-today.test.js
//
// #397 / #400 — what the Courrier opens, what Home's letter row opens, and what
// the Courrier says about a reply it has not checked.
//
//   1. Home's «New letter» row and the Courrier tab pick their target from one
//      function (`courrierTarget`), so they cannot name two different letters;
//      with no letter pending the row is hidden;
//   2. a reply the corrector could not check never reads «No corrections found»,
//      in any of the three chrome languages (the Journal's basic check, which is
//      the same claim, is held to the same rule);
//   3. the thread is listed in the order of the times it prints, newest last.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const { courrierCopy } = require('./courrier-copy.ts');
const Waiting = require('./courrier-waiting.tsx');

const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');
const mission = (id, status, extra = {}) => ({ id, status, title: `Lettre ${id}`, ...extra });
const LILA = { name: 'Lila', id: 'lila' };

// ---- 1. one function picks the letter ---------------------------------------

test('the Courrier page does not keep its own idea of which letter is today\'s', () => {
  const page = read('pages', 'missions.tsx');
  assert.doesNotMatch(page, /function pickMission/, 'the page still orders the day\'s missions itself');
  assert.match(page, /courrierTarget/);
});

test('Home\'s letter row links to the mission the Courrier opens', () => {
  const waiting = mission('m-lila', 'available', { correspondent: LILA, courrier: { origin: 'story_born' } });
  const done = mission('m-weekly', 'completed');
  // The week's letter is already answered; Lila's letter is the one that waits.
  const today = { active_mission: null, weekly_mission: done, post_session_recommendation: waiting };

  const target = Waiting.courrierTarget(today);
  const entry = Waiting.courrierHomeEntry(Waiting.courrierAwaitingLetter(today));

  assert.equal(target.mission.id, 'm-lila', 'the Courrier opened the answered weekly letter');
  assert.equal(target.waiting, true);
  assert.equal(entry.href, '/missions?mission=m-lila');
  assert.equal(entry.href, `/missions?mission=${target.mission.id}`);
});

test('Home and the Courrier agree on every shape of the day', () => {
  const waiting = (id) => mission(id, 'available');
  const started = (id) => mission(id, 'in_progress');
  const done = (id) => mission(id, 'completed');
  const lapsed = (id) => mission(id, 'lapsed');
  const days = [
    { active_mission: waiting('a'), weekly_mission: waiting('w'), post_session_recommendation: null },
    { active_mission: null, weekly_mission: done('w'), post_session_recommendation: waiting('p') },
    { active_mission: lapsed('a'), weekly_mission: started('w'), post_session_recommendation: waiting('p') },
    { active_mission: null, weekly_mission: null, post_session_recommendation: started('p') },
    { active_mission: started('a'), weekly_mission: done('w'), post_session_recommendation: done('p') },
  ];
  for (const today of days) {
    const target = Waiting.courrierTarget(today);
    const entry = Waiting.courrierHomeEntry(Waiting.courrierAwaitingLetter(today));
    assert.ok(entry, JSON.stringify(today));
    assert.equal(entry.href, `/missions?mission=${target.mission.id}`, JSON.stringify(today));
  }
});

test('with no letter pending the row is hidden and the Courrier has only a finished one to show', () => {
  const today = { active_mission: null, weekly_mission: mission('w', 'completed'), post_session_recommendation: null };
  const target = Waiting.courrierTarget(today);
  assert.equal(target.waiting, false);
  assert.equal(target.mission.id, 'w');
  assert.equal(Waiting.courrierHomeEntry(Waiting.courrierAwaitingLetter(today)), null);
  assert.equal(Waiting.courrierTarget(null).mission, null);
  assert.equal(Waiting.courrierTarget({}).mission, null);
});

// ---- 2. an unchecked reply is not a clean one -------------------------------

const CLAIMS_NOTHING_FOUND = /(no|aucune|keine|rien|nothing|nichts)\b.{0,24}(correction|korrektur|to correct|zu korrigieren)/i;

test('«unchecked» never reads «No corrections found», in any chrome language', () => {
  for (const language of ['en', 'fr', 'de']) {
    const line = courrierCopy(language).unassessed;
    assert.ok(line && line.length > 0, language);
    assert.doesNotMatch(line, CLAIMS_NOTHING_FOUND, `${language}: «${line}» says a reply with errors is clean`);
  }
});

test('the Journal\'s model-free check does not say nothing was found either', () => {
  const { cahierCopy } = require('../cahiers/cahier-copy.ts');
  for (const language of ['en', 'fr', 'de']) {
    const line = cahierCopy(language).journal.correction_clean_basic;
    assert.ok(line && line.length > 0, language);
    assert.doesNotMatch(line, CLAIMS_NOTHING_FOUND, `${language}: «${line}»`);
  }
});

// ---- 3. the thread reads in the conversation's order --------------------------

test('the page lists turns by the turn counter, the order the conversation took', () => {
  // #397 / review on #411: the composer reads the last assistant turn from this list,
  // so an older reply with a later stamp must never move below the real last one.
  const page = read('pages', 'missions.tsx');
  assert.match(page, /from '@\/components\/courrier\/mission-turns'/);
  assert.doesNotMatch(page, /function missionTurns|function currentComposerInstruction|inStoredOrder\(/);
  assert.match(read('components', 'courrier', 'mission-turns.ts'), /function missionTurns[\s\S]{0,400}turn_index/);
});

test('the composer answers the highest turn index even when an earlier reply carries a later time', () => {
  const Turns = require('./mission-turns.ts');
  const t = courrierCopy('en');
  const base = { label: 'base', instruction: 'base', placeholder: 'base' };
  // An old thread: the reply at turn 2 was stamped after the actual latest reply at turn 4.
  const thread = {
    id: 'm-old',
    turns: [
      { id: 3, turn_index: 3, role: 'user', text: 'Et le marché ?', created_at: '2026-10-31T02:55:00+00:00' },
      {
        id: 2,
        turn_index: 2,
        role: 'assistant',
        text: 'Merci, à demain.',
        created_at: '2026-10-31T03:30:00+00:00',
        audio_payload: { branch: { state: 'understood' } },
      },
      {
        id: 4,
        turn_index: 4,
        role: 'assistant',
        text: 'Le marché ouvre à quelle heure ?',
        created_at: '2026-10-31T03:00:00+00:00',
        audio_payload: { branch: { state: 'clarify' } },
      },
      { id: 1, turn_index: 1, role: 'user', text: 'Bonjour Lila !', created_at: '2026-10-31T02:50:00+00:00' },
    ],
  };

  assert.deepEqual(Turns.missionTurns(thread).map((turn) => turn.id), [1, 2, 3, 4]);
  assert.equal(Turns.latestAssistantTurn(thread).id, 4);

  const copy = Turns.currentComposerInstruction(thread, base, t);
  assert.equal(copy.label, t.composer_label_reply, 'the stale «understood» reply closed the thread');
  assert.notEqual(copy.instruction, t.composer_instruction_last);
  assert.match(copy.instruction, /Le marché ouvre à quelle heure/);
});
