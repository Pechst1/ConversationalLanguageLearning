// node --test components/courrier/courrier-held-reply.test.js
//
// Pilot P0, walk of 17 Nov (A1, Lila): after «Senden» the thread only said «Lila hat
// auf diese Nachricht noch nicht geantwortet», one «Noch einmal nachfragen» changed
// nothing visible, and nothing said Lila was writing while the button worked.
//
//   1. #1025 (live walk 23 Nov) undoes what pilot P0 first did here: the stock
//      acknowledgement printed in her voice («Lila : « Merci pour ton message, je l'ai
//      bien lu… »») read as Lila's answer to a real reply. The thread says plainly that
//      she has not answered yet and offers «Ask again»; no line nobody wrote is hers;
//   2. «… schreibt zurück» shows while a reply is asked for again, not only on send;
//   3. a retry that still brings no reply leaves a line under the message, not only a toast.

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

const PAGE = fs.readFileSync(path.join(WEB_ROOT, 'pages', 'missions.tsx'), 'utf8');
const pendingBlock = () => PAGE.slice(PAGE.indexOf('turnReplyPending(turn) &&'), PAGE.indexOf('<CrRepair'));

test('no chrome line puts a reply nobody wrote in the character\'s mouth', () => {
  const { courrierCopy, crFill } = require('./courrier-copy.ts');
  for (const lang of ['fr', 'en', 'de']) {
    const copy = courrierCopy(lang);
    assert.equal(copy.reply_held_line, undefined, `${lang}: a «{name}: {text}» line for a reply nobody wrote`);
    const pending = crFill(copy.reply_pending_line, { name: 'Lila' });
    assert.match(pending, /Lila/, `${lang}: the pending line does not name who has not answered`);
    assert.doesNotMatch(pending, /je l.ai bien lu/i);
    assert.ok(copy.reply_retry, `${lang}: no «Ask again»`);
  }
});

test('the unanswered message says nobody answered and offers «Ask again», never a held line', () => {
  const block = pendingBlock();
  assert.doesNotMatch(block, /held_reply/, 'a line the server held back is drawn as the character\'s words');
  assert.doesNotMatch(block, /reply_held_line/);
  assert.match(block, /crFill\(t\.reply_pending_line, \{ name: messenger\.contact_name \}\)/);
  assert.match(block, /t\.reply_retry/, '«Ask again» is not offered');
});

test('the writing sign shows while a reply is asked for again', () => {
  const typing = PAGE.slice(PAGE.lastIndexOf('{', PAGE.indexOf('className="cr-typing"')) - 80, PAGE.indexOf('className="cr-typing"'));
  assert.match(typing, /submitting \|\| retryingReply/, 'no «schreibt zurück» while «Noch einmal nachfragen» works');
});

test('a retry that brings no reply leaves a line on the thread', () => {
  const retry = PAGE.slice(PAGE.indexOf('const retryReply'), PAGE.indexOf('const finishMission'));
  assert.match(retry, /setRetryMissed\(/, 'a failed retry is only a toast');
  assert.match(pendingBlock(), /retryMissed === turn\.id[\s\S]*t\.toast_reply_retry_failed/);
});
