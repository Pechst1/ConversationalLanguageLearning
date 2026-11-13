// node --test components/cahiers/journal-basic-check.test.js
//
// #754 — walk 13 Nov, no model on the stack. The Journal's «Your French» card said
// «Basic check only», drew no correction at all, then «One mistake is noted in Le
// Relevé», and offered «Check again» on a stack where no model could ever answer.
// The card must draw every fix it counts, and offer no retry for `no_model`.

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

const APOSTROPHE = { label: 'Spelling', span_fr: 'j étais', corrected_fr: "j'étais", note_native: 'An apostrophe is missing.' };
const NAME_M_A = { label: 'Spelling', span_fr: 'Gus m a', corrected_fr: "Gus m'a", note_native: 'An apostrophe is missing.' };

// What the server sent on main for the walk's retell: one fix found, none drawn up front.
const noModel = (errata, extra = {}) => ({
  id: 'e1',
  entry_text: "Gus m a demandé qui j étais, et Margaux m a donné un café crème.",
  errata_recorded: errata.length,
  correction: {
    assessment_status: 'checked',
    checker: 'deterministic',
    failure_reason: 'no_model',
    retryable: false,
    foreground: null,
    errata,
    corrected_answer: '',
    assessment_truncated: false,
    check: {
      outcome: 'not_checked',
      call: 'not_called',
      failure: 'no_model',
      retryable: false,
      edits: errata.map((item) => ({ span: item.span_fr, replacement: item.corrected_fr })),
    },
    ...extra,
  },
});

test('#754 · with no model the Journal offers no «Check again» that could never work', () => {
  const t = cahierCopy('en').journal;
  assert.equal(journal.canRetryCorrection(noModel([APOSTROPHE])), false, 'basic check, no model: no retry');
  assert.equal(journal.canRetryCorrection(noModel([])), false, 'nothing found, no model: no retry');
  // A payload from before `check` names no_model in its own fields.
  const legacy = noModel([]);
  delete legacy.correction.check;
  assert.equal(journal.canRetryCorrection(legacy), false, 'an old payload with no_model: no retry');
  // A model that failed is still worth asking again.
  const failed = noModel([APOSTROPHE], { failure_reason: 'model_error', retryable: true });
  failed.correction.check = { ...failed.correction.check, call: 'failed', failure: 'provider_error', retryable: true };
  assert.equal(journal.canRetryCorrection(failed), true);
  // Unread and unfixed, the card says checking is unavailable, not «not checked yet».
  assert.equal(journal.correctionLine(noModel([]), t), t.correction_check_unavailable);
  assert.doesNotMatch(journal.correctionLine(noModel([]), t), /not checked yet/);
});

test('#754 · the basic check draws the one fix it counts, and the count never exceeds what it draws', () => {
  for (const language of ['fr', 'en', 'de']) {
    const t = cahierCopy(language).journal;
    assert.ok(t.correction_why_no_model, `${language}: the no-model line exists`);
    const one = renderToStaticMarkup(React.createElement(journal.FrenchCheck, { entry: noModel([APOSTROPHE]), t }));
    assert.match(one, /j&#x27;étais|j'étais/, `${language}: «j étais → j'étais» is drawn`);
    assert.ok(one.includes(t.correction_basic), `${language}: under «basic check only»`);
    assert.ok(one.includes(t.errata_one), `${language}: the one noted mistake is the one shown`);
    assert.ok(!one.includes(t.retry_correction), `${language}: no retry with no model`);
    assert.ok(one.includes(t.correction_why_no_model), `${language}: says the full check is unavailable`);
  }
  const t = cahierCopy('fr').journal;
  // Three fixes, none chosen up front: the first is drawn and «Tout voir» opens all three.
  const three = noModel([NAME_M_A, APOSTROPHE, { ...NAME_M_A, span_fr: 'Margaux m a', corrected_fr: "Margaux m'a" }]);
  assert.equal(journal.shownCorrections(three).length, 3);
  assert.equal(journal.errataNoted(three), 3);
  const html = renderToStaticMarkup(React.createElement(journal.FrenchCheck, { entry: three, t }));
  assert.match(html, /Gus m&#x27;a|Gus m'a/);
  assert.ok(html.includes(t.show_all));
  // The server recorded more than the card lists: the line says what the card shows.
  const over = noModel([APOSTROPHE]);
  over.errata_recorded = 3;
  assert.equal(journal.errataNoted(over), 1);
  const nothing = noModel([]);
  nothing.errata_recorded = 1;
  assert.equal(journal.errataNoted(nothing), 0, '«a mistake is noted» over no correction');
});
