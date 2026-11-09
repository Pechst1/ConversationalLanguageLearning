// node --test lib/verdict.test.js
//
// #333: one screen state on every surface that judges what a learner wrote, in one set of
// words, and a `data-check` on each line so a walk can name it.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');

const WEB_ROOT = path.resolve(__dirname, '..');
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/ts'));
require(path.join(WEB_ROOT, 'node_modules/sucrase/register/tsx'));

const Module = require('node:module');
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function resolve(request, ...rest) {
  if (request.startsWith('@/')) return originalResolve.call(this, path.join(WEB_ROOT, request.slice(2)), ...rest);
  return originalResolve.call(this, request, ...rest);
};

const { CHECK_COPY, checkState, isUnread, fixRows } = require('./verdict.ts');
const read = (...parts) => fs.readFileSync(path.join(WEB_ROOT, ...parts), 'utf8');

const NOT_CHECKED = { outcome: 'not_checked', call: 'failed', edits: [] };
const BASIC = { ...NOT_CHECKED, edits: [{ span: 'tres', replacement: 'très' }] };

test('each result has one state, and only a verdict reads as settled', () => {
  assert.equal(checkState(NOT_CHECKED), 'not_checked');
  assert.equal(checkState(BASIC), 'basic');
  assert.equal(checkState({ outcome: 'not_checked', call: 'pending', edits: [] }), 'checking');
  assert.equal(checkState({ outcome: 'not_checked', call: 'empty', edits: [] }), 'not_checked');
  assert.equal(checkState({ outcome: 'not_checked', call: 'not_called', edits: [] }), 'not_checked');
  for (const outcome of ['right', 'partly', 'not_yet']) {
    assert.equal(checkState({ outcome, call: 'ok', edits: [] }), 'settled', outcome);
  }
  assert.equal(checkState(undefined), 'settled', 'an older server sends no check');
  assert.deepEqual(['not_checked', 'basic', 'checking', 'settled'].map(isUnread), [true, true, false, false]);
});

test('the words the owner approved, in all three languages', () => {
  assert.equal(CHECK_COPY.en.not_checked, "Answer saved, not checked yet. It doesn't count yet.");
  assert.equal(CHECK_COPY.de.not_checked, 'Antwort gespeichert, noch nicht geprüft. Sie zählt noch nicht.');
  assert.equal(CHECK_COPY.fr.not_checked, 'Réponse enregistrée, pas encore vérifiée. Elle ne compte pas encore.');
  assert.equal(CHECK_COPY.en.basic, 'Basic check only. The full check did not run.');
  assert.equal(CHECK_COPY.de.basic, 'Nur Grundprüfung. Die volle Prüfung lief nicht.');
  assert.equal(CHECK_COPY.fr.basic, 'Vérification de base seulement. La vérification complète n’a pas eu lieu.');
});

test('every surface takes its line from the one table', () => {
  const { courrierCopy } = require('../components/courrier/courrier-copy.ts');
  const { cahierCopy } = require('../components/cahiers/cahier-copy.ts');
  const { epreuveCopy } = require('../components/epreuve/epreuve-copy.ts');
  const { journeyCopy } = require('../components/atelier-v2/journey/journey-copy.ts');
  for (const language of ['en', 'de', 'fr']) {
    const words = CHECK_COPY[language];
    assert.equal(courrierCopy(language).unassessed, words.not_checked, `courrier ${language}`);
    assert.equal(courrierCopy(language).check_basic, words.basic, `courrier ${language}`);
    assert.equal(cahierCopy(language).journal.correction_unavailable, words.not_checked, `journal ${language}`);
    assert.equal(cahierCopy(language).journal.correction_basic, words.basic, `journal ${language}`);
    assert.equal(epreuveCopy(language).unscored, words.not_checked, `forge ${language}`);
    assert.equal(epreuveCopy(language).check_basic, words.basic, `forge ${language}`);
    assert.equal(journeyCopy(language).check_not_checked, words.not_checked, `scene and drills ${language}`);
  }
});

test('every surface marks the line for the walk', () => {
  for (const file of [
    ['pages', 'missions.tsx'],
    ['pages', 'atelier.tsx'],
    ['components', 'cahiers', 'JournalTab.tsx'],
    ['components', 'atelier-v2', 'journey', 'JourneySteps.tsx'],
    ['components', 'atelier-v2', 'journey', 'RespondThread.tsx'],
  ]) {
    assert.match(read(...file), /data-check=/, file.join('/'));
  }
});

test('the Journal says who read it, whatever the old payload field claims', () => {
  const { correctionLine, canRetryCorrection, journalCheckState } = require('../components/cahiers/JournalTab.tsx');
  const { cahierCopy } = require('../components/cahiers/cahier-copy.ts');
  const t = cahierCopy('en').journal;
  const rulesOnly = { correction: { assessment_status: 'checked', checker: 'deterministic', retryable: true, errata: [{ span_fr: 'tres' }], check: BASIC } };
  const nothing = { correction: { assessment_status: 'checked', checker: 'deterministic', retryable: true, errata: [], check: NOT_CHECKED } };
  const read_ = { correction: { assessment_status: 'checked', checker: 'model', errata: [], check: { outcome: 'right', call: 'ok', edits: [] } } };
  assert.equal(correctionLine(rulesOnly, t), t.correction_basic);
  assert.equal(correctionLine(nothing, t), t.correction_unavailable);
  assert.equal(correctionLine(read_, t), t.correction_clean);
  assert.equal(canRetryCorrection(rulesOnly), true);
  assert.equal(canRetryCorrection(read_), false);
  // An older server: a deterministic pass is not a model's check.
  assert.equal(journalCheckState({ correction: { assessment_status: 'checked', checker: 'deterministic', errata: [] } }), 'not_checked');
  assert.equal(journalCheckState({ correction: { assessment_status: 'checked', errata: [] } }), 'settled');
});

test('a letter closed on an unread message prints no verdict, goals or mood', () => {
  const { crOutcomeLabel, crOutcomeSentence } = require('../components/courrier/Correspondance.tsx');
  const { crSealNumbers } = require('../components/courrier/Courrier.tsx');
  const { courrierCopy } = require('../components/courrier/courrier-copy.ts');
  for (const language of ['fr', 'en', 'de']) {
    const copy = courrierCopy(language);
    assert.equal(crOutcomeLabel('partial', language, { unchecked: true }), copy.outcome_unchecked);
    assert.notEqual(copy.outcome_unchecked, copy.outcome_partial);
    assert.match(crOutcomeSentence('partial', 'Camille', language, { unchecked: true }), /Camille/);
  }
  const rows = crSealNumbers({ objectives_met: 1, objectives_total: 1, words_written: 12, unchecked: true });
  assert.ok(!rows.some((row) => row.value === '1/1'), 'goals 1/1 printed for a letter nobody read');
  assert.match(read('pages', 'missions.tsx'), /!letterHeld\.unanswered && !letterHeld\.unchecked/);
});

test('#133 · two or more mechanical fixes share one line, where the first of them stood', () => {
  const rows = fixRows([
    { wrong: 'c est', fixed: "c'est", why: 'a' },
    { wrong: 'je vend', fixed: 'je vends', why: 'b' },
    { wrong: 'Qu est-ce', fixed: "Qu'est-ce", why: 'c' },
    { wrong: 'a', fixed: 'à', why: 'd' },
    { wrong: 'aujourdhui', fixed: "aujourd'hui", why: 'e' },
  ]);
  assert.deepEqual(rows, [
    { kind: 'apostrophes', fixes: ["c'est", "Qu'est-ce", "aujourd'hui"] },
    { kind: 'one', fixed: 'je vends', why: 'b' },
    { kind: 'one', fixed: 'à', why: 'd' },
  ]);
});

test('#133 · one mechanical fix keeps its own reason, and a real fix never joins a group', () => {
  assert.deepEqual(fixRows([{ wrong: 'tres', fixed: 'très', why: 'accent' }]), [
    { kind: 'one', fixed: 'très', why: 'accent' },
  ]);
  const rows = fixRows([
    { wrong: 'la restaurant', fixed: 'le restaurant', why: 'x' },
    { wrong: 'une bon', fixed: 'un bon', why: 'y' },
  ]);
  assert.equal(rows.length, 2);
  assert.ok(rows.every((row) => row.kind === 'one'));
});

