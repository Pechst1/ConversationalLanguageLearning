// node --test components/courrier/courrier-no-reply.test.js
//
// #397 (child of #333) — a reply nobody wrote is shown as «not answered yet»,
// and the walks read the Courrier in the learner's time zone.
//
//   1. the server marks a turn nobody answered `reply_state: 'pending'`; the page
//      says so, in all three chrome languages (since #782 the composer still empties:
//      the message went out, see courrier-sent-clears.test.js);
//   2. every walk driver gives its browser a time zone, so the Courrier's stamps
//      are the learner's hours and not the machine's UTC (#316 «again»).

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..', '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');

test('a turn the server marks pending is a reply nobody gave', () => {
  const { replyPending } = require('./mission-turns.ts');
  assert.equal(replyPending({ reply_state: 'pending' }), true);
  assert.equal(replyPending({ reply_text: 'Ah bon ?', branch: {} }), false);
  assert.equal(replyPending(undefined), false);
  assert.equal(replyPending(null), false);
});

test('the page says nobody answered', () => {
  const page = read('pages', 'missions.tsx');
  const send = page.slice(page.indexOf('const sendReply'), page.indexOf('const recheckReply'));
  assert.match(send, /replyPending\(result\.outcome\)\) toast\(t\.toast_reply_pending\)/, 'sendReply never says nobody answered');
});

test('the pending line exists in every chrome language and is not the stock reply', () => {
  const { courrierCopy } = require('./courrier-copy.ts');
  for (const lang of ['fr', 'en', 'de']) {
    const line = courrierCopy(lang).toast_reply_pending;
    assert.ok(line && line.length > 20, `${lang}: no pending line`);
    assert.doesNotMatch(line, /je l.ai bien lu/i);
  }
});

// #590 — the thread itself says which learner message nobody answered, the reply can be
// asked for again from there, and a letter finished on it prints no verdict.

test('the thread marks the learner turn nobody answered', () => {
  const { turnReplyPending } = require('./mission-turns.ts');
  assert.equal(turnReplyPending({ role: 'user', reply_state: 'pending' }), true);
  assert.equal(turnReplyPending({ role: 'user' }), false);
  assert.equal(turnReplyPending({ role: 'assistant', reply_state: 'pending' }), false);
  assert.equal(turnReplyPending(undefined), false);
});

test('the page prints the pending line under the turn and offers to ask again', () => {
  const page = read('pages', 'missions.tsx');
  assert.match(page, /turnReplyPending\(turn\) &&/);
  assert.match(page, /t\.reply_pending_line/);
  assert.match(page, /apiService\.retryMissionTurnReply\(mission\.id, turnId\)/);
});

test('asking again keeps the unsent draft in the composer', () => {
  const page = read('pages', 'missions.tsx');
  const retry = page.slice(page.indexOf('const retryReply'), page.indexOf('const finishMission'));
  assert.ok(retry.includes('retryMissionTurnReply'), 'retry handler not found');
  assert.doesNotMatch(retry, /setReply\(/);
  assert.doesNotMatch(retry, /pilot:mission-draft/);
});

test('a letter finished on an unanswered message prints no verdict, goals or mood', () => {
  const { crOutcomeLabel, crOutcomeSentence } = require('./Correspondance.tsx');
  const { crSealNumbers } = require('./Courrier.tsx');
  const { courrierCopy } = require('./courrier-copy.ts');
  for (const lang of ['fr', 'en', 'de']) {
    const copy = courrierCopy(lang);
    assert.equal(crOutcomeLabel('kept', lang, { unanswered: true }), copy.outcome_unanswered);
    assert.notEqual(crOutcomeLabel('kept', lang, { unanswered: true }), copy.outcome_kept);
    assert.match(crOutcomeSentence('kept', 'Camille', lang, { unanswered: true }), /Camille/);
    for (const key of ['reply_pending_line', 'reply_retry', 'reply_retrying', 'toast_reply_retry_failed']) {
      assert.ok(copy[key] && copy[key].length > 5, `${lang}: ${key} missing`);
    }
  }
  const rows = crSealNumbers({ objectives_met: 1, objectives_total: 1, words_written: 12, reply_pending: true });
  assert.ok(!rows.some((row) => row.value === '1/1'), 'goals 1/1 printed for an unanswered letter');
  assert.ok(crSealNumbers({ objectives_met: 1, objectives_total: 1 }).some((row) => row.value === '1/1'));
});

test('every walk driver sets a time zone on its browser context', () => {
  for (const file of ['walk.mjs', 'explore.mjs', 'appels-walk.mjs', 'explore-live.mjs']) {
    const source = read('e2e', file);
    assert.match(source, /newContext\([^;]*timezoneId: WALK_TIMEZONE/s, `${file} walks in the machine's time zone`);
  }
  const zone = read('e2e', 'lib', 'walk-timezone.mjs');
  assert.match(zone, /Europe\/Berlin/);
});
