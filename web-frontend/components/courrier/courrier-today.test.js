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

// ---- 3. the thread reads in the order of its times --------------------------

test('turns are listed by stored time, newest last, the counter breaking ties', () => {
  const { inStoredOrder } = require('@/lib/clock-time.ts');
  const turns = [
    { id: 1, turn_index: 1, created_at: '2026-10-31T02:58:00+00:00' },
    { id: 2, turn_index: 2, created_at: '2026-10-31T02:57:00+00:00' },
    { id: 3, turn_index: 3, created_at: '2026-10-31T03:11:00+00:00' },
    { id: 4, turn_index: 4, created_at: '2026-10-31T03:02:00+00:00' },
    { id: 5, turn_index: 5, created_at: '2026-10-31T02:57:00+00:00' },
    { id: 6, turn_index: 6 },
  ];
  assert.deepEqual(inStoredOrder(turns).map((turn) => turn.id), [2, 5, 1, 4, 3, 6]);
});

test('the page lists its turns through that function', () => {
  assert.match(read('pages', 'missions.tsx'), /inStoredOrder\(/);
});
