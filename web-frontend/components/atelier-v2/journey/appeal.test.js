// node --test components/atelier-v2/journey/appeal.test.js
//
// Package V stage 5: «I think this is right» under a drill's «not yet» or «partly». One quiet
// line, in en, de and fr; upheld turns the verdict, anything else keeps it and says why.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '../../..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const { appealOffered, feedbackAfterAppeal } = require('./journey-state.ts');
const { journeyCopy } = require('./journey-copy.ts');

const miss = {
  task_outcome: 'not_yet',
  assistance_level: 'none',
  check: { outcome: 'not_yet', checked_by: 'key', call: 'not_called', counts: true, edits: [] },
};
const graded = { kind: 'graded', verdict: 'incorrect', result: miss, replySource: 'unknown' };

test('the line is offered under a drill\'s «not yet» or «partly», and nowhere else', () => {
  assert.equal(appealOffered(miss, 'recall'), true);
  assert.equal(appealOffered({ ...miss, check: { ...miss.check, outcome: 'partly' } }, 'recall'), true);
  assert.equal(appealOffered({ ...miss, check: { ...miss.check, outcome: 'right' } }, 'recall'), false);
  assert.equal(appealOffered({ ...miss, check: { ...miss.check, outcome: 'not_checked' } }, 'recall'), false);
  assert.equal(appealOffered(miss, 'respond'), false);
  assert.equal(appealOffered({ ...miss, appeal: { state: 'refused', reason: null } }, 'recall'), false, 'once only');
});

test('upheld turns the verdict; refused, unread and the limit keep it and say so', () => {
  const right = { ...miss.check, outcome: 'right', checked_by: 'model', call: 'ok' };
  const upheld = feedbackAfterAppeal(graded, { state: 'upheld', reason: 'Oui.' }, right);
  assert.equal(upheld.kind, 'graded');
  assert.equal(upheld.verdict, 'correct');
  assert.equal(upheld.result.check.outcome, 'right');
  assert.equal(upheld.result.appeal.state, 'upheld');

  for (const state of ['refused', 'unread', 'limit']) {
    const kept = feedbackAfterAppeal(graded, { state, reason: state === 'refused' ? 'Non.' : null }, null);
    assert.equal(kept.verdict, 'incorrect');
    assert.equal(kept.result.appeal.state, state);
  }
});

test('every line exists in en, de and fr, and the French one is the owner\'s words', () => {
  const keys = ['appeal_line', 'appeal_upheld', 'appeal_refused', 'appeal_unread', 'appeal_limit'];
  for (const language of ['en', 'de', 'fr']) {
    const copy = journeyCopy(language);
    for (const key of keys) assert.ok(String(copy[key] || '').trim(), `${language}.${key}`);
  }
  assert.equal(journeyCopy('fr').appeal_line, 'Je pense que c’est juste');
  assert.match(journeyCopy('de').appeal_upheld, /^Du /, 'du, not Sie');
  assert.match(journeyCopy('fr').appeal_upheld, /^Tu /, 'tu, not vous');
});

test('the line is the quiet action and notice already on the sheet: no new shape, colour or slab', () => {
  const source = fs.readFileSync(path.join(__dirname, 'JourneySteps.tsx'), 'utf8');
  const block = source.slice(source.indexOf('function AppealLine'), source.indexOf('export function JourneyFeedbackView'));
  assert.match(block, /<Action\s+tone="quiet"/);
  assert.match(block, /<Notice tone="quiet">/);
  assert.doesNotMatch(block, /#[0-9a-fA-F]{3,6}|uppercase|style=\{/);
  assert.match(block, /data-appeal=/);
});

// #729: the 12 Nov walk's item. «In welchem Satz steckt die Regel von heute?», the pick
// «Il pleut.», the key «C'est qui, vous ?». An upheld appeal turned the band «Richtig» and
// left the miss's reveal under it: «In diesem Satz steckt die Regel: C'est qui, vous ? ·
// Nicht dieser: Il pleut.». Upheld is one state: the item is right everywhere.
test('an upheld appeal leaves no trace of the miss on the sheet: no reveal of the key, no struck pick', () => {
  const apiPath = Module._resolveFilename('@/services/api', module, false);
  require.cache[apiPath] = {
    id: apiPath, filename: apiPath, loaded: true, exports: { __esModule: true, default: {}, apiService: {} },
  };
  const React = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const { JourneyFeedbackView } = require('./JourneySteps.tsx');

  const pick = {
    ...miss,
    correction: {
      kind: 'pick',
      span_fr: 'Il pleut.',
      corrected_fr: 'C’est qui, vous ?',
      note_native: 'Être heißt sein: je suis, tu es, il est.',
      notes_native: [],
    },
  };
  const sheet = { kind: 'graded', verdict: 'incorrect', result: pick, replySource: 'unknown' };
  const right = { ...miss.check, outcome: 'right', checked_by: 'model', call: 'ok' };
  const upheld = feedbackAfterAppeal(sheet, { state: 'upheld', reason: 'Ja.' }, right);
  const de = journeyCopy('de');
  const html = renderToStaticMarkup(
    React.createElement(JourneyFeedbackView, {
      feedback: upheld,
      copy: de,
      stepKind: 'recall',
      onContinue() {},
      onRetry() {},
      onDismiss() {},
      onAppeal: async () => {},
    }),
  );

  assert.equal(upheld.verdict, 'correct');
  assert.ok(html.includes(de.correct), `«${de.correct}» on the band`);
  assert.ok(!html.includes(de.pick_not_it), `no «${de.pick_not_it}» under «${de.correct}»`);
  assert.ok(!html.includes(de.correction_pick), `no «${de.correction_pick}» under «${de.correct}»`);
  assert.ok(!html.includes('Il pleut.'), 'the pick is not struck through');
  assert.ok(!html.includes('av2-correction'), 'no reveal of the key at all');

  // A refused appeal keeps the miss, reveal and all.
  const refused = feedbackAfterAppeal(sheet, { state: 'refused', reason: 'Nein.' }, null);
  assert.equal(refused.result.correction.span_fr, 'Il pleut.');
});
