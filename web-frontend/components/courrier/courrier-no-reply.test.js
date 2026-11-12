// node --test components/courrier/courrier-no-reply.test.js
//
// #397 (child of #333) — a reply nobody wrote is shown as «not answered yet»,
// and the walks read the Courrier in the learner's time zone.
//
//   1. the server marks a turn nobody answered `reply_state: 'pending'`; the page
//      keeps the text in the composer and says so, in all three chrome languages;
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

test('the page keeps the text and says nobody answered', () => {
  const page = read('pages', 'missions.tsx');
  const send = page.slice(page.indexOf('const sendReply'), page.indexOf('const recheckReply'));
  const pending = send.indexOf('replyPending(result.outcome)');
  assert.ok(pending > 0, 'sendReply never looks at the pending state');
  assert.ok(pending < send.indexOf("setReply('')"), 'the composer is emptied before the pending state is read');
  assert.match(send.slice(pending, send.indexOf("setReply('')")), /toast\(t\.toast_reply_pending\)/);
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
  // #693: the line and the press are drawn by CrReplyPending (tested below).
  assert.match(read('components', 'courrier', 'Courrier.tsx'), /t\.reply_pending_line/);
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

// #693 — live walk 11 Nov: Lila never answered, «Ask again» was pressed, and for 15 s nothing
// changed: no reply, no error. The press only swapped its words for a moment and the failure
// was a toast, so the thread read exactly as before and the learner could not tell whether
// the retry ran, failed or was still going. The thread now draws that state itself: busy with
// a spinner while the call runs, and a line under the message once a retry came back empty.

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const h = React.createElement;
const decode = (s) => s.replace(/&#x27;/g, "'").replace(/&amp;/g, '&').replace(/&quot;/g, '"');
const renderIn = (language, element) => {
  const { AtelierV2Root } = require('@/components/atelier-v2/ui/AtelierV2Root.tsx');
  return decode(renderToStaticMarkup(h(AtelierV2Root, { language }, element)));
};
const unanswered = (extra = {}) => ({ id: 't1', role: 'user', reply_state: 'pending', reply_attempts: 1, ...extra });

function replyPendingView() {
  const { CrReplyPending } = require('./Courrier.tsx');
  assert.equal(typeof CrReplyPending, 'function', 'nothing on the thread draws the state of an unanswered message');
  return CrReplyPending;
}

test('while the reply is asked for again the press is busy, spins and is really disabled', () => {
  const CrReplyPending = replyPendingView();
  const { courrierCopy } = require('./courrier-copy.ts');
  for (const language of ['fr', 'en', 'de']) {
    const t = courrierCopy(language);
    const html = renderIn(language, h(CrReplyPending, { name: 'Lila', turn: unanswered(), retrying: true, onRetry() {} }));
    assert.match(html, /aria-busy="true"/, `${language}: the press is not busy while the call runs`);
    assert.match(html, /disabled=""/, `${language}: a second tap can queue a second call`);
    assert.match(html, /av2-btn__spinner/, `${language}: no spinner while the call runs`);
    assert.ok(html.includes(t.reply_retrying), `${language}: the press does not say it is trying again`);
  }
});

test('a reply asked again that came back empty says so under the message, and can be asked once more', () => {
  const CrReplyPending = replyPendingView();
  const { courrierCopy, crFill } = require('./courrier-copy.ts');
  for (const language of ['fr', 'en', 'de']) {
    const t = courrierCopy(language);
    const before = renderIn(language, h(CrReplyPending, { name: 'Lila', turn: unanswered(), onRetry() {} }));
    const after = renderIn(
      language,
      h(CrReplyPending, { name: 'Lila', turn: unanswered({ reply_attempts: 2, reply_asked_local_time: '05 h 42' }), onRetry() {} }),
    );
    assert.notEqual(after, before, `${language}: a failed «Ask again» leaves the thread exactly as it was`);
    const failed = crFill(t.reply_retry_failed_line || '', { name: 'Lila', time: '05 h 42' });
    assert.ok(failed && after.includes(failed), `${language}: no line says the retry ran and failed`);
    assert.ok(after.includes(t.reply_retry), `${language}: the learner cannot ask once more`);
    assert.doesNotMatch(after, /aria-busy/, `${language}: a finished retry still reads as running`);
    assert.ok(!before.includes(failed), `${language}: a first miss already reads as a failed retry`);
    const untimed = renderIn(language, h(CrReplyPending, { name: 'Lila', turn: unanswered({ reply_attempts: 2 }), onRetry() {} }));
    assert.ok(untimed.includes(crFill(t.reply_retry_failed_line_untimed, { name: 'Lila' })), `${language}: no failure line without a time`);
  }
});

test('a retry that did not reach the server is shown as failed on the thread, not only in a toast', () => {
  const CrReplyPending = replyPendingView();
  const { courrierCopy, crFill } = require('./courrier-copy.ts');
  const t = courrierCopy('en');
  const html = renderIn('en', h(CrReplyPending, { name: 'Lila', turn: unanswered(), failed: true, onRetry() {} }));
  assert.ok(html.includes(crFill(t.reply_retry_failed_line_untimed, { name: 'Lila' })));
});

test('a finished letter keeps the unanswered line but offers no retry', () => {
  const CrReplyPending = replyPendingView();
  const { courrierCopy, crFill } = require('./courrier-copy.ts');
  const t = courrierCopy('en');
  const html = renderIn('en', h(CrReplyPending, { name: 'Lila', turn: unanswered() }));
  assert.ok(html.includes(crFill(t.reply_pending_line, { name: 'Lila' })));
  assert.ok(!html.includes(t.reply_retry));
});

test('the page draws every unanswered message with its retry state and the call in flight', () => {
  const page = read('pages', 'missions.tsx');
  const drawn = page.match(/<CrReplyPending[\s\S]*?\/>/);
  assert.ok(drawn, 'the page draws the unanswered message by hand, without its retry state');
  assert.match(drawn[0], /retrying=\{retryingReply === turn\.id\}/, 'the press is not busy while its call runs');
  assert.match(drawn[0], /failed=\{/, 'a retry that never reached the server is not shown on the thread');
});
