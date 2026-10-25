// node --test components/cahiers/journal-followup.test.js
//
// #337 — the Journal's «One week later» Reply made the question vanish with no
// result at all: the server only ever sent an *unanswered* follow-up, so the
// answered one had nothing to show. The learner must always get one visible
// result line after answering.

const assert = require('node:assert/strict');
const path = require('node:path');
const Module = require('node:module');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) {
    return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  }
  return originalResolve.call(this, request, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const { cahierCopy } = require('./cahier-copy.ts');
const journal = require('./JournalTab.tsx');

const answered = (extra = {}) => ({
  entry_id: 'e1',
  prompt_fr: 'Et la semaine dernière, avec Lila ?',
  due_on: '2026-10-25',
  answered: true,
  text: 'Lila avait un chat.',
  signal: 'used_again_later',
  ...extra,
});

test('an answered week-later line always yields exactly one result sentence', () => {
  assert.equal(typeof journal.followupResultLine, 'function', 'the journal has a result sentence for the follow-up');
  const en = cahierCopy('en').journal;
  assert.equal(
    journal.followupResultLine(answered({ facts_total: 1, facts_matched: 1 }), en),
    'You recalled everything the scene kept (1/1).',
  );
  assert.equal(
    journal.followupResultLine(answered({ facts_total: 3, facts_matched: 1 }), en),
    'You recalled 1 of 3 details.',
  );
  assert.equal(
    journal.followupResultLine(answered({ signal: 'not_recalled', facts_total: 2, facts_matched: 0 }), en),
    'None of what the scene kept appears (0/2).',
  );
  // An older server, or a scene with nothing scored, still ends in a line.
  for (const language of ['fr', 'en', 'de']) {
    const t = cahierCopy(language).journal;
    const line = journal.followupResultLine(answered({ signal: 'not_recalled' }), t);
    assert.ok(line && line.trim(), `${language}: a fallback line`);
    assert.equal(journal.followupResultLine(null, t), null, 'no answered follow-up, no line');
    assert.equal(journal.followupResultLine({ ...answered(), answered: false }, t), null);
  }
});

test('the answered follow-up renders its result where the question was', () => {
  assert.equal(typeof journal.FollowupResult, 'function', 'the journal renders the follow-up result');
  const t = cahierCopy('en').journal;
  const html = renderToStaticMarkup(
    React.createElement(journal.FollowupResult, { followup: answered({ facts_total: 1, facts_matched: 1 }), t }),
  );
  assert.match(html, /You recalled everything the scene kept \(1\/1\)\./);
  assert.match(html, /role="status"/);
  assert.match(html, /One week later/);
});
